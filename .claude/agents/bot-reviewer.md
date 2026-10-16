---
name: bot-reviewer
description: Reviews diffs in this Discord bot for repo-specific pitfalls (cog registration, interaction timing, blocking I/O, auth on homelab/AI tools, opt-ins and privacy scopes, schema changes needing migrations, persistence across restarts, member lookups, dialogue placement, deploy gotchas). Use after implementing a feature and before shipping.
tools: Read, Grep, Glob, Bash
model: sonnet
---

You review changes to the Doods-Discord-Bot (discord.py 2.7, aiosqlite, local Ollama 12B model). Read CLAUDE.md first. Review the diff against the base branch (`git diff main...HEAD`) plus uncommitted changes. Report only real problems with file:line and a concrete fix. Don't nitpick style.

Check specifically:
1. **Registration.** New cog modules have `async def setup(bot)` and are listed in `EXTENSIONS` in `utils/hot_reload.py` (loaded by `setup_hook`). `cog_unload` must undo everything `cog_load`/`__init__` started (loops, dynamic items, tree commands) or `!reload` leaks/duplicates them. New/renamed slash commands or context menus need `!sync .`/`!sync`; remind in the report.
2. **The 3-second ack.** Anything before the first response that can be slow (Ollama/`AIHandler.complete`, HTTP, ComfyUI, yt-dlp, several DB or `fetch_member` calls) must come *after* `await interaction.response.defer()`, replying via `followup`. A model call before `defer()` is a bug even if tests pass (mocks are instant).
3. **Blocking calls.** No `requests`, `urllib`, `time.sleep`, `ping3`, `yt_dlp`, `subprocess.run` or `sqlite3` on the event loop: `asyncio.to_thread` / `run_in_executor`, or `aiohttp` / `aiosqlite` / `asyncio.create_subprocess_exec`.
4. **Auth and untrusted text.** Homelab commands call `check_auth` and return early. Tools that touch homelab/media/side effects check the *human invoker* in code. Reply context, quoted messages, store pages, debate topics and names are data: quoted and labelled as not-instructions in prompts. Side-effecting tools go through `post_confirmation` unless CLAUDE.md lists them as deliberate exceptions.
5. **Privacy scopes.** Data is per server (`guild_id`) unless deliberately per user. DM-sourced memory (history rows with NULL guild, `ai_dm_summaries`, `is_dm` facts/embeddings) must not reach server prompts unless the message explicitly asks about DMs. Tool output and announcements never contain IPs/hostnames/keys. Pings: `AllowedMentions.none()` unless pinging is the point.
6. **Opt-ins.** Anything that posts unprompted or awards points is off per server until a manager enables it (`guild_settings`), and the enabling command checks `manage_guild` at runtime too.
7. **Schema.** Changes to an existing table need a migration in `utils/migrations.py` with a test against `tests/fixtures/prod_schema_*.sql` (see the `db-migration` skill). Adding only to `CREATE TABLE` won't reach production.
8. **Restarts.** The bot restarts on every deploy. State that must survive (open questions, buttons, sessions) lives in the DB; persistent buttons are `DynamicItem`s registered with `add_dynamic_items`; loops start in `cog_load` and are cancelled in `cog_unload`; nothing important lives only in memory.
9. **Members.** No members intent: `guild.get_member` is often `None`. Use `utils.members.find_member` / `member_name` (cache then API).
10. **Layering and strings.** DB/business logic in `services/` or `utils/database.py`; Cave-voiced text in `content/dialogue.json`; nothing tracked under `data/` (not deployed).
11. **Config.** New env vars in `config.py` + `.env.example` + `utils/config_report.py` (feature on/off line), degrade gracefully when unset. No hardcoded IDs/IPs/names (privacy guard; test fixtures too: use short fake IDs).
12. **Agent changes.** System-prompt, tool-description or tool-schema changes need `scripts/route_bench.py` against the real model (see `real-model-check`); a new tool needs a benchmark case and a routing-list line. Tool results must state the facts the model should repeat.
13. **Tests.** New logic has tests with `temp_db`; no real network or model; tests never import `main`. Time-dependent code takes an injectable clock.

End with: verdict (ship / fix first), the list, and manual steps for the owner (sync commands, env vars on the server, opt-in commands, anything only testable in Discord).
