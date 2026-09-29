#!/usr/bin/env python3
"""Reject mutable third-party GitHub Action references."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
USES = re.compile(r"^\s*-?\s*uses:\s*([^\s#]+)", re.MULTILINE)
PINNED = re.compile(r"^[^/@\s]+/[^@\s]+(?:/[^@\s]+)?@[0-9a-f]{40}$")


def main() -> int:
    failures: list[str] = []
    references = 0
    for path in sorted((*WORKFLOWS.glob("*.yml"), *WORKFLOWS.glob("*.yaml"))):
        text = path.read_text(encoding="utf-8")
        for match in USES.finditer(text):
            reference = match.group(1)
            references += 1
            if reference.startswith("./") or PINNED.fullmatch(reference):
                continue
            line = text.count("\n", 0, match.start()) + 1
            failures.append(f"{path.relative_to(ROOT)}:{line}: mutable action reference {reference}")

    if failures:
        print("\n".join(failures))
        return 1
    print(f"Verified {references} immutable workflow action references.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
