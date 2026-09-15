import os
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from .db import connect, init_db, rows, utc_now
from .mqtt_service import publish_command, start_mqtt


def create_app(test_config=None):
    app = Flask(__name__, template_folder="templates", static_folder="static")
    db_path = (test_config or {}).get("DB_PATH", os.getenv("PILLBOX_DB", str(Path(__file__).parent / "data" / "pillbox.db")))
    app.config.update(DB_PATH=db_path)
    app.config["MQTT_CLIENT"] = (test_config or {}).get("MQTT_CLIENT")
    init_db(db_path)

    @app.get("/")
    def dashboard():
        return render_template("dashboard.html")

    @app.get("/api/devices")
    def devices():
        db = connect(app.config["DB_PATH"]); result = rows(db, "SELECT * FROM devices ORDER BY device_id"); db.close(); return jsonify(result)

    @app.get("/api/devices/<device_id>/status")
    def status(device_id):
        db = connect(app.config["DB_PATH"]); result = rows(db, "SELECT * FROM devices WHERE device_id=?", (device_id,)); db.close()
        return (jsonify(result[0]) if result else (jsonify({"error": "device not found"}), 404))

    @app.get("/api/devices/<device_id>/events")
    def events(device_id):
        db = connect(app.config["DB_PATH"]); result = rows(db, "SELECT * FROM medication_events WHERE device_id=? ORDER BY id DESC LIMIT 50", (device_id,)); db.close(); return jsonify(result)

    @app.get("/api/devices/<device_id>/environment")
    def environment(device_id):
        db = connect(app.config["DB_PATH"]); result = rows(db, "SELECT * FROM environment_readings WHERE device_id=? ORDER BY id DESC LIMIT 20", (device_id,)); db.close(); return jsonify(result)

    @app.get("/api/devices/<device_id>/schedules")
    def schedules(device_id):
        db = connect(app.config["DB_PATH"]); result = rows(db, "SELECT * FROM schedules WHERE device_id=? ORDER BY slot_id", (device_id,)); db.close(); return jsonify(result)

    @app.post("/api/devices/<device_id>/commands")
    def commands(device_id):
        body = request.get_json(silent=True) or {}
        command = body.get("command")
        if command not in {"CLEAR_ALERT", "REQUEST_STATUS", "UPDATE_SCHEDULE"}:
            return jsonify({"error": "unsupported command"}), 400
        db = connect(app.config["DB_PATH"])
        exists = db.execute("SELECT 1 FROM devices WHERE device_id=?", (device_id,)).fetchone()
        db.close()
        if not exists:
            return jsonify({"error": "device not found"}), 404
        normalized = {"command": command}
        if command == "UPDATE_SCHEDULE":
            if (not isinstance(body.get("slot_id"), int) or not 1 <= body["slot_id"] <= 3 or
                    not isinstance(body.get("hour"), int) or not 0 <= body["hour"] <= 23 or
                    not isinstance(body.get("minute"), int) or not 0 <= body["minute"] <= 59 or
                    not isinstance(body.get("enabled"), bool)):
                return jsonify({"error": "invalid schedule command"}), 400
            normalized.update(slot_id=body["slot_id"], hour=body["hour"], minute=body["minute"], enabled=body["enabled"])
        if not publish_command(app.config.get("MQTT_CLIENT"), device_id, normalized):
            return jsonify({"error": "MQTT broker unavailable"}), 503
        return jsonify({"device_id": device_id, "published": True, "command": normalized}), 202

    @app.post("/api/refill/verify")
    def refill_verify():
        body = request.get_json(silent=True) or {}
        required = ("actor_id", "box_id", "slot_id", "medication_code")
        if any(not body.get(key) for key in required) or not isinstance(body.get("slot_id"), int):
            return jsonify({"error": "invalid refill payload"}), 400
        db = connect(app.config["DB_PATH"])
        expected = db.execute("SELECT patient_id, medication_code FROM slot_assignments WHERE device_id=? AND slot_id=?", (body["box_id"], body["slot_id"])).fetchone()
        if not expected:
            db.close(); return jsonify({"error": "unknown box or slot"}), 404
        result = "VERIFIED" if body["medication_code"] == expected["medication_code"] else "MEDICATION_MISMATCH"
        db.execute("""INSERT INTO refill_audit_logs(actor_id, box_id, patient_id, slot_id, expected_medication_code,
                     scanned_medication_code, result, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                   (body["actor_id"], body["box_id"], expected["patient_id"], body["slot_id"], expected["medication_code"], body["medication_code"], result, utc_now()))
        db.commit(); db.close()
        response = {"result": result}
        if result != "VERIFIED": response["expected_code"] = expected["medication_code"]
        return jsonify(response)

    @app.post("/api/refill/confirm")
    def refill_confirm():
        body = request.get_json(silent=True) or {}
        if not body.get("actor_id") or not body.get("box_id") or not isinstance(body.get("slot_id"), int):
            return jsonify({"error": "invalid confirm payload"}), 400
        db = connect(app.config["DB_PATH"])
        audit = db.execute("""SELECT id FROM refill_audit_logs WHERE actor_id=? AND box_id=? AND slot_id=?
                              AND result='VERIFIED' AND confirmed=0 ORDER BY id DESC LIMIT 1""",
                          (body["actor_id"], body["box_id"], body["slot_id"])).fetchone()
        if not audit:
            db.close(); return jsonify({"error": "valid verification required before confirm"}), 409
        db.execute("UPDATE refill_audit_logs SET confirmed=1 WHERE id=?", (audit["id"],)); db.commit(); db.close()
        return jsonify({"result": "CONFIRMED", "audit_id": audit["id"]})

    @app.get("/api/refill/audit")
    def refill_audit():
        db = connect(app.config["DB_PATH"]); result = rows(db, "SELECT * FROM refill_audit_logs ORDER BY id DESC LIMIT 50"); db.close(); return jsonify(result)

    if os.getenv("PILLBOX_MQTT_AUTOSTART", "0") == "1":
        app.config["MQTT_CLIENT"] = start_mqtt(db_path, os.getenv("MQTT_HOST", "localhost"), int(os.getenv("MQTT_PORT", "1883")))
        app.extensions["mqtt"] = app.config["MQTT_CLIENT"]
    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)
