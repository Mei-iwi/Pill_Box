import json
import logging
import math
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

from .care_service import (
    apply_refill_ack,
    resolve_alerts,
    update_alerts,
    validate_refill_open,
)
from .db import connect, utc_now
from .mqtt_config import configure_mqtt

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
    "REFILL_OPEN",
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
    if "utc_synced" in message and not isinstance(message["utc_synced"], bool):
        raise ValueError("invalid UTC synchronization flag")
    if "refill_session_id" in message and (
        not isinstance(message["refill_session_id"], str)
        or len(message["refill_session_id"]) != 32
        or any(c not in "0123456789abcdef" for c in message["refill_session_id"])
    ):
        raise ValueError("invalid refill session ID")
    if (
        kind == "event"
        and message.get("event") == "REFILL_OPEN"
        and (
            message.get("schema_version") != 2
            or message.get("occurrence_id") is not None
            or "refill_session_id" not in message
        )
    ):
        raise ValueError(
            "refill events require session identity and no medication occurrence"
        )
    for key, maximum in (
        ("uptime_ms", 4294967295),
        ("device_local_minute", 1439),
        ("device_epoch_local", 4102444800),
    ):
        if key in message and (
            type(message[key]) is not int or not 0 <= message[key] <= maximum
        ):
            raise ValueError("invalid " + key)
    if "boot_id" in message and (
        not isinstance(message["boot_id"], str)
        or not 1 <= len(message["boot_id"]) <= 120
    ):
        raise ValueError("invalid boot_id")
    for key in ("state", "device_state"):
        if key in message and message[key] not in ("IDLE", "REMINDING", "ALERT"):
            raise ValueError("invalid " + key)
    if "storage_status" in message and message["storage_status"] not in (
        "PENDING",
        "WARNING",
        "NORMAL",
        "SENSOR_ERROR",
    ):
        raise ValueError("invalid storage_status")
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


def store_message(topic, message, db_path=None, registered_only=False):
    message = validate_message(topic, message)
    with connect(db_path) as db:
        if (
            registered_only
            and not db.execute(
                "SELECT 1 FROM devices WHERE device_id=?", (message["device_id"],)
            ).fetchone()
        ):
            raise ValueError("device must be provisioned before MQTT access")
        _store_message(topic, message, db)


