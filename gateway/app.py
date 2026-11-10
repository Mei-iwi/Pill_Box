import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Flask, g, jsonify, render_template, request

from .auth import actor, configure_auth, scoped
from .db import connect, init_db, rows, utc_now
from .mqtt_service import publish_command, start_mqtt


def availability(device):
    device["reported_status"] = device["status"]
    try:
        seen = datetime.fromisoformat(device["last_seen"])
        fresh = (datetime.now(timezone.utc) - seen).total_seconds() < 65
    except (TypeError, ValueError):
        fresh = False
    if not fresh:
        device["status"] = "offline"
    return device


def list_result(db, table, where, args, order, default_limit=50, columns="*"):
    """Keep legacy arrays; opt-in pagination returns a bounded, counted result."""
    clause = (" WHERE " + where) if where else ""
    if "page" not in request.args and "page_size" not in request.args:
        return jsonify(
            rows(
                db,
                f"SELECT {columns} FROM {table}{clause} ORDER BY {order} LIMIT ?",
                (*args, default_limit),
            )
        )
    try:
        page = int(request.args.get("page", "1"))
        size = int(request.args.get("page_size", "8"))
        if page < 1 or not 1 <= size <= 50:
            raise ValueError
    except ValueError:
        return jsonify(error="invalid pagination"), 400
    total = db.execute(f"SELECT count(*) FROM {table}{clause}", args).fetchone()[0]
    pages = max(1, (total + size - 1) // size)
    page = min(page, pages)
    items = rows(
        db,
        f"SELECT {columns} FROM {table}{clause} ORDER BY {order} LIMIT ? OFFSET ?",
        (*args, size, (page - 1) * size),
    )
    return jsonify(items=items, total=total, page=page, page_size=size, pages=pages)


def create_app(test_config=None):
    app = Flask(__name__, template_folder="templates", static_folder="static")
    db_path = (test_config or {}).get(
        "DB_PATH",
        os.getenv("PILLBOX_DB", str(Path(__file__).parent / "data" / "pillbox.db")),
    )
    app.config.update(DB_PATH=db_path)
    app.config["MQTT_CLIENT"] = (test_config or {}).get("MQTT_CLIENT")
    init_db(db_path)
    configure_auth(app, test_config)

    @app.before_request
    def json_object():
        if request.method == "POST" and not isinstance(
            request.get_json(silent=True), dict
        ):
            return jsonify(error="JSON object required"), 400

    @app.get("/api/session")
    def session_info():
        return jsonify(
            identity=g.identity, auth_enabled=app.config["AUTH_IDENTITIES"] is not None
        )

    @app.get("/")
    def dashboard():
        return render_template("dashboard.html")

    @app.get("/api/devices")
    def devices():
        db = connect(app.config["DB_PATH"])
        result = rows(
            db,
            "SELECT d.*,p.display_name patient_name,(SELECT event FROM medication_events e WHERE e.device_id=d.device_id AND e.event IN ('STORAGE_WARNING','STORAGE_NORMAL') ORDER BY e.id DESC LIMIT 1) storage_status FROM devices d LEFT JOIN patients p ON p.patient_id=d.patient_id ORDER BY d.device_id",
        )
        db.close()
        return jsonify([availability(d) for d in scoped(result, "device_id")])

    @app.get("/api/devices/<device_id>/status")
    def status(device_id):
        db = connect(app.config["DB_PATH"])
        result = rows(db, "SELECT * FROM devices WHERE device_id=?", (device_id,))
        db.close()
        return (
            jsonify(availability(result[0]))
            if result
            else (jsonify({"error": "device not found"}), 404)
        )

    @app.get("/api/devices/<device_id>/events")
    def events(device_id):
        with connect(app.config["DB_PATH"]) as db:
            return list_result(
                db, "medication_events", "device_id=?", (device_id,), "id DESC"
            )

    @app.get("/api/devices/<device_id>/environment")
    def environment(device_id):
        db = connect(app.config["DB_PATH"])
        result = rows(
            db,
            "SELECT * FROM environment_readings WHERE device_id=? ORDER BY id DESC LIMIT 20",
            (device_id,),
        )
        db.close()
        return jsonify(result)

    @app.get("/api/devices/<device_id>/schedules")
    def schedules(device_id):
        db = connect(app.config["DB_PATH"])
        result = rows(
            db,
            "SELECT s.*,m.label medication_name FROM schedules s LEFT JOIN medication_catalog m ON m.medication_code=s.medication_code WHERE s.device_id=? ORDER BY s.hour,s.minute,s.schedule_id",
            (device_id,),
        )
        db.close()
        return jsonify(result)

    @app.get("/api/devices/<device_id>/occurrences")
    def occurrences(device_id):
        with connect(app.config["DB_PATH"]) as db:
            return list_result(
                db,
                "schedule_occurrences",
                "device_id=?",
                (device_id,),
                "scheduled_at DESC,occurrence_id DESC",
            )

    @app.get("/api/devices/<device_id>/slots")
    def slots(device_id):
        with connect(app.config["DB_PATH"]) as db:
            result = rows(
                db,
                "SELECT a.*,m.label medication_name FROM slot_assignments a LEFT JOIN medication_catalog m ON m.medication_code=a.medication_code WHERE a.device_id=? ORDER BY a.slot_id",
                (device_id,),
            )
        return jsonify(result)

    @app.post("/api/devices/<device_id>/commands")
    def commands(device_id):
        body = request.get_json(silent=True) or {}
        command = body.get("command")
        if not isinstance(command, str) or command not in {
            "CLEAR_ALERT",
            "REQUEST_STATUS",
            "UPDATE_SCHEDULE",
        }:
            return jsonify({"error": "unsupported command"}), 400
        db = connect(app.config["DB_PATH"])
        exists = db.execute(
            "SELECT 1 FROM devices WHERE device_id=?", (device_id,)
        ).fetchone()
        db.close()
        if not exists:
            return jsonify({"error": "device not found"}), 404
        normalized = {"command": command}
        if command == "UPDATE_SCHEDULE":
            if (
                not isinstance(body.get("schedule_id"), str)
                or type(body.get("hour")) is not int
                or not 0 <= body["hour"] <= 23
                or type(body.get("minute")) is not int
                or not 0 <= body["minute"] <= 59
                or not isinstance(body.get("enabled"), bool)
            ):
                return jsonify({"error": "invalid schedule command"}), 400
            with connect(app.config["DB_PATH"]) as db:
                if not db.execute(
                    "SELECT 1 FROM schedules WHERE device_id=? AND schedule_id=?",
                    (device_id, body["schedule_id"]),
                ).fetchone():
                    return jsonify({"error": "schedule not assigned to device"}), 400
            normalized.update(
                schedule_id=body["schedule_id"],
                hour=body["hour"],
                minute=body["minute"],
                enabled=body["enabled"],
            )
        command_id = secrets.token_hex(16)
        normalized["command_id"] = command_id
        with connect(app.config["DB_PATH"]) as db:
            db.execute(
                "INSERT INTO command_requests(command_id,device_id,command,payload,created_at) VALUES (?,?,?,?,?)",
                (command_id, device_id, command, json.dumps(normalized), utc_now()),
            )
        if not publish_command(app.config.get("MQTT_CLIENT"), device_id, normalized):
            with connect(app.config["DB_PATH"]) as db:
                db.execute(
                    "UPDATE command_requests SET status='PUBLISH_FAILED' WHERE command_id=?",
                    (command_id,),
                )
            return jsonify({"error": "MQTT broker unavailable"}), 503
        return jsonify(
            {
                "device_id": device_id,
                "published": True,
                "command": normalized,
                "command_id": command_id,
                "status": "PENDING_DEVICE_ACK",
            }
        ), 202

    @app.get("/api/devices/<device_id>/commands")
    def command_history(device_id):
        with connect(app.config["DB_PATH"]) as db:
            return list_result(
                db,
                "command_requests",
                "device_id=?",
                (device_id,),
                "created_at DESC,command_id DESC",
                10,
                "command_id,command,status,created_at,ack_at",
            )

    @app.post("/api/refill/verify")
    def refill_verify():
        body = request.get_json(silent=True) or {}
        body["actor_id"] = actor(body)
        required = ("actor_id", "box_id", "patient_id", "medication_code")
        if (
            any(
                not isinstance(body.get(key), str) or not 1 <= len(body[key]) <= 120
                for key in required
            )
            or type(body.get("slot_id")) is not int
            or not 1 <= body["slot_id"] <= 3
        ):
            return jsonify({"error": "invalid refill payload"}), 400
        db = connect(app.config["DB_PATH"])
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            "UPDATE refill_verifications SET consumed=1 WHERE actor_id=? AND box_id=? AND slot_id=? AND consumed=0",
            (body["actor_id"], body["box_id"], body["slot_id"]),
        )
        expected = db.execute(
            "SELECT patient_id, medication_code,version FROM slot_assignments WHERE device_id=? AND slot_id=?",
            (body["box_id"], body["slot_id"]),
        ).fetchone()
        device = db.execute(
            "SELECT patient_id FROM devices WHERE device_id=?", (body["box_id"],)
        ).fetchone()
        result = (
            "UNKNOWN_BOX_OR_SLOT"
            if not expected
            else "PATIENT_BOX_MISMATCH"
            if not device
            or device["patient_id"] != body["patient_id"]
            or expected["patient_id"] != body["patient_id"]
            else "MEDICATION_MISMATCH"
            if body["medication_code"] != expected["medication_code"]
            else "VERIFIED"
        )
        db.execute(
            """INSERT INTO refill_audit_logs(actor_id, box_id, patient_id, slot_id, expected_medication_code,
                     scanned_medication_code, result, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                body["actor_id"],
                body["box_id"],
                body["patient_id"],
                body["slot_id"],
                expected["medication_code"] if expected else None,
                body["medication_code"],
                result,
                utc_now(),
            ),
        )
        response = {"result": result}
        if result == "VERIFIED":
            token = secrets.token_urlsafe(32)
            expiry = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
            db.execute(
                "INSERT INTO refill_verifications VALUES (?,?,?,?,?,?,?,?,0)",
                (
                    token,
                    body["actor_id"],
                    body["box_id"],
                    body["patient_id"],
                    body["slot_id"],
                    body["medication_code"],
                    expected["version"],
                    expiry,
                ),
            )
            response.update(verification_id=token, expires_at=expiry)
        db.commit()
        db.close()
        return jsonify(response)

    @app.post("/api/refill/confirm")
    def refill_confirm():
        body = request.get_json(silent=True) or {}
        body["actor_id"] = actor(body)
        if not isinstance(body.get("actor_id"), str) or not isinstance(
            body.get("verification_id"), str
        ):
            return jsonify({"error": "invalid confirm payload"}), 400
        db = connect(app.config["DB_PATH"])
        db.execute("BEGIN IMMEDIATE")
        verification = db.execute(
            "SELECT * FROM refill_verifications WHERE verification_id=?",
            (body["verification_id"],),
        ).fetchone()
        if not verification:
            db.close()
            return jsonify({"error": "valid verification required before confirm"}), 409
        current = db.execute(
            "SELECT * FROM slot_assignments WHERE device_id=? AND slot_id=?",
            (verification["box_id"], verification["slot_id"]),
        ).fetchone()
        device = db.execute(
            "SELECT patient_id FROM devices WHERE device_id=?",
            (verification["box_id"],),
        ).fetchone()
        result = "CONFIRMED"
        if verification["actor_id"] != body["actor_id"]:
            result = "ACTOR_MISMATCH"
        elif verification["consumed"]:
            result = "VERIFICATION_REPLAY"
        elif datetime.fromisoformat(verification["expires_at"]) <= datetime.now(
            timezone.utc
        ):
            result = "VERIFICATION_EXPIRED"
        elif (
            not current
            or not device
            or device["patient_id"] != verification["patient_id"]
            or current["version"] != verification["assignment_version"]
            or current["medication_code"] != verification["medication_code"]
            or current["patient_id"] != verification["patient_id"]
        ):
            result = "STALE_VERIFICATION"
        if result == "CONFIRMED":
            db.execute(
                "UPDATE refill_verifications SET consumed=1 WHERE verification_id=?",
                (body["verification_id"],),
            )
        audit = db.execute(
            """INSERT INTO refill_audit_logs(actor_id,box_id,patient_id,slot_id,expected_medication_code,scanned_medication_code,result,timestamp,confirmed)
                VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                body["actor_id"],
                verification["box_id"],
                verification["patient_id"],
                verification["slot_id"],
                current["medication_code"] if current else None,
                verification["medication_code"],
                result,
                utc_now(),
                int(result == "CONFIRMED"),
            ),
        )
        db.commit()
        db.close()
        return jsonify({"result": result, "audit_id": audit.lastrowid}), (
            200 if result == "CONFIRMED" else 409
        )

    @app.get("/api/refill/audit")
    def refill_audit():
        filters = []
        args = []
        device = request.args.get("device_id")
        if g.identity and g.identity["role"] != "admin":
            allowed = g.identity["devices"]
            if device and device not in allowed:
                return jsonify(error="device not assigned to identity"), 403
            if not allowed:
                filters.append("0=1")
            else:
                filters.append("box_id IN (" + ",".join("?" for _ in allowed) + ")")
                args.extend(allowed)
        if device:
            filters.append("box_id=?")
            args.append(device)
        with connect(app.config["DB_PATH"]) as db:
            return list_result(
                db, "refill_audit_logs", " AND ".join(filters), tuple(args), "id DESC"
            )

    if os.getenv("PILLBOX_MQTT_AUTOSTART", "0") == "1":
        app.config["MQTT_CLIENT"] = start_mqtt(
            db_path,
            os.getenv("MQTT_HOST", "localhost"),
            int(os.getenv("MQTT_PORT", "1883")),
        )
        app.extensions["mqtt"] = app.config["MQTT_CLIENT"]
    return app


if __name__ == "__main__":
    app = create_app()
    app.run(
        host=os.getenv("PILLBOX_BIND", "127.0.0.1"),
        port=int(os.getenv("PORT", "5000")),
        debug=False,
    )
