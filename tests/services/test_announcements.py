from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

import pytest

from commands.announcements import Announcements
from services.announcement_service import AnnouncementService

TZ = ZoneInfo("America/Chicago")


class Clock:
    def __init__(self, at):
        self.at = at

    def __call__(self):
        return self.at


@pytest.fixture
def homelab():
    h = MagicMock()
    h._overseerr.return_value = None
    h.printer_status = AsyncMock(return_value=None)
    return h


async def test_birthdays_opt_in_once_per_year(temp_db, homelab):
    clock = Clock(datetime(2026, 3, 14, 8, 0, tzinfo=TZ))
    s = AnnouncementService(temp_db, homelab, tz=TZ, clock=clock)
    await s.set_birthday(1, 7, 3, 14)
    await s.set_birthday(2, 7, 3, 14)          # other server, not opted in
    with pytest.raises(ValueError):
        await s.set_birthday(1, 8, 2, 30)
    await s.set_channel(1, 100)
    assert await s.due_birthdays() == []       # before 9 am
    clock.at = clock.at.replace(hour=10)
    assert await s.due_birthdays() == [(1, 7)]
    assert await s.due_birthdays() == []       # once
    clock.at = clock.at.replace(year=2027)
    assert await s.due_birthdays() == [(1, 7)]  # next year again
    await s.remove_birthday(1, 7)
    clock.at = clock.at.replace(year=2028)
    assert await s.due_birthdays() == []


async def test_leap_day_birthday_on_feb_28(temp_db, homelab):
    s = AnnouncementService(temp_db, homelab, tz=TZ, clock=Clock(datetime(2027, 2, 28, 12, 0, tzinfo=TZ)))
    await s.set_channel(1, 100)
    await s.set_birthday(1, 7, 2, 29)
    assert await s.due_birthdays() == [(1, 7)]


async def test_new_media_first_run_is_silent(temp_db, homelab, mocker):
    s = AnnouncementService(temp_db, homelab, tz=TZ)
    homelab._overseerr.return_value = ("http://overseerr", {})
    homelab.media_details = AsyncMock(side_effect=lambda tmdb, kind: {"title": f"T{tmdb}", "year": "2026"})
    batches = [[{"media": {"mediaType": "movie", "tmdbId": 1}}, {"media": {"mediaType": "tv", "tmdbId": 2}}],
               [{"media": {"mediaType": "movie", "tmdbId": 3}}, {"media": {"mediaType": "movie", "tmdbId": 1}}]]

    class Resp:
        status = 200
        def __init__(self, data): self.data = data
        async def json(self): return {"results": self.data}
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False

    class Session:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        def get(self, *a, **k): return Resp(batches.pop(0))

    mocker.patch("services.announcement_service.aiohttp.ClientSession", Session)
    assert await s.new_media() == []            # backlog recorded, not announced
    assert await s.new_media() == ["T3 (2026)"]


async def test_printer_transition_only(temp_db, homelab):
    s = AnnouncementService(temp_db, homelab, tz=TZ)
    states = ["printing", "printing", "complete", "complete", "standby"]
    homelab.printer_status = AsyncMock(side_effect=[{"state": st, "filename": "cube.gcode", "duration": "1h 2m"} for st in states])
    results = [await s.printer_finished() for _ in states]
    assert [r is not None for r in results] == [False, False, True, False, False]


async def test_cog_posts_only_to_opted_in_and_pings_only_birthday_person(temp_db, homelab):
    channel = MagicMock()
    channel.send = AsyncMock()
    member = SimpleNamespace(mention="<@7>", display_name="GLaDOS")
    guild = SimpleNamespace(get_member=lambda uid: member)
    ai = SimpleNamespace(complete=AsyncMock(return_value="Happy birthday!"), _get_persona_system_prompt=lambda: "Cave")
    bot = SimpleNamespace(db=temp_db, homelab_service=homelab, get_channel=lambda cid: channel,
                          get_guild=lambda gid: guild, ai_handler=ai)
    cog = Announcements(bot)
    cog.service.clock = lambda: datetime(2026, 3, 14, 10, 0, tzinfo=TZ)
    await cog.service.set_birthday(1, 7, 3, 14)
    await cog.announce_birthdays()
    channel.send.assert_not_awaited()            # server not opted in
    await cog.service.set_channel(1, 100)
    await cog.service.set_birthday(1, 7, 3, 14)
    await cog.announce_birthdays()
    assert channel.send.call_args.args[0] == "🎂 <@7> Happy birthday!"
    assert channel.send.call_args.kwargs["allowed_mentions"].users == [member]
