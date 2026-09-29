# Distribution safety

Clippi-Health is developed inside a working data folder that may contain private health records. Git ignores those files, but a generic folder ZIP, recursive copy, or permissive packager does not honor that boundary automatically.

## Before every release

1. Run `python3 scripts/audit_distribution.py` from the repository root. It rejects tracked medical-data paths, review artifacts, home-directory paths, and non-example email addresses.
2. Run the test suites and build the Electron app.
3. Run `cd app && npm pack --dry-run --json`. The manifest must contain only `package.json`, the public README, and release files under `dist/`, including `LICENSE`, `THIRD_PARTY_NOTICES.md`, and `LICENSE.plotly.js.txt`; it must never contain `test/`, `.smoke/`, source records, generated dashboards, or local configuration.
4. Create source archives from tracked Git content, for example `git archive --format=tar.gz --output clippi-health-source.tar.gz HEAD`. Never archive the checkout directory itself.
5. Inspect the final installer or archive from a clean checkout before publishing it.

The local `raw/`, `email/`, `data/`, `dashboard.html`, curated notes, connection overrides, and smoke-test images are rebuildable working data. They are not release assets.

## Git history

Removing a sensitive file in a later commit does not remove earlier copies. Before making a repository public or mirroring it for distribution, audit every reachable commit and purge sensitive historical blobs. Contributor names and email addresses in commit metadata are also part of a source repository's public history.
