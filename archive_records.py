"""Read user-selected email/document ZIP exports without contacting any service.

Archives remain intact under raw/imports/. During a rebuild, supported members are
read into the local documents table. Archive contents are data, never instructions.
"""
import hashlib
import io
import json
import mailbox
import re
import shutil
import tempfile
import zipfile
from datetime import timezone
from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree


EMAIL_EXTENSIONS = {'.eml', '.mbox'}
DOCUMENT_EXTENSIONS = {'.pdf', '.docx', '.html', '.htm', '.txt', '.md', '.xml'}
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.tif', '.tiff', '.heic'}
SUPPORTED_EXTENSIONS = EMAIL_EXTENSIONS | DOCUMENT_EXTENSIONS | IMAGE_EXTENSIONS
UNSUPPORTED_OUTLOOK_EXTENSIONS = {'.pst', '.olm', '.msg'}
MAX_IN_MEMORY_MEMBER = 512 * 1024 * 1024


def archive_digest(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def member_extension(name):
    return PurePosixPath(name).suffix.lower()


def archive_kinds(names):
    """Classify ZIP member names without extracting them."""
    extensions = {member_extension(name) for name in names if name and not name.endswith('/')}
    return {
        'supported': sorted(extensions & SUPPORTED_EXTENSIONS),
        'outlook': sorted(extensions & UNSUPPORTED_OUTLOOK_EXTENSIONS),
    }


def safe_content(part):
    try:
        content = part.get_content()
    except (LookupError, UnicodeDecodeError):
        payload = part.get_payload(decode=True) or b''
        return payload.decode('utf-8', errors='replace')
    return content if isinstance(content, str) else str(content)


def message_body(message, hp):
    body = message.get_body(preferencelist=('plain', 'html'))
    if body is not None:
        text = safe_content(body)
        return hp.html_to_text(text) if body.get_content_type() == 'text/html' else text.strip()
    if message.get_content_maintype() == 'text':
        text = safe_content(message)
        return hp.html_to_text(text) if message.get_content_type() == 'text/html' else text.strip()
    return ''


def message_when(message):
    raw = str(message.get('Date') or '').strip()
    if not raw:
        return None, None
    try:
        parsed = parsedate_to_datetime(raw)
    except (TypeError, ValueError, OverflowError):
        return None, None
    if parsed is None:
        return None, None
    calendar_date = parsed.date().isoformat()
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc)
    return calendar_date, parsed.isoformat(timespec='minutes')


def docx_text(data, hp):
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as package:
            xml = package.read('word/document.xml')
        root = ElementTree.fromstring(xml)
    except (KeyError, zipfile.BadZipFile, ElementTree.ParseError):
        return ''
    paragraphs = []
    for paragraph in root.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'):
        text = ''.join(node.text or '' for node in paragraph.iter(
            '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t'))
        if text.strip():
            paragraphs.append(text.strip())
    return '\n'.join(paragraphs)


def document_text(data, extension, hp):
    if extension == '.pdf':
        with tempfile.NamedTemporaryFile(suffix='.pdf') as temp:
            temp.write(data)
            temp.flush()
            return hp.pdf_text(Path(temp.name))
    if extension == '.docx':
        return docx_text(data, hp)
    if extension in {'.html', '.htm', '.xml'}:
        return hp.html_to_text(data.decode('utf-8', errors='replace'))
    if extension in {'.txt', '.md'}:
        return data.decode('utf-8', errors='replace')
    return '[Image retained in the selected archive; no OCR text was generated.]'


def source_key(path, digest):
    slug = re.sub(r'[^a-z0-9]+', '-', path.stem.lower()).strip('-')[:36] or 'import'
    return f'archive-{slug}-{digest[:10]}'


def archive_ref(hp, archive, member):
    return f'{hp.rel(archive)}#{member}'


def read_member(archive, info):
    if info.file_size > MAX_IN_MEMORY_MEMBER:
        raise ValueError(f'{info.filename} is larger than the 512 MiB per-file limit')
    return archive.read(info)


def insert_attachment(db, source, archive_path, archive_hash, member_name, message_index,
                      part_index, parent_id, email_date, part, counts, hp):
    filename = part.get_filename() or f'attachment-{part_index}'
    extension = Path(filename).suffix.lower()
    payload = part.get_payload(decode=True) or b''
    text = document_text(payload, extension, hp) if extension in DOCUMENT_EXTENSIONS | IMAGE_EXTENSIONS \
        else '[Attachment retained inside the selected email archive; this file type was not text-extracted.]'
    hp.insert(
        db, 'documents', source=source, org=Path(archive_path).stem,
        kind=hp.document_kind_from_filename(filename, 'attachment'), date=email_date,
        title=filename, author=str(part.get('Content-Type') or ''), parent_id=parent_id, text=text,
        path=archive_ref(hp, archive_path, member_name), format=extension.lstrip('.') or 'attachment',
        source_id=f'{source}:{member_name}:message:{message_index}:attachment:{part_index}',
        provenance=json.dumps({
            'type': 'local_archive_email_attachment', 'archive_sha256': archive_hash,
            'archive_member': member_name, 'attachment_filename': filename,
            'enclosing_message_index': message_index,
        }, ensure_ascii=False),
    )
    counts['attachments'] += 1


