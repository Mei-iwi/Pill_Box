import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .schema import SCHEMA


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def connect(path=None):
    db_path = path or os.getenv(
        "PILLBOX_DB", str(Path(__file__).parent / "data" / "pillbox.db")
    )
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path, factory=ClosingConnection)
    connection.row_factory = sqlite3.Row
    return connection


def init_db(path=None):
    db = connect(path)
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript(SCHEMA)
    migrate(db)
    db.commit()
    seed_defaults(db)
    db.commit()
    db.close()


def seed_defaults(db):
    for device, patient in (("PB01", "P001"), ("PB02", "P002")):
        db.execute(
            "INSERT OR IGNORE INTO devices(device_id, patient_id) VALUES (?, ?)",
            (device, patient),
        )
        db.execute(
            "UPDATE devices SET patient_id=? WHERE device_id=? AND patient_id IS NULL",
            (patient, device),
        )
        db.execute(
            "INSERT OR IGNORE INTO patients VALUES (?, ?)",
            (patient, "Hồ sơ " + patient.removeprefix("P").lstrip("0").zfill(2)),
        )
    for code, label in (
        ("MED001", "Vitamin C"),
        ("MED002", "Vitamin D3"),
        ("MED003", "Canxi"),
        ("MED004", "Vitamin B12"),
    ):
        db.execute(
            "INSERT OR IGNORE INTO medication_catalog VALUES (?, ?)", (code, label)
        )
    for slot, code in ((1, "MED001"), (2, "MED002"), (3, "MED003")):
        db.execute(
            "INSERT OR IGNORE INTO slot_assignments(device_id,slot_id,patient_id,medication_code) VALUES ('PB01', ?, 'P001', ?)",
            (slot, code),
        )
    db.execute(
        "INSERT OR IGNORE INTO slot_assignments(device_id,slot_id,patient_id,medication_code) VALUES ('PB02',1,'P002','MED004')"
    )
    for sid, device, slot, med, hour, minute in (
        ("S1", "PB01", 1, "MED001", 8, 0),
        ("S2", "PB01", 1, "MED001", 14, 0),
        ("S3", "PB01", 2, "MED002", 9, 0),
        ("S4", "PB01", 3, "MED003", 20, 0),
        ("S5", "PB02", 1, "MED004", 7, 30),
    ):
        db.execute(
            "INSERT OR IGNORE INTO schedules(schedule_id,device_id,slot_id,medication_code,hour,minute,on_time_window_minutes,late_tracking_window_minutes) VALUES (?,?,?,?,?,?,15,240)",
            (sid, device, slot, med, hour, minute),
        )
    db.execute("""UPDATE schedules SET medication_code=(SELECT medication_code FROM slot_assignments a
                  WHERE a.device_id=schedules.device_id AND a.slot_id=schedules.slot_id) WHERE medication_code IS NULL""")


