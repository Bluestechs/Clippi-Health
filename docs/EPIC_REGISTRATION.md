# Epic registration for the BJC MyChart connector

Direct MyChart access needs a client id issued specifically to Clippi-Health. Epic's registration is self-service and free for standards-based public APIs, but the app owner must create the account, provide business identity information, answer the patient-app Data Use Questionnaire, accept Epic's terms, and mark the app ready. Do not use a client id copied from another app.

The manual **MyChart download → Clippi-Health import** path does not require this registration.

## Information to prepare

- App name: **Clippi-Health**. Do not put “Epic” in the product name.
- Public documentation: the final HTTPS URL where the distributor publishes this project's `README.md`.
- Data-use policy: the final HTTPS URL where the distributor publishes `PRIVACY.md`.
- A short product summary, product screenshot, and project thumbnail/logo.
- The legal/business identity requested for an Epic on FHIR developer account: name, company email and name, country, and business address. Epic's current signup form also accepts a phone number and website.

Review the public documentation and privacy policy before production registration so they describe the release that users will actually receive.

## App configuration

Create the app from [Epic on FHIR → Build Apps](https://fhir.epic.com/Developer/Apps) with these settings:

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

1. Create the app, save it, and mark it ready for Sandbox.
2. Copy the **non-production** client id. Epic says changes can take up to an hour to reach its sandbox.
3. Test the complete standalone flow against Epic's sandbox: login, consent, loopback callback, token exchange, FHIR reads, local import, rebuild, and token disposal.
4. Complete the Data Use Questionnaire accurately. The answers are shown during patient authorization. Keep the requested APIs consistent with the data-use policy.
5. Finalize the app details, accept Epic's terms, and mark it Ready for Production.
6. Copy the **production** client id. Epic warns that most app-record details cannot be changed after this point; material technical changes require a new app record.
7. In Clippi-Health, open **Sources → BJC HealthCare MyChart → App-owner setup**, paste the production public client id, and run a real BJC connection test.
8. After a successful BJC test, put that same public production id in `connectors/bjc-mychart.json` for signed releases. A public client id identifies the app; it is not a client secret.

If BJC rejects a production client as unknown, first confirm the app is Ready for Production and qualifies for automatic distribution. If it does not, the remaining work is customer activation: provide BJC the production client id so the appropriate BJC/Epic administrator can request or sync its client record.

## Official references

- [Epic developer resources and deployment sequence](https://open.epic.com/DeveloperResources)
- [Epic app creation, sandbox, production activation, and Data Use Questionnaire](https://fhir.epic.com/Documentation?docId=cms_access_playbook)
- [Epic native-app loopback and PKCE guidance](https://fhir.epic.com/Documentation?docid=searchparameters&section=FHIR_Params__postfilter_unsupported)
- [BJC HealthCare & Washington University endpoint in Epic's endpoint directory](https://open.epic.com/MyApps/Endpoints)
