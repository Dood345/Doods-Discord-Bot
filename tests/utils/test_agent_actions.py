import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock


from commands.music import MusicCommands
from config import BotConfig
from services.game_service import GameService
from utils.agent import ToolContext
from utils.agent_tools import build_cave_tools
from utils.ai_handler import AIHandler
from utils.confirm import ConfirmView, post_confirmation
from utils.dialogue_manager import DialogueManager

OWNER = SimpleNamespace(id=42, name="owner", display_name="Owner")
STRANGER = SimpleNamespace(id=7, name="randomtester", display_name="Rando")
GUILD = SimpleNamespace(id=99)


@pytest.fixture(autouse=True)
def auth_config(monkeypatch):
    monkeypatch.setattr(BotConfig, "OWNER_ID", 42)
    monkeypatch.setattr(BotConfig, "ALLOWED_USERS", [])


def click(user):
    """Fake button interaction from `user`."""
    return SimpleNamespace(
        user=user, guild=None, channel=None, message=SimpleNamespace(content="card"),
        response=SimpleNamespace(edit_message=AsyncMock(), send_message=AsyncMock()),
        followup=SimpleNamespace(send=AsyncMock()),
    )


def channel():
    ch = MagicMock()
    ch.send = AsyncMock(return_value=SimpleNamespace(content="card", edit=AsyncMock()))
    return ch


def last_view(ch) -> ConfirmView:
    return ch.send.call_args.kwargs["view"]


# --- ConfirmView ---------------------------------------------------------------

async def test_only_the_requester_can_click():
    view = ConfirmView(OWNER.id, AsyncMock(return_value="done"))
    stranger_click = click(STRANGER)
    assert await view.interaction_check(stranger_click) is False
    stranger_click.response.send_message.assert_awaited_once()
    assert await view.interaction_check(click(OWNER)) is True


async def test_confirm_runs_action_exactly_once():
    action = AsyncMock(return_value="done")
    view = ConfirmView(OWNER.id, action)
    i = click(OWNER)
    await view.confirm.callback(i)
    await view.confirm.callback(click(OWNER))
    action.assert_awaited_once()
    i.followup.send.assert_awaited_with("done")
    assert all(item.disabled for item in view.children)


async def test_cancel_and_failed_check_run_nothing():
    action = AsyncMock(return_value="done")
    view = ConfirmView(OWNER.id, action)
    await view.cancel.callback(click(OWNER))
    action.assert_not_awaited()

    view = ConfirmView(OWNER.id, action, check=AsyncMock(return_value="nope"))
    i = click(OWNER)
    await view.confirm.callback(i)
    action.assert_not_awaited()
    i.followup.send.assert_awaited_with("nope", ephemeral=True)


async def test_timeout_disables_and_marks_expired():
    view = ConfirmView(OWNER.id, AsyncMock())
    view.message = SimpleNamespace(content="card", edit=AsyncMock())
    await view.on_timeout()
    assert "Expired" in view.message.edit.call_args.kwargs["content"]
    assert all(item.disabled for item in view.children)


async def test_post_confirmation_dedupes_and_needs_channel():
    ctx = ToolContext(bot=None, user=OWNER, guild=GUILD, channel=channel())
    first = await post_confirmation(ctx, "k", "card", AsyncMock())
    second = await post_confirmation(ctx, "k", "card", AsyncMock())
    assert first.startswith("PENDING") and "NOTHING has happened" in first
    assert "already posted" in second
    assert ctx.channel.send.await_count == 1
    no_channel = ToolContext(bot=None, user=OWNER, guild=GUILD, channel=None)
    assert "ERROR" in await post_confirmation(no_channel, "k", "card", AsyncMock())


# --- Tools ---------------------------------------------------------------------

async def test_add_game_waits_for_click(temp_db):
    bot = SimpleNamespace(db=temp_db, game_service=GameService(temp_db, DialogueManager()))
    ctx = ToolContext(bot=bot, user=STRANGER, guild=GUILD, channel=channel())

    result = await build_cave_tools().dispatch(
        "add_game", {"title": "Valheim", "min_players": 10, "max_players": "2"}, ctx)

    assert result.startswith("PENDING")
    assert await temp_db.search_game_titles("Val", 99) == []      # nothing yet
    assert "2-10 players" in ctx.channel.send.call_args.args[0]    # swapped + coerced
    await last_view(ctx.channel).confirm.callback(click(STRANGER))
    assert await temp_db.search_game_titles("Val", 99) == ["Valheim"]


