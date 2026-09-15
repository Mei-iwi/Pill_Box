# MQTT contract

Topics:

- `pillbox/PB01/status`
- `pillbox/PB01/event`
- `pillbox/PB01/environment`
- `pillbox/PB01/heartbeat`
- `pillbox/PB01/command`
- `pillbox/PB01/config`

Event payload contains `device_id`, `event`, `slot_id`, `schedule_id`, `scheduled_minute`, `occurred_minute`, `delay_minutes` and monotonic `seq`. The Gateway validates device/topic/event/slot and rejects malformed JSON. Repeated `(device_id, seq)` events are ignored by SQLite uniqueness.

Allowed commands are `CLEAR_ALERT`, `REQUEST_STATUS`, and `UPDATE_SCHEDULE`. Unknown commands are rejected. Gateway normalizes payloads and publishes with QoS 1 to `pillbox/<device_id>/command` only while connected.

## Demo broker

The verified endpoint is `test.mosquitto.org:1883` without credentials. It is a public test service: never publish patient data, secrets, or anything sensitive. Production firmware reads host/port from ignored `Secrets.h`; the Wokwi build and Gateway environment use the same endpoint.

Gateway uses asynchronous reconnect, so Flask startup does not crash when the broker is temporarily offline.
