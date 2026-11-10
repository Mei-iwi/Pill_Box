import json
import logging
import math
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

from .db import connect, utc_now

LOGGER = logging.getLogger(__name__)
EVENTS = {
    "REMINDER_STARTED",
    "TAKEN_ON_TIME",
    "TAKEN_LATE",
    "MISSED",
    "WRONG_SLOT",
    "STORAGE_WARNING",
    "STORAGE_NORMAL",
    "SENSOR_ERROR",
    "UNSCHEDULED_OPEN",
    "AMBIGUOUS_OPEN",
}
TOPIC_KINDS = {"status", "event", "environment", "heartbeat"}


def validate_message(topic, payload):
    parts = topic.split("/")
    if (
        len(parts) != 3
        or parts[0] != "pillbox"
        or not parts[1]
        or any(c in parts[1] for c in "+#")
        or parts[2] not in TOPIC_KINDS
    ):
        raise ValueError("invalid topic")
    try:
        message = json.loads(payload) if isinstance(payload, (str, bytes)) else payload
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid JSON") from exc
    if not isinstance(message, dict) or message.get("device_id") != parts[1]:
        raise ValueError("invalid device_id")
    kind = parts[2]
    if "seq" in message and (
        type(message["seq"]) is not int or not 0 <= message["seq"] <= 4294967295
    ):
        raise ValueError("invalid seq")
    if kind in {"status", "heartbeat"}:
        for key in (
            "state",
            "status",
            "boot_id",
            "command_id",
            "command",
            "command_result",
        ):
            if key in message and (
                not isinstance(message[key], str) or len(message[key]) > 120
            ):
                raise ValueError("invalid " + key)
        if "schedules" in message and (
            not isinstance(message["schedules"], list) or len(message["schedules"]) > 16
        ):
            raise ValueError("invalid schedules")
        for key in ("queue_depth", "queue_dropped"):
            if key in message and (type(message[key]) is not int or message[key] < 0):
                raise ValueError("invalid " + key)
    if kind in {"event", "environment", "heartbeat"} and (
        type(message.get("seq")) is not int or not 0 <= message["seq"] <= 4294967295
    ):
        raise ValueError("missing integer seq")
    if kind == "event":
        if (
            not isinstance(message.get("event"), str)
            or message.get("event") not in EVENTS
        ):
            raise ValueError("unknown event")
        if type(message.get("slot_id")) is not int or not 0 <= message["slot_id"] <= 3:
            raise ValueError("invalid slot")
        if type(message.get("schema_version", 1)) is not int or message.get(
            "schema_version", 1
        ) not in (1, 2):
            raise ValueError("invalid schema version")
        if message.get("schema_version") == 2:
            for key in ("boot_id", "event_id", "device_time_quality"):
                if (
                    not isinstance(message.get(key), str)
                    or not 1 <= len(message[key]) <= 120
                ):
                    raise ValueError("invalid " + key)
            for key in ("scheduled_at", "occurred_at"):
                value = message.get(key)
                if value is None and message["device_time_quality"] == "unsynchronized":
                    continue
                try:
                    if datetime.fromisoformat(value).utcoffset() is None:
                        raise ValueError("timezone required")
                except (TypeError, ValueError) as exc:
                    raise ValueError("invalid " + key) from exc
            if message["event"] in {
                "REMINDER_STARTED",
                "MISSED",
                "TAKEN_ON_TIME",
                "TAKEN_LATE",
                "WRONG_SLOT",
            }:
                if not isinstance(message.get("schedule_id"), str) or not isinstance(
                    message.get("occurrence_id"), str
                ):
                    raise ValueError("missing occurrence identity")
                if not message["occurrence_id"].startswith(
                    parts[1] + ":" + message["schedule_id"] + ":"
                ):
                    raise ValueError("occurrence context mismatch")
            if (
                type(message.get("delay_minutes", 0)) is not int
                or not 0 <= message.get("delay_minutes", 0) <= 1440
            ):
                raise ValueError("invalid delay")
    if kind == "environment":
        epoch = message.get("sampled_epoch_local", 0)
        if type(epoch) is not int or not 0 <= epoch <= 4102444800:
            raise ValueError("invalid sampled epoch")
        if not isinstance(message.get("sensor_ok"), bool):
            raise ValueError("invalid sensor_ok")
        if message["sensor_ok"]:
            for key, low, high in (
                ("temperature_c", -40, 80),
                ("humidity_percent", 0, 100),
            ):
                value = message.get(key)
                if (
                    type(value) not in (int, float)
                    or not low <= value <= high
                    or not math.isfinite(value)
                ):
                    raise ValueError("invalid " + key)
    return message


def store_message(topic, message, db_path=None):
    message = validate_message(topic, message)
    with connect(db_path) as db:
        _store_message(topic, message, db)


