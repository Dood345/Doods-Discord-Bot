"""Game Night Director: pick games that fit the crowd, and work out when game night starts."""

import random
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from config import BotConfig

PICKS = 3
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
