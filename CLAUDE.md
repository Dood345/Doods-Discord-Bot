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

AI tests mock `AIHandler._chat` (agent path) or `AIHandler._generate` (one-shot prompts); never hit a real model in tests. With `OLLAMA_URL` unset the handler starts disabled (`client is None`), so tests set `handler.client = True`.

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

**AI backend:** a local **Ollama** server (`OLLAMA_URL`, model from `OLLAMA_MODEL`, always `think: false`). The default persona is "Cave Johnson" (Portal).
- **Chat (@mention) is an agent.** `AIHandler.get_chat_response` builds a `/api/chat` message list (system persona + `SERVER_CONTEXTS` entry + a clearance line from `is_authorized(user)`, last 10 `ai_history` rows as turns with `model`→`assistant` (longer chit-chat history made the 12B model skip tools), then the user message with any reply context quoted as untrusted and a `queue_song` hint if it contains a YouTube link). It then calls `utils.agent.run_agent`, which loops model → tool calls → results (max 4 rounds, per-tool and overall timeouts). If the loop fails it falls back to one plain chat call. Only the final user/assistant pair is saved to memory. After each reply a background job (`_summarize_history`) folds messages older than the prompt window into a per-user rolling summary (`ai_summaries` table, batches of 20, max 800 chars) that is injected as delimited background; tests disable it via an autouse fixture unless marked `real_summaries`. Replies stream: `get_chat_response(on_text=...)` streams Ollama tokens and `utils/streaming.ReplyStreamer` posts after ~40 chars and edits at most every 1.5 s. 3 s per-user cooldown. Tool-enabled calls run at temperature 0.3 and the system prompt has an explicit intent→tool routing list; after changing the prompt or model, re-measure routing with a scripted benchmark against the real model (realistic chit-chat history matters).
- **Tools** live in `utils/agent_tools.py` (`build_cave_tools()`), each a thin wrapper over a service. `requires_auth` tools are hidden from unauthorized callers *and* re-checked at dispatch against `ToolContext.user` (the real Discord author, from `on_message`); `requires_guild` tools are unavailable in DMs. Tool output is read aloud in public channels, so it must never contain IPs/hostnames/keys.
- Side-effecting tools (`add_game`, `queue_song`, `request_media`) never act at tool time: they call `utils.confirm.post_confirmation`, which posts a `ConfirmView` card only the invoking user can click (120 s expiry, optional re-check on click) and returns a `PENDING` note so the model tells the user to click. `remember_fact` writes to the `user_facts` table (max 20/user), which is injected into the system prompt as delimited notes; `/memory` shows them and `/clearhistory` wipes them.
- `queue_song` goes through `MusicCommands.resolve_track`/`enqueue_track` (single tracks, YouTube hosts only since yt-dlp runs inside the LAN; won't hijack a session in another voice channel). `play_next` takes a `Guild`.
- One-shot prompts (character commands, roast/compliment, beer, image-prompt enhancement) still use `_generate` on `/api/generate`. Character commands fall back to `dialogue.json` `fallback` entries when AI fails.
- Tests mock `AIHandler._chat` (agent path) or `_generate` (one-shot path); see `tests/utils/test_agent.py` for the scripted-model pattern.

**Homelab cog** (`commands/homelab_commands.py`): printer (Moonraker/webcam via `PRINTER_HOST`), service pings, Overseerr/Sonarr/Radarr/Lidarr. Every command must call `await self.check_auth(interaction)` (owner ID or username in `ALLOWED_USERS`).

**Image generation**: `services/image_service.py` (`bot.image_service`) is shared by `/imagine` and Cave's `generate_image` tool. It allows one job at a time (ComfyUI and Ollama share the GPU), a 60 s per-user cooldown, runs the prompt through `AIHandler.enhance_image_prompt` (safety check + enhancement; `fail_closed=True` for chat-initiated images so an Ollama failure refuses instead of passing the raw prompt), then calls `utils/image_gen.py` (ComfyUI at `COMFY_URL`, workflow `utils/image_z_image_turbo.json`, blocking calls in a thread, 180 s websocket timeout). The chat tool runs the job in the background and returns `STARTED`.

**Music** (`commands/music.py`): yt-dlp + ffmpeg (must be on PATH) voice playback via `FFmpegOpusAudio` (ffmpeg applies volume and encodes Opus once at `MUSIC_BITRATE`), `edge-tts` announcements. YouTube access needs three things on the server, all wired through `YDL_OPTIONS`:
- `cookiefile`: `www.youtube.com_cookies.txt` in the repo root (untracked, preserved by deploy; export from a private window and close it without logging out). Note the Python option is `cookiefile`, not `cookies`.
- a JS runtime for YouTube's challenges: `yt-dlp[default]` (pulls in `yt-dlp-ejs`) + Deno from the `deno` PyPI package (`_js_runtimes()`); the server's Node 20 is too old for yt-dlp's solver.
- PO tokens from the bgutil provider container (plugin `bgutil-ytdlp-pot-provider`, URL `YT_POT_PROVIDER_URL`). Recreate it on the server with `docker run -d --name bgutil-provider --restart unless-stopped -p 127.0.0.1:4416:4416 brainicism/bgutil-ytdlp-pot-provider`.
**Song routing** (`MusicCommands.resolve_request` → `MusicLibrary.plan`, used by Cave's `queue_song`): a request that is just an artist in the library queues a shuffled 10-track mix (or a 15-track radio when `radio=true` or the artist has < 5 tracks); `radio=true` on a song seeds a radio with it. Radios take ~1/3 from the artist and the rest from Plex's `/similar` artists in the library. Single tracks follow `resolve_track`: YouTube links play from YouTube; any other request tries the owner's Plex library first (`services/music_library.py`, `bot.music_library`: `/hubs/search`, best track by word-match score ≥ 0.6, or a random track when the request names an artist; needs `PLEX_TOKEN`, `PLEX_URL` defaults to `http://PLEX_IP:32400`; queue URLs are `plex:/library/parts/...` and stream with the token in an ffmpeg header), then SoundCloud (`scsearch5`, originals preferred over remixes/covers/live unless asked), then a YouTube search. `/play` itself still searches YouTube directly.
"Sign in to confirm you're not a bot" for popular videos means YouTube has flagged the home IP; stop testing for a few hours rather than retrying.

## Privacy rules (repo is public)

Never commit real Discord guild/user/channel IDs, LAN IPs/hostnames, friends' names, or homelab URLs. Real values go in `.env` (documented in `.env.example`) or private files under `data/` (gitignored, and preserved on the server because deploy excludes `data/`). CI's privacy-guard step fails on 17–20 digit numbers and `192.168.x.x` in tracked files. Any new env var must be added to `.env.example` and the user told to add it to the server's `.env` before merging to `main`.

## Deployment / CI

- Push to `main` → `.github/workflows/deploy.yml` on a self-hosted runner: rsyncs the repo to `/home/dood345/discordBot/` (excluding `.env`, `data/`, `venv`, cookies file), runs `uv sync --no-dev`, restarts `discordBot.service` via systemd. Anything under `data/` (DB, logs, `server_contexts.json`) is server-local and never deployed; tracked content like dialogue lives in `content/`.
- PRs to `main`/`dev` → `build.yml`: `uv sync`, compileall, `pytest`, privacy guard.
- Workflow is feature branch → `dev` → `main`. Never push straight to `main` (it deploys).
- Overhaul roadmap and per-phase kickoff prompts: `docs/ROADMAP.md`.
