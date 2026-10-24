"""Channel personas: a server channel can have one of the PERSONAS answer @mentions instead of Cave.

The choice is stored per channel in `guild_settings` (key `persona:<channel_id>`) and stays until someone
resets it; threads follow their parent channel. Each persona keeps its own memory (see AIHandler).
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

KEY_PREFIX = "persona:"


class PersonaService:
    def __init__(self, db, personas: Dict):
        self.db = db
        self.personas = personas          # BotConfig.PERSONAS: key -> Persona (name, emoji, prompt...)
        self._channels: Dict[int, str] = {}

    async def load(self) -> int:
        async with self.db.get_connection() as conn:
            async with conn.execute("SELECT key, value FROM guild_settings WHERE key LIKE ?", (KEY_PREFIX + "%",)) as cur:
                rows = await cur.fetchall()
        self._channels = {int(key[len(KEY_PREFIX):]): value for key, value in rows if value in self.personas}
        return len(self._channels)

    def for_channel(self, channel) -> Optional[str]:
        """The persona answering in this channel (a thread uses its parent's), or None for Cave."""
        if channel is None:
            return None
        persona = self._channels.get(getattr(channel, "id", None))
        if persona is None and getattr(channel, "parent_id", None):
            persona = self._channels.get(channel.parent_id)
        return persona if persona in self.personas else None

    async def set(self, guild_id: int, channel_id: int, persona: str):
        if persona not in self.personas:
            raise ValueError(f"unknown persona {persona!r}")
        async with self.db.get_connection() as conn:
            await conn.execute("INSERT OR REPLACE INTO guild_settings (guild_id, key, value) VALUES (?, ?, ?)",
                               (guild_id, f"{KEY_PREFIX}{channel_id}", persona))
            await conn.commit()
        self._channels[channel_id] = persona

    async def reset(self, guild_id: int, channel_id: int) -> Optional[str]:
        """Back to Cave; returns the persona that was there (None if it was already Cave)."""
        async with self.db.get_connection() as conn:
            await conn.execute("DELETE FROM guild_settings WHERE guild_id = ? AND key = ?",
                               (guild_id, f"{KEY_PREFIX}{channel_id}"))
            await conn.commit()
        return self._channels.pop(channel_id, None)

    def label(self, persona: Optional[str]) -> str:
        info = self.personas.get(persona) if persona else None
        return f"{info.emoji} {info.name}" if info else "🧪 Cave Johnson"
