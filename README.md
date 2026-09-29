<p align="center"><img src="assets/clippi-health-logo.png" alt="Clippi-Health paperclip and heart logo" width="160"></p>

# Clippi-Health

Clippi-Health turns personal health exports into a local SQLite database, searchable records, a single-file dashboard, and cited reference documents. It accepts standards-based FHIR and C-CDA records, Apple Health exports, local correspondence exports, and ordinary documents.

The project is licensed under Apache-2.0. The former bundled MyChart browser exporter was removed because its source had no license and therefore could not safely be copied, modified, or redistributed.

The public product name is **Clippi-Health**. Existing `hp`, `healthpilot.py`, `healthpilot-source.json`, and `hp://` identifiers remain stable compatibility interfaces. See the [logo candidates](docs/BRAND.md) and the current [project progress](progress.md).

## What it builds

| Artifact | Purpose |
|---|---|
| `data/health.db` | Normalized SQLite tables plus verbatim FHIR resources and email lab evidence |
| `dashboard.html` | Offline dashboard with charts, timeline, and record search |
| `data/DATA_DICTIONARY.md` | Generated schema, provenance, and data-quality reference |
| `data/CASE_STUDY.md` | Topic-organized record with citations |
| `data/export/*.csv` | Portable table exports |
| `data/records/*.md` | One searchable Markdown file per document |

All medical data is ignored by Git. Source data stays under `raw/` or `email/`; generated data stays under `data/` and `dashboard.html`.

## Supported inputs

- **FHIR records (JSONL/NDJSON):** direct SMART-on-FHIR downloads and user-supplied exports under `raw/fhir/<source>/`. Every resource is retained in `fhir_resources`; common clinical resources are also projected into labs, encounters, conditions, procedures, medications, immunizations, allergies, and documents.
- **C-CDA / IHE XDM:** standards-based record-download folders under `raw/other/`.
- **Apple Health:** Export All Health Data zips under `raw/apple/`, including clinical FHIR records and HealthKit device data.
- **Local email/document ZIPs:** Gmail Takeout MBOX, standard EML messages, and PDF/DOCX/HTML/text/XML/image members under `raw/imports/`. Archives are read offline and remain intact.
- **Correspondence exports:** provenance-preserving email folders under `email/`, with optional OCR sidecars and lab evidence.
- **Loose files:** PDF, HTML, text, and XML files under `raw/other/`.

## Run it

The core builder uses Python 3.9+ and the standard library.

```bash
./hp setup
./hp add ~/Downloads/export.zip
./hp build
./hp open
```

Common queries:

```bash
./hp summary
./hp labs "IgG"
./hp search copper zinc --kind note
./hp timeline --since 2025
./hp sql "SELECT resource_type, count(*) FROM fhir_resources GROUP BY resource_type"
```

Put `--json` before a command for machine-readable output. See generated `data/DATA_DICTIONARY.md` for the complete schema and provenance model.

## Local SMART-on-FHIR connector

Clippi-Health has no hosted service. Its connector helper runs only on the user's computer, opens the selected health system in the system browser, receives OAuth on loopback, and downloads FHIR directly to local storage. It uses public-client OAuth with PKCE, persists no token, and exits after the import.

The signed local catalog includes a BJC HealthCare & Washington University MyChart endpoint profile. Direct connection becomes available after Clippi-Health receives an Epic production public client id; app-owner setup lives in the desktop **Sources** tab and a local override stays under ignored `raw/connectors/`. Providers that require a server-held client secret are intentionally unsupported.

The BJC profile also works immediately without app registration: **Sources** shows BJC's current **Your Menu → Document Center** instructions, opens BJC MyChart, and accepts the downloaded ZIP or record folder. MyChart IHE XDM ZIPs are parsed directly during the local rebuild, so they do not need to be unpacked first.

Quest Diagnostics and Labcorp cards provide verified Apple Health Records and portal-PDF import instructions. Direct OAuth remains disabled until each laboratory supplies a documented third-party public-client registration and endpoint profile. See [`docs/LAB_EXPORTS.md`](docs/LAB_EXPORTS.md).

Developer commands:

```bash
./hp smart list
./hp smart connect fhir-example
./hp smart import patient-export.jsonl --source fhir-example --org "Example Health"
```

The complete trust boundary and provider-profile format are documented in [`docs/CONNECTORS.md`](docs/CONNECTORS.md). The exact Epic owner checklist is in [`docs/EPIC_REGISTRATION.md`](docs/EPIC_REGISTRATION.md). Production provider registrations and installer work are tracked in [`ROADMAP.md`](ROADMAP.md).

## Desktop app

The Electron app imports local files, rebuilds the database, edits curated events and notes, and reads the dashboard:

```bash
cd app
npm install
npm start
```

See [`app/README.md`](app/README.md). Packaging and cross-platform installers are roadmap work.

Before publishing a source archive or desktop package, follow [`DISTRIBUTION.md`](DISTRIBUTION.md) and run `python3 scripts/audit_distribution.py`. Never ZIP a working data folder: ignored source records and generated outputs can still be present on disk.

## Local correspondence exports

The desktop **Sources** tab accepts a local ZIP without connecting to an email account. For Gmail, label the searched conversations and create a one-time Mail export for that label in Google Takeout. For Outlook on the web or new Outlook, download the selected messages as EML files, put them in a folder, and ZIP the folder. PST, OLM, and MSG parsing is not bundled yet.

The structured path below remains available for exports that include reviewed OCR and lab-evidence metadata.

Place each export under `email/` and add `healthpilot-source.json`:

```json
{"key": "email-example", "org": "Practice correspondence", "patient_addresses": ["patient@example.test"]}
```

The importer keeps messages, original attachments, supplied OCR, chronology files, and every `labs.csv` evidence row. Only dated, verified primary lab-report rows enter lab charts; ambiguous readings and restated values remain reviewable evidence.

## Repository layout

```text
healthpilot.py        database builder
fhir_records.py       generic FHIR JSONL retention and clinical projections
smart_connect.py      local one-shot SMART OAuth/FHIR connector helper
archive_records.py    offline email/document ZIP importer
email_records.py      local correspondence and OCR-evidence importer
reports.py            generated data dictionary and cited case study
hp                    command-line front door
app/                  Electron desktop shell
scripts/              dashboard, PDF, redaction, and serving helpers
vendor/               third-party browser assets with their own licenses
```

## Privacy

Clippi-Health does not include telemetry or operate a hosted service. Direct connections send authorization and record requests only to the health system selected by the user. Portal credentials are entered on that system's page, records download directly to the user's computer, and one-shot OAuth tokens are discarded when the local helper exits.

`raw/`, `email/`, `data/`, `dashboard.html`, curated notes, and connection metadata can contain protected health information. They are ignored by Git and must not be committed.

## License

Clippi-Health is licensed under the [Apache License 2.0](LICENSE). Bundled third-party components retain their own licenses; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
