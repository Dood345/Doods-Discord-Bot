from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord

from commands.music import GuildPlayer, MusicCommands
from services.music_sessions import (QUEUE_TTL, REWIND, MusicSession, MusicSessionStore, elapsed, is_stale,
                                     place_request, snapshot)

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
    cog.reboot_messages = {9}                                      # this server opted in to reboot notes
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


REQUEST = ("https://youtu.be/req", "Vampire Party Mix", "Book Club Radio")
OLD = ("plex:/library/parts/3/4/lynchesque.flac", "Lynchesque", "Dusty Kid")


def leftover_player(last_active=1000.0):
    """Voice dropped mid-song: the player still holds the interrupted song and its queue."""
    p = GuildPlayer(5)
    p.current_track, p.queue, p.last_active = TRACK, [OLD], last_active
    return p


def test_idle_request_plays_first_then_leftovers():
    p = leftover_player()
    assert place_request(p, [REQUEST], idle=True, now=2000.0) == 2
    # the interrupted song comes back right after the request, then the rest of the old queue
    assert p.queue == [REQUEST, TRACK, OLD] and p.current_track is None and p.last_active == 2000.0


def test_request_while_playing_joins_the_end():
    p = leftover_player()
    assert place_request(p, [REQUEST], idle=False, now=2000.0) == 0
    assert p.queue == [OLD, REQUEST] and p.current_track == TRACK


def test_day_old_leftovers_are_dropped():
    p = leftover_player(last_active=1000.0)
    assert not is_stale(p, now=1000.0 + QUEUE_TTL)
    assert is_stale(p, now=1001.0 + QUEUE_TTL)
    assert place_request(p, [REQUEST], idle=True, now=1001.0 + QUEUE_TTL) == 0
    assert p.queue == [REQUEST]
    assert not is_stale(GuildPlayer(5))        # never used: nothing to expire


def rejoin_cog(p):
    """The bot isn't in voice; the member is. Connecting returns an idle voice client."""
    vc = MagicMock()
    vc.is_playing.return_value = vc.is_paused.return_value = False
    guild = SimpleNamespace(id=9, voice_client=None)
    target = SimpleNamespace(id=5, connect=AsyncMock(return_value=vc))
    member = SimpleNamespace(guild=guild, voice=SimpleNamespace(channel=target))
    cog = MusicCommands(SimpleNamespace(db=None))
    cog.players[5] = p

    async def fake_play_next(_guild):
        p.current_track = p.queue.pop(0)
    cog.play_next = AsyncMock(side_effect=fake_play_next)
    return cog, member


async def test_rejoin_plays_the_request_not_the_old_queue():
    # The 16:03 report: Cave said "now playing <request>" but the old Dusty Kid queue played instead
    p = leftover_player(last_active=None)
    cog, member = rejoin_cog(p)
    reply = await cog.enqueue_tracks(member, None, [REQUEST])
    assert p.current_track == REQUEST
    assert "Vampire Party Mix" in reply and "2 tracks left from earlier" in reply


async def test_reply_says_so_when_the_request_failed():
    p = leftover_player(last_active=None)
    cog, member = rejoin_cog(p)

    async def request_fails(_guild):
        p.queue.pop(0)                         # play_next skips a broken track...
        p.current_track = p.queue.pop(0)       # ...and plays the next one
    cog.play_next = AsyncMock(side_effect=request_fails)
    reply = await cog.enqueue_tracks(member, None, [REQUEST])
    assert "Couldn't play your request" in reply and "Kryptonite" in reply


async def test_restore_is_quiet_unless_the_server_opted_in():
    channel, vc = voice_channel()
    text = MagicMock(spec=discord.TextChannel)
    text.send = AsyncMock()
    cog = cog_with(channel, text)
    cog.sessions.load_recent.return_value = [MusicSession(5, 9, 77, TRACK, 90.0, [NEXT])]
    assert await cog.restore_sessions() == 1
    text.send.assert_not_awaited()
