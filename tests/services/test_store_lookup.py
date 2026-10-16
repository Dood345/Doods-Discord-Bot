from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from commands.game_commands import GameCommands
from services.game_service import GameService
from services.store_lookup import StoreLookup, details_from_steam, parse_store_link
from utils.agent import ToolContext
from utils.agent_tools import build_cave_tools
from utils.dialogue_manager import DialogueManager

VALHEIM = {
    "name": "Valheim",
    "short_description": "A brutal exploration and survival game for 1-10 players.",
    "genres": [{"description": "Action"}, {"description": "Indie"}, {"description": "RPG"}],
    "categories": [{"description": "Single-player"}, {"description": "Online Co-op"}],
    "release_date": {"coming_soon": False, "date": "Feb 2, 2021"},
    "metacritic": {"score": 89},
}


def test_parse_store_links():
    assert parse_store_link("https://store.steampowered.com/app/892970/Valheim/") == {"store": "steam", "app_id": 892970}
    assert parse_store_link("https://store.epicgames.com/en-US/p/alan-wake-2") == {"store": "epic", "title": "Alan Wake 2"}
    assert parse_store_link("https://store.epicgames.com/en-US/p/hades-a1b2c3d4")["title"] == "Hades"
    for bad in ("https://example.com/app/5", "ftp://store.steampowered.com/app/5", "valheim", "https://store.steampowered.com/"):
        assert parse_store_link(bad) is None


def test_details_from_steam():
    info = details_from_steam(VALHEIM, "Very Positive")
    assert (info["title"], info["min_players"], info["max_players"], info["players_guessed"]) == ("Valheim", 1, 10, False)
    assert info["tags"] == "action, rpg, co-op"  # no 'indie', no 'single-player' on a co-op game
    assert info["external_rating"] == "Very Positive, Metacritic 89"
    assert info["release_state"] == "full release"

    early = dict(VALHEIM, short_description="Scavenge moons.", genres=[{"description": "Early Access"}], metacritic=None)
    info = details_from_steam(early, None)
    assert (info["min_players"], info["max_players"], info["players_guessed"]) == (1, 4, True)
    assert info["release_state"] == "early access" and info["external_rating"] is None
    solo = dict(early, categories=[{"description": "Single-player"}])
    assert details_from_steam(solo, None)["max_players"] == 1


async def test_lookup_never_fetches_non_store_links():
    store = StoreLookup()
    store._json = AsyncMock()
    assert await store.lookup("http://192.0.2.1/admin") is None
    store._json.assert_not_awaited()


def fake_service(db, info):
    service = GameService(db, DialogueManager(), store_lookup=SimpleNamespace(lookup=AsyncMock(return_value=info)))
    return service


async def test_add_game_tool_fills_from_link(temp_db):
    info = {"store_link": "https://store.steampowered.com/app/892970/", **details_from_steam(VALHEIM, "Very Positive")}
    bot = SimpleNamespace(db=temp_db, game_service=fake_service(temp_db, info))
    ch = MagicMock()
    ch.send = AsyncMock(return_value=SimpleNamespace(content="card", edit=AsyncMock()))
    user = SimpleNamespace(id=7, name="rando", display_name="Rando")
    ctx = ToolContext(bot=bot, user=user, guild=SimpleNamespace(id=99), channel=ch)

    result = await build_cave_tools().dispatch(
        "add_game", {"link": info["store_link"], "title": "valheim game", "min_players": 1, "max_players": 4}, ctx)
    assert result.startswith("PENDING")
    card = ch.send.call_args.kwargs["view"].body.content
    assert "**Valheim** (1-10 players" in card and "Very Positive" in card

    view = ch.send.call_args.kwargs["view"]
    click = SimpleNamespace(user=user, guild=None, channel=None, message=SimpleNamespace(content="card"),
                            response=SimpleNamespace(edit_message=AsyncMock(), send_message=AsyncMock()),
                            followup=SimpleNamespace(send=AsyncMock()))
    await view.confirm.callback(click)
    game = (await temp_db.get_game_library(99))[0]
    assert game["title"] == "Valheim" and game["max_players"] == 10
    assert game["store_link"] == info["store_link"] and game["release_state"] == "full release"


async def test_add_game_tool_rejects_non_store_link(temp_db):
    bot = SimpleNamespace(db=temp_db, game_service=fake_service(temp_db, None))
    ctx = ToolContext(bot=bot, user=SimpleNamespace(id=7, display_name="R"), guild=SimpleNamespace(id=99), channel=MagicMock())
    assert (await build_cave_tools().dispatch("add_game", {"link": "https://example.com"}, ctx)).startswith("ERROR")


async def test_game_add_command_with_only_a_link(temp_db):
    info = {"store_link": "https://store.steampowered.com/app/1966720/", "title": "Lethal Company",
            "min_players": 1, "max_players": 4, "players_guessed": True, "tags": "action, co-op",
            "release_state": "early access", "external_rating": "Overwhelmingly Positive"}
    cog = GameCommands(SimpleNamespace(game_service=fake_service(temp_db, info)))
    sent = AsyncMock()
    interaction = SimpleNamespace(user=SimpleNamespace(id=7), guild_id=99,
                                  response=SimpleNamespace(defer=AsyncMock()), followup=SimpleNamespace(send=sent))

    await GameCommands.add_game.callback(cog, interaction, link=info["store_link"])
    text = sent.call_args.args[0]
    assert "1-4 players" in text and "guessed" in text and "Overwhelmingly Positive" in text
    game = (await temp_db.get_game_library(99))[0]
    assert game["title"] == "Lethal Company" and game["release_state"] == "early access"

    await GameCommands.add_game.callback(cog, interaction)
    assert sent.call_args.kwargs.get("ephemeral") is True
