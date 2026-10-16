import random
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

import discord

from commands.game_night import GameNight
from utils.layouts import card_text
from services.game_night_service import parse_start, pick_games

TZ = ZoneInfo("America/Chicago")
NOW = datetime(2026, 10, 16, 18, 0, tzinfo=TZ)
LIB = [
    {"title": "Valheim", "min_players": 1, "max_players": 10, "status": "played", "avg_rating": 9},
    {"title": "Portal 2", "min_players": 1, "max_players": 2, "status": "played", "avg_rating": 10},
    {"title": "Lethal Company", "min_players": 1, "max_players": 4, "status": "unknown", "avg_rating": None},
    {"title": "Rust", "min_players": 1, "max_players": 50, "status": "avoid", "avg_rating": 2},
    {"title": "Deep Rock Galactic", "min_players": 1, "max_players": 4, "status": "playing", "avg_rating": 8},
]


def test_parse_start():
    assert parse_start("9pm", NOW) == NOW.replace(hour=21)
    assert parse_start("20:30", NOW) == NOW.replace(hour=20, minute=30)
    assert parse_start("8:15 am", NOW).day == 17                    # already passed -> tomorrow
    assert parse_start(None, NOW) == NOW.replace(hour=21)           # default 9pm
    assert parse_start("6pm", NOW).day == 17                        # right now counts as passed
    for bad in ("soon", "25:00", "13pm", "9:75"):
        assert parse_start(bad, NOW) is None


def test_pick_games_fits_players_and_skips_avoid():
    for seed in range(20):
        picks = pick_games(LIB, 4, rng=random.Random(seed))
        titles = {g["title"] for g in picks}
        assert len(picks) == 3 and "Rust" not in titles and "Portal 2" not in titles
    assert {g["title"] for g in pick_games(LIB, 8)} == {"Valheim"}
    assert pick_games(LIB, 80) == []
    assert len(pick_games(LIB, None)) == 3


async def test_gamenight_posts_picks_poll_and_event(temp_db):
    for g in LIB:
        await temp_db.add_game(g["title"], 1, 99, min_players=g["min_players"], max_players=g["max_players"], status=g["status"])
    ai = SimpleNamespace(complete=AsyncMock(return_value="GAME NIGHT, LAB BOYS!"), _get_persona_system_prompt=lambda: "Cave")
    cog = GameNight(SimpleNamespace(db=temp_db, ai_handler=ai))
    cog.service.now = lambda: NOW
    vc = MagicMock(spec=discord.VoiceChannel)
    vc.members = [SimpleNamespace(bot=False), SimpleNamespace(bot=False), SimpleNamespace(bot=True)]
    guild = SimpleNamespace(create_scheduled_event=AsyncMock(return_value=SimpleNamespace(url="https://discord.com/events/1/2")))
    sent = AsyncMock()
    i = SimpleNamespace(guild_id=99, guild=guild, user=SimpleNamespace(voice=SimpleNamespace(channel=vc)),
                        response=SimpleNamespace(defer=AsyncMock(), send_message=AsyncMock()), followup=SimpleNamespace(send=sent))

    await GameNight.gamenight.callback(cog, i, start="9pm")
    text = card_text(sent.call_args_list[0].kwargs["view"])
    assert sent.call_args_list[0].kwargs["allowed_mentions"].users is False
    assert "2 players" in text and "GAME NIGHT, LAB BOYS!" in text and "Rust" not in text
    assert "Event created" in text
    kwargs = guild.create_scheduled_event.call_args.kwargs
    assert kwargs["channel"] is vc and kwargs["start_time"] == NOW.replace(hour=21)
    poll = sent.call_args_list[1].kwargs["poll"]
    assert len(poll.answers) == 3


async def test_gamenight_bad_time_and_forbidden_event(temp_db):
    cog = GameNight(SimpleNamespace(db=temp_db, ai_handler=None))
    i = SimpleNamespace(response=SimpleNamespace(send_message=AsyncMock()))
    await GameNight.gamenight.callback(cog, i, start="whenever")
    assert i.response.send_message.call_args.kwargs["ephemeral"] is True

    guild = SimpleNamespace(create_scheduled_event=AsyncMock(side_effect=discord.Forbidden(MagicMock(status=403), "no")))
    note = await cog._schedule(SimpleNamespace(guild=guild, user="x"), NOW, MagicMock(), ["A"])
    assert "Manage Events" in note
