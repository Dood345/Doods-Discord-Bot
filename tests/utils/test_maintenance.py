import json
import os
import time

from commands.maintenance import newest_backup_age, write_ready_marker
from utils import migrations


def test_ready_marker_is_fresh_json(tmp_path):
    path = str(tmp_path / "data" / "ready.json")
    before = time.time()
    write_ready_marker(path, guilds=3)
    data = json.load(open(path))
    assert data["ready_at"] >= before and data["guilds"] == 3 and data["pid"] == os.getpid()
    assert os.path.getmtime(path) >= before - 1


def test_nightly_rotation_is_separate_from_premigrate(tmp_path):
    db = str(tmp_path / "x.db")
    import sqlite3
    with sqlite3.connect(db) as c:
        c.execute("CREATE TABLE t (a)")
    folder = tmp_path / "backups"
    folder.mkdir()
    (folder / "auto-premigrate-20260101-000000.db").write_bytes(b"")
    for i in range(16):
        (folder / f"auto-nightly-202601{i + 10:02d}-033000.db").write_bytes(b"")
    migrations.backup(db, "nightly", keep=14)
    names = os.listdir(folder)
    assert sum(n.startswith("auto-nightly-") for n in names) == 14
    assert "auto-premigrate-20260101-000000.db" in names         # other labels untouched


def test_newest_backup_age(tmp_path):
    db = str(tmp_path / "x.db")
    assert newest_backup_age(db) == float("inf")
    folder = tmp_path / "backups"
    folder.mkdir()
    f = folder / "auto-nightly-20260101-033000.db"
    f.write_bytes(b"")
    os.utime(f, (time.time() - 3600, time.time() - 3600))
    assert 3500 < newest_backup_age(db) < 3700
