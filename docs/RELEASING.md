# Releasing Clippi-Health installers

Clippi-Health keeps health data local. GitHub Actions receives source code and public build inputs only; it never receives a user's record store. The production workflow creates a draft release so signed artifacts can be installed on clean machines before anyone publishes them.

## Apple setup

An Apple Development identity is suitable for development but not distribution outside the Mac App Store. The release requires a **Developer ID Application** certificate.

1. Reuse a valid Developer ID Application identity with its private key, or create one through Xcode → Settings → Accounts → Manage Certificates → + → Developer ID Application. The developer website and a manually generated CSR are an alternative, not an additional requirement. Apple restricts creation of these certificates to the Account Holder role.
2. Export the certificate and private key together as a password-protected `.p12`, and base64-encode the file. The GitHub workflow requires an exportable identity rather than a cloud-managed private key.
3. In App Store Connect → Users and Access → Integrations → App Store Connect API → **Team Keys**, create a team API key for this workflow. The Account Holder may first need to request API access. Download the `.p8` once, retain the Key ID and Issuer ID, and base64-encode the file. Current `notarytool` also supports individual API keys without an issuer; this workflow and Forge configuration require a Team key and issuer.
4. Add these GitHub Actions secrets:

   | Secret | Value |
   |---|---|
   | `MACOS_CERTIFICATE_P12_BASE64` | Base64 contents of the exported `.p12` |
   | `MACOS_CERTIFICATE_PASSWORD` | Export password for that `.p12` |
   | `MACOS_SIGN_IDENTITY` | Complete `Developer ID Application: … (TEAMID)` identity |
   | `APPLE_API_KEY_BASE64` | Base64 contents of the App Store Connect `.p8` key |
   | `APPLE_API_KEY_ID` | API key id |
   | `APPLE_API_ISSUER` | App Store Connect issuer id |

The workflow imports the certificate into an ephemeral keychain, signs and notarizes the app, notarizes and staples the DMG, validates both, and discards the runner.

Keep private-key exports outside the checkout or in the ignored local signing-credential directory. Base64 is encoding, not encryption. Never put passwords or key contents in chat, logs, or command arguments; use secure local entry and standard input when configuring GitHub secrets.

