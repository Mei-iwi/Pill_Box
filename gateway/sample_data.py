"""Pseudonymous care configurations; no fabricated measurements or dose history."""

DEVICE_IDS = tuple(f"PB{i:02}" for i in range(1, 7))


def seed_care_dataset(db):
    db.execute("INSERT INTO app_settings VALUES ('dataset_profile','care-training-v1')")
    catalog = [
        ("MED001", "Vitamin C"),
        ("MED002", "Vitamin D3"),
        ("MED003", "Canxi"),
        ("MED004", "Vitamin B12"),
    ]
    db.executemany("INSERT INTO medication_catalog VALUES (?,?)", catalog)
    for i, device in enumerate(DEVICE_IDS, 1):
        patient = f"P{i:03}"
        label = f"Khu {'A' if i <= 3 else 'B'} · Phòng {100 + i} · Hồ sơ {i:02}"
        db.execute("INSERT INTO patients VALUES (?,?)", (patient, label))
        db.execute(
            "INSERT INTO devices(device_id,patient_id) VALUES (?,?)", (device, patient)
        )
        meds = (
            ("MED001", "MED002", "MED003")
            if i == 1
            else tuple(catalog[(i + j) % 4][0] for j in range(3))
        )
        for slot, med in enumerate(meds, 1):
            db.execute(
                "INSERT INTO slot_assignments(device_id,slot_id,patient_id,medication_code) VALUES (?,?,?,?)",
                (device, slot, patient, med),
            )
        # PB01 stays compatible with the checked-in Wokwi firmware.
        for n, (slot, hour, minute) in enumerate(
            [(1, 8, 0), (1, 14, 0), (2, 9, 0), (3, 20, 0)], 1
        ):
            sid = f"S{n}" if i == 1 else f"{device}_S{n}"
            offset = 0 if i == 1 else (i - 1) * 5
            db.execute(
                "INSERT INTO schedules(schedule_id,device_id,slot_id,medication_code,hour,minute,on_time_window_minutes,late_tracking_window_minutes) VALUES (?,?,?,?,?,?,15,240)",
                (sid, device, slot, meds[slot - 1], hour, minute + offset),
            )
