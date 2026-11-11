"""Bounded diagnostic APIs applying Labs 4, 7 and 8 to the existing Gateway."""

from datetime import datetime, timedelta, timezone

from flask import g, jsonify, request

from .db import connect, rows
from .mqtt_service import store_message

COMMAND_COLUMNS = "command_id,command,status,created_at,ack_at,CASE WHEN ack_at IS NOT NULL THEN max(0,CAST((julianday(ack_at)-julianday(created_at))*86400000 AS INTEGER)) END ack_latency_ms"


def expire_commands(path):
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat()
    with connect(path) as db:
        db.execute(
            "UPDATE command_requests SET status='TIMEOUT' WHERE status='PENDING' AND created_at<?",
            (cutoff,),
        )
        db.execute(
            "UPDATE refill_sessions SET status='EXPIRED' WHERE status='PENDING' AND command_id IN (SELECT command_id FROM command_requests WHERE status='TIMEOUT')"
        )


def register_lab_routes(app):
    @app.before_request
    def command_deadlines():
        if request.path.startswith("/api/") and request.method == "GET":
            expire_commands(app.config["DB_PATH"])

    @app.get("/api/devices/<device_id>/environment/history")
    def environment_history(device_id):
        try:
            hours = int(request.args.get("hours", 1))
            if hours not in (1, 24):
                raise ValueError()
        except (ValueError, TypeError):
            return jsonify(error="hours must be 1 or 24"), 400
        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        with connect(app.config["DB_PATH"]) as db:
            # Bucket on Gateway receipt time to avoid mixing RTC demo time with real UTC.
            interval = 60 if hours == 1 else 600
            result = rows(
                db,
                """SELECT CAST(strftime('%s',received_at) AS INTEGER)/? bucket,
                min(received_at) received_at,avg(temperature_c) temperature_c,
                avg(humidity_percent) humidity_percent,count(*) samples
                FROM environment_readings WHERE device_id=? AND received_at>=? AND sensor_ok=1
                GROUP BY bucket ORDER BY bucket LIMIT 145""",
                (interval, device_id, since),
            )
        return jsonify(hours=hours, bucket_seconds=interval, items=result)

    @app.post("/api/devices/<device_id>/telemetry")
    def http_telemetry(device_id):
        if not app.config.get("HTTP_INGEST_ENABLED"):
            return jsonify(error="HTTP telemetry testing is disabled"), 404
        if not g.identity or g.identity["role"] != "admin":
            return jsonify(error="admin role required"), 403
        body = request.get_json()
        kind, message = body.get("kind"), body.get("message")
        if kind not in (
            "status",
            "heartbeat",
            "environment",
            "event",
        ) or not isinstance(message, dict):
            return jsonify(error="kind and message object required"), 400
        try:
            store_message(
                f"pillbox/{device_id}/{kind}",
                message,
                app.config["DB_PATH"],
                registered_only=True,
            )
        except (ValueError, TypeError) as exc:
            return jsonify(error=str(exc)), 400
        return jsonify(result="STORED"), 201

    @app.get("/api/notifications")
    def notification_history():
        if not g.identity or g.identity["role"] != "admin":
            return jsonify(error="admin role required"), 403
        with connect(app.config["DB_PATH"]) as db:
            result = rows(
                db, "SELECT * FROM alert_notifications ORDER BY id DESC LIMIT 50"
            )
        return jsonify(
            items=result,
            delivery="outbox; delivery requires explicit SMTP configuration",
        )
