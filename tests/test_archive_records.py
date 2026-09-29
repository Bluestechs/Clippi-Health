import json
import re
import sqlite3
import tempfile
import unittest
import zipfile
from email.message import EmailMessage
from pathlib import Path

import archive_records


SCHEMA = """
CREATE TABLE documents(
  id INTEGER PRIMARY KEY, source TEXT, org TEXT, kind TEXT, date TEXT, title TEXT,
  author TEXT, dept TEXT, encounter_id INTEGER, parent_id INTEGER, text TEXT, path TEXT,
  format TEXT, source_id TEXT, provenance TEXT);
CREATE TABLE sources(
  key TEXT PRIMARY KEY, org TEXT, kind TEXT, system TEXT, method TEXT, path TEXT,
  exported_at TEXT, coverage_from TEXT, coverage_to TEXT, record_counts TEXT, gaps TEXT, notes TEXT);
"""


class Helpers:
    def __init__(self, root):
        self.root = root.resolve()

    @staticmethod
    def insert(db, table, **row):
        columns = ', '.join(row)
        marks = ', '.join('?' for _ in row)
        return db.execute(f'INSERT INTO {table} ({columns}) VALUES ({marks})', list(row.values())).lastrowid

    def rel(self, path):
        return str(Path(path).resolve().relative_to(self.root))

    @staticmethod
    def html_to_text(text):
        return re.sub(r'<[^>]+>', '', text).strip()

    @staticmethod
    def pdf_text(_path):
        return 'PDF text'


def message(subject, body='Body text', attachment=False):
    item = EmailMessage()
    item['From'] = 'Doctor Example <doctor@example.test>'
    item['To'] = 'Patient <patient@example.test>'
    item['Date'] = 'Tue, 12 May 2026 10:30:00 -0500'
    item['Subject'] = subject
    item['Message-ID'] = f'<{subject.lower().replace(" ", "-")}@example.test>'
    item.set_content(body)
    if attachment:
        item.add_attachment(b'Attached note', maintype='text', subtype='plain', filename='note.txt')
    return item


class ArchiveRecordTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.imports = self.root / 'raw' / 'imports'
        self.imports.mkdir(parents=True)
        self.db = sqlite3.connect(':memory:')
        self.db.executescript(SCHEMA)
        self.hp = Helpers(self.root)

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def test_classifies_supported_and_outlook_members(self):
        kinds = archive_records.archive_kinds(['Takeout/Mail/Health.mbox', 'Outlook/archive.pst', 'docs/report.pdf'])
        self.assertEqual(kinds['supported'], ['.mbox', '.pdf'])
        self.assertEqual(kinds['outlook'], ['.pst'])

    def test_email_calendar_date_is_not_shifted_by_utc_conversion(self):
        item = message('Late message')
        item.replace_header('Date', 'Tue, 12 May 2026 23:30:00 -0500')
        date, instant = archive_records.message_when(item)
        self.assertEqual(date, '2026-05-12')
        self.assertTrue(instant.startswith('2026-05-13T04:30'))

    def test_ingests_eml_message_attachment_and_document_from_zip(self):
        path = self.imports / 'selected-mail.zip'
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('mail/message.eml', message('Treatment update', attachment=True).as_bytes())
            archive.writestr('documents/2026-05-13-note.txt', 'Follow-up document')

        totals = archive_records.ingest_archives(self.db, self.root, self.hp)

        self.assertEqual(len(totals), 1)
        counts = next(iter(totals.values()))
        self.assertEqual(counts, {'messages': 1, 'attachments': 1, 'documents': 1, 'unsupported': 0, 'errors': 0})
        rows = self.db.execute('SELECT kind,date,title,text,path FROM documents ORDER BY id').fetchall()
        self.assertEqual(rows[0][:4], ('message', '2026-05-12', 'Treatment update', 'Body text'))
        self.assertEqual(rows[1][:4], ('attachment', '2026-05-12', 'note.txt', 'Attached note'))
        self.assertEqual(rows[2][:4], ('document', '2026-05-13', '2026-05-13-note.txt', 'Follow-up document'))
        self.assertTrue(all(row[4].startswith('raw/imports/selected-mail.zip#') for row in rows))
        source = self.db.execute('SELECT system,method,coverage_from,coverage_to,record_counts FROM sources').fetchone()
        self.assertEqual(source[0], 'User-selected local email/document ZIP')
        self.assertIn('No account or service access', source[1])
        self.assertEqual(source[2:4], ('2026-05-12', '2026-05-13'))
        self.assertEqual(json.loads(source[4])['messages'], 1)

    def test_ingests_gmail_style_mbox_member(self):
        mbox = b'From doctor@example.test Tue May 12 10:30:00 2026\n' + message('MBOX message').as_bytes() + b'\n\n'
        path = self.imports / 'takeout.zip'
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('Takeout/Mail/Health.mbox', mbox)

        totals = archive_records.ingest_archives(self.db, self.root, self.hp)

        self.assertEqual(next(iter(totals.values()))['messages'], 1)
        self.assertEqual(self.db.execute("SELECT title FROM documents WHERE kind='message'").fetchone()[0], 'MBOX message')

    def test_records_unsupported_outlook_member_without_parsing_it(self):
        path = self.imports / 'outlook.zip'
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('mail/export.pst', b'not parsed')

        totals = archive_records.ingest_archives(self.db, self.root, self.hp)

        self.assertEqual(next(iter(totals.values()))['unsupported'], 1)
        self.assertEqual(self.db.execute('SELECT count(*) FROM documents').fetchone()[0], 0)
        gaps = json.loads(self.db.execute('SELECT gaps FROM sources').fetchone()[0])
        self.assertEqual(gaps['unsupported_members'], ['mail/export.pst'])


if __name__ == '__main__':
    unittest.main()
