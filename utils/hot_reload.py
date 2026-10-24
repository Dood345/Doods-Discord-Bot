"""Hot-reloading cogs and a few stateless services without restarting the bot (owner-only `!reload`).

Every cog module in `commands/` is a discord.py extension (it has `async def setup(bot)`). `DoodsBot.setup_hook`
loads them in the order of `EXTENSIONS`, and `!reload` uses `bot.reload_extension`, which rolls back to the old
module if the new one fails to import or set up.

Limits worth knowing:
- Reloading a cog re-imports only that cog's module, not the `services/`/`utils/` modules it imports.
  Changed service code needs `!reload service <name>` (stateless services only, see `SERVICES`) or a restart.
- Music and Voice Cave own live voice connections (`MusicCommands.cog_unload` disconnects every voice client and
  the players' "song ended" callbacks point at the old cog), so they are refused while the bot is in voice.
- Changed slash-command names/options still need `!sync .`; a reload only updates the bot's in-memory tree.
- Not reloadable: ai_handler (everything holds it; background memory jobs), image_service (GPU lock and running
  jobs), points_service / test_chamber (per-server caches, and each holds the other), homelab_service (the
  printer webcam cache and the presence loop), db and config (read at startup).
"""

import importlib
import importlib.util
import json
import logging
import sys
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

from discord.ext import commands

from utils.error_reporting import scrub

logger = logging.getLogger(__name__)

# Load order on startup (same order the cogs were add_cog'd in before they became extensions)
EXTENSIONS = [
    "commands.character_commands",
    "commands.social_commands",
    "commands.game_commands",
    "commands.misc_commands",
    "commands.gift_commands",
    "commands.homelab_commands",
    "commands.image_cog",
    "commands.music",
    "commands.context_menus",
    "commands.points_commands",
    "commands.test_chamber",
    "commands.game_night",
    "commands.announcements",
    "commands.voice_cave",
    "commands.maintenance",
    "commands.personas",
]

# Cogs that hold voice connections: reloading them would cut off whatever is playing
VOICE_EXTENSIONS = {"commands.music", "commands.voice_cave"}


@dataclass
class ServiceSpec:
    attr: str                       # attribute on the bot
    modules: List[str]              # reloaded in this order (dependencies first)
    build: Callable                 # (bot) -> new instance, using the freshly reloaded modules
    dependents: List[str] = field(default_factory=list)  # extensions that cache the instance in __init__


SERVICES = {
    "gift": ServiceSpec("gift_service", ["services.gift_service"],
                        lambda bot: sys.modules["services.gift_service"].GiftService(bot.db),
                        ["commands.gift_commands"]),
    "game": ServiceSpec("game_service", ["services.store_lookup", "services.game_service"],
                        lambda bot: sys.modules["services.game_service"].GameService(bot.db, bot.dialogue),
                        ["commands.game_commands"]),
    "music_library": ServiceSpec("music_library", ["services.music_library"],
                                 lambda bot: sys.modules["services.music_library"].MusicLibrary(),
                                 ["commands.music"]),  # music imports match_score/constants from it
}


@dataclass
class ReloadResult:
    name: str
    ok: bool
    message: str = ""


def resolve(name: str, extensions: List[str] = EXTENSIONS) -> Optional[str]:
    """'music', 'commands.music', 'music.py' or a cog's class name ('MusicCommands') -> 'commands.music'."""
    key = name.strip().lower().removesuffix(".py")
    for ext in extensions:
        short = ext.rsplit(".", 1)[-1]
        if key in (ext, short, short.replace("_", ""), short.removesuffix("_commands"), short.removesuffix("_cog")):
            return ext
    return None


def resolve_loaded_cog(bot, name: str, extensions: List[str] = EXTENSIONS) -> Optional[str]:
    """A cog class name ('MusicCommands') -> the extension it came from (only reloadable ones)."""
    for cog_name, cog in getattr(bot, "cogs", {}).items():
        if cog_name.lower() == name.strip().lower() and type(cog).__module__ in extensions:
            return type(cog).__module__
    return None


def blocker(bot, ext: str) -> Optional[str]:
    """Why `ext` can't be reloaded right now, or None."""
    if ext in VOICE_EXTENSIONS and list(getattr(bot, "voice_clients", [])):
        return "I'm in a voice channel; reloading would cut it off. `/stop` first, then reload."
    return None


async def _before_reload(bot, ext: str) -> None:
    if ext == "commands.music":
        # The fresh cog resumes saved sessions on load. The save loop runs every 10 s, so a session that just
        # ended (/stop) could still be on disk and get "resumed"; write the current (empty) state first.
        cog = bot.get_cog("MusicCommands")
        sessions = getattr(cog, "sessions", None)
        if sessions:
            await sessions.save_all(cog._active_sessions())


def describe_error(error: BaseException) -> str:
    original = getattr(error, "original", None) or error.__cause__ or error
    # Posted in Discord: no paths/URLs/IPs/keys (the full traceback is only in the log)
    return scrub(f"{type(original).__name__}: {original}")[:300]


