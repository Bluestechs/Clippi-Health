# Local connector architecture

Clippi-Health has a strict local-first boundary: it does not operate or depend on a hosted Clippi-Health service. Medical records move directly from a health system selected by the user to the user's computer. There is no relay, cloud account, webhook receiver, telemetry endpoint, or remote Clippi-Health database.

## Direct SMART-on-FHIR flow

The intended user flow is:

1. The user clicks **Connect a source** in the desktop app.
2. The app starts its bundled connector helper on loopback (`127.0.0.1`) and opens the system browser.
3. The helper discovers the health system's SMART endpoints and begins public-client OAuth with PKCE.
4. The user signs in and consents on the health system's own page.
5. The health system redirects the browser to the helper's fixed loopback callback.
6. The helper validates OAuth state, exchanges the code with the PKCE verifier, and downloads FHIR directly from that health system.
7. The helper writes NDJSON under `raw/fhir/<source>/`, discards the access token when it exits, and rebuilds the local record.

The helper is an implementation detail of the installed app. The app starts it for a connection, streams status into the UI, stops it when complete, and handles failures. A user should not install, configure, or supervise a separate daemon.

The protocol is defined by [SMART App Launch](https://hl7.org/fhir/smart-app-launch/). Provider profiles contain only public configuration: organization name, FHIR base URL, public client id, registered loopback redirect URI, scopes, and supported resource types. Client secrets are forbidden.

## Product boundary

- Bind callbacks to loopback only, on a fixed registered port; never listen on a LAN interface.
- Open authorization in the system browser; never collect portal credentials inside Clippi-Health.
- Use PKCE and a fresh, high-entropy OAuth state for every attempt.
- Send bearer tokens only to the authenticated FHIR origin that issued them.
- Keep access tokens in memory for a one-shot import, then discard them. The user signs in again for a later refresh.
- Store original FHIR resources locally and retain provenance through every projection.
- Bundle a signed provider catalog with app releases rather than querying a Clippi-Health directory service.
- Do not add tunnels, hosted callbacks, connector aggregators, remote analytics, or crash reports containing record data.

## Manual MyChart download

The bundled BJC profile includes a no-registration path in the desktop **Sources** tab. It opens the official BJC MyChart login and gives the current BJC steps: open **Your Menu**, choose **Document Center**, select the appropriate record request, and download the result when MyChart says it is ready. The user can select the ZIP itself or an uncompressed record folder. Clippi-Health recognizes IHE XDM packages inside the ZIP and parses their C-CDA XML locally during the rebuild.

This path needs no Clippi-Health app id and makes no portal request on the user's behalf. It is also the fallback for providers where direct SMART access is unavailable.

## Coverage limitation

SMART requires an app to be registered with an EHR authorization service. A fully local connector works where a health system accepts a public/native client and a loopback redirect. If a provider requires a confidential client with a server-held secret, Clippi-Health cannot support that provider without violating this architecture. The app should explain that limitation and offer manual FHIR or C-CDA import.

## Current implementation

`smart_connect.py` provides the local connector engine:

- validates public-client provider profiles;
- discovers SMART authorization and token endpoints;
- uses authorization-code OAuth with S256 PKCE and state validation;
- receives the callback on loopback only;
- fetches patient-context FHIR resources directly, with same-origin pagination checks;
- atomically replaces the prior local NDJSON export;
- persists source metadata but never OAuth tokens;
- imports an existing FHIR NDJSON export without OAuth.

The catalog includes the verified BJC HealthCare & Washington University FHIR R4 endpoint. It intentionally has no borrowed client id: direct connection remains disabled until Epic issues a production public client id for Clippi-Health. An app owner can enter that public identifier in **Sources**; it is saved as an ignored local override under `raw/connectors/`. The bundled manual-export flow remains available without it. Synthetic tests exercise the helper without sending records off-device.

## Adding provider profiles

Profiles live in `connectors/*.json`. Start from `connectors/provider.example.json`, complete the provider's public-client registration, and verify the exact redirect URI and scopes in a sandbox before distributing it. Public client ids are identifiers, not secrets, but every profile must still be reviewed for provenance and permitted redistribution. A profile may ship with an empty client id when it provides a verified endpoint and manual export instructions; the app must label direct connection as unavailable until configured.

For the BJC profile, follow [`EPIC_REGISTRATION.md`](EPIC_REGISTRATION.md). It records the intended Epic app settings, required owner-supplied information, sandbox and production sequence, automatic-distribution caveat, and BJC activation fallback.
