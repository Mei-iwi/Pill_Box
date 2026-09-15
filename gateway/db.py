import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .schema import SCHEMA


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def connect(path=None):
    db_path = path or os.getenv("PILLBOX_DB", str(Path(__file__).parent / "data" / "pillbox.db"))
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def init_db(path=None):
    db = connect(path)
    db.executescript(SCHEMA)
    db.commit()
    seed_demo(db)
    db.commit()
    db.close()


def seed_demo(db):
    db.execute("INSERT OR IGNORE INTO devices(device_id, status) VALUES ('PB01', 'offline')")
    db.execute("INSERT OR IGNORE INTO patients(patient_id, display_name) VALUES ('P001', 'Demo patient')")
    for code, label in (("MED001", "Demo medication A"), ("MED002", "Demo medication B"), ("MED003", "Demo medication C")):
        db.execute("INSERT OR IGNORE INTO medication_catalog VALUES (?, ?)", (code, label))
    for slot, code in ((1, "MED001"), (2, "MED002"), (3, "MED003")):
        db.execute("INSERT OR IGNORE INTO slot_assignments VALUES ('PB01', ?, 'P001', ?)", (slot, code))
    for sid, slot, hour in (("S1", 1, 8), ("S2", 2, 14), ("S3", 3, 20)):
        db.execute("INSERT OR IGNORE INTO schedules(schedule_id, device_id, slot_id, hour, minute) VALUES (?, 'PB01', ?, ?, 0)", (sid, slot, hour))


def rows(db, sql, args=()):
    return [dict(row) for row in db.execute(sql, args).fetchall()]
