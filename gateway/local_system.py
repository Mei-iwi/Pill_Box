"""Run the dashboard with six explicit, local software simulators (no broker)."""

import argparse
import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from flask import g, jsonify, request

from .accounts import DEFAULT_PATH, create_accounts
from .app import create_app
from .db import connect, init_db
from .mqtt_service import store_message
from .sample_data import DEVICE_IDS

LOGGER = logging.getLogger(__name__)
LOCAL_TIME = timezone(timedelta(hours=7))


class LocalFleet:
    def __init__(self, path):
        self.path = path
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.started = time.monotonic()
        self.boxes = {
            did: dict(
                boot=uuid.uuid4().hex,
                seq=0,
                online=True,
                state="IDLE",
                storage="NORMAL",
                pending=None,
                missed=False,
                refill=None,
                scenario=0,
            )
            for did in DEVICE_IDS
        }
        self.thread = None

    def uptime(self):
        return 1000 + int((time.monotonic() - self.started) * 1000)

    def emit(self, did, kind, **fields):
        box = self.boxes[did]
        box["seq"] += 1
        now = datetime.now(LOCAL_TIME)
        message = dict(
            device_id=did,
            boot_id=box["boot"],
            seq=box["seq"],
            uptime_ms=self.uptime(),
            utc_synced=True,
            device_local_minute=now.hour * 60 + now.minute,
            state=box["state"],
            **fields,
        )
        store_message(f"pillbox/{did}/{kind}", message, self.path, registered_only=True)

    def heartbeat(self, did):
        box = self.boxes[did]
        self.emit(did, "heartbeat", status="online", queue_depth=0, queue_dropped=0)
        warning = box["storage"] == "WARNING"
        self.emit(
            did,
            "environment",
            sensor_ok=box["storage"] != "SENSOR_ERROR",
            temperature_c=32.5 if warning else 25.0 + int(did[-1]) * 0.2,
            humidity_percent=75.0 if warning else 52.0 + int(did[-1]),
            storage_status=box["storage"],
        )

    def event(self, did, name, slot=0, schedule=None, **extra):
        box = self.boxes[did]
        now = datetime.now(LOCAL_TIME)
        scheduled = now.replace(hour=8, minute=0, second=0, microsecond=0)
        if schedule:
            with connect(self.path) as db:
                configured = db.execute(
                    "SELECT hour,minute FROM schedules WHERE device_id=? AND schedule_id=?",
                    (did, schedule),
                ).fetchone()
            scheduled = scheduled.replace(
                hour=configured["hour"], minute=configured["minute"]
            )
            minutes = (
                20
                if name == "TAKEN_LATE"
                else 16
                if name == "MISSED"
                else 2
                if name == "TAKEN_ON_TIME"
                else 0
            )
            now = scheduled + timedelta(minutes=minutes)
        seq = box["seq"] + 1
        self.emit(
            did,
            "event",
            schema_version=2,
            event_id=f"{did}:{box['boot']}:{seq}",
            event=name,
            slot_id=slot,
            schedule_id=schedule,
            occurrence_id=f"{did}:{schedule}:{now:%Y%m%d}:{box['scenario']}"
            if schedule
            else None,
            scheduled_at=scheduled.isoformat(),
            occurred_at=now.isoformat(),
            device_time_quality="software_simulator",
            device_state=box["state"],
            **extra,
        )

    def is_connected(self):
        return not self.stop_event.is_set()

    def publish(self, topic, payload, qos=1):
        did = topic.split("/")[1]
        command = json.loads(payload)
        with self.lock:
            box = self.boxes.get(did)
            if not box or not box["online"]:
                return SimpleNamespace(rc=4)
            name = command["command"]
            result = "APPLIED"
            extra = {}
            if box["refill"] and box["refill"]["expires_epoch_utc"] <= time.time():
                box["refill"] = None
            if name == "BEGIN_REFILL":
                expiry = command["expires_epoch_utc"]
                if expiry <= time.time() or expiry > time.time() + 300 or box["refill"]:
                    result = "REJECTED"
                else:
                    box["refill"] = dict(command)
            elif name == "END_REFILL":
                box["refill"] = None
            elif name == "CLEAR_ALERT":
                box["state"] = "IDLE"
            elif name == "UPDATE_SCHEDULE":
                extra["schedules"] = [command]
            if "refill_session_id" in command:
                extra["refill_session_id"] = command["refill_session_id"]
            self.emit(
                did,
                "status",
                status="online",
                command_id=command["command_id"],
                command=name,
                command_result=result,
                **extra,
            )
        return SimpleNamespace(rc=0)

    def action(self, did, action):
        with self.lock:
            box = self.boxes[did]
            if action == "online":
                box["online"] = True
                self.heartbeat(did)
                return
            if action == "offline":
                self.emit(did, "status", status="offline")
                box["online"] = False
                return
            if not box["online"]:
                raise ValueError("Hộp đang ngoại tuyến. Chọn Kết nối lại trước.")
            refill = box["refill"]
            if refill and refill["expires_epoch_utc"] <= time.time():
                box["refill"] = refill = None
            sid = "S1" if did == "PB01" else did + "_S1"
            if action in ("remind", "missed"):
                if box["pending"] is None:
                    box["scenario"] += 1
                box["pending"] = sid
                box["missed"] = action == "missed"
                box["state"] = "ALERT" if box["missed"] else "REMINDING"
                self.event(
                    did, "MISSED" if box["missed"] else "REMINDER_STARTED", 1, sid
                )
            elif action.startswith("open"):
                slot = int(action[-1])
                if refill and slot == refill["slot_id"]:
                    self.event(
                        did,
                        "REFILL_OPEN",
                        slot,
                        refill_session_id=refill["refill_session_id"],
                    )
                elif box["pending"] and slot == 1:
                    box["state"] = "IDLE"
                    self.event(
                        did,
                        "TAKEN_LATE" if box["missed"] else "TAKEN_ON_TIME",
                        1,
                        box["pending"],
                        delay_minutes=20 if box["missed"] else 0,
                    )
                    box["pending"] = None
                else:
                    box["state"] = "ALERT"
                    self.event(
                        did,
                        "WRONG_SLOT" if box["pending"] else "UNSCHEDULED_OPEN",
                        slot,
                        box["pending"],
                    )
            elif action in ("hot", "normal", "sensor"):
                box["storage"] = {
                    "hot": "WARNING",
                    "normal": "NORMAL",
                    "sensor": "SENSOR_ERROR",
                }[action]
                self.event(
                    did,
                    {
                        "hot": "STORAGE_WARNING",
                        "normal": "STORAGE_NORMAL",
                        "sensor": "SENSOR_ERROR",
                    }[action],
                )
                self.heartbeat(did)
            else:
                raise ValueError("Thao tác mô phỏng không hợp lệ.")

    def tick(self):
        with self.lock:
            for did, box in self.boxes.items():
                if box["online"]:
                    self.heartbeat(did)

    def start(self):
        self.tick()

        def run():
            while not self.stop_event.wait(5):
                try:
                    self.tick()
                except Exception:
                    LOGGER.exception("Local simulator heartbeat failed")

        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=10)
        with self.lock:
            for did in self.boxes:
                self.emit(did, "status", status="offline")


