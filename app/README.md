# Clippi-Health desktop app

The Electron app is the local front door for importing files, rebuilding the Clippi-Health database, editing curated timeline events and notes, and reading the dashboard.

The unlicensed browser exporter and its saved portal sessions have been removed. OAuth portal connection uses a bundled, one-shot SMART-on-FHIR helper that binds to loopback and downloads records directly from the selected health system. The app includes a BJC HealthCare & Washington University endpoint profile. For direct access, each user completes their own Epic registration, supplies the requested identity/data-use information, accepts Epic's terms, and saves their own production public client ID in **Sources → Your registration for direct connection**. Clippi-Health does not provide a maintainer/shared ID. It is saved only in the selected local record store; without it, direct access stays unavailable. Saving an ID enables an attempt, not proof of Epic/BJC activation. The same Sources card opens BJC MyChart, gives BJC's Document Center steps, and imports the resulting ZIP locally without developer/app registration. See [your registration checklist](../docs/EPIC_REGISTRATION.md).

## Prerequisites

- Node.js 22 for development and packaging.
- Python 3.9+ for source development.
- macOS/Windows packaging: PyInstaller and pypdf from `../packaging/requirements-build.txt`.
- Linux packaging: a running Docker engine (or Podman with `CONTAINER_ENGINE=podman`); Python and runtime build dependencies are installed in the baseline container.

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
# macOS/Windows only; Linux installs these inside its container.
if [ "$(uname -s)" != Linux ]; then
  python3 -m pip install -r ../packaging/requirements-build.txt
fi
npm ci
npm run make

Beta 1.0 now contains fixed Linux x64/ARM64 DEB/ZIP assets from `2939089`, verified in native [run 36813492802](https://github.com/Bluestechs/Clippi-Health/actions/runs/36813492802). Both engines passed the glibc 2.35 baseline checks and both installed/extracted desktop gates passed on Ubuntu 24.04. The beta tag and macOS/Windows assets are unchanged; updated release notes and `SHA256SUMS` identify the replacement downloads. Re-download the fixed DEB and use `sudo apt install --reinstall ./Clippi-Health-beta-1.0-linux-arm64.deb` (or the x64 filename) when replacing internal version 0.1.0. Never replace system glibc.
```

Artifacts are written under `out/make/`. PyInstaller runs natively on each target. Linux always freezes the engine in an Ubuntu 22.04/glibc 2.35 container with system Python 3.10, then runs build, Doctor, query, connector, and demo checks there; the host Python is not used. DEBs require `libc6 (>= 2.35)`. The GitHub **Installer builds** workflow covers macOS Apple Silicon/Intel and Windows/Linux x64/ARM64; `platforms` selects Windows/Linux targets and `include_macos` controls optional Mac evaluation packages. Windows x64 produces unsigned Squirrel Setup and ZIP; ARM64 is a native ZIP because Squirrel wrappers are Intel binaries. Linux runners remain Ubuntu 24.04, with installed/extracted-app smoke. A corrected ARM64 DEB also passed installed demo/UI smoke in Debian 12 with glibc 2.36; fresh-machine/GPU acceptance remains separate. Prefer DEB; portable ZIP requires a configured Chromium sandbox. Headless smoke uses Xvfb and evaluation-only software rendering, without disabling sandboxing. Published Beta 1.0 Linux assets predate this fix; see [`../docs/RELEASING.md`](../docs/RELEASING.md).

The tag-driven production workflow requires Apple Developer ID signing plus notarization and Microsoft Artifact Signing. It creates a draft release only after every platform succeeds. See [`../docs/RELEASING.md`](../docs/RELEASING.md).

The palette button in the upper-right corner offers **System**, **Light · Paper**, and **Dark** without occupying the header with a permanent selector. Paper uses a lower-glare warm canvas with high-contrast text and stronger card/control separation; Dark preserves Clippi-Health's original dark palette. The saved local preference also applies to the dashboard inside the app.

## Tabs

The header's **Try demo** button opens Sally Seastar's synthetic diabetes record in an isolated local folder. Mode selection survives restart; **Exit demo** confirms before showing your records again. Imports, provider sign-ins and external windows are disabled while demonstrating the app. See [the recording walkthrough](../docs/DEMO.md). The smoke test now uses its own disposable profile and this demo, including chart zoom verification.

- **Dashboard:** reads the generated local dashboard through the restricted `hp://root/` protocol. Vitals pairs glucose with pink basal/orange bolus insulin charts and synchronized date zoom/reset; see [the diabetes view](../docs/DIABETES_VIEW.md).
- **Sources:** lists the sources in the current build, guides BJC MyChart, Quest Diagnostics, and Labcorp imports, imports user-selected local email/document ZIPs without mailbox access, starts a direct SMART connector when a registered provider profile is available, or copies Apple Health, FHIR/C-CDA, PDFs, and ordinary files into `raw/` after showing a plan. Quest and Labcorp currently use Apple Health or official-report downloads while direct third-party OAuth registration is investigated. The dashboard's **Manage sources** button opens this tab when it is viewed inside the desktop app.
- **Build:** runs `python3 healthpilot.py` and streams progress.
- **Timeline events:** edits `curated_events.csv`.
- **Notes:** edits `case_study_notes.md`.
- **Doctor:** checks prerequisites and allows the user to choose a Clippi-Health data folder.

## State and privacy

On first launch, an installed app creates its record store under the operating system's per-user application-data directory. A user can choose another folder from **Doctor**. The selected path is stored in Electron's user-data directory. Medical sources and generated outputs stay in that local folder. The app has no telemetry.

Clippi-Health has no hosted account, callback service, connector relay, or telemetry endpoint. Your public client ID identifies your registered app, not your patient account; sign in separately on the provider's page. This per-user registration is Clippi-Health policy, not a universal SMART requirement for patients. The ID stays under the selected store's `raw/connectors/`; removing it disables direct access, and choosing another store uses that store's configuration. Provider profiles use public-client OAuth with PKCE/state and the BJC callback `http://127.0.0.1:8765/oauth/callback`; client secrets are forbidden. Tokens remain in the local helper's memory for one import and are discarded when it exits. See [`../docs/CONNECTORS.md`](../docs/CONNECTORS.md).
