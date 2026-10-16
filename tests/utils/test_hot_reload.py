"""utils/hot_reload.py against a real (not logged-in) commands.Bot and throwaway extension modules."""

import sys
import textwrap
from pathlib import Path
from types import SimpleNamespace

import discord
import pytest
from discord.ext import commands

from utils import hot_reload
from utils.hot_reload import (EXTENSIONS, ServiceSpec, format_results, reload_all, reload_dialogue, reload_one,
                              reload_service, resolve, resolve_loaded_cog)

COG_SOURCE = '''
from discord.ext import commands

EVENTS = __import__("builtins").__dict__.setdefault("_hot_reload_events", [])


class {cls}(commands.Cog):
    VERSION = {version}

    async def cog_load(self):
        EVENTS.append(("load", "{cls}", self.VERSION))

    async def cog_unload(self):
        EVENTS.append(("unload", "{cls}", self.VERSION))


async def setup(bot):
    {body}
    await bot.add_cog({cls}())
'''


@pytest.fixture
def ext_dir(tmp_path, monkeypatch):
    pkg = tmp_path / "hr_exts"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    monkeypatch.syspath_prepend(str(tmp_path))
    events = __import__("builtins").__dict__.setdefault("_hot_reload_events", [])
    events.clear()
    yield pkg
    for name in [m for m in sys.modules if m == "hr_exts" or m.startswith("hr_exts.")]:
        del sys.modules[name]


def write_cog(pkg: Path, module: str, cls: str, version: int, body: str = "pass"):
    (pkg / f"{module}.py").write_text(textwrap.dedent(COG_SOURCE.format(cls=cls, version=version, body=body)))
    sys.modules.pop(f"hr_exts.{module}", None)


@pytest.fixture
async def bot():
    b = commands.Bot(command_prefix="!", intents=discord.Intents.none())
    yield b
    for ext in list(b.extensions):
        await b.unload_extension(ext)


async def test_reload_picks_up_changed_code_and_runs_unload_then_load(bot, ext_dir):
    write_cog(ext_dir, "alpha", "Alpha", 1)
    await bot.load_extension("hr_exts.alpha")
    write_cog(ext_dir, "alpha", "Alpha", 2)

    result = await reload_one(bot, "hr_exts.alpha")

    assert result.ok
    assert bot.get_cog("Alpha").VERSION == 2
    events = __import__("builtins")._hot_reload_events
    assert events == [("load", "Alpha", 1), ("unload", "Alpha", 1), ("load", "Alpha", 2)]


async def test_broken_reload_keeps_the_old_cog_and_reports_the_error(bot, ext_dir):
    write_cog(ext_dir, "alpha", "Alpha", 1)
    await bot.load_extension("hr_exts.alpha")
    write_cog(ext_dir, "alpha", "Alpha", 2, body='raise RuntimeError("bad config")')

    result = await reload_one(bot, "hr_exts.alpha")

    assert not result.ok
    assert "RuntimeError: bad config" in result.message
    assert bot.get_cog("Alpha").VERSION == 1  # rolled back
    assert "hr_exts.alpha" in bot.extensions


async def test_syntax_error_is_reported_too(bot, ext_dir):
    write_cog(ext_dir, "alpha", "Alpha", 1)
    await bot.load_extension("hr_exts.alpha")
    (ext_dir / "alpha.py").write_text("def broken(:\n")

    result = await reload_one(bot, "hr_exts.alpha")

    assert not result.ok and "SyntaxError" in result.message
    assert bot.get_cog("Alpha").VERSION == 1


async def test_reload_all_keeps_going_past_a_failure(bot, ext_dir):
    write_cog(ext_dir, "alpha", "Alpha", 1)
    write_cog(ext_dir, "beta", "Beta", 1)
    await bot.load_extension("hr_exts.alpha")
    await bot.load_extension("hr_exts.beta")
    write_cog(ext_dir, "alpha", "Alpha", 2, body='raise RuntimeError("nope")')
    write_cog(ext_dir, "beta", "Beta", 2)

    results = await reload_all(bot, ["hr_exts.alpha", "hr_exts.beta"])

    assert [r.ok for r in results] == [False, True]
    assert bot.get_cog("Alpha").VERSION == 1 and bot.get_cog("Beta").VERSION == 2
    text = format_results(results)
    assert "❌ `hr_exts.alpha`: RuntimeError: nope" in text and "✅ `hr_exts.beta`" in text


async def test_unloaded_extension_gets_loaded(bot, ext_dir):
    write_cog(ext_dir, "alpha", "Alpha", 1)
    assert (await reload_one(bot, "hr_exts.alpha")).ok
    assert bot.get_cog("Alpha")


def test_voice_cogs_are_refused_while_connected():
    in_voice = SimpleNamespace(voice_clients=[object()])
    idle = SimpleNamespace(voice_clients=[])
    assert hot_reload.blocker(in_voice, "commands.music")
    assert hot_reload.blocker(in_voice, "commands.voice_cave")
    assert hot_reload.blocker(in_voice, "commands.points_commands") is None
    assert hot_reload.blocker(idle, "commands.music") is None