def create_local_app(path, identities):
    fleet = LocalFleet(path)
    app = create_app(
        dict(
            DB_PATH=str(path),
            AUTH_IDENTITIES=identities,
            MQTT_CLIENT=fleet,
            REQUIRE_REFILL_SESSION=True,
        )
    )
    app.config["LOCAL_SIMULATION"] = True
    app.extensions["local_fleet"] = fleet

    @app.post("/api/simulator/action")
    def simulator_action():
        if g.identity["role"] not in ("admin", "nurse"):
            return jsonify(error="caregiver role required"), 403
        body = request.get_json()
        did, action = body.get("box_id"), body.get("action")
        if (
            not isinstance(did, str)
            or not isinstance(action, str)
            or did not in fleet.boxes
            or action
            not in {
                "online",
                "offline",
                "remind",
                "missed",
                "open1",
                "open2",
                "open3",
                "hot",
                "normal",
                "sensor",
            }
        ):
            return jsonify(error="invalid simulator action"), 400
        try:
            fleet.action(did, action)
        except ValueError as exc:
            return jsonify(error=str(exc)), 409
        return jsonify(result="APPLIED")

    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="gateway/data/pillbox.db")
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()
    # This mode never connects the dataset to an external broker.
    os.environ["PILLBOX_MQTT_AUTOSTART"] = "0"
    path = Path(args.db)
    init_db(path)
    with connect(path) as db:
        profile = db.execute(
            "SELECT value FROM app_settings WHERE key='dataset_profile'"
        ).fetchone()
    if not profile:
        parser.error(
            "Run python -m gateway.reset_data --db "
            + str(path)
            + " --realistic first (backs up existing data)."
        )
    app = create_local_app(path, create_accounts(DEFAULT_PATH))
    fleet = app.extensions["local_fleet"]
    fleet.start()
    print(f"Local software simulators PB01–PB06: http://127.0.0.1:{args.port}")
    try:
        app.run(host="127.0.0.1", port=args.port, debug=False, use_reloader=False)
    finally:
        fleet.stop()


if __name__ == "__main__":
    main()
