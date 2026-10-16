"""Music sessions that survive restarts: what was playing, where, how far in, and what was queued.

The music cog snapshots every active player every few seconds; after a restart it resumes any
recent session whose voice channel still has people in it. A session disappears from the table
as soon as its player does (queue finished, /stop), so only restarts trigger a resume.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

MAX_AGE = 30 * 60      # don't resume sessions older than this (seconds)
REWIND = 3             # replay a few seconds so the resume doesn't feel like a skip

Track = Tuple[str, str, str]


@dataclass
class MusicSession:
    channel_id: int
    guild_id: int
    text_channel_id: Optional[int]
    current: Track
    position: float
    queue: List[Track] = field(default_factory=list)
    paused: bool = False
    saved_at: float = 0.0


def elapsed(player, now: Optional[float] = None) -> float:
    """Seconds into the current track, accounting for a pause in progress."""
    if not player.start_time:
        return 0.0
    end = player.pause_start_time or now or time.time()
    return max(0.0, end - player.start_time)


def snapshot(player, guild_id: int, now: Optional[float] = None) -> Optional[MusicSession]:
    if not player.current_track:
        return None
    channel = getattr(player, "notification_channel", None)
    return MusicSession(
        channel_id=player.channel_id, guild_id=guild_id,
        text_channel_id=getattr(channel, "id", None),
        current=tuple(player.current_track), position=elapsed(player, now),
        queue=[tuple(t) for t in player.queue], paused=bool(player.pause_start_time),
        saved_at=now or time.time())


class MusicSessionStore:
    def __init__(self, db):
        self.db = db

    async def save_all(self, sessions: List[MusicSession]):
        """Replace the stored sessions with exactly these (players that ended are removed)."""
        async with self.db.get_connection() as conn:
            await conn.execute("DELETE FROM music_sessions")
            await conn.executemany(
                "INSERT INTO music_sessions (channel_id, guild_id, text_channel_id, current, position, queue, paused, saved_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [(s.channel_id, s.guild_id, s.text_channel_id, json.dumps(s.current), s.position,
                  json.dumps(s.queue), int(s.paused), s.saved_at) for s in sessions])
            await conn.commit()

    async def load_recent(self, now: Optional[float] = None, max_age: float = MAX_AGE) -> List[MusicSession]:
        now = now or time.time()
        async with self.db.get_connection() as conn:
            async with conn.execute("SELECT channel_id, guild_id, text_channel_id, current, position, queue, paused, saved_at "
                                    "FROM music_sessions") as cur:
                rows = await cur.fetchall()
        sessions = []
        for channel_id, guild_id, text_id, current, position, queue, paused, saved_at in rows:
            if now - saved_at > max_age:
                continue
            sessions.append(MusicSession(channel_id, guild_id, text_id, tuple(json.loads(current)), position,
                                         [tuple(t) for t in json.loads(queue)], bool(paused), saved_at))
        return sessions

    async def clear(self):
        async with self.db.get_connection() as conn:
            await conn.execute("DELETE FROM music_sessions")
            await conn.commit()


def fmt_time(seconds: float) -> str:
    seconds = int(seconds)
    return f"{seconds // 60}:{seconds % 60:02d}"
