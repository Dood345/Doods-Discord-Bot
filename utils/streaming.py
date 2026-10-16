"""Show Cave's reply in Discord while it streams in."""

import time

import discord

MAX_LEN = 2000            # Discord message limit
EDIT_INTERVAL = 1.5       # seconds between edits (Discord allows ~5 edits / 5 s per channel)
MIN_FIRST_CHARS = 40      # don't post a one-word stub
CURSOR = " ▌"


class ReplyStreamer:
    """Replies to `message` once enough text arrives, then edits it as more streams in."""

    def __init__(self, message, clock=time.monotonic):
        self.message = message
        self.reply = None
        self.last_edit = 0.0
        self.clock = clock

    @staticmethod
    def _fit(text: str, cursor: bool) -> str:
        suffix = CURSOR if cursor else ""
        limit = MAX_LEN - len(suffix)
        return (text if len(text) <= limit else text[:limit - 1] + "…") + suffix

    async def update(self, text: str):
        now = self.clock()
        try:
            if self.reply is None:
                if len(text) >= MIN_FIRST_CHARS:
                    self.reply = await self.message.reply(self._fit(text, cursor=True))
                    self.last_edit = now
            elif now - self.last_edit >= EDIT_INTERVAL:
                await self.reply.edit(content=self._fit(text, cursor=True))
                self.last_edit = now
        except discord.HTTPException:
            pass  # a dropped intermediate edit is fine; finish() sets the final text

    async def finish(self, text: str):
        final = self._fit(text, cursor=False)
        if self.reply is None:
            await self.message.reply(final)
        else:
            await self.reply.edit(content=final)
