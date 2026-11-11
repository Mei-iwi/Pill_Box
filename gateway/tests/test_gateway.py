import json
import tempfile
import unittest
from pathlib import Path

from gateway.app import create_app
from gateway.db import connect, init_db
from gateway.mqtt_service import store_message, validate_message


class FakePublishResult:
    rc = 0


class FakeMqttClient:
    def __init__(self):
        self.calls = []

    def is_connected(self):
        return True

    def publish(self, topic, payload, qos=0):
        self.calls.append((topic, json.loads(payload), qos))
        return FakePublishResult()


class GatewayTests(unittest.TestCase):
    def setUp(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as self.tmp:
            pass
        init_db(self.tmp.name)
        self.mqtt = FakeMqttClient()
        self.app = create_app(
            {"DB_PATH": self.tmp.name, "MQTT_CLIENT": self.mqtt}
        ).test_client()

    def test_valid_event_and_duplicate(self):
        payload = {
            "device_id": "PB01",
            "event": "TAKEN_LATE",
            "slot_id": 1,
            "seq": 10,
            "delay_minutes": 12,
        }
        store_message("pillbox/PB01/event", payload, self.tmp.name)
        store_message("pillbox/PB01/event", payload, self.tmp.name)
        result = self.app.get("/api/devices/PB01/events").get_json()
        self.assertEqual(len(result), 1)

    def test_invalid_json(self):
        with self.assertRaises(ValueError):
            validate_message("pillbox/PB01/event", "{")

    def test_unknown_event(self):
        with self.assertRaises(ValueError):
            validate_message(
                "pillbox/PB01/event",
                {"device_id": "PB01", "event": "NOPE", "slot_id": 1, "seq": 1},
            )

    def test_invalid_slot(self):
        with self.assertRaises(ValueError):
            validate_message(
                "pillbox/PB01/event",
                {"device_id": "PB01", "event": "MISSED", "slot_id": 4, "seq": 1},
            )

    def test_heartbeat(self):
        store_message(
            "pillbox/PB01/heartbeat",
            {"device_id": "PB01", "status": "online", "state": "IDLE", "seq": 11},
            self.tmp.name,
        )
        self.assertEqual(
            self.app.get("/api/devices/PB01/status").get_json()["status"], "online"
        )
        store_message(
            "pillbox/PB01/status",
            {"device_id": "PB01", "status": "online"},
            self.tmp.name,
        )
        self.assertEqual(
            self.app.get("/api/devices/PB01/status").get_json()["last_seq"], 11
        )

    def test_environment(self):
        store_message(
            "pillbox/PB01/environment",
            {
                "device_id": "PB01",
                "temperature_c": 28,
                "humidity_percent": 60,
                "sensor_ok": True,
                "seq": 12,
            },
            self.tmp.name,
        )
        self.assertEqual(
            len(self.app.get("/api/devices/PB01/environment").get_json()), 1
        )

    def test_refill_verified_and_confirm(self):
        response = self.app.post(
            "/api/refill/verify",
            json={
                "actor_id": "NURSE01",
                "box_id": "PB01",
                "patient_id": "P001",
                "slot_id": 1,
                "medication_code": "MED001",
            },
        )
        self.assertEqual(response.get_json()["result"], "VERIFIED")
        body = {
            "actor_id": "NURSE01",
            "verification_id": response.get_json()["verification_id"],
        }
        self.assertEqual(
            self.app.post("/api/refill/confirm", json=body).status_code, 200
        )
        self.assertEqual(
            self.app.post("/api/refill/confirm", json=body).get_json()["result"],
            "VERIFICATION_REPLAY",
        )

    def test_refill_mismatch_blocks_confirm(self):
        response = self.app.post(
            "/api/refill/verify",
            json={
                "actor_id": "NURSE01",
                "box_id": "PB01",
                "patient_id": "P001",
                "slot_id": 1,
                "medication_code": "MED999",
            },
        )
        self.assertEqual(response.get_json()["result"], "MEDICATION_MISMATCH")
        self.assertEqual(
            self.app.post(
                "/api/refill/confirm",
                json={"actor_id": "NURSE01", "verification_id": "invalid"},
            ).status_code,
            409,
        )

    def test_valid_command_publishes_expected_topic_and_payload(self):
        response = self.app.post(
            "/api/devices/PB01/commands",
            json={"command": "REQUEST_STATUS", "ignored": "value"},
        )
        self.assertEqual(response.status_code, 202)
        self.assertEqual(
            self.mqtt.calls,
            [
                (
                    "pillbox/PB01/command",
                    {
                        "command": "REQUEST_STATUS",
                        "command_id": response.get_json()["command_id"],
                    },
                    1,
                )
            ],
        )

    def test_invalid_command_is_rejected_without_publish(self):
        response = self.app.post(
            "/api/devices/PB01/commands", json={"command": "RUN_ARBITRARY_CODE"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.mqtt.calls, [])

    def test_update_schedule_validates_contract(self):
        invalid = self.app.post(
            "/api/devices/PB01/commands",
            json={"command": "UPDATE_SCHEDULE", "slot_id": 1},
        )
        self.assertEqual(invalid.status_code, 400)
        valid = self.app.post(
            "/api/devices/PB01/commands",
            json={
                "command": "UPDATE_SCHEDULE",
                "schedule_id": "S1",
                "hour": 9,
                "minute": 15,
                "enabled": True,
            },
        )
        self.assertEqual(valid.status_code, 202)

    def tearDown(self):
        Path(self.tmp.name).unlink(missing_ok=True)

    def verify(self):
        return self.app.post(
            "/api/refill/verify",
            json={
                "actor_id": "NURSE01",
                "box_id": "PB01",
                "patient_id": "P001",
                "slot_id": 1,
                "medication_code": "MED001",
            },
        ).get_json()["verification_id"]

    def test_refill_patient_box_mismatch_and_unknown_slot(self):
        body = {
            "actor_id": "NURSE01",
            "box_id": "PB02",
            "patient_id": "P001",
            "slot_id": 1,
            "medication_code": "MED004",
        }
        self.assertEqual(
            self.app.post("/api/refill/verify", json=body).get_json()["result"],
            "PATIENT_BOX_MISMATCH",
        )
        body.update(box_id="PB01", slot_id=3, medication_code="MED001")
        self.assertEqual(
            self.app.post("/api/refill/verify", json=body).get_json()["result"],
            "MEDICATION_MISMATCH",
        )
        body.update(box_id="PB02", slot_id=2)
        self.assertEqual(
            self.app.post("/api/refill/verify", json=body).get_json()["result"],
            "UNKNOWN_BOX_OR_SLOT",
        )
        self.assertEqual(len(self.app.get("/api/refill/audit").get_json()), 3)

    def test_refill_expired(self):
        token = self.verify()
        with connect(self.tmp.name) as db:
            db.execute(
                "UPDATE refill_verifications SET expires_at='2000-01-01T00:00:00+00:00'"
            )
        r = self.app.post(
            "/api/refill/confirm",
            json={"actor_id": "NURSE01", "verification_id": token},
        )
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.get_json()["result"], "VERIFICATION_EXPIRED")

    def test_refill_stale(self):
        token = self.verify()
        with connect(self.tmp.name) as db:
            db.execute(
                "UPDATE slot_assignments SET medication_code='MED002' WHERE device_id='PB01' AND slot_id=1"
            )
        self.assertEqual(
            self.app.post(
                "/api/refill/confirm",
                json={"actor_id": "NURSE01", "verification_id": token},
            ).get_json()["result"],
            "STALE_VERIFICATION",
        )

    def test_refill_actor_mismatch(self):
        token = self.verify()
        self.assertEqual(
            self.app.post(
                "/api/refill/confirm",
                json={"actor_id": "OTHER", "verification_id": token},
            ).get_json()["result"],
            "ACTOR_MISMATCH",
        )

    def event_v2(self, name, seq, boot="boot1"):
        return {
            "schema_version": 2,
            "device_id": "PB01",
            "boot_id": boot,
            "event_id": f"PB01:{boot}:{seq}",
            "seq": seq,
            "event": name,
            "slot_id": 1,
            "schedule_id": "S1",
            "occurrence_id": "PB01:S1:20261110",
            "scheduled_at": "2026-11-10T08:00:00+07:00",
            "occurred_at": "2026-11-10T10:00:00+07:00",
            "device_time_quality": "rtc",
            "delay_minutes": 120,
        }

    def test_missed_late_reconciliation_duplicate_and_out_of_order(self):
        for name, seq in [
            ("REMINDER_STARTED", 1),
            ("MISSED", 2),
            ("TAKEN_LATE", 3),
            ("MISSED", 2),
            ("REMINDER_STARTED", 4),
        ]:
            store_message("pillbox/PB01/event", self.event_v2(name, seq), self.tmp.name)
        result = self.app.get("/api/devices/PB01/occurrences").get_json()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["current_outcome"], "LATE")
        self.assertEqual(result[0]["delay_minutes"], 120)
        self.assertEqual(len(self.app.get("/api/devices/PB01/events").get_json()), 4)

    def test_sequence_after_reboot(self):
        for boot in ("one", "two"):
            store_message(
                "pillbox/PB01/event",
                self.event_v2("TAKEN_LATE", 1, boot),
                self.tmp.name,
            )
        self.assertEqual(len(self.app.get("/api/devices/PB01/events").get_json()), 2)

    def test_invalid_v2_timestamp_identity_types(self):
        for key, value in [
            ("occurred_at", "invalid"),
            ("boot_id", ""),
            ("schema_version", 3),
            ("slot_id", True),
            ("occurrence_id", "PB02:S1:20261110"),
            ("delay_minutes", -1),
        ]:
            payload = self.event_v2("TAKEN_LATE", 1)
            payload[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_message("pillbox/PB01/event", payload)

    def test_sensor_error_and_invalid_nan(self):
        body = {
            "device_id": "PB01",
            "seq": 1,
            "sensor_ok": False,
            "temperature_c": None,
            "humidity_percent": None,
        }
        store_message("pillbox/PB01/environment", body, self.tmp.name)
        self.assertFalse(
            self.app.get("/api/devices/PB01/environment").get_json()[0]["sensor_ok"]
        )
        body.update(sensor_ok=True, temperature_c=float("nan"), humidity_percent=50)
        with self.assertRaises(ValueError):
            validate_message("pillbox/PB01/environment", body)

    def test_demo_mapping(self):
        schedules = self.app.get("/api/devices/PB01/schedules").get_json()
        self.assertEqual(len(schedules), 4)
        self.assertEqual(
            [
                (s["schedule_id"], s["slot_id"])
                for s in schedules
                if s["medication_code"] == "MED001"
            ],
            [("S1", 1), ("S2", 1)],
        )
        self.assertEqual(
            self.app.get("/api/devices/PB02/status").get_json()["patient_id"], "P002"
        )

    def test_migration_preserves_old_rows_and_schedules(self):
        import sqlite3

        from gateway.schema import SCHEMA

        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "old.db")
            with sqlite3.connect(path) as db:
                db.executescript(SCHEMA)
                db.execute(
                    "INSERT INTO schedules VALUES ('CUSTOM','PB01',3,11,11,1,5,120)"
                )
                db.execute(
                    "INSERT INTO medication_events(device_id,seq,event,slot_id,received_at) VALUES ('PB01',1,'MISSED',1,'old')"
                )
            db.close()
            init_db(path)
            init_db(path)
            with connect(path) as db:
                self.assertEqual(
                    db.execute(
                        "SELECT hour FROM schedules WHERE schedule_id='CUSTOM'"
                    ).fetchone()[0],
                    11,
                )
                self.assertEqual(
                    db.execute("SELECT count(*) FROM medication_events").fetchone()[0],
                    1,
                )

    def test_command_ack_updates_only_the_requested_schedule(self):
        request = {
            "command": "UPDATE_SCHEDULE",
            "schedule_id": "S1",
            "hour": 8,
            "minute": 30,
            "enabled": True,
        }
        response = self.app.post("/api/devices/PB01/commands", json=request).get_json()
        self.assertEqual(
            next(
                s
                for s in self.app.get("/api/devices/PB01/schedules").get_json()
                if s["schedule_id"] == "S1"
            )["minute"],
            0,
        )
        ack = {
            "device_id": "PB01",
            "command_id": response["command_id"],
            "command": "UPDATE_SCHEDULE",
            "command_result": "APPLIED",
            "schedules": [request],
        }
        store_message("pillbox/PB01/status", ack, self.tmp.name)
        schedules = self.app.get("/api/devices/PB01/schedules").get_json()
        self.assertEqual(
            next(s for s in schedules if s["schedule_id"] == "S1")["minute"], 30
        )
        self.assertEqual(
            next(s for s in schedules if s["schedule_id"] == "S2")["hour"], 14
        )
        self.assertEqual(
            self.app.get("/api/devices/PB01/commands").get_json()[0]["status"],
            "APPLIED",
        )

    def test_unavailable_broker(self):
        api = create_app({"DB_PATH": self.tmp.name}).test_client()
        self.assertEqual(
            api.post(
                "/api/devices/PB01/commands", json={"command": "REQUEST_STATUS"}
            ).status_code,
            503,
        )

    def test_non_object_payload(self):
        self.assertEqual(
            self.app.post("/api/refill/verify", json=["bad"]).status_code, 400
        )

    def test_malformed_types_are_rejected(self):
        self.assertEqual(
            self.app.post(
                "/api/devices/PB01/commands", json={"command": []}
            ).status_code,
            400,
        )
        for payload in (
            {"device_id": "PB01", "event": [], "slot_id": 1, "seq": 1},
            {"device_id": "PB01", "event": "MISSED", "slot_id": 1, "seq": 2**80},
        ):
            with self.assertRaises(ValueError):
                validate_message("pillbox/PB01/event", payload)
        with self.assertRaises(ValueError):
            validate_message("pillbox/PB02/event", self.event_v2("MISSED", 1))

    def test_heartbeat_timeout(self):
        with connect(self.tmp.name) as db:
            db.execute(
                "UPDATE devices SET status='online',last_seen='2000-01-01T00:00:00+00:00' WHERE device_id='PB01'"
            )
        self.assertEqual(
            self.app.get("/api/devices/PB01/status").get_json()["status"], "offline"
        )

    def test_invalid_confirm_token_type_with_auth(self):
        identities = {
            "n" * 32: {"actor_id": "NURSE01", "role": "nurse", "devices": ["PB01"]}
        }
        api = create_app(
            {"DB_PATH": self.tmp.name, "AUTH_IDENTITIES": identities}
        ).test_client()
        self.assertEqual(
            api.post(
                "/api/refill/confirm",
                headers={"Authorization": "Bearer " + "n" * 32},
                json={"verification_id": ["bad"]},
            ).status_code,
            400,
        )

    def test_auth_unauthorized_forbidden_scope_and_actor(self):
        family = "f" * 32
        nurse = "n" * 32
        admin = "a" * 32
        identities = {
            family: {"actor_id": "FAMILY01", "role": "family", "devices": ["PB01"]},
            nurse: {"actor_id": "NURSE_AUTH", "role": "nurse", "devices": ["PB01"]},
            admin: {"actor_id": "ADMIN", "role": "admin", "devices": []},
        }
        api = create_app(
            {
                "DB_PATH": self.tmp.name,
                "MQTT_CLIENT": self.mqtt,
                "AUTH_IDENTITIES": identities,
            }
        ).test_client()
        self.assertEqual(api.get("/api/devices").status_code, 401)
        f = {"Authorization": "Bearer " + family}
        n = {"Authorization": "Bearer " + nurse}
        self.assertEqual(
            api.get("/api/devices/PB02/status", headers=f).status_code, 403
        )
        self.assertEqual(len(api.get("/api/devices", headers=f).get_json()), 1)
        self.assertEqual(
            api.post("/api/refill/verify", headers=f, json={}).status_code, 403
        )
        self.assertEqual(
            api.post(
                "/api/devices/PB01/commands",
                headers=n,
                json={"command": "UPDATE_SCHEDULE"},
            ).status_code,
            403,
        )
        body = {
            "actor_id": "IMPERSONATED",
            "box_id": "PB01",
            "patient_id": "P001",
            "slot_id": 1,
            "medication_code": "MED001",
        }
        verify = api.post("/api/refill/verify", headers=n, json=body).get_json()
        self.assertEqual(
            api.post(
                "/api/refill/confirm",
                headers=n,
                json={
                    "actor_id": "IMPERSONATED",
                    "verification_id": verify["verification_id"],
                },
            ).status_code,
            200,
        )
        self.assertEqual(
            api.get("/api/refill/audit", headers=n).get_json()[0]["actor_id"],
            "NURSE_AUTH",
        )
        self.assertEqual(
            len(
                api.get(
                    "/api/devices", headers={"Authorization": "Bearer " + admin}
                ).get_json()
            ),
            2,
        )


if __name__ == "__main__":
    unittest.main()
