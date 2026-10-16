"""Game Night Director: pick games that fit the crowd, and work out when game night starts."""

import random
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from config import BotConfig

PICKS = 3
EARLY_JOIN = timedelta(minutes=15)      # attendance counts from a little before the start...
ATTEND_WINDOW = timedelta(hours=4)      # ...until this long after it
ATTEND_CHECKS = 10                      # sightings by the 2-minute loop (~20 minutes) to count as attending
ATTEND_POINTS = 15


@dataclass
class GameNightRecord:
    id: int
    guild_id: int
    voice_channel_id: int
    text_channel_id: Optional[int]
    starts_at: float
    ends_at: float
TIME_RE = re.compile(r"^\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*$", re.IGNORECASE)


def parse_start(text: Optional[str], now: datetime) -> Optional[datetime]:
    """'9pm', '21:00', '8:30 pm' -> the next such local time after `now` (today, or tomorrow if passed).
    None/empty -> 9 pm by default; unparseable -> None."""
    if not text:
        text = "9pm"
    m = TIME_RE.match(text)
    if not m:
        return None
    hour, minute, ampm = int(m.group(1)), int(m.group(2) or 0), (m.group(3) or "").lower()
    if ampm:
        if not 1 <= hour <= 12:
            return None
        hour = hour % 12 + (12 if ampm == "pm" else 0)
    if hour > 23 or minute > 59:
        return None
    start = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if start <= now + timedelta(minutes=5):
        start += timedelta(days=1)
    return start


def pick_games(library: List[Dict], players: Optional[int], k: int = PICKS, rng=random) -> List[Dict]:
    """Up to k games that fit `players` (any count if None), skipping ones marked avoid.
    Better-rated games are more likely; unrated ones get an average chance."""
    fits = [g for g in library
            if (g.get("status") or "").lower() != "avoid"
            and (players is None or (g.get("min_players") or 1) <= players <= (g.get("max_players") or 99))]
    picks = []
    pool = list(fits)
    while pool and len(picks) < k:
        weights = [(g.get("avg_rating") or 6) ** 2 for g in pool]
        choice = rng.choices(pool, weights=weights)[0]
        picks.append(choice)
        pool.remove(choice)
    return picks


class GameNightService:
    def __init__(self, db, tz: Optional[ZoneInfo] = None):
        self.db = db
        self.tz = tz or ZoneInfo(BotConfig.BOT_TIMEZONE)

    def now(self) -> datetime:
        return datetime.now(self.tz)

    async def suggest(self, guild_id: int, players: Optional[int]) -> List[Dict]:
        return pick_games(await self.db.get_game_library(guild_id), players)

    # --- Attendance ---------------------------------------------------------------
    # /gamenight records the night; a 2-minute loop counts who's in its voice channel from shortly
    # before the start until ATTEND_WINDOW later. ATTEND_CHECKS sightings (~20 min) earns the points.

    async def record_night(self, guild_id: int, voice_channel_id: int, text_channel_id: Optional[int],
                           starts_at: datetime) -> int:
        start = starts_at.timestamp() - EARLY_JOIN.total_seconds()
        async with self.db.get_connection() as conn:
            cur = await conn.execute(
                "INSERT INTO game_nights (guild_id, voice_channel_id, text_channel_id, starts_at, ends_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (guild_id, voice_channel_id, text_channel_id, start, starts_at.timestamp() + ATTEND_WINDOW.total_seconds()))
            await conn.commit()
            return cur.lastrowid

    async def open_nights(self, now: Optional[float] = None) -> List[GameNightRecord]:
        """Nights not yet closed whose window has started (including ones that just ended, to close them)."""
        now = now if now is not None else self.now().timestamp()
        async with self.db.get_connection() as conn:
            async with conn.execute("SELECT id, guild_id, voice_channel_id, text_channel_id, starts_at, ends_at "
                                    "FROM game_nights WHERE closed = 0 AND starts_at <= ?", (now,)) as cur:
                return [GameNightRecord(*row) for row in await cur.fetchall()]

    async def record_presence(self, night_id: int, user_ids: List[int]) -> List[int]:
        """Count one sighting for each user; returns users who just reached ATTEND_CHECKS."""
        qualified = []
        async with self.db.get_connection() as conn:
            for uid in user_ids:
                await conn.execute(
                    "INSERT INTO game_night_attendance (night_id, user_id, checks) VALUES (?, ?, 1) "
                    "ON CONFLICT(night_id, user_id) DO UPDATE SET checks = checks + 1", (night_id, uid))
                async with conn.execute("SELECT checks FROM game_night_attendance WHERE night_id = ? AND user_id = ?",
                                        (night_id, uid)) as cur:
                    if (await cur.fetchone())[0] == ATTEND_CHECKS:
                        qualified.append(uid)
            await conn.commit()
        return qualified

    async def close_night(self, night_id: int) -> List[int]:
        """Mark the night done; returns everyone who qualified (for the summary)."""
        async with self.db.get_connection() as conn:
            await conn.execute("UPDATE game_nights SET closed = 1 WHERE id = ?", (night_id,))
            async with conn.execute("SELECT user_id FROM game_night_attendance WHERE night_id = ? AND checks >= ? "
                                    "ORDER BY user_id", (night_id, ATTEND_CHECKS)) as cur:
                rows = await cur.fetchall()
            await conn.commit()
        return [r[0] for r in rows]
