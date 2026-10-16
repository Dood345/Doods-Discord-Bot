from types import SimpleNamespace
from unittest.mock import MagicMock

from commands.music import GuildPlayer, MusicCommands
from services.game_service import GameService
from utils.agent import ToolContext
from utils.agent_tools import build_cave_tools
from utils.dialogue_manager import DialogueManager

GUILD_ID = 99


def voice_client(channel_id=5, playing=True, paused=False):
    vc = MagicMock()
    vc.channel = SimpleNamespace(id=channel_id)
    vc.is_playing.return_value = playing
    vc.is_paused.return_value = paused
    return vc


def member(channel_id=None):
    voice = SimpleNamespace(channel=SimpleNamespace(id=channel_id)) if channel_id else None
    return SimpleNamespace(id=7, name="rando", display_name="Rando", voice=voice)


def music_bot(vc):
    music = MusicCommands(MagicMock(music_library=None))
    player = GuildPlayer(5)
    player.current_track = ("https://youtu.be/x", "Still Alive", "Jonathan Coulton")
    music.players[5] = player
    return SimpleNamespace(get_cog=lambda name: music), SimpleNamespace(id=GUILD_ID, voice_client=vc)


async def test_skip_song_needs_same_voice_channel():
    vc = voice_client()
    bot, guild = music_bot(vc)
    tools = build_cave_tools()

    for user in (member(None), member(channel_id=6)):
        result = await tools.dispatch("skip_song", {}, ToolContext(bot=bot, user=user, guild=guild))
        assert result.startswith("ERROR")
    vc.stop.assert_not_called()

    result = await tools.dispatch("skip_song", {}, ToolContext(bot=bot, user=member(5), guild=guild))
    assert "Still Alive" in result
    vc.stop.assert_called_once()


async def test_skip_works_while_paused_and_reports_idle():
    bot, guild = music_bot(voice_client(playing=False, paused=True))
    music = bot.get_cog("MusicCommands")
    assert music.skip_current(guild)[1] == "Still Alive"

    idle_vc = voice_client(playing=False, paused=False)
    assert music.skip_current(SimpleNamespace(id=GUILD_ID, voice_client=idle_vc)) is None
    idle_vc.stop.assert_not_called()


async def test_rate_game_resolves_loose_titles(temp_db):
    for title in ("Valheim", "Portal", "Portal 2"):
        await temp_db.add_game(title, 1, GUILD_ID)
    bot = SimpleNamespace(db=temp_db, game_service=GameService(temp_db, DialogueManager()))
    ctx = ToolContext(bot=bot, user=member(), guild=SimpleNamespace(id=GUILD_ID))
    tools = build_cave_tools()

    assert not (await tools.dispatch("rate_game", {"title": "valheim", "score": "9"}, ctx)).startswith("ERROR")
    assert not (await tools.dispatch("rate_game", {"title": "portal", "score": 10}, ctx)).startswith("ERROR")
    ambiguous = await tools.dispatch("rate_game", {"title": "port", "score": 7}, ctx)
    assert ambiguous.startswith("ERROR") and "Portal 2" in ambiguous
    assert (await tools.dispatch("rate_game", {"title": "Halo", "score": 7}, ctx)).startswith("ERROR")
    assert (await tools.dispatch("rate_game", {"title": "Valheim", "score": "great"}, ctx)).startswith("ERROR")

    ratings = {g["title"]: g["avg_rating"] for g in await temp_db.get_game_library(GUILD_ID)}
    assert ratings["Valheim"] == 9 and ratings["Portal"] == 10 and ratings["Portal 2"] is None
