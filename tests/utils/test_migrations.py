"""The migration runner, starting from the schema production actually has (tests/fixtures)."""

import glob
import os
import sqlite3

import pytest

from utils import migrations
from utils.database import DatabaseHandler

FIXTURE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fixtures", "prod_schema_2026-10-16.sql")


def make_db(path, schema_sql=None, rows=""):
    with sqlite3.connect(path) as conn:
        if schema_sql:
            conn.executescript(schema_sql)
        if rows:
            conn.executescript(rows)


def versions(path):
    with sqlite3.connect(path) as conn:
        return [r[0] for r in conn.execute("SELECT version FROM schema_version ORDER BY version")]


def backups(tmp_path):
    return glob.glob(str(tmp_path / "backups" / "auto-*.db"))


async def test_prod_schema_upgrades_without_touching_data(tmp_path):
    path = str(tmp_path / "prod.db")
    make_db(path, open(FIXTURE, encoding="utf-8").read(), rows="""
        INSERT INTO ai_summaries (user_id, summary, last_id) VALUES (1, 'Plays Valheim.', 10);
        INSERT INTO ai_dm_summaries (user_id, summary, last_id) VALUES (1, 'DM stuff.', 4);
        INSERT INTO games (title, min_players, max_players, guild_id) VALUES ('Valheim', 1, 10, 0);
    """)
    db = DatabaseHandler(db_path=path)
    await db.setup_tables()

    assert versions(path) == [v for v, _, _ in migrations.MIGRATIONS]
    assert len(backups(tmp_path)) == 1                       # backed up before migrating
    assert (await db.get_ai_summary(1))[0] == "Plays Valheim."   # the summaries wipe didn't fire on prod
    assert (await db.get_ai_summary(1, dm=True))[0] == "DM stuff."
    assert [g["title"] for g in await db.get_game_library(0)] == ["Valheim"]

    await db.setup_tables()                                  # nothing pending: no new backup
    assert len(backups(tmp_path)) == 1


async def test_fresh_database_is_stamped_without_backup(tmp_path):
    path = str(tmp_path / "fresh.db")
    await DatabaseHandler(db_path=path).setup_tables()
    assert versions(path) == [v for v, _, _ in migrations.MIGRATIONS]
    assert backups(tmp_path) == []


async def test_only_pending_migrations_run(tmp_path, monkeypatch):
    path = str(tmp_path / "db.db")
    await DatabaseHandler(db_path=path).setup_tables()
    ran = []

    async def m3(conn, existed_before):
        ran.append(sorted(existed_before)[:1])
        await conn.execute("ALTER TABLE gifts ADD COLUMN note TEXT")

    nxt = migrations.LATEST + 1
    monkeypatch.setattr(migrations, "MIGRATIONS", migrations.MIGRATIONS + [(nxt, "gift notes", m3)])
    monkeypatch.setattr(migrations, "LATEST", nxt)
    await DatabaseHandler(db_path=path).setup_tables()
    await DatabaseHandler(db_path=path).setup_tables()
    assert len(ran) == 1 and versions(path)[-1] == nxt
    with sqlite3.connect(path) as conn:
        assert "note" in [r[1] for r in conn.execute("PRAGMA table_info(gifts)")]


def test_backup_rotation(tmp_path):
    path = str(tmp_path / "x.db")
    make_db(path, "CREATE TABLE t (a);")
    folder = tmp_path / "backups"
    folder.mkdir()
    for i in range(7):
        (folder / f"auto-premigrate-2026010{i}-000000.db").write_bytes(b"")
    migrations.backup(path)
    names = sorted(os.path.basename(p) for p in backups(tmp_path))
    assert len(names) == migrations.BACKUPS_KEPT and "auto-premigrate-20260100-000000.db" not in names


@pytest.mark.parametrize("table", ["games", "tags"])
def test_rebuild_sql_matches_baseline(table):
    # setup_tables and the rebuild migration share one definition
    sql = {"games": migrations.GAMES_SQL, "tags": migrations.TAGS_SQL}[table]
    assert "guild_id" in sql and "UNIQUE" in sql


async def test_persona_columns_keep_existing_memory_as_caves(tmp_path):
    path = str(tmp_path / "prod.db")
    make_db(path, open(FIXTURE, encoding="utf-8").read(), rows="""
        INSERT INTO ai_history (user_id, guild_id, role, content) VALUES (1, 5, 'user', 'I main Dwarf');
        INSERT INTO ai_history (user_id, guild_id, role, content) VALUES (1, 5, 'model', 'Noted, volunteer!');
        INSERT INTO user_facts (user_id, fact) VALUES (1, 'mains Dwarf in Deep Rock');
        INSERT INTO ai_embeddings (history_id, user_id, text, vector) VALUES (1, 1, 'User: I main Dwarf', x'00');
    """)
    db = DatabaseHandler(db_path=path)
    await db.setup_tables()
    with sqlite3.connect(path) as conn:
        for table in ("ai_history", "ai_embeddings", "user_facts"):
            assert "persona" in [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
    assert [c for _, c, _ in await db.get_ai_history_with_scope(1)] == ["I main Dwarf", "Noted, volunteer!"]
    assert await db.get_user_facts(1) == ["mains Dwarf in Deep Rock"]
    assert len(await db.get_embeddings(1)) == 1
    # A persona starts with a clean slate
    assert await db.get_ai_history_with_scope(1, persona="hank") == []
    assert await db.get_user_facts(1, persona="hank") == []
    assert await db.get_embeddings(1, persona="hank") == []
    await db.setup_tables()                                  # idempotent
