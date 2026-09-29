#!/usr/bin/env python3
"""redact — best-effort copies of Markdown files with patient identifiers replaced.

    python3 scripts/redact.py [files…] [--strict] [--out DIR]

Defaults: the hand-written and generated Markdown documents; output to redacted/redacted-<name>.md.
Identifiers come from redact.json (names, DOB, ids, phones, addresses, family) plus general patterns
(any phone number, email, MRN/ID/requisition/accession numbers, street addresses, ZIP codes).
--strict also replaces clinician names and institutions listed in redact.json with generic labels.

This is best effort, not HIPAA Safe Harbor: dates, ages, clinicians and institutions are kept unless --strict.
Read the residual report and the output before sharing anything.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "redact.json"
DEFAULT_FILES = ["README_first.md", "case_study_notes.md", "unresolved-questions.md", "journal.md",
                 "clinical_summary_draft.md", "data/CASE_STUDY.md", "data/DATA_DICTIONARY.md"]


def load_config():
    if not CONFIG.exists():
        sys.exit("redact.json not found — see scripts/redact.py docstring")
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def build_rules(cfg, strict):
    rules = []  # (label, compiled regex, replacement)
    esc = lambda s: re.escape(s)
    # configured literal identifiers, longest first so "Alex Example" beats "Example"
    for key, tag in (("names", "[PATIENT]"), ("family", "[FAMILY MEMBER]"), ("ids", "[ID]"), ("phones", "[PHONE]"),
                     ("emails", "[EMAIL]"), ("addresses", "[ADDRESS]"), ("dob", "[DOB]")):
        for lit in sorted(cfg.get(key, []), key=len, reverse=True):
            flags = re.I if key in ("names", "family", "addresses", "emails") else 0
            pat = rf"(?<![\w-]){esc(lit)}(?:['’]s)?(?![\w-])" if key in ("names", "family") else esc(lit)
            rules.append((f"{key}:{lit}", re.compile(pat, flags), tag))
    # general patterns
    rules += [
        ("mrn", re.compile(r"\b(MRN|Patient ID|Requisition|Specimen|Accession#?|Invitae #|CEID)\s*:\s*(?=[A-Za-z-]*\d)[A-Za-z0-9-]{4,40}\b", re.I),
         lambda m: m.group(1) + ": [ID]"),
        ("phone", re.compile(r"\(?\b\d{3}\)?[-. ]\d{3}[-. ]\d{4}\b"), "[PHONE]"),
        ("email", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"), "[EMAIL]"),
        ("street", re.compile(r"(?<![/\d:-])\b\d{2,5}\s+(?:[A-Z][A-Za-z.]+\s){1,3}(?:AVE|AVENUE|ST|STREET|RD|ROAD|BLVD|DRIVE|LN|LANE|CT|WAY|PL|DR(?!\.?\s+[A-Z][a-z]))\b\.?", re.I), "[ADDRESS]"),
        ("city-state-zip", re.compile(r"\b[A-Z][A-Za-z.]+(?:\s+[A-Z][A-Za-z.]+){0,3},?\s+[A-Z]{2}\s+\d{5}(?:-\d{4})?\b"), "[CITY, STATE ZIP]"),
    ]
    if strict:
        for lit in sorted(cfg.get("providers", []), key=len, reverse=True):
            rules.append((f"provider:{lit}", re.compile(rf"(?<![\w-]){esc(lit)}(?![\w-])", re.I), "[CLINICIAN]"))
        for lit in sorted(cfg.get("places", []), key=len, reverse=True):
            rules.append((f"place:{lit}", re.compile(rf"(?<![\w-]){esc(lit)}(?![\w-])", re.I), "[INSTITUTION]"))
    return rules


def redact_text(text, rules):
    counts = {}
    for label, rx, rep in rules:
        text, n = rx.subn(rep, text)
        if n:
            counts[label] = n
    return text, counts


def residuals(text, cfg):
    """Anything that still looks like an identifier after redaction."""
    found = []
    for lit in cfg.get("names", []) + cfg.get("family", []) + cfg.get("ids", []) + cfg.get("phones", []) + cfg.get("dob", []):
        if lit and re.search(rf"(?<![\w-]){re.escape(lit)}(?![\w-])", text, re.I):
            found.append(lit)
    for pat, what in ((r"\b\d{3}[-.]\d{3}[-.]\d{4}\b", "phone-like"), (r"\b\d{9}\b", "9-digit id"), (r"@[\w-]+\.\w", "email")):
        if re.search(pat, text):
            found.append(what)
    return found


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    strict = "--strict" in sys.argv
    out_dir = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else ROOT / "redacted"
    cfg = load_config()
    rules = build_rules(cfg, strict)
    out_dir.mkdir(parents=True, exist_ok=True)
    files = [ROOT / f for f in (args or DEFAULT_FILES)]
    for src in files:
        if not src.exists():
            print(f"skip {src.relative_to(ROOT)} (missing)")
            continue
        text, counts = redact_text(src.read_text(encoding="utf-8"), rules)
        dest = out_dir / f"redacted-{src.name}"
        dest.write_text(text, encoding="utf-8")
        left = residuals(text, cfg)
        total = sum(counts.values())
        print(f"{dest.relative_to(ROOT)}: {total} replacement{'s' if total != 1 else ''}"
              + (f" — " + ", ".join(f"{k.split(':')[0]}×{v}" for k, v in sorted(counts.items())) if counts else "")
              + (f"\n   RESIDUAL: {', '.join(left)}" if left else ""))
    print("\nKept on purpose (not Safe Harbor): dates, ages, clinician and institution names" + ("" if strict else " (use --strict to replace those too)") + ".")


if __name__ == "__main__":
    main()
