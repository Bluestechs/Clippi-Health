# Provider profiles

This directory is the signed, local provider catalog used by `smart_connect.py`. The example file is documentation and is ignored by the profile loader.

A provider profile may contain verified manual-export instructions without an OAuth endpoint. A direct endpoint may be bundled when its provenance is verified, but catalog `client_id` values must stay empty. Each user registers their own use of Clippi-Health and supplies their own public client ID in the selected local store. The loader never uses a bundled ID as a fallback. Saving an ID enables an attempt, not proof of provider activation; verify the full flow against the health system. BJC uses the fixed callback `http://127.0.0.1:8765/oauth/callback`. Profiles must never contain a client secret, access token, refresh token, portal password, or patient identifier.

The desktop app presents bundled profiles by name, provides their manual download path, and labels direct connection status. Manual-only profiles cannot accept a client ID until their endpoint and OAuth contract have been verified. Your public client ID entered for a verified direct profile is written to ignored `raw/connectors/` in the selected store, not to the catalog. Removing it disables direct access again. Follow [your Epic registration checklist](../docs/EPIC_REGISTRATION.md) for BJC; manual MyChart export needs no developer/app registration. Running the helper directly is for development:

```bash
./hp smart list
./hp smart connect fhir-example
./hp smart import export.ndjson --source fhir-example --org "Example Health"
```