def _store_message(topic, message, db):
    kind = topic.split("/")[-1]
    device_id = message["device_id"]
    if (
        kind == "event"
        and message.get("schema_version") == 2
        and message["event"]
        in {"REMINDER_STARTED", "MISSED", "TAKEN_ON_TIME", "TAKEN_LATE", "WRONG_SLOT"}
    ):
        schedule = db.execute(
            "SELECT slot_id FROM schedules WHERE device_id=? AND schedule_id=?",
            (device_id, message["schedule_id"]),
        ).fetchone()
        if not schedule or (
            message["event"] != "WRONG_SLOT"
            and schedule["slot_id"] != message["slot_id"]
        ):
            raise ValueError("schedule not assigned to event device/slot")
    db.execute("INSERT OR IGNORE INTO devices(device_id) VALUES (?)", (device_id,))
    if kind in {"status", "heartbeat"}:
        db.execute(
            "UPDATE devices SET status=?, state=COALESCE(?,state), last_seen=?, last_seq=COALESCE(?,last_seq),boot_id=COALESCE(?,boot_id),queue_depth=COALESCE(?,queue_depth),queue_dropped=COALESCE(?,queue_dropped) WHERE device_id=?",
            (
                message.get("status", "online"),
                message.get("state"),
                utc_now(),
                message.get("seq"),
                message.get("boot_id"),
                message.get("queue_depth"),
                message.get("queue_dropped"),
                device_id,
            ),
        )
        if message.get("command_id") and message.get("command_result") in (
            "APPLIED",
            "REJECTED",
        ):
            pending = db.execute(
                "SELECT * FROM command_requests WHERE command_id=? AND device_id=? AND status='PENDING'",
                (message["command_id"], device_id),
            ).fetchone()
            if pending and pending["command"] == message.get("command"):
                result = message["command_result"]
                if pending["command"] == "UPDATE_SCHEDULE" and result == "APPLIED":
                    wanted = json.loads(pending["payload"])
                    matching = [
                        s
                        for s in message.get("schedules", [])
                        if isinstance(s, dict)
                        and all(
                            s.get(k) == wanted[k]
                            for k in ("schedule_id", "hour", "minute", "enabled")
                        )
                    ]
                    if not matching:
                        result = "INVALID_ACK"
                    else:
                        db.execute(
                            "UPDATE schedules SET hour=?,minute=?,enabled=? WHERE device_id=? AND schedule_id=?",
                            (
                                wanted["hour"],
                                wanted["minute"],
                                int(wanted["enabled"]),
                                device_id,
                                wanted["schedule_id"],
                            ),
                        )
                db.execute(
                    "UPDATE command_requests SET status=?,ack_at=? WHERE command_id=?",
                    (result, utc_now(), message["command_id"]),
                )
    elif kind == "event":
        db.execute(
            "UPDATE devices SET last_seen=?, last_seq=? WHERE device_id=?",
            (utc_now(), message["seq"], device_id),
        )
        inserted = db.execute(
            """INSERT OR IGNORE INTO medication_events
            (device_id, seq, event, slot_id, schedule_id, scheduled_minute, occurred_minute, delay_minutes, received_at,
             event_id,boot_id,occurrence_id,schema_version,scheduled_at,occurred_at,device_time_quality)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?,?,?,?,?,?,?,?)""",
            (
                device_id,
                message["seq"],
                message["event"],
                message["slot_id"],
                message.get("schedule_id"),
                message.get("scheduled_minute"),
                message.get("occurred_minute"),
                message.get("delay_minutes", 0),
                utc_now(),
                message.get("event_id"),
                message.get("boot_id", "legacy"),
                message.get("occurrence_id"),
                message.get("schema_version", 1),
                message.get("scheduled_at"),
                message.get("occurred_at"),
                message.get("device_time_quality", "legacy"),
            ),
        ).rowcount
        outcomes = {
            "REMINDER_STARTED": "PENDING",
            "MISSED": "MISSED",
            "TAKEN_ON_TIME": "ON_TIME",
            "TAKEN_LATE": "LATE",
        }
        if inserted and message.get("occurrence_id") and message["event"] in outcomes:
            outcome = outcomes[message["event"]]
            db.execute(
                """INSERT INTO schedule_occurrences(occurrence_id,device_id,schedule_id,slot_id,scheduled_at,current_outcome,confirmed_at,delay_minutes,last_event_at)
                VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(occurrence_id) DO UPDATE SET
                current_outcome=excluded.current_outcome,confirmed_at=excluded.confirmed_at,
                delay_minutes=excluded.delay_minutes,last_event_at=excluded.last_event_at
                WHERE schedule_occurrences.current_outcome NOT IN ('ON_TIME','LATE')
                AND (excluded.current_outcome IN ('ON_TIME','LATE') OR
                     (excluded.current_outcome='MISSED' AND schedule_occurrences.current_outcome='PENDING'))""",
                (
                    message["occurrence_id"],
                    device_id,
                    message["schedule_id"],
                    message["slot_id"],
                    message.get("scheduled_at"),
                    outcome,
                    message.get("occurred_at")
                    if outcome in ("ON_TIME", "LATE")
                    else None,
                    message.get("delay_minutes", 0),
                    message.get("occurred_at"),
                ),
            )
    elif kind == "environment":
        sampled = message.get("sampled_epoch_local", 0)
        sampled_at = (
            datetime.fromtimestamp(sampled, timezone.utc)
            .replace(tzinfo=timezone(timedelta(hours=7)))
            .isoformat()
            if sampled
            else None
        )
        db.execute(
            """INSERT INTO environment_readings(device_id, temperature_c, humidity_percent, sensor_ok, received_at,sampled_at)
                     VALUES (?, ?, ?, ?, ?,?)""",
            (
                device_id,
                message.get("temperature_c") if message["sensor_ok"] else None,
                message.get("humidity_percent") if message["sensor_ok"] else None,
                int(message["sensor_ok"]),
                utc_now(),
                sampled_at,
            ),
        )


def on_message(client, userdata, message):
    try:
        parsed = validate_message(message.topic, message.payload)
        store_message(message.topic, parsed, userdata.get("db_path"))
    except ValueError as exc:
        LOGGER.warning("Rejected MQTT message: %s", exc)
    except sqlite3.Error:
        LOGGER.exception("MQTT message could not be committed to SQLite")


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
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=client_id or f"pillbox-gateway-{uuid.uuid4().hex[:10]}",
    )
    client.user_data_set({"db_path": db_path})
    client.on_message = on_message
    client.on_connect = on_connect
    client.reconnect_delay_set(min_delay=1, max_delay=15)
    client.connect_async(host, port, 60)
    client.loop_start()
    return client
