import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gateway.accounts import create_accounts
from gateway.db import connect, init_db
from gateway.local_system import create_local_app
from gateway.reset_data import reset_data


class LocalSystemTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.path = self.root / "local.db"
        self.patch = patch("gateway.reset_data.DATA_ROOT", self.root)
        self.patch.start()
        reset_data(self.path, realistic=True)
        self.identities = create_accounts(self.root / "auth.json")
        with patch.dict("os.environ", {"PILLBOX_MQTT_AUTOSTART": "0"}):
            self.app = create_local_app(self.path, self.identities)
        self.client = self.app.test_client()
        self.fleet = self.app.extensions["local_fleet"]
        self.fleet.tick()

    def tearDown(self):
        self.patch.stop()
        self.temp.cleanup()

    def headers(self, actor="ADMIN01"):
        token = next(k for k, v in self.identities.items() if v["actor_id"] == actor)
        return {"Authorization": "Bearer " + token}

    def post(self, url, body, actor="ADMIN01"):
        return self.client.post(url, json=body, headers=self.headers(actor))

    def action(self, name, did="PB01", actor="ADMIN01"):
        result = self.post(
            "/api/simulator/action", dict(box_id=did, action=name), actor
        )
        self.assertEqual(result.status_code, 200, result.get_json())

    def scalar(self, sql):
        with connect(self.path) as db:
            return db.execute(sql).fetchone()[0]

    def test_dataset_survives_restart_without_legacy_seed(self):
        init_db(self.path)
        self.assertEqual(self.scalar("SELECT count(*) FROM devices"), 6)
        self.assertEqual(self.scalar("SELECT count(*) FROM schedules"), 24)
        self.assertEqual(self.scalar("SELECT count(*) FROM slot_assignments"), 18)
        self.assertEqual(
            self.scalar("SELECT count(*) FROM schedules WHERE schedule_id='S5'"), 0
        )
        self.assertEqual(self.scalar("SELECT count(*) FROM medication_events"), 0)

    def test_scoped_accounts_and_heartbeat(self):
        for actor, expected in [
            ("ADMIN01", 6),
            ("NURSE_A", 3),
            ("NURSE_B", 3),
            ("FAMILY01", 1),
        ]:
            devices = self.client.get(
                "/api/devices", headers=self.headers(actor)
            ).get_json()
            self.assertEqual(len(devices), expected)
            self.assertTrue(all(d["status"] == "online" for d in devices))
        self.assertEqual(
            self.post(
                "/api/simulator/action", dict(box_id="PB04", action="open1"), "NURSE_A"
            ).status_code,
            403,
        )
        self.assertEqual(
            self.post(
                "/api/simulator/action", dict(box_id="PB01", action="open1"), "FAMILY01"
            ).status_code,
            403,
        )
        self.assertEqual(self.client.get("/api/session").status_code, 401)

    def test_real_command_ack_and_offline(self):
        command = self.post(
            "/api/devices/PB01/commands", dict(command="REQUEST_STATUS")
        )
        self.assertEqual(command.status_code, 202)
        self.assertEqual(self.scalar("SELECT status FROM command_requests"), "APPLIED")
        self.action("offline")
        result = self.post("/api/devices/PB01/commands", dict(command="REQUEST_STATUS"))
        self.assertEqual(result.status_code, 503)
        self.action("online")

    def test_scenarios_and_alert_recovery(self):
        for action in [
            "remind",
            "open2",
            "open1",
            "missed",
            "open1",
            "hot",
            "normal",
            "sensor",
            "normal",
        ]:
            self.action(action)
        self.assertEqual(self.scalar("SELECT count(*) FROM schedule_occurrences"), 2)
        self.assertEqual(
            self.scalar(
                "SELECT count(*) FROM alerts WHERE status!='RESOLVED' AND kind IN ('MISSED','STORAGE_WARNING','SENSOR_ERROR')"
            ),
            0,
        )
        self.assertEqual(
            self.scalar(
                "SELECT count(*) FROM medication_events WHERE event='TAKEN_LATE'"
            ),
            1,
        )

    def test_refill_open_is_required_and_never_completes_dose(self):
        body = dict(
            box_id="PB01", patient_id="P001", slot_id=1, medication_code="MED001"
        )
        verified = self.post("/api/refill/verify", body, "NURSE_A")
        vid = verified.get_json()["verification_id"]
        request = dict(verification_id=vid)
        self.assertEqual(
            self.post("/api/refill/authorize", request, "NURSE_A").status_code, 202
        )
        self.assertEqual(self.scalar("SELECT status FROM refill_sessions"), "ACTIVE")
        self.assertEqual(
            self.post("/api/refill/confirm", request, "NURSE_A").status_code, 409
        )
        self.action("open1", actor="NURSE_A")
        self.assertEqual(self.scalar("SELECT opened_count FROM refill_sessions"), 1)
        result = self.post("/api/refill/confirm", request, "NURSE_A")
        self.assertEqual(result.status_code, 200, result.get_json())
        self.assertEqual(self.scalar("SELECT status FROM refill_sessions"), "CLOSED")
        self.assertIsNotNone(self.scalar("SELECT end_uptime_ms FROM refill_sessions"))
        self.assertEqual(self.scalar("SELECT count(*) FROM schedule_occurrences"), 0)

    def test_schedule_admin_only(self):
        body = dict(
            command="UPDATE_SCHEDULE", schedule_id="S1", hour=8, minute=10, enabled=True
        )
        self.assertEqual(
            self.post("/api/devices/PB01/commands", body, "NURSE_A").status_code, 403
        )
        self.assertEqual(self.post("/api/devices/PB01/commands", body).status_code, 202)
        self.assertEqual(
            self.scalar("SELECT minute FROM schedules WHERE schedule_id='S1'"), 10
        )

    def test_reset_removes_sessions_and_alerts_with_backup(self):
        self.action("hot")
        backup = reset_data(self.path, realistic=True)
        self.assertTrue(backup.exists())
        self.assertEqual(self.scalar("SELECT count(*) FROM alerts"), 0)
        self.assertEqual(self.scalar("SELECT count(*) FROM environment_readings"), 0)
        self.assertEqual(
            self.scalar("SELECT count(*) FROM devices WHERE status='online'"), 0
        )

    def test_accounts_are_random_stable_and_ui_is_local_only(self):
        self.assertTrue(all(len(key) == 24 for key in self.identities))
        self.assertEqual(self.identities, create_accounts(self.root / "auth.json"))
        self.assertNotEqual(self.identities, create_accounts(self.root / "other.json"))
        page = self.client.get("/")
        self.assertIn(b'id="simulator-panel"', page.data)
        self.assertEqual(page.headers["Cache-Control"], "no-store")


if __name__ == "__main__":
    unittest.main()
