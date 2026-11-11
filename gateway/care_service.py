"""Care workflows shared by HTTP and MQTT; refill access never confirms a dose."""

import json
from datetime import datetime, timezone

from .db import utc_now


def verification_problem(db, verification, actor_id):
    if not verification:
        return "VERIFICATION_REQUIRED"
    if verification["actor_id"] != actor_id:
        return "ACTOR_MISMATCH"
    if verification["consumed"]:
        return "VERIFICATION_REPLAY"
    if datetime.fromisoformat(verification["expires_at"]) <= datetime.now(timezone.utc):
        return "VERIFICATION_EXPIRED"
    current = db.execute(
        "SELECT * FROM slot_assignments WHERE device_id=? AND slot_id=?",
        (verification["box_id"], verification["slot_id"]),
    ).fetchone()
    device = db.execute(
        "SELECT patient_id FROM devices WHERE device_id=?", (verification["box_id"],)
    ).fetchone()
    if (
        not current
        or not device
        or any(
            (
                device["patient_id"] != verification["patient_id"],
                current["version"] != verification["assignment_version"],
                current["patient_id"] != verification["patient_id"],
                current["medication_code"] != verification["medication_code"],
            )
        )
    ):
        return "STALE_VERIFICATION"
    return None


def apply_refill_ack(db, message, pending):
    payload = json.loads(pending["payload"])
    sid = payload["refill_session_id"]
    session = db.execute(
        "SELECT * FROM refill_sessions WHERE session_id=?", (sid,)
    ).fetchone()
    if (
        not session
        or message.get("refill_session_id") != sid
        or message.get("boot_id") != session["boot_id"]
        or type(message.get("uptime_ms")) is not int
    ):
        if session and pending["command"] == "BEGIN_REFILL":
            db.execute(
                "UPDATE refill_sessions SET status='REJECTED' WHERE session_id=?",
                (sid,),
            )
        return "INVALID_ACK"
    if message["command_result"] != "APPLIED":
        if pending["command"] == "BEGIN_REFILL":
            db.execute(
                "UPDATE refill_sessions SET status='REJECTED' WHERE session_id=?",
                (sid,),
            )
        return "REJECTED"
    if pending["command"] == "END_REFILL":
        db.execute(
            "UPDATE refill_sessions SET status='CLOSED',end_uptime_ms=? WHERE session_id=?",
            (message["uptime_ms"], sid),
        )
        return "APPLIED"
    verification = db.execute(
        "SELECT * FROM refill_verifications WHERE verification_id=?",
        (session["verification_id"],),
    ).fetchone()
    if (
        session["status"] != "PENDING"
        or verification_problem(db, verification, session["actor_id"])
        or datetime.fromisoformat(session["expires_at"]) <= datetime.now(timezone.utc)
    ):
        db.execute(
            "UPDATE refill_sessions SET status='REJECTED' WHERE session_id=?", (sid,)
        )
        return "INVALID_ACK"
    db.execute(
        "UPDATE refill_sessions SET status='ACTIVE',started_uptime_ms=? WHERE session_id=?",
        (message["uptime_ms"], sid),
    )
    return "APPLIED"


def validate_refill_open(db, message):
    session = db.execute(
        "SELECT * FROM refill_sessions WHERE session_id=?",
        (message.get("refill_session_id"),),
    ).fetchone()
    if (
        not session
        or session["status"] not in ("ACTIVE", "CLOSED")
        or session["started_uptime_ms"] is None
        or session["device_id"] != message["device_id"]
        or session["slot_id"] != message["slot_id"]
        or session["boot_id"] != message.get("boot_id")
        or type(message.get("uptime_ms")) is not int
    ):
        raise ValueError("refill access requires a device-acknowledged session")
    elapsed = (message["uptime_ms"] - session["started_uptime_ms"]) & 0xFFFFFFFF
    end = session["end_uptime_ms"]
    if elapsed >= session["duration_seconds"] * 1000 or (
        end is not None
        and elapsed > ((end - session["started_uptime_ms"]) & 0xFFFFFFFF)
    ):
        raise ValueError("refill access outside authorized device interval")
    return session


def resolve_alerts(db, device, kinds, occurrence=None):
    sql = (
        "UPDATE alerts SET status='RESOLVED',resolved_at=?,updated_at=? WHERE device_id=? AND kind IN ("
        + ",".join("?" for _ in kinds)
        + ") AND status!='RESOLVED'"
    )
    args = [utc_now(), utc_now(), device, *kinds]
    if occurrence:
        sql += " AND occurrence_id=?"
        args.append(occurrence)
    db.execute(sql, args)


def update_alerts(db, message):
    kind, did = message["event"], message["device_id"]
    occurrence = message.get("occurrence_id")
    if kind in ("TAKEN_ON_TIME", "TAKEN_LATE") and occurrence:
        resolve_alerts(db, did, ["MISSED"], occurrence)
        return
    if kind == "STORAGE_NORMAL":
        current = db.execute(
            "SELECT last_seq FROM devices WHERE device_id=?", (did,)
        ).fetchone()
        if current["last_seq"] == message["seq"]:
            resolve_alerts(db, did, ["STORAGE_WARNING", "SENSOR_ERROR"])
        return
    if kind not in {
        "MISSED",
        "WRONG_SLOT",
        "UNSCHEDULED_OPEN",
        "AMBIGUOUS_OPEN",
        "STORAGE_WARNING",
        "SENSOR_ERROR",
    }:
        return
    if kind == "MISSED" and occurrence:
        current = db.execute(
            "SELECT current_outcome FROM schedule_occurrences WHERE occurrence_id=?",
            (occurrence,),
        ).fetchone()
        if current and current["current_outcome"] in ("ON_TIME", "LATE"):
            return
    if kind in ("STORAGE_WARNING", "SENSOR_ERROR"):
        current = db.execute(
            "SELECT boot_id,last_seq FROM devices WHERE device_id=?", (did,)
        ).fetchone()
        if current["last_seq"] != message["seq"] or (
            message.get("boot_id") and current["boot_id"] != message["boot_id"]
        ):
            return
    identity = (
        occurrence
        if kind == "MISSED" and occurrence
        else kind
        if kind in ("STORAGE_WARNING", "SENSOR_ERROR")
        else message.get("event_id")
        or f"{message.get('boot_id', 'legacy')}:{message['seq']}"
    )
    key = f"{did}:{kind}:{identity}"
    timestamp = utc_now()
    db.execute(
        """INSERT INTO alerts(alert_key,device_id,kind,severity,slot_id,occurrence_id,source_event_id,created_at,updated_at)
        VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(alert_key) DO UPDATE SET
        updated_at=excluded.updated_at,source_event_id=excluded.source_event_id,
        acknowledged_by=CASE WHEN alerts.status='RESOLVED' THEN NULL ELSE alerts.acknowledged_by END,
        acknowledged_at=CASE WHEN alerts.status='RESOLVED' THEN NULL ELSE alerts.acknowledged_at END,
        resolved_at=CASE WHEN alerts.status='RESOLVED' THEN NULL ELSE alerts.resolved_at END,
        status=CASE WHEN alerts.status='RESOLVED' THEN 'OPEN' ELSE alerts.status END""",
        (
            key,
            did,
            kind,
            "critical"
            if kind in ("MISSED", "WRONG_SLOT", "UNSCHEDULED_OPEN")
            else "warning",
            message["slot_id"],
            occurrence,
            message.get("event_id"),
            timestamp,
            timestamp,
        ),
    )
