"""Facility announcements: opt-in proactive posts.

- New media: Overseerr requests that became available, posted (title only) to servers that opted in.
- Birthdays: users opt themselves in with /birthday; shout-out on the day in opted-in servers.
- Printer: when a print finishes, the owner gets a DM (with a webcam snapshot if configured).

Every announcement is recorded in `announced` so restarts never repeat one.
"""

import logging
from datetime import datetime, time
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import aiohttp

from config import BotConfig

logger = logging.getLogger(__name__)

SETTING_CHANNEL = "announce_channel"
BIRTHDAY_TIME = time(9, 0)  # local


class AnnouncementService:
    def __init__(self, db, homelab, tz: Optional[ZoneInfo] = None, clock=None):
        self.db = db
        self.homelab = homelab
        self.tz = tz or ZoneInfo(BotConfig.BOT_TIMEZONE)
        self.clock = clock or (lambda: datetime.now(self.tz))
        self._printer_state: Optional[str] = None

    def now(self) -> datetime:
        return self.clock().astimezone(self.tz)

    # --- Settings / bookkeeping ---

    async def set_channel(self, guild_id: int, channel_id: Optional[int]):
        async with self.db.get_connection() as conn:
            if channel_id is None:
                await conn.execute("DELETE FROM guild_settings WHERE guild_id = ? AND key = ?", (guild_id, SETTING_CHANNEL))
            else:
                await conn.execute("INSERT OR REPLACE INTO guild_settings (guild_id, key, value) VALUES (?, ?, ?)",
                                   (guild_id, SETTING_CHANNEL, str(channel_id)))
            await conn.commit()

    async def channels(self) -> Dict[int, int]:
        async with self.db.get_connection() as conn:
            async with conn.execute("SELECT guild_id, value FROM guild_settings WHERE key = ?", (SETTING_CHANNEL,)) as cur:
                return {g: int(v) for g, v in await cur.fetchall()}

    async def mark(self, key: str) -> bool:
        """Record an announcement; False if it was already made."""
        async with self.db.get_connection() as conn:
            cur = await conn.execute("INSERT OR IGNORE INTO announced (item_key) VALUES (?)", (key,))
            await conn.commit()
            return cur.rowcount == 1

    async def _any_marked(self, prefix: str) -> bool:
        async with self.db.get_connection() as conn:
            async with conn.execute("SELECT 1 FROM announced WHERE item_key LIKE ? LIMIT 1", (f"{prefix}%",)) as cur:
                return await cur.fetchone() is not None

    # --- Birthdays ---

    async def set_birthday(self, guild_id: int, user_id: int, month: int, day: int):
        datetime(2000, month, day)  # validates (2000 is a leap year, so Feb 29 is allowed)
        async with self.db.get_connection() as conn:
            await conn.execute("INSERT OR REPLACE INTO birthdays (guild_id, user_id, month, day) VALUES (?, ?, ?, ?)",
                               (guild_id, user_id, month, day))
            await conn.commit()

    async def remove_birthday(self, guild_id: int, user_id: int):
        async with self.db.get_connection() as conn:
            await conn.execute("DELETE FROM birthdays WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
            await conn.commit()

    async def due_birthdays(self) -> List[Tuple[int, int]]:
        """[(guild_id, user_id)] to celebrate now (after 9 am on their day, once per year, opted-in servers only)."""
        now = self.now()
        if now.time() < BIRTHDAY_TIME:
            return []
        days = [(now.month, now.day)]
        if (now.month, now.day) == (2, 28) and not _is_leap(now.year):
            days.append((2, 29))  # Feb 29 birthdays get celebrated on the 28th in non-leap years
        channels = await self.channels()
        due = []
        async with self.db.get_connection() as conn:
            for month, day in days:
                async with conn.execute("SELECT guild_id, user_id FROM birthdays WHERE month = ? AND day = ?",
                                        (month, day)) as cur:
                    due += [(g, u) for g, u in await cur.fetchall() if g in channels]
        return [(g, u) for g, u in due if await self.mark(f"birthday:{g}:{u}:{now.year}")]

    # --- New media ---

    async def new_media(self) -> List[str]:
        """Titles that became available since the last check. The first run only records what's there."""
        conf = self.homelab._overseerr()
        if conf is None:
            return []
        base, headers = conf
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{base}/api/v1/request?take=20&skip=0&filter=available&sort=modified",
                                       headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        return []
                    requests = (await resp.json()).get("results", [])
        except Exception as e:
            logger.debug(f"Overseerr unavailable for announcements: {e}")
            return []
        first_run = not await self._any_marked("media:")
        titles = []
        for req in requests:
            media = req.get("media") or {}
            key = f"media:{media.get('mediaType')}:{media.get('tmdbId')}"
            if not media.get("tmdbId") or not await self.mark(key) or first_run:
                continue
            details = await self.homelab.media_details(media["tmdbId"], media.get("mediaType"))
            if details:
                titles.append(f"{details['title']} ({details['year']})")
        return titles

    # --- Printer ---

    async def printer_finished(self) -> Optional[Dict]:
        """The printer's status when a print just ended (printing/paused -> complete, error or cancelled), else None."""
        status = await self.homelab.printer_status()
        if status is None:
            return None
        previous, self._printer_state = self._printer_state, status["state"]
        if previous in ("printing", "paused") and status["state"] in ("complete", "error", "cancelled"):
            return status
        return None

def _is_leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
