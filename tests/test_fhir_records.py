"""Synthetic FHIR fixtures only; no personal records."""
import base64
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import fhir_records
import healthpilot as hp


class FhirImportTests(unittest.TestCase):
    def test_bulk_export_is_retained_and_common_resources_are_projected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            folder = root / "raw" / "fhir" / "example"
            folder.mkdir(parents=True)
            (folder / "healthpilot-source.json").write_text(json.dumps({"key": "fhir-example", "org": "Example Health"}))
            resources = [
                {"resourceType": "Patient", "id": "p1", "name": [{"given": ["Alex"], "family": "Example"}], "birthDate": "1980-01-02"},
                {"resourceType": "Observation", "id": "lab1", "category": [{"coding": [{"code": "laboratory"}]}],
                 "code": {"coding": [{"system": "http://loinc.org", "code": "5631-7", "display": "Copper"}]},
                 "effectiveDateTime": "2026-01-03T09:30:00-06:00", "valueQuantity": {"value": 75, "unit": "mcg/dL"},
                 "referenceRange": [{"low": {"value": 70}, "high": {"value": 140}}]},
                {"resourceType": "Observation", "id": "vital1", "category": [{"coding": [{"code": "vital-signs"}]}],
                 "code": {"text": "Heart rate"}, "valueQuantity": {"value": 70, "unit": "bpm"}},
                {"resourceType": "Condition", "id": "c1", "code": {"text": "Example condition"}, "recordedDate": "2025-02-03"},
                {"resourceType": "Encounter", "id": "e1", "type": [{"text": "Office visit"}],
                 "period": {"start": "2025-02-03T10:00:00Z"}, "serviceProvider": {"display": "Example Clinic"}},
                {"resourceType": "MedicationRequest", "id": "m1", "medicationCodeableConcept": {"text": "Example 5 mg tablet"},
                 "authoredOn": "2025-02-03", "dosageInstruction": [{"text": "Take once daily"}]},
                {"resourceType": "Immunization", "id": "i1", "vaccineCode": {"text": "Example vaccine"},
                 "occurrenceDateTime": "2024-10-01"},
                {"resourceType": "Procedure", "id": "pr1", "code": {"text": "Example procedure"},
                 "performedDateTime": "2025-05-06"},
                {"resourceType": "AllergyIntolerance", "id": "a1", "code": {"text": "Example allergen"},
                 "reaction": [{"manifestation": [{"text": "Rash"}], "severity": "mild"}]},
                {"resourceType": "DiagnosticReport", "id": "dr1", "code": {"text": "Example imaging"},
                 "effectiveDateTime": "2025-06-07", "conclusion": "No acute finding."},
                {"resourceType": "Binary", "id": "b1", "contentType": "text/plain",
                 "data": base64.b64encode(b"Synthetic clinical document").decode()},
                {"resourceType": "DocumentReference", "id": "d1", "date": "2025-07-08",
                 "description": "Outside note", "content": [{"attachment": {"url": "Binary/b1", "contentType": "text/plain"}}]},
                {"resourceType": "Goal", "id": "g1", "description": {"text": "Unsupported but retained"}},
            ]
            export = folder / "records.jsonl"
            export.write_text("\n".join(json.dumps(resource) for resource in resources) + "\n")

            db = sqlite3.connect(":memory:")
            db.executescript(hp.SCHEMA)
            with patch.multiple(hp, ROOT=root, DATA=root / "data"):
                totals = fhir_records.ingest_exports(db, root, hp)

            self.assertEqual(totals["fhir-example"]["fhir_resources"], len(resources))
            self.assertEqual(db.execute("SELECT count(*) FROM fhir_resources").fetchone()[0], len(resources))
            self.assertEqual(db.execute("SELECT count(*) FROM labs").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT test,value_num,units,date FROM labs").fetchone(),
                             ("Copper", 75.0, "mcg/dL", "2026-01-03"))
            self.assertEqual(db.execute("SELECT name FROM conditions").fetchone()[0], "Example condition")
            self.assertEqual(db.execute("SELECT type,dept FROM encounters").fetchone(), ("Office visit", "Example Clinic"))
            self.assertEqual(db.execute("SELECT name,sig FROM medications").fetchone(),
                             ("Example 5 mg tablet", "Take once daily"))
            self.assertEqual(db.execute("SELECT count(*) FROM documents").fetchone()[0], 2)
            self.assertIn("Synthetic clinical document", db.execute(
                "SELECT text FROM documents WHERE source_id='d1'").fetchone()[0])
            self.assertEqual(json.loads(db.execute("SELECT value FROM meta WHERE key='patient'").fetchone()[0])["firstName"], "Alex")
            self.assertEqual(db.execute("SELECT json_extract(json, '$.description.text') FROM fhir_resources "
                                        "WHERE resource_type='Goal'").fetchone()[0], "Unsupported but retained")

    def test_bundle_entries_receive_distinct_resource_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bundle.ndjson"
            path.write_text(json.dumps({"resourceType": "Bundle", "entry": [
                {"resource": {"resourceType": "Patient", "id": "one"}},
                {"resource": {"resourceType": "Patient", "id": "two"}},
            ]}) + "\n")
            rows = list(fhir_records.iter_resources(path))
            self.assertEqual([key for key, _ in rows], ["bundle.ndjson:1:0", "bundle.ndjson:1:1"])


if __name__ == "__main__":
    unittest.main()
