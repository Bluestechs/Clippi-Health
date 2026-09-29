"""C-CDA ZIP ingestion tests with a synthetic MyChart-style IHE XDM package."""
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import healthpilot


DOCUMENT = """<?xml version="1.0" encoding="UTF-8"?>
<ClinicalDocument xmlns="urn:hl7-org:v3">
  <id root="synthetic-document"/>
  <title>Synthetic Visit Summary</title>
  <effectiveTime value="20260928"/>
  <custodian><assignedCustodian><representedCustodianOrganization><name>BJC HealthCare</name></representedCustodianOrganization></assignedCustodian></custodian>
  <component><structuredBody><component><section>
    <title>Results</title><text><paragraph>Synthetic result text.</paragraph></text>
  </section></component></structuredBody></component>
</ClinicalDocument>
"""


class CcdaZipTests(unittest.TestCase):
    def test_mychart_zip_is_ingested_without_unpacking(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            raw = root / "raw"
            folder = raw / "other"
            folder.mkdir(parents=True)
            archive_path = folder / "mychart-record.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("download/IHE_XDM/SUBSET01/DOC0001.XML", DOCUMENT)

            db = sqlite3.connect(":memory:")
            db.executescript(healthpilot.SCHEMA)
            with patch.multiple(healthpilot, ROOT=root, RAW=raw):
                self.assertEqual(healthpilot.ingest_all_ccda(db), 1)
            source = db.execute("SELECT key, org, path FROM sources").fetchone()
            document = db.execute("SELECT title, path, text FROM documents").fetchone()
            self.assertEqual(source, ("ccda-bjc-healthcare", "BJC HealthCare", "raw/other/mychart-record.zip"))
            self.assertEqual(document[0], "Synthetic Visit Summary")
            self.assertIn("mychart-record.zip!/download/IHE_XDM/SUBSET01/DOC0001.XML", document[1])
            self.assertIn("Synthetic result text", document[2])


if __name__ == "__main__":
    unittest.main()
