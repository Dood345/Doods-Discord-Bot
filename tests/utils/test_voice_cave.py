import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from commands.voice_cave import VoiceCave, speakable


def test_speakable_strips_markdown_links_and_emoji():
    text = "**LISTEN UP** <@123> 🎉 check https://example.com/x :) <:cave:999> `science`!"
    assert speakable(text) == "LISTEN UP check a link :) science!"
    assert len(speakable("word " * 400)) <= 604


def vc(channel_id=5, playing=False):
    v = MagicMock()
    v.channel = SimpleNamespace(id=channel_id, name="Lab")
    v.is_playing.return_value = playing
    v.is_paused.return_value = False
    v.disconnect = AsyncMock()
    v.play = MagicMock(side_effect=lambda source, after: after(None))
    return v


def member(guild, channel_id=5):
    channel = SimpleNamespace(id=channel_id, connect=AsyncMock(return_value=vc(channel_id)))
    return SimpleNamespace(guild=guild, voice=SimpleNamespace(channel=channel) if channel_id else None)


def cog():
    c = VoiceCave(SimpleNamespace(get_cog=lambda name: None))

    async def fake_tts(text):
        path = os.path.join(os.environ.get("TMP", "."), "test_cave_tts.mp3")
        open(path, "w").close()
        return path
    c.synthesize = fake_tts
    return c


async def test_refuses_without_voice_or_over_music(monkeypatch):
    monkeypatch.setattr("commands.voice_cave.discord.FFmpegOpusAudio", MagicMock())
    c = cog()
    guild = SimpleNamespace(id=1, voice_client=None)
    assert "Join a voice channel" in await c.speak(member(guild, None), "hi")
    guild.voice_client = vc(5, playing=True)
    assert "won't talk over the music" in await c.speak(member(guild, 5), "hi")
    guild.voice_client = vc(6, playing=True)
    assert "busy broadcasting" in await c.speak(member(guild, 5), "hi")


async def test_joins_speaks_cleans_up_and_leaves(monkeypatch):
    monkeypatch.setattr("commands.voice_cave.discord.FFmpegOpusAudio", MagicMock())
    c = cog()
    guild = SimpleNamespace(id=1, voice_client=None)
    m = member(guild, 5)
    joined = vc(5)

    async def connect():
        guild.voice_client = joined
        return joined
    m.voice.channel.connect = connect

    assert await c.speak(m, "**Science!**") is None
    joined.play.assert_called_once()
    joined.disconnect.assert_awaited_once()                 # joined just to speak -> leaves
    assert not os.path.exists(os.path.join(os.environ.get("TMP", "."), "test_cave_tts.mp3"))
    assert c._speaking == set()


async def test_stays_if_already_connected(monkeypatch):
    monkeypatch.setattr("commands.voice_cave.discord.FFmpegOpusAudio", MagicMock())
    c = cog()
    existing = vc(5)
    guild = SimpleNamespace(id=1, voice_client=existing)
    assert await c.speak(member(guild, 5), "hello") is None
    existing.disconnect.assert_not_awaited()
