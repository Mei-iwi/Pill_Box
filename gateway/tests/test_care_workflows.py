import ssl
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from gateway.app import create_app
from gateway.db import connect
from gateway.mqtt_config import configure_mqtt
from gateway.mqtt_service import store_message, validate_message
from gateway.provision import provision
from gateway.tests.test_gateway import FakeMqttClient


class CareWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name) / "care.db")
        self.mqtt = FakeMqttClient()
        self.app = create_app(
            {
                "DB_PATH": self.path,
                "MQTT_CLIENT": self.mqtt,
                "REQUIRE_REFILL_SESSION": True,
            }
        )
        self.api = self.app.test_client()
        store_message(
            "pillbox/PB01/heartbeat",
            {
                "device_id": "PB01",
                "seq": 0,
                "boot_id": "boot-a",
                "uptime_ms": 100000,
                "status": "online",
                "state": "IDLE",
                "utc_synced": True,
            },
            self.path,
        )

    def tearDown(self):
        self.temp.cleanup()

    def verify(self):
        return self.api.post(
            "/api/refill/verify",
            json={
                "actor_id": "NURSE01",
                "box_id": "PB01",
                "patient_id": "P001",
                "slot_id": 1,
                "medication_code": "MED001",
            },
        ).get_json()["verification_id"]

    def begin(self, ack=True):
        vid = self.verify()
        response = self.api.post(
            "/api/refill/authorize",
            json={"actor_id": "NURSE01", "verification_id": vid},
        )
        self.assertEqual(response.status_code, 202)
        result = response.get_json()
        if ack:
            self.ack(result["command_id"], "BEGIN_REFILL", result["session_id"])
        return vid, result

    def ack(self, cid, command, sid, boot="boot-a", uptime=101000):
        store_message(
            "pillbox/PB01/status",
            {
                "device_id": "PB01",
                "boot_id": boot,
                "uptime_ms": uptime,
                "command_id": cid,
                "command": command,
                "command_result": "APPLIED",
                "refill_session_id": sid,
            },
            self.path,
        )

    def event(self, name="REFILL_OPEN", seq=10, sid=None, uptime=102000, **extra):
        payload = {
            "device_id": "PB01",
            "schema_version": 2,
            "boot_id": "boot-a",
            "event_id": f"boot-a:{seq}",
            "seq": seq,
            "uptime_ms": uptime,
            "event": name,
            "slot_id": 1,
            "schedule_id": "REFILL",
            "occurrence_id": None,
            "device_time_quality": "rtc",
            "occurred_at": "2026-11-11T08:00:00+07:00",
            "scheduled_at": "2026-11-11T08:00:00+07:00",
            **extra,
        }
        if sid:
            payload["refill_session_id"] = sid
        store_message("pillbox/PB01/event", payload, self.path)
        return payload

    def test_refill_access_is_audited_without_completing_medication(self):
        vid, result = self.begin()
        payload = self.event(sid=result["session_id"])
        store_message("pillbox/PB01/event", payload, self.path)
        snapshot = self.api.get("/api/devices/PB01/live").get_json()
        self.assertEqual(snapshot["occurrences"]["total"], 0)
        self.assertEqual(snapshot["alerts"]["total"], 0)
        self.assertEqual(snapshot["refill_session"]["opened_count"], 1)
        response = self.api.post(
            "/api/refill/confirm", json={"actor_id": "NURSE01", "verification_id": vid}
        )
        self.assertEqual(response.get_json()["result"], "CONFIRMED")
        self.assertEqual(self.mqtt.calls[-1][1]["command"], "END_REFILL")

    def test_open_before_ack_or_without_authorization_is_rejected(self):
        _, result = self.begin(ack=False)
        with self.assertRaises(ValueError):
            self.event(sid=result["session_id"])
        with self.assertRaises(ValueError):
            self.event(sid="f" * 32)

    def test_confirm_requires_open_and_session_cannot_be_replayed(self):
        vid, _result = self.begin()
        response = self.api.post(
            "/api/refill/confirm", json={"actor_id": "NURSE01", "verification_id": vid}
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["result"], "REFILL_OPEN_REQUIRED")
        self.assertEqual(
            self.api.post(
                "/api/refill/authorize",
                json={"actor_id": "NURSE01", "verification_id": vid},
            ).status_code,
            409,
        )

    def test_closed_session_accepts_queued_earlier_open_but_not_later_open(self):
        vid, result = self.begin()
        response = self.api.post(
            "/api/refill/end", json={"actor_id": "NURSE01", "verification_id": vid}
        )
        self.ack(
            response.get_json()["result"]["command_id"],
            "END_REFILL",
            result["session_id"],
            uptime=104000,
        )
        self.event(sid=result["session_id"], uptime=103000)
        with self.assertRaises(ValueError):
            self.event(sid=result["session_id"], seq=11, uptime=105000)

    def test_wrong_slot_expired_interval_and_wrong_boot_are_rejected(self):
        _, result = self.begin()
        with self.assertRaises(ValueError):
            self.event(sid=result["session_id"], slot_id=2)
        with self.assertRaises(ValueError):
            self.event(sid=result["session_id"], uptime=999999)
        with self.assertRaises(ValueError):
            self.event(sid=result["session_id"], boot_id="boot-b")

    def test_invalid_ack_does_not_activate_window(self):
        _, result = self.begin(ack=False)
        self.ack(result["command_id"], "BEGIN_REFILL", "f" * 32)
        with connect(self.path) as db:
            self.assertEqual(
                db.execute(
                    "SELECT status FROM command_requests WHERE command_id=?",
                    (result["command_id"],),
                ).fetchone()[0],
                "INVALID_ACK",
            )
        with self.assertRaises(ValueError):
            self.event(sid=result["session_id"])

    def test_new_boot_closes_authorization_and_offline_box_cannot_authorize(self):
        vid, result = self.begin()
        store_message(
            "pillbox/PB01/heartbeat",
            {"device_id": "PB01", "boot_id": "boot-b", "seq": 1, "status": "online"},
            self.path,
        )
        with connect(self.path) as db:
            self.assertEqual(
                db.execute(
                    "SELECT status FROM refill_sessions WHERE session_id=?",
                    (result["session_id"],),
                ).fetchone()[0],
                "CLOSED",
            )
            db.execute("UPDATE devices SET status='offline' WHERE device_id='PB01'")
        vid = self.verify()
        self.assertEqual(
            self.api.post(
                "/api/refill/authorize",
                json={"actor_id": "NURSE01", "verification_id": vid},
            ).status_code,
            409,
        )

    def test_alert_is_deduplicated_resolved_and_audited(self):
        payload = self.event("UNSCHEDULED_OPEN", schedule_id="NONE")
        store_message("pillbox/PB01/event", payload, self.path)
        alerts = self.api.get("/api/alerts").get_json()
        self.assertEqual(alerts["total"], 1)
        aid = alerts["items"][0]["alert_id"]
        self.assertEqual(
            self.api.post(
                f"/api/alerts/{aid}/ack",
                json={"actor_id": "NURSE01", "action": "resolve"},
            ).status_code,
            200,
        )
        self.assertEqual(self.api.get("/api/alerts").get_json()["total"], 0)
        history = self.api.get("/api/alerts?history=1").get_json()["items"][0]
        self.assertEqual(history["acknowledged_by"], "NURSE01")
        self.assertEqual(history["status"], "RESOLVED")

        for seq, ok, status, t, h in [
            (20, False, "SENSOR_ERROR", None, None),
            (21, True, "WARNING", 32, 75),
            (22, True, "NORMAL", 25, 50),
        ]:
            store_message(
                "pillbox/PB01/environment",
                {
                    "device_id": "PB01",
                    "boot_id": "boot-a",
                    "seq": seq,
                    "sensor_ok": ok,
                    "storage_status": status,
                    "temperature_c": t,
                    "humidity_percent": h,
                },
                self.path,
            )
            kinds = {a["kind"] for a in self.api.get("/api/alerts").get_json()["items"]}
            self.assertEqual(
                kinds,
                {"SENSOR_ERROR"}
                if not ok
                else {"STORAGE_WARNING"}
                if status == "WARNING"
                else set(),
            )

    def test_missed_resolves_after_late_and_old_event_does_not_reopen(self):
        context = {"schedule_id": "S1", "occurrence_id": "PB01:S1:20261111"}
        self.event("MISSED", seq=1, **context)
        self.event("TAKEN_LATE", seq=2, **context)
        self.event("MISSED", seq=3, **context)
        self.assertEqual(self.api.get("/api/alerts").get_json()["total"], 0)

    def test_family_and_other_box_cannot_modify_alerts_or_refill(self):
        self.event("UNSCHEDULED_OPEN", schedule_id="NONE")
        auth = {
            "f" * 32: {"actor_id": "F01", "role": "family", "devices": ["PB01"]},
            "n" * 32: {"actor_id": "N01", "role": "nurse", "devices": ["PB02"]},
        }
        api = create_app({"DB_PATH": self.path, "AUTH_IDENTITIES": auth}).test_client()
        aid = self.api.get("/api/alerts").get_json()["items"][0]["alert_id"]
        self.assertEqual(
            api.post(
                f"/api/alerts/{aid}/ack",
                headers={"Authorization": "Bearer " + "f" * 32},
                json={},
            ).status_code,
            403,
        )
        self.assertEqual(
            api.get(
                "/api/alerts", headers={"Authorization": "Bearer " + "n" * 32}
            ).get_json()["total"],
            0,
        )
        self.assertEqual(
            api.post(
                f"/api/alerts/{aid}/ack",
                headers={"Authorization": "Bearer " + "n" * 32},
                json={},
            ).status_code,
            404,
        )
        vid = self.verify()
        self.assertEqual(
            api.post(
                "/api/refill/authorize",
                headers={"Authorization": "Bearer " + "n" * 32},
                json={"verification_id": vid},
            ).status_code,
            403,
        )

    def test_registered_only_rejects_unknown_box_and_provision_keeps_existing(self):
        with self.assertRaises(ValueError):
            store_message(
                "pillbox/PB03/heartbeat",
                {"device_id": "PB03", "seq": 0},
                self.path,
                registered_only=True,
            )
        provision(self.path, "PB03", "P003", "Ho so 03")
        store_message(
            "pillbox/PB03/heartbeat",
            {"device_id": "PB03", "seq": 0},
            self.path,
            registered_only=True,
        )
        with connect(self.path) as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) FROM schedules WHERE device_id='PB03'"
                ).fetchone()[0],
                4,
            )
            self.assertEqual(
                db.execute(
                    "SELECT schedule_id FROM schedules WHERE device_id='PB03' ORDER BY schedule_id LIMIT 1"
                ).fetchone()[0],
                "PB03_S1",
            )
        with self.assertRaises(ValueError):
            provision(self.path, "PB03", "P004", "Other")

    def test_refill_requires_utc_synchronization(self):
        with connect(self.path) as db:
            db.execute("UPDATE devices SET utc_synced=0 WHERE device_id='PB01'")
        vid = self.verify()
        response = self.api.post(
            "/api/refill/authorize",
            json={"actor_id": "NURSE01", "verification_id": vid},
        )
        self.assertEqual(response.status_code, 409)
        self.assertIn("synchronize UTC", response.get_json()["error"])

    def test_refill_event_cannot_claim_medication_occurrence(self):
        with self.assertRaises(ValueError):
            validate_message(
                "pillbox/PB01/event",
                {
                    "device_id": "PB01",
                    "seq": 1,
                    "event": "REFILL_OPEN",
                    "slot_id": 1,
                    "schema_version": 1,
                },
            )


