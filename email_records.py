"""Local, provenance-preserving import of exported correspondence and OCR evidence.

Only directories with healthpilot-source.json are loaded. The exporter/OCR tool is
not executed, and message content is never treated as an instruction.
"""
import csv
import hashlib
import json
import re
from email import policy
from email.parser import BytesParser
from email.utils import parseaddr
from pathlib import Path

LAB_FIELDS = (
    'collected_datetime reported_datetime lab_vendor ordering_provider specimen_id panel '
    'test result units reference_range flag performing_lab_code notes uncertain row_type '
    'verification_status email_date email_sender email_folder source_file source_page page_id'
).split()
SCHEMA = """
CREATE TABLE email_lab_evidence(
  id INTEGER PRIMARY KEY, source TEXT, source_id TEXT UNIQUE,
  document_id INTEGER, lab_id INTEGER, import_status TEXT, possible_duplicate_lab_ids TEXT,
""" + ',\n'.join(f'  {name} TEXT' for name in LAB_FIELDS) + "\n);\n"


def read_csv(path):
    with path.open(newline='', encoding='utf-8-sig') as fh:
        return list(csv.DictReader(fh))


def within(base, name):
    path = (base / name).resolve()
    path.relative_to(base.resolve())
    if not path.exists():
        raise ValueError(f'Missing email source file: {path}')
    return path


def current_message(body):
    """Conservatively split explicit reply/forward headers; retain full text separately."""
    markers = [
        r'(?m)^[^\S\r\n]*On [^\n]*(?:\n[^\n]*){0,5}?wrote:[^\n]*$',
        r'(?mi)^[^\S\r\n]*-+\s*(?:Original Message|Forwarded message)\s*-+[^\n]*$',
        r'(?mi)^[^\S\r\n]*Begin forwarded message:[^\n]*$',
        r'(?m)^[^\S\r\n]*>.*$',
        r'(?mi)^[^\S\r\n]*From:[^\n]+\n(?:[^\n]*\n){0,3}[^\S\r\n]*(?:Sent|Date):',
    ]
    boundaries = [m.start() for pat in markers if (m := re.search(pat, body))]
    return body[:min(boundaries)].strip() if boundaries else body.strip()


def message_category(entry, timeline):
    category = timeline.get('event')
    if category and category != 'correspondence':
        return category
    subject = entry['subject']
    if re.search(r'payment|receipt|superbill|account|pricing|price increase', subject, re.I):
        return 'billing / administration'
    if re.search(r'appointment (?:rescheduled|scheduled|reminder|today)|intake form', subject, re.I):
        return 'scheduling / intake'
    if re.search(r'vaccine registration|nutritional counseling services|year-end reminder|happy birthday|automatic reply', subject, re.I):
        return 'practice notice / marketing'
    return 'correspondence'


def numeric_range(text):
    s = (text or '').replace('–', '-').replace('−', '-')
    number = r'(-?\d+(?:\.\d+)?)'
    match = re.fullmatch(r'\s*' + number + r'\s*-\s*' + number + r'\s*', s)
    if match:
        return float(match[1]), float(match[2])
    match = re.fullmatch(r'\s*([<>])(?:=|\s*OR\s*=)?\s*' + number + r'\s*', s, re.I)
    if match:
        return (None, float(match[2])) if match[1] == '<' else (float(match[2]), None)
    return None, None


def lab_status(row):
    # Derivative summaries and risk-summary badges remain evidence, not extra measurements.
    if (row['uncertain'].strip() or '[?' in row['result'] or '[illegible]' in row['result']
            or row['verification_status'] not in {'VERIFIED', 'CORRECTED'}):
        return 'review_required'
    if row['row_type'] != 'lab_report':
        return 'secondary_evidence'
    if not re.match(r'^\d{4}-\d{2}-\d{2}(?:$|[ T])', row['collected_datetime']):
        return 'collection_date_missing'
    if row['result'].strip().upper() in {'TNO', 'DNR', 'NOT PERFORMED', 'NOT ORDERED', ''}:
        return 'not_performed'
    if 'INFLAMMATION SUMMARY' in row['panel'].upper() or 'trend table' in row['notes'].lower():
        return 'report_summary'
    if row['test'] == 'REFLEXIVE URINE CULTURE' or row['result'].upper().startswith('SEE NOTE'):
        return 'report_comment'
    return 'primary_result'


