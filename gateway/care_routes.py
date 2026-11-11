"""Authorized refill windows and the central care alert queue."""

import json
import secrets
from datetime import datetime, timezone

from flask import g, jsonify, request

from .auth import actor
from .care_service import verification_problem
from .db import connect, utc_now
from .mqtt_service import publish_command


def alert_filter(device_id=None, unresolved=True):
    clauses, args = [], []
    if unresolved:
        clauses.append("status!='RESOLVED'")
    if device_id:
        clauses.append("device_id=?")
        args.append(device_id)
    if g.identity and g.identity["role"] != "admin":
        devices = g.identity["devices"]
        clauses.append(
            "device_id IN (" + ",".join("?" for _ in devices) + ")"
            if devices
            else "0=1"
        )
        args.extend(devices)
    return " AND ".join(clauses) or "1=1", tuple(args)


def send_saved_command(config, device_id, command):
    with connect(config["DB_PATH"]) as db:
        db.execute(
            "INSERT INTO command_requests(command_id,device_id,command,payload,created_at) VALUES (?,?,?,?,?)",
            (
                command["command_id"],
                device_id,
                command["command"],
                json.dumps(command),
                utc_now(),
            ),
        )
    if publish_command(config.get("MQTT_CLIENT"), device_id, command):
        return True
    with connect(config["DB_PATH"]) as db:
        db.execute(
            "UPDATE command_requests SET status='PUBLISH_FAILED' WHERE command_id=?",
            (command["command_id"],),
        )
    return False


def close_refill_session(config, verification_id):
    with connect(config["DB_PATH"]) as db:
        session = db.execute(
            "SELECT * FROM refill_sessions WHERE verification_id=?", (verification_id,)
        ).fetchone()
        if not session or session["end_uptime_ms"] is not None:
            return None
        db.execute(
            "UPDATE refill_sessions SET status='CLOSED' WHERE session_id=?",
            (session["session_id"],),
        )
    command = {
        "command": "END_REFILL",
        "command_id": secrets.token_hex(16),
        "refill_session_id": session["session_id"],
    }
    published = send_saved_command(config, session["device_id"], command)
    return {
        "command_id": command["command_id"],
        "status": "PENDING" if published else "PUBLISH_FAILED",
    }


