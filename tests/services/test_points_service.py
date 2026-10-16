from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

from commands.points_commands import PointsCommands
from services.points_service import PointsService, load_achievements
from utils.agent import ToolContext
from utils.agent_tools import build_cave_tools

TZ = ZoneInfo("America/Chicago")
DAY = datetime(2026, 10, 16, 9, 0, tzinfo=TZ)


def service(db):
    return PointsService(db, tz=TZ)


async def enabled(db, guilds=(1, 2, 9)):
    s = service(db)
    for g in guilds:
        await s.set_enabled(g, True)
    return s


def test_achievement_file_loads():
    ach = load_achievements()
    assert {"first_test", "chamber_19", "lab_regular"} <= {a.id for a in ach}
    assert all(a.type in ("points", "reason_count") and a.threshold > 0 for a in ach)


async def test_activity_once_per_local_day_per_server(temp_db):
    s = await enabled(temp_db)
    earned = await s.record_activity(1, 7, DAY)
    assert [a.id for a in earned] == ["first_test"]
    assert await s.record_activity(1, 7, DAY + timedelta(hours=5)) == []           # same day
    s._seen.clear()
    assert await s.record_activity(1, 7, DAY + timedelta(hours=5)) == []           # DB also dedupes
    await s.record_activity(1, 7, DAY + timedelta(days=1))                          # next day
    await s.record_activity(2, 7, DAY)                                              # other server
    assert await temp_db.get_points(1, 7) == 2 and await temp_db.get_points(2, 7) == 1

    # 23:30 and 00:30 local are different days even though both are the same UTC date
    late = datetime(2026, 10, 20, 23, 30, tzinfo=TZ)
    assert s.local_date(late) != s.local_date(late + timedelta(hours=1))


async def test_reason_count_achievements_and_idempotent_awards(temp_db):
    s = await enabled(temp_db)
    paid, earned = await s.award(1, 7, 10, "trivia_first", "trivia:1:7")
    assert paid and {a.id for a in earned} == {"first_test", "quickest_draw"}
    assert await s.award(1, 7, 10, "trivia_first", "trivia:1:7") == (False, [])
    for day in range(6):
        await s.record_activity(1, 7, DAY + timedelta(days=day))
    _, earned = await s.award(1, 7, 1, "activity", "activity:x")  # 7th day
    assert [a.id for a in earned] == ["lab_regular"]


async def test_profile_rank_and_leaderboard(temp_db):
    s = await enabled(temp_db)
    for uid, pts in ((1, 5), (2, 50), (3, 20)):
        await s.award(9, uid, pts, "test", f"t:{uid}")
    await s.award(8, 4, 999, "test", "other-server")
    points, rank, achievements = await s.profile(9, 3)
    assert (points, rank) == (20, 2) and achievements[0].id == "first_test"
    assert await s.leaderboard(9) == [(2, 50), (3, 20), (1, 5)]
    assert (await s.profile(9, 42))[:2] == (0, None)


def interaction(guild, user):
    return SimpleNamespace(guild_id=9, guild=guild, user=user,
                           response=SimpleNamespace(send_message=AsyncMock(), defer=AsyncMock()),
                           followup=SimpleNamespace(send=AsyncMock()))


async def test_points_commands_never_ping(temp_db):
    s = await enabled(temp_db)
    await s.award(9, 1, 50, "test", "a")
    await s.award(9, 2, 10, "test", "b")
    members = {1: SimpleNamespace(display_name="GLaDOS"), 2: SimpleNamespace(display_name="Wheatley")}
    guild = SimpleNamespace(get_member=members.get)
    bot = SimpleNamespace(points_service=s, dialogue=SimpleNamespace(get=lambda *a, **k: "empty"))
    cog = PointsCommands(bot)

    i = interaction(guild, SimpleNamespace(id=2, display_name="Wheatley"))
    await PointsCommands.leaderboard_command.callback(cog, i)
    i.response.defer.assert_awaited_once()  # acked before any member lookups
    text = i.followup.send.call_args.args[0]
    assert text.index("GLaDOS") < text.index("Wheatley") and "<@" not in text
    assert i.followup.send.call_args.kwargs["allowed_mentions"].users is False

    i = interaction(guild, SimpleNamespace(id=2, display_name="Wheatley"))
    await PointsCommands.points_command.callback(cog, i)
    assert "10 Science Points (rank #2" in i.response.send_message.call_args.args[0]


async def test_science_points_tool(temp_db):
    s = await enabled(temp_db)
    await s.award(9, 7, 12, "test", "a")
    guild = SimpleNamespace(id=9, get_member=lambda uid: SimpleNamespace(display_name="Rando"))
    ctx = ToolContext(bot=SimpleNamespace(points_service=s), user=SimpleNamespace(id=7, display_name="Rando"), guild=guild)
    result = await build_cave_tools().dispatch("science_points", {}, ctx)
    assert "12 Science Points (rank #1)" in result and "1. Rando (12)" in result


async def test_points_are_off_until_a_manager_turns_them_on(temp_db):
    s = service(temp_db)
    assert await s.record_activity(1, 7, DAY) == []
    assert await temp_db.get_points(1, 7) == 0

    bot = SimpleNamespace(points_service=s, dialogue=SimpleNamespace(get=lambda *a, **k: "empty"))
    cog = PointsCommands(bot)
    i = interaction(SimpleNamespace(get_member=lambda uid: None), SimpleNamespace(id=7, display_name="R"))
    await PointsCommands.leaderboard_command.callback(cog, i)
    assert "/sciencepoints on" in i.response.send_message.call_args.args[0]
    i.response.defer.assert_not_awaited()

    manager = SimpleNamespace(id=1, guild_permissions=SimpleNamespace(manage_guild=True))
    i = interaction(None, manager)
    await PointsCommands.turn_on.callback(cog, i)
    fresh = service(temp_db)                    # setting survives a restart (not just the cache)
    assert await fresh.is_enabled(9)
    assert await fresh.record_activity(9, 7, DAY)  # first_test achievement

    nobody = SimpleNamespace(id=2, guild_permissions=SimpleNamespace(manage_guild=False))
    i = interaction(None, nobody)
    await PointsCommands.turn_off.callback(cog, i)
    assert i.response.send_message.call_args.kwargs["ephemeral"] is True
    assert await s.is_enabled(9)