Apple references: [create Developer ID certificates](https://developer.apple.com/help/account/certificates/create-developer-id-certificates/), [create a CSR in Keychain Access](https://developer.apple.com/help/account/certificates/create-a-certificate-signing-request/), [create an App Store Connect team key](https://developer.apple.com/help/app-store-connect/get-started/app-store-connect-api/), and [customize the notarization workflow](https://developer.apple.com/documentation/security/customizing-the-notarization-workflow/).

## Microsoft setup

The steps below configure the existing direct-download Squirrel EXE pipeline using paid Azure Artifact Signing. Microsoft manages its short-lived certificates, but signing alone does not eliminate initial SmartScreen reputation warnings. Individual Public Trust validation is currently available in the United States and Canada. No Azure account has been configured for this project.

An alternative to assess before purchasing signing is Microsoft Store distribution as **MSIX**: Microsoft re-signs the package after certification, with no purchased signing certificate and no SmartScreen reputation prompts during Store installation. The Store EXE/MSI path still requires publisher Authenticode signing. The current app builds Squirrel EXE installers, not MSIX; Store distribution requires a separate packaging, installation/update, and certification workstream. See [Microsoft code-signing options](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/code-signing-options).

1. Create or use an Azure subscription whose billing profile type and legal details match the intended individual identity.
2. Register the `Microsoft.CodeSigning` resource provider.
3. Create a Basic Artifact Signing account, complete individual public identity validation in the Azure portal, and create a Public Trust certificate profile.
4. Create a Microsoft Entra application or managed identity for GitHub Actions. Add a GitHub federated credential for this repository and assign **Artifact Signing Certificate Profile Signer** at the narrowest applicable scope.
5. Add these GitHub Actions secrets:

   | Secret | Value |
   |---|---|
   | `AZURE_CLIENT_ID` | Entra application/client id |
   | `AZURE_TENANT_ID` | Entra tenant id |
   | `AZURE_SUBSCRIPTION_ID` | Azure subscription id |

6. Add these GitHub Actions repository variables:

   | Variable | Value |
   |---|---|
   | `AZURE_ARTIFACT_SIGNING_ENDPOINT` | Regional account endpoint, such as `https://eus.codesigning.azure.net/` |
   | `AZURE_ARTIFACT_SIGNING_ACCOUNT` | Artifact Signing account name |
   | `AZURE_ARTIFACT_SIGNING_PROFILE` | Public Trust certificate profile name |

The workflow uses GitHub OIDC, so no long-lived Azure client secret is stored. It signs previously unsigned application binaries before Squirrel packages them, then signs and verifies the final Setup executable.

Microsoft references: [Artifact Signing quickstart](https://learn.microsoft.com/azure/artifact-signing/quickstart), [GitHub OIDC authentication](https://github.com/Azure/artifact-signing-action/blob/main/docs/authentication.md), and the [official Artifact Signing action](https://github.com/Azure/artifact-signing-action).

## Signed macOS beta builds

Once the six Apple secrets above are configured, run **Actions → Signed macOS builds → Run workflow** on `main`. This builds Apple Silicon and Intel apps, signs/notarizes the applications, notarizes/staples the DMGs, validates signatures, and mounts each delivered image to verify native executable/engine architecture, clean-store engine behavior, and the actual fictional desktop smoke before upload. It requires no Microsoft credentials and uploads no health records. Fresh-machine installation, full import/recovery, and uninstall acceptance remain separate.

Both architectures passed the signed workflow and actual mounted-app gate in [run 36801160834](https://github.com/bennydogg/clippi-health/actions/runs/36801160834), from commit `a114c3c`, on 2026-10-01. Both downloaded DMGs also passed local image/ticket validation; the Apple Silicon app passed deep/strict signature verification and Gatekeeper assessment (`Notarized Developer ID`).

The published [Beta 1.0 prerelease](https://github.com/bennydogg/clippi-health/releases/tag/beta-1.0) contains nine installer/ZIP assets plus `SHA256SUMS`, all built from `a114c3c`. Its annotated Git tag is `beta-1.0`; Git tags cannot contain spaces. Beta 1.0 is release metadata and the internal app version remains 0.1.0. Every platform now includes the latest per-user registration, formatted-guide, reflow, and Sources focus fixes. The former mixed-source draft assets were removed only after replacement upload digests matched local SHA-256 values. Publication was explicitly requested with incomplete fresh-machine and assistive-technology acceptance disclosed; this is not production or clinical-use acceptance.

The separate `Signed release` tag workflow reuses this same macOS job and still waits for Windows and Linux release gates. Do not push a version tag just to test Apple signing. If the Apple build fails, inspect its signing/notarization diagnostics before making a public release.

## Evaluation builds

Run **Actions → Installer builds → Run workflow** on the selected source commit. Native builders cover macOS Apple Silicon/Intel, Windows x64/ARM64, and Linux x64/ARM64; artifacts are retained for seven days. Choose Windows/Linux targets with `platforms` and disable `include_macos` when the separate signed Mac workflow supplies release artifacts. Mac evaluation packages use ad-hoc signatures; unsigned Windows/Linux packages must be explicitly labeled. The published beta uses signed/notarized Mac DMGs, not ad-hoc Mac artifacts.

Windows x64 produces an unsigned Squirrel Setup EXE and portable ZIP. Windows ARM64 produces a native portable ZIP only: the Squirrel installer wrappers are Intel binaries, so they are not offered as native ARM64 installers. The workflow checks native PE architecture and launches the extracted ZIP; x64 also installs Setup silently and exercises the installed app. Publisher/SmartScreen warnings are expected for these evaluation builds. Microsoft Store MSIX is the preferred future distribution path; its packaging/certification work and identity registration remain separate. No Azure signing account or paid service is configured.

Linux x64/ARM64 produces `.deb` and portable ZIP packages on native Ubuntu 24.04 runners. The bundled engine is frozen separately in `packaging/Dockerfile.linux-runtime` using Ubuntu 22.04 system Python 3.10 and glibc 2.35; do not substitute the runner's newer Python. `runtime:prepare` runs the build, Doctor, query, connector, and populated-demo checks inside that baseline container before packaging. DEBs declare `libc6 (>= 2.35)`. The workflow checks ELF/DEB architecture, installs the DEB, and exercises installed/extracted apps with fictional records. Headless smoke uses Xvfb and `--disable-gpu` only for evaluation. ZIP smoke configures the extracted Chromium sandbox helper as root-owned with mode 4755. Prefer DEB; never run the app as root or disable its sandbox.

The corrected ARM64 engine passed on glibc 2.35, and a locally rebuilt ARM64 DEB passed installed-engine and actual demo/UI smoke on Debian 12 (glibc 2.36), including 73 visual conditions. Evidence is local under `app/out/linux-glibc-smoke/`; this is container verification, not fresh-machine, GPU, screen-reader, update, or uninstall acceptance. Linux x64 baseline runtime execution remains unverified locally. No Python/Node development tools are required by packaged users.

Beta 1.0 Windows/Linux packages passed their Ubuntu 24.04/native Windows gates in [run 36801229535](https://github.com/bennydogg/clippi-health/actions/runs/36801229535), from tagged `a114c3c`. Those published Linux packages predate the compatibility fix: an ARM64 installation reported `GLIBC_2.38 not found` while loading bundled Python 3.12, which prevents both Doctor and demo loading. Reinstalling the same asset cannot fix it. The locally verified replacement is `app/out/linux-glibc-smoke/clippi-health_0.1.0_arm64.deb` (SHA-256 `c41f79aa8243be6e94996aaf07772a091012dc969170a9d1a4048a22467a6005`); it has not been published and keeps internal version 0.1.0. Publish newly built assets under a new prerelease/tag rather than changing the existing tag or implying the old packages passed Debian verification. Windows packages remain intentionally unsigned; the separate `v*` production signing gate is unchanged.

## Production release

1. Update `app/package.json` to the intended version and commit the result on `main`.
2. Confirm CI is green.
3. Create and push the exact matching tag, for example `v0.1.0` for package version `0.1.0`.
4. The **Signed release** workflow builds native artifacts and creates a draft GitHub release. Any missing credential, tag mismatch, failed signature, or failed notarization stops the release.
5. Install the draft artifacts on clean supported machines. Check launch, source import, rebuild, dashboard, uninstall, publisher display, macOS Gatekeeper, and Windows SmartScreen.
6. Publish the draft in GitHub only after that review.

Do not publish local ad-hoc builds as trusted signed packages. Explicitly approved prereleases may contain CI-verified unsigned Windows/Linux artifacts with prominent trust and acceptance warnings, as Beta 1.0 does. Production publication still requires the signing and clean-machine gates above.
