# Clippi-Health desktop app

The Electron app is the local front door for importing files, rebuilding the Clippi-Health database, editing curated timeline events and notes, and reading the dashboard.

The unlicensed browser exporter and its saved portal sessions have been removed. OAuth portal connection uses a bundled, one-shot SMART-on-FHIR helper that binds to loopback and downloads records directly from the selected health system. The app includes a BJC HealthCare & Washington University endpoint profile; direct access awaits Clippi-Health's Epic production client id. Until then, the same Sources card opens BJC MyChart, gives BJC's Document Center steps, and imports the resulting ZIP locally.

## Prerequisites

- Node.js for the Electron development build.
- Python 3.9+ for the record builder.
- On macOS, Swift/PDFKit improves PDF text extraction. Portable PDF extraction is roadmap work.

## Run and test

```bash
cd app
npm install
npm start
npm run typecheck
npm test
npm run smoke
```

The app is currently a development build and has no signed installer.

The palette button in the upper-right corner offers **System**, **Light · Paper**, and **Dark** without occupying the header with a permanent selector. Paper uses a lower-glare warm canvas with high-contrast text and stronger card/control separation; Dark preserves Clippi-Health's original dark palette. The saved local preference also applies to the dashboard inside the app.

## Tabs

- **Dashboard:** reads the generated local dashboard through the restricted `hp://root/` protocol.
- **Sources:** lists the sources in the current build, guides a one-time BJC MyChart download, imports its ZIP directly, imports user-selected local email/document ZIPs without mailbox access, starts a direct SMART connector when a registered provider profile is available, or copies Apple Health, FHIR/C-CDA, and ordinary files into `raw/` after showing a plan. The dashboard's **Manage sources** button opens this tab when it is viewed inside the desktop app.
- **Build:** runs `python3 healthpilot.py` and streams progress.
- **Timeline events:** edits `curated_events.csv`.
- **Notes:** edits `case_study_notes.md`.
- **Doctor:** checks prerequisites and allows the user to choose a Clippi-Health data folder.

## State and privacy

The selected data-folder path is stored in Electron's user-data directory. Medical sources and generated outputs stay in the chosen Clippi-Health folder and are ignored by Git. The app has no telemetry.

Clippi-Health has no hosted account, callback service, connector relay, or telemetry endpoint. Provider profiles must use public-client OAuth with PKCE; client secrets are forbidden. Tokens remain in the local helper's memory for one import and are discarded when it exits. See [`../docs/CONNECTORS.md`](../docs/CONNECTORS.md).
