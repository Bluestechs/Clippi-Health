#!/usr/bin/env python3
"""Audit the complete npm graph with one narrowly scoped build-only exception."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


APP = Path(__file__).resolve().parents[1] / "app"
ALLOWED = {
    "GHSA-w3rx-r6r6-pgpr": {
        "package": "image-size",
        "version": "0.7.5",
        "reason": (
            "image-size 0.7.5 is reachable only from the macOS DMG builder and reads the "
            "repository-controlled background image; it never handles imported health data"
        ),
    }
}


def main() -> int:
    completed = subprocess.run(
        ["npm", "audit", "--json"],
        cwd=APP,
        check=False,
        capture_output=True,
        text=True,
    )
    try:
        report = json.loads(completed.stdout)
    except json.JSONDecodeError:
        print(completed.stdout)
        print(completed.stderr)
        return 1

    lock = json.loads((APP / "package-lock.json").read_text(encoding="utf-8"))
    packages = lock.get("packages", {})
    advisories: dict[str, str] = {}
    runtime_nodes: list[str] = []
    for package_name, vulnerability in report.get("vulnerabilities", {}).items():
        for node in vulnerability.get("nodes", []):
            if not packages.get(node, {}).get("dev", False):
                runtime_nodes.append(node)
        for via in vulnerability.get("via", []):
            if not isinstance(via, dict):
                continue
            url = str(via.get("url", ""))
            advisory = url.rstrip("/").rsplit("/", 1)[-1]
            if advisory:
                advisories[advisory] = package_name

    unexpected = sorted(advisories.keys() - ALLOWED.keys())
    mismatched: list[str] = []
    for advisory, package_name in advisories.items():
        if advisory not in ALLOWED:
            continue
        expected = ALLOWED[advisory]
        version = packages.get(f"node_modules/{package_name}", {}).get("version")
        if package_name != expected["package"] or version != expected["version"]:
            mismatched.append(f"{advisory} affects {package_name}@{version}")
    total = report.get("metadata", {}).get("vulnerabilities", {}).get("total", 0)
    if unexpected or mismatched or runtime_nodes or (total and not advisories):
        print(completed.stdout)
        problems = unexpected or mismatched or runtime_nodes or ["unidentified advisory"]
        print("Unexpected npm security findings: " + ", ".join(problems))
        return 1

    if advisories:
        for advisory in sorted(advisories):
            print(f"Accepted build-only advisory {advisory}: {ALLOWED[advisory]['reason']}")
    else:
        print("No npm security advisories found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
