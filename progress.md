# Clippi-Health progress

Updated 2026-09-30.

## Working now

- Accessibility improvements cover keyboard tabs, named controls and status, skip links, record-reader focus and history, chart date controls, text equivalents, and sampled contrast/reflow fixes. The target is WCAG 2.2 AA; conformance is not yet claimed. See `docs/ACCESSIBILITY.md` for measured evidence and limitations.

- Vitals pairs CGM and insulin side by side with linked zoom/reset. Basal insulin is pink and bolus orange in both themes, using delivery-reason metadata from Apple Health. Missing types remain unspecified; daily subtype totals stay with the selected source's combined total. A cache-version change reparses older exports on rebuild.

- Demo mode now persists the exact personal return folder, including development defaults, across packaged launches. Unavailable folders stay selected with a recovery message. Regression tests cover both cases.

- **Try demo** creates Sally Seastar's entirely synthetic diabetes record in a separate local store. A year of simulated CGM and daily device metrics, quarterly labs, notes and timeline events populate the app for recording. Mode persists across restart; returning to personal records requires confirmation. Imports, sign-ins and external windows are disabled in demo mode. The sample exercises the real import/build/chart pipeline, and smoke tests now use a disposable demo profile.
- Populated demo coverage caught and fixed a stale care-team source lookup that could fail case-study generation when encounters included departments.

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
- GitHub CI covers the Python tests, Electron tests and type checking, the public-source audit, package-manifest inspection, and the shipped dependency audit. The four-runner evaluation workflow now builds and verifies installers successfully on macOS Apple Silicon, macOS Intel, Windows x64, and Linux x64.
- A fail-closed production workflow is ready for Developer ID/notarization and Microsoft Artifact Signing. A version tag creates a draft release only after signed platform artifacts validate.

## Release work remaining

- Complete manual pointer/tooltip and full-workflow accessibility checks, native Windows/Linux zoom and contrast checks, VoiceOver/NVDA/Linux screen-reader assessment, and a synthetic accessibility gate in CI. Track these in issues #7–#9.
- Complete Epic registration for a Clippi-Health production public client id, then validate the BJC connection end to end.
- Submit Quest's FHIR API request and contact Labcorp about third-party patient-facing FHIR registration, then validate any offered local public-client flow before enabling it.
- Create and export an Apple Developer ID Application certificate, add the notarization credentials to GitHub, and validate the signed release on both Mac architectures.
- Complete Microsoft Artifact Signing identity validation and GitHub OIDC setup, then validate the Windows release job.
- Install the verified evaluation artifacts on clean Windows and Linux machines and exercise launch, import, rebuild, and uninstall before publishing the first binary release.
- Add practical Android and Health Connect export support.
- Build the optional, explicitly enabled local read-only MCP server and companion query skill.
- Add contributor and security documentation plus synthetic fixtures for community development.

## Verification

The current source catalog passes 31 Python unit tests, Electron type checking, 55 Electron component tests, the distribution PII audit, and the production-dependency audit. The isolated fictional Electron smoke also passes 19 accessibility/navigation checks, 5 narrow-dashboard checks, 15 chart-control checks, and 73 sampled visual conditions in an ordinary-color run. Screen-reader behavior and complete WCAG conformance remain unverified. The bundled native engine passed build/query/connector checks from a clean data directory and generation/rebuild of the populated Sally Seastar demo. Both source and packaged desktop smoke runs passed all tabs, both explicit themes and CGM chart zoom checks using disposable profiles. GitHub Actions run 36618736252 built and verified DMG/ZIP artifacts for both Mac architectures, a Windows Squirrel installer, and Linux DEB/ZIP artifacts from commit `ed4c846`. A locally built macOS Apple Silicon app also passed strict bundle-signature verification and full UI screenshot smoke coverage across every tab and both explicit themes. Evaluation macOS artifacts are ad-hoc signed and Windows artifacts are unsigned until production credentials are configured.
