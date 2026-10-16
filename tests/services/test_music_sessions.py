from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord

from commands.music import GuildPlayer, MusicCommands
from services.music_sessions import REWIND, MusicSession, MusicSessionStore, elapsed, snapshot

TRACK = ("plex:/library/parts/1/2/kryptonite.flac", "Kryptonite", "3 Doors Down")
NEXT = ("https://youtu.be/x", "Still Alive", "Jonathan Coulton")


def player(start=1000.0, paused_at=None):
    p = GuildPlayer(5)
    p.current_track, p.queue, p.start_time, p.pause_start_time = TRACK, [NEXT], start, paused_at
    p.notification_channel = SimpleNamespace(id=77)
    return p


def test_elapsed_and_snapshot():
    assert elapsed(player(), now=1090.0) == 90.0
    assert elapsed(player(paused_at=1030.0), now=1090.0) == 30.0   # frozen while paused
    snap = snapshot(player(), guild_id=9, now=1090.0)
    assert (snap.channel_id, snap.guild_id, snap.text_channel_id, snap.position) == (5, 9, 77, 90.0)
    assert snap.current == TRACK and snap.queue == [NEXT] and not snap.paused
    idle = player()
    idle.current_track = None
    assert snapshot(idle, 9) is None


async def test_store_round_trip_and_expiry(temp_db):
    store = MusicSessionStore(temp_db)
    await store.save_all([MusicSession(5, 9, 77, TRACK, 90.0, [NEXT], False, saved_at=1000.0)])
    [s] = await store.load_recent(now=1100.0)
    assert (s.current, s.queue, s.position) == (TRACK, [NEXT], 90.0)
    assert await store.load_recent(now=1000.0 + 31 * 60) == []    # too old to resume
    await store.save_all([])                                       # player ended -> session gone
    assert await store.load_recent(now=1100.0) == []


def voice_channel(humans=1):
    ch = MagicMock(spec=discord.VoiceChannel)
    ch.id, ch.mention = 5, "#lab"
    ch.members = [SimpleNamespace(bot=False)] * humans + [SimpleNamespace(bot=True)]
    vc = MagicMock()
    vc.is_playing.return_value = True
    ch.guild = SimpleNamespace(id=9, voice_client=None)

    async def connect():
        ch.guild.voice_client = vc
        return vc
    ch.connect = AsyncMock(side_effect=connect)
    return ch, vc


def cog_with(channel, text):
    lookup = {5: channel, 77: text}
    bot = SimpleNamespace(db=None, get_channel=lookup.get, voice_clients=[], is_closed=lambda: False)
    cog = MusicCommands(bot)
    cog.sessions = SimpleNamespace(load_recent=AsyncMock())
    cog.play_next = AsyncMock()
    return cog


async def test_restore_rejoins_and_seeks():
    channel, vc = voice_channel()
    text = MagicMock(spec=discord.TextChannel)
    text.send = AsyncMock()
    cog = cog_with(channel, text)
    cog.sessions.load_recent.return_value = [MusicSession(5, 9, 77, TRACK, 90.0, [NEXT], paused=True)]

    assert await cog.restore_sessions() == 1
    channel.connect.assert_awaited_once()
    p = cog.players[5]
    assert p.current_track == TRACK and p.queue == [NEXT] and p.seek_position == 90.0 - REWIND
    cog.play_next.assert_awaited_once_with(channel.guild)
    vc.pause.assert_called_once()                                    # it was paused before the restart
    assert "1:30" in text.send.call_args.args[0] and "Kryptonite" in text.send.call_args.args[0]


async def test_restore_skips_empty_channels():
    channel, _ = voice_channel(humans=0)
    cog = cog_with(channel, None)
    cog.sessions.load_recent.return_value = [MusicSession(5, 9, None, TRACK, 10.0)]
    assert await cog.restore_sessions() == 0
    channel.connect.assert_not_awaited()
