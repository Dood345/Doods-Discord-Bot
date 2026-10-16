---
name: ship-check
description: Pre-ship verification for the Discord bot - tests, lint, compile, import smoke test, privacy guard, env/config drift, migrations, real-model routing when the agent changed, and the manual steps the owner must do. Use before shipping (the `ship` skill runs tests and lint again, but not the rest).
---

# Ship check

Run everything; report pass/fail for each with the actual output on failure. Don't declare success on partial results. On Windows use `python -m uv`.

1. **Branch.** `git branch --show-current` is a feature branch, not `main`/`dev`.
2. **Tests.** `python -m uv run pytest -q`
3. **Lint.** `python -m uv run ruff check .` (F + E9: undefined names, unused imports, syntax).
4. **Import smoke test.** `python -m uv run python -c "import main"` (catches cog import errors and config-time crashes without connecting to Discord; fine here, never in tests).
5. **Privacy guard (same as CI).** `git grep -nE '\b[0-9]{17,20}\b|\b192\.168\.[0-9]+\.[0-9]+\b' -- . ':!uv.lock' ':!*.example.json'` prints nothing. `git status --short` shows no `.env`, `*.db`, cookies, `data/` files. Deeper look: `privacy-auditor` agent.
6. **Env drift.** Every `os.getenv('X')` has a line in `.env.example`, and new features have a line in `utils/config_report.py`. List env vars added in this branch (`git diff main...HEAD -- config.py .env.example`).
7. **Schema.** If the diff touches `setup_tables` or table definitions of an existing table, a migration exists with a prod-fixture test (`db-migration` skill).
8. **Agent.** If the system prompt, tool descriptions or tool schemas changed: `python -m uv run python scripts/route_bench.py` passes against the real model (`real-model-check` skill).
9. **Review.** Non-trivial diff and `bot-reviewer` hasn't run on it: run it.
10. **Report:**
    - Checks: pass/fail list
    - Before shipping: env vars to add to the server's `.env`; private files under `data/` on the server
    - After deploy: `!sync .` per server (or `!sync`) if commands/context menus changed; opt-in commands managers must run; what can only be verified in Discord
