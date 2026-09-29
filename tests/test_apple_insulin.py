"""Delivery-reason preservation and source-consistent daily insulin totals."""
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import healthpilot as hp


class InsulinTests(unittest.TestCase):
    def record(self, amount, reason=None, source="Pump", key="HKInsulinDeliveryReason"):
        metadata = f'<MetadataEntry key="{key}" value="{reason}"/>' if reason is not None else ""
        return (f'<Record type="HKQuantityTypeIdentifierInsulinDelivery" value="{amount}" unit="IU" '
                f'startDate="2026-09-20 12:00:00 +0000" sourceName="{source}">{metadata}</Record>')

    def parse(self, records):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "health.zip"
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("apple_health_export/export.xml", "<HealthData>" + "".join(records) + "</HealthData>")
            return {row[1]: row[2] for row in hp.parse_apple_vitals(archive)["rows"]}

    def test_preserves_basal_bolus_and_unspecified(self):
        totals = self.parse([self.record(10, "1"), self.record(2, "2"),
                             self.record(3, "2", key="HKMetadataKeyInsulinDeliveryReason"),
                             self.record(4), self.record(1, "unrecognized")])
        self.assertEqual(totals, {"Insulin": 20, "Insulin basal": 10, "Insulin bolus": 5, "Insulin unspecified": 5})

    def test_does_not_combine_maxima_from_different_sources(self):
        totals = self.parse([self.record(18, "1", "Pump"), self.record(12, "2", "Pump"),
                            self.record(21, "1", "Duplicate feed"), self.record(3, "2", "Duplicate feed")])
        self.assertEqual(totals, {"Insulin": 30, "Insulin basal": 18, "Insulin bolus": 12})

    def test_equal_totals_prefer_the_feed_with_delivery_types(self):
        totals = self.parse([self.record(30, None, "Unspecified feed"),
                            self.record(18, "1", "Pump"), self.record(12, "2", "Pump")])
        self.assertEqual(totals, {"Insulin": 30, "Insulin basal": 18, "Insulin bolus": 12})

    def test_untyped_and_zero_samples_are_not_guessed_or_dropped(self):
        self.assertEqual(self.parse([self.record(5)]), {"Insulin": 5, "Insulin unspecified": 5})
        self.assertEqual(self.parse([self.record(0, "1")]), {"Insulin": 0, "Insulin basal": 0})

    def test_old_cache_is_reparsed(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            archive = directory / "health.zip"
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("apple_health_export/export.xml", "<HealthData>" + self.record(4, "1") + "</HealthData>")
            st = archive.stat()
            (directory / f"apple_vitals_{st.st_size}_{int(st.st_mtime)}.json").write_text(json.dumps({"rows": []}))
            with patch.object(hp, "DATA", directory):
                self.assertIn("Insulin basal", {row[1] for row in hp.apple_vitals(archive)["rows"]})
