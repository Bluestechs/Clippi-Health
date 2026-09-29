# Clippi-Health progress

Updated 2026-09-29.

## Working now

- A local Python builder imports supported health-record sources into SQLite, searchable Markdown, CSV exports, cited reference documents, and an offline dashboard.
- The Electron app provides in-app source management, rebuild controls, timeline-event and note editing, health checks, and dashboard viewing.
- Local imports cover FHIR JSONL/NDJSON, C-CDA and IHE XDM packages, Apple Health exports, Gmail Takeout MBOX, EML, correspondence folders, and ordinary document archives.
- The BJC HealthCare and Washington University MyChart profile includes accurate one-time Document Center export instructions and local ZIP/folder import.
- The direct SMART-on-FHIR helper uses the system browser, authorization code flow with PKCE, a loopback callback, read-only scopes, and an in-memory token that is discarded after each import.
- The app offers System, Paper, and Dark themes through the compact palette button in the upper-right corner.
- The public product and package name is Clippi-Health. Stable internal compatibility interfaces retain their existing names.
- The balanced Record Smile logo is the selected production direction and is already used in the desktop app. Two alternate explorations remain in `assets/logo-candidates/`, and the brand source is documented in `docs/BRAND.md`.

## Release work remaining

- Derive the macOS `.icns`, Windows `.ico`, Linux icon set, and installer artwork from the selected master.
- Complete Epic registration for a Clippi-Health production public client id, then validate the BJC connection end to end.
- Build and sign painless macOS, Windows, and Linux installers that bundle the runtime.
- Finish Windows and Linux portability, including replacement of the macOS-only PDFKit extraction path.
- Add practical Android and Health Connect export support.
- Build the optional, explicitly enabled local read-only MCP server and companion query skill.
- Add contributor and security documentation plus synthetic fixtures for community development.

## Verification

This branding and theme-menu update passes 22 Python unit tests, Electron type checking, 47 Electron component tests, a full local record rebuild, and the Electron screenshot smoke run. The smoke run covers every tab, both explicit themes, the BJC connector card, and an assertion that the palette menu opens above the app content.
