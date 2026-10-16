"""Import the owner's Steam library into the shared game library (guild_id 0).

Owned games come from the Steam Web API (needs STEAM_API_KEY + STEAM_ID, and the profile's
game details set to public); details for each game come from the same store lookup that
/game add link: uses. Store lookups are cached on disk and spaced out, because Steam's store
API allows roughly 200 requests per 5 minutes (each game needs 2).
"""

import asyncio
import json
import logging
import os
import re
from typing import Callable, Dict, List, Optional

import aiohttp

from services.store_lookup import StoreLookup, _norm

logger = logging.getLogger(__name__)

WEB_API = "https://api.steampowered.com"
LOOKUP_DELAY = 3.0  # seconds between uncached store lookups


async def resolve_steam_id(session, key: str, steam_id: str) -> Optional[str]:
    """A 17-digit SteamID64 as-is, or a vanity name (steamcommunity.com/id/<name>) resolved to one."""
    if steam_id.isdigit():
        return steam_id
    async with session.get(f"{WEB_API}/ISteamUser/ResolveVanityURL/v1/",
                           params={"key": key, "vanityurl": steam_id}) as resp:
        data = (await resp.json(content_type=None)).get("response", {})
    return data.get("steamid") if data.get("success") == 1 else None


async def owned_games(key: str, steam_id: str) -> List[Dict]:
    """[{appid, name, playtime_forever, playtime_2weeks?}]. Raises ValueError with a readable reason."""
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
        sid = await resolve_steam_id(session, key, steam_id)
        if not sid:
            raise ValueError(f"Couldn't resolve Steam ID '{steam_id}'")
        async with session.get(f"{WEB_API}/IPlayerService/GetOwnedGames/v1/",
                               params={"key": key, "steamid": sid, "include_appinfo": 1,
                                       "include_played_free_games": 1, "format": "json"}) as resp:
            if resp.status in (401, 403):
                raise ValueError("Steam rejected the API key")
            data = (await resp.json(content_type=None)).get("response", {})
    if "games" not in data:
        raise ValueError("No games returned: set Steam profile > Privacy > Game details to Public")
    return data["games"]


def clean_title(title: str) -> str:
    """'Rocket League®' -> 'Rocket League' (trademark symbols just get in the way of search)."""
    return " ".join(re.sub(r"[®™©]", "", title).split())


def status_from_playtime(game: Dict) -> str:
    if game.get("playtime_2weeks"):
        return "playing"
    return "played" if game.get("playtime_forever") else "unknown"


class SteamImporter:
    def __init__(self, db, store: Optional[StoreLookup] = None, cache_path: str = "data/steam_import_cache.json",
                 delay: float = LOOKUP_DELAY, sleep: Callable = asyncio.sleep):
        self.db = db
        self.store = store or StoreLookup()
        self.cache_path = cache_path
        self.delay = delay
        self.sleep = sleep
        self.cache: Dict[str, Optional[Dict]] = {}
        self._retried = set()
        if cache_path and os.path.exists(cache_path):
            with open(cache_path, encoding="utf-8") as f:
                self.cache = json.load(f)

    def _save_cache(self):
        if self.cache_path:
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(self.cache, f)

    async def details(self, appid: int) -> Optional[Dict]:
        key = str(appid)
        # Failed lookups (timeouts, delisted pages) are retried once per run
        if key not in self.cache or (self.cache[key] is None and key not in self._retried):
            self._retried.add(key)
            self.cache[key] = await self.store.lookup(f"https://store.steampowered.com/app/{appid}/")
            self._save_cache()
            await self.sleep(self.delay)
        return self.cache[key]

    async def run(self, games: List[Dict], multiplayer_only: bool = True, dry_run: bool = False,
                  progress: Callable[[str], None] = print) -> Dict[str, int]:
        existing = {_norm(g["title"]) for g in await self.db.get_game_library(0)}
        counts = {"added": 0, "existing": 0, "single_player": 0, "no_store_page": 0}
        for i, game in enumerate(sorted(games, key=lambda g: -g.get("playtime_forever", 0)), 1):
            info = await self.details(game["appid"])
            if not info:
                counts["no_store_page"] += 1  # delisted, DLC-only, tools, region-locked...
                continue
            title = clean_title(info["title"] or game.get("name", ""))
            if _norm(title) in existing:
                counts["existing"] += 1
                continue
            if multiplayer_only and info["max_players"] <= 1:
                counts["single_player"] += 1
                continue
            existing.add(_norm(title))
            counts["added"] += 1
            progress(f"[{i}/{len(games)}] + {title} ({info['min_players']}-{info['max_players']} players)")
            if dry_run:
                continue
            await self.db.add_game(
                title=title, added_by=0, guild_id=0,
                tags=[t.strip() for t in (info.get("tags") or "").split(",") if t.strip()],
                min_players=info["min_players"], max_players=info["max_players"],
                status=status_from_playtime(game), external_rating=info.get("external_rating"),
                release_date=info.get("release_date"), release_state=info.get("release_state"),
                category=info.get("category"), store_link=info.get("store_link"),
                notes="From the boss's Steam library" + (" (player count guessed)" if info.get("players_guessed") else ""))
        return counts
