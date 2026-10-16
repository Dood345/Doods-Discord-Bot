---
name: real-model-check
description: Check Cave's behavior against the real Ollama model instead of mocks - the routing benchmark after prompt/tool changes, and prod-copy replays when a Discord user reports Cave doing something wrong. Use after touching the system prompt, tool descriptions/schemas or the model, and to root-cause any "Cave said/did X" report.
---

# Real-model checks

Unit tests mock the model, so they can't tell you whether the 12B model will call the right tool. Two scripts can.

## Routing benchmark (dev PC, model on Ollama here)
```
python -m uv run python scripts/route_bench.py            # 14 cases covering every tool + one chit-chat
python -m uv run python scripts/route_bench.py --runs 3   # the model isn't deterministic
python -m uv run python scripts/route_bench.py --poison "what are science points?=<the bad answer>"
```
- Add a case to `DEFAULT_CASES` for every new tool, plus a near-miss phrasing for any tool it could be confused with.
- Expect 100%. A miss usually means the routing list in `AIHandler.get_chat_response`'s system prompt needs a line, or two tool descriptions overlap.
- Seeded chit-chat history matters: clean histories hide failures that production shows.

## Replay a real conversation (on the server, real history, tools stubbed)
```
ssh doodlab 'cd /home/dood345/discordBot && venv/bin/python scripts/prod_replay.py "<the user message>" --runs 3'
ssh doodlab 'cd /home/dood345/discordBot && venv/bin/python scripts/prod_replay.py "<the user message>" --dump'
```
Uses a temp copy of `data/doodlab.db`, so the owner's real history, summary, notes and recall are in play and nothing is written. `--dump` prints exactly what the model receives (memory block + history); read it before theorizing. Compare against the deployed code first (reproduce), then copy the changed files into a temp checkout on the server and replay again to prove the fix:
```
ssh doodlab 'rm -rf /tmp/rc && rsync -a --exclude venv --exclude data /home/dood345/discordBot/ /tmp/rc/ && ln -s /home/dood345/discordBot/data /tmp/rc/data'
scp utils/ai_handler.py doodlab:/tmp/rc/utils/
ssh doodlab 'cd /tmp/rc && /home/dood345/discordBot/venv/bin/python scripts/prod_replay.py "..." ; rm -rf /tmp/rc'
```

## Harness traps (each has cost real time)
- **A result of 0/N with instant timings is a broken harness, not a model result.** Print the reply; `None` means the call failed (AI disabled, wrong model name, exception swallowed by `get_chat_response`).
- `load_dotenv()` with no path searches from the *script's* folder; pass the repo's `.env` explicitly.
- The dev `.env` may not set `OLLAMA_MODEL`; the default name doesn't exist on Ollama. `route_bench.py` picks the installed chat model.
- Stub `ToolRegistry.dispatch` and `AIHandler._background_memory`, and make `db.add_ai_message` a no-op so runs don't pollute each other.
- Don't import `main` in tests or harnesses (it loads `.env` and configures logging at import).

## What earlier rounds found this way
- Cave copied his own earlier wrong answer when the same question sat in his 10-message window: fixed with `drop_repeated_question` (reproduced only with the real history).
- Tool output without the real rules made Cave invent Science Points rules: tool results must contain the facts you want repeated.
- Small-model routing: temperature 0.3, an explicit intent -> tool list, hints for links (YouTube, store links).