def primary_lab(row, source, attachment, hp):
    name = row['test']
    panel = row['panel'].upper()
    # Specimen context matters: urinary WBC/glucose must not become blood tests.
    if 'URINALYSIS' in panel:
        name = name + ', URINE'
    elif panel == 'CULTURE, URINE, ROUTINE' and name == 'Result':
        name = 'Urine culture'
    unit_raw = row['units']
    unit = hp.clean_unit(unit_raw)
    test, group, canonical_unit = hp.canonical_test(name, unit=unit)
    value, comparator = hp.parse_value(row['result'].replace('≤', '<=').replace('≥', '>='))
    lo, hi = numeric_range(row['reference_range'])
    # Do not invent units absent from a source or label an unconverted value with new units.
    if value is not None and unit:
        value, new_unit = hp.convert_unit(value, unit, canonical_unit)
        if new_unit != unit:
            lo = hp.convert_unit(lo, unit, canonical_unit)[0]
            hi = hp.convert_unit(hi, unit, canonical_unit)[0]
        unit = new_unit
    date, collected_at = hp.parse_when(row['collected_datetime'])
    flag = {'H': 'High', 'L': 'Low', 'A': 'Abnormal'}.get(row['flag'].strip().upper())
    return dict(
        source=source, org=row['lab_vendor'], order_name=row['panel'], result_type='LAB',
        date=date, collected_at=collected_at, test=test, test_group=group, test_raw=row['test'],
        value_text=row['result'], value_num=value, comparator=comparator, units=unit,
        units_raw=unit_raw, ref_low=lo, ref_high=hi, ref_text=row['reference_range'], flag=flag,
        comment=row['notes'], lab=row['performing_lab_code'], provider=row['ordering_provider'],
        source_file=hp.rel(attachment),
        provenance='Lab report transcribed by supplied OCR export; ' + row['verification_status'] +
                   '; specimen ' + row['specimen_id'] + '; page ' + row['source_page'] +
                   '; see email_lab_evidence for verbatim source fields.')


def possible_duplicates(db, lab):
    """Quarantine plausible repeats when date/unit metadata prevent exact deduplication.

    This does not decide which source date is correct or merge adjacent-day measurements.
    The original evidence and candidate links remain available for review.
    """
    found = []
    query = """SELECT id,date,value_num,value_text,units,comparator FROM labs
        WHERE source NOT LIKE 'email-%' AND lower(test)=lower(?)
        AND abs(julianday(date)-julianday(?)) <= 1 ORDER BY id"""
    for lid, date, value, text, unit, comparator in db.execute(query, [lab['test'], lab['date']]):
        unit = (unit or '').strip()
        current_unit = (lab['units'] or '').strip()
        if unit != current_unit and unit and current_unit:
            continue  # Known different units must never be compared without conversion.
        if (comparator or '') != (lab['comparator'] or ''):
            continue
        if value is not None and lab['value_num'] is not None:
            same = round(value, 4) == round(lab['value_num'], 4)
        elif value is None and lab['value_num'] is None:
            same = (text or '').strip().casefold() == (lab['value_text'] or '').strip().casefold()
        else:
            same = False
        if same:
            if date == lab['date'] and unit == current_unit:
                return []  # An exact match takes precedence over neighboring-day candidates.
            found.append(lid)
    return found


