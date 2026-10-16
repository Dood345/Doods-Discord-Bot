"""Replay a chat message against a COPY of the production DB with the real model. Run ON THE SERVER:

    ssh doodlab 'cd /home/dood345/discordBot && venv/bin/python scripts/prod_replay.py "what are science points?" --runs 3'
    ... --dump    # print the memory block and history the model receives instead of calling it

Answers "why did Cave do that?" for a Discord report: it uses the owner's real history, summary, notes and
recall, but tools are stubbed (nothing is queued, requested or saved) and the DB is a temp copy. Uses the
owner's ID by default (--user to change) and the first guild in server_contexts (--guild).
See .claude/skills/real-model-check/SKILL.md.
"""

import argparse
import asyncio
import logging
import os
import shutil
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import AsyncMock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
from dotenv import load_dotenv  # noqa: E402

# load_dotenv() with no path searches from the *script's* folder; be explicit
load_dotenv(os.path.join(ROOT, ".env"))
logging.disable(logging.CRITICAL)

import utils.agent as agent  # noqa: E402
from config import BotConfig  # noqa: E402
from utils.ai_handler import AIHandler  # noqa: E402
from utils.database import DatabaseHandler  # noqa: E402


async def main(args):
    copy = os.path.join(tempfile.mkdtemp(), "replay.db")
    shutil.copy(os.path.join("data", "doodlab.db"), copy)
    db = DatabaseHandler(db_path=copy)
    handler = AIHandler(db, SimpleNamespace(db=db, dialogue=None, get_cog=lambda name: None))
    if not handler.is_available():
        print("AI is disabled (OLLAMA_URL missing from .env?)")
        return 1
    handler._background_memory = AsyncMock()
    db.add_ai_message = AsyncMock()  # keep history fixed between runs
    user_id = args.user or BotConfig.OWNER_ID
    guild_id = args.guild or (sorted(BotConfig.SERVER_CONTEXTS)[0] if BotConfig.SERVER_CONTEXTS else None)
    user = SimpleNamespace(id=user_id, name=(BotConfig.ALLOWED_USERS or ["owner"])[0], display_name="Replay")
    guild = SimpleNamespace(id=guild_id) if guild_id else None

    if args.dump:
        handler._chat = AsyncMock(return_value={"content": "(dump)"})
        await handler.get_chat_response(user_id, args.message, guild_id=guild_id, user=user, guild=guild)
        messages = handler._chat.call_args.args[0]
        system = messages[0]["content"]
        marks = [i for i in (system.find("NOTES THIS USER"), system.find("SUMMARY OF"), system.find("OLDER EXCHANGES")) if i >= 0]
        print("=== MEMORY ===\n" + (system[min(marks):] if marks else "(none)"))
        print("=== HISTORY ===")
        for m in messages[1:]:
            print(f"{m['role']:9} | {m['content'][:160]}".replace("\n", " "))
        return 0

    called = []

    async def stub_dispatch(self, name, tool_args, ctx):
        called.append(f"{name}({tool_args})")
        return "Tool result unavailable in this replay."
    agent.ToolRegistry.dispatch = stub_dispatch
    for run in range(1, args.runs + 1):
        called.clear()
        handler._last_chat.clear()
        reply = await handler.get_chat_response(user_id, args.message, guild_id=guild_id, user=user, guild=guild)
        if not reply:
            print("The model call failed (reply was empty); check Ollama is up and OLLAMA_MODEL in .env")
            return 1
        print(f"run {run}: tools={called or 'none'}")
        print(f"  reply: {reply[:300]}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Replay a chat message against a copy of the prod DB")
    parser.add_argument("message")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--user", type=int)
    parser.add_argument("--guild", type=int)
    parser.add_argument("--dump", action="store_true", help="show what the model would receive")
    sys.exit(asyncio.run(main(parser.parse_args())))
