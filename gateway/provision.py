"""Register a new box explicitly; never overwrite an existing assignment."""

import argparse
import re

from .db import connect, init_db


def provision(path, device_id, patient_id, label):
    if (
        not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", device_id)
        or not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", patient_id)
        or not isinstance(label, str)
        or not 1 <= len(label) <= 120
    ):
        raise ValueError(
            "device/patient IDs require 1-32 letters, digits, underscores or hyphens"
        )
    init_db(path)
    with connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        if db.execute(
            "SELECT 1 FROM devices WHERE device_id=?", (device_id,)
        ).fetchone():
            raise ValueError("device already exists; existing records were kept")
        db.execute(
            "INSERT OR IGNORE INTO patients(patient_id,display_name) VALUES (?,?)",
            (patient_id, label),
        )
        db.execute(
            "INSERT INTO devices(device_id,patient_id) VALUES (?,?)",
            (device_id, patient_id),
        )
        for slot, med in [(1, "MED001"), (2, "MED002"), (3, "MED003")]:
            db.execute(
                "INSERT INTO slot_assignments(device_id,slot_id,patient_id,medication_code) VALUES (?,?,?,?)",
                (device_id, slot, patient_id, med),
            )
        for suffix, slot, hour in [
            ("S1", 1, 8),
            ("S2", 1, 14),
            ("S3", 2, 9),
            ("S4", 3, 20),
        ]:
            db.execute(
                "INSERT INTO schedules(schedule_id,device_id,slot_id,medication_code,hour,minute,on_time_window_minutes,late_tracking_window_minutes) VALUES (?,?,?,?,?,0,15,240)",
                (
                    device_id + "_" + suffix,
                    device_id,
                    slot,
                    {1: "MED001", 2: "MED002", 3: "MED003"}[slot],
                    hour,
                ),
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--device", required=True)
    parser.add_argument("--patient", required=True)
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    provision(args.db, args.device, args.patient, args.label)
    print(
        f'Registered {args.device}. Set PILLBOX_DEVICE_ID="{args.device}" and PILLBOX_SCHEDULE_PREFIX="{args.device}_". Configure broker ACL and API assignments separately.'
    )


if __name__ == "__main__":
    main()
