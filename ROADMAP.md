# Roadmap

Clippi-Health is local-first. It will not operate or depend on a hosted Clippi-Health account, data relay, webhook receiver, connector aggregator, telemetry system, or remote medical-record database. Generated data is disposable and may be rebuilt when schemas change.

## Accessibility — high priority

- Target WCAG 2.2 AA for the web dashboard and Electron app; current conformance is unclaimed. Maintain the [assessment and status](docs/ACCESSIBILITY.md).
- Local chart controls and sampled zoom/spacing/contrast/focus fixes are implemented. Complete the manual and native-platform verification tracked in [chart controls and hover equivalents (#7)](https://github.com/bennydogg/clippi-health/issues/7), [zoom/reflow/contrast/focus coverage (#8)](https://github.com/bennydogg/clippi-health/issues/8), and [screen-reader assessment and regression checks (#9)](https://github.com/bennydogg/clippi-health/issues/9) as release priorities.
- Keep keyboard navigation, visible selection/context, accessible names, text chart alternatives, and predictable return behavior part of routine UI acceptance. Test using fictional records only.

## Direct connector experience

- Polish the **Connect a health system** desktop flow with cancellation, richer progress, and provider-specific recovery guidance. The app owns the helper lifecycle; users never manage a daemon or terminal process.
- Support each user completing their own Epic public/native registration and entering their own production public client ID locally. Do not make direct BJC access depend on a shared maintainer registration or ship a shared production ID; validate provider activation and the complete connection for user-supplied registrations.
- Submit Quest's official FHIR API request and contact Labcorp interoperability support for patient-facing FHIR endpoint and public-client onboarding details. Enable direct OAuth only after each provider supports PKCE, a loopback redirect, distributable client registration, and synthetic end-to-end testing. The app already includes verified Apple Health and PDF import instructions for both laboratories.
- Add reviewed endpoint profiles and provider-specific manual download instructions to the signed local catalog.
- Keep OAuth tokens in memory for one import and require a fresh login for later pulls.
- Treat providers that require a confidential server-held secret as unsupported; guide those users to manual FHIR/C-CDA export.
- Keep generic FHIR NDJSON and C-CDA import paths for sources without direct SMART support.

## Record coverage and import fidelity

- Keep note and visit classification in the importer, grounded in structured source metadata or an explicitly named note file. The overview cards open the exact normalized records counted in the database; they do not infer a complete lifetime care history.
- Surface source-level coverage limits, extend standards-backed note and encounter mapping, and flag unresolved curated timeline source links. Track this work in [record coverage #10](https://github.com/bennydogg/clippi-health/issues/10).
- Maintain the durable [data mapping](docs/DATA_MAPPING.md), generated private data dictionary, and [classification ADR](docs/adr/0001-record-classification.md) together when an import rule changes.

## Cross-platform desktop

- Normalize browser launching, loopback OAuth callbacks, paths, permissions, encodings, long paths, and process lifecycle across all three operating systems.
- Remove assumptions about Homebrew, Xcode tools, Apple Health, and macOS LaunchAgents from the core workflow.
- Give future iOS and Android clients the same Clippi logo and System/Paper/Dark theme choices as the desktop app.

## Installation for non-technical users

- Apple credentials are configured and signed/notarized Mac builds passed on both architectures. Validate the resulting DMGs on clean Apple Silicon and Intel machines, then publish a reviewed Mac beta independently of the Windows signing setup; see [release instructions](docs/RELEASING.md).
- Prefer Microsoft Store MSIX for trusted Windows distribution; implement its packaging/update/certification path when account registration is available. Keep explicitly unsigned x64/ARM64 evaluation builds separate from that future release. No Azure signing account is configured.
- Native Linux x64/ARM64 DEB and portable ZIP packages passed installed/extracted fictional smoke on Ubuntu 24.04. Complete fresh-machine and Debian ARM64 VM testing; older glibc compatibility and portable ZIP sandbox setup remain qualification boundaries.
- Add a Linux AppImage or Flatpak alongside the existing `.deb` and ZIP packages if community demand justifies the extra format.
- Add first-run source connection, data-folder selection, update checks, repair, and uninstall behavior.

## Android and non-Apple health data

- Add a source-adapter interface that maps imported samples into the existing daily metric model while retaining raw provenance.
- Support practical Android exports, prioritizing Health Connect-compatible exports and well-documented Google Fit/Samsung Health archives as their available formats permit.
- Add source-specific duplicate handling so the same wearable or lab observation is not counted twice after cross-device imports.
- Keep FHIR clinical records separate from consumer-device measurements while presenting both in one timeline.

## Optional agent access through MCP

- Ship a separate, opt-in local MCP server over the generated SQLite database.
- Start with read-only, bounded tools for source listing, schema inspection, lab series, timeline queries, document search, and citation retrieval.
- Avoid arbitrary SQL by default; offer an advanced read-only query tool with statement validation and row/size limits.
- Make every tool return provenance and stable source identities so agents can cite the underlying record.
- Add explicit enable/disable controls, loopback-only transport, local authentication, audit logs, and redaction/export controls.
- Keep the MCP server absent or disabled in the default installation so installing Clippi-Health does not grant agent access.

## Community readiness

- Publish connector and importer fixtures containing synthetic data only.
- Add a contributor guide, security policy, threat model, and issue templates.
- Document the boundary between Apache-2.0 project code, third-party dependencies, and remote health systems selected by the user.
- Design schemas around open standards and retain unsupported source data verbatim so community adapters can evolve without data loss.
