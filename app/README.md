# Clippi-Health desktop app

The Electron app is the local front door for importing files, rebuilding the Clippi-Health database, editing curated timeline events and notes, and reading the dashboard.

The unlicensed browser exporter and its saved portal sessions have been removed. OAuth portal connection uses a bundled, one-shot SMART-on-FHIR helper that binds to loopback and downloads records directly from the selected health system. The app includes a BJC HealthCare & Washington University endpoint profile; direct access awaits Clippi-Health's Epic production client id. Until then, the same Sources card opens BJC MyChart, gives BJC's Document Center steps, and imports the resulting ZIP locally.

## Prerequisites

- Node.js 22 for development and packaging.
- Python 3.9+ for source development.
- PyInstaller and pypdf from `../packaging/requirements-build.txt` when producing a self-contained package.

People installing a release do not need these tools. The packaged app includes the record engine and portable PDF extraction.

## Run and test

```bash
cd app
npm install
npm start
npm run typecheck
npm test
npm run smoke
```

To make an installer on the current operating system:

```bash
python3 -m pip install -r ../packaging/requirements-build.txt
npm ci
npm run make
```

Artifacts are written under `out/make/`. PyInstaller is deliberately run on each target operating system rather than cross-compiled. The GitHub **Installer builds** workflow exercises macOS Apple Silicon, macOS Intel, Windows x64, and Linux x64. Locally produced macOS apps receive an ad-hoc signature so the bundle is internally valid; evaluation macOS and Windows artifacts still lack a trusted publisher identity.

The tag-driven production workflow requires Apple Developer ID signing plus notarization and Microsoft Artifact Signing. It creates a draft release only after every platform succeeds. See [`../docs/RELEASING.md`](../docs/RELEASING.md).

The palette button in the upper-right corner offers **System**, **Light · Paper**, and **Dark** without occupying the header with a permanent selector. Paper uses a lower-glare warm canvas with high-contrast text and stronger card/control separation; Dark preserves Clippi-Health's original dark palette. The saved local preference also applies to the dashboard inside the app.

## Tabs

The header's **Try demo** button opens Sally Seastar's synthetic diabetes record in an isolated local folder. Mode selection survives restart; **Exit demo** confirms before showing your records again. Imports, provider sign-ins and external windows are disabled while demonstrating the app. See [the recording walkthrough](../docs/DEMO.md). The smoke test now uses its own disposable profile and this demo, including chart zoom verification.

- **Dashboard:** reads the generated local dashboard through the restricted `hp://root/` protocol.
- **Sources:** lists the sources in the current build, guides BJC MyChart, Quest Diagnostics, and Labcorp imports, imports user-selected local email/document ZIPs without mailbox access, starts a direct SMART connector when a registered provider profile is available, or copies Apple Health, FHIR/C-CDA, PDFs, and ordinary files into `raw/` after showing a plan. Quest and Labcorp currently use Apple Health or official-report downloads while direct third-party OAuth registration is investigated. The dashboard's **Manage sources** button opens this tab when it is viewed inside the desktop app.
- **Build:** runs `python3 healthpilot.py` and streams progress.
- **Timeline events:** edits `curated_events.csv`.
- **Notes:** edits `case_study_notes.md`.
- **Doctor:** checks prerequisites and allows the user to choose a Clippi-Health data folder.

## State and privacy

On first launch, an installed app creates its record store under the operating system's per-user application-data directory. A user can choose another folder from **Doctor**. The selected path is stored in Electron's user-data directory. Medical sources and generated outputs stay in that local folder. The app has no telemetry.

Clippi-Health has no hosted account, callback service, connector relay, or telemetry endpoint. Provider profiles must use public-client OAuth with PKCE; client secrets are forbidden. Tokens remain in the local helper's memory for one import and are discarded when it exits. See [`../docs/CONNECTORS.md`](../docs/CONNECTORS.md).