def ingest_exports(db, root, hp):
    totals = {}
    for config_path in sorted((root / 'email').glob('*/healthpilot-source.json')):
        export = config_path.parent
        config = json.loads(config_path.read_text(encoding="utf-8-sig"))
        source, org = config['key'], config['org']
        if not source.startswith('email-'):
            raise ValueError('Email source keys must start with email-')
        patients = {x.lower() for x in config.get('patient_addresses', [])}
        index = read_csv(export / 'index.csv')
        timeline = {r['folder']: r for r in read_csv(export / 'timeline.csv')} if (export / 'timeline.csv').exists() else {}
        counts = dict(messages=0, attachments=0, quoted_correspondence=0, reference_documents=0,
                      lab_evidence=0, primary_lab_rows=0, possible_duplicate_rows=0)
        attachments = {}
        seen = set()
        for entry in index:
            msg_id = entry['gmail_message_id']
            if not msg_id or msg_id in seen:
                raise ValueError(f'Missing/duplicate message id in {export}: {msg_id}')
            seen.add(msg_id)
            folder = within(export, entry['folder'])
            original = within(folder, 'original.eml')
            markdown = within(folder, 'message.md')
            raw = markdown.read_text(encoding="utf-8", errors="replace")
            if '\n---\n' not in raw:
                raise ValueError(f'Missing message/body separator: {markdown}')
            body = raw.split('\n---\n', 1)[1].strip()
            message = BytesParser(policy=policy.default).parsebytes(original.read_bytes(), headersonly=True)
            sender = str(message.get('From') or entry['sender'])
            patient = parseaddr(sender)[1].lower() in patients
            author = 'Me' if patient else sender
            new_text = current_message(body)
            t = timeline.get(entry['folder'], {})
            provenance = json.dumps(dict(
                type='local_email_export', message_id=msg_id, thread_id=entry['thread_id'],
                email_datetime=entry['date'], sender=sender, recipient=str(message.get('To', '')),
                direction=t.get('direction') or ('patient sent' if patient else 'received correspondence'),
                category=message_category(entry, t), appointment=t.get('appointment', ''),
                gmail_link=entry['gmail_link'], export_folder=hp.rel(folder),
                text_source=hp.rel(markdown), original_sha256=hashlib.sha256(original.read_bytes()).hexdigest(),
                extraction='Current text before explicit reply/forward header; full export preserved.',
            ), ensure_ascii=False)
            doc_id = hp.insert(db, 'documents', source=source, org=org, kind='message',
                date=entry['date'][:10], title=entry['subject'], author=sender,
                text=f"— {author}, {entry['date']}\n\n{new_text or '[No new body text; see original and attachments.]'}",
                path=hp.rel(original), format='eml', source_id='gmail:' + msg_id, provenance=provenance)
            counts['messages'] += 1
            if new_text != body:
                hp.insert(db, 'documents', source=source, org=org, kind='attachment', date=entry['date'][:10],
                    title='Quoted correspondence: ' + entry['subject'], author='Multiple correspondents; see headers',
                    parent_id=doc_id, text='Full exported correspondence, including earlier quoted messages. '
                    'Statements belong to the authors identified by the embedded headers; the date below is '
                    'the enclosing email date.\n\n' + raw,
                    path=hp.rel(markdown), format='md', source_id=f'gmail:{msg_id}:quoted',
                    provenance=json.dumps(dict(json.loads(provenance),
                        original_sha256=hashlib.sha256(markdown.read_bytes()).hexdigest(),
                        extraction='Full exported email text with embedded reply/forward headers.'), ensure_ascii=False))
                counts['quoted_correspondence'] += 1
            for path in sorted(folder.iterdir()):
                if path.suffix.lower() not in {'.pdf', '.jpg', '.jpeg', '.png', '.tif', '.tiff', '.heic', '.docx'}:
                    continue
                path = within(folder, path.name)
                sidecar = next((p for p in (path.with_suffix('.ocr.md'), path.with_suffix('.extracted.txt')) if p.exists()), None)
                # Preserve originals even when there is no supplied transcription.
                text = sidecar.read_text(encoding="utf-8", errors="replace") if sidecar else '[No text sidecar supplied; open the original attachment.]'
                method = 'supplied OCR transcription (uncertain readings retained)' if sidecar and sidecar.name.endswith('.ocr.md') else 'supplied text extraction' if sidecar else 'metadata only'
                aid = hp.insert(db, 'documents', source=source, org=org, kind='attachment',
                    date=entry['date'][:10], title=path.name, author='See attachment', parent_id=doc_id,
                    text='Attachment to email dated ' + entry['date'] + '. This is the transmission date; '
                         'clinical and collection dates are in the attachment.\nText: ' + method + '.\n\n' + text,
                    path=hp.rel(path), format=path.suffix.lstrip('.').lower(),
                    source_id=f'gmail:{msg_id}:attachment:{path.name}',
                    provenance=json.dumps(dict(type=method, text_source=hp.rel(sidecar) if sidecar else None,
                        original_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                        review_file=hp.rel(export / 'OCR_REVIEW.md'), enclosing_message_id=msg_id)))
                attachments[(entry['folder'], path.name)] = (aid, path)
                counts['attachments'] += 1
        for name in ('INDEX.md', 'TIMELINE.md', 'OCR_REVIEW.md'):
            path = export / name
            if path.exists():
                hp.insert(db, 'documents', source=source, org=org, kind='document',
                    title=f'{org} — {name}', author='Export/transcription index',
                    text='Export aid, not a clinician-authored assessment. Appointment notifications '
                         'do not establish that a visit occurred.\n\n' + path.read_text(encoding="utf-8", errors="replace"),
                    path=hp.rel(path), format='md', source_id=f'{source}:{name}',
                    provenance='Supplied local export index, chronology or OCR review notes; dates appear in text.')
                counts['reference_documents'] += 1
        if (export / 'labs.csv').exists():
            for number, row in enumerate(read_csv(export / 'labs.csv'), start=2):
                if set(LAB_FIELDS) - row.keys():
                    raise ValueError(f'Incomplete lab columns: {export}/labs.csv')
                attachment_id, path = attachments[(row['email_folder'], row['source_file'])]
                sid = f'{source}:labs.csv:{number}'
                status = lab_status(row)
                lab_id = None
                candidates = []
                if status == 'primary_result':
                    lab = primary_lab(row, source, path, hp)
                    candidates = possible_duplicates(db, lab)
                    if candidates:
                        status = 'possible_duplicate'
                        counts['possible_duplicate_rows'] += 1
                    else:
                        lab_id = hp.insert(db, 'labs', source_id=sid, **lab)
                        counts['primary_lab_rows'] += 1
                hp.insert(db, 'email_lab_evidence', source=source, source_id=sid,
                    document_id=attachment_id, lab_id=lab_id, import_status=status,
                    possible_duplicate_lab_ids=json.dumps(candidates),
                    **{field: row[field] for field in LAB_FIELDS})
                counts['lab_evidence'] += 1
        dates = [r['date'][:10] for r in index]
        hp.insert(db, 'sources', key=source, org=org, kind='email', system='Local Gmail correspondence export',
            method='index.csv + original.eml + message.md; attachment .ocr.md/.extracted.txt; labs.csv retained in email_lab_evidence. No online access.',
            path=hp.rel(export), exported_at='unknown', coverage_from=min(dates) if dates else None, coverage_to=max(dates) if dates else None,
            record_counts=json.dumps(counts), gaps=json.dumps({'summary': 'Only supplied export contents; referenced attachments may be absent.'}),
            notes='Email dates are transmission dates. Office sender identity does not establish clinician authorship; '
            'signatures remain in text. Patient text and quoted history are distinguished. Only dated, verified/corrected '
            'primary lab rows enter labs; letters, historical reprints, images, uncertain readings, unperformed tests and '
            'risk summaries remain in email_lab_evidence. Possible duplicates with adjacent dates or missing units '
            'are held for review with candidate links, not merged or charted as new results. OCR verification is export metadata, not independent medical verification.')
        totals[source] = counts
    return totals
