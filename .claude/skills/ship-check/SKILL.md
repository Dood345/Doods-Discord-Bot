---
name: ship-check
description: Pre-PR / pre-merge verification for the Discord bot - tests, compile, import smoke test, privacy guard, env/config drift, and the manual deploy steps the owner must do. Use before opening a PR to dev or merging dev into main.
---

# Ship check

Run everything; report pass/fail for each with the actual output on failure. Don't declare success on partial results.

On Windows use `python -m uv`; on Linux/macOS use `uv`.

1. **Branch.** `git branch --show-current` must not be `main` (pushing to `main` deploys immediately). PRs target `dev`.
2. **Tests.** `python -m uv run pytest -q`
3. **Compile.** `python -m uv run python -m compileall -q . -x "\.venv"`
4. **Import smoke test.** `python -m uv run python -c "import main"` (catches cog import errors and config-time crashes without connecting to Discord).
5. **Privacy guard (same as CI).**
   `git grep -nE '\b[0-9]{17,20}\b|\b192\.168\.[0-9]+\.[0-9]+\b' -- . ':!uv.lock' ':!*.example.json'` must print nothing. Also make sure `git status --short` shows no `.env`, `*.db`, cookies, `.coverage` or `data/server_contexts.json`. For a deeper look, use the `privacy-auditor` agent.
6. **Env drift.** Every `os.getenv('X')` in the code (`git grep -ohE "getenv\('[A-Z_]+'"`) has a line in `.env.example`. List any env vars *added in this branch* (`git diff dev...HEAD -- config.py .env.example`).
7. **Review.** If the diff is more than trivial and `bot-reviewer` hasn't run on it, run it.
8. **Report** in this shape:
   - Checks: pass/fail list
   - Manual steps before merging to `main`: env vars to add to the server's `.env`; private files to create under `data/` on the server (e.g. `data/server_contexts.json`); DB columns that need an `ALTER TABLE`
   - After deploy: `!sync` if slash commands were added/renamed/changed