def insert_message(db, source, archive_path, archive_hash, member_name, message_index, message, counts, hp):
    date, datetime = message_when(message)
    sender = str(message.get('From') or '')
    subject = str(message.get('Subject') or '').strip() or '(no subject)'
    message_id = str(message.get('Message-ID') or '').strip()
    body = message_body(message, hp) or '[No readable message body; see the original archive.]'
    provenance = {
        'type': 'local_archive_email', 'archive_sha256': archive_hash, 'archive_member': member_name,
        'message_index': message_index, 'message_id': message_id or None,
        'email_datetime': datetime, 'sender': sender, 'recipient': str(message.get('To') or ''),
        'extraction': 'Headers and complete readable message body from a user-selected local export.',
    }
    doc_id = hp.insert(
        db, 'documents', source=source, org=Path(archive_path).stem, kind='message', date=date,
        title=subject, author=sender, text=body, path=archive_ref(hp, archive_path, member_name),
        format='eml' if member_extension(member_name) == '.eml' else 'mbox',
        source_id=f'{source}:{member_name}:message:{message_index}',
        provenance=json.dumps(provenance, ensure_ascii=False),
    )
    counts['messages'] += 1
    if date:
        counts['_dates'].append(date)
    for part_index, part in enumerate(message.iter_attachments(), start=1):
        insert_attachment(db, source, archive_path, archive_hash, member_name, message_index,
                          part_index, doc_id, date, part, counts, hp)


def ingest_mbox(db, source, archive_path, archive_hash, archive, info, counts, hp):
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix='.mbox', delete=False) as temp:
            temp_path = Path(temp.name)
            with archive.open(info) as member:
                shutil.copyfileobj(member, temp)
        box = mailbox.mbox(temp_path, create=False, factory=lambda stream: BytesParser(policy=policy.default).parse(stream))
        try:
            for index, message in enumerate(box, start=1):
                insert_message(db, source, archive_path, archive_hash, info.filename, index, message, counts, hp)
        finally:
            box.close()
    finally:
        if temp_path:
            temp_path.unlink(missing_ok=True)


def ingest_archive(db, path, hp):
    digest = archive_digest(path)
    source = source_key(path, digest)
    counts = {'messages': 0, 'attachments': 0, 'documents': 0, 'unsupported': 0, 'errors': 0, '_dates': []}
    unsupported = []
    errors = []
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            if info.is_dir() or info.filename.startswith('__MACOSX/'):
                continue
            extension = member_extension(info.filename)
            try:
                if extension == '.mbox':
                    ingest_mbox(db, source, path, digest, archive, info, counts, hp)
                elif extension == '.eml':
                    message = BytesParser(policy=policy.default).parsebytes(read_member(archive, info))
                    insert_message(db, source, path, digest, info.filename, 1, message, counts, hp)
                elif extension in DOCUMENT_EXTENSIONS | IMAGE_EXTENSIONS:
                    data = read_member(archive, info)
                    title = PurePosixPath(info.filename).name
                    match = re.search(r'\d{4}-\d{2}-\d{2}', title)
                    date = match.group(0) if match else None
                    hp.insert(
                        db, 'documents', source=source, org=path.stem,
                        kind=hp.document_kind_from_filename(title), date=date,
                        title=title, text=document_text(data, extension, hp),
                        path=archive_ref(hp, path, info.filename), format=extension.lstrip('.'),
                        source_id=f'{source}:{info.filename}',
                        provenance=json.dumps({
                            'type': 'local_archive_document', 'archive_sha256': digest,
                            'archive_member': info.filename,
                        }, ensure_ascii=False),
                    )
                    counts['documents'] += 1
                    if date:
                        counts['_dates'].append(date)
                elif extension in UNSUPPORTED_OUTLOOK_EXTENSIONS:
                    unsupported.append(info.filename)
                    counts['unsupported'] += 1
            except (OSError, ValueError, zipfile.BadZipFile, RuntimeError) as exc:
                errors.append(f'{info.filename}: {exc}')
                counts['errors'] += 1

    dates = counts.pop('_dates')
    gap_parts = []
    if unsupported:
        gap_parts.append('Outlook PST/OLM/MSG members were retained but not parsed; export messages as EML files.')
    if errors:
        gap_parts.append('Some archive members could not be read.')
    hp.insert(
        db, 'sources', key=source, org=path.stem, kind='local archive',
        system='User-selected local email/document ZIP',
        method='Offline ZIP read; MBOX/EML messages and supported document members are indexed locally. No account or service access.',
        path=hp.rel(path), exported_at='unknown', coverage_from=min(dates) if dates else None,
        coverage_to=max(dates) if dates else None, record_counts=json.dumps(counts),
        gaps=json.dumps({'summary': ' '.join(gap_parts), 'unsupported_members': unsupported, 'errors': errors}),
        notes='Email dates are transmission dates. Message authorship comes from exported headers. '
              'The original ZIP remains authoritative; extracted text is searchable convenience data.',
    )
    return source, counts


def ingest_archives(db, root, hp):
    totals = {}
    folder = root / 'raw' / 'imports'
    for path in sorted(folder.glob('*.zip')) if folder.exists() else []:
        try:
            source, counts = ingest_archive(db, path, hp)
            totals[source] = counts
        except (OSError, zipfile.BadZipFile) as exc:
            print(f'  skip unreadable local archive {path.name}: {exc}')
    return totals
