# Releasing Clippi-Health installers

Clippi-Health keeps health data local. GitHub Actions receives source code and public build inputs only; it never receives a user's record store. The production workflow creates a draft release so signed artifacts can be installed on clean machines before anyone publishes them.

## Apple setup

An Apple Development identity is suitable for development but not distribution outside the Mac App Store. The release requires a **Developer ID Application** certificate.

1. In the Apple Developer account, create a Developer ID Application certificate. Apple restricts creation of Developer ID certificates to the Account Holder role.
2. Install the certificate and its private key in Keychain Access, export both as a password-protected `.p12`, and base64-encode the file.
3. In App Store Connect → Users and Access → Integrations → App Store Connect API → **Team Keys**, create a team API key for notarization. The Account Holder may first need to request API access. Download the `.p8` once and base64-encode it. Individual API keys cannot be used with `notarytool`.
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

Apple references: [create Developer ID certificates](https://developer.apple.com/help/account/certificates/create-developer-id-certificates/), [create a CSR in Keychain Access](https://developer.apple.com/help/account/certificates/create-a-certificate-signing-request/), [create an App Store Connect team key](https://developer.apple.com/help/app-store-connect/get-started/app-store-connect-api/), and [customize the notarization workflow](https://developer.apple.com/documentation/security/customizing-the-notarization-workflow/).

## Microsoft setup

Microsoft Artifact Signing is the least burdensome current route to a publicly trusted Windows identity because Microsoft manages the short-lived signing certificate. Individual public-trust validation is currently available to developers in the United States and Canada. It still requires a one-time Azure setup and paid Artifact Signing account.

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

Once the six Apple secrets above are configured, run **Actions → Signed macOS builds → Run workflow** on `main`. This builds Apple Silicon and Intel apps, signs them with Developer ID, notarizes and staples the DMGs, verifies the app signatures, and uploads the results as workflow artifacts. It does not require Microsoft credentials, create a GitHub release, or upload any health records. Install the downloaded DMG on a clean Mac to check Gatekeeper, launch, source selection, import, rebuild, dashboard, and uninstall before offering it to testers.

The separate `Signed release` tag workflow reuses this same macOS job and still waits for Windows and Linux release gates. Do not push a version tag just to test Apple signing. If the Apple build fails, inspect its signing/notarization diagnostics before making a public release.

## Evaluation builds

Run **Actions → Installer builds → Run workflow** at any commit. It builds macOS Apple Silicon, macOS Intel, Windows x64, and Linux x64 artifacts and retains them for seven days. These are useful for clean-machine testing. macOS uses an ad-hoc bundle signature and Windows is unsigned, so operating-system trust prompts are expected.

## Production release

1. Update `app/package.json` to the intended version and commit the result on `main`.
2. Confirm CI is green.
3. Create and push the exact matching tag, for example `v0.1.0` for package version `0.1.0`.
4. The **Signed release** workflow builds native artifacts and creates a draft GitHub release. Any missing credential, tag mismatch, failed signature, or failed notarization stops the release.
5. Install the draft artifacts on clean supported machines. Check launch, source import, rebuild, dashboard, uninstall, publisher display, macOS Gatekeeper, and Windows SmartScreen.
6. Publish the draft in GitHub only after that review.

Do not upload locally generated ad-hoc or unsigned packages to a public release.
