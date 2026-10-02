"""Tidepool export parsing: units, delivered insulin, day assignment, dedup."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import healthpilot as hp
from tidepool_records import ingest_tidepool, parse_tidepool_data

SCHEMA = """
CREATE TABLE vitals_daily(date TEXT, metric TEXT, value REAL, min REAL, max REAL, n INTEGER, unit TEXT,
  PRIMARY KEY(date, metric));
CREATE TABLE device_samples(date TEXT, time TEXT, kind TEXT, value REAL, unit TEXT, detail REAL);
CREATE TABLE sources(key TEXT PRIMARY KEY, org TEXT, kind TEXT, system TEXT, method TEXT, path TEXT,
  exported_at TEXT, coverage_from TEXT, coverage_to TEXT, record_counts TEXT, gaps TEXT, notes TEXT);
"""


def cbg(value, units="mg/dL", day="2026-09-20", **extra):
    datum = {"type": "cbg", "value": value, "units": units,
             "deviceTime": f"{day}T12:00:00", "time": f"{day}T12:00:00.000Z",
             "id": f"cbg-{value}-{units}-{len(str(extra))}-{day}"}
    datum.update(extra)
    return datum


class TidepoolParseTests(unittest.TestCase):
    def rows(self, items):
        return {(row[0], row[1]): row for row in parse_tidepool_data(items)["rows"]}

    def test_glucose_units_and_unusable_values_never_guessed(self):
        rows = self.rows([cbg(100), cbg(5.5, "mmol/L", id="m"),
                          cbg(90, None, id="nou"), {"type": "cbg", "units": "mg/dL", "id": "nov",
                                                    "deviceTime": "2026-09-20T12:00:00"}])
        glucose = rows[("2026-09-20", "CGM / meter glucose")]
        self.assertEqual(glucose[5], 2)  # n counts only the two usable readings
        self.assertAlmostEqual(glucose[2], round((100 + 5.5 * 18.01559) / 2, 2))
        self.assertEqual(glucose[6], "mg/dL")

    def test_day_prefers_device_time_over_utc_offset(self):
        rows = self.rows([cbg(100, id="d", deviceTime="2026-09-20T23:00:00",
                              time="2026-09-21T03:00:00.000Z", timezoneOffset=-240)])
        self.assertIn(("2026-09-20", "CGM / meter glucose"), rows)
        rows = self.rows([{"type": "cbg", "value": 100, "units": "mg/dL", "id": "o",
                            "time": "2026-09-21T03:00:00.000Z", "timezoneOffset": -240}])
        self.assertIn(("2026-09-20", "CGM / meter glucose"), rows)

    def test_bolus_uses_delivered_not_programmed(self):
        rows = self.rows([{"type": "bolus", "subType": "dual/square", "id": "b",
                            "normal": 3.0, "extended": 2.0, "expectedNormal": 10.0,
                            "expectedExtended": 5.0, "deviceTime": "2026-09-20T12:00:00"}])
        self.assertEqual(rows[("2026-09-20", "Insulin bolus")][2], 5.0)
        self.assertEqual(rows[("2026-09-20", "Insulin")][2], 5.0)

    def test_basal_rate_times_duration_and_suspend_is_zero(self):
        rows = self.rows([
            {"type": "basal", "deliveryType": "scheduled", "id": "s",
             "rate": 1.0, "duration": 3600000, "deviceTime": "2026-09-20T01:00:00"},
            {"type": "basal", "deliveryType": "suspend", "id": "x",
             "rate": 0, "duration": 1800000, "deviceTime": "2026-09-20T02:00:00"},
            {"type": "basal", "deliveryType": "temp", "id": "nodur",
             "rate": 2.0, "deviceTime": "2026-09-20T03:00:00"},
            {"type": "basal", "deliveryType": "temp", "id": "norate",
             "duration": 3600000, "deviceTime": "2026-09-20T04:00:00"},
        ])
        self.assertEqual(rows[("2026-09-20", "Insulin basal")][2], 1.0)

    def test_wizard_carbs_summed(self):
        rows = self.rows([
            {"type": "wizard", "id": "w1", "carbInput": 45, "deviceTime": "2026-09-20T08:00:00"},
            {"type": "wizard", "id": "w2", "carbInput": 15, "deviceTime": "2026-09-20T12:00:00"},
            {"type": "wizard", "id": "w3", "deviceTime": "2026-09-20T18:00:00"},
        ])
        self.assertEqual(rows[("2026-09-20", "Carbs logged")][2], 60)

    def test_ids_dedupe_across_overlapping_exports(self):
        first = [cbg(100, id="same"), cbg(110, id="other")]
        parsed = parse_tidepool_data(first + [cbg(100, id="same")])
        self.assertEqual(parsed["n_datum"], 2)
        self.assertEqual(parsed["type_counts"], {"cbg": 2})

    def test_samples_carry_local_stamps_and_basal_durations(self):
        parsed = parse_tidepool_data([
            cbg(120, id="s1"),
            {"type": "smbg", "id": "s2", "value": 110, "units": "mg/dL",
             "deviceTime": "2026-09-20T07:30:00"},
            {"type": "bolus", "id": "s3", "normal": 4.5, "deviceTime": "2026-09-20T08:10:00"},
            {"type": "basal", "id": "s4", "rate": 0.9, "duration": 1800000,
             "deviceTime": "2026-09-20T08:00:00"},
            {"type": "wizard", "id": "s5", "carbInput": 45, "deviceTime": "2026-09-20T08:05:00"},
        ])
        self.assertEqual(parsed["samples"], [
            ["2026-09-20 07:30", "smbg", 110.0, "mg/dL", None],
            ["2026-09-20 08:00", "basal", 0.9, "U/hr", 1800000.0],
            ["2026-09-20 08:05", "carbs", 45.0, "g", None],
            ["2026-09-20 08:10", "bolus", 4.5, "U", None],
            ["2026-09-20 12:00", "cbg", 120.0, "mg/dL", None],
        ])

    def test_time_in_range_needs_twelve_readings(self):
        many = [cbg(100 + i, id=f"g{i}") for i in range(12)]
        rows = self.rows(many)
        self.assertEqual(rows[("2026-09-20", "Glucose time in range 70–180")][2], 100.0)
        rows = self.rows(many[:11])
        self.assertNotIn(("2026-09-20", "Glucose time in range 70–180"), rows)


class TidepoolIngestTests(unittest.TestCase):
    def test_ingest_writes_vitals_and_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            (root / "raw" / "other").mkdir(parents=True)
            export = [cbg(100, id="a"), cbg(200, id="b"),
                      {"type": "bolus", "id": "c", "normal": 2.5,
                       "deviceTime": "2026-09-20T12:00:00"},
                      {"type": "upload", "id": "u", "deviceManufacturers": ["Dexcom"]}]
            (root / "raw" / "other" / "TidepoolExport.json").write_text(json.dumps(export))
            (root / "raw" / "other" / "TidepoolExport-broken.json").write_text("{not json")
            (root / "raw" / "other" / "notes.json").write_text(json.dumps({"hello": 1}))
            db = sqlite3.connect(":memory:")
            db.executescript(SCHEMA)
            with patch.object(hp, "ROOT", root):
                counts = ingest_tidepool(db, root, hp)
            self.assertEqual(counts["files"], 1)
            self.assertEqual(counts["cbg"], 2)
            metrics = {row[0] for row in db.execute("SELECT metric FROM vitals_daily").fetchall()}
            self.assertIn("CGM / meter glucose", metrics)
            self.assertIn("Insulin bolus", metrics)
            source = db.execute("SELECT key, org, coverage_from FROM sources").fetchone()
            self.assertEqual(source, ("tidepool", "Tidepool", "2026-09-20"))

    def test_ingest_with_no_tidepool_file_returns_empty(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            (root / "raw" / "other").mkdir(parents=True)
            db = sqlite3.connect(":memory:")
            db.executescript(SCHEMA)
            with patch.object(hp, "ROOT", root):
                self.assertEqual(ingest_tidepool(db, root, hp), {})


if __name__ == "__main__":
    unittest.main()
