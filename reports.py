#!/usr/bin/env python3
"""Generated reference documents for the Clippi-Health database.

  data/DATA_DICTIONARY.md   what every table and column holds, where each row came from (system → export →
                            file → row), the vocabularies in use, and how to query — for people and agents
  data/CASE_STUDY.md        the record organized by the topics in topics.json; every statement cites a record

Imported by healthpilot.py after each build. Run directly to regenerate from an existing database:

    python3 reports.py
"""
import json
import os
import re
import sqlite3
import sys
from collections import OrderedDict, defaultdict
from datetime import datetime
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("CLIPPI_HEALTH_ROOT", SOURCE_ROOT)).expanduser().resolve()
DATA = ROOT / "data"
DB_PATH = DATA / "health.db"
TOPICS_PATH = ROOT / "topics.json"
NOTES_PATH = ROOT / "case_study_notes.md"
TODAY = datetime.now().strftime("%Y-%m-%d")

RULES = (
    "**Ground rules.** This database and the documents generated from it restate what the source records say. "
    "They do not interpret results, rank diagnoses, or give medical advice. Every statement in a generated "
    "document cites the record it came from as `[#id date “title”]`; open the record (`./hp show <id>`) before "
    "relying on it. Record ids are reassigned on every rebuild — in anything you keep, cite `date + title` or "
    "the row's `source_id`."
)

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def q(db, sql, *args):
    cur = db.execute(sql, args)
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def one(db, sql, *args):
    r = db.execute(sql, args).fetchone()
    return r[0] if r else None


def meta(db, key):
    return one(db, "SELECT value FROM meta WHERE key=?", key)


def esc(v):
    return re.sub(r"\s+", " ", str("" if v is None else v)).replace("|", "\\|").strip()


def md_table(rows, cols, headers=None):
    headers = headers or cols
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        out.append("| " + " | ".join(esc(r.get(c)) for c in cols) + " |")
    return "\n".join(out)


def short_org(org, source):
    return (org or source or "").replace(" (Apple Health)", "")


def fmt_num(v):
    return "" if v is None else f"{v:.4g}"


def value_str(r):
    if r.get("value_num") is not None:
        return f"{r.get('comparator') or ''}{fmt_num(r['value_num'])} {r.get('units') or ''}".strip()
    return (r.get("value_text") or "").strip()


def ref_str(r):
    lo, hi = r.get("ref_low"), r.get("ref_high")
    if lo is not None and hi is not None:
        return f"{fmt_num(lo)}–{fmt_num(hi)}"
    if hi is not None:
        return f"≤{fmt_num(hi)}"
    if lo is not None:
        return f"≥{fmt_num(lo)}"
    return r.get("ref_text") or ""


def flag_of(r):
    f = r.get("flag")
    v, lo, hi = r.get("value_num"), r.get("ref_low"), r.get("ref_high")
    if not f and v is not None:
        f = "High" if hi is not None and v > hi else "Low" if lo is not None and v < lo else None
    return f


def flag_str(r):
    return {"High": "▲ High", "Low": "▼ Low", None: ""}.get(flag_of(r), flag_of(r) or "")


def cite(d):
    a = f" — {d['author']}" if d.get("author") else ""
    return f"[#{d['id']} {d.get('date') or 'undated'} “{d.get('title') or 'untitled'}”{a}]"


def load_topics():
    if not TOPICS_PATH.exists():
        return {}
    return {k: v for k, v in json.loads(TOPICS_PATH.read_text(encoding="utf-8")).items() if not k.startswith("_")}


def rx(patterns):
    pats = [p for p in (patterns or []) if p]
    return re.compile("|".join(f"(?:{p})" for p in pats), re.I) if pats else None

# ---------------------------------------------------------------------------
# topic matching (shared with hp and the dashboard)
# ---------------------------------------------------------------------------

def topic_tests(db, topic):
    r = rx(topic.get("tests"))
    if not r:
        return []
    return [t for t in q(db, "SELECT test, test_group, count(*) n, min(date) first, max(date) last FROM labs_clean "
                             "WHERE date IS NOT NULL GROUP BY test ORDER BY test_group, test") if r.search(t["test"])]


DOC_KINDS = ("note", "report", "message", "attachment", "document", "ccda", "journal")


def topic_docs(db, topic, kinds=DOC_KINDS, min_hits=3, name=None):
    """Documents about a topic: department matches, the title matches, a journal entry is tagged with the topic,
    or the text hits at least `min_hits` distinct keywords (a single hit is usually the problem-list boilerplate
    every note repeats). Each returned row carries `why`: 'dept', 'title', 'tag', and/or the keyword matches."""
    kw, dp = rx(topic.get("keywords")), rx(topic.get("departments"))
    marks = ",".join("?" * len(kinds))
    out = []
    for d in q(db, f"SELECT id, kind, date, title, author, dept, text FROM documents WHERE kind IN ({marks}) "
                   "ORDER BY date, id", *kinds):
        why = []
        if dp and d["dept"] and dp.search(d["dept"]):
            why.append("dept")
        if kw and kw.search(d["title"] or ""):
            why.append("title")
        if d["kind"] == "journal" and name and re.search(rf"^tags:.*\b{re.escape(name)}\b", d["text"] or "", re.I | re.M):
            why.append("tag")
        hits = sorted({m.group(0).lower() for m in kw.finditer(d["text"] or "")}) if kw else []
        if why or len(hits) >= min_hits:
            d["why"] = why + hits
            out.append(d)
    return out


def topic_events(db, topic, doc_ids):
    """Events whose title/detail mention the topic, or that cite a document filed under one of its departments."""
    kw = rx(topic.get("keywords"))
    out = []
    for e in q(db, "SELECT * FROM events ORDER BY date"):
        ids = set(json.loads(e["doc_ids"] or "[]"))
        if (kw and (kw.search(e["title"] or "") or kw.search(e["detail"] or ""))) or (ids & doc_ids):
            out.append(e)
    return out


def strong_doc_ids(docs):
    """Ids of documents matched by department or title (not by keyword count alone)."""
    return {d["id"] for d in docs if "dept" in d["why"] or "title" in d["why"] or "tag" in d["why"]}


HEADINGS = re.compile(r"(Impression & Recommendations|Impression and Recommendations|Assessment & Plan|Assessment/Plan|"
                      r"Assessment and Plan|ASSESSMENT/PLAN|ASSESSMENT AND PLAN|CONCLUSION/INTERPRETATION|"
                      r"Impression:|IMPRESSION:|Assessment:|ASSESSMENT:|Recommendations?:|Plan:|SUMMARY OF FINDINGS:)")
