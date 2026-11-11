"""Create local access keys once, then show them when needed. Never ships secrets."""

import argparse
import json
import os
import secrets
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .config import load_environment, project_path

DEFAULT_PATH = Path(__file__).parent / "auth.local.json"


def create_accounts(path=DEFAULT_PATH):
    path = Path(path)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8-sig"))
    records = {}
    for actor, role, devices in [
        ("ADMIN01", "admin", [f"PB{i:02}" for i in range(1, 7)]),
        ("NURSE_A", "nurse", ["PB01", "PB02", "PB03"]),
        ("NURSE_B", "nurse", ["PB04", "PB05", "PB06"]),
        ("FAMILY01", "family", ["PB01"]),
    ]:
        records[secrets.token_urlsafe(18)] = dict(
            actor_id=actor, role=role, devices=devices
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as source:
        json.dump(records, source, ensure_ascii=False, indent=2)
    return records


def main():
    load_environment()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["create", "show"])
    parser.add_argument(
        "--file", default=os.getenv("PILLBOX_AUTH_FILE") or str(DEFAULT_PATH)
    )
    parser.add_argument(
        "--rotate", action="store_true", help="Back up and replace existing keys"
    )
    args = parser.parse_args()
    args.file = str(project_path(args.file))
    if args.action == "create":
        path = Path(args.file)
        if args.rotate and path.exists():
            folder = (
                DEFAULT_PATH.parent
                / "data"
                / "backups"
                / datetime.now(timezone.utc).strftime("accounts-%Y%m%dT%H%M%S%fZ")
            )
            folder.mkdir(parents=True)
            shutil.copy2(path, folder / "auth.local.json")
            path.unlink()
        create_accounts(args.file)
        print(
            f"Accounts ready: {args.file}. Use 'python -m gateway.accounts show' to view keys."
        )
    else:
        records = json.loads(Path(args.file).read_text(encoding="utf-8-sig"))
        for key, identity in records.items():
            print(
                f"{identity['actor_id']} | {identity['role']} | {','.join(identity['devices'])} | {key}"
            )


if __name__ == "__main__":
    main()
