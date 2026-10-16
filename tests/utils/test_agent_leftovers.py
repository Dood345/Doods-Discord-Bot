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


# --- /play routing --------------------------------------------------------------

def play_interaction():
    from unittest.mock import AsyncMock
    msg = SimpleNamespace(edit=AsyncMock())
    return SimpleNamespace(
        guild=SimpleNamespace(id=GUILD_ID), channel=None,
        response=SimpleNamespace(defer=AsyncMock()),
        followup=SimpleNamespace(send=AsyncMock(return_value=msg))), msg


async def test_play_search_goes_library_first():
    from unittest.mock import AsyncMock
    music = MusicCommands(MagicMock(music_library=None))
    vc = voice_client(playing=True)
    music._ensure_voice_connection = AsyncMock(return_value=vc)
    tracks = [("plex:/library/parts/1/2/a.flac", "Kryptonite", "3 Doors Down"), ("plex:/x", "Loser", "3 Doors Down")]
    music.resolve_request = AsyncMock(return_value=(tracks, "a 2-track **3 Doors Down** mix"))
    music._fetch_youtube_data = AsyncMock()

    interaction, msg = play_interaction()
    await MusicCommands.play.callback(music, interaction, query="3 doors down", radio=True)

    music.resolve_request.assert_awaited_once_with("3 doors down", radio=True)
    music._fetch_youtube_data.assert_not_awaited()
    assert music.players[5].queue == tracks
    assert "facility archives" in msg.edit.call_args.kwargs["content"]


async def test_play_reports_resolve_errors_and_keeps_links_on_youtube():
    from unittest.mock import AsyncMock
    music = MusicCommands(MagicMock(music_library=None))
    music._ensure_voice_connection = AsyncMock(return_value=voice_client(playing=True))
    music.resolve_request = AsyncMock(return_value="No playable tracks found.")
    interaction, msg = play_interaction()
    await MusicCommands.play.callback(music, interaction, query="zzzz")
    assert "No playable tracks" in msg.edit.call_args.kwargs["content"]
    assert music.players[5].queue == []

    music.resolve_request.reset_mock()
    music._fetch_youtube_data = AsyncMock(return_value={"url": "u", "title": "Still Alive", "uploader": "JC"})
    interaction, _ = play_interaction()
    await MusicCommands.play.callback(music, interaction, url="https://youtu.be/x")
    music.resolve_request.assert_not_awaited()
    assert music.players[5].queue == [("u", "Still Alive", "JC")]


def test_repeated_question_drops_old_answers():
    from utils.ai_handler import drop_repeated_question
    history = [("user", "hi"), ("model", "Hello!"),
               ("user", "What are science points?"), ("model", "Made-up answer."),
               ("user", "play kryptonite"), ("model", "Queued."),
               ("user", "what are SCIENCE points"), ("model", "Made-up answer again.")]
    kept = drop_repeated_question(history, "what are science points??")
    assert kept == [("user", "hi"), ("model", "Hello!"), ("user", "play kryptonite"), ("model", "Queued.")]
    assert drop_repeated_question(history, "something new") == history
