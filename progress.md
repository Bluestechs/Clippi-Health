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
- The desktop app now packages a self-contained local record engine with pypdf, its connector catalog, templates, and browser assets. Installed users do not need Python, Node, Git, or terminal commands.
- Branded macOS ICNS, Windows ICO, and Linux PNG assets are generated from the selected logo. Electron packages use the Clippi-Health bundle id and medical-app category.
- Electron Forge makes DMG/ZIP, Windows Squirrel, and DEB/ZIP artifacts. Every build verifies the bundled runtime against a temporary clean record store before packaging.
- GitHub CI covers the Python tests, Electron tests and type checking, the public-source audit, package-manifest inspection, and the shipped dependency audit. A separate four-runner workflow builds evaluation installers.
- A fail-closed production workflow is ready for Developer ID/notarization and Microsoft Artifact Signing. A version tag creates a draft release only after signed platform artifacts validate.

## Release work remaining

- Complete Epic registration for a Clippi-Health production public client id, then validate the BJC connection end to end.
- Submit Quest's FHIR API request and contact Labcorp about third-party patient-facing FHIR registration, then validate any offered local public-client flow before enabling it.
- Create and export an Apple Developer ID Application certificate, add the notarization credentials to GitHub, and validate the signed release on both Mac architectures.
- Complete Microsoft Artifact Signing identity validation and GitHub OIDC setup, then validate the Windows release job.
- Run the new native jobs and clean-machine install/uninstall tests on Windows and Linux; address any platform-specific findings before publishing the first binary release.
- Add practical Android and Health Connect export support.
- Build the optional, explicitly enabled local read-only MCP server and companion query skill.
- Add contributor and security documentation plus synthetic fixtures for community development.

## Verification

The current source catalog passes 24 Python unit tests, Electron type checking, 47 Electron component tests, the distribution PII audit, and the production-dependency audit. The bundled native engine passed build/query/connector checks from a clean data directory. A locally built macOS Apple Silicon app passed strict bundle-signature verification and full UI screenshot smoke coverage across every tab and both explicit themes; its DMG and ZIP were built successfully. That local artifact is ad-hoc signed and remains an evaluation build until Developer ID notarization is configured.
