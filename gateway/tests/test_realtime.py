import tempfile
import unittest
from pathlib import Path

from gateway.app import create_app
from gateway.db import connect
from gateway.mqtt_service import store_message, validate_message


class RealtimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name) / "live.db")
        self.api = create_app({"DB_PATH": self.path}).test_client()

    def tearDown(self):
        self.temp.cleanup()

    def status(self, seq, boot="boot-a", **extra):
        store_message(
            "pillbox/PB01/heartbeat",
            dict(
                device_id="PB01",
                seq=seq,
                boot_id=boot,
                status="online",
                state="IDLE",
                **extra,
            ),
            self.path,
        )

    def event(self, seq, state="REMINDING"):
        return {
            "schema_version": 2,
            "device_id": "PB01",
            "seq": seq,
            "boot_id": "boot-a",
            "event_id": f"boot-a:{seq}",
            "event": "REMINDER_STARTED",
            "slot_id": 1,
            "schedule_id": "S1",
            "occurrence_id": "PB01:S1:20261111",
            "scheduled_at": "2026-11-11T08:00:00+07:00",
            "occurred_at": "2026-11-11T08:00:00+07:00",
            "device_time_quality": "rtc",
            "device_state": state,
            "device_local_minute": 480,
            "device_epoch_local": 1794384000,
        }

    def environment(self, seq, boot="boot-a", status="NORMAL", temperature=25):
        store_message(
            "pillbox/PB01/environment",
            {
                "device_id": "PB01",
                "seq": seq,
                "boot_id": boot,
                "storage_status": status,
                "sensor_ok": True,
                "temperature_c": temperature,
                "humidity_percent": 50,
            },
            self.path,
        )

    def test_event_updates_device_without_waiting_for_heartbeat(self):
        store_message("pillbox/PB01/event", self.event(1), self.path)
        live = self.api.get("/api/devices/PB01/live").get_json()
        self.assertEqual(live["device"]["state"], "REMINDING")
        self.assertEqual(live["device"]["device_local_minute"], 480)
        self.assertEqual(live["occurrences"]["items"][0]["current_outcome"], "PENDING")
        self.assertEqual(len(live["recent"]), 1)

    def test_queued_event_cannot_rewind_newer_status(self):
        self.status(20, uptime_ms=2000)
        store_message("pillbox/PB01/event", self.event(10), self.path)
        state = self.api.get("/api/devices/PB01/status").get_json()
        self.assertEqual((state["state"], state["last_seq"]), ("IDLE", 20))
        self.assertEqual(len(self.api.get("/api/devices/PB01/events").get_json()), 1)

    def test_boot_change_resets_warning_then_confirms_normal(self):
        self.environment(50, status="WARNING", temperature=40)
        self.status(1, boot="boot-b")
        device = self.api.get("/api/devices").get_json()[0]
        self.assertEqual(
            (device["boot_id"], device["storage_status"], device["last_seq"]),
            ("boot-b", "PENDING", 1),
        )
        self.environment(2, boot="boot-b", status="NORMAL")
        self.assertEqual(
            self.api.get("/api/devices/PB01/live").get_json()["device"][
                "storage_status"
            ],
            "NORMAL",
        )

    def test_late_telemetry_does_not_reactivate_warning(self):
        self.environment(50, status="WARNING", temperature=40)
        self.environment(52, status="NORMAL", temperature=25)
        self.environment(51, status="WARNING", temperature=41)
        live = self.api.get("/api/devices/PB01/live").get_json()
        self.assertEqual(live["device"]["storage_status"], "NORMAL")
        self.assertEqual(live["readings"][0]["temperature_c"], 25)
        self.assertEqual(live["readings"][0]["seq"], 52)

    def test_live_pagination_and_empty_defaults(self):
        with connect(self.path) as db:
            for i in range(19):
                db.execute(
                    "INSERT INTO medication_events(device_id,seq,event,slot_id,received_at) VALUES ('PB01',?,'UNSCHEDULED_OPEN',1,'now')",
                    (i,),
                )
        result = self.api.get("/api/devices/PB01/live?events_page=2&page_size=8")
        self.assertEqual(result.headers["Cache-Control"], "no-store")
        live = result.get_json()
        self.assertEqual(
            (live["events"]["page"], live["events"]["total"], len(live["recent"])),
            (2, 19, 4),
        )
        self.assertEqual(live["events"]["items"][0]["seq"], 10)
        self.assertEqual(live["recent"][0]["seq"], 18)
        self.assertEqual(live["audit"]["total"], 0)
        self.assertEqual(len(live["schedules"]), 4)
        self.assertEqual(
            self.api.get("/api/devices/PB01/live?events_page=0").status_code, 400
        )
        self.assertEqual(self.api.get("/api/devices/PB99/live").status_code, 404)

    def test_live_auth_scope_and_family_does_not_receive_audit(self):
        token = "f" * 32
        with connect(self.path) as db:
            db.execute(
                "INSERT INTO refill_audit_logs(actor_id,box_id,patient_id,slot_id,scanned_medication_code,result,timestamp) VALUES ('N01','PB01','P001',1,'MED001','VERIFIED','now')"
            )
        api = create_app(
            {
                "DB_PATH": self.path,
                "AUTH_IDENTITIES": {
                    token: {"actor_id": "F01", "role": "family", "devices": ["PB01"]}
                },
            }
        ).test_client()
        headers = {"Authorization": "Bearer " + token}
        self.assertEqual(api.get("/api/devices/PB01/live").status_code, 401)
        self.assertEqual(
            api.get("/api/devices/PB02/live", headers=headers).status_code, 403
        )
        data = api.get("/api/devices/PB01/live", headers=headers).get_json()
        self.assertEqual([d["device_id"] for d in data["devices"]], ["PB01"])
        self.assertEqual(data["audit"]["items"], [])

    def test_realtime_fields_validate_ranges(self):
        for key, value in [
            ("uptime_ms", -1),
            ("device_local_minute", 1440),
            ("device_local_minute", True),
            ("device_epoch_local", "bad"),
            ("device_state", "UNKNOWN"),
            ("storage_status", []),
            ("boot_id", {}),
        ]:
            body = self.event(1)
            body[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_message("pillbox/PB01/event", body)

    def test_sqlite_supports_concurrent_read_snapshots(self):
        with connect(self.path) as db:
            self.assertEqual(db.execute("PRAGMA journal_mode").fetchone()[0], "wal")
