"""Demo privacy and real-pipeline checks; all fixtures are synthetic."""
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

from demo_data import generate

REPO = Path(__file__).resolve().parent.parent


class DemoDataTests(unittest.TestCase):
    def test_refuses_personal_store_and_symlinks(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "records"
            root.mkdir()
            sentinel = root / "personal.txt"
            sentinel.write_text("Private fixture must remain unchanged")
            with self.assertRaises(ValueError):
                generate(root)
            self.assertEqual(sentinel.read_text(), "Private fixture must remain unchanged")
            self.assertEqual(list(root.iterdir()), [sentinel])
            if os.name != "nt":
                link = Path(temp) / "link"
                link.symlink_to(root, target_is_directory=True)
                with self.assertRaises(ValueError):
                    generate(link)

    def test_generated_inputs_build_searchable_populated_record(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "demo"
            generate(root, date(2026, 9, 29))
            env = {**os.environ, "CLIPPI_HEALTH_ROOT": str(root), "CLIPPI_HEALTH_RESOURCES": str(REPO)}
            result = subprocess.run([sys.executable, str(REPO / "healthpilot.py")], cwd=root,
                                    env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            dashboard = (root / "dashboard.html").read_text(encoding="utf-8")
            self.assertIn('<img class="brand-logo" src="data:image/png;base64,', dashboard)
            self.assertNotIn("__LOGO_BASE64__", dashboard)
            with sqlite3.connect(root / "data/health.db") as db:
                patient = json.loads(db.execute("SELECT value FROM meta WHERE key='patient'").fetchone()[0])
                self.assertEqual((patient["firstName"], patient["lastName"]), ("Sally", "Seastar"))
                self.assertEqual(db.execute("SELECT count(*) FROM labs_clean").fetchone()[0], 108)
                for table in ("documents", "encounters", "conditions", "procedures", "medications", "immunizations", "allergies", "events"):
                    self.assertGreater(db.execute(f"SELECT count(*) FROM {table}").fetchone()[0], 0)
                glucose = db.execute("SELECT value,min,max,n FROM vitals_daily WHERE metric='CGM / meter glucose'").fetchall()
                self.assertEqual(len(glucose), 365)
                self.assertTrue(all(low < value < high and n == 288 for value, low, high, n in glucose))
                self.assertGreater(len({r[0] for r in glucose}), 300)
                self.assertEqual(db.execute("SELECT count(*) FROM vitals_daily WHERE metric='Glucose time in range 70–180'").fetchone()[0], 365)
                for metric in ("Insulin basal", "Insulin bolus"):
                    self.assertEqual(db.execute("SELECT count(*) FROM vitals_daily WHERE metric=?", [metric]).fetchone()[0], 365)
                self.assertGreater(db.execute("SELECT count(*) FROM documents_fts WHERE documents_fts MATCH 'diabetes'").fetchone()[0], 5)
            page = (root / "dashboard.html").read_text(encoding="utf-8")
            self.assertIn('"demo":true', page)
            self.assertIn('"lastName":"Seastar"', page)
            self.assertNotIn(str(REPO), page)
            self.assertNotIn(str(root), page)
            # Rebuild does not change edits; explicitly starting a fresh demo restores samples.
            notes = root / "case_study_notes.md"
            notes.write_text("Temporary fictional edit")
            generate(root, date(2026, 9, 29))
            self.assertIn("Sally Seastar", notes.read_text())


if __name__ == "__main__":
    unittest.main()
