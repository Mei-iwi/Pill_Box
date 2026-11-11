"""Back up and reset local application data; never fabricate clinical history.

Profiles are pseudonymous. Catalog names are everyday examples, schedules are
configurations rather than prescriptions. No measurements/confirmations are seeded.
"""

import argparse
from datetime import datetime, timezone
from pathlib import Path

from .db import connect, init_db, seed_defaults

DATA_ROOT = (Path(__file__).parent / "data").resolve()
TABLES = (
    "alerts",
    "refill_sessions",
    "refill_verifications",
    "refill_audit_logs",
    "command_requests",
    "schedule_occurrences",
    "medication_events",
    "medication_events_legacy",
    "environment_readings",
    "schedules",
    "slot_assignments",
    "medication_catalog",
    "devices",
    "patients",
    "app_settings",
)


def reset_data(path, realistic=False):
    target = Path(path).resolve()
    if not target.is_relative_to(DATA_ROOT) or target.suffix != ".db":
        raise ValueError("Only .db files inside gateway/data can be reset")
    backup = None
    if target.exists():
        backup = (
            DATA_ROOT
            / "backups"
            / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            / target.name
        )
        backup.parent.mkdir(parents=True, exist_ok=True)
        with connect(target) as source, connect(backup) as destination:
            source.backup(destination)
    init_db(target)
    with connect(target) as db:
        db.execute("BEGIN IMMEDIATE")
        existing = {
            row[0]
            for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        for table in TABLES:
            if table in existing:
                db.execute(f"DELETE FROM {table}")
        if realistic:
            from .sample_data import seed_care_dataset

            seed_care_dataset(db)
        else:
            seed_defaults(db)
    return backup


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", action="append", required=True)
    parser.add_argument("--realistic", action="store_true")
    args = parser.parse_args()
    for item in args.db:
        saved = reset_data(item, realistic=args.realistic)
        print(f"Reset: {Path(item).resolve()} | Backup: {saved or 'new database'}")
