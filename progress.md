# Clippi-Health progress

Updated 2026-10-01.

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
- GitHub CI covers Python/Electron tests, type checking, public-source/package/dependency audits. All six native Mac/Windows/Linux targets passed the actual packaged-app gate from common commit `a114c3c`. CI run 36801161341 and Security run 36801161388 also passed.
- Signed Mac [run 36801160834](https://github.com/bennydogg/clippi-health/actions/runs/36801160834) built Developer ID signed/notarized Apple Silicon and Intel applications with stapled DMGs, then mounted and exercised both delivered images. Windows/Linux [run 36801229535](https://github.com/bennydogg/clippi-health/actions/runs/36801229535) passed native architecture, engine, and installed/extracted UI checks. The separate production workflow remains fail-closed on Microsoft signing.
- [Beta 1.0](https://github.com/bennydogg/clippi-health/releases/tag/beta-1.0) is published as a GitHub prerelease, not a draft. Its true annotated Git tag `beta-1.0` points to `a114c3c`. All nine installer/ZIP assets include the current fixes, with uploaded digests matching `SHA256SUMS`. The superseded mixed-source draft downloads were removed after replacement verification. The unauthenticated release page and public manifest download were exercised. Beta 1.0 is release metadata; internal app version remains 0.1.0. Fresh-machine and complete assistive-technology acceptance remain disclosed beta limitations.

## Release work remaining

- Complete manual pointer/tooltip and full-workflow accessibility checks, VoiceOver/NVDA/Linux screen-reader assessment, physical GPU/OS accessibility conditions, and the complete WCAG regression gate. All six native targets pass sampled zoom, contrast, and focus checks. Track remaining assessment in issues #7–#9.
- Validate BJC direct access using each user's own Epic public/native registration and locally entered production client ID. No maintainer-wide production registration or shared ID is required by the selected product design; actual provider acceptance/activation remains unverified.
- Submit Quest's FHIR API request and contact Labcorp about third-party patient-facing FHIR registration, then validate any offered local public-client flow before enabling it.
- Complete clean-machine Apple Silicon/Intel installation, Gatekeeper launch, real import/recovery, rebuild, and uninstall acceptance before production readiness; native fictional mounted-app smokes and local Apple Silicon Gatekeeper already pass.
- Complete Microsoft Store MSIX packaging/certification and account registration for trusted Windows distribution. Azure signing is not configured; current Windows evaluation packages are intentionally unsigned.
- Complete clean Windows/Linux installation, import/recovery, rebuild, GPU, and uninstall acceptance beyond the native fictional beta gates.
- Add practical Android and Health Connect export support.
- Build the optional, explicitly enabled local read-only MCP server and companion query skill.
- Add contributor and security documentation plus synthetic fixtures for community development.

## Verification

Both downloaded DMGs from signed run 36801160834 passed local disk-image checksum and stapled-ticket validation. The Apple Silicon app additionally passed deep/strict signature verification and Gatekeeper assessment (`Notarized Developer ID`). Both native Mac architectures passed the actual mounted-DMG fictional engine/UI gate in CI: 24 navigation, 5 narrow-dashboard, 15 chart-control, and 73 visual samples. This is not clean-machine or complete assistive-technology acceptance.

Native Windows/Linux x64/ARM64 jobs passed engine build/query/catalog checks, the populated fictional demo, 24 navigation assertions, 5 narrow-dashboard checks, 15 chart controls, and 73 visual samples per extracted/installed smoke in run 36801229535. Windows x64 Setup was installed and exercised; ARM64 is a native portable ZIP. Windows text enlargement now grows the palette control, and Sources catalog refreshes preserve focused DOM when unchanged. Linux DEB/ZIP runs used Ubuntu 24.04 with Xvfb/software rendering; sandbox behavior was not relaxed. Debian ARM64 VM, older glibc, physical GPU, screen readers, and clean-machine uninstall remain unverified.

The per-user Epic checklist now renders as generated semantic HTML, not raw Markdown, in a sandboxed local window. Actual packaged Mac inspection verified formatted headings/lists/emphasis/code and HTTPS references, plus 360px reflow without horizontal overflow. The guide is a frontend asset rather than an engine resource; packaged users still need no Python or Markdown-file association.

The tagged source passes 37 Python tests, TypeScript checking, and 55 Electron component tests. The bundled native engines pass clean-store build/query/catalog and populated-demo rebuild checks. Public beta Mac DMGs are Developer ID signed/notarized; Windows and Linux packages are explicitly unsigned. Source/package/dependency audits remain CI requirements.
