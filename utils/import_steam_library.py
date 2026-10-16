"""Import the owner's Steam games into the shared game library.

Run from the repo root (on the server: /home/dood345/discordBot):
    venv/bin/python -m utils.import_steam_library --dry-run   # preview, writes nothing
    venv/bin/python -m utils.import_steam_library             # multiplayer/co-op games only
    venv/bin/python -m utils.import_steam_library --all       # include single-player games

Needs STEAM_API_KEY (https://steamcommunity.com/dev/apikey) and STEAM_ID (SteamID64 or the
vanity name from steamcommunity.com/id/<name>) in .env, and Steam profile > Privacy >
Game details set to Public. Safe to re-run: existing titles are skipped and store lookups
are cached in data/steam_import_cache.json (first run takes ~3 s per game).
"""

import argparse
import asyncio
import sys

from dotenv import load_dotenv

load_dotenv()

from config import BotConfig  # noqa: E402  (after load_dotenv, like main.py)
from services.steam_library import SteamImporter, owned_games  # noqa: E402
from utils.database import DatabaseHandler  # noqa: E402


async def main(include_single_player: bool, dry_run: bool) -> int:
    if not BotConfig.STEAM_API_KEY or not BotConfig.STEAM_ID:
        print("Set STEAM_API_KEY and STEAM_ID in .env first.")
        return 1
    try:
        games = await owned_games(BotConfig.STEAM_API_KEY, BotConfig.STEAM_ID)
    except ValueError as e:
        print(f"Steam: {e}")
        return 1
    print(f"🔬 {len(games)} games in the Steam library. Looking them up (cached lookups are instant)...")
    db = DatabaseHandler()
    await db.setup_tables()
    counts = await SteamImporter(db).run(games, multiplayer_only=not include_single_player, dry_run=dry_run)
    verb = "Would add" if dry_run else "Added"
    print(f"\n{verb} {counts['added']} games. Already in the library: {counts['existing']}. "
          f"Skipped single-player: {counts['single_player']}. No store page: {counts['no_store_page']}.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--all", action="store_true", help="also import single-player games")
    parser.add_argument("--dry-run", action="store_true", help="show what would be added without writing")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.all, args.dry_run)))
