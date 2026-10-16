"""Startup report: which features are on, which are off and why, plus known config traps.

Logged once from setup_hook so a missing or mistyped .env entry shows up in the log instead of as a
mystery later. Only on/off states and setting names are logged, never values.
"""

import logging
import os
from typing import List, Tuple
from zoneinfo import ZoneInfo

from config import BotConfig

logger = logging.getLogger(__name__)

COOKIES_FILE = "www.youtube.com_cookies.txt"


def _missing(*names: str) -> List[str]:
    return [n for n in names if not getattr(BotConfig, n, None)]


def feature_states() -> List[Tuple[str, bool, str]]:
    """(feature, enabled, note) rows. The note says what's missing when a feature is off."""
    rows = []

    def add(name, needs, note_on=""):
        missing = _missing(*needs)
        rows.append((name, not missing, note_on if not missing else "set " + ", ".join(missing)))

    add("AI chat (Cave)", ["OLLAMA_URL"])
    add("Recall of old chats", ["OLLAMA_URL", "OLLAMA_EMBED_MODEL"])
    add("Owner error DMs + owner-only actions", ["OWNER_ID"])
    add("Music library (Plex)", ["PLEX_URL", "PLEX_TOKEN"])
    rows.append(("YouTube cookies", os.path.exists(COOKIES_FILE),
                 "" if os.path.exists(COOKIES_FILE) else f"add {COOKIES_FILE} to the repo root (popular videos may hit bot checks)"))
    add("Image generation (ComfyUI)", ["COMFY_URL"])
    add("3D printer", ["PRINTER_IP"])
    add("Media requests (Overseerr)", ["OVERSEERR_URL", "OVERSEERR_API_KEY"])
    add("Download queue (Sonarr/Radarr)", ["SONARR_URL", "SONARR_API_KEY", "RADARR_URL", "RADARR_API_KEY"])
    add("Steam library import", ["STEAM_API_KEY", "STEAM_ID"])
    rows.append(("Per-server personas", bool(BotConfig.SERVER_CONTEXTS),
                 "" if BotConfig.SERVER_CONTEXTS else "no data/server_contexts.json (default persona everywhere)"))
    return rows


def warnings() -> List[str]:
    """Settings that are present but look wrong."""
    found = []
    webcam = BotConfig.PRINTER_WEBCAM_URL or ""
    if "action=stream" in webcam:
        found.append("PRINTER_WEBCAM_URL points at the live stream; it's only an override now, and snapshots use "
                     "action=snapshot (or remove it to auto-discover the webcam)")
    for name in ("OLLAMA_URL", "OVERSEERR_URL", "SONARR_URL", "RADARR_URL", "LIDARR_URL", "COMFY_URL", "PLEX_URL"):
        value = getattr(BotConfig, name, None)
        if value and not str(value).startswith(("http://", "https://")):
            found.append(f"{name} should start with http:// or https://")
    try:
        ZoneInfo(BotConfig.BOT_TIMEZONE)
    except Exception:
        found.append(f"BOT_TIMEZONE '{BotConfig.BOT_TIMEZONE}' isn't a known time zone (daily features will break)")
    if BotConfig.OLLAMA_EMBED_MODEL and not BotConfig.OLLAMA_URL:
        found.append("OLLAMA_EMBED_MODEL is set but OLLAMA_URL isn't")
    return found


def log_report():
    rows = feature_states()
    on = [name for name, enabled, _ in rows if enabled]
    logger.info(f"Features on ({len(on)}/{len(rows)}): {', '.join(on)}")
    for name, enabled, note in rows:
        if not enabled:
            logger.info(f"Feature off: {name} ({note})")
    for warning in warnings():
        logger.warning(f"Config check: {warning}")
