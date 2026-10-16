---
name: doodlab-ops
description: Work on the production server ("doodlab") safely - logs, service state, .env edits, prod-DB copies, long-running jobs, backups and restores, deploy rollbacks. Use whenever a task needs to look at or change anything on the server.
---

# Working on the doodlab

- SSH alias: `doodlab` (key in the owner's `~/.ssh`). Bot at `/home/dood345/discordBot`, venv at `venv/` (run things with `venv/bin/python` from the repo root), systemd unit `discordBot.service`.
- Passwordless sudo covers **only** `sudo systemctl restart discordBot.service`. Not stop/start, nothing else.
- Logs: `data/logs/bot.log`. Useful greps: `Agent tool call` (what Cave decided), `Features on|Feature off|Config check` (startup config report), `Applying database migration`, `Music sessions saved|Resumed music`, `Unhandled error`.
- The owner's PC (this machine) runs Ollama, Plex, Overseerr and ComfyUI; the server reaches them over the LAN. If AI/Plex/requests fail, check the PC side first.

## Golden rules
1. **Never print secret values or LAN addresses** into the conversation. Mask when showing config: `grep -E "^PRINTER" .env | tr -d "\r" | sed -E "s/(192\.168\.[0-9]+)\.[0-9]+/\1.x/"`; for keys only show whether they're set (`grep -c "^KEY=.\+" .env`).
2. **Back up before changing anything**: `.env` -> `cp .env data/backups/env-before-<change>`; DB -> `venv/bin/python -c "import sqlite3; s=sqlite3.connect('data/doodlab.db'); d=sqlite3.connect('data/backups/doodlab-pre-<change>.db'); s.backup(d)"`.
3. **Experiment on copies**: copy `data/doodlab.db` to a temp dir (or a temp checkout with `rsync -a --exclude venv --exclude data`) and point the code at it. Clean up `/tmp` afterwards.
4. **Don't trust a harness that returns instantly or empty**: print real output (see the `real-model-check` skill).

## .env edits (the owner allows them)
- The file mixes CRLF and LF lines. python-dotenv copes; shell tools don't: strip `\r` (`tr -d "\r"`) when reading values in bash, or curl fails with "malformed URL".
- Edit single lines with `sed -i "s#^KEY=.*#KEY=value#"` after the backup, then `sudo systemctl restart discordBot.service` (config is read at import).
- Check the result in the startup config report: `grep -E "Features on|Feature off|Config check" data/logs/bot.log | tail -5`.

## Long jobs
Run detached and poll a log or cache: `nohup venv/bin/python -m utils.import_steam_library --dry-run > data/steam_dryrun.log 2>&1 &`. Output to a file is block-buffered, so watch a side effect (cache size, DB rows) for progress. Deploys restart the bot but don't kill these.

## Backups and restores
- Automatic: `data/backups/auto-nightly-*.db` (03:30 local, 14 kept), `auto-premigrate-*.db` (before migrations, 5 kept). Manual ones: `doodlab-pre-*.db`, `env-before-*`.
- Restore a DB: back up the current one, copy the backup over `data/doodlab.db`, restart. (The bot writes to the DB constantly; restoring under a running bot then restarting is acceptable here because the restart re-reads it, but take the extra backup first.)

## Deploys
- Each deploy snapshots the running release to `/home/dood345/discordBot.prev` (code + venv), and rolls back to it automatically if the bot doesn't write a fresh `data/ready.json` within 120 s. A rolled-back deploy shows as a failed run on GitHub with a "Rolled back" warning.
- Manual rollback: `rsync -a --delete --exclude=.env --exclude=data --exclude=.git --exclude=www.youtube.com_cookies.txt /home/dood345/discordBot.prev/ /home/dood345/discordBot/ && sudo systemctl restart discordBot.service`.
- The rollback path can be exercised from GitHub Actions: run "Deploy to Doodlab" with `simulate_failure` (needs the owner's GitHub login).
