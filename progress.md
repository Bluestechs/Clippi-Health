# Clippi-Health progress

Updated 2026-09-29.

## Working now

- A local Python builder imports supported health-record sources into SQLite, searchable Markdown, CSV exports, cited reference documents, and an offline dashboard.
- The Electron app provides in-app source management, rebuild controls, timeline-event and note editing, health checks, and dashboard viewing.
- Local imports cover FHIR JSONL/NDJSON, C-CDA and IHE XDM packages, Apple Health exports, Gmail Takeout MBOX, EML, correspondence folders, and ordinary document archives.
- The BJC HealthCare and Washington University MyChart profile includes accurate one-time Document Center export instructions and local ZIP/folder import.
- Quest Diagnostics and Labcorp source cards include verified Apple Health Records and official-report PDF import instructions. Direct OAuth is explicitly disabled until each laboratory provides third-party public-client registration and endpoint details.
- The direct SMART-on-FHIR helper uses the system browser, authorization code flow with PKCE, a loopback callback, read-only scopes, and an in-memory token that is discarded after each import.
- The app offers System, Paper, and Dark themes through the compact palette button in the upper-right corner.
- The public product and package name is Clippi-Health. Stable internal compatibility interfaces retain their existing names.
- The balanced Record Smile logo is the selected production direction and is already used in the desktop app. Two alternate explorations remain in `assets/logo-candidates/`, and the brand source is documented in `docs/BRAND.md`.
- The public repository README displays the production logo. Future mobile clients are expected to carry the same logo and System, Paper, and Dark theme choices.

## Release work remaining

- Derive the macOS `.icns`, Windows `.ico`, Linux icon set, and installer artwork from the selected master.
- Complete Epic registration for a Clippi-Health production public client id, then validate the BJC connection end to end.
- Submit Quest's FHIR API request and contact Labcorp about third-party patient-facing FHIR registration, then validate any offered local public-client flow before enabling it.
- Build and sign painless macOS, Windows, and Linux installers that bundle the runtime.
- Finish Windows and Linux portability, including replacement of the macOS-only PDFKit extraction path.
- Add practical Android and Health Connect export support.
- Build the optional, explicitly enabled local read-only MCP server and companion query skill.
- Add contributor and security documentation plus synthetic fixtures for community development.

## Verification

The current source catalog passes 24 Python unit tests, Electron type checking, 47 Electron component tests, and the distribution PII audit. The connector list validates BJC, Quest Diagnostics, and Labcorp profiles without enabling unverified OAuth paths. The Electron screenshot smoke run covers every tab, both explicit themes, the connector cards, and an assertion that the palette menu opens above the app content.
