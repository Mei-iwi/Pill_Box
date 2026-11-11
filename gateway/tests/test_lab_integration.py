import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from gateway.app import create_app
from gateway.db import connect
from gateway.mqtt_service import store_message, validate_message
from gateway.notifications import dispatch
from gateway.tests.test_gateway import FakeMqttClient


class LabIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name) / "labs.db")
        self.admin = "a" * 24
        self.family = "f" * 24
        self.nurse = "n" * 24
        with patch.dict("os.environ", {"PILLBOX_MQTT_AUTOSTART": "0"}):
            self.app = create_app(
                dict(
                    DB_PATH=self.path,
                    MQTT_CLIENT=FakeMqttClient(),
                    HTTP_INGEST_ENABLED=True,
                    AUTH_IDENTITIES={
                        self.admin: dict(actor_id="ADMIN", role="admin", devices=[]),
                        self.family: dict(
                            actor_id="FAMILY", role="family", devices=["PB01"]
                        ),
                        self.nurse: dict(
                            actor_id="NURSE", role="nurse", devices=["PB01"]
                        ),
                    },
                )
            )
        self.client = self.app.test_client()
        self.headers = {"Authorization": "Bearer " + self.admin}

    def tearDown(self):
        self.temp.cleanup()

    def scalar(self, sql):
        with connect(self.path) as db:
            return db.execute(sql).fetchone()[0]

    def environment(self, seq=1, temperature=32, humidity=75, storage="WARNING"):
        return dict(
            device_id="PB01",
            boot_id="lab",
            seq=seq,
            sensor_ok=True,
            temperature_c=temperature,
            humidity_percent=humidity,
            storage_status=storage,
        )

    def publish(self, message):
        store_message("pillbox/PB01/environment", message, self.path)

    def test_rule_chain_open_escalation_recovery_without_spam(self):
        self.publish(self.environment())
        self.publish(self.environment(seq=2))
        self.assertEqual(self.scalar("SELECT count(*) FROM alert_notifications"), 1)
        self.publish(self.environment(seq=3, temperature=40))
        self.assertEqual(self.scalar("SELECT severity FROM alerts"), "critical")
        self.assertEqual(self.scalar("SELECT count(*) FROM alert_notifications"), 2)
        self.publish(self.environment(seq=4, temperature=40))
        self.assertEqual(self.scalar("SELECT count(*) FROM alert_notifications"), 2)
        self.publish(self.environment(seq=5, temperature=34))
        self.assertEqual(self.scalar("SELECT severity FROM alerts"), "critical")
        self.publish(
            self.environment(seq=6, temperature=25, humidity=50, storage="NORMAL")
        )
        self.assertEqual(self.scalar("SELECT status FROM alerts"), "RESOLVED")
        self.assertEqual(
            self.scalar(
                "SELECT count(*) FROM alert_notifications WHERE transition='RECOVERED'"
            ),
            1,
        )

    def test_environment_duplicates_are_not_stored_twice(self):
        self.publish(self.environment())
        self.publish(self.environment())
        self.publish(self.environment(temperature=40))
        self.assertEqual(self.scalar("SELECT count(*) FROM environment_readings"), 1)
        self.assertEqual(self.scalar("SELECT severity FROM alerts"), "warning")

    def test_stale_samples_cannot_escalate_current_alarm(self):
        self.publish(self.environment(seq=10))
        self.publish(self.environment(seq=9, temperature=40))
        self.assertEqual(self.scalar("SELECT severity FROM alerts"), "warning")

    def test_http_validates_schema_identity_and_admin(self):
        endpoint = "/api/devices/PB01/telemetry"
        body = dict(kind="environment", message=self.environment())
        self.assertEqual(self.client.post(endpoint, json=body).status_code, 401)
        for token in (self.family, self.nurse):
            self.assertEqual(
                self.client.post(
                    endpoint, json=body, headers={"Authorization": "Bearer " + token}
                ).status_code,
                403,
            )
        self.assertEqual(
            self.client.post(endpoint, json=body, headers=self.headers).status_code, 201
        )
        body["message"]["device_id"] = "PB02"
        self.assertEqual(
            self.client.post(endpoint, json=body, headers=self.headers).status_code, 400
        )
        self.app.config["HTTP_INGEST_ENABLED"] = False
        self.assertEqual(
            self.client.post(endpoint, json=body, headers=self.headers).status_code, 404
        )

    def test_http_rejects_invalid_values_and_large_body(self):
        body = dict(kind="environment", message=self.environment(temperature=100))
        self.assertEqual(
            self.client.post(
                "/api/devices/PB01/telemetry", json=body, headers=self.headers
            ).status_code,
            400,
        )
        result = self.client.post(
            "/api/devices/PB01/telemetry",
            json={"oversize": "x" * 9000},
            headers=self.headers,
        )
        self.assertEqual(result.status_code, 413)

    def test_history_bounded_and_scoped(self):
        for i in range(1, 5):
            self.publish(self.environment(seq=i))
        result = self.client.get(
            "/api/devices/PB01/environment/history?hours=24", headers=self.headers
        )
        self.assertEqual(result.status_code, 200)
        self.assertLessEqual(len(result.get_json()["items"]), 145)
        self.assertEqual(sum(p["samples"] for p in result.get_json()["items"]), 4)
        self.assertEqual(
            self.client.get(
                "/api/devices/PB01/environment/history?hours=999", headers=self.headers
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.get(
                "/api/devices/PB02/environment/history",
                headers={"Authorization": "Bearer " + self.family},
            ).status_code,
            403,
        )

    def test_commands_timeout_and_ignore_late_ack(self):
        response = self.client.post(
            "/api/devices/PB01/commands",
            json={"command": "REQUEST_STATUS"},
            headers=self.headers,
        )
        cid = response.get_json()["command_id"]
        old = (datetime.now(timezone.utc) - timedelta(seconds=61)).isoformat()
        with connect(self.path) as db:
            db.execute("UPDATE command_requests SET created_at=?", (old,))
        result = self.client.get(
            "/api/devices/PB01/commands", headers=self.headers
        ).get_json()
        self.assertEqual(result[0]["status"], "TIMEOUT")
        store_message(
            "pillbox/PB01/status",
            dict(
                device_id="PB01",
                command_id=cid,
                command="REQUEST_STATUS",
                command_result="APPLIED",
            ),
            self.path,
        )
        self.assertEqual(self.scalar("SELECT status FROM command_requests"), "TIMEOUT")

    def test_ack_latency_uses_gateway_receipt_time(self):
        response = self.client.post(
            "/api/devices/PB01/commands",
            json={"command": "REQUEST_STATUS"},
            headers=self.headers,
        )
        cid = response.get_json()["command_id"]
        store_message(
            "pillbox/PB01/status",
            dict(
                device_id="PB01",
                command_id=cid,
                command="REQUEST_STATUS",
                command_result="APPLIED",
            ),
            self.path,
        )
        result = self.client.get(
            "/api/devices/PB01/commands", headers=self.headers
        ).get_json()
        self.assertGreaterEqual(result[0]["ack_latency_ms"], 0)

    def test_dry_run_never_sends_and_success_is_not_repeated(self):
        self.publish(self.environment())
        transport = Mock()
        self.assertEqual(dispatch(self.path, transport=transport)["sent"], 0)
        transport.assert_not_called()
        self.assertEqual(dispatch(self.path, send=True, transport=transport)["sent"], 1)
        self.assertEqual(dispatch(self.path, send=True, transport=transport)["sent"], 0)
        self.assertEqual(transport.call_count, 1)

    def test_failed_delivery_is_bounded(self):
        self.publish(self.environment())
        transport = Mock(side_effect=OSError("offline"))
        for _ in range(5):
            dispatch(self.path, send=True, transport=transport)
        self.assertEqual(transport.call_count, 3)
        self.assertEqual(
            self.scalar("SELECT status FROM alert_notifications"), "FAILED"
        )

    def test_notification_history_admin_only(self):
        self.assertEqual(
            self.client.get("/api/notifications", headers=self.headers).status_code, 200
        )
        self.assertEqual(
            self.client.get(
                "/api/notifications", headers={"Authorization": "Bearer " + self.nurse}
            ).status_code,
            403,
        )

    def test_network_diagnostics_validation(self):
        message = dict(
            device_id="PB01",
            seq=1,
            boot_id="lab",
            wifi_rssi=-65,
            ip_address="192.168.1.25",
        )
        store_message("pillbox/PB01/heartbeat", message, self.path)
        self.assertEqual(
            self.scalar("SELECT wifi_rssi FROM devices WHERE device_id='PB01'"), -65
        )
        for field, value in [
            ("wifi_rssi", -999),
            ("wifi_rssi", True),
            ("ip_address", "bad"),
        ]:
            with self.assertRaises(ValueError):
                validate_message("pillbox/PB01/heartbeat", {**message, field: value})

    def test_family_cannot_control_device_even_with_valid_key(self):
        response = self.client.post(
            "/api/devices/PB01/commands",
            json={"command": "CLEAR_ALERT"},
            headers={"Authorization": "Bearer " + self.family},
        )
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
