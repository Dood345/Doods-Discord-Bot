"""Messages Cave couldn't answer while the model was down, answered later in the order they came in.

When a mention gets no reply from the model, the message's IDs (never its text) go into `ai_backlog`.
They're answered oldest-first after the next reply that works, or when a backed-off health check sees
Ollama answering again. Each one is re-fetched first (so edits and deletions are respected), replied to
with a "catching up" note, and the model is told the message is late; tools that act on the present
without a confirm card (skip_song) are withheld for those replies.
"""

import asyncio
import hashlib
import logging
import re
import time
from datetime import datetime
from typing import Awaitable, Callable, List, NamedTuple, Optional
from zoneinfo import ZoneInfo

import aiohttp
import discord

from config import BotConfig
from utils.ai_handler import CARD_ONLY
from utils.members import find_member
from utils.streaming import ReplyStreamer

logger = logging.getLogger(__name__)

ERROR_REPLY = "🤖 *confused processing noises* (AI error)"
QUEUED_NOTE = "\n-# I'll get back to this once my brain is back online."
MAX_PENDING = 10              # messages kept in total...
MAX_PER_USER = 3              # ...and per user (the rest are dropped)
MAX_AGE = 6 * 3600            # older than this isn't worth answering
MAX_ATTEMPTS = 3              # a message that fails this many catch-up tries is dropped
BACKOFF = [60, 120, 300, 600]  # seconds between health checks while Ollama stays down


class Outcome(NamedTuple):
    status: str               # ok | cooldown (an anti-spam line, not the model) | busy | failed
    text: Optional[str] = None


class Pending(NamedTuple):
    message_id: int
    channel_id: int
    user_id: int
    created_at: float
    attempts: int


def mention_text(content: str, bot_id: int) -> str:
    """The message without Cave's own mention (others stay); 'Hello!' if that leaves nothing."""
    return re.sub(rf"<@!?{bot_id}>", "", content or "").strip() or "Hello!"


def text_key(content: str, bot_id: int) -> str:
    """Hash of the normalized text: spots a re-ask without storing what was said."""
    normalized = " ".join(mention_text(content, bot_id).lower().split())
    return hashlib.sha1(normalized.encode()).hexdigest()


async def reply_context_for(message) -> Optional[str]:
    if not (message.reference and message.reference.message_id):
        return None
    try:
        ref = await message.channel.fetch_message(message.reference.message_id)
        return f"REPLIED TO -> {ref.author.display_name}: {ref.content}"
    except Exception:
        return None  # deleted or inaccessible


async def answer_mention(bot, message, *, on_fail: Optional[Callable[[], Awaitable[str]]] = None,
                         late_since: Optional[str] = None, prefix: str = "", user=None) -> Outcome:
    """Run the chat agent for a message that mentions Cave and stream the reply.

    `on_fail()` gives the text to post if the model fails (live messages). `user` overrides the author
    (a re-fetched message's author is a plain User; tools like queue_song need the Member).
    """
    handler = bot.ai_handler
    guild_id = message.guild.id if message.guild else None
    streamer = ReplyStreamer(message, prefix=prefix)
    reply_context = await reply_context_for(message)
    # Decided with no await before get_chat_response claims the user, so it can't change in between
    if late_since and message.author.id in handler._busy_users:
        return Outcome("busy")
    cooling = not late_since and handler.would_cooldown(message.author.id)
    async with message.channel.typing():
        response = await handler.get_chat_response(
            message.author.id, mention_text(message.content, bot.user.id), guild_id,
            reply_context=reply_context, user=user or message.author, guild=message.guild,
            channel=message.channel, on_text=streamer.update, late_since=late_since, card_only_ok=True)
    if response == CARD_ONLY:
        if streamer.reply is not None:  # text that streamed before the card went up
            try:
                await streamer.reply.delete()
            except discord.HTTPException:
                pass
        return Outcome("ok", response)
    if response:
        await streamer.finish(response)
        return Outcome("cooldown" if cooling else "ok", response)
    if on_fail:
        await streamer.finish(await on_fail())
    elif streamer.reply is not None:
        try:
            await streamer.reply.delete()  # a half-streamed catch-up reply that then failed
        except discord.HTTPException:
            pass
    return Outcome("failed")


