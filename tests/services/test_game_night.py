import random
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

import discord

from commands.game_night import GameNight
from utils.layouts import card_text
from services.game_night_service import ATTEND_CHECKS, ATTEND_POINTS, GameNightService, parse_start, pick_games
from services.points_service import PointsService

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
    points = PointsService(temp_db, achievements=[], tz=TZ)
    await points.set_enabled(99, True)
    cog = GameNight(SimpleNamespace(db=temp_db, ai_handler=ai, points_service=points))
    cog.service.now = lambda: NOW
    vc = MagicMock(spec=discord.VoiceChannel)
    vc.id, vc.mention = 5, "#lounge"
    vc.members = [SimpleNamespace(bot=False), SimpleNamespace(bot=False), SimpleNamespace(bot=True)]
    guild = SimpleNamespace(create_scheduled_event=AsyncMock(return_value=SimpleNamespace(url="https://discord.com/events/1/2")))
    sent = AsyncMock()
    i = SimpleNamespace(guild_id=99, channel_id=77, guild=guild, user=SimpleNamespace(voice=SimpleNamespace(channel=vc)),
                        response=SimpleNamespace(defer=AsyncMock(), send_message=AsyncMock()), followup=SimpleNamespace(send=sent))

    await GameNight.gamenight.callback(cog, i, start="9pm")
    text = card_text(sent.call_args_list[0].kwargs["view"])
    assert sent.call_args_list[0].kwargs["allowed_mentions"].users is False
    assert "2 players" in text and "GAME NIGHT, LAB BOYS!" in text and "Rust" not in text
    assert "Event created" in text and f"earn {ATTEND_POINTS} Science Points" in text
    [night] = await cog.service.open_nights(now=NOW.replace(hour=21).timestamp())
    assert (night.guild_id, night.voice_channel_id, night.text_channel_id) == (99, 5, 77)
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


# --- Attendance points ---

START = NOW.replace(hour=21)


async def test_attendance_window_and_counting(temp_db):
    service = GameNightService(temp_db, tz=TZ)
    night_id = await service.record_night(99, 5, 77, START)
    assert await service.open_nights(now=START.timestamp() - 20 * 60) == []      # too early
    assert len(await service.open_nights(now=START.timestamp() - 10 * 60)) == 1   # 15 min early counts
    for _ in range(ATTEND_CHECKS - 1):
        assert await service.record_presence(night_id, [1, 2]) == []
    assert await service.record_presence(night_id, [1]) == [1]                    # qualifies exactly once
    assert await service.record_presence(night_id, [1]) == []
    assert await service.close_night(night_id) == [1]                             # 2 left early
    assert await service.open_nights(now=START.timestamp()) == []


def attendance_cog(temp_db, points, humans):
    member = lambda uid: SimpleNamespace(id=uid, bot=False, display_name=f"Subject {uid}")
    voice = SimpleNamespace(members=[member(u) for u in humans] + [SimpleNamespace(id=999, bot=True)])
    text = SimpleNamespace(send=AsyncMock())
    guild = SimpleNamespace(id=99, get_channel={5: voice, 77: text}.get, get_member=lambda uid: member(uid))
    cog = GameNight(SimpleNamespace(db=temp_db, points_service=points, get_guild=lambda gid: guild))
    return cog, text


async def test_attendees_get_points_once_and_a_summary(temp_db):
    points = PointsService(temp_db, achievements=[], tz=TZ)
    await points.set_enabled(99, True)
    cog, text = attendance_cog(temp_db, points, humans=[1, 2])
    await cog.service.record_night(99, 5, 77, START)
    for i in range(ATTEND_CHECKS + 3):
        await cog.check_attendance(now=START.timestamp() + i * 120)
    assert (await points.profile(99, 1))[0] == ATTEND_POINTS                      # paid once, not every check
    assert (await points.profile(99, 2))[0] == ATTEND_POINTS
    text.send.assert_not_awaited()

    await cog.check_attendance(now=START.timestamp() + 5 * 3600)                 # window over
    msg = text.send.call_args.args[0]
    assert "Subject 1" in msg and "Subject 2" in msg
    assert text.send.call_args.kwargs["allowed_mentions"].users is False
    await cog.check_attendance(now=START.timestamp() + 6 * 3600)
    assert text.send.await_count == 1                                            # closed nights stay closed


async def test_no_attendance_points_while_science_points_is_off(temp_db):
    points = PointsService(temp_db, achievements=[], tz=TZ)
    cog, text = attendance_cog(temp_db, points, humans=[1])
    await cog.service.record_night(99, 5, 77, START)
    for i in range(ATTEND_CHECKS + 1):
        await cog.check_attendance(now=START.timestamp() + i * 120)
    await cog.check_attendance(now=START.timestamp() + 5 * 3600)
    assert (await points.profile(99, 1))[0] == 0
    text.send.assert_not_awaited()
