---
name: new-slash-command
description: Add a new slash command or cog to the Discord bot the way this repo does it (service layer, dialogue.json strings, setup_hook registration, temp_db test, !sync reminder). Use whenever adding or renaming a / command.
---

# Adding a slash command

Follow these steps in order. Read CLAUDE.md first if you haven't.

## 1. Decide where it lives
- Fits an existing cog in `commands/`? Add it there.
- New feature area? Create `commands/<area>_commands.py` with a `commands.Cog` subclass. Then **import it and `await self.add_cog(...)` in `DoodsBot.setup_hook()` in `main.py`**. Forgetting this is the #1 way a command silently doesn't exist.

## 2. Put logic in a service, not the cog
Anything touching the DB or with real rules goes in `services/<area>_service.py` (constructor takes `db` and, if it returns user-facing text, `dialogue`). Instantiate it in `DoodsBot.__init__` as `self.<area>_service` and read it in the cog via `bot.<area>_service`. New tables go in `DatabaseHandler.setup_tables()`. Remember `CREATE TABLE IF NOT EXISTS` won't add columns to an existing table on the server.

Scope data by `interaction.guild_id` unless it's deliberately per-user-global.

## 3. Write the command
```python
@app_commands.command(name="thing", description="Short, Discord-visible description")
@app_commands.describe(target="What this option means")
async def thing(self, interaction: discord.Interaction, target: str):
    await interaction.response.defer()          # if anything below may take >3s
    result = await self.bot.thing_service.do(interaction.user.id, interaction.guild_id, target)
    await interaction.followup.send(result)
```
- Use `defer()` + `followup` for anything slow (AI, HTTP, ComfyUI, yt-dlp). Otherwise `response.send_message`.
- Blocking libraries (`requests`, `urllib`, `ping3`, `yt_dlp`) go through `await self.bot.loop.run_in_executor(None, fn, *args)`.
- Homelab or privileged? First line after the signature: `if not await self.check_auth(interaction): return` (see `commands/homelab_commands.py`).
- Private/noisy responses: `ephemeral=True`.
- Option suggestions: `@thing.autocomplete("target")` returning `app_commands.Choice`s (see `game_commands.py`).

## 4. Strings in Cave's voice
User-facing flavor text goes in `content/dialogue.json` under the speaking character (usually `cave_johnson`) as a list of variants with `{placeholders}`. Fetch it with `self.bot.dialogue.get("cave_johnson", "thing_success", fallback="...", target=target)`. Keep the JSON valid (the test suite loads it).

## 5. Config
New settings: `os.getenv` in `config.py`, a line in `.env.example`, and the feature disables itself cleanly when unset. Never hardcode IDs/IPs/names (repo is public; CI privacy guard fails on them).

## 6. Test
Add `tests/services/test_<area>_service.py` using the `temp_db` fixture (async tests need no decorator). Mock any HTTP/AI (`mocker.patch.object(handler, "_generate", AsyncMock(...))`).

## 7. Finish
- Run the `ship-check` skill.
- Tell the user: run `!sync .` in their test server (instant) or `!sync` (global, ~1 h) after deploy, and list any env vars to add to the server's `.env`.
- If the AI agent (docs/ROADMAP.md Phase 1) exists, consider exposing the feature as an AI tool too.
