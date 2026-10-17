"""Mentions the model couldn't answer are answered later, oldest first."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

import discord

import services.ai_backlog as backlog_mod
from services.ai_backlog import MAX_ATTEMPTS, MAX_PER_USER, AIBacklog, answer_mention, mention_text
from utils.agent import Tool, ToolContext, ToolRegistry

BOT_ID = 4242
NOW = 1_800_000_000.0


class FakeChannel:
    def __init__(self, cid=7):
        self.id = cid
        self.messages = {}

    def typing(self):
        class _T:
            async def __aenter__(s): return None
            async def __aexit__(s, *a): return False
        return _T()

    async def fetch_message(self, mid):
        if mid not in self.messages:
            raise discord.NotFound(MagicMock(status=404), "gone")
        return self.messages[mid]


def msg(channel, mid, text, user=1, at=NOW - 600):
    m = SimpleNamespace(id=mid, content=f"<@{BOT_ID}> {text}", channel=channel, guild=SimpleNamespace(id=9),
                        author=SimpleNamespace(id=user, display_name=f"U{user}"), reference=None,
                        created_at=datetime.fromtimestamp(at, timezone.utc), reply=AsyncMock())
    channel.messages[mid] = m
    return m


def make(temp_db, replies):
    """replies: list of responses get_chat_response returns in turn (None = model failed)."""
    calls = []

    async def chat(user_id, text, guild_id, **kw):
        calls.append((text, kw.get("late_since")))
        return replies.pop(0) if replies else "ok"
    channel = FakeChannel()
    handler = SimpleNamespace(get_chat_response=chat, _busy_users=set())
    bot = SimpleNamespace(user=SimpleNamespace(id=BOT_ID), ai_handler=handler, get_channel=lambda cid: channel)
    return AIBacklog(temp_db, bot, clock=lambda: NOW, tz=ZoneInfo("America/Chicago")), channel, calls


def test_only_caves_mention_is_stripped():
    assert mention_text(f"<@{BOT_ID}> roast <@55> please", BOT_ID) == "roast <@55> please"
    assert mention_text(f"<@!{BOT_ID}>", BOT_ID) == "Hello!"


async def test_live_failure_posts_the_error_and_success_streams(temp_db):
    b, channel, _ = make(temp_db, [None])
    m = msg(channel, 1, "hi")
    assert await answer_mention(b.bot, m, on_fail=backlog_mod.ERROR_REPLY) is None
    assert "confused processing noises" in m.reply.call_args.args[0]


async def test_missed_messages_are_answered_oldest_first_and_late(temp_db):
    b, channel, calls = make(temp_db, ["first", "second"])
    newer, older = msg(channel, 2, "what's up", at=NOW - 60), msg(channel, 1, "play portal", at=NOW - 600)
    assert await b.add(newer) and await b.add(older)
    assert await b.drain() == 2
    assert [c[0] for c in calls] == ["play portal", "what's up"]
    assert all(c[1].startswith("at ") for c in calls)                   # the model is told it's late
    assert "Catching up" in older.reply.call_args.args[0] and "first" in older.reply.call_args.args[0]
    assert await b.pending() == []


async def test_stops_at_a_failure_and_drops_after_max_attempts(temp_db):
    b, channel, calls = make(temp_db, [None])
    a, c = msg(channel, 1, "one", at=NOW - 600), msg(channel, 2, "two", at=NOW - 60)
    await b.add(a)
    await b.add(c)
    assert await b.drain() == 0 and len(calls) == 1                     # still down: don't try the next one
    assert [p.attempts for p in await b.pending()] == [1, 0]
    b.bot.ai_handler.get_chat_response = AsyncMock(return_value=None)
    for _ in range(MAX_ATTEMPTS - 1):
        await b.drain()
    assert [p.message_id for p in await b.pending()] == [2]             # a message that always fails gets dropped


async def test_deleted_messages_are_skipped_and_busy_users_wait(temp_db):
    b, channel, calls = make(temp_db, [])
    gone = msg(channel, 1, "deleted later", at=NOW - 600)
    await b.add(gone)
    del channel.messages[1]
    keep = msg(channel, 2, "hello", user=3, at=NOW - 60)
    await b.add(keep)
    b.bot.ai_handler._busy_users.add(3)
    assert await b.drain() == 0 and [p.message_id for p in await b.pending()] == [2]
    b.bot.ai_handler._busy_users.clear()
    assert await b.drain() == 1


async def test_caps_and_reasks(temp_db):
    b, channel, calls = make(temp_db, [])
    for i in range(MAX_PER_USER + 1):
        await b.add(msg(channel, 10 + i, f"spam {i}"))
    assert len(await b.pending()) == MAX_PER_USER
    again = msg(channel, 99, "spam 0", at=NOW)                          # asked again and answered live
    b.drain = AsyncMock()
    await b.after_success(again)
    assert [p.message_id for p in await b.pending()] == [11, 12]


async def test_health_check_backs_off_while_down(temp_db, monkeypatch):
    b, channel, calls = make(temp_db, [])
    await b.add(msg(channel, 1, "hi"))
    b.ollama_up = AsyncMock(return_value=False)
    await b.tick()
    await b.tick()                                                      # inside the backoff: no second check
    assert b.ollama_up.await_count == 1
    b._next_check = 0
    b.ollama_up = AsyncMock(return_value=True)
    await b.tick()
    assert calls and await b.pending() == []


def test_blocked_tools_are_hidden_and_refused():
    async def h(ctx):
        return "skipped"
    reg = ToolRegistry([Tool("skip_song", "skip", h), Tool("now_playing", "np", h)])
    ctx = ToolContext(bot=None, user=SimpleNamespace(id=1), blocked={"skip_song"})
    assert [s["function"]["name"] for s in reg.schemas_for(ctx)] == ["now_playing"]


async def test_late_chat_withholds_skip_and_notes_the_time(temp_db):
    from utils.ai_handler import AIHandler
    handler = AIHandler(temp_db, SimpleNamespace(db=temp_db, dialogue=None, get_cog=lambda n: None))
    handler.client = True
    handler._chat = AsyncMock(return_value={"content": "Late but here!"})
    await handler.get_chat_response(1, "skip this", 9, user=SimpleNamespace(id=1, name="x"),
                                    guild=SimpleNamespace(id=9), late_since="at 4:03 PM")
    messages, tools = handler._chat.call_args.args[0], handler._chat.call_args.args[1]
    assert "sent at 4:03 PM" in messages[-1]["content"]
    assert "skip_song" not in [t["function"]["name"] for t in tools]
