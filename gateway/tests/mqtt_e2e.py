"""Real-broker integration check using a synthetic PB01 MQTT device.

This proves Broker -> Gateway -> SQLite -> Flask API/dashboard and the reverse
command path. It does not claim ESP32/Wokwi execution.
"""
import json
import os
import sqlite3
import tempfile
import threading
import time
import uuid

import paho.mqtt.client as mqtt

from gateway.app import create_app
from gateway.db import init_db
from gateway.mqtt_service import start_mqtt


HOST = os.getenv("MQTT_HOST", "test.mosquitto.org")
PORT = int(os.getenv("MQTT_PORT", "1883"))


def wait_until(predicate, label, timeout=15):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(0.1)
    raise TimeoutError(label)


def scalar(db_path, sql, args=()):
    with sqlite3.connect(db_path) as db:
        return db.execute(sql, args).fetchone()[0]


def main():
    db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_file.close()
    init_db(db_file.name)
    gateway = start_mqtt(db_file.name, HOST, PORT, f"pillbox-gateway-e2e-{uuid.uuid4().hex[:8]}")
    wait_until(gateway.is_connected, "gateway MQTT connection")

    base = int(time.time()) % 1_000_000 * 100
    command_received = threading.Event()
    received_commands = []
    device = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"pillbox-device-e2e-{uuid.uuid4().hex[:8]}")

    def on_connect(client, userdata, flags, reason_code, properties):
        client.subscribe("pillbox/PB01/command", qos=1)

    def on_message(client, userdata, message):
        command = json.loads(message.payload)
        received_commands.append(command)
        command_received.set()
        if command.get("command") == "REQUEST_STATUS":
            client.publish("pillbox/PB01/status", json.dumps({"device_id":"PB01","status":"online","state":"IDLE","seq":base + 90}), qos=1)

    device.on_connect = on_connect
    device.on_message = on_message
    device.connect(HOST, PORT, 15)
    device.loop_start()
    wait_until(device.is_connected, "device MQTT connection")

    app = create_app({"DB_PATH": db_file.name, "MQTT_CLIENT": gateway})
    api = app.test_client()

    device.publish("pillbox/PB01/heartbeat", json.dumps({"device_id":"PB01","status":"online","state":"IDLE","seq":base + 1}), qos=1)
    events = [
        ("REMINDER_STARTED", 1, 0), ("TAKEN_ON_TIME", 1, 3),
        ("WRONG_SLOT", 1, 0), ("MISSED", 2, 0), ("TAKEN_LATE", 3, 30),
        ("STORAGE_WARNING", 0, 0),
    ]
    for offset, (name, slot, delay) in enumerate(events, 2):
        device.publish("pillbox/PB01/event", json.dumps({"device_id":"PB01","event":name,"slot_id":slot,"schedule_id":f"S{slot}","scheduled_minute":480,"occurred_minute":480+delay,"delay_minutes":delay,"seq":base+offset}), qos=1)
    device.publish("pillbox/PB01/environment", json.dumps({"device_id":"PB01","temperature_c":31.5,"humidity_percent":72.0,"sensor_ok":True,"seq":base+20}), qos=1)

    wait_until(lambda: scalar(db_file.name, "SELECT COUNT(*) FROM medication_events WHERE seq BETWEEN ? AND ?", (base+2, base+7)) == 6, "event inserts")
    wait_until(lambda: scalar(db_file.name, "SELECT COUNT(*) FROM environment_readings WHERE device_id='PB01'") >= 1, "environment insert")
    assert api.get("/").status_code == 200
    assert api.get("/api/devices/PB01/status").get_json()["status"] == "online"

    command_response = api.post("/api/devices/PB01/commands", json={"command":"REQUEST_STATUS"})
    assert command_response.status_code == 202
    wait_until(command_received.is_set, "device command receipt")
    wait_until(lambda: api.get("/api/devices/PB01/status").get_json()["last_seq"] == base + 90, "command response status")

    duplicate = {"device_id":"PB01","event":"TAKEN_ON_TIME","slot_id":1,"schedule_id":"S1","scheduled_minute":480,"occurred_minute":481,"delay_minutes":1,"seq":base+50}
    device.publish("pillbox/PB01/event", json.dumps(duplicate), qos=1)
    device.publish("pillbox/PB01/event", json.dumps(duplicate), qos=1)
    wait_until(lambda: scalar(db_file.name, "SELECT COUNT(*) FROM medication_events WHERE device_id='PB01' AND seq=?", (base+50,)) == 1, "duplicate prevention")

    queued = {"device_id":"PB01","event":"TAKEN_LATE","slot_id":1,"schedule_id":"S1","scheduled_minute":480,"occurred_minute":500,"delay_minutes":20,"seq":base+60}
    device.disconnect(); device.loop_stop()
    offline_queue = [queued]
    device.connect(HOST, PORT, 15); device.loop_start(); wait_until(device.is_connected, "device reconnect")
    for payload in offline_queue:
        device.publish("pillbox/PB01/event", json.dumps(payload), qos=1)
    wait_until(lambda: scalar(db_file.name, "SELECT COUNT(*) FROM medication_events WHERE seq=?", (base+60,)) == 1, "reconnect sync")

    verified = api.post("/api/refill/verify", json={"actor_id":"NURSE01","box_id":"PB01","slot_id":1,"medication_code":"MED001"})
    confirmed = api.post("/api/refill/confirm", json={"actor_id":"NURSE01","box_id":"PB01","slot_id":1})
    mismatch = api.post("/api/refill/verify", json={"actor_id":"NURSE01","box_id":"PB01","slot_id":1,"medication_code":"MED002"})
    assert verified.get_json()["result"] == "VERIFIED" and confirmed.get_json()["result"] == "CONFIRMED"
    assert mismatch.get_json()["result"] == "MEDICATION_MISMATCH"

    report = {
        "broker": f"{HOST}:{PORT}", "heartbeat_to_db": True,
        "events_to_db": [name for name, _, _ in events], "environment_to_db": True,
        "dashboard_http": True, "command_round_trip": received_commands[-1],
        "duplicate_prevention": True, "simulated_offline_queue_sync": True,
        "refill_verified_confirmed": True, "refill_mismatch_blocked": True,
        "device": "synthetic MQTT client (not ESP32/Wokwi)",
    }
    print(json.dumps(report, indent=2))
    device.disconnect(); device.loop_stop(); gateway.disconnect(); gateway.loop_stop()


if __name__ == "__main__":
    main()
