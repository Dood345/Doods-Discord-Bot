"""Fill in game details from a Steam or Epic store link (#103).

Only Steam's public store API is ever fetched; the user's URL is parsed, never requested
(the bot runs inside the LAN). Epic pages sit behind bot protection, so an Epic link is
matched to the same game on Steam by name, and falls back to just the title from the slug.
"""

import logging
import re
from typing import Dict, Optional
from urllib.parse import urlparse

import aiohttp

logger = logging.getLogger(__name__)

STEAM_HOSTS = {"store.steampowered.com", "steamcommunity.com"}
EPIC_HOSTS = {"store.epicgames.com", "www.epicgames.com", "epicgames.com"}
STEAM_API = "https://store.steampowered.com"
PLAYERS_RE = re.compile(r"(\d+)\s*(?:-|–|to)\s*(\d+)\s*players", re.IGNORECASE)
UP_TO_RE = re.compile(r"up to (\d+)\s*players", re.IGNORECASE)
MULTIPLAYER_CATEGORIES = {"Multi-player", "Co-op", "Online Co-op", "LAN Co-op", "Shared/Split Screen Co-op",
                          "Online PvP", "PvP", "Shared/Split Screen"}
TAG_CATEGORIES = {"Co-op": "co-op", "Online Co-op": "co-op", "LAN Co-op": "co-op",
                  "PvP": "pvp", "Online PvP": "pvp", "Single-player": "single-player"}
SKIP_GENRES = {"Indie", "Early Access", "Free To Play", "Free to Play"}


def _norm(name: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", name.lower()))


def parse_store_link(link: str) -> Optional[Dict]:
    """{'store': 'steam', 'app_id': 892970} / {'store': 'epic', 'title': 'Alan Wake 2'}, or None."""
    try:
        url = urlparse(link.strip())
    except ValueError:
        return None
    host = (url.hostname or "").lower()
    if url.scheme not in ("http", "https"):
        return None
    if host in STEAM_HOSTS:
        m = re.search(r"/app/(\d+)", url.path)
        return {"store": "steam", "app_id": int(m.group(1))} if m else None
    if host in EPIC_HOSTS:
        m = re.search(r"/p(?:roduct)?/([a-z0-9-]+)", url.path.lower())
        if not m:
            return None
        parts = m.group(1).split("-")
        # Some Epic slugs end in a random id ("alan-wake-2-a1b2c3"): drop it
        if len(parts) > 1 and len(parts[-1]) >= 6 and re.search(r"\d", parts[-1]) and re.search(r"[a-z]", parts[-1]):
            parts = parts[:-1]
        title = " ".join(p if p.isdigit() else p.capitalize() for p in parts if p)
        return {"store": "epic", "title": title} if title else None
    return None


def details_from_steam(data: Dict, review_desc: Optional[str]) -> Dict:
    """Map a Steam appdetails `data` object to add_game fields."""
    genres = [g["description"] for g in data.get("genres", [])]
    categories = {c["description"] for c in data.get("categories", [])}
    text = f"{data.get('short_description', '')} {data.get('about_the_game', '')[:3000]}"
    multiplayer = bool(categories & MULTIPLAYER_CATEGORIES)
    guessed = True
    if m := PLAYERS_RE.search(text):
        lo, hi, guessed = int(m.group(1)), int(m.group(2)), False
    elif m := UP_TO_RE.search(text):
        lo, hi, guessed = 1, int(m.group(1)), False
    else:
        lo, hi = (1, 4) if multiplayer else (1, 1)
    lo, hi = max(1, min(lo, hi)), min(max(lo, hi), 100)

    release = data.get("release_date") or {}
    if release.get("coming_soon"):
        state = "TBA"
    elif "Early Access" in genres:
        state = "early access"
    else:
        state = "full release"

    tags = [g.lower() for g in genres if g not in SKIP_GENRES]
    tags += sorted({t for c, t in TAG_CATEGORIES.items() if c in categories})
    if multiplayer:
        tags = [t for t in tags if t != "single-player"]
        if "co-op" not in tags and "pvp" not in tags:
            tags.append("multiplayer")
    rating = review_desc
    if (data.get("metacritic") or {}).get("score"):
        rating = f"{rating}, Metacritic {data['metacritic']['score']}" if rating else f"Metacritic {data['metacritic']['score']}"
    return {
        "title": data.get("name", "").strip()[:100],
        "min_players": lo, "max_players": hi, "players_guessed": guessed,
        "tags": ", ".join(dict.fromkeys(tags)) or None,
        "release_date": release.get("date") or None,
        "release_state": state,
        "external_rating": rating,
        "category": genres[0].lower() if genres and genres[0] not in SKIP_GENRES else None,
    }


class StoreLookup:
    def __init__(self, timeout: float = 8):
        self.timeout = aiohttp.ClientTimeout(total=timeout)

    async def _json(self, session, path: str, params: Dict) -> Optional[Dict]:
        async with session.get(f"{STEAM_API}{path}", params=params) as resp:
            if resp.status != 200:
                logger.warning(f"Steam {path} returned {resp.status}")
                return None
            return await resp.json(content_type=None)

    async def _steam_search(self, session, title: str) -> Optional[int]:
        found = await self._json(session, "/api/storesearch/", {"term": title, "cc": "us", "l": "en"})
        for item in (found or {}).get("items", []):
            if item.get("type") == "app" and _norm(item.get("name", "")) == _norm(title):
                return item["id"]
        return None

    async def lookup(self, link: str) -> Optional[Dict]:
        """add_game fields for a store link (always includes store_link), or None if the link isn't a store page."""
        parsed = parse_store_link(link)
        if not parsed:
            return None
        base = {"store_link": link.strip()[:300]}
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                app_id = parsed.get("app_id")
                if parsed["store"] == "epic":
                    app_id = await self._steam_search(session, parsed["title"])
                    if app_id is None:
                        return {**base, "title": parsed["title"], "min_players": 1, "max_players": 4, "players_guessed": True}
                details = await self._json(session, "/api/appdetails", {"appids": app_id, "cc": "us", "l": "en"})
                entry = (details or {}).get(str(app_id)) or {}
                if not entry.get("success"):
                    return None
                reviews = await self._json(session, f"/appreviews/{app_id}",
                                           {"json": 1, "language": "all", "purchase_type": "all", "num_per_page": 0})
                review_desc = ((reviews or {}).get("query_summary") or {}).get("review_score_desc")
                info = details_from_steam(entry["data"], review_desc if review_desc and "review" not in review_desc.lower() else None)
                if parsed["store"] == "epic":
                    info["title"] = info["title"] or parsed["title"]
                return {**base, **info}
        except Exception as e:
            logger.warning(f"Store lookup failed for {link!r}: {e!r}")
            if parsed["store"] == "epic":
                return {**base, "title": parsed["title"], "min_players": 1, "max_players": 4, "players_guessed": True}
            return None
