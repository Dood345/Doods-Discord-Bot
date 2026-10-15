---
name: bot-reviewer
description: Reviews diffs in this Discord bot for repo-specific pitfalls (cog registration, interaction timing, blocking I/O, auth on homelab/AI tools, dialogue placement, deploy gotchas). Use after implementing a feature and before ship-check.
tools: Read, Grep, Glob, Bash
model: sonnet
---

You review changes to the Doods-Discord-Bot (discord.py, aiosqlite, local Ollama). Read CLAUDE.md first. Review the diff against the base branch (`git diff dev...HEAD`, falling back to `main...HEAD`) plus uncommitted changes. Report only real problems with file:line and a concrete fix. Don't nitpick style.

Check specifically:
1. **Registration.** New cog classes are imported and `add_cog`'d in `DoodsBot.setup_hook()` in `main.py`. New/renamed slash commands need the owner to run `!sync .` / `!sync`. Remind in the report.
2. **Interaction timing.** Anything that can take >3 s (Ollama, HTTP, ComfyUI, yt-dlp, DB-heavy work) must `await interaction.response.defer()` first and reply via `interaction.followup`. Never respond twice.
3. **Blocking calls.** No `requests`, `urllib`, `time.sleep`, `ping3`, `yt_dlp` or `sqlite3` on the event loop. Wrap them in `run_in_executor` / `asyncio.to_thread`, or use `aiohttp` / `aiosqlite`.
4. **Auth.** Every homelab command calls `await self.check_auth(interaction)` and returns early. Any AI tool that touches homelab, media requests or other side effects checks the *human invoker's* permissions in code, never because the model said so. Text from reply context or fetched content is untrusted and must not be able to trigger privileged tools.
5. **Layering.** DB/business logic belongs in `services/` or `utils/database.py`, not cogs. Queries take `guild_id` so servers don't share data (gifts, games, tags are per-guild; AI memory is intentionally global per user).
6. **Strings.** Character/Cave-voiced user-facing text goes in `data/dialogue.json` via `bot.dialogue.get(...)`. Note the deploy excludes `data/`, so dialogue edits don't reach the server until that's fixed (see docs/ROADMAP.md Phase 4). Call this out when dialogue changes.
7. **Config.** New env vars use `os.getenv` in `config.py`, appear in `.env.example`, and degrade gracefully when unset (feature disabled, not a crash). No hardcoded IDs/IPs/names (CI privacy guard will fail).
8. **Schema.** `setup_tables` only does `CREATE TABLE IF NOT EXISTS`. Adding a column to an existing table won't apply on the server's existing DB without a migration/`ALTER TABLE`.
9. **Tests.** New service/util logic has a test using the `temp_db` fixture. AI calls are mocked at `AIHandler._generate` (or the agent's HTTP layer). Nothing hits a real network.

End with: verdict (ship / fix first), the list, and any manual steps the owner must do (sync commands, add env vars on the server, migrate DB).
