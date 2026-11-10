"""Real-broker synthetic test; never claims ESP32/Wokwi runtime."""

import json
import os
import tempfile
import threading
import time
import uuid
from pathlib import Path

import paho.mqtt.client as mqtt

from gateway.app import create_app
from gateway.db import connect, init_db
from gateway.mqtt_service import start_mqtt


def wait_until(predicate, label, timeout=20):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.1)
    raise TimeoutError(label)


def main():
    host = os.getenv("MQTT_HOST", "test.mosquitto.org")
    port = int(os.getenv("MQTT_PORT", "1883"))
    did = "PBTEST_" + uuid.uuid4().hex[:10]
    boot = uuid.uuid4().hex
    subscribed = threading.Event()
    clients = []
    with tempfile.TemporaryDirectory() as directory:
        path = str(Path(directory) / "e2e.db")
        init_db(path)
        with connect(path) as db:
            db.execute(
                "INSERT INTO devices(device_id,patient_id) VALUES (?, 'P001')", (did,)
            )
            for sid, hour in (("TEST_S1", 8), ("TEST_S2", 14)):
                db.execute(
                    "INSERT INTO schedules(schedule_id,device_id,slot_id,medication_code,hour,minute) VALUES (?,?,1,'MED001',?,0)",
                    (sid, did, hour),
                )

        def scalar(sql, args=()):
            with connect(path) as db:
                return db.execute(sql, args).fetchone()[0]

        def publish(kind, payload):
            payload["device_id"] = did
            result = device.publish(f"pillbox/{did}/{kind}", json.dumps(payload), qos=1)
            result.wait_for_publish(timeout=10)
            assert result.is_published(), "publish timeout"

        def event(name, seq, at, sid="TEST_S1", slot=1, delay=0):
            scheduled = "14:00" if sid == "TEST_S2" else "08:00"
            payload = {
                "schema_version": 2,
                "event_id": f"{did}:{boot}:{seq}",
                "boot_id": boot,
                "seq": seq,
                "event": name,
                "slot_id": slot,
                "schedule_id": sid,
                "occurrence_id": f"{did}:{sid}:20261110" if slot else None,
                "scheduled_at": f"2026-11-10T{scheduled}:00+07:00",
                "occurred_at": f"2026-11-10T{at}:00+07:00",
                "device_time_quality": "synthetic",
                "delay_minutes": delay,
            }
            if name.startswith("TAKEN"):
                payload["device_state"] = "IDLE"
            elif name == "MISSED":
                payload["device_state"] = "ALERT"
            elif name in ("REMINDER_STARTED", "WRONG_SLOT"):
                payload["device_state"] = "REMINDING"
            hour, minute = map(int, at.split(":"))
            payload["device_local_minute"] = hour * 60 + minute
            return payload

        def on_connect(client, userdata, flags, reason, properties):
            client.subscribe(f"pillbox/{did}/command", qos=1)

        def on_message(client, userdata, message):
            command = json.loads(message.payload)
            ack = {
                "device_id": did,
                "status": "online",
                "state": "IDLE",
                "command_id": command["command_id"],
                "command": command["command"],
                "command_result": "APPLIED",
            }
            if command["command"] == "UPDATE_SCHEDULE":
                ack["schedules"] = [command]
            client.publish(f"pillbox/{did}/status", json.dumps(ack), qos=1)

        try:
            gateway = start_mqtt(path, host, port)
            clients.append(gateway)
            wait_until(gateway.is_connected, "gateway connection")
            device = mqtt.Client(
                mqtt.CallbackAPIVersion.VERSION2,
                client_id="synthetic-" + uuid.uuid4().hex[:12],
            )
            clients.append(device)
            device.on_connect = on_connect
            device.on_message = on_message
            device.on_subscribe = lambda *args: subscribed.set()
            device.connect(host, port, 15)
            device.loop_start()
            wait_until(subscribed.is_set, "device subscription")
            api = create_app({"DB_PATH": path, "MQTT_CLIENT": gateway}).test_client()
            publish("heartbeat", {"status": "online", "state": "IDLE", "seq": 0})
            wait_until(
                lambda: bool(
                    api.get(f"/api/devices/{did}/status").get_json()["last_seen"]
                ),
                "heartbeat persistence",
            )
            messages = [
                event("REMINDER_STARTED", 1, "08:00"),
                event("WRONG_SLOT", 2, "08:01", slot=2),
                event("MISSED", 3, "08:15", delay=15),
                event("TAKEN_LATE", 4, "10:00", delay=120),
                event("REMINDER_STARTED", 5, "14:00", "TEST_S2"),
                event("TAKEN_ON_TIME", 6, "14:01", "TEST_S2", delay=1),
                event("STORAGE_WARNING", 7, "14:02", "ENV", slot=0),
                event("SENSOR_ERROR", 8, "14:03", "ENV", slot=0),
                event("STORAGE_NORMAL", 9, "14:04", "ENV", slot=0),
            ]
            for message in messages:
                publish("event", message)
            publish("event", messages[3])
            wait_until(
                lambda: (
                    scalar(
                        "SELECT count(*) FROM medication_events WHERE device_id=?",
                        (did,),
                    )
                    == 9
                ),
                "events and duplicate",
            )
            occurrences = api.get(f"/api/devices/{did}/occurrences").get_json()
            live = api.get(f"/api/devices/{did}/live").get_json()
            assert live["device"]["state"] == "IDLE"
            assert live["device"]["device_local_minute"] == 844
            assert live["device"]["storage_status"] == "NORMAL"
            assert len(occurrences) == 2
            s1 = next(o for o in occurrences if o["schedule_id"] == "TEST_S1")
            assert s1["current_outcome"] == "LATE" and s1["delay_minutes"] == 120
            assert (
                next(o for o in occurrences if o["schedule_id"] == "TEST_S2")[
                    "current_outcome"
                ]
                == "ON_TIME"
            )
            publish(
                "environment",
                {
                    "temperature_c": 31.5,
                    "humidity_percent": 72,
                    "sensor_ok": True,
                    "seq": 20,
                },
            )
            publish(
                "environment",
                {
                    "temperature_c": None,
                    "humidity_percent": None,
                    "sensor_ok": False,
                    "seq": 21,
                },
            )
            wait_until(
                lambda: (
                    scalar(
                        "SELECT count(*) FROM environment_readings WHERE device_id=?",
                        (did,),
                    )
                    == 2
                ),
                "environment",
            )
            for command in (
                {"command": "REQUEST_STATUS"},
                {"command": "CLEAR_ALERT"},
                {
                    "command": "UPDATE_SCHEDULE",
                    "schedule_id": "TEST_S2",
                    "hour": 14,
                    "minute": 15,
                    "enabled": True,
                },
            ):
                response = api.post(f"/api/devices/{did}/commands", json=command)
                assert response.status_code == 202
                cid = response.get_json()["command_id"]
                wait_until(
                    lambda cid=cid: (
                        scalar(
                            "SELECT count(*) FROM command_requests WHERE command_id=? AND status='APPLIED'",
                            (cid,),
                        )
                        == 1
                    ),
                    "command ACK " + command["command"],
                )
            assert (
                scalar("SELECT minute FROM schedules WHERE schedule_id='TEST_S2'") == 15
            )
            device.disconnect()
            device.loop_stop()
            queued = event("UNSCHEDULED_OPEN", 30, "15:00", "NONE", slot=0)
            device.connect(host, port, 15)
            device.loop_start()
            wait_until(device.is_connected, "synthetic reconnect")
            publish("event", queued)
            wait_until(
                lambda: (
                    scalar(
                        "SELECT count(*) FROM medication_events WHERE device_id=? AND seq=30",
                        (did,),
                    )
                    == 1
                ),
                "synthetic queued event",
            )
            refill = {
                "actor_id": "NURSE01",
                "box_id": "PB01",
                "patient_id": "P001",
                "slot_id": 1,
                "medication_code": "MED001",
            }
            verified = api.post("/api/refill/verify", json=refill).get_json()
            assert verified["result"] == "VERIFIED"
            confirmation = {
                "actor_id": "NURSE01",
                "verification_id": verified["verification_id"],
            }
            assert (
                api.post("/api/refill/confirm", json=confirmation).get_json()["result"]
                == "CONFIRMED"
            )
            assert (
                api.post("/api/refill/confirm", json=confirmation).get_json()["result"]
                == "VERIFICATION_REPLAY"
            )
            refill["medication_code"] = "MED002"
            assert (
                api.post("/api/refill/verify", json=refill).get_json()["result"]
                == "MEDICATION_MISMATCH"
            )
            assert api.get("/").status_code == 200
            print(
                json.dumps(
                    {
                        "result": "PASS",
                        "broker": f"{host}:{port}",
                        "device": did,
                        "source": "synthetic MQTT; NOT ESP32/Wokwi",
                        "events": 10,
                        "occurrences": 2,
                        "late_reconciliation": True,
                        "next_schedule_independent": True,
                        "duplicate_prevention": True,
                        "command_ack": [
                            "REQUEST_STATUS",
                            "CLEAR_ALERT",
                            "UPDATE_SCHEDULE",
                        ],
                        "environment_sensor_error": True,
                        "refill_confirm_mismatch_replay": True,
                        "synthetic_reconnect": True,
                        "firmware_queue_runtime": "NOT_RUN",
                        "dashboard": "HTTP/API only; browser NOT_RUN",
                    },
                    indent=2,
                )
            )
        finally:
            for client in reversed(clients):
                if client:
                    client.disconnect()
                    client.loop_stop()


if __name__ == "__main__":
    main()
