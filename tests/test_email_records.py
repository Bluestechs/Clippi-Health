"""Synthetic fixtures only: no personal records or addresses."""
import csv
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import healthpilot as hp
import email_records as er
import reports


def evidence(**overrides):
    row = dict.fromkeys(er.LAB_FIELDS, '')
    row.update(test='COPPER', result='75', units='mcg/dL', collected_datetime='2026-01-02 09:30',
               row_type='lab_report', verification_status='VERIFIED')
    row.update(overrides)
    return row


class EmailImportTests(unittest.TestCase):
    def test_ambiguity_and_secondary_evidence_never_become_primary(self):
        for row in [evidence(row_type='physician_letter'), evidence(row_type='historical'),
                    evidence(row_type='patient_image'), evidence(uncertain='Y'),
                    evidence(result='6.2[?or 6.8]'), evidence(verification_status='NEEDS_HUMAN'),
                    evidence(collected_datetime=''), evidence(result='TNO'),
                    evidence(panel='INFLAMMATION SUMMARY'), evidence(notes='current trend table'),
                    evidence(result='SEE NOTE:')]:
            with self.subTest(row=row):
                self.assertNotEqual(er.lab_status(row), 'primary_result')
        self.assertEqual(er.lab_status(evidence(verification_status='CORRECTED')), 'primary_result')

    def test_quote_split_preserves_sender_attribution(self):
        for boundary in ['On Tue, A Person\n<person@example.test> wrote:',
                         'On Tue, A wrote:', '-----Original Message-----', '> Earlier text',
                         'Begin forwarded message:']:
            self.assertEqual(er.current_message('Office reply.\n\n' + boundary + '\nPatient hypothesis.'), 'Office reply.')
        self.assertEqual(er.current_message('On treatment since Monday.\nNo quoted reply.'),
                         'On treatment since Monday.\nNo quoted reply.')

    def test_specimen_context_units_and_bounds(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(hp, 'ROOT', Path(directory).resolve()):
            p = Path(directory) / 'sample.pdf'
            urine = er.primary_lab(evidence(test='WBC', result='NONE SEEN', units='/HPF',
                panel='URINALYSIS, COMPLETE W/REFLEX TO CULTURE'), 'email-example', p, hp)
            self.assertEqual(urine['test'], 'Urine WBC')
            blood = er.primary_lab(evidence(test='ABSOLUTE NEUTROPHILS', result='2000',
                units='cells/uL', reference_range='1500-7800'), 'email-example', p, hp)
            self.assertEqual((blood['value_num'], blood['units'], blood['ref_low'], blood['ref_high']),
                             (2.0, 'K/uL', 1.5, 7.8))
            bound = er.primary_lab(evidence(result='<5', units=''), 'email-example', p, hp)
            self.assertEqual((bound['comparator'], bound['units']), ('<', ''))

    def test_dedupe_respects_units_bounds_and_source_precedence(self):
        db = sqlite3.connect(':memory:'); db.executescript(hp.SCHEMA)
        ids = []
        for source, units, comparator, date in [('email-example', 'mg/L', None, '2026-01-02'),
                ('apple', 'mg/L', None, '2026-01-02'), ('bjc', 'mg/L', None, '2026-01-02'),
                ('email-example', 'mg/dL', None, '2026-01-02'),
                ('email-example', 'mg/L', '<', '2026-01-02'), ('email-example', 'mg/L', None, None)]:
            ids.append(hp.insert(db, 'labs', source=source, units=units, comparator=comparator,
                                 date=date, test='Example', value_num=5, value_text='5'))
        self.assertEqual(hp.dedupe_labs(db), 2)
        self.assertEqual(db.execute('SELECT dup_of FROM labs WHERE id=?', [ids[0]]).fetchone()[0], ids[2])
        self.assertEqual(hp.dedupe_labs(db), 2)
        self.assertEqual(db.execute('SELECT count(*) FROM labs_clean').fetchone()[0], 4)

    def test_possible_duplicates_keep_date_and_unit_disagreements_out_of_charts(self):
        db = sqlite3.connect(':memory:'); db.executescript(hp.SCHEMA)
        existing = hp.insert(db, 'labs', source='apple', test='Copper', date='2026-01-03',
                             value_num=75, value_text='75', units='mcg/dL')
        lab = dict(test='Copper', date='2026-01-02', value_num=75, value_text='75',
                   units='mcg/dL', comparator=None)
        self.assertEqual(er.possible_duplicates(db, lab), [existing])
        self.assertEqual(er.possible_duplicates(db, dict(lab, comparator='<')), [])
        self.assertEqual(er.possible_duplicates(db, dict(lab, date='2026-01-03')), [])
        self.assertEqual(er.possible_duplicates(db, dict(lab, units='mg/dL')), [])
        self.assertEqual(er.possible_duplicates(db, dict(lab, units='', date='2026-01-03')), [existing])
        self.assertEqual(er.possible_duplicates(db, dict(lab, date='2026-01-05')), [])
        hp.insert(db, 'labs', source='apple', test='Copper', date='2026-01-02',
                  value_num=75, value_text='75', units='mcg/dL')
        self.assertEqual(er.possible_duplicates(db, lab), [])

    def test_administrative_mail_is_searchable_but_not_a_clinician_assessment(self):
        db = sqlite3.connect(':memory:'); db.executescript(hp.SCHEMA)
        for title in ['Year-End Reminder: screening', 'Lab discussion']:
            category = er.message_category({'subject':title}, {})
            hp.insert(db, 'documents', source='email-example', kind='message', date='2026-01-03',
                      title=title, text='— Office, 2026-01-03\n\nPancreas discussion.',
                      provenance=json.dumps({'category':category}))
        matches = reports.clinician_messages(db, {'keywords':['pancreas']})
        self.assertEqual([d['title'] for d, _ in matches], ['Lab discussion'])

    def test_full_import_links_originals_preserves_every_evidence_row_and_rebuilds(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(hp, 'ROOT', Path(directory).resolve()):
            root = Path(directory); ex = root/'email'/'fixture'; msg = ex/'message-one'; msg.mkdir(parents=True)
            (ex/'healthpilot-source.json').write_text(json.dumps(dict(key='email-example', org='Example',
                                                                   patient_addresses=['patient@example.test'])))
            index = dict(date='2026-01-03 10:00', sender='office@example.test', subject='Results',
                         folder='message-one', gmail_message_id='abc123', thread_id='thread123', gmail_link='')
            with (ex/'index.csv').open('w') as fh:
                w = csv.DictWriter(fh, fieldnames=index); w.writeheader(); w.writerow(index)
            (msg/'original.eml').write_text('From: Office <office@example.test>\nTo: patient@example.test\n\nOffice reply.')
            (msg/'message.md').write_text('# Results\n\n---\n\nOffice reply.\n\nOn Tue, Patient wrote:\n> A patient hypothesis.')
            (msg/'sample.pdf').write_bytes(b'Synthetic attachment placeholder')
            (msg/'sample.ocr.md').write_text('Copper: 75; uncertain letter reading: 76[?]')
            (ex/'OCR_REVIEW.md').write_text('Example review item')
            rs = [evidence(email_folder='message-one', source_file='sample.pdf', source_page='1'),
                  evidence(email_folder='message-one', source_file='sample.pdf', source_page='2',
                           row_type='physician_letter', result='76[?]', uncertain='Y', collected_datetime='')]
            with (ex/'labs.csv').open('w') as fh:
                w = csv.DictWriter(fh, fieldnames=er.LAB_FIELDS); w.writeheader(); w.writerows(rs)
            results = []
            for _ in range(2):
                db = sqlite3.connect(':memory:'); db.executescript(hp.SCHEMA)
                results.append(er.ingest_exports(db, root, hp))
                with patch.multiple(reports, DATA=root, ROOT=root, TOPICS_PATH=root/'topics.json'):
                    reports.build_dictionary(db)
                    self.assertIn('email_lab_evidence', (root/'DATA_DICTIONARY.md').read_text())
                for path, provenance in db.execute('SELECT path,provenance FROM documents'):
                    if provenance.startswith('{'):
                        metadata = json.loads(provenance)
                        self.assertEqual(hashlib.sha256((root/path).read_bytes()).hexdigest(), metadata['original_sha256'])
                self.assertEqual(db.execute('SELECT count(*) FROM labs').fetchone()[0], 1)
                self.assertEqual(db.execute('SELECT count(*) FROM email_lab_evidence').fetchone()[0], 2)
                self.assertEqual(db.execute('SELECT count(*) FROM encounters').fetchone()[0], 0)
                self.assertEqual(db.execute('SELECT count(*) FROM medications').fetchone()[0], 0)
                self.assertEqual(db.execute('SELECT count(*) FROM email_lab_evidence e JOIN documents a '
                    'ON e.document_id=a.id JOIN documents m ON a.parent_id=m.id WHERE m.kind="message"').fetchone()[0], 2)
                text = db.execute('SELECT text FROM documents WHERE kind="message"').fetchone()[0]
                self.assertNotIn('patient hypothesis', text)
                db.execute("INSERT INTO documents_fts(documents_fts) VALUES('rebuild')")
                self.assertEqual(db.execute("SELECT count(*) FROM documents_fts WHERE documents_fts MATCH 'hypothesis'").fetchone()[0], 1)
            self.assertEqual(results[0], results[1])
            with self.assertRaises(ValueError):
                er.within(ex, '../../outside')


if __name__ == '__main__':
    unittest.main()
