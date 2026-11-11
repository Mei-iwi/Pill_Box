"""Lab 9: confirmed environmental alarms, severity, durable notification transitions."""

from .db import utc_now


def initialize_rules(db):
    db.executescript("""
        CREATE TABLE IF NOT EXISTS alert_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT, alert_id INTEGER NOT NULL,
            device_id TEXT NOT NULL, kind TEXT NOT NULL, severity TEXT NOT NULL,
            transition TEXT NOT NULL, created_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING', attempts INTEGER NOT NULL DEFAULT 0,
            sent_at TEXT, last_error TEXT);
        CREATE TRIGGER IF NOT EXISTS alarm_open_notification AFTER INSERT ON alerts
        BEGIN INSERT INTO alert_notifications(alert_id,device_id,kind,severity,transition,created_at)
        VALUES(NEW.alert_id,NEW.device_id,NEW.kind,NEW.severity,'OPEN',NEW.created_at); END;
        CREATE TRIGGER IF NOT EXISTS alarm_transition_notification AFTER UPDATE ON alerts
        WHEN (OLD.status='RESOLVED' AND NEW.status='OPEN')
          OR (OLD.status!='RESOLVED' AND NEW.status='RESOLVED')
          OR (OLD.severity!='critical' AND NEW.severity='critical' AND NEW.status!='RESOLVED')
        BEGIN INSERT INTO alert_notifications(alert_id,device_id,kind,severity,transition,created_at)
        VALUES(NEW.alert_id,NEW.device_id,NEW.kind,NEW.severity,
          CASE WHEN NEW.status='RESOLVED' THEN 'RECOVERED'
               WHEN OLD.status='RESOLVED' THEN 'OPEN' ELSE 'ESCALATED' END,NEW.updated_at); END;
    """)


def classify_confirmed_environment(db, message):
    if not message["sensor_ok"] or message.get("storage_status") != "WARNING":
        return
    severity = (
        "critical"
        if message["temperature_c"] > 35 or message["humidity_percent"] > 85
        else "warning"
    )
    current = db.execute(
        "SELECT severity FROM alerts WHERE device_id=? AND kind='STORAGE_WARNING' AND status!='RESOLVED'",
        (message["device_id"],),
    ).fetchone()
    if (
        current
        and current["severity"] == "critical"
        and (message["temperature_c"] > 33 or message["humidity_percent"] > 83)
    ):
        severity = "critical"
    db.execute(
        "UPDATE alerts SET severity=?,updated_at=? WHERE device_id=? AND kind='STORAGE_WARNING' AND status!='RESOLVED' AND severity!=?",
        (severity, utc_now(), message["device_id"], severity),
    )