class MqttSecurityTests(unittest.TestCase):
    def test_tls_context_verifies_certificates_and_hostname(self):
        client = Mock()
        configure_mqtt(
            client, {"MQTT_TLS": "1", "MQTT_USER": "gateway", "MQTT_PASSWORD": "secret"}
        )
        context = client.tls_set_context.call_args.args[0]
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)
        self.assertGreaterEqual(context.minimum_version, ssl.TLSVersion.TLSv1_2)
        client.username_pw_set.assert_called_once_with("gateway", "secret")

    def test_care_rejects_plaintext_or_missing_credentials(self):
        for env in [
            {"PILLBOX_DEPLOYMENT": "care"},
            {"PILLBOX_DEPLOYMENT": "care", "MQTT_TLS": "1"},
            {"MQTT_USER": "gateway"},
        ]:
            with self.assertRaises(ValueError):
                configure_mqtt(Mock(), env)

    def test_missing_ca_and_unpaired_client_certificate_fail_closed(self):
        for env in [
            {"MQTT_TLS": "1", "MQTT_CA_FILE": "does-not-exist"},
            {"MQTT_TLS": "1", "MQTT_CERT_FILE": "one-only"},
        ]:
            with self.assertRaises(ValueError):
                configure_mqtt(Mock(), env)

    def test_wokwi_plaintext_profile_stays_available(self):
        client = Mock()
        configure_mqtt(client, {})
        client.tls_set_context.assert_not_called()
