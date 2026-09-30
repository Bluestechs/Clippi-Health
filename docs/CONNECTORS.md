# Local connector architecture

Clippi-Health has a strict local-first boundary: it does not operate or depend on a hosted Clippi-Health service. Medical records move directly from a health system selected by the user to the user's computer. There is no relay, cloud account, webhook receiver, telemetry endpoint, or remote Clippi-Health database.

## Direct SMART-on-FHIR flow

The intended user flow is:

1. For direct Epic access, the user completes their own registration and saves their own production public client ID in **Sources → Your registration for direct connection**. No maintainer/shared ID ships with the app. Without a local ID, direct access is unavailable; manual export remains available. The user then clicks **Connect**.
2. The app starts its bundled connector helper on loopback (`127.0.0.1`) and opens the system browser.
3. The helper discovers the health system's SMART endpoints and begins public-client OAuth with PKCE.
4. The user signs in and consents on the health system's own page.
5. The health system redirects the browser to the helper's fixed loopback callback, `http://127.0.0.1:8765/oauth/callback` for BJC.
6. The helper validates OAuth state, exchanges the code with the PKCE verifier, and downloads FHIR directly from that health system.
7. The helper writes NDJSON under `raw/fhir/<source>/`, discards the access token when it exits, and rebuilds the local record.

The helper is an implementation detail of the installed app. The app starts it for a connection, streams status into the UI, stops it when complete, and handles failures. A user should not install, configure, or supervise a separate daemon.

The protocol is defined by [SMART App Launch](https://hl7.org/fhir/smart-app-launch/). Provider profiles contain public configuration: organization name, FHIR base URL, registered loopback redirect URI, scopes, and supported resource types. The public client ID comes only from the selected local store's `raw/connectors/` override; a catalog ID is not used as a fallback. Client secrets are forbidden. The client ID identifies a registered app, not a patient; the user signs in separately to obtain patient authorization.

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

This path needs no developer/app registration or public client ID and makes no portal request on the user's behalf. It is also the fallback for providers where direct SMART access is unavailable.

## Coverage limitation

SMART authorization requires an app registration accepted by the EHR authorization service; it does not universally require each patient to register as a developer. Clippi-Health chooses per-user Epic registration rather than a maintainer-operated shared registration. A fully local connector works where a health system accepts that registration as a public/native client with a loopback redirect. If a provider requires a confidential client with a server-held secret, Clippi-Health cannot support that provider without violating this architecture. The app explains that limitation and offers manual FHIR or C-CDA import.

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

The catalog includes the verified BJC HealthCare & Washington University FHIR R4 endpoint with an empty client ID. Each Clippi-Health user follows their own Epic registration, terms, and data-use requirements, then saves their own production public ID in **Sources** as an ignored override under the selected store's `raw/connectors/`. A new store has direct access disabled, and removing the local ID disables it again. Saving an ID enables a connection attempt; it does not prove Epic/BJC activation. The bundled manual-export flow remains available without registration. Synthetic tests exercise the helper without sending records off-device.

## Adding provider profiles

Profiles live in `connectors/*.json`. Start from `connectors/provider.example.json`, document the provider's public-client registration, and verify the exact redirect URI and scopes in a sandbox before distributing the endpoint profile. Leave the catalog's `client_id` empty: users supply their own public IDs locally, and the loader never falls back to a catalog ID. Public client IDs are identifiers, not secrets, but are not distributed as a shared Clippi-Health registration. A profile may ship before user activation when it provides a verified endpoint and manual export instructions; direct connection remains unavailable until the selected store has its own configured ID.

For the BJC profile, follow [`EPIC_REGISTRATION.md`](EPIC_REGISTRATION.md). It records your Epic app settings, identity and data-use information, sandbox and production sequence, automatic-distribution caveat, and BJC activation fallback.