async def test_refused_reload_does_not_touch_the_cog(bot, ext_dir, monkeypatch):
    write_cog(ext_dir, "alpha", "Alpha", 1)
    await bot.load_extension("hr_exts.alpha")
    write_cog(ext_dir, "alpha", "Alpha", 2)
    monkeypatch.setattr(hot_reload, "VOICE_EXTENSIONS", {"hr_exts.alpha"})
    monkeypatch.setattr(type(bot), "voice_clients", property(lambda self: [object()]))

    result = await reload_one(bot, "hr_exts.alpha")

    assert not result.ok and "/stop" in result.message
    assert bot.get_cog("Alpha").VERSION == 1


async def test_music_reload_clears_stale_saved_sessions_first(monkeypatch):
    saved = []
    sessions = SimpleNamespace(save_all=lambda snaps: _record(saved, snaps))
    music = SimpleNamespace(sessions=sessions, _active_sessions=lambda: [])
    reloaded = []

    async def reload_extension(name):
        reloaded.append(name)

    fake_bot = SimpleNamespace(voice_clients=[], extensions={"commands.music": None},
                               get_cog=lambda name: music, reload_extension=reload_extension)

    assert (await reload_one(fake_bot, "commands.music")).ok
    assert saved == [[]] and reloaded == ["commands.music"]


async def _record(store, value):
    store.append(value)


def test_resolve_accepts_short_names():
    assert resolve("music") == "commands.music"
    assert resolve("points") == "commands.points_commands"
    assert resolve("testchamber") == "commands.test_chamber"
    assert resolve("test_chamber") == "commands.test_chamber"
    assert resolve("image") == "commands.image_cog"
    assert resolve("commands.game_night") == "commands.game_night"
    assert resolve("game") == "commands.game_commands"
    assert resolve("nonsense") is None


async def test_resolve_loaded_cog_by_class_name(bot, ext_dir):
    write_cog(ext_dir, "alpha", "Alpha", 1)
    await bot.load_extension("hr_exts.alpha")
    assert resolve_loaded_cog(bot, "alpha") == "hr_exts.alpha"


def test_every_cog_module_is_a_registered_extension():
    modules = {f"commands.{p.stem}" for p in Path("commands").glob("*.py") if p.stem != "__init__"}
    assert set(EXTENSIONS) == modules
    for ext in EXTENSIONS:
        assert "async def setup(bot)" in Path(ext.replace(".", "/") + ".py").read_text(encoding="utf-8")


async def test_service_reload_swaps_instance_and_reloads_dependents(bot, ext_dir):
    (ext_dir / "svc.py").write_text("class Svc:\n    VERSION = 1\n")
    write_cog(ext_dir, "alpha", "Alpha", 1)
    import hr_exts.svc  # noqa: F401
    bot.svc = sys.modules["hr_exts.svc"].Svc()
    await bot.load_extension("hr_exts.alpha")
    (ext_dir / "svc.py").write_text("class Svc:\n    VERSION = 2\n")
    specs = {"svc": ServiceSpec("svc", ["hr_exts.svc"], lambda b: sys.modules["hr_exts.svc"].Svc(),
                                ["hr_exts.alpha"])}

    results = await reload_service(bot, "svc", specs)

    assert [r.ok for r in results] == [True, True]
    assert bot.svc.VERSION == 2


async def test_broken_service_keeps_the_old_instance(bot, ext_dir):
    (ext_dir / "svc.py").write_text("class Svc:\n    VERSION = 1\n")
    import hr_exts.svc  # noqa: F401
    old = bot.svc = sys.modules["hr_exts.svc"].Svc()
    (ext_dir / "svc.py").write_text("raise ValueError('broken service')\n")
    specs = {"svc": ServiceSpec("svc", ["hr_exts.svc"], lambda b: sys.modules["hr_exts.svc"].Svc())}

    results = await reload_service(bot, "svc", specs)

    assert not results[0].ok and "broken service" in results[0].message
    assert bot.svc is old


def test_dialogue_reload_refuses_broken_json(tmp_path):
    from utils.dialogue_manager import DialogueManager
    path = tmp_path / "dialogue.json"
    path.write_text('{"cave": {"hi": ["hello"]}}', encoding="utf-8")
    dialogue = DialogueManager(str(path))
    fake_bot = SimpleNamespace(dialogue=dialogue)

    path.write_text('{"cave": {"hi": ["hey there"]}}', encoding="utf-8")
    assert reload_dialogue(fake_bot).ok
    assert dialogue.get("cave", "hi") == "hey there"

    path.write_text('{"cave": ', encoding="utf-8")
    assert not reload_dialogue(fake_bot).ok
    assert dialogue.get("cave", "hi") == "hey there"  # not wiped
