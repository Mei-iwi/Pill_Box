SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
    device_id TEXT PRIMARY KEY, status TEXT NOT NULL DEFAULT 'offline', state TEXT,
    last_seen TEXT, last_seq INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS patients (patient_id TEXT PRIMARY KEY, display_name TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS schedules (
    schedule_id TEXT PRIMARY KEY, device_id TEXT NOT NULL, slot_id INTEGER NOT NULL,
    hour INTEGER NOT NULL, minute INTEGER NOT NULL, enabled INTEGER NOT NULL DEFAULT 1,
    on_time_window_minutes INTEGER NOT NULL DEFAULT 5,
    late_tracking_window_minutes INTEGER NOT NULL DEFAULT 120
);
CREATE TABLE IF NOT EXISTS medication_catalog (medication_code TEXT PRIMARY KEY, label TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS slot_assignments (
    device_id TEXT NOT NULL, slot_id INTEGER NOT NULL, patient_id TEXT NOT NULL,
    medication_code TEXT NOT NULL, PRIMARY KEY (device_id, slot_id)
);
CREATE TABLE IF NOT EXISTS medication_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, device_id TEXT NOT NULL, seq INTEGER NOT NULL,
    event TEXT NOT NULL, slot_id INTEGER NOT NULL, schedule_id TEXT, scheduled_minute INTEGER,
    occurred_minute INTEGER, delay_minutes INTEGER, received_at TEXT NOT NULL,
    UNIQUE(device_id, seq)
);
CREATE TABLE IF NOT EXISTS environment_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT, device_id TEXT NOT NULL, temperature_c REAL,
    humidity_percent REAL, sensor_ok INTEGER NOT NULL, received_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS refill_audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT, actor_id TEXT NOT NULL, box_id TEXT NOT NULL,
    patient_id TEXT NOT NULL, slot_id INTEGER NOT NULL, expected_medication_code TEXT,
    scanned_medication_code TEXT NOT NULL, result TEXT NOT NULL, timestamp TEXT NOT NULL,
    confirmed INTEGER NOT NULL DEFAULT 0
);
"""