STOP = re.compile(r"\n(Current Outpatient Medications|Medications Ordered|Problem List\n|Relevant Orders|Return in about|"
                  r"My total encounter time|This note was dictated|Electronically signed|The patient has verbally consented|"
                  r"\d+ minutes were spent)", re.I)


def assessment(text, limit=1100):
    """The assessment/impression/plan part of a note, verbatim, trimmed to about `limit` characters."""
    m = HEADINGS.search(text or "")
    if not m:
        return ""
    seg = text[m.start():]
    s = STOP.search(seg, 40)
    if s:
        seg = seg[:s.start()]
    seg = re.sub(r"[ \t]+", " ", re.sub(r"\n{2,}", "\n", seg)).strip()
    if len(seg) > limit:
        cut = seg.rfind(". ", 0, limit)
        seg = seg[: cut + 1 if cut > limit // 2 else limit].rstrip() + " …"
    return seg


def excerpt(text, pattern, width=220):
    m = pattern.search(text or "") if pattern else None
    if not m:
        return re.sub(r"\s+", " ", (text or "")[: width * 2])
    s, e = max(0, m.start() - width), min(len(text), m.end() + width)
    return ("…" if s else "") + re.sub(r"\s+", " ", text[s:e]) + ("…" if e < len(text) else "")


def patient_messages(db, topic):
    """Message segments written by the patient that mention a topic keyword."""
    kw = rx(topic.get("keywords"))
    out = []
    if not kw:
        return out
    for d in q(db, "SELECT id, date, title, text FROM documents WHERE kind='message' ORDER BY date"):
        for seg in re.split(r"\n\n(?=— )", d["text"] or ""):
            if seg.startswith("— Me,") and kw.search(seg):
                out.append((d, seg))
    return out


def clinician_messages(db, topic):
    """Message segments written by clinicians/staff that mention a topic keyword (most recent first)."""
    kw = rx(topic.get("keywords"))
    out = []
    if not kw:
        return out
    for d in q(db, "SELECT id, date, title, text, source, provenance FROM documents WHERE kind='message' ORDER BY date DESC"):
        if (d["source"] or "").startswith("email-"):
            category = json.loads(d["provenance"] or "{}").get("category", "correspondence")
            if category != "correspondence":
                continue
        for seg in re.split(r"\n\n(?=— )", d["text"] or ""):
            if seg.startswith("— ") and not seg.startswith("— Me,") and kw.search(seg):
                out.append((d, seg))
    return out


def current_medications(db):
    """The 'Current Outpatient Medications' list from the most recent note that has one, verbatim."""
    for d in q(db, "SELECT id, date, title, author, text FROM documents WHERE kind='note' AND text LIKE '%Current Outpatient Medications%' ORDER BY date DESC LIMIT 1"):
        seg = d["text"].split("Current Outpatient Medications", 1)[1]
        seg = re.split(r"No current facility|Review of Systems|Allergies|Past Medical", seg, 1)[0]
        meds = [ln.strip() for ln in seg.split("\n") if ln.strip() and ln.strip() not in ("•", "Medication", "Sig", "Dispense", "Refill")]
        return d, meds
    return None, []


def pcp(db):
    for (text,) in db.execute("SELECT text FROM documents WHERE kind='note' AND text LIKE '%PCP:%' ORDER BY date DESC LIMIT 5"):
        m = re.search(r"PCP:\s*([^\n|]{3,80})", text)
        if m and "no primary" not in m.group(1).lower():
            return m.group(1).strip()
    return None


def lab_rows(db, test):
    return q(db, "SELECT date, value_num, value_text, comparator, units, ref_low, ref_high, ref_text, flag, org, source "
                 "FROM labs_clean WHERE test=? AND date IS NOT NULL ORDER BY date", test)


def lab_summary_row(db, test):
    pts = lab_rows(db, test)
    latest, prev = pts[-1], (pts[-2] if len(pts) > 1 else None)
    first = pts[0] if len(pts) > 2 else None
    return {"test": test, "latest": f"{value_str(latest)} {flag_str(latest)}".strip(), "date": latest["date"],
            "ref": ref_str(latest),
            "previous": f"{value_str(prev)} {flag_str(prev)} ({prev['date']})".strip() if prev else "",
            "first": f"{value_str(first)} ({first['date']})" if first else "", "n": len(pts),
            "sources": ", ".join(sorted({short_org(p["org"], p["source"]) for p in pts}))}

# ---------------------------------------------------------------------------
# data dictionary
# ---------------------------------------------------------------------------

TABLE_DOCS = OrderedDict([
    ("sources", ("One row per export that fed the database. `key` is what every other table's `source` column refers to.", [
        ("key", "short id used in other tables' `source` column, including configured email source keys"),
        ("org", "organization whose records these are"),
        ("kind", "export type"),
        ("system", "system of record (and host) the data came from"),
        ("method", "how the export was produced and which raw files map to which tables"),
        ("path", "local source folder or zip, under raw/ or email/"),
        ("exported_at", "when the export was made (file time, local)"),
        ("coverage_from / coverage_to", "earliest and latest dated record from this source (future appointments excluded)"),
        ("record_counts", "JSON: rows loaded, by table or kind"),
        ("gaps", "JSON description of source limitations or data that may be missing"),
        ("notes", "caveats specific to this source")])),
    ("labs", ("One row per lab component (one number or text result). Query the view `labs_clean` to skip cross-source duplicates.", [
        ("id", "row id (reassigned on every rebuild)"),
        ("source", "sources.key"),
        ("org", "lab or health system that reported the result"),
        ("order_name", "panel/order the component belongs to, e.g. `CBC W/ AUTO DIFFERENTIAL`; null for standalone Quest observations"),
        ("result_type", "source result category; standards-based FHIR and Apple clinical rows use `LAB`. Imaging/pathology narrative text is in `documents` (kind=report)"),
        ("date", "collection date, `YYYY-MM-DD` (result date when collection date is absent)"),
        ("collected_at", "`YYYY-MM-DD HH:MM` local, when the source gave a time"),
        ("test", "**canonical test name** — the key that lines up the same test across sources (see § Vocabularies)"),
        ("test_group", "family used for grouping and charting (Blood counts, Metabolic, Immunology …)"),
        ("test_raw", "the test name exactly as the source spelled it"),
        ("loinc", "LOINC code when the source supplied one"),
        ("value_text", "value as reported: `8.8`, `<0.5`, `Negative`, `NON-REACTIVE`"),
        ("value_num", "numeric value, in `units`; null for text results"),
        ("comparator", "`<` or `>` when the lab reported a bound rather than a value"),
        ("units", "unit after harmonization (K/uL, M/uL, U/L …); `value_num`, `ref_low`, `ref_high` are all in this unit"),
        ("units_raw", "unit as reported"),
        ("ref_low / ref_high", "reference range from the same report, converted like the value"),
        ("ref_text", "reference range as text (`3.8 - 9.9`, `Negative`, `<4.4`)"),
        ("flag", "`High`, `Low` or `Abnormal` as flagged by the lab; null when the lab did not flag (tools also compare value to range)"),
        ("comment", "lab comment attached to the component"),
        ("lab", "performing lab or source organization named in the report"),
        ("provider", "ordering provider when supplied"),
        ("source_file", "raw file the row was parsed from (`zip!member` for Apple)"),
        ("source_id", "the source's own id, such as a FHIR Observation id"),
        ("provenance", "how the row was extracted (see § Sources)"),
        ("dup_of", "id of the row this duplicates (same dated test, value, units and comparator). `labs_clean` = rows where this is null")])),
    ("email_lab_evidence", ("Every supplied email labs.csv row, verbatim, including handwritten/uncertain results, historical reprints and repeated values. Only eligible primary lab-report results are also loaded into labs.", [
        ("id / source / source_id", "row id, sources.key, stable CSV source identity including original line number"),
        ("document_id", "documents.id of the original attachment; parent_id links it to the enclosing email"),
        ("lab_id", "labs.id when included in the lab series; follow labs.dup_of for its retained canonical row"),
        ("import_status", "primary_result · possible_duplicate · secondary_evidence · review_required · collection_date_missing · not_performed · report_summary · report_comment"),
        ("possible_duplicate_lab_ids", "JSON list of existing labs.id candidates with matching test/value but adjacent dates or missing unit metadata. These remain unmerged evidence, excluded from charts pending review"),
        ("collected_datetime / reported_datetime", "verbatim specimen/report dates; no email-date substitution"),
        ("lab_vendor / ordering_provider / specimen_id / performing_lab_code", "verbatim laboratory provenance"),
        ("panel / test / result / units / reference_range / flag", "verbatim transcribed fields; no unit conversion, ambiguity resolution or flag interpretation in this table"),
        ("notes / uncertain / row_type / verification_status", "supplied OCR notes and status. row_type distinguishes lab_report, physician_letter, historical and patient_image. Verification describes the export's reading pass, not independent medical verification"),
        ("email_date / email_sender / email_folder", "enclosing email metadata, not a specimen date or claim of attachment authorship"),
        ("source_file / source_page / page_id", "original attachment basename (relative to source path/email_folder), page and transcription page id")])),
    ("fhir_resources", ("Every resource from a direct SMART-on-FHIR download or supplied FHIR NDJSON export, retained verbatim even when Clippi-Health does not project that resource type into another table.", [
        ("source / org", "sources.key and the connected health organization"),
        ("resource_key", "stable export-file and line identity used to retain resources that lack an id"),
        ("resource_type / resource_id", "FHIR resource type and source id"),
        ("last_updated", "FHIR meta.lastUpdated when present"),
        ("source_file", "raw JSONL file containing the resource"),
        ("json", "verbatim compact FHIR JSON; the CSV export reports its character count instead of duplicating PHI") ])),
    ("documents", ("Every searchable text record: clinical notes, visit summaries, reports, correspondence, attachments, FHIR documents and C-CDA summaries. Full-text index: `documents_fts`.", [
        ("id", "row id (reassigned on every rebuild)"),
        ("source / org", "sources.key and organization"),
        ("kind", "`note` explicitly typed or named clinical note (including encounter-linked C-CDA episode note and named note attachments) · `avs` visit summary · `report` result narrative · `message` correspondence · `attachment` other linked file or quoted history · `document` other local/FHIR document · `ccda` C-CDA summary without an explicit encounter-linked note classification · `journal` patient-authored entry"),
        ("date", "source date, `YYYY-MM-DD`; for email attachments this is the enclosing transmission date, not necessarily the clinical event date"),
        ("title", "note type (`Progress Notes`, `H&P`, `Discharge Summary` …), order name, message subject, or file name"),
        ("author", "signing clinician, ordering provider, or document type"),
        ("dept", "department of the visit the record belongs to (notes and AVS)"),
        ("encounter_id", "encounters.id only when the source explicitly links a document to a structured encounter"),
        ("parent_id", "documents.id of the enclosing message for email attachments, including note files"),
        ("text", "plain text. HTML flattened; PDFs extracted with PDFKit. Email attachments use supplied OCR/text sidecars with uncertainty retained; originals remain at `path`"),
        ("path", "original file under raw/ or email/"),
        ("format", "original format: html, json, pdf, jpg, png, tif, xml, eml, md, or `metadata-only` when the portal did not allow download"),
        ("source_id", "the source's own stable id, such as a FHIR resource id, email message id, or C-CDA id"),
        ("provenance", "how the row was extracted")])),
    ("documents_fts", ("SQLite FTS5 index over `documents.title` and `documents.text`. `SELECT rowid FROM documents_fts WHERE documents_fts MATCH '\"fecal calprotectin\"'` — rowid = documents.id. Supports AND/OR/NOT, phrases in double quotes, and `prefix*`.", [])),
    ("encounters", ("One row per explicitly documented C-CDA encompassingEncounter or finished/completed FHIR Encounter. This is not a complete visit history.", [
        ("date / datetime", "structured encounter start date (and time when supplied); no email or filename date substitution"),
        ("type", "source visit/encounter type: Office Visit, Telephone, Emergency Department, Surgery, and similar"),
        ("provider", "clinician or nurse the visit is filed under"),
        ("dept", "department / clinic"),
        ("source_file / source_id", "original source file and source encounter id when provided")])),
    ("conditions", ("Problem list and past-medical-history entries.", [
        ("name", "condition as written in the chart"),
        ("noted", "date first noted (problem list); history entries are usually undated"),
        ("kind", "`problem` (active problem list) or `medical_history`")])),
    ("procedures", ("Surgical/procedure history entries (often undated). Dated procedures also appear in `events`.", [
        ("name / date / kind", "as listed in the chart; kind is `surgical_history`")])),
    ("medications", ("Medication requests/statements as supplied by each source; current and historical entries may be mixed.", [
        ("name / sig", "drug and directions"), ("date", "date supplied by the source, often empty"), ("provider", "prescriber or source reference when supplied")])),
    ("immunizations", ("Immunizations from FHIR, C-CDA, and Apple Health inputs.", [("name / date", "vaccine and date")])),
    ("allergies", ("Allergy list (empty means the chart lists none).", [])),
    ("vitals_daily", ("Device data (Apple Health and Tidepool exports) rolled up to one row per day and metric.", [
        ("date / metric", "day and metric name (see § Vocabularies → Device metrics)"),
        ("value", "daily mean (glucose, weight, heart rate, HRV, SpO2 …) or daily total (steps, insulin, carbs, sleep hours)"),
        ("min / max / n", "daily minimum, maximum and sample count for averaged metrics"),
        ("unit", "unit of `value`")])),
    ("device_samples", ("Intraday Tidepool samples behind the daily rows, for the single-day overlay. cbg/smbg in mg/dL; bolus in delivered units; basal as rate segments; carbs in grams.", [
        ("date / time", "day and local `YYYY-MM-DD HH:MM` wall time of the sample"),
        ("kind", "`cbg`, `smbg`, `bolus`, `basal` or `carbs`"),
        ("value / unit", "glucose, delivered bolus units, basal rate in U/hr, or grams"),
        ("detail", "basal segment duration in milliseconds; otherwise null")])),
    ("events", ("The timeline: dated things worth seeing at a glance, derived from the tables above plus `curated_events.csv`.", [
        ("date / lane / title / detail", "lane ∈ Diagnoses · Surgery & procedures · Hospital & ED · Imaging · Pathology & reports · Milestones"),
        ("doc_ids", "JSON array of documents.id supporting the event"),
        ("curated", "1 when the row came from curated_events.csv (hand-written; it may replace automatic rows)"),
        ("provenance", "`problem_list`, `surgical_history`, `encounter`, `report` or `curated`")])),
    ("meta", ("Build metadata: `patient`, `built_at`, `schema_version`, `apple_record_types` (HealthKit sample counts by type).", [])),
])


def build_dictionary(db, vital_types=None):
    L = []
    add = L.append
    add("# Clippi-Health — data dictionary\n")
    add(f"Generated {datetime.now():%Y-%m-%d %H:%M} from `data/health.db` (schema {meta(db, 'schema_version')}, "
        f"built {meta(db, 'built_at')}). Regenerated on every `python3 healthpilot.py`.\n")
    add(RULES + "\n")

    # 1. what is here
    add("## 1. What is here\n")
    counts = []
    for t, (desc, _) in TABLE_DOCS.items():
        if t in ("documents_fts", "meta"):
            continue
        n = one(db, f"SELECT count(*) FROM {t}")
        extra = ""
        if t == "labs":
            extra = f" ({one(db, 'SELECT count(*) FROM labs_clean')} after de-duplication, {one(db, 'SELECT count(DISTINCT test) FROM labs_clean')} distinct tests)"
        if t == "documents":
            extra = " (" + ", ".join(f"{r['n']} {r['kind']}" for r in q(db, "SELECT kind, count(*) n FROM documents GROUP BY kind ORDER BY n DESC")) + ")"
        counts.append({"table": f"`{t}`", "rows": f"{n:,}{extra}", "what": desc})
    add(md_table(counts, ["table", "rows", "what"], ["Table", "Rows", "What it holds"]))
    cov = q(db, "SELECT key, coverage_from, coverage_to FROM sources")
    add("\nDate coverage by source: " + "; ".join(f"**{r['key']}** {r['coverage_from']} → {r['coverage_to']}" for r in cov) + ".\n")

    # 2. access
    add("## 2. How to access it\n")
    add("""All of these read the same `data/health.db` (SQLite 3, one file, no server). The core builder uses Python's standard library.

| Means | Use it for | Example |
|---|---|---|
| `./hp` CLI | quick answers without SQL; `--json` for machine-readable output | `./hp labs "A1c"` · `./hp search calprotectin --kind note` · `./hp show 41` · `./hp topic Immune` |
| `sqlite3` shell / any SQLite client | ad-hoc SQL, joins | `sqlite3 data/health.db "SELECT date, value_num, units FROM labs_clean WHERE test='IgG' ORDER BY date"` |
| Python `sqlite3` (standard library) | scripts, notebooks | `sqlite3.connect('data/health.db').execute(...)` |
| Full-text search | find records by words | `SELECT d.id, d.date, d.title FROM documents_fts f JOIN documents d ON d.id=f.rowid WHERE documents_fts MATCH 'copper AND zinc'` |
| `data/export/*.csv` | spreadsheets, pandas, anything that reads CSV; one file per table | `data/export/labs.csv` |
| `data/records/*.md` | reading or grepping records as files; front matter carries the metadata | `data/records/2026-05-06_note_0041_Discharge-Summary.md` |
| `dashboard.html` | charts, timeline, search in a browser; offline, single file | double-click it |
| `data/CASE_STUDY.md` | the record organized by topic, with citations | |

Conventions: dates are ISO `YYYY-MM-DD` (local time); numbers are plain floats; JSON columns are text; ids are integers reassigned on every rebuild; text is UTF-8 plain text with newlines preserved.
""")

    # 3. sources & provenance
    add("## 3. Sources and provenance\n")
    add("Every row records where it came from: `source` (which export), `source_file` / `path` (which raw file), "
        "`source_id` (the source system's own id) and `provenance` (how it was extracted). The chain for each source:\n")
    for s in q(db, "SELECT * FROM sources ORDER BY key"):
        add(f"### `{s['key']}` — {s['org']}\n")
        add(f"- **System:** {s['system']}")
        add(f"- **Export:** {s['kind']}, exported {s['exported_at']}; files under `{s['path']}`")
        add(f"- **Method:** {s['method']}")
        add(f"- **Coverage:** {s['coverage_from']} → {s['coverage_to']}")
        rc = json.loads(s["record_counts"] or "{}")
        if rc:
            add("- **Loaded:** " + ", ".join(f"{v} {k}" for k, v in rc.items()))
        gaps = json.loads(s["gaps"] or "{}")
        if gaps:
            na = gaps.get("needs_attention") or []
            add(f"- **Known source limitations:** {gaps.get('summary') or ''} "
                + ("Could not fetch: " + ", ".join(f"`{g['endpoint']}` ({g['outcome']})" for g in na) + ". " if na else "")
                + ("Empty: " + ", ".join(f"`{e}`" for e in gaps.get("empty") or []) + "." if gaps.get("empty") else ""))
        if s["notes"]:
            add(f"- **Caveats:** {s['notes']}")
        add("")
    add("**Provenance values in use** (row counts):\n")
    prov = []
    for t in ("labs", "documents", "events"):
        for r in q(db, f"SELECT provenance, count(*) n FROM {t} GROUP BY provenance ORDER BY n DESC"):
            prov.append({"table": f"`{t}`", "n": r["n"], "provenance": r["provenance"]})
    add(md_table(prov, ["table", "n", "provenance"], ["Table", "Rows", "provenance"]))
    add("""
**Raw layout** (never modified by the build):

```
raw/fhir/<source>/*.jsonl    direct SMART/FHIR or supplied NDJSON → fhir_resources and projected clinical tables
raw/apple/*.zip              Apple Health export — clinical-records/*.json (FHIR) → labs, immunizations; export.xml → vitals_daily
raw/other/TidepoolExport*.json  Tidepool Export Data (JSON) → vitals_daily (direct pump/CGM export; wins overlapping day+metric)
email/*/healthpilot-source.json  configured local email exports; index.csv + messages + attachments + OCR + labs.csv
raw/other/**                 anything added by hand (PDF/HTML/TXT → documents; IHE_XDM/*.XML C-CDA → documents and explicit encounters)
curated_events.csv           hand-written timeline rows → events (curated=1)
```
""")

    # 4. tables
    add("## 4. Tables and columns\n")
    for t, (desc, cols) in TABLE_DOCS.items():
        add(f"### `{t}`\n\n{desc}\n")
        if cols:
            add(md_table([{"col": f"`{c}`", "meaning": m} for c, m in cols], ["col", "meaning"], ["Column", "Meaning"]))
        add("")
    add("`labs_clean` is a view: `SELECT * FROM labs WHERE dup_of IS NULL`. Use it unless you are auditing duplicates.\n")

    # 5. vocabularies
    add("## 5. Vocabularies\n")
    add("### Lab tests\n")
    add("`labs.test` is the canonical name. Names from different labs are mapped onto it (`test_raw` keeps the original); "
        "units are converted to one unit per test where the conversion is a plain factor (K/cumm, 10*3/uL, Thousand/uL → K/uL; "
        "cells/uL → K/uL ÷1000; Units/L → U/L; %-of-total-Hgb → %). Tests with no mapping keep their source name and are "
        "grouped by name pattern. Quest reuses blood-test names for urinalysis components (`GLUCOSE`, `WBC`); those are "
        "identified by LOINC code and named `Urine …`.\n")
    agg = OrderedDict()
    for r in q(db, "SELECT test_group, test, date, units, org, source, loinc, test_raw FROM labs_clean WHERE date IS NOT NULL ORDER BY test_group, test, date"):
        a = agg.setdefault((r["test_group"], r["test"]), {"n": 0, "first": r["date"], "last": r["date"], "units": set(), "orgs": set(), "loinc": set(), "raw": set()})
        a["n"] += 1
        a["last"] = r["date"]
        a["units"].add(r["units"] or "")
        a["orgs"].add(short_org(r["org"], r["source"]))
        if r["loinc"]:
            a["loinc"].add(r["loinc"])
        a["raw"].add(r["test_raw"] or "")
    rows = []
    for (g, t), a in agg.items():
        raw = sorted(x for x in a["raw"] if x and x != t)
        rows.append({"group": g, "test": t, "n": a["n"], "first": a["first"], "last": a["last"],
                     "units": ", ".join(sorted(u for u in a["units"] if u)), "sources": ", ".join(sorted(a["orgs"])),
                     "loinc": ", ".join(sorted(a["loinc"])), "raw": "; ".join(raw[:5]) + (" …" if len(raw) > 5 else "")})
    add(md_table(rows, ["group", "test", "n", "first", "last", "units", "sources", "loinc", "raw"],
                 ["Group", "Test (canonical)", "n", "First", "Last", "Units", "Sources", "LOINC", "Source spellings"]))

    add("\n### Document kinds, encounter types, event lanes\n")
    add(md_table(q(db, "SELECT kind, count(*) n, min(date) first, max(date) last FROM documents GROUP BY kind ORDER BY n DESC"),
                 ["kind", "n", "first", "last"], ["documents.kind", "n", "First", "Last"]))
    add("")
    add(md_table(q(db, "SELECT type, count(*) n, min(date) first, max(date) last FROM encounters GROUP BY type ORDER BY n DESC"),
                 ["type", "n", "first", "last"], ["encounters.type", "n", "First", "Last"]))
    add("")
    add(md_table(q(db, "SELECT lane, count(*) n, sum(curated) curated, min(date) first, max(date) last FROM events GROUP BY lane ORDER BY n DESC"),
                 ["lane", "n", "curated", "first", "last"], ["events.lane", "n", "curated", "First", "Last"]))
    add("\n### Departments (encounters)\n")
    add(md_table(q(db, "SELECT dept, count(*) n, min(date) first, max(date) last FROM encounters WHERE dept IS NOT NULL GROUP BY dept ORDER BY last DESC"),
                 ["dept", "n", "first", "last"], ["Department", "Visits", "First", "Last"]))
    add("\n### Device metrics (`vitals_daily.metric`)\n")
    vt = {m: (hk, unit, how) for hk, (m, unit, how) in (vital_types or {}).items()}
    tidepool_here = one(db, "SELECT 1 FROM sources WHERE key='tidepool'") is not None
    tidepool_source = {
        "CGM / meter glucose": "Tidepool cbg + smbg",
        "Glucose time in range 70–180": "derived from Tidepool cbg + smbg",
        "Insulin": "Tidepool bolus delivered + basal rate × duration",
        "Insulin basal": "Tidepool basal rate × duration",
        "Insulin bolus": "Tidepool bolus delivered (normal + extended)",
        "Carbs logged": "Tidepool wizard carbInput",
    }
    vrows = []
    for r in q(db, "SELECT metric, unit, count(*) days, min(date) first, max(date) last FROM vitals_daily GROUP BY metric ORDER BY metric"):
        hk, _, how = vt.get(r["metric"], ("derived", "", ""))
        rollup = {"mean": "daily mean, min, max, n", "sum": "daily total (max across apps writing the same metric, to avoid double counting)"}.get(how, "")
        if r["metric"] in tidepool_source and tidepool_here:
            rollup = {"mean": "daily mean, min, max, n", "sum": "daily total"}.get(how, rollup)
            hk = tidepool_source[r["metric"]] + (f"; {hk} on days without Tidepool coverage" if hk != "derived" else "")
        if r["metric"].startswith("Glucose time in range"):
            rollup, hk = "% of that day's readings between 70 and 180 mg/dL, on days with ≥12 readings", "derived from HKQuantityTypeIdentifierBloodGlucose"
        if r["metric"] == "Sleep":
            rollup, hk = "hours in 'asleep' stages, credited to the wake-up date", "HKCategoryTypeIdentifierSleepAnalysis"
        if r["metric"] in ("Insulin basal", "Insulin bolus", "Insulin unspecified"):
            hk = "HKQuantityTypeIdentifierInsulinDelivery + HKInsulinDeliveryReason"
            rollup = "daily total by recorded delivery reason, from the same source selected for total insulin; missing or unknown reasons stay unspecified"
        vrows.append({"metric": r["metric"], "unit": r["unit"], "days": r["days"], "first": r["first"], "last": r["last"], "hk": hk, "rollup": rollup})
    add(md_table(vrows, ["metric", "unit", "days", "first", "last", "hk", "rollup"], ["Metric", "Unit", "Days", "First", "Last", "HealthKit type", "Roll-up"]))
    hk_counts = json.loads(meta(db, "apple_record_types") or "{}")
    if hk_counts:
        add("\nHealthKit sample types present in the export (raw counts; only the ones above are loaded): " +
            ", ".join(f"{k.replace('HKQuantityTypeIdentifier', '').replace('HKCategoryTypeIdentifier', '')} {v:,}" for k, v in list(hk_counts.items())[:30]) + ".")

    # 6. where to look by topic
    topics = load_topics()
    if topics:
        add("\n## 6. Where to look, by topic\n")
        add("Topics are defined in `topics.json` (patterns over test names, record text and departments). "
            "`./hp topic <name>` prints the full section; `data/CASE_STUDY.md` has all of them.\n")
        for name, t in topics.items():
            docs = topic_docs(db, t)
            tests = topic_tests(db, t)
            kinds = defaultdict(int)
            for d in docs:
                kinds[d["kind"]] += 1
            depts = sorted({d["dept"] for d in docs if d.get("dept") and "dept" in d["why"]})
            add(f"### {name} ({t.get('status', '')})\n")
            add(f"- **Labs:** {len(tests)} tests — " + ", ".join(f"{x['test']} ({x['n']})" for x in tests[:18]) + (" …" if len(tests) > 18 else ""))
            add(f"- **Records:** {len(docs)} — " + ", ".join(f"{v} {k}" for k, v in sorted(kinds.items(), key=lambda x: -x[1])))
            if depts:
                add(f"- **Departments:** " + "; ".join(depts))
            if docs:
                add(f"- **Most recent:** " + "; ".join(cite(d) for d in docs[-3:]))
            add("")

    # 7. caveats
    add("## 7. Caveats and data-quality notes\n")
    add(f"""- **Email evidence.** All supplied lab transcription rows live in `email_lab_evidence` and its CSV export. Letters, historical reprints, images, uncertain/page-review readings, unperformed tests and report summaries/comments and possible repeats with adjacent dates or missing units do not enter lab charts. An email date is never substituted for a missing collection date. Email `message` text stops at explicit reply/forward headers; full quoted history is a linked attachment with embedded author/date headers. Appointment/billing notices do not create completed encounters or medication records.
- **Duplicates across sources.** The same result can arrive through FHIR, Apple Health, and supplied correspondence. Rows with the same dated test, value, units and comparator are marked `dup_of`; `labs_clean` hides them. {one(db, 'SELECT count(*) FROM labs WHERE dup_of IS NOT NULL')} rows are marked.
- **Flags.** `flag` is only what the source flagged. Tools re-derive High/Low from `ref_low`/`ref_high` when present. Text results (`Negative`, `NON-REACTIVE`) have no numeric range.
- **Reference ranges change** between labs and over time. Charts show the most recent range for the test.
- **Undated history.** Source problem/procedure history can omit dates (`noted`/`date` null); those rows are not on the timeline unless added in `curated_events.csv`.
- **Timeline derivation.** Automatic events come from problem-list dates, visit types (surgery/anesthesia/procedure/infusion/ED/hospital), imaging and pathology reports, and dated procedures. Same-day outpatient hospital visits are merged into the procedure they belong to. Curated rows can replace automatic ones (`replaces` column).
- **Text extraction.** Source HTML/XML is flattened to text. Scanned PDFs and image attachments can have empty `text`; open `path`. FHIR Binary files are materialized under `data/fhir_files/` during a build.
- **Apple Health clinical records** are FHIR DSTU2 as delivered by the labs; standalone Observations carry no performer and are attributed to Quest (see source notes). `issued` vs `effectiveDateTime` can differ by days; `date` uses `effectiveDateTime`.
- **Device data** is summarized per day. Glucose comes from every app that wrote to HealthKit (Dexcom, Loop, meters), so CGM days have hundreds of samples and meter-only days a few; `n` tells them apart. Time in range is only computed on days with ≥12 readings.
- **Tidepool device data** is also summarized per day: delivered insulin only (bolus normal + extended; basal rate × duration), pump-wizard carbs, glucose in mg/dL. Where Tidepool and Apple HealthKit cover the same day and metric, the Tidepool value is used and the raw exports stay authoritative.
- **Time zones.** UTC instants are converted to local time; Apple and FHIR timestamps can carry their own offsets.
- **Document and encounter tagging.** `note` requires an explicit FHIR document type, encounter-linked C-CDA episode-note code, or a source filename explicitly naming a clinical note. An email message about an appointment or a note mentioned inside a document does not create a note or encounter. `encounters` projects only structured C-CDA encompassing encounters with dates and finished/completed FHIR Encounters. Source exports may omit many real visits or notes; dashboard counts mean indexed records, not lifetime totals. See `docs/DATA_MAPPING.md` and the record-classification ADR.
- **Ids are not stable** across rebuilds. `source_id`, `path`, and `date + title` are.
""")

    # 8. rebuild
    add("## 8. Rebuilding and adding data\n")
    add("""```bash
./hp smart import export.jsonl --source fhir-example --org "Example Health"  # existing FHIR NDJSON export
python3 healthpilot.py                     # rebuilds health.db, dashboard.html, exports, this file, CASE_STUDY.md
```
Apple Health: iPhone → Health → profile picture → Export All Health Data → replace the zip in `raw/apple/`.
Other files: drop PDFs/HTML/text or an IHE XDM C-CDA record-download folder into `raw/other/`.
Hand-curated inputs: `curated_events.csv` (timeline), `topics.json` (topics), `case_study_notes.md` (patient's notes).
""")
    out = DATA / "DATA_DICTIONARY.md"
    out.write_text("\n".join(L), encoding="utf-8")
    return out

# ---------------------------------------------------------------------------
# case study
# ---------------------------------------------------------------------------

def topic_section(db, name, topic, level="###"):
    L = [f"{level} {name}" + (f" — {topic['status']}" if topic.get("status") else "")]
    if topic.get("framing"):
        L.append(f"\n*Patient's framing:* {topic['framing']}\n")
    kw = rx(topic.get("keywords"))
    docs = topic_docs(db, topic, name=name)
    doc_ids = {d["id"] for d in docs}

    probs = OrderedDict()
    for c in q(db, "SELECT name, noted, kind, source, org FROM conditions ORDER BY noted"):
        if kw and kw.search(c["name"]) and c["name"].lower() not in probs:
            probs[c["name"].lower()] = c
    if probs:
        L.append("**Problem list / history entries**\n")
        for c in probs.values():
            L.append(f"- {c['name']} — {'noted ' + c['noted'] if c['noted'] else 'undated'} "
                     f"({short_org(c['org'], c['source'])}, {c['kind'].replace('_', ' ')})")
        L.append("")

    evs = topic_events(db, topic, strong_doc_ids(docs))
    if evs:
        L.append("**Timeline** (events matching this topic; ◆ = written by hand in curated_events.csv)\n")
        for e in evs:
            ids = json.loads(e["doc_ids"] or "[]")
            cites = " ".join(cite(d) for d in q(db, f"SELECT id, date, title, author FROM documents WHERE id IN ({','.join('?' * len(ids))}) ORDER BY id", *ids)) if ids else ""
            detail = esc(e["detail"])[:320]
            L.append(f"- {e['date']} — {'◆ ' if e['curated'] else ''}**{e['title']}** ({e['lane']}){': ' + detail if detail else ''} {cites}")
        L.append("")

    tests = topic_tests(db, topic)
    if tests:
        L.append("**Labs** — latest first; ▲/▼ = outside the lab's reference range; full series: `./hp labs \"<test>\"`\n")
        rows, collapsed = [], OrderedDict()
        for t in tests:
            label = next((lab for pat, lab in (topic.get("collapse") or {}).items() if re.search(pat, t["test"], re.I)), None)
            if label:
                collapsed.setdefault(label, []).append(t["test"])
            else:
                rows.append(lab_summary_row(db, t["test"]))
        for label, names in collapsed.items():
            dates = sorted({r["date"] for n in names for r in lab_rows(db, n)})
            rows.append({"test": label, "latest": f"{len(names)} components", "date": ", ".join(dates),
                         "ref": "", "previous": "", "first": "", "n": sum(len(lab_rows(db, n)) for n in names), "sources": "table below"})
        L.append(md_table(rows, ["test", "latest", "date", "ref", "previous", "first", "n", "sources"],
                          ["Test", "Latest", "Date", "Ref range", "Previous", "First", "n", "Sources"]))
        L.append("")
        # full series for the tests the topic singles out
        series = rx(topic.get("series"))
        if series:
            L.append("**Series** (every result, oldest → newest)\n")
            for t in tests:
                if series.search(t["test"]):
                    pts = lab_rows(db, t["test"])
                    L.append(f"- **{t['test']}** ({pts[-1].get('units') or 'text'}; latest ref {ref_str(pts[-1]) or '—'}): " +
                             "; ".join(f"{p['date']} {value_str(p).replace(' ' + (p.get('units') or ''), '')}{' ' + flag_str(p).split()[0] if flag_of(p) else ''}" for p in pts))
            L.append("")
        # collapsed panels as component × date tables when there are only a few dates
        for label, names in collapsed.items():
            dates = sorted({r["date"] for n in names for r in lab_rows(db, n)})
            if not 1 <= len(dates) <= 4:
                continue
            L.append(f"**{label}** — {', '.join(dates)}\n")
            prow = []
            for n in names:
                by_date = {r["date"]: r for r in lab_rows(db, n)}
                row = {"c": n.replace("S. pneumo Type ", "Type "), "ref": next((ref_str(r) for r in by_date.values() if ref_str(r)), "")}
                for d in dates:
                    r = by_date.get(d)
                    row[d] = (f"{value_str(r).replace(' ' + (r.get('units') or ''), '')} {flag_str(r).split()[0] if flag_of(r) else ''}".strip() if r else "")
                prow.append(row)
            L.append(md_table(prow, ["c"] + dates + ["ref"], ["Component"] + dates + ["Ref"]))
            L.append("")

    by_dept = OrderedDict()
    for d in sorted((d for d in docs if d["kind"] == "note" and "dept" in d["why"]), key=lambda x: x["date"] or "", reverse=True):
        if d["dept"] not in by_dept and assessment(d["text"]):
            by_dept[d["dept"]] = d
    if by_dept:
        L.append("**Latest documented assessment, per clinic** (verbatim excerpts)\n")
        for dept, d in by_dept.items():
            L.append(f"*{dept}* {cite(d)}\n")
            L.append("> " + assessment(d["text"]).replace("\n", "\n> ") + "\n")

    others = [d for d in docs if d["kind"] in ("report", "attachment", "document", "ccda")]
    if others:
        L.append("**Reports, attachments and documents mentioning this topic** (most recent 15)\n")
        for d in others[-15:]:
            L.append(f"- {cite(d)} — {d['kind']}, matched “{d['why'][-1]}”")
        L.append("")

    pm = patient_messages(db, topic)
    if pm:
        L.append("**Patient-reported, in correspondence** (most recent 6)\n")
        for d, seg in pm[-6:]:
            L.append(f"- {cite(d)}: {excerpt(seg, kw, 200)}")
        L.append("")
    cm = clinician_messages(db, topic)
    if cm:
        L.append("**From clinicians, in correspondence** (most recent 5)\n")
        for d, seg in cm[:5]:
            L.append(f"- {cite(d)}: {excerpt(seg, kw, 220)}")
        L.append("")

    dp = rx(topic.get("departments"))
    upcoming = [e for e in q(db, "SELECT date, type, dept, provider FROM encounters WHERE date > ? ORDER BY date", TODAY)
                if dp and e["dept"] and dp.search(e["dept"])]
    if upcoming:
        L.append("**Upcoming appointments (as exported)**\n")
        for e in upcoming:
            L.append(f"- {e['date']} — {e['type']}, {e['dept']}{' — ' + e['provider'] if e['provider'] else ''}")
        L.append("")
    L.append(f"*Records matched: {len(docs)} · explore with `./hp topic \"{name}\"`*\n")
    return "\n".join(L)


def at_a_glance(db, patient):
    """One page a new clinician reads first: who, active problems, current meds, key dated events, care team."""
    L = ["## At a glance\n"]
    dob = patient.get("dateOfBirth") or patient.get("birthDate")
    age = patient.get("age")
    who = ", ".join(x for x in [f"DOB {dob}" if dob else "", f"age {age}" if age else ""] if x)
    doc = pcp(db)
    L.append(f"- **Patient:** {who}" + (f" · **PCP on record:** {doc}" if doc else ""))
    for k in ("height", "weight"):
        v = patient.get(k) or {}
        if v.get("value"):
            L.append(f"- **{k.title()}:** {v['value']} (recorded {v.get('dateRecorded')})")
    L.append("")
    probs = q(db, "SELECT name, noted, source, org FROM conditions WHERE kind='problem' ORDER BY noted DESC")
    if probs:
        L.append("**Active problem list** (as kept by each health system, newest first)\n")
        for c in probs:
            L.append(f"- {c['name']} — {'noted ' + c['noted'] if c['noted'] else 'undated'} ({short_org(c['org'], c['source'])})")
        L.append("")
    hist = OrderedDict((c["name"].lower(), c) for c in q(db, "SELECT name FROM conditions WHERE kind='medical_history' ORDER BY name"))
    if hist:
        L.append("**Past medical history entries:** " + "; ".join(c["name"] for c in hist.values()) + "\n")
    d, meds = current_medications(db)
    if meds:
        L.append(f"**Current medications** — the medication list in the most recent note that carries one {cite(d)}\n")
        for m in meds:
            L.append(f"- {m}")
        L.append("")
    curated = q(db, "SELECT date, lane, title FROM events WHERE curated=1 ORDER BY date")
    if curated:
        L.append("**Key dated events** (hand-curated from the records; details and citations in the topic sections)\n")
        for e in curated:
            L.append(f"- {e['date']} — {e['title']} *({e['lane']})*")
        L.append("")
    year_ago = (datetime.now().replace(year=datetime.now().year - 1)).strftime("%Y-%m-%d")
    team = q(db, "SELECT dept, max(date) last, count(*) n, group_concat(DISTINCT provider) providers, source FROM encounters "
                 "WHERE date BETWEEN ? AND ? AND dept IS NOT NULL GROUP BY dept ORDER BY last DESC", year_ago, TODAY)
    if team:
        L.append("**Clinics seen in the last 12 months**\n")
        for t in team:
            provs = [p for p in (t["providers"] or "").split(",") if p and not p.startswith("Nurse")][:3]
            L.append(f"- {t['dept']} — {t['n']} contact{'s' if t['n'] != 1 else ''}, last {t['last']}" + (f" ({', '.join(provs)})" if provs else ""))
        L.append("")
    upcoming = q(db, "SELECT date, type, dept, provider FROM encounters WHERE date > ? ORDER BY date", TODAY)
    if upcoming:
        L.append("**Scheduled appointments (as exported)**\n")
        for e in upcoming:
            L.append(f"- {e['date']} — {e['type']}, {e['dept']}{' — ' + e['provider'] if e['provider'] else ''}")
        L.append("")
    return "\n".join(L)


def journal_section(db, limit=12):
    """The patient's own dated observations from journal.md, newest first — clearly marked as patient-authored."""
    entries = q(db, "SELECT id, date, title, text FROM documents WHERE kind='journal' ORDER BY date DESC, id DESC LIMIT ?", limit)
    if not entries:
        return ""
    L = ["## Most recent observations — patient's journal\n",
         "Written by the patient in `journal.md`; not a clinical record. Newest first.\n"]
    for e in entries:
        text = e["text"] or ""
        tags = re.match(r"tags:\s*(.+)", text)
        body = re.sub(r"^tags:.*\n\n?", "", text).strip()
        L.append(f"**{e['date']} — {e['title']}**" + (f" · *{tags.group(1)}*" if tags else "") + f" {cite(e)}\n")
        L.append(body + "\n")
    return "\n".join(L)


def build_case_study(db):
    patient = json.loads(meta(db, "patient") or "{}")
    who = " ".join(x for x in [patient.get("firstName"), f"(DOB {patient.get('dateOfBirth') or patient.get('birthDate')})"] if x)
    topics = load_topics()
    L = [f"# Case study — {who}\n",
         f"Generated {datetime.now():%Y-%m-%d %H:%M} from `data/health.db`; sources: " +
         "; ".join(f"{r['org']} (exported {r['exported_at']})" for r in q(db, "SELECT org, exported_at FROM sources")) + ".\n",
         RULES + "\n",
         "Topics, their order and the patient's framing come from `topics.json`; the closing section is `case_study_notes.md` verbatim.\n"]
    L.append(at_a_glance(db, patient))
    L.append(journal_section(db))
    focus = [(n, t) for n, t in topics.items() if t.get("status") == "focus"]
    background = [(n, t) for n, t in topics.items() if t.get("status") != "focus"]
    if focus:
        L.append("## Current focus\n")
        for n, t in focus:
            L.append(topic_section(db, n, t))
    if background:
        L.append("## Background\n")
        for n, t in background:
            L.append(topic_section(db, n, t))

    L.append("## Medications (as listed in each portal at export)\n")
    for s in q(db, "SELECT DISTINCT source, org FROM medications"):
        L.append(f"*{short_org(s['org'], s['source'])}*\n")
        for m in q(db, "SELECT name, sig FROM medications WHERE source=? ORDER BY name", s["source"]):
            L.append(f"- {m['name']}" + (f" — {m['sig']}" if m["sig"] else ""))
        L.append("")

    L.append("## Care team (departments seen, most recent first)\n")
    care = q(db, "SELECT dept, count(*) n, min(date) first, max(date) last, group_concat(DISTINCT provider) providers, source, org "
                 "FROM encounters WHERE date <= ? AND dept IS NOT NULL GROUP BY dept, source, org ORDER BY last DESC LIMIT 25", TODAY)
    for c in care:
        provs = [p for p in (c["providers"] or "").split(",") if p and not p.startswith("Nurse")][:3]
        c["providers"] = ", ".join(provs)
        c["src"] = short_org(c["org"], c["source"])
    L.append(md_table(care, ["dept", "n", "first", "last", "providers", "src"], ["Department", "Visits", "First", "Last", "Clinicians", "Source"]))
    L.append("")

    L.append("## Sources and coverage\n")
    for s in q(db, "SELECT * FROM sources ORDER BY key"):
        rc = json.loads(s["record_counts"] or "{}")
        L.append(f"- **{s['org']}** — {s['kind']}, exported {s['exported_at']}, records {s['coverage_from']} → {s['coverage_to']}; "
                 + ", ".join(f"{v} {k}" for k, v in rc.items()))
    L.append("")
    if NOTES_PATH.exists():
        L.append("---\n")
        L.append(NOTES_PATH.read_text(encoding="utf-8").strip() + "\n")
    out = DATA / "CASE_STUDY.md"
    out.write_text("\n".join(L), encoding="utf-8")
    return out


def build_all(db, vital_types=None):
    return build_dictionary(db, vital_types), build_case_study(db)


if __name__ == "__main__":
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        import healthpilot
        vt = healthpilot.VITAL_TYPES
    except Exception:  # noqa: BLE001 — reports must still work without the builder importable
        vt = None
    for p in build_all(conn, vt):
        print(p.relative_to(ROOT))
    sys.exit(0)
