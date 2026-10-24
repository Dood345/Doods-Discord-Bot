"""Numbered schema migrations for databases that already exist.

`DatabaseHandler.setup_tables()` creates any missing table in its current shape (the baseline), then
`run_migrations()` upgrades tables that predate a change, because CREATE TABLE IF NOT EXISTS never
alters an existing table. `schema_version` records what has run. A brand-new database is stamped
at the latest version without running anything.

Adding a migration: append (next number, description, async fn(conn, existed_before)) to MIGRATIONS.
Write it to be safe on databases that already have the change (check columns before altering), and
add a test that upgrades tests/fixtures/prod_schema_*.sql. A backup is taken automatically before
any pending migration runs (data/backups/auto-*.db, newest 5 kept).
"""

import glob
import logging
import os
import sqlite3
from datetime import datetime
from typing import Awaitable, Callable, List, Set, Tuple

logger = logging.getLogger(__name__)

BACKUPS_KEPT = 5

# Current definitions of tables that migrations rebuild ({table} = name to create)
GAMES_SQL = '''CREATE TABLE IF NOT EXISTS {table}
    (id INTEGER PRIMARY KEY AUTOINCREMENT,
     title TEXT,
     category TEXT,
     min_players INTEGER,
     max_players INTEGER,
     ideal_players INTEGER,
     status TEXT DEFAULT 'unknown',
     external_rating TEXT,
     notes TEXT,
     release_date TEXT,
     release_state TEXT,
     last_update TEXT,
     store_link TEXT,
     added_by INTEGER,
     guild_id INTEGER,
     created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
     UNIQUE(title, guild_id))'''

TAGS_SQL = '''CREATE TABLE IF NOT EXISTS {table}
    (id INTEGER PRIMARY KEY AUTOINCREMENT,
     name TEXT,
     guild_id INTEGER,
     created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
     UNIQUE(name, guild_id))'''


async def columns(conn, table: str) -> List[str]:
    async with conn.execute(f"PRAGMA table_info({table})") as cursor:
        return [row[1] for row in await cursor.fetchall()]


async def table_names(conn) -> Set[str]:
    async with conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'") as cursor:
        return {row[0] for row in await cursor.fetchall()}


# --- Migrations -------------------------------------------------------------------------------

async def _per_server_games(conn, existed_before: Set[str]):
    """games/tags from before per-server data: no guild_id, globally UNIQUE title/name.
    Rebuild them in the current shape; existing rows become shared (guild_id 0) and keep their ids,
    so game_tags and game_ratings links survive."""
    for table, sql in (("games", GAMES_SQL), ("tags", TAGS_SQL)):
        old_cols = await columns(conn, table)
        if not old_cols or "guild_id" in old_cols:
            continue
        logger.warning(f"Migrating legacy '{table}' table to the per-server schema")
        await conn.execute(sql.format(table=f"{table}_new"))
        shared = [c for c in old_cols if c in await columns(conn, f"{table}_new") and c != "guild_id"]
        col_list = ", ".join(shared)
        await conn.execute(f"INSERT OR IGNORE INTO {table}_new ({col_list}, guild_id) SELECT {col_list}, 0 FROM {table}")
        await conn.execute(f"DROP TABLE {table}")
        # Renaming a table that nothing references leaves game_tags' "REFERENCES games(id)" intact
        await conn.execute(f"ALTER TABLE {table}_new RENAME TO {table}")


async def _separate_dm_memory(conn, existed_before: Set[str]):
    """DM memory kept apart from server memory: is_dm columns, and summaries that mixed both are reset."""
    if "is_dm" not in await columns(conn, "ai_embeddings"):
        await conn.execute("ALTER TABLE ai_embeddings ADD COLUMN is_dm INTEGER DEFAULT 0")
        await conn.execute("UPDATE ai_embeddings SET is_dm = 1 WHERE history_id IN "
                           "(SELECT id FROM ai_history WHERE guild_id IS NULL)")
    if "is_dm" not in await columns(conn, "user_facts"):
        # Where old notes were saved wasn't recorded; they stay visible everywhere
        await conn.execute("ALTER TABLE user_facts ADD COLUMN is_dm INTEGER DEFAULT 0")
    if "ai_summaries" in existed_before and "ai_dm_summaries" not in existed_before:
        # Summaries from before the split mixed DM and server chat: rebuild them per scope
        await conn.execute("DELETE FROM ai_summaries")


async def _persona_memory(conn, existed_before: Set[str]):
    """Channel personas keep their own memory: a persona column (NULL = Cave, so all existing rows stay Cave's)."""
    for table in ("ai_history", "ai_embeddings", "user_facts"):
        if table in await table_names(conn) and "persona" not in await columns(conn, table):
            await conn.execute(f"ALTER TABLE {table} ADD COLUMN persona TEXT")


Migration = Tuple[int, str, Callable[..., Awaitable[None]]]
MIGRATIONS: List[Migration] = [
    (1, "per-server games and tags", _per_server_games),
    (2, "DM memory kept apart from server memory", _separate_dm_memory),
    (3, "per-persona memory (persona column, NULL = Cave)", _persona_memory),
]
LATEST = MIGRATIONS[-1][0]


# --- Runner -----------------------------------------------------------------------------------

def current_version_sync(db_path: str) -> Tuple[int, bool]:
    """(schema version, whether the database already has tables), read without aiosqlite."""
    if db_path == ":memory:" or not os.path.exists(db_path):
        return 0, False
    with sqlite3.connect(db_path) as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        if "schema_version" not in tables:
            return 0, bool(tables)
        return conn.execute("SELECT COALESCE(MAX(version), 0) FROM schema_version").fetchone()[0], True


def backup(db_path: str, label: str = "premigrate", keep: int = BACKUPS_KEPT) -> str:
    """Consistent copy via SQLite's backup API into data/backups, keeping the newest `keep` with this label."""
    folder = os.path.join(os.path.dirname(db_path) or ".", "backups")
    os.makedirs(folder, exist_ok=True)
    target = os.path.join(folder, f"auto-{label}-{datetime.now():%Y%m%d-%H%M%S}.db")
    with sqlite3.connect(db_path) as src, sqlite3.connect(target) as dst:
        src.backup(dst)
    for old in sorted(glob.glob(os.path.join(folder, f"auto-{label}-*.db")))[:-keep]:
        os.remove(old)
    return target


async def run_migrations(conn, existed_before: Set[str]) -> List[int]:
    """Apply pending migrations in order; returns the versions applied (stamps fresh databases)."""
    await conn.execute("CREATE TABLE IF NOT EXISTS schema_version "
                       "(version INTEGER PRIMARY KEY, description TEXT, applied_at DATETIME DEFAULT CURRENT_TIMESTAMP)")
    async with conn.execute("SELECT COALESCE(MAX(version), 0) FROM schema_version") as cursor:
        current = (await cursor.fetchone())[0]
    if not existed_before - {"schema_version"}:
        # Brand-new database: the baseline already is the latest schema
        await conn.executemany("INSERT OR IGNORE INTO schema_version (version, description) VALUES (?, ?)",
                               [(v, d) for v, d, _ in MIGRATIONS])
        await conn.commit()
        return []
    applied = []
    for version, description, fn in MIGRATIONS:
        if version <= current:
            continue
        logger.info(f"Applying database migration {version}: {description}")
        await fn(conn, existed_before)
        await conn.execute("INSERT INTO schema_version (version, description) VALUES (?, ?)", (version, description))
        await conn.commit()
        applied.append(version)
    return applied
