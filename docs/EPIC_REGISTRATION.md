# Your Epic registration for the BJC MyChart connector

For direct MyChart access in Clippi-Health, **each app user registers their own use of the app with Epic and supplies their own production public client ID**. Clippi-Health does not provide a maintainer-owned or shared client ID. You create your Epic developer account, provide the identity and data-use information Epic requests, accept the terms yourself, and complete activation for your registration. Do not use an ID copied from another app or another user.

This is Clippi-Health's product policy, not a claim that SMART on FHIR universally requires every patient to have a developer account. A public client ID identifies the registered app; it is not a patient identity, password, or client secret. You still sign in and consent separately on BJC MyChart for each import.

The manual **MyChart download → Clippi-Health import** path does not require this registration.

## Information to prepare

- App name: **Clippi-Health**. Do not put “Epic” in the product name.
- Public documentation: the project's published HTTPS documentation for the release you are using, or documentation you provide that accurately describes your registered use.
- Data-use policy: the project's published `PRIVACY.md` as a description of Clippi-Health, plus any information Epic requests about your own registered use. Review it; do not claim a different operator's identity or data practices as your own.
- A short product summary, product screenshot, and project thumbnail/logo.
- Your own legal/business identity as requested by Epic's developer-account form. Supply accurate information and follow Epic's current eligibility and account requirements; do not enter the maintainer's identity.

Review the documentation, privacy policy, and Epic's current terms before registering. Your questionnaire answers must describe your actual use of this local-only app. An issued ID or a saved local configuration does not by itself establish that Epic or BJC has activated the registration.

## App configuration

Create your app registration from [Epic on FHIR → Build Apps](https://fhir.epic.com/Developer/Apps) with these settings:

- Primary user / consumer type: **Patients**.
- Direction: **Incoming API**.
- Launch: patient-facing **standalone** OAuth 2.0 / SMART on FHIR.
- Default FHIR version: **R4**.
- Client type: native/public, non-confidential. Do not provision a client secret, backend credential, or refresh token.
- Redirect URI: `http://127.0.0.1:8765/oauth/callback` exactly, including the path and port.
- Security: authorization code flow with PKCE S256. Clippi-Health already generates a new verifier and OAuth state for every connection.
- Access: read-only patient access. Register only the R4 APIs needed for Patient plus AllergyIntolerance, CarePlan, CareTeam, Condition, DiagnosticReport, DocumentReference, Encounter, Goal, Immunization, MedicationRequest, MedicationStatement, Observation, and Procedure reads/searches.

Epic generally requires HTTPS redirect URIs in production, but its native-app guidance explicitly permits localhost/loopback redirects for native apps and recommends PKCE. Confirm that Epic accepts the exact `127.0.0.1` URI before marking the record ready for production. Do not substitute a hosted callback; Clippi-Health has no hosted service.

If Epic offers automatic distribution for the chosen patient-facing USCDI APIs, use it only if the final API selection qualifies. Qualifying patient-facing apps are distributed automatically to US Epic organizations. Otherwise, BJC must request or receive the client record for its environment before the connection will work.

## Register, test, and activate

1. Create your app registration, save it, and mark it ready for Sandbox.
2. Copy your **non-production** client ID. Epic says changes can take up to an hour to reach its sandbox.
3. Test the complete standalone flow against Epic's sandbox using its sandbox endpoint and non-production ID: login, consent, loopback callback, token exchange, FHIR reads, local import, rebuild, and token disposal. The bundled BJC endpoint is production, not the sandbox; do not use a sandbox ID there.
4. Complete the Data Use Questionnaire accurately for your own registration. The answers are shown during patient authorization. Keep the requested APIs consistent with your data-use information.
5. Finalize your app details, accept Epic's terms yourself, and mark your registration Ready for Production.
6. Copy your **production** public client ID. Epic warns that most app-record details cannot be changed after this point; material technical changes require a new app record.
7. In Clippi-Health, open **Sources → BJC HealthCare MyChart → Your registration for direct connection**, paste your production public client ID, and select **Save your client ID locally**. It is saved under `raw/connectors/` in the selected local record store, not in the app's bundled provider catalog or a hosted service. Never enter a client secret or token.
8. Run a real BJC connection test by choosing **Connect**, then sign in and consent on BJC's page. Saving an ID enables an attempt; it does not verify production activation or record access. Keep your ID local—do not put it in `connectors/bjc-mychart.json`, commit it, or distribute it to other users.

To remove it, open **Your direct connection settings → Remove your local client ID**. Direct access becomes unavailable again; manual export stays available. Choosing a different record store uses that store's own configuration and does not carry your ID across.

If BJC rejects your production client as unknown, first confirm your registration is Ready for Production and qualifies for automatic distribution. If it does not, provide BJC your production client ID so the appropriate BJC/Epic administrator can request or sync its client record. Actual activation and Epic's acceptance of this per-user registration approach must be confirmed for your registration; they are not guaranteed by Clippi-Health.

## Official references

- [Epic developer resources and deployment sequence](https://open.epic.com/DeveloperResources)
- [Epic app creation, sandbox, production activation, and Data Use Questionnaire](https://fhir.epic.com/Documentation?docId=cms_access_playbook)
- [Epic native-app loopback and PKCE guidance](https://fhir.epic.com/Documentation?docid=searchparameters&section=FHIR_Params__postfilter_unsupported)
- [BJC HealthCare & Washington University endpoint in Epic's endpoint directory](https://open.epic.com/MyApps/Endpoints)
