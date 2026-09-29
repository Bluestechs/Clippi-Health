#!/usr/bin/env python3
"""Packaged Clippi-Health processing engine used by the Electron application."""
import os
import runpy
import sys
from pathlib import Path


def resource_root():
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)).resolve()


def initialize_data_root():
    configured = os.environ.get("CLIPPI_HEALTH_ROOT")
    if not configured:
        return
    root = Path(configured).expanduser().resolve()
    for child in ("raw/apple", "raw/imports", "raw/other", "raw/fhir", "data"):
        (root / child).mkdir(parents=True, exist_ok=True)
    marker = root / "clippi-health.json"
    if not marker.exists():
        marker.write_text('{\n  "format": "clippi-health-record-store",\n  "version": 1\n}\n')


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in {"build", "query", "smart"}:
        raise SystemExit("usage: clippi-runtime {build|query|smart} [arguments ...]")
    command = sys.argv.pop(1)
    resources = resource_root()
    os.environ.setdefault("CLIPPI_HEALTH_RESOURCES", str(resources))
    initialize_data_root()

    if command == "build":
        import healthpilot
        sys.argv = ["clippi-runtime build", *sys.argv[1:]]
        healthpilot.main()
    elif command == "smart":
        import smart_connect
        sys.argv = ["clippi-runtime smart", *sys.argv[1:]]
        smart_connect.main()
    else:
        sys.argv = ["hp", *sys.argv[1:]]
        runpy.run_path(str(resources / "hp"), run_name="__main__")


if __name__ == "__main__":
    main()
