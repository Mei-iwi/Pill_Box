import json
import tempfile
import unittest
from pathlib import Path

from gateway.app import create_app
from gateway.db import init_db
from gateway.mqtt_service import validate_message, store_message


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
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close(); init_db(self.tmp.name)
        self.mqtt = FakeMqttClient()
        self.app = create_app({"DB_PATH": self.tmp.name, "MQTT_CLIENT": self.mqtt}).test_client()

    def test_valid_event_and_duplicate(self):
        payload = {"device_id":"PB01","event":"TAKEN_LATE","slot_id":1,"seq":10,"delay_minutes":12}
        store_message("pillbox/PB01/event", payload, self.tmp.name); store_message("pillbox/PB01/event", payload, self.tmp.name)
        result = self.app.get("/api/devices/PB01/events").get_json(); self.assertEqual(len(result), 1)

    def test_invalid_json(self):
        with self.assertRaises(ValueError): validate_message("pillbox/PB01/event", "{")

    def test_unknown_event(self):
        with self.assertRaises(ValueError): validate_message("pillbox/PB01/event", {"device_id":"PB01","event":"NOPE","slot_id":1,"seq":1})

    def test_invalid_slot(self):
        with self.assertRaises(ValueError): validate_message("pillbox/PB01/event", {"device_id":"PB01","event":"MISSED","slot_id":4,"seq":1})

    def test_heartbeat(self):
        store_message("pillbox/PB01/heartbeat", {"device_id":"PB01","status":"online","state":"IDLE","seq":11}, self.tmp.name)
        self.assertEqual(self.app.get("/api/devices/PB01/status").get_json()["status"], "online")

    def test_environment(self):
        store_message("pillbox/PB01/environment", {"device_id":"PB01","temperature_c":28,"humidity_percent":60,"sensor_ok":True,"seq":12}, self.tmp.name)
        self.assertEqual(len(self.app.get("/api/devices/PB01/environment").get_json()), 1)

    def test_refill_verified_and_confirm(self):
        response = self.app.post("/api/refill/verify", json={"actor_id":"NURSE01","box_id":"PB01","slot_id":1,"medication_code":"MED001"})
        self.assertEqual(response.get_json()["result"], "VERIFIED")
        self.assertEqual(self.app.post("/api/refill/confirm", json={"actor_id":"NURSE01","box_id":"PB01","slot_id":1}).status_code, 200)

    def test_refill_mismatch_blocks_confirm(self):
        response = self.app.post("/api/refill/verify", json={"actor_id":"NURSE01","box_id":"PB01","slot_id":1,"medication_code":"MED999"})
        self.assertEqual(response.get_json()["result"], "MEDICATION_MISMATCH")
        self.assertEqual(self.app.post("/api/refill/confirm", json={"actor_id":"NURSE01","box_id":"PB01","slot_id":1}).status_code, 409)

    def test_valid_command_publishes_expected_topic_and_payload(self):
        response = self.app.post("/api/devices/PB01/commands", json={"command":"REQUEST_STATUS", "ignored":"value"})
        self.assertEqual(response.status_code, 202)
        self.assertEqual(self.mqtt.calls, [("pillbox/PB01/command", {"command":"REQUEST_STATUS"}, 1)])

    def test_invalid_command_is_rejected_without_publish(self):
        response = self.app.post("/api/devices/PB01/commands", json={"command":"RUN_ARBITRARY_CODE"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.mqtt.calls, [])

    def test_update_schedule_validates_contract(self):
        invalid = self.app.post("/api/devices/PB01/commands", json={"command":"UPDATE_SCHEDULE", "slot_id":1})
        self.assertEqual(invalid.status_code, 400)
        valid = self.app.post("/api/devices/PB01/commands", json={"command":"UPDATE_SCHEDULE", "slot_id":1, "hour":9, "minute":15, "enabled":True})
        self.assertEqual(valid.status_code, 202)


if __name__ == "__main__": unittest.main()
