"""Unhandled errors get logged in full and DMed to the owner (scrubbed and rate-limited).

Wired up in main.py for slash commands / context menus (tree.on_error), prefix commands and
event handlers (Bot.on_error). The DM never contains tokens, keys or LAN addresses: aiohttp,
yt-dlp and ffmpeg errors often embed the URL they were fetching.
"""

import logging
import re
import time
import traceback
from typing import Dict, Optional

logger = logging.getLogger(__name__)

RATE_LIMIT_SECONDS = 15 * 60   # one DM per distinct error per 15 minutes
TRACE_CHARS = 1500

_SCRUBBERS = [
    (re.compile(r"(?i)(x-plex-token|api[_-]?key|apikey|token|key|secret|password|authorization)(\s*[=:]\s*|=)[^\s&'\",)]+"), r"\1\2[redacted]"),
    (re.compile(r"(?i)https?://[^\s'\")]+"), "[url]"),
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b"), "[ip]"),
    (re.compile(r"\b[MN][A-Za-z\d_-]{23,25}\.[A-Za-z\d_-]{6}\.[A-Za-z\d_-]{27,}\b"), "[discord-token]"),
]


def scrub(text: str) -> str:
    for pattern, replacement in _SCRUBBERS:
        text = pattern.sub(replacement, text)
    return text


def signature(where: str, error: BaseException) -> str:
    """Same place + same error type + same innermost frame = same problem (for rate limiting)."""
    tb = traceback.extract_tb(error.__traceback__)
    frame = f"{tb[-1].filename.rsplit('/', 1)[-1].rsplit(chr(92), 1)[-1]}:{tb[-1].lineno}" if tb else "?"
    return f"{where}|{type(error).__name__}|{frame}"


class ErrorReporter:
    def __init__(self, bot, owner_id: int, clock=time.monotonic):
        self.bot = bot
        self.owner_id = owner_id
        self.clock = clock
        self._last_sent: Dict[str, float] = {}

    def _should_send(self, sig: str) -> bool:
        now = self.clock()
        if now - self._last_sent.get(sig, -RATE_LIMIT_SECONDS) < RATE_LIMIT_SECONDS:
            return False
        self._last_sent[sig] = now
        return True

    def format(self, where: str, error: BaseException, user: Optional[str] = None) -> str:
        trace = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        trace = scrub(trace)[-TRACE_CHARS:]
        who = f" (triggered by {user})" if user else ""
        return (f"🚨 **Unhandled error in `{where}`**{who}\n`{type(error).__name__}: {scrub(str(error))[:300]}`\n"
                f"```py\n{trace}\n```")

    async def report(self, where: str, error: BaseException, user: Optional[str] = None) -> bool:
        """Log it, and DM the owner unless this exact problem was reported recently. True if a DM went out."""
        logger.error(f"Unhandled error in {where}", exc_info=(type(error), error, error.__traceback__))
        if not self.owner_id or not self._should_send(signature(where, error)):
            return False
        try:
            owner = self.bot.get_user(self.owner_id) or await self.bot.fetch_user(self.owner_id)
            await owner.send(self.format(where, error, user)[:2000])
            return True
        except Exception as e:
            logger.warning(f"Couldn't DM the owner about an error: {e}")
            return False


async def handle_app_command_error(reporter: ErrorReporter, interaction, error) -> None:
    """tree.on_error: expected failures get a short ephemeral reply; anything else is reported."""
    from discord import HTTPException, app_commands

    if isinstance(error, app_commands.CommandOnCooldown):
        text = f"⏳ Cooldown. Try again in {error.retry_after:.0f}s."
    elif isinstance(error, (app_commands.CheckFailure, app_commands.TransformerError)):
        text = "⛔ You can't use that here."
    else:
        command = interaction.command.qualified_name if interaction.command else "unknown command"
        await reporter.report(f"/{command}", getattr(error, "original", error), str(interaction.user))
        text = "🤖 Something broke in the lab. The incident has been reported to management."
    try:
        if interaction.response.is_done():
            await interaction.followup.send(text, ephemeral=True)
        else:
            await interaction.response.send_message(text, ephemeral=True)
    except HTTPException:
        pass  # the interaction expired; the report already went out