def register_care_routes(app, page_data):
    @app.post("/api/refill/authorize")
    def authorize_refill():
        body = request.get_json() or {}
        vid, who = body.get("verification_id"), actor(body)
        if not isinstance(vid, str) or not isinstance(who, str):
            return jsonify(error="verification and actor required"), 400
        with connect(app.config["DB_PATH"]) as db:
            db.execute("BEGIN IMMEDIATE")
            verification = db.execute(
                "SELECT * FROM refill_verifications WHERE verification_id=?", (vid,)
            ).fetchone()
            problem = verification_problem(db, verification, who)
            if problem:
                return jsonify(result=problem), 409
            device = db.execute(
                "SELECT * FROM devices WHERE device_id=?", (verification["box_id"],)
            ).fetchone()
            now = datetime.now(timezone.utc)
            try:
                recent = (
                    now - datetime.fromisoformat(device["last_seen"])
                ).total_seconds() < 65
            except (TypeError, ValueError):
                recent = False
            if not recent or device["status"] != "online" or not device["boot_id"]:
                return jsonify(error="device must be online before refill"), 409
            if not device["utc_synced"]:
                return jsonify(error="device must synchronize UTC before refill"), 409
            if db.execute(
                "SELECT 1 FROM refill_sessions WHERE verification_id=? OR (device_id=? AND status IN ('PENDING','ACTIVE') AND expires_at>?)",
                (vid, verification["box_id"], now.isoformat()),
            ).fetchone():
                return jsonify(error="refill session already exists"), 409
            expiry_epoch = int(
                datetime.fromisoformat(verification["expires_at"]).timestamp()
            )
            duration = expiry_epoch - int(now.timestamp())
            if duration < 1:
                return jsonify(result="VERIFICATION_EXPIRED"), 409
            sid, cid = secrets.token_hex(16), secrets.token_hex(16)
            command = {
                "command": "BEGIN_REFILL",
                "command_id": cid,
                "refill_session_id": sid,
                "slot_id": verification["slot_id"],
                "expires_epoch_utc": expiry_epoch,
            }
            db.execute(
                """INSERT INTO refill_sessions(session_id,verification_id,device_id,slot_id,actor_id,boot_id,command_id,created_at,expires_at,duration_seconds)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    sid,
                    vid,
                    verification["box_id"],
                    verification["slot_id"],
                    who,
                    device["boot_id"],
                    cid,
                    now.isoformat(),
                    datetime.fromtimestamp(expiry_epoch, timezone.utc).isoformat(),
                    min(duration, 300),
                ),
            )
        if not send_saved_command(app.config, verification["box_id"], command):
            with connect(app.config["DB_PATH"]) as db:
                db.execute(
                    "UPDATE refill_sessions SET status='REJECTED' WHERE session_id=?",
                    (sid,),
                )
            return jsonify(error="MQTT broker unavailable"), 503
        return jsonify(
            session_id=sid,
            command_id=cid,
            status="PENDING",
            expires_at=datetime.fromtimestamp(expiry_epoch, timezone.utc).isoformat(),
        ), 202

    @app.post("/api/refill/end")
    def end_refill():
        body = request.get_json() or {}
        vid, who = body.get("verification_id"), actor(body)
        if not isinstance(vid, str) or not isinstance(who, str):
            return jsonify(error="verification and actor required"), 400
        with connect(app.config["DB_PATH"]) as db:
            session = db.execute(
                "SELECT actor_id FROM refill_sessions WHERE verification_id=?", (vid,)
            ).fetchone()
            if not session or session["actor_id"] != who:
                return jsonify(error="refill session not assigned to actor"), 403
        result = close_refill_session(app.config, vid)
        return jsonify(result=result), 202

    @app.get("/api/alerts")
    def alerts():
        where, args = alert_filter(
            request.args.get("device_id"), request.args.get("history") != "1"
        )
        try:
            with connect(app.config["DB_PATH"]) as db:
                result = page_data(
                    db,
                    "alerts",
                    where,
                    args,
                    "alert_id DESC",
                    request.args.get("page", 1),
                    request.args.get("page_size", 8),
                )
            return jsonify(result)
        except (ValueError, TypeError):
            return jsonify(error="invalid pagination"), 400

    @app.post("/api/alerts/<int:alert_id>/ack")
    def acknowledge_alert(alert_id):
        if g.identity and g.identity["role"] not in ("nurse", "admin"):
            return jsonify(error="caregiver role required"), 403
        body = request.get_json() or {}
        who = actor(body)
        action = body.get("action", "acknowledge")
        if (
            not isinstance(who, str)
            or not 1 <= len(who) <= 120
            or action not in ("acknowledge", "resolve")
        ):
            return jsonify(error="invalid alert action"), 400
        with connect(app.config["DB_PATH"]) as db:
            where, args = alert_filter(unresolved=False)
            alert = db.execute(
                "SELECT * FROM alerts WHERE alert_id=? AND " + where, (alert_id, *args)
            ).fetchone()
            if not alert:
                return jsonify(error="alert not found"), 404
            if action == "resolve" and alert["kind"] not in (
                "WRONG_SLOT",
                "UNSCHEDULED_OPEN",
                "AMBIGUOUS_OPEN",
            ):
                return jsonify(
                    error="condition must recover before resolving alert"
                ), 409
            if alert["status"] != "RESOLVED":
                db.execute(
                    "UPDATE alerts SET status=?,acknowledged_by=?,acknowledged_at=?,updated_at=?,resolved_at=? WHERE alert_id=?",
                    (
                        "RESOLVED" if action == "resolve" else "ACKNOWLEDGED",
                        who,
                        utc_now(),
                        utc_now(),
                        utc_now() if action == "resolve" else None,
                        alert_id,
                    ),
                )
        return jsonify(status="RESOLVED" if action == "resolve" else "ACKNOWLEDGED")
