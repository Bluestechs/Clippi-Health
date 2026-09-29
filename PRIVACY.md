# Clippi-Health data-use and privacy policy

Clippi-Health is local software for importing, organizing, searching, and citing a person's own health records. It does not operate a Clippi-Health account, hosted data service, connector relay, analytics service, or telemetry endpoint.

## Data the app accesses

Clippi-Health accesses only sources the user chooses. These may include FHIR clinical records, C-CDA record downloads, Apple Health exports, local email or document exports, and files selected on the user's computer. A direct health-system connection may read patient demographics, allergies, care plans and teams, conditions, diagnostic reports, documents, encounters, goals, immunizations, medications, observations, and procedures.

## How the data is used and stored

The app uses health data to build a local SQLite database, searchable record files, cited summaries, CSV exports, and an offline dashboard. Source records and generated files remain in the user's selected data folder on that computer. Clippi-Health keeps them until the user deletes or replaces them. The project does not receive or retain a server-side copy.

For a direct SMART-on-FHIR import, Clippi-Health opens the health system's own sign-in and consent page. The user's portal password is never entered into Clippi-Health. The health system sends authorized records directly to the computer. The OAuth access token is kept only in the local connector process and is discarded when that one import ends; Clippi-Health does not persist refresh tokens.

## Sharing and secondary use

Clippi-Health does not sell health data, use it for advertising, or transfer it to a project-operated service. It does not give third parties access to the local record. A user can separately choose to copy, open, or share files produced by the app; those user-directed actions are outside Clippi-Health's local processing.

## User control

The user chooses every source, can inspect the retained original files and provenance, can remove imported sources from the local data folder, and can rebuild generated outputs. Removing a source locally does not change the original record held by a healthcare organization. A user can revoke a direct app authorization from MyChart's **Linked Apps and Devices** activity.

## Security and support

Direct connections use the system browser, OAuth authorization code flow, PKCE S256, a fixed loopback callback, and a new high-entropy state value for each attempt. Clippi-Health requests read-only patient access and does not include a client secret in the distributed app.

Security or privacy concerns can be reported through the project's public issue tracker. Distributors should replace this sentence with their maintained support or security-reporting URL before release. Do not include health records, portal credentials, access tokens, or other sensitive personal information in a public issue.
