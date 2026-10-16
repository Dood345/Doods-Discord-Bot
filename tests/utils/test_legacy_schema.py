"""Regression: production's games/tags tables predated guild_id, and CREATE TABLE IF NOT EXISTS
left them that way, so every per-server game query failed with 'no such column: guild_id'."""

import sqlite3

from utils.database import DatabaseHandler

LEGACY_SCHEMA = """
CREATE TABLE games (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT UNIQUE, category TEXT, min_players INTEGER,
    max_players INTEGER, ideal_players INTEGER, status TEXT DEFAULT 'unknown', external_rating TEXT, notes TEXT,
    release_date TEXT, release_state TEXT, last_update TEXT, store_link TEXT, added_by INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE tags (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE game_tags (game_id INTEGER, tag_id INTEGER, PRIMARY KEY (game_id, tag_id),
    FOREIGN KEY(game_id) REFERENCES games(id) ON DELETE CASCADE, FOREIGN KEY(tag_id) REFERENCES tags(id) ON DELETE CASCADE);
INSERT INTO games (id, title, min_players, max_players, status) VALUES (7, 'Valheim', 1, 10, 'played');
INSERT INTO tags (id, name) VALUES (3, 'survival');
INSERT INTO game_tags VALUES (7, 3);
"""


async def test_legacy_game_tables_are_migrated(tmp_path):
    path = str(tmp_path / "legacy.db")
    with sqlite3.connect(path) as conn:
        conn.executescript(LEGACY_SCHEMA)

    db = DatabaseHandler(db_path=path)
    await db.setup_tables()
    await db.setup_tables()  # idempotent on the second start

    with sqlite3.connect(path) as conn:
        for table in ("games", "tags"):
            assert "guild_id" in [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
        assert not conn.execute("SELECT name FROM sqlite_master WHERE name LIKE '%_legacy'").fetchall()
        game_tags_sql = conn.execute("SELECT sql FROM sqlite_master WHERE name = 'game_tags'").fetchone()[0]
        assert "REFERENCES games(id)" in game_tags_sql and "REFERENCES tags(id)" in game_tags_sql

    # Old rows became shared (guild_id 0) with ids and tag links intact
    library = await db.get_game_library(guild_id=123)
    assert [(g["id"], g["title"], g["tags"]) for g in library] == [(7, "Valheim", "survival")]
    assert "Valheim" in await db.recommend_games(guild_id=123, min_players=4)
    assert "Valheim" in await db.recommend_games(guild_id=123, tag="surv")

    # Per-server features work now: the same title can exist per server
    assert await db.add_game("Lethal Company", 1, 123, min_players=1, max_players=4, tags=["horror"]) not in (None, -1)
    assert await db.search_game_titles("Lethal", 999) == []
    assert await db.get_tags(123) == ["horror", "survival"]
