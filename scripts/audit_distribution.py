#!/usr/bin/env python3
"""Fail when tracked release sources contain likely local or personal material."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SENSITIVE_PATHS = (
    re.compile(r"^(?:raw|email|data)/"),
    re.compile(r"^dashboard\.html$"),
    re.compile(r"(?:^|/)(?:clinical_summary|case_study_notes|journal|unresolved-questions)", re.I),
    re.compile(r"(?:^|/)(?:gemini|pathologist)_review_", re.I),
    re.compile(r"(?:^|/)redact\.json$", re.I),
    re.compile(r"(?:^|/)\.smoke/", re.I),
)
HOME_PATH = re.compile(r"/(?:Users|home)/[^/\s]+")
EMAIL = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
SAFE_EMAIL_DOMAINS = {"example.com", "example.test"}
SKIP_CONTENT = {"LICENSE", "app/package-lock.json", "vendor/plotly-basic.min.js"}


def release_source_files() -> list[str]:
    raw = subprocess.check_output(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
    )
    return [name for name in raw.decode().split("\0") if name]


def main() -> int:
    findings: list[str] = []
    for name in release_source_files():
        if any(pattern.search(name) for pattern in SENSITIVE_PATHS):
            findings.append(f"sensitive tracked path: {name}")
        if name in SKIP_CONTENT:
            continue
        path = ROOT / name
        try:
            text = path.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if HOME_PATH.search(line):
                findings.append(f"absolute home path: {name}:{number}")
            for address in EMAIL.findall(line):
                domain = address.rsplit("@", 1)[1].lower()
                if domain not in SAFE_EMAIL_DOMAINS:
                    findings.append(f"non-example email address: {name}:{number}")
    if findings:
        print("Distribution audit failed:")
        for finding in sorted(set(findings)):
            print(f"- {finding}")
        return 1
    print("Distribution audit passed: release sources contain no blocked paths or personal markers.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
