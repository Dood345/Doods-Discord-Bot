"""Components v2 builders (utils/layouts.py): structure, Discord's limits, and no content/embed mixing."""

import discord
import pytest

from services.points_service import Achievement
from utils import layouts


def payload(card: layouts.Card) -> list:
    return card.to_components()


def all_text(card: layouts.Card) -> str:
    return "\n".join(item.content for item in card.walk_children() if isinstance(item, discord.ui.TextDisplay))


def assert_within_limits(card: layouts.Card):
    assert card.content_length() <= 4000
    assert card.total_children_count <= 40
    payload(card)  # serialises


YT = ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "Never Gonna", "Rick")
PLEX = ("plex:/library/parts/1/file.flac", "Still Alive", "GLaDOS")


def test_queue_card_shows_now_playing_with_thumbnail_and_up_next():
    card = layouts.queue_card(YT, [PLEX] * 3, channel_name="Lab", elapsed=75, source=lambda url: "▶️ YouTube")
    text = all_text(card)
    assert "Never Gonna" in text and "1:15" in text and "▶️ YouTube" in text
    assert "`3.` Still Alive · GLaDOS" in text and "Up next** (3)" in text
    thumbs = [i for i in card.walk_children() if isinstance(i, discord.ui.Thumbnail)]
    assert thumbs and "dQw4w9WgXcQ" in thumbs[0].media.url
    assert_within_limits(card)


def test_queue_card_without_thumbnail_and_paused():
    card = layouts.queue_card(PLEX, [], elapsed=10, paused=True)
    assert not [i for i in card.walk_children() if isinstance(i, discord.ui.Section)]
    assert "paused at 0:10" in all_text(card) and "nothing queued" in all_text(card)


def test_queue_card_stays_within_limits_for_huge_queues_and_long_titles():
    long = ("https://soundcloud.com/x", "T" * 500, "U" * 300)
    card = layouts.queue_card(long, [long] * 500)
    assert "…and 490 more" in all_text(card)
    assert_within_limits(card)


def test_points_card_lists_achievements_and_next_up():
    a = Achievement("first", "First Test", "🧪", "Earn a point", "points", 1)
    b = Achievement("ten", "Regular", "🔁", "Earn ten points", "points", 10)
    card = layouts.points_card("Chell", "https://cdn.example/avatar.png", 1234, 2, [a], next_up=b)
    text = all_text(card)
    assert "1,234" in text and "#2" in text and "🧪 **First Test** · Earn a point" in text and "Next up: 🔁 Regular" in text
    assert any(isinstance(i, discord.ui.Thumbnail) for i in card.walk_children())
    assert_within_limits(card)


def test_leaderboard_card_podium_then_rest():
    board = [(f"user{i}", 100 - i) for i in range(10)]
    text = all_text(layouts.leaderboard_card(board))
    assert "🥇 **user0** · 100" in text and "🥉 **user2**" in text and "`#4` user3 · 97" in text


def test_leaderboard_card_huge_board_fits():
    card = layouts.leaderboard_card([("N" * 100, 5)] * 2000)
    assert_within_limits(card)


def game(title, status="playing", rating=7.5):
    return {"title": title, "status": status, "avg_rating": rating, "min_players": 2, "max_players": 4,
            "ideal_players": 3, "release_state": "full release"}


def test_game_library_card_groups_by_status():
    games = [game("Portal 2"), game("Deep Rock", "wishlisted", None), game("Lethal", "avoid")]
    text = all_text(layouts.game_library_card(games, ["Player Count: **3**"], grouped=True))
    assert text.index("Playing") < text.index("Wishlisted") < text.index("Avoid")
    assert "unrated" in text and "3 simulations" in text


def test_game_library_card_fits_a_huge_library():
    games = [game("G" * 90 + str(i), s) for i in range(400) for s in ("playing",)]
    card = layouts.game_library_card(games, [], grouped=False)
    assert "more" in all_text(card)
    assert_within_limits(card)


def test_game_night_card():
    card = layouts.game_night_card(1700000000, 4, "GAME NIGHT!", [game("Portal 2")], "📅 Event created")
    text = all_text(card)
    assert "<t:1700000000:F>" in text and "4 players" in text and "Portal 2" in text and "Event created" in text
    assert_within_limits(card)


def test_printer_card_printing_with_snapshot():
    status = {"state": "printing", "filename": "benchy.gcode", "progress": 42, "duration": "1h 2m",
              "remaining": "1h", "layer": (10, 100), "temps": {"extruder": (210, 210), "heater_bed": (60, 60)},
              "filament_detected": False, "message": "Printing"}
    card = layouts.printer_card(status, media_filename="snapshot.jpg")
    text = all_text(card)
    assert "PRINTING" in text and "42%" in text and "layer 10/100" in text and "no filament" in text
    gallery = [i for i in card.walk_children() if isinstance(i, discord.ui.MediaGallery)]
    assert gallery and gallery[0].items[0].media.url == "attachment://snapshot.jpg"
    accent = card.container.accent_colour
    assert getattr(accent, "value", accent) == 0x2ECC71
    assert_within_limits(card)


def test_printer_card_idle_without_media():
    card = layouts.printer_card({"state": "standby", "temps": {}, "filament_detected": True, "message": ""},
                                media_note="Couldn't record a clip")
    assert not [i for i in card.walk_children() if isinstance(i, discord.ui.MediaGallery)]
    assert "Couldn't record a clip" in all_text(card)


def test_card_rejects_text_over_the_limit():
    with pytest.raises(ValueError):
        layouts.Card(layouts.text("x" * 4001))


def test_fit_lines_budget():
    out = layouts.fit_lines([f"line {i}" for i in range(100)], 50)
    assert len(out) <= 60 and out.endswith("more")
    assert layouts.fit_lines(["a", "b"], 100) == "a\nb"


def test_youtube_thumbnail_only_for_youtube():
    assert layouts.youtube_thumbnail("https://youtu.be/dQw4w9WgXcQ")
    assert layouts.youtube_thumbnail("https://soundcloud.com/a/b") is None
    assert layouts.youtube_thumbnail("plex:/library/parts/1") is None
    assert layouts.youtube_thumbnail("https://soundcloud.com/a?v=dQw4w9WgXcQ") is None


def test_elapsed_seconds_respects_pause():
    assert layouts.elapsed_seconds(100.0, None, now=160.0) == 60.0
    assert layouts.elapsed_seconds(100.0, 130.0, now=500.0) == 30.0
    assert layouts.elapsed_seconds(None, None) is None


def test_game_library_card_clips_a_huge_tag_filter():
    games = [game("G" * 90 + str(i), s) for i in range(300) for s in GAME_STATUSES]
    card = layouts.game_library_card(games, ["Tag: **" + "x" * 5000 + "**"], grouped=True)
    assert_within_limits(card)


GAME_STATUSES = ("playing", "wishlisted", "unknown", "played", "avoid")
