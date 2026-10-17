---
name: db-migration
description: Change the schema of an existing table safely (add/rename columns, change constraints, backfill, rebuild) via utils/migrations.py, with a test against production's real schema and a dry run on a copy of the prod DB. Use whenever a change touches a table that already exists in production.
---

# Schema changes

`CREATE TABLE IF NOT EXISTS` in `DatabaseHandler.setup_tables()` only creates *missing* tables; it never alters an existing one. Production's DB is old (it once still had pre-`guild_id` game tables, which broke every per-server game query with "no such column" while every test passed on fresh DBs).

## New table
Add it to `setup_tables()`. No migration needed. Add it to the next `tests/fixtures/prod_schema_*.sql` refresh.

## Changing an existing table
1. Update the `CREATE TABLE` in `setup_tables()` (or the shared `GAMES_SQL`/`TAGS_SQL` in `utils/migrations.py`) so fresh databases get the new shape.
2. Append a migration to `MIGRATIONS` in `utils/migrations.py`: `(next_number, "what it does", async fn(conn, existed_before))`. Rules:
   - **Idempotent and state-checking**: check `await columns(conn, table)` before `ALTER TABLE ... ADD COLUMN`; a rebuild checks the old shape first.
   - Destructive steps (DELETE, wipes) only when `existed_before` proves the old state; production may already be past it.
   - Rebuilds: create `<table>_new`, copy shared columns (keep ids so links survive), `DROP` the old table, `RENAME` the new one. Don't rename the old table away first (SQLite rewrites other tables' foreign keys to follow it).
   - Backfill from data that exists (e.g. `is_dm` from `ai_history.guild_id IS NULL`); when the truth is unknown, pick the safe default and say so in a comment.
3. Test it in `tests/utils/test_migrations.py` starting from `tests/fixtures/prod_schema_*.sql` with a few realistic rows; assert the data survives and the migration is a no-op the second time.
4. Dry run on a copy of production before shipping:
```
ssh doodlab 'rm -rf /tmp/mig && mkdir -p /tmp/mig/data && rsync -a --exclude venv --exclude data /home/dood345/discordBot/ /tmp/mig/ && cd /home/dood345/discordBot && venv/bin/python -c "import sqlite3; s=sqlite3.connect(\"data/doodlab.db\"); d=sqlite3.connect(\"/tmp/mig/data/doodlab.db\"); s.backup(d)"'
scp utils/database.py utils/migrations.py doodlab:/tmp/mig/utils/
ssh doodlab 'cd /tmp/mig && /home/dood345/discordBot/venv/bin/python -c "import asyncio; from utils.database import DatabaseHandler; asyncio.run(DatabaseHandler().setup_tables())" && <row counts / schema checks> ; rm -rf /tmp/mig'
```
   Compare row counts before/after for every table you touch.
5. Ship. On startup the bot backs up the DB (`data/backups/auto-premigrate-*.db`, newest 5) before applying pending migrations and logs `Applying database migration N`. Check those lines after the deploy.

## Refreshing the prod schema fixture
DDL only, never rows:
```
ssh doodlab 'cd /home/dood345/discordBot && venv/bin/python -c "import sqlite3; c=sqlite3.connect(\"data/doodlab.db\"); [print(s + \";\") for (s,) in c.execute(\"select sql from sqlite_master where sql is not null and name not like \x27sqlite_%\x27 order by type desc, name\")]"' > tests/fixtures/prod_schema_<date>.sql
```
Then grep it for 17–20 digit numbers and LAN IPs before committing (there should be none).