class AIBacklog:
    def __init__(self, db, bot, clock=time.time, tz: Optional[ZoneInfo] = None):
        self.db = db
        self.bot = bot
        self.clock = clock
        self.tz = tz or ZoneInfo(BotConfig.BOT_TIMEZONE)
        self._lock = asyncio.Lock()
        self._fails = 0
        self._next_check = 0.0
        self._tasks = set()

    # --- Store ----------------------------------------------------------------

    async def add(self, message) -> bool:
        """Remember a message the model couldn't answer; False if it's over the caps."""
        now = self.clock()
        async with self.db.get_connection() as conn:
            await conn.execute("DELETE FROM ai_backlog WHERE created_at < ?", (now - MAX_AGE,))
            async with conn.execute("SELECT COUNT(*), SUM(user_id = ?) FROM ai_backlog", (message.author.id,)) as cur:
                total, mine = await cur.fetchone()
            if total >= MAX_PENDING or (mine or 0) >= MAX_PER_USER:
                await conn.commit()
                return False
            cur = await conn.execute(
                "INSERT OR IGNORE INTO ai_backlog (message_id, channel_id, user_id, created_at, text_key) "
                "VALUES (?, ?, ?, ?, ?)",
                (message.id, message.channel.id, message.author.id, message.created_at.timestamp(),
                 text_key(message.content, self.bot.user.id)))
            await conn.commit()
            return cur.rowcount > 0

    async def pending(self) -> List[Pending]:
        async with self.db.get_connection() as conn:
            async with conn.execute("SELECT message_id, channel_id, user_id, created_at, attempts FROM ai_backlog "
                                    "WHERE created_at >= ? ORDER BY created_at, message_id",
                                    (self.clock() - MAX_AGE,)) as cur:
                return [Pending(*row) for row in await cur.fetchall()]

    async def remove(self, message_id: int):
        async with self.db.get_connection() as conn:
            await conn.execute("DELETE FROM ai_backlog WHERE message_id = ?", (message_id,))
            await conn.commit()

    async def _bump(self, message_id: int) -> int:
        async with self.db.get_connection() as conn:
            await conn.execute("UPDATE ai_backlog SET attempts = attempts + 1 WHERE message_id = ?", (message_id,))
            async with conn.execute("SELECT attempts FROM ai_backlog WHERE message_id = ?", (message_id,)) as cur:
                row = await cur.fetchone()
            await conn.commit()
        return row[0] if row else MAX_ATTEMPTS

    # --- Catching up ------------------------------------------------------------

    async def after_success(self, message) -> None:
        """A live reply worked: drop this user's re-asks of the same thing, then answer the backlog."""
        self._fails, self._next_check = 0, 0.0
        async with self.db.get_connection() as conn:
            cur = await conn.execute("DELETE FROM ai_backlog WHERE user_id = ? AND channel_id = ? AND text_key = ?",
                                     (message.author.id, message.channel.id, text_key(message.content, self.bot.user.id)))
            await conn.commit()
            if cur.rowcount:
                logger.info(f"Dropped {cur.rowcount} missed message(s) that were asked again")
        task = asyncio.create_task(self.drain())
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    def _late_label(self, created_at: float) -> str:
        when = datetime.fromtimestamp(created_at, self.tz)
        same_day = when.date() == datetime.fromtimestamp(self.clock(), self.tz).date()
        clock = when.strftime("%I:%M %p").lstrip("0")
        return f"at {clock}" if same_day else f"on {when.strftime('%a')} at {clock}"

    async def _fetch(self, item: Pending):
        """The original message, or None if it's gone (deleted, channel gone, no access)."""
        channel = self.bot.get_channel(item.channel_id)
        if channel is None:
            channel = await self.bot.fetch_channel(item.channel_id)  # DMs aren't cached after a restart
        return await channel.fetch_message(item.message_id)

    async def drain(self) -> int:
        """Answer pending messages oldest-first; stops at the first one the model fails on."""
        if self._lock.locked():
            return 0
        answered = 0
        async with self._lock:
            for item in await self.pending():
                if item.user_id in self.bot.ai_handler._busy_users:
                    continue  # they're talking to Cave right now; their old message waits for the next pass
                try:
                    message = await self._fetch(item)
                except (discord.NotFound, discord.Forbidden):
                    await self.remove(item.message_id)
                    continue
                except discord.HTTPException as e:
                    logger.warning(f"Couldn't fetch a missed message: {e}")
                    break
                if not any(getattr(u, "id", None) == self.bot.user.id for u in getattr(message, "mentions", [])):
                    await self.remove(item.message_id)  # edited so it no longer asks Cave
                    continue
                prefix = f"-# ⏰ Catching up on this from <t:{int(item.created_at)}:R>; my brain was offline.\n"
                user = await find_member(message.guild, message.author.id) if message.guild else None
                try:
                    outcome = await answer_mention(self.bot, message, late_since=self._late_label(item.created_at),
                                                   prefix=prefix, user=user)
                except discord.HTTPException as e:
                    # Discord refused the reply (deleted meanwhile, no permission): not a model problem
                    logger.warning(f"Couldn't post a catch-up reply: {e}")
                    if getattr(e, "status", None) in (403, 404) or await self._bump(item.message_id) >= MAX_ATTEMPTS:
                        await self.remove(item.message_id)
                    continue
                if outcome.status == "busy":
                    continue
                if outcome.status == "ok":
                    await self.remove(item.message_id)
                    answered += 1
                    continue
                if await self._bump(item.message_id) >= MAX_ATTEMPTS:
                    logger.warning(f"Giving up on missed message {item.message_id} after {MAX_ATTEMPTS} tries")
                    await self.remove(item.message_id)
                self._mark_down()
                break
        if answered:
            logger.info(f"Answered {answered} message(s) missed while the AI was down")
        return answered

    def _mark_down(self):
        self._fails += 1
        self._next_check = self.clock() + BACKOFF[min(self._fails, len(BACKOFF)) - 1]

    async def ollama_up(self) -> bool:
        """Cheap liveness check (no model load). A working server can still fail to load the model,
        so a failed catch-up reply also counts as down."""
        url = (BotConfig.OLLAMA_URL or "").rstrip("/")
        if not url:
            return False
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{url}/api/version", timeout=aiohttp.ClientTimeout(total=3)) as resp:
                    return resp.status == 200
        except Exception:
            return False

    async def tick(self) -> None:
        """Called every 30 s: when something is waiting and the backoff allows, check Ollama and catch up."""
        if self.clock() < self._next_check or not await self.pending():
            return
        if not await self.ollama_up():
            self._mark_down()
            return
        if await self.drain() and not await self.pending():
            self._fails = 0
