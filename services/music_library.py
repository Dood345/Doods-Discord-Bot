"""The owner's Plex music library as a playback source (searched before SoundCloud/YouTube)."""

import logging
import random
import re
from typing import Dict, List, Optional, Tuple

import aiohttp

from config import BotConfig

logger = logging.getLogger(__name__)

PLEX_PREFIX = "plex:"   # queue URLs for library tracks look like "plex:/library/parts/123/456/file.flac"
MATCH_THRESHOLD = 0.6   # share of the request's words that must appear in "title artist"
FILLER = {"play", "some", "a", "the", "song", "songs", "track", "by", "music", "from", "please", "me", "put", "on"}


def words(text: str) -> List[str]:
    return [w for w in re.findall(r"[a-z0-9']+", text.lower()) if w not in FILLER]


def match_score(query: str, candidate: str) -> float:
    """How much of the request appears in the candidate text (0..1)."""
    q = words(query)
    if not q:
        return 0.0
    have = set(words(candidate))
    return sum(1 for w in q if w in have) / len(q)


class MusicLibrary:
    def __init__(self, base_url: Optional[str] = None, token: Optional[str] = None):
        self.base_url = (base_url if base_url is not None else BotConfig.PLEX_URL or "").rstrip("/")
        self.token = token if token is not None else BotConfig.PLEX_TOKEN

    @property
    def available(self) -> bool:
        return bool(self.base_url and self.token)

    def _headers(self) -> Dict[str, str]:
        return {"X-Plex-Token": self.token, "Accept": "application/json"}

    async def _get(self, path: str, params: Optional[Dict] = None) -> Optional[Dict]:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}{path}", params=params, headers=self._headers(),
                                       timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status != 200:
                        logger.warning(f"Plex {path} returned {resp.status}")
                        return None
                    return (await resp.json()).get("MediaContainer", {})
        except Exception as e:
            logger.warning(f"Plex request failed: {e}")
            return None

    @staticmethod
    def _track(meta: Dict) -> Optional[Tuple[str, str, str]]:
        try:
            part_key = meta["Media"][0]["Part"][0]["key"]
        except (KeyError, IndexError, TypeError):
            return None
        artist = meta.get("originalTitle") or meta.get("grandparentTitle") or "Unknown Artist"
        return (PLEX_PREFIX + part_key, meta.get("title", "Unknown"), artist)

    async def find(self, query: str) -> Optional[Tuple[str, str, str]]:
        """Best library track for a request, or a random track if it names an artist. None if no good match."""
        if not self.available:
            return None
        container = await self._get("/hubs/search", {"query": query, "limit": 10})
        if not container:
            return None
        hubs = {h.get("type"): h.get("Metadata") or [] for h in container.get("Hub", [])}

        best, best_score = None, 0.0
        for meta in hubs.get("track", []):
            text = f"{meta.get('title', '')} {meta.get('grandparentTitle', '')} {meta.get('originalTitle', '')}"
            score = match_score(query, text)
            if score > best_score:
                best, best_score = meta, score
        if best is not None and best_score >= MATCH_THRESHOLD:
            return self._track(best)

        # "play some Daft Punk": the request is (mostly) an artist name
        for artist in hubs.get("artist", []):
            if match_score(query, artist.get("title", "")) >= MATCH_THRESHOLD:
                leaves = await self._get(f"/library/metadata/{artist['ratingKey']}/allLeaves")
                tracks = [t for t in (self._track(m) for m in (leaves or {}).get("Metadata", [])) if t]
                if tracks:
                    return random.choice(tracks)
        return None

    def stream_source(self, queue_url: str) -> Tuple[str, str]:
        """(stream URL, extra ffmpeg before_options) for a plex: queue entry. Token goes in a header, not the URL."""
        return f"{self.base_url}{queue_url[len(PLEX_PREFIX):]}", f'-headers "X-Plex-Token: {self.token}"'