def touch_device(db, message, state=None, status="online", storage=None):
    """Update live fields without letting a queued old event rewind newer state."""
    current = db.execute(
        "SELECT * FROM devices WHERE device_id=?", (message["device_id"],)
    ).fetchone()
    boot = message.get("boot_id")
    seq = message.get("seq")
    uptime = message.get("uptime_ms")
    new_boot = bool(boot and boot != current["boot_id"])
    fresh = new_boot or (
        seq >= (current["last_seq"] or 0)
        if seq is not None
        else uptime is None
        or current["device_uptime_ms"] is None
        or uptime >= current["device_uptime_ms"]
    )
    fields = {"last_seen": utc_now()}
    if fresh:
        fields["status"] = status
        if new_boot:
            db.execute(
                "UPDATE refill_sessions SET status='CLOSED' WHERE device_id=? AND boot_id!=? AND status IN ('PENDING','ACTIVE')",
                (message["device_id"], boot),
            )
            fields.update(
                boot_id=boot,
                last_seq=0,
                state=None,
                storage_status="PENDING",
                device_uptime_ms=None,
                device_local_minute=None,
                device_epoch_local=None,
                utc_synced=0,
            )
        if seq is not None:
            fields["last_seq"] = seq
        if state is not None:
            fields["state"] = state
        if storage is not None:
            fields["storage_status"] = storage
        for key, column in (
            ("uptime_ms", "device_uptime_ms"),
            ("utc_synced", "utc_synced"),
            ("device_local_minute", "device_local_minute"),
            ("device_epoch_local", "device_epoch_local"),
            ("queue_depth", "queue_depth"),
            ("queue_dropped", "queue_dropped"),
        ):
            if key in message:
                fields[column] = message[key]
    db.execute(
        "UPDATE devices SET "
        + ",".join(key + "=?" for key in fields)
        + " WHERE device_id=?",
        (*fields.values(), message["device_id"]),
    )


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
        touch_device(
            db,
            message,
            state=message.get("state"),
            status=message.get("status", "online"),
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
                if pending["command"] in ("BEGIN_REFILL", "END_REFILL"):
                    result = apply_refill_ack(db, message, pending)
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
        if message["event"] == "REFILL_OPEN":
            validate_refill_open(db, message)
        storage = {
            "STORAGE_WARNING": "WARNING",
            "STORAGE_NORMAL": "NORMAL",
            "SENSOR_ERROR": "SENSOR_ERROR",
        }.get(message["event"])
        touch_device(db, message, state=message.get("device_state"), storage=storage)
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
        if inserted and message["event"] == "REFILL_OPEN":
            db.execute(
                "UPDATE medication_events SET refill_session_id=? WHERE event_id=?",
                (message["refill_session_id"], message["event_id"]),
            )
            db.execute(
                "UPDATE refill_sessions SET opened_count=opened_count+1,last_opened_at=? WHERE session_id=?",
                (utc_now(), message["refill_session_id"]),
            )
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
        if inserted:
            update_alerts(db, message)
    elif kind == "environment":
        touch_device(
            db,
            message,
            storage=message.get(
                "storage_status", "SENSOR_ERROR" if not message["sensor_ok"] else None
            ),
        )
        current = db.execute(
            "SELECT boot_id,last_seq FROM devices WHERE device_id=?", (device_id,)
        ).fetchone()
        if current["last_seq"] == message["seq"] and (
            not message.get("boot_id") or current["boot_id"] == message["boot_id"]
        ):
            storage = message.get("storage_status")
            if message["sensor_ok"] and storage != "SENSOR_ERROR":
                resolve_alerts(db, device_id, ["SENSOR_ERROR"])
            if storage == "NORMAL":
                resolve_alerts(db, device_id, ["STORAGE_WARNING", "SENSOR_ERROR"])
            elif storage in ("WARNING", "SENSOR_ERROR") or not message["sensor_ok"]:
                update_alerts(
                    db,
                    {
                        **message,
                        "event": "SENSOR_ERROR"
                        if not message["sensor_ok"] or storage == "SENSOR_ERROR"
                        else "STORAGE_WARNING",
                        "slot_id": 0,
                    },
                )
        sampled = message.get("sampled_epoch_local", 0)
        sampled_at = (
            datetime.fromtimestamp(sampled, timezone.utc)
            .replace(tzinfo=timezone(timedelta(hours=7)))
            .isoformat()
            if sampled
            else None
        )
        db.execute(
            """INSERT INTO environment_readings(device_id, temperature_c, humidity_percent, sensor_ok, received_at,sampled_at,boot_id,seq,storage_status)
                     VALUES (?, ?, ?, ?, ?,?,?,?,?)""",
            (
                device_id,
                message.get("temperature_c") if message["sensor_ok"] else None,
                message.get("humidity_percent") if message["sensor_ok"] else None,
                int(message["sensor_ok"]),
                utc_now(),
                sampled_at,
                message.get("boot_id"),
                message["seq"],
                message.get("storage_status"),
            ),
        )


def on_message(client, userdata, message):
    try:
        parsed = validate_message(message.topic, message.payload)
        store_message(
            message.topic,
            parsed,
            userdata.get("db_path"),
            userdata.get("registered_only", False),
        )
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
    configure_mqtt(client)
    import os

    client.user_data_set(
        {
            "db_path": db_path,
            "registered_only": os.getenv("PILLBOX_DEPLOYMENT") == "care"
            or os.getenv("PILLBOX_REQUIRE_REGISTERED_DEVICES") == "1",
        }
    )
    client.on_message = on_message
    client.on_connect = on_connect
    client.reconnect_delay_set(min_delay=1, max_delay=15)
    client.connect_async(host, port, 60)
    client.loop_start()
    return client
