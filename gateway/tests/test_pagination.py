import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gateway.app import create_app
from gateway.db import connect, init_db
from gateway.reset_data import reset_data


class PaginationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "records.db"
        init_db(self.path)
        self.api = create_app({"DB_PATH": self.path}).test_client()
        with connect(self.path) as db:
            for seq in range(23):
                db.execute(
                    "INSERT INTO medication_events(device_id,seq,event,slot_id,received_at) VALUES ('PB01',?,'UNSCHEDULED_OPEN',1,'2026-11-10T08:00:00+07:00')",
                    (seq,),
                )

    def tearDown(self):
        self.tmp.cleanup()

    def test_pages_have_stable_order_and_no_overlap(self):
        first = self.api.get("/api/devices/PB01/events?page=1&page_size=8").get_json()
        second = self.api.get("/api/devices/PB01/events?page=2&page_size=8").get_json()
        self.assertEqual(
            (first["total"], first["pages"], len(first["items"])), (23, 3, 8)
        )
        self.assertEqual(
            [row["seq"] for row in first["items"]], list(range(22, 14, -1))
        )
        self.assertTrue(
            {row["id"] for row in first["items"]}.isdisjoint(
                row["id"] for row in second["items"]
            )
        )
        self.assertEqual(
            self.api.get("/api/devices/PB01/events?page=999&page_size=8").get_json()[
                "page"
            ],
            3,
        )
        self.assertIsInstance(self.api.get("/api/devices/PB01/events").get_json(), list)

    def test_invalid_and_empty_pagination(self):
        for query in ("page=0", "page=bad", "page_size=0", "page_size=1000"):
            self.assertEqual(
                self.api.get("/api/devices/PB01/events?" + query).status_code, 400
            )
        empty = self.api.get("/api/devices/PB02/events?page=1").get_json()
        self.assertEqual((empty["total"], empty["items"], empty["pages"]), (0, [], 1))

    def test_audit_count_is_scoped_before_pagination(self):
        with connect(self.path) as db:
            for device in ("PB01", "PB02"):
                db.execute(
                    "INSERT INTO refill_audit_logs(actor_id,box_id,patient_id,slot_id,scanned_medication_code,result,timestamp) VALUES ('N01',?,'P001',1,'MED001','VERIFIED','now')",
                    (device,),
                )
        token = "n" * 32
        api = create_app(
            {
                "DB_PATH": self.path,
                "AUTH_IDENTITIES": {
                    token: {"actor_id": "N01", "role": "nurse", "devices": ["PB01"]}
                },
            }
        ).test_client()
        headers = {"Authorization": "Bearer " + token}
        result = api.get("/api/refill/audit?page=1", headers=headers).get_json()
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["box_id"], "PB01")
        self.assertEqual(
            api.get(
                "/api/refill/audit?device_id=PB02&page=1", headers=headers
            ).status_code,
            403,
        )

    def test_reset_preserves_backup_and_starts_with_clean_history(self):
        with patch("gateway.reset_data.DATA_ROOT", Path(self.tmp.name)):
            backup = reset_data(self.path)
        self.assertTrue(backup.exists())
        with connect(backup) as db:
            self.assertEqual(
                db.execute("SELECT count(*) FROM medication_events").fetchone()[0], 23
            )
        with connect(self.path) as db:
            self.assertEqual(
                db.execute("SELECT count(*) FROM medication_events").fetchone()[0], 0
            )
            self.assertEqual(
                db.execute(
                    "SELECT label FROM medication_catalog WHERE medication_code='MED001'"
                ).fetchone()[0],
                "Vitamin C",
            )
            self.assertEqual(
                db.execute("SELECT count(*) FROM environment_readings").fetchone()[0], 0
            )
            self.assertEqual(
                db.execute("SELECT count(*) FROM schedules").fetchone()[0], 5
            )

    def test_reset_rejects_paths_outside_local_data(self):
        with self.assertRaises(ValueError):
            reset_data(self.path)
