from types import SimpleNamespace
from unittest.mock import AsyncMock

from services.steam_library import SteamImporter, status_from_playtime

STORE = {
    10: {"title": "Valheim", "min_players": 1, "max_players": 10, "players_guessed": False, "tags": "survival, co-op",
         "release_state": "full release", "external_rating": "Very Positive", "store_link": "https://store.steampowered.com/app/10/"},
    20: {"title": "Celeste", "min_players": 1, "max_players": 1, "players_guessed": True, "tags": "platformer"},
    30: None,  # delisted
    40: {"title": "DEEP ROCK GALACTIC", "min_players": 1, "max_players": 4, "players_guessed": False, "tags": "co-op"},
}
OWNED = [{"appid": 10, "name": "Valheim", "playtime_forever": 900, "playtime_2weeks": 60},
         {"appid": 20, "name": "Celeste", "playtime_forever": 0},
         {"appid": 30, "name": "Gone Game", "playtime_forever": 5},
         {"appid": 40, "name": "Deep Rock Galactic", "playtime_forever": 300}]


def importer(db, tmp_path):
    store = SimpleNamespace(lookup=AsyncMock(side_effect=lambda link: STORE[int(link.rstrip("/").rsplit("/", 1)[1])]))
    return SteamImporter(db, store=store, cache_path=str(tmp_path / "cache.json"), sleep=AsyncMock()), store


def test_status_from_playtime():
    assert [status_from_playtime(g) for g in OWNED] == ["playing", "unknown", "played", "played"]


async def test_import_multiplayer_skips_existing_and_caches(temp_db, tmp_path):
    await temp_db.add_game("Deep Rock Galactic", 0, 0, min_players=1, max_players=4)  # from the curated seed
    imp, store = importer(temp_db, tmp_path)
    counts = await imp.run(OWNED, progress=lambda line: None)
    assert counts == {"added": 1, "existing": 1, "single_player": 1, "no_store_page": 1}
    valheim = next(g for g in await temp_db.get_game_library(0) if g["title"] == "Valheim")
    assert (valheim["max_players"], valheim["status"], valheim["guild_id"]) == (10, "playing", 0)
    assert valheim["tags"] == "survival, co-op" or set(valheim["tags"].split(", ")) == {"survival", "co-op"}

    # Re-run: everything comes from the cache, nothing is added twice
    imp2, store2 = importer(temp_db, tmp_path)
    counts = await imp2.run(OWNED, progress=lambda line: None)
    store2.lookup.assert_not_awaited()
    assert counts["added"] == 0 and counts["existing"] == 2


async def test_all_flag_and_dry_run(temp_db, tmp_path):
    imp, _ = importer(temp_db, tmp_path)
    counts = await imp.run(OWNED, multiplayer_only=False, dry_run=True, progress=lambda line: None)
    assert counts["added"] == 3 and counts["single_player"] == 0
    assert await temp_db.get_game_library(0) == []  # dry run wrote nothing


def test_clean_title_and_retry_failed_lookups(temp_db, tmp_path):
    from services.steam_library import clean_title
    assert clean_title("Call of Duty®: Black Ops™ ") == "Call of Duty: Black Ops"


async def test_failed_lookups_retry_once_per_run(temp_db, tmp_path):
    imp, store = importer(temp_db, tmp_path)
    store.lookup = AsyncMock(return_value=None)
    await imp.details(30)
    await imp.details(30)
    assert store.lookup.await_count == 1           # cached for the rest of this run
    imp2, store2 = importer(temp_db, tmp_path)     # next run retries it
    await imp2.details(30)
    store2.lookup.assert_awaited_once()
