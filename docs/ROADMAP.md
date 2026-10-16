# Cave Johnson Overhaul Roadmap

Where the bot is today: a solid cog-based discord.py bot with a service layer, async SQLite, a local Ollama LLM, and a lot of personality. The "agent" in Cave's chat is keyword matching: `get_chat_response` looks for words like "recommend … game" or "what's playing" and pastes DB/music status into one big prompt string sent to `/api/generate`. Cave can't *do* anything from chat, and conversation memory is a flat text dump of the last 20 messages.

The goal: make Cave a real agent that can act inside the facility (games, music, images, homelab) safely, make the server more fun to hang out in, and modernize the plumbing so it's easy to keep extending.

Each phase is one or more PRs, branch → `dev` → `main`. Each phase ends with the `ship-check` skill green. Kickoff prompts at the bottom can be pasted into a fresh Claude Code session. Reference the issue number in the PR (`Closes #104`) so GitHub closes it on merge.

### Open issues → where they land

| Issue | Ask | Phase |
|---|---|---|
| #104 | Cave queues songs from natural language | 1b `queue_song` tool ✅ |
| #105 | Cave can query local media servers | 1b `search_media` / `request_media` ✅ |
| #106 | Cave can ping local devices | 1b `service_status` tool ✅ |
| #84 | Small permanent memory per user | 1d `user_facts` ✅ |
| #90 | Radio toggle: start radio from one song | 2 (music) ✅ |
| #100 | Game list should work with the per-channel/guild system | 2 (games) ✅ |
| #103 | Adding a game by link auto-fills info (Steam/Epic) | 2 (games) + agent `add_game` tool |
| #48 | Gift claim shows item IDs publicly | 2 — privacy fix, use ephemeral replies / select menus ✅ |
| #69 | Send a link to add to the print queue instead of a file | won't do: print settings vary too much per model |

---

## Phase 0 — Hygiene (done in `chore/privacy-scrub-and-roadmap`)

