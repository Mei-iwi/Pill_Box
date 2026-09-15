import json
import logging
import uuid

from .db import connect, utc_now

LOGGER = logging.getLogger(__name__)
EVENTS = {"REMINDER_STARTED", "TAKEN_ON_TIME", "TAKEN_LATE", "MISSED", "WRONG_SLOT", "STORAGE_WARNING"}
TOPIC_KINDS = {"status", "event", "environment", "heartbeat"}


def validate_message(topic, payload):
    parts = topic.split("/")
    if len(parts) != 3 or parts[0] != "pillbox" or parts[1] == "+" or parts[2] not in TOPIC_KINDS:
        raise ValueError("invalid topic")
    try:
        message = json.loads(payload) if isinstance(payload, (str, bytes)) else payload
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid JSON") from exc
    if not isinstance(message, dict) or message.get("device_id") != parts[1]:
        raise ValueError("invalid device_id")
    kind = parts[2]
    if kind in {"event", "environment", "heartbeat"} and not isinstance(message.get("seq"), int):
        raise ValueError("missing integer seq")
    if kind == "event":
        if message.get("event") not in EVENTS:
            raise ValueError("unknown event")
        if not isinstance(message.get("slot_id"), int) or not 0 <= message["slot_id"] <= 3:
            raise ValueError("invalid slot")
    if kind == "environment":
        if not isinstance(message.get("sensor_ok"), bool):
            raise ValueError("invalid sensor_ok")
    return message


def store_message(topic, message, db_path=None):
    kind = topic.split("/")[-1]
    db = connect(db_path)
    device_id = message["device_id"]
    db.execute("INSERT OR IGNORE INTO devices(device_id) VALUES (?)", (device_id,))
    if kind in {"status", "heartbeat"}:
        db.execute("UPDATE devices SET status=?, state=?, last_seen=?, last_seq=? WHERE device_id=?",
                   (message.get("status", "online"), message.get("state"), utc_now(), message.get("seq", 0), device_id))
    elif kind == "event":
        db.execute("UPDATE devices SET last_seen=?, last_seq=? WHERE device_id=?", (utc_now(), message["seq"], device_id))
        db.execute("""INSERT OR IGNORE INTO medication_events
            (device_id, seq, event, slot_id, schedule_id, scheduled_minute, occurred_minute, delay_minutes, received_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""", (device_id, message["seq"], message["event"], message["slot_id"],
            message.get("schedule_id"), message.get("scheduled_minute"), message.get("occurred_minute"),
            message.get("delay_minutes", 0), utc_now()))
    elif kind == "environment":
        db.execute("""INSERT INTO environment_readings(device_id, temperature_c, humidity_percent, sensor_ok, received_at)
                     VALUES (?, ?, ?, ?, ?)""", (device_id, message.get("temperature_c"), message.get("humidity_percent"),
                     int(message["sensor_ok"]), utc_now()))
    db.commit()
    db.close()


def on_message(client, userdata, message):
    try:
        parsed = validate_message(message.topic, message.payload)
        store_message(message.topic, parsed, userdata.get("db_path"))
    except ValueError as exc:
        LOGGER.warning("Rejected MQTT message: %s", exc)


def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code != 0:
        LOGGER.warning("MQTT connection rejected: %s", reason_code)
        return
    for kind in TOPIC_KINDS:
        client.subscribe(f"pillbox/+/{kind}", qos=1)


def publish_command(client, device_id, command):
    if client is None or not client.is_connected():
        return False
    topic = f"pillbox/{device_id}/command"
    payload = json.dumps(command, separators=(",", ":"), sort_keys=True)
    result = client.publish(topic, payload, qos=1)
    return result.rc == 0


def start_mqtt(db_path, host, port, client_id=None):
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        LOGGER.warning("paho-mqtt not installed; MQTT listener disabled")
        return None
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id or f"pillbox-gateway-{uuid.uuid4().hex[:10]}")
    client.user_data_set({"db_path": db_path})
    client.on_message = on_message
    client.on_connect = on_connect
    client.reconnect_delay_set(min_delay=1, max_delay=15)
    client.connect_async(host, port, 60)
    client.loop_start()
    return client
