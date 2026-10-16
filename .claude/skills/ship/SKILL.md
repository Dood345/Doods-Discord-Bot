---
name: ship
description: Ship a finished change to production the way this repo does it - feature branch, commit, scripts/ship.ps1 (local tests + lint, dev CI, main deploy with health check and auto-rollback), then verify on the server. Use whenever a change is ready to go live.
---

# Shipping a change

Production deploys on every push to `main`, so shipping is mechanical and strict. The owner wants changes live on the next build; don't stop at "committed".

## 1. Branch and commit
- Work on a feature branch cut from an up-to-date `main` (`git checkout main && git pull --ff-only && git checkout -b feat/<thing>`). Never commit to `dev` or `main` directly.
- Run the suite **before** committing and chain with `&&`, never `;` (a red commit once got pushed because the commit ran after a failing test):
  `python -m uv run pytest -q 2>&1 | tail -1 && python -m uv run ruff check . && git add -A && git commit -m "..."`
- Commit message: what changed and why in plain words, the real-model or prod-copy evidence if any, `Fixes #N` for issues, and the attribution line the session asks for.

## 2. Ship
```
pwsh scripts/ship.ps1 <branch>        # Windows dev PC: & "scripts\ship.ps1" <branch> from PowerShell
```
It refuses to run with uncommitted changes, re-runs tests + lint, merges into `dev`, waits for **Build Verification**, merges into `main`, waits for **Deploy to Doodlab** (which waits for the bot to write a fresh `data/ready.json` and rolls back to the previous release if it doesn't within 120 s), then prints the service state. Run it in the background for long waits and keep working on files that the branch switch won't touch (new untracked files are safe; tracked files are not, because the script checks out `dev` and `main`).

If dev CI fails: read the failing step (`Invoke-RestMethod <run.jobs_url>`), fix on the branch, commit, ship again. Common: privacy guard tripped by a 17–20 digit number in a test.

## 3. Verify on the server
Use the `doodlab-ops` skill (or the `ops-checker` agent): service active, no new errors since the restart, the feature's own log lines, and for DB changes the migration lines. Check the actual behavior when you can (run the new code path against the live config or a prod DB copy). "Deploy: success" only means the bot came online.

## 4. Tell the owner
- What's live and what was verified (and what wasn't: e.g. "not tried in Discord yet").
- `!sync .` per server (or `!sync` once) when slash commands or context menus were added or changed.
- New env vars: add to `.env.example` in the change, and either add them to the server `.env` yourself (owner has allowed it; back up first) or tell the owner exactly which to add.
- Opt-in features stay off until a manager enables them; say which command turns them on.