- [x] Guild IDs, friend/server names moved out of `config.py` into gitignored `data/server_contexts.json`
- [x] `.coverage` untracked; `.env.example` added; README de-Geminied
- [x] AI handler no longer crashes without `OLLAMA_URL`; AI tests mock Ollama instead of the dead Gemini client (27/27 green)
- [x] CI: uv + Python 3.14 + pytest + privacy guard (the old job installed from a `requirements.txt` that didn't exist)
- [x] Privacy Policy describes actual data handling (cross-server memory, reply context, logs, `/clearhistory`)
- [x] Git history rewritten and force-pushed
- [x] Deleted merged stale branches (local and remote)
- [x] ToS §5 now defers to the GPL-3.0 `LICENSE`: the code is open source; the ToS only covers the hosted instance
- [x] `OLLAMA_MODEL` env var (the hard-coded `gemma4:12b` didn't exist on the server, so AI chat was 404ing in prod); `think: false`
- [x] `dialogue.json` moved to `content/` so it actually deploys (prod had been running without it)

## Phase 1 — Cave becomes a real agent (the big one)

**1a. Switch to chat + tool calling.** ✅ (`utils/agent.py`; verified: the installed Gemma 4 12B supports tools, ~3–5 s per answer with `think: false`)
- First, on the server: `ollama show <model>` and confirm `tools` is listed under Capabilities. If the current model lacks it, pick one that has it (Qwen 3, Llama 3.x, Mistral Small and newer Gemma releases generally do) and benchmark latency on the homelab GPU.
- Move from `/api/generate` (one prompt string) to `/api/chat` with a real `messages` array: system persona → server context → history turns → user message. History becomes proper turns, not "User: … Model: …" text.
- Build `utils/agent/` with a small tool registry: each tool = name, JSON schema, async handler, `requires_auth: bool`, `side_effect: bool`. Loop: call model → run requested tools → feed results back → repeat (max ~4 iterations, per-tool timeout) → final text.
- Replace the keyword "RAG" blocks with tools.

**1b. Starter tools** (each wraps an existing service/cog — no new business logic in the agent). Read-only ones ✅: `recommend_games`, `list_game_tags`, `now_playing`, `service_status`, `printer_status`, `download_queue`. Side-effect tools ✅ behind confirm cards: `add_game`, `queue_song` (#104), `search_media` + `request_media` (#105). `generate_image` ✅ (shared ImageService: one job at a time, fail-closed safety filter, background post). `rate_game` and `skip_song` ✅ (act directly: a rating only touches the caller's own score, and skipping needs the caller in the music's voice channel, same as `/skip`).
| Tool | Wraps | Gate |
|---|---|---|
| `recommend_games`, `search_games`, `add_game`, `rate_game` | `GameService` | — |
| `now_playing`, `queue_song`, `skip_song` | `MusicCommands` | caller must be in the voice channel |
| `generate_image` | `image_gen` via executor | cooldown |
| `wishlist_lookup` | `GiftService` | — |
| `printer_status`, `service_status`, `media_queue` | homelab cog | `check_auth` |
| `request_media` | Overseerr | `check_auth` + confirmation button |
| `remember_fact` / `recall_facts` | new `user_facts` table | only about the caller |

**1c. Safety — non-negotiable once tools exist.** ✅ for read-only tools (auth filter + dispatch re-check, quoted reply context, clearance line, cooldown, tool-call logging). Known limit: the 12B model sometimes invents live data instead of calling a tool; a larger/instruction-tuned model or lower temperature would help.
- Tools run with the *invoking user's* permissions. Homelab tools re-check `check_auth` against the human who sent the message, never trust the model's claim.
- Reply context (someone else's message) and any fetched content are injected as clearly delimited untrusted data. A user must not be able to get Cave to run a privileged tool by replying to a message that says "ignore instructions and request…".
- Side-effecting tools (requesting media, adding games, queueing music for everyone) post a Discord button confirmation instead of acting silently.
- Per-user AI cooldown; log every tool call (name, args, user) at INFO.

**1d. Better memory.** ✅ `user_facts` + `remember_fact` + `/memory` + `/clearhistory` wipes facts (#84). Rolling summaries ✅ (`ai_summaries`). Embedding recall ✅ (`ai_embeddings`, nomic-embed-text on Ollama's CPU).
- Rolling summary: when history exceeds N turns, summarize older turns into a per-user summary row instead of dropping them.
- `user_facts` table ("likes Valheim", "hates horror games") written via `remember_fact`, shown in the system prompt. `/clearhistory` wipes facts too; add `/memory` to show what Cave knows about you (privacy policy already promises deletion).
- Optional later: Ollama embeddings for semantic recall over old conversations.

**1e. Feel.** ✅ streamed replies (post early, throttled edits). Stream the response by editing the reply message as tokens arrive; show "Cave is consulting the lab boys…" while tools run.

Deliverable also includes the `add-ai-tool` skill (written once the registry's real shape exists).

## Phase 2 — More fun

- **Library-first music.** ✅ Cave's song requests try Plex → SoundCloud → YouTube search; YouTube links still go to YouTube. Artist requests queue a mix; "radio" requests mix in similar artists from the library (#90). `/play` uses the same routing (plus a `radio` option); links and `playlist-only` still go to YouTube.

- **One character command, data-driven personas.** Replace nine near-identical `/hank`, `/dale`, … commands with `/ask character:<autocomplete> prompt:` backed by a persona file (prompt, emoji, fallback lines, reactions). Adding a character = editing data. Keep old commands as aliases for a release.
- **Character showdowns.** `/debate hank cartman topic:` — two personas argue for 3 rounds, server votes with a native Discord poll.
- **Context-menu commands.** Right-click a message → "Ask Cave about this", "Roast this", "Fact-check (Dale edition)".
- **Science Points economy.** XP for participating, trivia wins, game-night attendance; `/leaderboard`; Aperture-themed achievements ("Survived Test Chamber 19").
- **Daily Test Chamber.** Scheduled daily trivia or riddle (`tasks.loop`), first correct answer gets points; Cave announces winners in character.
- **Game Night Director.** Cave proposes 3 games from the library filtered by who's online/in voice and player counts, runs a poll, creates a Discord Scheduled Event, pings attendees.
- **Facility announcements.** Opt-in proactive posts: printer job finished (poll Moonraker → ping you with webcam snapshot), new media available (Overseerr webhook), birthday shout-outs (opt-in only).
- **Voice Cave.** Cave joins voice and speaks announcements/answers with edge-tts (plumbing already exists in music).
- **Image fun.** `/portrait @user` (test-subject ID badge), `/poster` (Aperture propaganda poster) using ComfyUI.

## Phase 3 — Modernize the plumbing

- Pin `discord.py` to a release instead of `@master`; adopt Components v2 (`LayoutView`) for richer embeds/menus.
- Auto-load cogs from `commands/` as extensions + owner `!reload <cog>` for hot reload without restarting the service.
- Typed settings (e.g. `pydantic-settings`) replacing the class-attribute `BotConfig`; validates `.env` on startup and logs what's disabled.
- DB: `schema_version` table + tiny migration runner (today it's `CREATE TABLE IF NOT EXISTS` only, so column changes need manual SQL).
- `ruff` (lint + format) in CI and a pre-commit hook.
- Error reporting: unhandled app-command errors DM the owner with a traceback summary; global `tree.on_error` handler (today only prefix-command errors are handled).
- Tests for cogs using lightweight interaction fakes.

## Phase 4 — Ops

- Nightly SQLite backup (`sqlite3 .backup`) with rotation on the server.
- Deploy: health check after `systemctl restart`; auto-rollback to previous release dir if the bot isn't online in 60 s.
- Parametrize the deploy path (`/home/<user>/discordBot`) via a repo variable.

---

## Kickoff prompts

Paste one into a fresh Claude Code session in this repo. Each assumes CLAUDE.md is loaded.

**Phase 0 finish**
> Finish Phase 0 of docs/ROADMAP.md: add an OLLAMA_MODEL env var (default to the current model, update .env.example), delete the local and remote branches that are fully merged into main (list them and ask me before deleting remotes), and propose a resolution for the ToS §5 vs LICENSE conflict. Run the ship-check skill before opening the PR to dev.

**Phase 1a–1c (agent core)**
> Implement Phase 1a–1c of docs/ROADMAP.md. Start by asking me for the output of `ollama show <model>` on the server to confirm tool support. Build utils/agent/ (tool registry + chat loop on Ollama /api/chat), port the existing game-recommendation and now-playing keyword blocks to tools, then add the starter tools in the table. Enforce the safety rules in 1c with tests: a non-authorized user and a malicious reply-context message must both fail to trigger privileged tools. Mock all Ollama calls in tests. Write the add-ai-tool skill at the end, then run ship-check.

**Phase 1d–1e (memory + streaming)**
> Implement Phase 1d–1e of docs/ROADMAP.md: rolling summaries, a user_facts table with remember/recall tools, /memory and an extended /clearhistory, and streamed replies. Update PrivacyPolicy.md for the new stored data. Run ship-check.

**Phase 2 (pick one item per session)**
> Implement "<item name>" from Phase 2 of docs/ROADMAP.md. Use the new-slash-command skill for any new command, put user-facing strings in content/dialogue.json in Cave's voice, and if the agent from Phase 1 exists, expose the feature as an AI tool too. Run ship-check.

**Phase 3 / 4**
> Implement "<item name>" from Phase 3 (or 4) of docs/ROADMAP.md without changing user-visible behavior. Keep the diff focused; run ship-check.