def migrate(db):
    """Additive migration; retain existing schedules and all historical events."""
    additions = {
        "devices": {
            "patient_id": "TEXT",
            "boot_id": "TEXT",
            "queue_depth": "INTEGER DEFAULT 0",
            "queue_dropped": "INTEGER DEFAULT 0",
            "storage_status": "TEXT",
            "device_uptime_ms": "INTEGER",
            "device_local_minute": "INTEGER",
            "device_epoch_local": "INTEGER",
            "utc_synced": "INTEGER NOT NULL DEFAULT 0",
        },
        "schedules": {"medication_code": "TEXT"},
        "slot_assignments": {"version": "INTEGER NOT NULL DEFAULT 1"},
        "environment_readings": {
            "sampled_at": "TEXT",
            "boot_id": "TEXT",
            "seq": "INTEGER",
            "storage_status": "TEXT",
        },
    }
    for table, columns in additions.items():
        existing = {r[1] for r in db.execute(f"PRAGMA table_info({table})")}
        for column, declaration in columns.items():
            if column not in existing:
                db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")
    if "event_id" not in {
        r[1] for r in db.execute("PRAGMA table_info(medication_events)")
    }:
        if not db.in_transaction:
            db.execute("BEGIN IMMEDIATE")
        db.execute("ALTER TABLE medication_events RENAME TO medication_events_legacy")
        db.execute("""CREATE TABLE medication_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,device_id TEXT NOT NULL,seq INTEGER NOT NULL,
            event TEXT NOT NULL,slot_id INTEGER NOT NULL,schedule_id TEXT,scheduled_minute INTEGER,
            occurred_minute INTEGER,delay_minutes INTEGER,received_at TEXT NOT NULL,
            event_id TEXT UNIQUE,boot_id TEXT NOT NULL DEFAULT 'legacy',occurrence_id TEXT,
            schema_version INTEGER DEFAULT 1,scheduled_at TEXT,occurred_at TEXT,device_time_quality TEXT,
            UNIQUE(device_id,boot_id,seq))""")
        db.execute("""INSERT INTO medication_events(id,device_id,seq,event,slot_id,schedule_id,scheduled_minute,occurred_minute,delay_minutes,received_at)
            SELECT id,device_id,seq,event,slot_id,schedule_id,scheduled_minute,occurred_minute,delay_minutes,received_at FROM medication_events_legacy""")
        # Keep the original table as a migration backup.
    db.executescript("""
        CREATE INDEX IF NOT EXISTS event_device_time ON medication_events(device_id,received_at);
        CREATE INDEX IF NOT EXISTS environment_device_boot_seq ON environment_readings(device_id,boot_id,seq);
        CREATE TABLE IF NOT EXISTS command_requests (
            command_id TEXT PRIMARY KEY,device_id TEXT NOT NULL,command TEXT NOT NULL,payload TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING',created_at TEXT NOT NULL,ack_at TEXT);
        CREATE TABLE IF NOT EXISTS schedule_occurrences (
            occurrence_id TEXT PRIMARY KEY,device_id TEXT NOT NULL,schedule_id TEXT NOT NULL,slot_id INTEGER NOT NULL,
            scheduled_at TEXT,current_outcome TEXT NOT NULL,confirmed_at TEXT,delay_minutes INTEGER DEFAULT 0,
            last_event_at TEXT);
        CREATE TABLE IF NOT EXISTS refill_verifications (
            verification_id TEXT PRIMARY KEY,actor_id TEXT NOT NULL,box_id TEXT NOT NULL,patient_id TEXT NOT NULL,
            slot_id INTEGER NOT NULL,medication_code TEXT NOT NULL,assignment_version INTEGER NOT NULL,
            expires_at TEXT NOT NULL,consumed INTEGER NOT NULL DEFAULT 0);
        CREATE TRIGGER IF NOT EXISTS assignment_version_update AFTER UPDATE OF medication_code,patient_id ON slot_assignments
        BEGIN UPDATE slot_assignments SET version=OLD.version+1 WHERE device_id=NEW.device_id AND slot_id=NEW.slot_id; END;
        CREATE TABLE IF NOT EXISTS refill_sessions (
            session_id TEXT PRIMARY KEY,verification_id TEXT UNIQUE NOT NULL,
            device_id TEXT NOT NULL,slot_id INTEGER NOT NULL,actor_id TEXT NOT NULL,
            boot_id TEXT NOT NULL,command_id TEXT UNIQUE NOT NULL,status TEXT NOT NULL DEFAULT 'PENDING',
            created_at TEXT NOT NULL,expires_at TEXT NOT NULL,duration_seconds INTEGER NOT NULL,
            started_uptime_ms INTEGER,end_uptime_ms INTEGER,opened_count INTEGER NOT NULL DEFAULT 0,
            last_opened_at TEXT);
        CREATE INDEX IF NOT EXISTS refill_session_device ON refill_sessions(device_id,status);
        CREATE TABLE IF NOT EXISTS alerts (
            alert_id INTEGER PRIMARY KEY AUTOINCREMENT,alert_key TEXT UNIQUE NOT NULL,
            device_id TEXT NOT NULL,kind TEXT NOT NULL,severity TEXT NOT NULL,
            slot_id INTEGER NOT NULL DEFAULT 0,occurrence_id TEXT,source_event_id TEXT,
            status TEXT NOT NULL DEFAULT 'OPEN',created_at TEXT NOT NULL,updated_at TEXT NOT NULL,
            acknowledged_by TEXT,acknowledged_at TEXT,resolved_at TEXT);
        CREATE INDEX IF NOT EXISTS alert_device_status ON alerts(device_id,status,alert_id);
    """)
    if "refill_session_id" not in {
        r[1] for r in db.execute("PRAGMA table_info(medication_events)")
    }:
        db.execute("ALTER TABLE medication_events ADD COLUMN refill_session_id TEXT")


def rows(db, sql, args=()):
    return [dict(row) for row in db.execute(sql, args).fetchall()]
