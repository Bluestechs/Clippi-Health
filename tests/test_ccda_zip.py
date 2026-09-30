"""C-CDA ZIP ingestion tests with a synthetic MyChart-style IHE XDM package."""
import sqlite3
import tempfile
import unittest
import zipfile
from xml.etree import ElementTree
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
    def test_coded_visit_note_projects_documented_encounter(self):
        visit = DOCUMENT.replace(
            '<title>Synthetic Visit Summary</title>',
            '<title>Synthetic Visit Note</title><code code="34133-9" codeSystem="2.16.840.1.113883.6.1"/>',
        ).replace(
            '<effectiveTime value="20260928"/>',
            '<effectiveTime value="20260928"/><componentOf><encompassingEncounter>'
            '<id root="synthetic-visit"/><effectiveTime><low value="20260927"/></effectiveTime>'
            '<code code="AMB" displayName="Ambulatory visit"/></encompassingEncounter></componentOf>',
        )
        db = sqlite3.connect(':memory:')
        db.executescript(healthpilot.SCHEMA)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'note.xml'
            path.write_text(visit)
            with patch.object(healthpilot, 'ROOT', Path(directory).resolve()):
                self.assertEqual(healthpilot.ingest_ccda(db, ElementTree.fromstring(visit),
                                                       path, 'ccda-example', 'Example Health'), 1)
        self.assertEqual(db.execute('SELECT date,type,source_id FROM encounters').fetchone(),
                         ('2026-09-27', 'Ambulatory visit', 'synthetic-visit'))
        self.assertEqual(db.execute('SELECT kind,date,encounter_id FROM documents').fetchone(),
                         ('note', '2026-09-27', 1))

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
