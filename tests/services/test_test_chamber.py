from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

import pytest

from commands.test_chamber import ANSWER_REPLIES, ChamberButton, TestChamber, question_text
from services.points_service import PointsService
from services.test_chamber_service import Question, TestChamberService, fallback_question

TZ = ZoneInfo("America/Chicago")


class Clock:
    def __init__(self, at):
        self.at = at

    def __call__(self):
        return self.at


@pytest.fixture
async def chamber(temp_db):
    clock = Clock(datetime(2026, 10, 16, 12, 0, tzinfo=TZ))
    fetcher = AsyncMock(return_value=Question("Science", "2+2?", ["3", "4", "5", "22"], 1))
    service = TestChamberService(temp_db, PointsService(temp_db, tz=TZ), tz=TZ, fetcher=fetcher, clock=clock)
    return service, clock, fetcher


def test_fallback_bank_is_valid():
    for _ in range(20):
        q = fallback_question()
        assert len(q.choices) == 4 and 0 <= q.correct_index < 4 and q.question


async def test_nothing_posts_without_opt_in_or_before_6pm(chamber):
    service, clock, fetcher = chamber
    assert await service.create_due() == []                  # nobody opted in
    await service.set_channel(1, 100)
    assert await service.create_due() == []                  # noon: too early
    clock.at = clock.at.replace(hour=18, minute=1)
    due = await service.create_due()
    assert [(q.guild_id, q.channel_id) for q in due] == [(1, 100)]
    assert due[0].closes_at == datetime(2026, 10, 17, 14, 0, tzinfo=TZ)


async def test_one_question_per_day_shared_and_restart_safe(chamber):
    service, clock, fetcher = chamber
    await service.set_channel(1, 100)
    await service.set_channel(2, 200)
    clock.at = clock.at.replace(hour=19)
    due = await service.create_due()
    assert len(due) == 2 and fetcher.await_count == 1        # one fetch shared by both servers
    await service.mark_posted(due[0].id, 555)
    # A "restart": a fresh service sees only the unposted one, and creates no duplicates
    fresh = TestChamberService(service.db, service.points, tz=TZ, fetcher=fetcher, clock=clock)
    again = await fresh.create_due()
    assert [q.id for q in again] == [due[1].id]


async def test_forced_post_and_opt_out(chamber):
    service, clock, _ = chamber
    await service.set_channel(1, 100)
    assert len(await service.create_due(force_guild=1)) == 1  # noon, but forced
    await service.set_channel(1, None)
    assert await service.channels() == {}


async def test_answers_scoring_and_close(chamber):
    service, clock, _ = chamber
    await service.set_channel(1, 100)
    q = (await service.create_due(force_guild=1))[0]
    await service.mark_posted(q.id, 555)

    assert await service.answer(q.id, 7, 0) == "wrong"
    assert await service.answer(q.id, 8, 1) == "correct"
    assert await service.answer(q.id, 9, 1) == "correct"
    assert await service.answer(q.id, 8, 0) == "duplicate"
    assert await service.answer(999, 8, 0) == "missing"

    assert await service.close_due() == []                   # not yet
    clock.at = q.closes_at + timedelta(minutes=1)
    assert await service.answer(q.id, 10, 1) == "closed"
    [result] = await service.close_due()
    assert (result.first, result.correct, result.total_answers) == (8, [8, 9], 3)
    assert await service.db.get_points(1, 8) == 10 and await service.db.get_points(1, 9) == 3
    assert await service.db.get_points(1, 7) == 0
    assert "quickest_draw" in [a.id for a in result.achievements[8]]
    assert await service.close_due() == []                   # closes once, pays once


async def test_button_and_announcement(chamber):
    service, clock, _ = chamber
    await service.set_channel(1, 100)
    q = (await service.create_due(force_guild=1))[0]
    await service.mark_posted(q.id, 555)

    item = await ChamberButton.from_custom_id(None, None, {"qid": str(q.id), "choice": "1"})
    i = SimpleNamespace(client=SimpleNamespace(test_chamber=service), user=SimpleNamespace(id=8),
                        response=SimpleNamespace(send_message=AsyncMock()))
    await item.callback(i)
    assert i.response.send_message.call_args.args[0] == ANSWER_REPLIES["correct"]
    assert "2+2?" in question_text(q) and "**B)** 4" in question_text(q)

    channel = MagicMock()
    channel.send = AsyncMock()
    channel.fetch_message = AsyncMock(return_value=SimpleNamespace(edit=AsyncMock()))
    guild = SimpleNamespace(get_member=lambda uid: SimpleNamespace(display_name="GLaDOS"))
    ai = SimpleNamespace(complete=AsyncMock(return_value=None), _get_persona_system_prompt=lambda: "Cave")
    bot = SimpleNamespace(test_chamber=service, get_channel=lambda cid: channel, get_guild=lambda gid: guild, ai_handler=ai)
    cog = TestChamber(bot)
    clock.at = q.closes_at + timedelta(minutes=1)
    await cog.close_due()
    text = channel.send.call_args.args[0]
    assert "Answer: **B) 4**" in text and "GLaDOS" in text and "Quickest Draw" in text
    assert channel.send.call_args.kwargs["allowed_mentions"].users is False
