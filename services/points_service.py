"""Science Points: per-server points and achievements.

Points are an append-only ledger (`science_points`); every award has a unique key, so
re-running an award (a restart, a double click) never pays twice. Achievement rules
live in content/achievements.json.
"""

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from config import BotConfig

logger = logging.getLogger(__name__)

ACHIEVEMENTS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "content", "achievements.json")
ACTIVITY_POINTS = 1
SETTING_ENABLED = "science_points"
DISABLED_MSG = "Science Points are off in this server. A server manager can turn them on with `/sciencepoints on`."


@dataclass(frozen=True)
class Achievement:
    id: str
    name: str
    emoji: str
    description: str
    type: str            # "points" (total) or "reason_count" (number of awards whose reason starts with `reason`)
    threshold: int
    reason: str = ""

    @property
    def label(self) -> str:
        return f"{self.emoji} **{self.name}**"


def load_achievements(path: str = ACHIEVEMENTS_FILE) -> List[Achievement]:
    try:
        with open(path, encoding="utf-8") as f:
            return [Achievement(**a) for a in json.load(f)]
    except (OSError, ValueError, TypeError) as e:
        logger.error(f"Could not load achievements from {path}: {e}")
        return []


class PointsService:
    def __init__(self, db, achievements: Optional[List[Achievement]] = None, tz: Optional[ZoneInfo] = None):
        self.db = db
        self.achievements = achievements if achievements is not None else load_achievements()
        self.by_id: Dict[str, Achievement] = {a.id: a for a in self.achievements}
        self.tz = tz or ZoneInfo(BotConfig.BOT_TIMEZONE)
        self._seen = set()
        self._enabled: Dict[int, bool] = {}

    # --- Per-server opt-in (off until a manager turns it on) ---

    async def is_enabled(self, guild_id: int) -> bool:
        if guild_id not in self._enabled:  # cached: this runs on every message
            async with self.db.get_connection() as conn:
                async with conn.execute("SELECT 1 FROM guild_settings WHERE guild_id = ? AND key = ?",
                                        (guild_id, SETTING_ENABLED)) as cur:
                    self._enabled[guild_id] = await cur.fetchone() is not None
        return self._enabled[guild_id]

    async def set_enabled(self, guild_id: int, enabled: bool):
        async with self.db.get_connection() as conn:
            if enabled:
                await conn.execute("INSERT OR REPLACE INTO guild_settings (guild_id, key, value) VALUES (?, ?, 'on')",
                                   (guild_id, SETTING_ENABLED))
            else:
                await conn.execute("DELETE FROM guild_settings WHERE guild_id = ? AND key = ?", (guild_id, SETTING_ENABLED))
            await conn.commit()
        self._enabled[guild_id] = enabled

    def local_date(self, now: Optional[datetime] = None) -> str:
        return (now or datetime.now(self.tz)).astimezone(self.tz).date().isoformat()

    async def award(self, guild_id: int, user_id: int, amount: int, reason: str, award_key: str) -> Tuple[bool, List[Achievement]]:
        """(paid, newly earned achievements). Paying the same award_key twice is a no-op."""
        if not await self.db.award_points(guild_id, user_id, amount, reason, award_key):
            return False, []
        return True, await self._check_achievements(guild_id, user_id)

    async def record_activity(self, guild_id: int, user_id: int, now: Optional[datetime] = None) -> List[Achievement]:
        """+1 for the first message of the (local) day on this server. Returns newly earned achievements."""
        key = f"activity:{guild_id}:{user_id}:{self.local_date(now)}"
        if key in self._seen or not await self.is_enabled(guild_id):  # skip the DB for everyone's 2nd+ message of the day
            return []
        if len(self._seen) > 10000:
            self._seen.clear()
        self._seen.add(key)
        _, earned = await self.award(guild_id, user_id, ACTIVITY_POINTS, "activity", key)
        return earned

    async def _check_achievements(self, guild_id: int, user_id: int) -> List[Achievement]:
        have = set(await self.db.get_achievements(guild_id, user_id))
        total = None
        earned = []
        for a in self.achievements:
            if a.id in have:
                continue
            if a.type == "points":
                total = total if total is not None else await self.db.get_points(guild_id, user_id)
                value = total
            else:
                value = await self.db.count_awards(guild_id, user_id, a.reason)
            if value >= a.threshold and await self.db.grant_achievement(guild_id, user_id, a.id):
                earned.append(a)
        return earned

    async def profile(self, guild_id: int, user_id: int) -> Tuple[int, Optional[int], List[Achievement]]:
        """(points, rank or None, achievements)."""
        points = await self.db.get_points(guild_id, user_id)
        rank = await self.db.get_rank(guild_id, user_id)
        ids = await self.db.get_achievements(guild_id, user_id)
        return points, rank, [self.by_id[i] for i in ids if i in self.by_id]

    async def leaderboard(self, guild_id: int, limit: int = 10) -> List[Tuple[int, int]]:
        return await self.db.get_leaderboard(guild_id, limit)
