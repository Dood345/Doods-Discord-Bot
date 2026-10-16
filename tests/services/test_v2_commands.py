"""Commands that reply with Components v2 cards: they send `view=` only (no content/embeds) and never ping."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord

from commands.game_commands import GameCommands
from commands.homelab_commands import HomeLabCommands
from config import BotConfig
from utils.layouts import card_text

STATUS = {"state": "printing", "filename": "@everyone benchy.gcode", "progress": 42, "duration": "1h 2m",
          "remaining": "1h", "layer": (10, 100), "temps": {"extruder": (210, 210)},
          "filament_detected": True, "message": ""}


def interaction(user_id=42):
    return SimpleNamespace(user=SimpleNamespace(id=user_id, name="owner"), guild=SimpleNamespace(id=99),
                           response=SimpleNamespace(defer=AsyncMock(), send_message=AsyncMock()),
                           followup=SimpleNamespace(send=AsyncMock()))


def homelab_cog(printer):
    cog = HomeLabCommands(SimpleNamespace(homelab_service=SimpleNamespace(printer=printer)))
    cog.update_printer_status.cancel()
    return cog


async def test_printer_sends_a_card_with_the_snapshot_in_a_gallery(monkeypatch):
    monkeypatch.setattr(BotConfig, "OWNER_ID", 42)
    printer = SimpleNamespace(configured=True, status=AsyncMock(return_value=STATUS),
                              snapshot=AsyncMock(return_value=b"jpg"), clip=AsyncMock())
    i = interaction()
    await HomeLabCommands.printer_status.callback(homelab_cog(printer), i)

    kwargs = i.followup.send.call_args.kwargs
    assert not i.followup.send.call_args.args and "embed" not in kwargs and "content" not in kwargs
    assert [f.filename for f in kwargs["files"]] == ["snapshot.jpg"]
    assert kwargs["allowed_mentions"].everyone is False
    view = kwargs["view"]
    assert "42%" in card_text(view)
    gallery = [c for c in view.walk_children() if isinstance(c, discord.ui.MediaGallery)]
    assert gallery[0].items[0].media.url == "attachment://snapshot.jpg"


async def test_printer_clip_failure_is_noted_in_the_card(monkeypatch):
    monkeypatch.setattr(BotConfig, "OWNER_ID", 42)
    printer = SimpleNamespace(configured=True, status=AsyncMock(return_value=STATUS),
                              snapshot=AsyncMock(), clip=AsyncMock(return_value=None))
    i = interaction()
    await HomeLabCommands.printer_status.callback(homelab_cog(printer), i, video=True)

    kwargs = i.followup.send.call_args.kwargs
    assert kwargs["files"] == []
    assert "Couldn't record a clip" in card_text(kwargs["view"])
    assert not [c for c in kwargs["view"].walk_children() if isinstance(c, discord.ui.MediaGallery)]


async def test_game_list_sends_a_grouped_card():
    games = [{"title": "Portal 2", "status": "playing", "avg_rating": 9.0, "min_players": 2, "max_players": 2,
              "ideal_players": None, "release_state": None},
             {"title": "Lethal Company", "status": "avoid", "avg_rating": None, "min_players": 1, "max_players": 4,
              "ideal_players": None, "release_state": "early access"}]
    service = MagicMock(get_library=AsyncMock(return_value=games))
    cog = GameCommands(SimpleNamespace(game_service=service, dialogue=None))
    i = interaction()

    await GameCommands.list_games.callback(cog, i)

    kwargs = i.followup.send.call_args.kwargs
    text = card_text(kwargs["view"])
    assert text.index("Portal 2") < text.index("Avoid") < text.index("Lethal Company")
    assert kwargs["allowed_mentions"].everyone is False