async def reload_one(bot, ext: str) -> ReloadResult:
    reason = blocker(bot, ext)
    if reason:
        return ReloadResult(ext, False, reason)
    try:
        if ext in bot.extensions:
            await _before_reload(bot, ext)
            await bot.reload_extension(ext)
        else:
            await bot.load_extension(ext)
    except Exception as e:
        # reload_extension restored the old module, so the previous version keeps running
        logger.exception(f"Reloading {ext} failed")
        return ReloadResult(ext, False, describe_error(e))
    logger.info(f"Reloaded {ext}")
    return ReloadResult(ext, True)


async def reload_all(bot, extensions: List[str] = EXTENSIONS) -> List[ReloadResult]:
    """Reload every extension, carrying on past failures and refusals."""
    return [await reload_one(bot, ext) for ext in extensions]


async def reload_service(bot, name: str, services: dict = SERVICES) -> List[ReloadResult]:
    """Re-import a stateless service's modules, swap a fresh instance onto the bot, then reload the cogs that
    cached the old one. If the import or construction fails, the old instance stays."""
    spec = services[name]
    try:
        # Compile everything first: a syntax error in the second module mustn't leave the first half-swapped
        for module in spec.modules:
            found = importlib.util.find_spec(module)
            source = found.loader.get_source(module) if found and found.loader else None
            if source is None:
                raise ModuleNotFoundError(module)
            compile(source, found.origin or module, "exec")
    except Exception as e:
        logger.exception(f"Reloading service {name} failed")
        return [ReloadResult(f"service {name}", False, describe_error(e))]
    try:
        for module in spec.modules:
            if module in sys.modules:
                importlib.reload(sys.modules[module])
            else:
                importlib.import_module(module)
        instance = spec.build(bot)
    except Exception as e:
        # The module body ran partway: the old instance stays, but on half-updated module globals
        logger.exception(f"Reloading service {name} failed")
        return [ReloadResult(f"service {name}", False, describe_error(e) + " (fix it and reload again, or restart)")]
    setattr(bot, spec.attr, instance)
    logger.info(f"Reloaded service {name}")
    return [ReloadResult(f"service {name}", True)] + [await reload_one(bot, ext) for ext in spec.dependents]


def reload_dialogue(bot) -> ReloadResult:
    """Re-read content/dialogue.json in place (DialogueManager wipes everything on a parse error, so check first)."""
    dialogue = bot.dialogue
    try:
        with open(dialogue.config_path, encoding="utf-8") as f:
            json.load(f)
    except Exception as e:
        logger.exception("dialogue.json didn't parse; keeping the loaded dialogue")
        return ReloadResult("dialogue", False, describe_error(e))
    dialogue.load_dialogue()
    return ReloadResult("dialogue", True)


def format_results(results: List[ReloadResult]) -> str:
    lines = [f"✅ `{r.name}`" if r.ok else f"❌ `{r.name}`: {r.message}" for r in results]
    if any(not r.ok for r in results):
        lines.append("-# Full tracebacks are in the bot log. Failed reloads keep the previous version running.")
    if any(r.ok for r in results):
        lines.append("-# Changed slash-command names or options still need `!sync .`.")
    text = "\n".join(lines)
    return text if len(text) <= 1900 else text[:1890] + "\n…"


def status_lines(bot, extensions: List[str] = EXTENSIONS) -> Tuple[str, ...]:
    loaded = getattr(bot, "extensions", {})
    exts = [f"{'🟢' if e in loaded else '⚪'} `{e.rsplit('.', 1)[1]}`"
            + (" (voice: refused while connected)" if e in VOICE_EXTENSIONS else "") for e in extensions]
    return (
        "**Cogs** (`!reload <name>` / `!reload all`)", *exts,
        f"**Services** (`!reload service <name>`): {', '.join(f'`{s}`' for s in SERVICES)}",
        "**Content**: `!reload dialogue`",
    )


class Reload(commands.Cog):
    """Owner-only `!reload`. Added with add_cog (not an extension) so it can never reload itself away."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="reload")
    @commands.is_owner()
    async def reload(self, ctx, target: str = "list", name: str = ""):
        target = target.lower()
        if target == "list":
            await ctx.send("\n".join(status_lines(self.bot)))
            return
        if target == "all":
            results = await reload_all(self.bot)
        elif target == "dialogue":
            results = [reload_dialogue(self.bot)]
        elif target == "service":
            if name.lower() not in SERVICES:
                await ctx.send(f"Reloadable services: {', '.join(SERVICES)}. The rest hold live state; restart for those.")
                return
            results = await reload_service(self.bot, name.lower())
        else:
            ext = resolve(target) or resolve_loaded_cog(self.bot, target)
            if not ext:
                await ctx.send(f"No cog called `{target}`. `!reload list` shows them.")
                return
            results = [await reload_one(self.bot, ext)]
        await ctx.send(format_results(results))
