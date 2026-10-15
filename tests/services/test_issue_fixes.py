"""Regression tests for #48 (gift claim privacy) and #100 (per-server game data)."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from commands.gift_commands import GiftCommands
from services.gift_service import GiftService

BASE = 0  # shared base library


async def test_base_game_ratings_and_tags_are_per_server(temp_db):
    game_id = await temp_db.add_game("Valheim", added_by=1, guild_id=BASE, min_players=1, max_players=10, tags=["survival"])
    await temp_db.rate_game(game_id, user_id=1, guild_id=111, rating=10)
    await temp_db.rate_game(game_id, user_id=2, guild_id=111, rating=8)
    await temp_db.rate_game(game_id, user_id=3, guild_id=222, rating=2)
    await temp_db.add_tags(game_id, ["spicy"], guild_id=111)

    lib_a = {g["title"]: g for g in await temp_db.get_game_library(111)}
    lib_b = {g["title"]: g for g in await temp_db.get_game_library(222)}

    assert lib_a["Valheim"]["avg_rating"] == 9
    assert lib_b["Valheim"]["avg_rating"] == 2
    assert sorted(lib_a["Valheim"]["tags"].split(", ")) == ["spicy", "survival"]   # no duplicates
    assert lib_b["Valheim"]["tags"] == "survival"                                   # 111's tag hidden
    assert [g["title"] for g in await temp_db.get_game_library(222, tag_filter="spicy")] == []
    assert "No simulations" in await temp_db.recommend_games(222, tag="spicy")
    assert "Valheim" in await temp_db.recommend_games(111, tag="spicy")


async def test_server_games_stay_private(temp_db):
    await temp_db.add_game("Secret Game", added_by=1, guild_id=111, min_players=1, max_players=4)
    assert [g["title"] for g in await temp_db.get_game_library(111)] == ["Secret Game"]
    assert await temp_db.get_game_library(222) == []


async def test_claimable_and_my_claims(temp_db):
    gifts = GiftService(temp_db)
    await gifts.add_gift(1, 9, "Lego set")
    await gifts.add_gift(1, 9, "Socks")
    await gifts.add_gift(2, 9, "Own thing")
    lego_id = (await gifts.get_wishlist(1, 9))[0][0]

    claimable = await gifts.get_claimable(2, 9)
    assert {name for _, name, _ in claimable} == {"Lego set", "Socks"}   # not your own items
    await gifts.claim_gift(2, 9, lego_id)
    assert {name for _, name, _ in await gifts.get_claimable(2, 9)} == {"Socks"}
    assert [(name, owner) for _, name, owner in await gifts.get_my_claims(2, 9)] == [("Lego set", 1)]


def view_interaction(viewer_id):
    return SimpleNamespace(
        user=SimpleNamespace(id=viewer_id), guild_id=9, guild=None,
        response=SimpleNamespace(send_message=AsyncMock()))


async def test_owner_never_sees_claims_and_ids_are_hidden(temp_db):
    gifts = GiftService(temp_db)
    await gifts.add_gift(1, 9, "Lego set")
    item_id = (await gifts.get_wishlist(1, 9))[0][0]
    await gifts.claim_gift(2, 9, item_id)
    cog = GiftCommands(MagicMock(gift_service=gifts))
    owner = SimpleNamespace(id=1, display_name="Owner")

    as_owner = view_interaction(1)
    await cog.gift_view.callback(cog, as_owner, owner)
    owner_text = str(as_owner.response.send_message.call_args.kwargs["embed"].to_dict())
    assert "CLAIMED" not in owner_text and "ID" not in owner_text

    as_friend = view_interaction(3)
    await cog.gift_view.callback(cog, as_friend, owner)
    friend_text = str(as_friend.response.send_message.call_args.kwargs["embed"].to_dict())
    assert "CLAIMED" in friend_text and f"ID: {item_id}" not in friend_text
