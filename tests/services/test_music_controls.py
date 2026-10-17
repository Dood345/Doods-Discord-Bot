"""Card buttons (pause / skip / restart) and leaving voice when everyone's gone."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import commands.music as music
from commands.music import GuildPlayer, MusicButton, MusicCommands
from utils.layouts import card_text

TRACK = ("plex:/library/parts/1/2/still-alive.flac", "Still Alive", "Jonathan Coulton")
NEXT = ("https://youtu.be/x", "Want You Gone", "Jonathan Coulton")


def human(uid=1):
    return SimpleNamespace(id=uid, bot=False)


def setup_cog(playing=True, members=None):
    channel = SimpleNamespace(id=5, name="Lab", mention="#lab", members=members if members is not None else [human()])
    vc = MagicMock(channel=channel)
    state = {"playing": playing, "paused": False}
    vc.is_playing.side_effect = lambda: state["playing"]
    vc.is_paused.side_effect = lambda: state["paused"]
    vc.pause.side_effect = lambda: state.update(playing=False, paused=True)
    vc.resume.side_effect = lambda: state.update(playing=True, paused=False)
    vc.disconnect = AsyncMock()
    guild = SimpleNamespace(id=9, voice_client=vc, me=SimpleNamespace(id=999), get_channel=lambda cid: channel)
    cog = MusicCommands(SimpleNamespace(db=None))
    p = GuildPlayer(5)
    p.current_track, p.queue, p.start_time = TRACK, [NEXT], 1000.0
    p.notification_channel = SimpleNamespace(send=AsyncMock())
    cog.players[5] = p
    return cog, guild, vc, p


def test_pause_resume_and_restart():
    cog, guild, vc, p = setup_cog()
    assert cog.toggle_pause(guild) == "paused" and p.pause_start_time
    assert cog.toggle_pause(guild) == "resumed" and p.pause_start_time is None
    assert cog.restart_current(guild) == TRACK
    assert p.seek_position == 0.0 and p.current_track == TRACK   # play_next replays it from the top
    vc.stop.assert_called_once()


def test_card_has_controls_only_while_playing():
    cog, guild, vc, p = setup_cog()
    card = cog.build_queue_card(guild, 5)
    ids = [c.custom_id for c in card.walk_children() if getattr(c, "custom_id", None)]
    assert ids == ["mc:restart", "mc:pause", "mc:skip"]
    assert "Still Alive" in card_text(card)
    cog.pause(guild)
    labels = [c.item.label for c in cog.build_queue_card(guild, 5).walk_children() if isinstance(c, MusicButton)]
    assert "Resume" in labels
    p.current_track = None                                         # queued but nothing on: no buttons
    vc.is_paused.side_effect = lambda: False
    card = cog.build_queue_card(guild, 5)
    assert not [c for c in card.walk_children() if getattr(c, "custom_id", None)]


async def test_buttons_only_work_for_people_in_the_channel():
    cog, guild, vc, p = setup_cog()
    response = SimpleNamespace(send_message=AsyncMock(), defer=AsyncMock())
    outsider = SimpleNamespace(voice=None)
    i = SimpleNamespace(client=SimpleNamespace(get_cog=lambda n: cog), guild=guild, user=outsider, response=response,
                        edit_original_response=AsyncMock())
    await MusicButton("pause").callback(i)
    assert "Join #lab" in response.send_message.call_args.args[0]
    vc.pause.assert_not_called()

    i.user = SimpleNamespace(voice=SimpleNamespace(channel=vc.channel))
    await MusicButton("pause").callback(i)
    vc.pause.assert_called_once()
    i.edit_original_response.assert_awaited_once()                 # the card refreshes in place


async def test_pauses_when_alone_resumes_when_someone_returns(monkeypatch):
    cog, guild, vc, p = setup_cog(members=[])
    await cog.check_alone(guild)
    assert vc.is_paused() and p.auto_paused and 9 in cog._alone_timers
    vc.channel.members = [human()]
    await cog.check_alone(guild)
    assert vc.is_playing() and not p.auto_paused and 9 not in cog._alone_timers


async def test_manual_pause_stays_paused_when_someone_returns():
    cog, guild, vc, p = setup_cog()
    cog.pause(guild)                                               # someone paused it on purpose
    vc.channel.members = []
    await cog.check_alone(guild)
    vc.channel.members = [human()]
    await cog.check_alone(guild)
    assert vc.is_paused()


async def test_leaves_after_the_timeout_but_keeps_the_queue(monkeypatch):
    monkeypatch.setattr(music, "ALONE_TIMEOUT", 0)
    cog, guild, vc, p = setup_cog(members=[])
    await cog.check_alone(guild)
    await asyncio.sleep(0.01)
    vc.disconnect.assert_awaited_once()
    assert p.queue == [NEXT] and 5 in cog.players                  # a request within a day picks it back up
    assert "left" in p.notification_channel.send.call_args.args[0]
