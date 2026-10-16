"""Ops housekeeping: nightly database backups and the readiness marker the deploy waits for."""

import asyncio
import glob
import json
import logging
import os
import time
from datetime import time as dtime
from zoneinfo import ZoneInfo

from discord.ext import commands, tasks

from config import BotConfig
from utils import migrations

logger = logging.getLogger(__name__)

NIGHTLY_KEEP = 14                 # two weeks of nightly backups
BACKUP_TIME = dtime(3, 30, tzinfo=ZoneInfo(BotConfig.BOT_TIMEZONE))
MAX_BACKUP_AGE = 26 * 60 * 60     # take one at startup if the newest is older than this (bot was down at 3:30)
READY_FILE = os.path.join("data", "ready.json")


def write_ready_marker(path: str = READY_FILE, guilds: int = 0) -> None:
    """Written in on_ready. The deploy workflow restarts the bot and waits for this file to be newer than
    the restart; if it never is, the deploy rolls back to the previous release."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"ready_at": time.time(), "pid": os.getpid(), "guilds": guilds}, f)
    os.replace(tmp, path)


def newest_backup_age(db_path: str, label: str = "nightly", now: float = None) -> float:
    folder = os.path.join(os.path.dirname(db_path) or ".", "backups")
    files = glob.glob(os.path.join(folder, f"auto-{label}-*.db"))
    if not files:
        return float("inf")
    return (now or time.time()) - max(os.path.getmtime(f) for f in files)


class Maintenance(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.nightly_backup.start()
        if newest_backup_age(self.bot.db.db_path) > MAX_BACKUP_AGE:
            await self.backup_now()

    async def cog_unload(self):
        self.nightly_backup.cancel()

    async def backup_now(self) -> str:
        path = await asyncio.to_thread(migrations.backup, self.bot.db.db_path, "nightly", NIGHTLY_KEEP)
        logger.info(f"Database backup written: {path}")
        return path

    @tasks.loop(time=BACKUP_TIME)
    async def nightly_backup(self):
        try:
            await self.backup_now()
        except Exception as e:
            logger.exception(f"Nightly backup failed: {e}")


async def setup(bot):
    await bot.add_cog(Maintenance(bot))