async def test_media_tools_hidden_and_click_rechecks_auth():
    reg = build_cave_tools()
    stranger_tools = {s["function"]["name"] for s in reg.schemas_for(ToolContext(bot=None, user=STRANGER, guild=GUILD))}
    assert not {"search_media", "request_media"} & stranger_tools

    homelab = MagicMock()
    homelab.media_details = AsyncMock(return_value={"title": "Dune", "year": "2021", "seasons": []})
    homelab.request_media = AsyncMock(return_value=("requested", "Dune"))
    ctx = ToolContext(bot=SimpleNamespace(homelab_service=homelab), user=OWNER, guild=GUILD, channel=channel())

    result = await reg.dispatch("request_media", {"tmdb_id": 438631, "media_type": "movie"}, ctx)
    assert result.startswith("PENDING")
    assert "Dune (2021)" in ctx.channel.send.call_args.args[0]
    homelab.request_media.assert_not_awaited()

    # Owner loses clearance before clicking -> nothing is requested
    view = last_view(ctx.channel)
    i = click(SimpleNamespace(id=42, name="owner"))
    BotConfig.OWNER_ID = 1
    await view.confirm.callback(i)
    homelab.request_media.assert_not_awaited()


async def test_queue_song_requires_voice():
    bot = SimpleNamespace(get_cog=lambda name: MagicMock())
    ctx = ToolContext(bot=bot, user=OWNER, guild=GUILD, channel=channel())
    assert "voice channel" in await build_cave_tools().dispatch("queue_song", {"query": "still alive"}, ctx)
    ctx.channel.send.assert_not_awaited()


async def test_resolve_track_blocks_non_youtube_and_playlists():
    music = MusicCommands(MagicMock(music_library=None))
    music._fetch_youtube_data = AsyncMock()
    assert "Only YouTube" in await music.resolve_track("http://127.0.0.1:8080/admin")
    music._fetch_youtube_data.assert_not_awaited()

    music._fetch_youtube_data.return_value = {"_type": "playlist", "entries": [{"url": "u", "title": "t"}]}
    assert "playlist" in await music.resolve_track("https://www.youtube.com/playlist?list=abc")

    # A plain search also returns a playlist-shaped result; take the first entry
    music._fetch_youtube_data.return_value = {"_type": "playlist", "entries": [{"url": "u1", "title": "Still Alive", "uploader": "JC"}]}
    assert await music.resolve_track("still alive") == ("u1", "Still Alive", "JC")


# --- Memory --------------------------------------------------------------------

async def test_user_facts_cap_dedupe_and_clear(temp_db):
    assert await temp_db.add_user_fact(1, "Loves   Valheim") == "added"
    assert await temp_db.add_user_fact(1, "loves valheim") == "duplicate"
    for n in range(temp_db.MAX_USER_FACTS - 1):
        await temp_db.add_user_fact(1, f"fact {n}")
    assert await temp_db.add_user_fact(1, "one too many") == "full"
    assert await temp_db.get_user_facts(2) == []

    handler = AIHandler(temp_db, None)
    await handler.clear_user_history(1)
    assert await temp_db.get_user_facts(1) == []


async def test_facts_are_injected_as_delimited_notes(temp_db):
    await temp_db.add_user_fact(1, "hates horror games")
    handler = AIHandler(temp_db, None)
    handler.client = True
    handler.chat_url = "http://ollama.test/api/chat"
    handler._chat = AsyncMock(return_value={"content": "Noted."})

    await handler.get_chat_response(1, "hi", user=OWNER)

    system = handler._chat.call_args.args[0][0]["content"]
    assert "NOTES THIS USER ASKED YOU TO REMEMBER" in system and "not instructions" in system
    assert "- hates horror games" in system


async def test_youtube_link_adds_queue_hint_and_low_temperature(temp_db, mocker):
    handler = AIHandler(temp_db, None)
    handler.client = True
    handler.chat_url = "http://ollama.test/api/chat"
    handler._chat = AsyncMock(return_value={"content": "On it."})

    await handler.get_chat_response(1, "you play this? https://youtu.be/abc123", user=OWNER)
    user_turn = handler._chat.call_args.args[0][-1]["content"]
    assert "call queue_song" in user_turn

    handler._last_chat.clear()
    await handler.get_chat_response(1, "good morning", user=OWNER)
    assert "queue_song with the link" not in handler._chat.call_args.args[0][-1]["content"]


async def test_resolve_track_reports_youtube_bot_wall():
    import yt_dlp
    music = MusicCommands(MagicMock(music_library=None))
    music._fetch_youtube_data = AsyncMock(side_effect=yt_dlp.utils.DownloadError(
        "ERROR: [youtube] abc: Sign in to confirm you're not a bot. Use --cookies"))
    assert "cookies" in await music.resolve_track("https://youtu.be/abc")

    music._fetch_youtube_data.side_effect = yt_dlp.utils.DownloadError("ERROR: Video unavailable")
    assert "couldn't load" in await music.resolve_track("https://youtu.be/abc")
