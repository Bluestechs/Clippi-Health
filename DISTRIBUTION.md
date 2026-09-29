# Distribution safety

Clippi-Health is developed inside a working data folder that may contain private health records. Git ignores those files, but a generic folder ZIP, recursive copy, or permissive packager does not honor that boundary automatically.

## Before every release

1. Run `python3 scripts/audit_distribution.py` from the repository root. It rejects tracked medical-data paths, review artifacts, home-directory paths, and non-example email addresses.
2. Use Node 22, run the test suites, and build the Electron app. Production packages also run `app/verify-runtime.mjs` against a clean temporary record store.
3. Run `cd app && npm pack --dry-run --json`. The manifest must contain only `package.json`, the public README, and release files under `dist/`, including the project and bundled-component notices; it must never contain `test/`, `.smoke/`, source records, generated dashboards, or local configuration.
4. Create source archives from tracked Git content, for example `git archive --format=tar.gz --output clippi-health-source.tar.gz HEAD`. Never archive the checkout directory itself.
5. Inspect the final installer or archive from a clean checkout before publishing it.

The local `raw/`, `email/`, `data/`, `dashboard.html`, curated notes, connection overrides, and smoke-test images are rebuildable working data. They are not release assets.

## Installer boundary

Electron Forge packages only `app/dist/` and `app/package.json`, then adds the PyInstaller engine from ignored `app/runtime/` as an explicit resource. The engine includes executable code, templates, the public connector catalog, and Plotly. It does not include the repository's `raw/`, `email/`, `data/`, dashboard output, curated notes, local connector overrides, or app configuration.

`npm run make` builds the engine natively for the current operating system and verifies a clean-store build, JSON query, and connector listing before packaging. The installed app writes records to a per-user application-data folder unless the user chooses another location.

## Signing and publishing

- The manual **Installer builds** workflow produces short-lived unsigned evaluation artifacts on macOS Apple Silicon, macOS Intel, Windows x64, and Linux x64. Do not publish those as trusted releases.
- A `v<package-version>` tag starts **Signed release**. The workflow rejects a tag/version mismatch, missing Apple credentials, missing Microsoft configuration, a failed signature, or failed notarization.
- macOS applications are signed with Developer ID Application, notarized, and placed in a separately notarized and stapled DMG.
- Windows application binaries and the Squirrel installer are signed and timestamped with Microsoft Artifact Signing.
- The workflow creates a GitHub draft release only after all target jobs succeed. Inspect and install those draft artifacts on clean machines before publishing the draft.

The exact account and repository setup is in [`docs/RELEASING.md`](docs/RELEASING.md).

The installed dependency tree has a separate risk boundary from the build toolchain. `npm audit --omit=dev` must pass. Electron Forge's current build-only tree has upstream archive-processing advisories; it processes pinned project inputs and official Electron/npm artifacts in isolated CI, and it is not shipped in the app. Reassess and update the lockfile before each release rather than applying forced major-version audit fixes without package verification.

## Git history

Removing a sensitive file in a later commit does not remove earlier copies. Before making a repository public or mirroring it for distribution, audit every reachable commit and purge sensitive historical blobs. Contributor names and email addresses in commit metadata are also part of a source repository's public history.
