# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Dependencies are managed with `uv` (`pyproject.toml` + `uv.lock`; requires Python >=3.14). On this Windows dev machine `uv` is invoked as `python -m uv`.

```bash
python -m uv sync                                   # install deps (incl. dev group)
python -m uv run python main.py                     # run the bot (needs .env)
python -m uv run pytest                             # full test suite (testpaths = tests)
python -m uv run pytest tests/utils/test_database.py::test_name -v   # single test
python -m uv run pytest --cov=utils --cov=services  # coverage
python -m uv run python utils/seed_games.py         # seed games table in data/doodlab.db
python -m uv run python utils/verify_db.py          # inspect DB contents
```

`pytest.ini` sets `asyncio_mode = auto` and `pythonpath = .`, so async tests need no decorator. `tests/conftest.py` provides `temp_db` (a `DatabaseHandler` on a tmp SQLite file with tables created) and `mock_config`.

AI tests mock `AIHandler._generate` (the single Ollama HTTP call); never hit a real model in tests. With `OLLAMA_URL` unset the handler starts disabled (`client is None`), so tests set `handler.client = True`.

Slash commands are **not** auto-synced on startup. After adding/changing an `app_commands` command, the owner runs the prefix command `!sync .` (instant, current guild), `!sync` (global, ~1h), or `!sync clear` in Discord. The `sync` command is defined inside `main.py`'s `__main__` block.

## Architecture

discord.py bot (`DoodsBot` in `main.py`, a `commands.Bot` subclass). `load_dotenv()` runs **before** `config` is imported because `BotConfig` reads env vars at class-definition time.

Shared singletons are attached to the bot in `DoodsBot.__init__` and accessed by cogs via `self.bot.<name>`:
- `bot.config` — `BotConfig` (`config.py`): character prompts/info, keyword reactions, homelab service IPs/URLs/API keys, auth (`OWNER_ID`, `ALLOWED_USERS`). `SERVER_CONTEXTS` (per-guild persona text, int guild ID → str) is loaded from the gitignored `data/server_contexts.json` (format: `data/server_contexts.example.json`); missing file → `{}`.
- `bot.db` — `DatabaseHandler` (`utils/database.py`): async `aiosqlite`, opens a new connection per call, default path `data/doodlab.db`. Tables (`gifts`, `ai_history`, `games`, `game_ratings`, `tags`, `game_tags`) are created in `setup_tables()` with `CREATE TABLE IF NOT EXISTS` — there are no migrations; `utils/reset_game_tables.py` drops/recreates game tables.
- `bot.dialogue` — `DialogueManager` (`utils/dialogue_manager.py`): static, user-facing strings live in `content/dialogue.json` (tracked and deployed; `data/` is runtime state only) keyed `character -> response_type -> [variants]`; `dialogue.get(char, type, fallback=..., **fmt_kwargs)` picks a random variant and `.format()`s it. Prefer adding strings here over hardcoding them in cogs.
- `bot.gift_service`, `bot.game_service` — service layer (`services/`) wrapping DB + dialogue logic so cogs stay thin. Tests target services and utils, not cogs.
- `bot.ai_handler` — `AIHandler` (`utils/ai_handler.py`).
- `bot.reaction_handler` — keyword emoji reactions from `config.KEYWORD_REACTIONS`.

Cogs live in `commands/` and are registered explicitly in `DoodsBot.setup_hook()` — a new cog must be imported and `add_cog`'d there. Most commands are slash commands (`app_commands`); prefix is `!`.

**AI backend:** a local **Ollama** server (`OLLAMA_URL` env var, model from `OLLAMA_MODEL`, non-streaming `/api/generate` with `think: false`). The default persona is "Cave Johnson" (Portal). `get_chat_response` builds a single prompt from: last 20 `ai_history` rows for the user (global across guilds), optional reply context, the guild's `SERVER_CONTEXTS` entry, and a lightweight game-recommendation RAG triggered by keyword intent detection that injects `db.recommend_games(...)` output. Character commands (`/hank`, `/dale`, ...) use `CHARACTER_PROMPTS` and fall back to `dialogue.json` `fallback` entries when AI fails. `on_message` in `main.py` routes @mentions to `get_chat_response`.

**Homelab cog** (`commands/homelab_commands.py`): printer (Moonraker/webcam via `PRINTER_HOST`), service pings, Overseerr/Sonarr/Radarr/Lidarr. Every command must call `await self.check_auth(interaction)` (owner ID or username in `ALLOWED_USERS`).

**Image generation** (`utils/image_gen.py` + `commands/image_cog.py`): talks to ComfyUI (`COMFY_URL`) using the workflow JSON `utils/image_z_image_turbo.json`, with blocking `urllib`/websocket calls run via `run_in_executor`.

**Music** (`commands/music.py`): yt-dlp + ffmpeg (must be on PATH) voice playback, `edge-tts` announcements; uses `www.youtube.com_cookies.txt` in the repo root (untracked).

## Privacy rules (repo is public)

Never commit real Discord guild/user/channel IDs, LAN IPs/hostnames, friends' names, or homelab URLs. Real values go in `.env` (documented in `.env.example`) or private files under `data/` (gitignored, and preserved on the server because deploy excludes `data/`). CI's privacy-guard step fails on 17–20 digit numbers and `192.168.x.x` in tracked files. Any new env var must be added to `.env.example` and the user told to add it to the server's `.env` before merging to `main`.

## Deployment / CI

- Push to `main` → `.github/workflows/deploy.yml` on a self-hosted runner: rsyncs the repo to `/home/dood345/discordBot/` (excluding `.env`, `data/`, `venv`, cookies file), runs `uv sync --no-dev`, restarts `discordBot.service` via systemd. Anything under `data/` (DB, logs, `server_contexts.json`) is server-local and never deployed; tracked content like dialogue lives in `content/`.
- PRs to `main`/`dev` → `build.yml`: `uv sync`, compileall, `pytest`, privacy guard.
- Workflow is feature branch → `dev` → `main`. Never push straight to `main` (it deploys).
- Overhaul roadmap and per-phase kickoff prompts: `docs/ROADMAP.md`.
