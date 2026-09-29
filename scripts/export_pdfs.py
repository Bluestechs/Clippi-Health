#!/usr/bin/env python3
"""Build the two clinician-facing PDFs into data/pdf/ (local only; data/ is git-ignored):

  Clinical_Summary_<date>.pdf   clinical_summary_draft.md, reader-ready: working notes and CLI hints removed
  Case_Study_<date>.pdf         data/CASE_STUDY.md, same cleanup, internal reconciliation notes removed

    python3 scripts/export_pdfs.py            (after ./hp build)
"""
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import md2pdf  # noqa: E402

OUT = ROOT / "data" / "pdf"


def strip_cli(md):
    """Remove hints meant for people at a terminal, keep everything a reader needs."""
    md = re.sub(r"\s*\(`\./hp show <id>` opens it\)", "", md)
    md = re.sub(r";\s*full series: `\./hp labs \"<test>\"`", "", md)
    md = re.sub(r"^\*Records matched:.*$\n?", "", md, flags=re.M)
    md = re.sub(r"^\*Explore:\*.*$\n?", "", md, flags=re.M)
    md = re.sub(r" Regenerated on every `python3 healthpilot.py`\.", "", md)
    md = re.sub(r"Rebuild after editing: `\./hp build`.*$", "", md, flags=re.M)
    md = re.sub(r"`\./hp [^`]*`", "the Clippi-Health database", md)
    return md


def clinical_summary():
    src = ROOT / "clinical_summary_draft.md"
    if not src.exists():
        return None
    md = src.read_text(encoding="utf-8")
    md = md.split("\n---\n", 1)[1] if "\n---\n" in md else md          # drop the working intro
    md = md.split("\n---\n\n## Answers to the blanks list", 1)[0]       # drop the fill-in checklist
    md = md.replace("⚠ *(", "*(Record note: ").replace("⚠ *", "*Record note: ")
    md = md.replace("*Unchanged from your draft — your analysis, not a record.*", "*Patient's own analysis, for discussion.*")
    md = md.replace("*Unchanged from your draft.* ", "")
    md = md.replace("table in `data/CASE_STUDY.md`, Immune section", "table in the accompanying Case Study, Immune section")
    md = md.replace("in your draft", "in the original draft")
    md = ("*Prepared by the patient from locally collected FHIR/C-CDA, Apple Health, laboratory, and correspondence records. "
          "Values from the record are in bold and cited as (date | record title); the patient's own answers are in "
          "bold without a citation. Nothing here is a clinical opinion except where attributed.*\n\n" + md)
    return strip_cli(md)


def case_study():
    src = ROOT / "data" / "CASE_STUDY.md"
    md = src.read_text(encoding="utf-8")
    md = re.sub(r"^## Where the .*? draft clinical summary and the records differ\n.*?(?=^## )", "", md, flags=re.S | re.M)
    md = re.sub(r"^Hand-edited\. Included verbatim.*?\n\n", "", md, flags=re.S | re.M)
    md = md.replace("Topics, their order and the patient's framing come from `topics.json`; the closing section is `case_study_notes.md` verbatim.",
                    "Organized by topic; the closing section is the patient's own notes and questions.")
    md = md.replace("Written by the patient in `journal.md`; not a clinical record. Newest first.", "Written by the patient; not a clinical record. Newest first.")
    md = re.sub(r"\(events matching this topic; ◆ = written by hand in curated_events\.csv\)", "(◆ = hand-curated from the records)", md)
    return strip_cli(md)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = date.today().isoformat()
    made = []
    for name, md in (("Clinical_Summary", clinical_summary()), ("Case_Study", case_study())):
        if not md:
            continue
        src = OUT / f"{name}_{stamp}.md"
        src.write_text(md, encoding="utf-8")
        pdf = OUT / f"{name}_{stamp}.pdf"
        html_path = pdf.with_suffix(".html")
        html_path.write_text(md2pdf.md_to_html(md, name.replace("_", " ")), encoding="utf-8")
        md2pdf.render_pdf(html_path, pdf)
        html_path.unlink()
        src.unlink()
        made.append(pdf)
    for p in made:
        n = len(re.findall(rb"/Type\s*/Page[^s]", p.read_bytes()))
        print(f"{p.relative_to(ROOT)}  {p.stat().st_size / 1024:.0f} KB  ~{n} pages")


if __name__ == "__main__":
    main()
