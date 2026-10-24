"""Tool-routing benchmark against the REAL model (Ollama on the dev PC). Tools are stubbed, so nothing happens.

    python -m uv run python scripts/route_bench.py                 # default cases
    python -m uv run python scripts/route_bench.py --poison "what are science points?=Science Points are your intellectual currency..."

Re-run after changing the system prompt, a tool description or the model. Each case is
(message, expected tool or None). History is seeded with realistic chit-chat, because short clean histories
hide routing failures that show up in production. --poison adds a (question=bad answer) exchange to the
history several times, to check the model calls the tool instead of copying an earlier wrong reply.
See .claude/skills/real-model-check/SKILL.md.
"""

import argparse
import asyncio
import logging
import os
import sys
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(ROOT, ".env"))
os.environ.setdefault("OLLAMA_URL", "http://localhost:11434")
if not os.environ.get("OLLAMA_MODEL"):
    # The dev .env may not name the production model: use the chat model Ollama actually has
    import json
    import urllib.request
    tags = json.load(urllib.request.urlopen(os.environ["OLLAMA_URL"].rstrip("/") + "/api/tags", timeout=10))
    chat_models = [m["name"] for m in tags.get("models", []) if "embed" not in m["name"]]
    if not chat_models:
        sys.exit("No chat model on the Ollama server")
    os.environ["OLLAMA_MODEL"] = chat_models[0]
logging.disable(logging.CRITICAL)

import utils.agent as agent  # noqa: E402
from config import BotConfig  # noqa: E402
from utils.ai_handler import AIHandler  # noqa: E402
from utils.database import DatabaseHandler  # noqa: E402

DEFAULT_CASES = [
    ("play some 3 doors down", "queue_song"),
    ("start a 3 doors down radio", "queue_song"),
    ("play the portal soundtrack", "queue_song"),
    ("skip this song", "skip_song"),
    ("can you resume the playlist", "resume_music"),
    ("whats playing right now", "now_playing"),
    ("what should 4 of us play tonight?", "recommend_games"),
    ("I'd give valheim a 9/10", "rate_game"),
    ("add this https://store.steampowered.com/app/892970/Valheim/", "add_game"),
    ("what are science points and how do I get them?", "science_points"),
    ("who's winning the leaderboard?", "science_points"),
    ("remember that I main Dwarf in Deep Rock", "remember_fact"),
    ("how's the 3d print going?", "printer_status"),
    ("draw me a turret wearing a party hat", "generate_image"),
    ("how are you today cave", None),
    ("describe a sunset to me in one sentence", None),
    ("what's the capital of australia?", None),
]
CHIT_CHAT = [("?", "A question, volunteer? Fantastic!"),
             ("good afternoon", "Good afternoon, Test Subject! Ready to maximize our scientific dividends!"),
             ("write me a poem", "From hot plastic soup we build the future...")]


async def main(args):
    db = DatabaseHandler(db_path=os.path.join(tempfile.mkdtemp(), "bench.db"))
    await db.setup_tables()
    history = CHIT_CHAT * 3
    for spec in args.poison or []:
        question, bad = spec.split("=", 1)
        history = [(question, bad)] * 2 + history + [(question, bad)] * 2
    for user_msg, reply in history:
        await db.add_ai_message(1, 5, "user", user_msg)
        await db.add_ai_message(1, 5, "model", reply)

    music = MagicMock()
    music.get_music_status = lambda guild: "Nothing is currently playing."
    bot = SimpleNamespace(db=db, homelab_service=MagicMock(), dialogue=None, game_service=MagicMock(),
                          get_cog=lambda name: music)
    handler = AIHandler(db, bot)
    handler._background_memory = AsyncMock()
    db.add_ai_message = AsyncMock()  # keep the seeded history identical for every case
    owner = SimpleNamespace(id=BotConfig.OWNER_ID or 1, name=(BotConfig.ALLOWED_USERS or ["owner"])[0], display_name="Owner")
    channel = MagicMock()
    channel.send = AsyncMock(return_value=SimpleNamespace(content="card", edit=AsyncMock()))
    called = []

    async def stub_dispatch(self, name, tool_args, ctx):
        called.append(name)
        return "PENDING: posted a confirmation button. NOTHING has happened yet."
    agent.ToolRegistry.dispatch = stub_dispatch

    hits = 0
    for message, want in DEFAULT_CASES:
        for _ in range(args.runs):
            called.clear()
            handler._last_chat.clear()
            start = time.time()
            reply = await handler.get_chat_response(1, message, guild_id=5, user=owner, guild=SimpleNamespace(id=5),
                                                    channel=channel, persona=args.persona)
            if not reply:
                # A None reply means the model call itself failed: that's a broken harness, not a routing miss
                sys.exit(f"Model call failed for {message!r} (model {os.environ['OLLAMA_MODEL']}); check OLLAMA_URL/OLLAMA_MODEL")
            ok = (want in called) if want else not called
            hits += ok
            print(f"{'OK  ' if ok else 'MISS'} want={want} got={called} [{time.time() - start:.1f}s] | {message}")
    total = len(DEFAULT_CASES) * args.runs
    print(f"routing {hits}/{total}")
    return 0 if hits == total else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tool-routing benchmark against the real model")
    parser.add_argument("--runs", type=int, default=1, help="repeat each case (the model isn't deterministic)")
    parser.add_argument("--poison", action="append", help="'question=bad answer' to seed into history")
    parser.add_argument("--persona", help="a key from content/personas.json: route as that channel persona")
    sys.exit(asyncio.run(main(parser.parse_args())))
