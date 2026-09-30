# Clippi-Health progress

Updated 2026-09-30.

## Working now

- Overview cards now open unfiltered labs, indexed clinical notes, documented visits, and all searchable records. C-CDA import projects dated encompassing encounters and their explicitly coded episode notes; FHIR import keeps only finished/completed visits, tags documents from source type, and links explicit encounter references. Clearly named local note files are tagged during import. The durable mapping is in `docs/DATA_MAPPING.md`, with the decision in `docs/adr/0001-record-classification.md`; the generated private dictionary reflects each rebuild.
- The selected Clippi logo now appears in the Electron header, the macOS Dock, and the standalone web dashboard. Electron sets its Dock icon at startup even when launched through the development binary; the dashboard embeds the compact PNG in its generated HTML for offline use.
- Source exports can still omit or bundle real notes and visits; source-level coverage and unresolved curated timeline links are tracked in [#10](https://github.com/bennydogg/clippi-health/issues/10).

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
- GitHub CI covers Python/Electron tests, type checking, public-source/package/dependency audits. Native Windows/Linux x64/ARM64 installed/extracted apps passed the full fictional desktop gate in [run 36791002050](https://github.com/bennydogg/clippi-health/actions/runs/36791002050) at `07b38c7`; native engine and executable architectures were checked. CI run 36791002122 and Security run 36791002093 also passed.
- Apple signing credentials are configured. The independent signed macOS workflow passed for Apple Silicon and Intel in [run 36777412583](https://github.com/bennydogg/clippi-health/actions/runs/36777412583) at commit `efa6daa`, producing Developer ID signed/notarized apps and notarized, stapled DMGs. The full release workflow remains fail-closed on Microsoft signing and other platform gates; no public release was created.
- [Desktop Beta 1](https://github.com/bennydogg/clippi-health/releases/tag/untagged-5f48cb7b18bd41b3984f) remains a draft prerelease. Nine installer/ZIP assets are attached: original signed Mac DMGs, unsigned Windows x64 Setup/ZIP and ARM64 ZIP, and Linux x64/ARM64 r2 DEB/ZIP packages. All uploaded asset digests and the checksum manifest match local SHA-256 values. Superseded Linux assets were removed after verified uploads. GitHub's assigned draft tag and original signed Mac target remain unchanged. Source commits and latest-fix coverage are explicit per platform; original Mac assets do not contain the later Windows/Linux fixes. Publication remains gated on clean-machine acceptance.

## Release work remaining

- Complete manual pointer/tooltip and full-workflow accessibility checks, VoiceOver/NVDA/Linux screen-reader assessment, physical GPU/OS accessibility conditions, and the complete WCAG regression gate. Native Windows/Linux sampled zoom, contrast, and focus checks pass. Track remaining assessment in issues #7–#9.
- Validate BJC direct access using each user's own Epic public/native registration and locally entered production client ID. No maintainer-wide production registration or shared ID is required by the selected product design; actual provider acceptance/activation remains unverified.
- Submit Quest's FHIR API request and contact Labcorp about third-party patient-facing FHIR registration, then validate any offered local public-client flow before enabling it.
- Install the signed/notarized macOS artifacts on clean Apple Silicon and Intel machines and exercise Gatekeeper acceptance, launch, import, rebuild, and uninstall before publishing a Mac beta.
- Complete Microsoft Store MSIX packaging/certification and account registration for trusted Windows distribution. Azure signing is not configured; current Windows evaluation packages are intentionally unsigned.
- Install the verified evaluation artifacts on clean Windows and Linux machines and exercise launch, import, rebuild, and uninstall before publishing the first binary release.
- Add practical Android and Health Connect export support.
- Build the optional, explicitly enabled local read-only MCP server and companion query skill.
- Add contributor and security documentation plus synthetic fixtures for community development.

## Verification

The downloaded Apple Silicon artifact from signed run 36777412583 passed local DMG checksum and stapled-ticket validation, deep/strict app signature verification, and Gatekeeper assessment (`Notarized Developer ID`). Its signed app passed the isolated fictional smoke: 24 navigation, 5 narrow-dashboard, 15 chart-control, and 73 visual samples, plus paired-chart and demo return-folder checks. Launching directly from the mounted image emitted sandbox-extension warnings; the smoke completed successfully. This is not clean-machine installation or Intel runtime acceptance.

Native Windows/Linux x64/ARM64 jobs passed engine build/query/catalog checks, the populated fictional demo, 24 navigation assertions, 5 narrow-dashboard checks, 15 chart controls, and 73 visual samples per extracted/installed smoke in run 36791002050. Windows x64 Setup was installed and exercised; ARM64 is a native portable ZIP. Windows text enlargement now grows the palette control, and Sources catalog refreshes preserve focused DOM when unchanged. Linux DEB/ZIP runs used Ubuntu 24.04 with Xvfb/software rendering; sandbox behavior was not relaxed. Debian ARM64 VM, older glibc, physical GPU, screen readers, and clean-machine uninstall remain unverified.

The per-user Epic checklist now renders as generated semantic HTML, not raw Markdown, in a sandboxed local window. Actual packaged Mac inspection verified formatted headings/lists/emphasis/code and HTTPS references, plus 360px reflow without horizontal overflow. The guide is a frontend asset rather than an engine resource; packaged users still need no Python or Markdown-file association.

The current checkout passes 37 Python unit tests, TypeScript checking, and 55 Electron component tests. The bundled native engine passed clean-store build/query/catalog and populated-demo rebuild checks. Existing source/package/dependency audits remain part of CI. Evaluation Mac artifacts are ad-hoc signed; Windows evaluation artifacts are unsigned, separate from the original Developer ID signed/notarized Mac draft assets.
