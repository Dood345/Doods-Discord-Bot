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
MIX_SIZE = 10            # tracks in an artist mix
MIN_MIX_TRACKS = 5       # fewer than this and an artist request becomes a radio instead
RADIO_SIZE = 15
RADIO_SIMILAR_ARTISTS = 6
FILLER = {"play", "some", "a", "the", "song", "songs", "track", "by", "music", "from", "please", "me", "put", "on", "radio", "station", "start", "mix", "playlist"}


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
        """Best single library track for a request (a random one if it names an artist). None if no good match."""
        planned = await self.plan(query)
        return planned[0][0] if planned else None

    async def plan(self, query: str, radio: bool = False) -> Optional[Tuple[List[Tuple[str, str, str]], str]]:
        """What to queue for a request: ([tracks], description), or None if the library has no good match.

        - exactly an artist ("play some 311"): a shuffled mix of their tracks, or a radio if asked
          (or if they have too few tracks for a real mix)
        - a song: that song, or a radio seeded with it when radio=True
        """
        if not self.available:
            return None
        # Plex search matches the whole phrase, so "play some Juicy J" must be sent as "juicy j"
        search_text = " ".join(words(query)) or query
        container = await self._get("/hubs/search", {"query": search_text, "limit": 10})
        if not container:
            return None
        hubs = {h.get("type"): h.get("Metadata") or [] for h in container.get("Hub", [])}

        # A request that is exactly an artist's name means "something by them",
        # not a track that merely features them
        for artist in hubs.get("artist", []):
            if words(query) == words(artist.get("title", "")):
                planned = await self._artist_plan(artist, radio)
                if planned:
                    return planned

        best, best_score = None, 0.0
        for meta in hubs.get("track", []):
            text = f"{meta.get('title', '')} {meta.get('grandparentTitle', '')} {meta.get('originalTitle', '')}"
            score = match_score(query, text)
            if score > best_score:
                best, best_score = meta, score
        if best is not None and best_score >= MATCH_THRESHOLD and (track := self._track(best)):
            if radio and best.get("grandparentRatingKey"):
                seed_artist = {"ratingKey": best["grandparentRatingKey"], "title": best.get("grandparentTitle", "")}
                rest = await self._radio_tracks(seed_artist, exclude={track[0]})
                return [track] + rest, f"a radio station starting with **{track[1]}**"
            return [track], f"**{track[1]}** by {track[2]}"

        # No good track match: the request is mostly an artist name
        for artist in hubs.get("artist", []):
            if match_score(query, artist.get("title", "")) >= MATCH_THRESHOLD:
                planned = await self._artist_plan(artist, radio)
                if planned:
                    return planned
        return None

    async def _artist_tracks(self, artist: Dict) -> List[Tuple[str, str, str]]:
        leaves = await self._get(f"/library/metadata/{artist['ratingKey']}/allLeaves")
        return [t for t in (self._track(m) for m in (leaves or {}).get("Metadata", [])) if t]

    async def _artist_plan(self, artist: Dict, radio: bool) -> Optional[Tuple[List[Tuple[str, str, str]], str]]:
        own = await self._artist_tracks(artist)
        if not own:
            return None
        name = artist.get("title", "that artist")
        if radio or len(own) < MIN_MIX_TRACKS:
            return await self._radio_tracks(artist, own=own), f"a **{name}** radio station"
        random.shuffle(own)
        mix = own[:MIX_SIZE]
        return mix, f"a {len(mix)}-track **{name}** mix"

    async def _radio_tracks(self, artist: Dict, own: Optional[List] = None, exclude=frozenset()) -> List[Tuple[str, str, str]]:
        """About a third from the artist, the rest from similar artists in the library, shuffled (artist first)."""
        own = [t for t in (own if own is not None else await self._artist_tracks(artist)) if t[0] not in exclude]
        random.shuffle(own)
        similar = await self._get(f"/library/metadata/{artist['ratingKey']}/similar")
        others = []
        for sim in (similar or {}).get("Metadata", [])[:RADIO_SIMILAR_ARTISTS]:
            tracks = await self._artist_tracks(sim)
            random.shuffle(tracks)
            others.extend(tracks[:3])
        own_count = RADIO_SIZE // 3 if others else RADIO_SIZE
        pool = own[1:own_count] + others
        random.shuffle(pool)
        return (own[:1] + pool)[:RADIO_SIZE]

    def stream_source(self, queue_url: str) -> Tuple[str, str]:
        """(stream URL, extra ffmpeg before_options) for a plex: queue entry. Token goes in a header, not the URL."""
        return f"{self.base_url}{queue_url[len(PLEX_PREFIX):]}", f'-headers "X-Plex-Token: {self.token}"'
