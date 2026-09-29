# Provider profiles

This directory is the signed, local provider catalog used by `smart_connect.py`. The example file is documentation and is ignored by the profile loader.

A provider profile may contain verified manual-export instructions without an OAuth endpoint. A direct endpoint may be bundled before activation when its provenance is verified. Direct connection is enabled only after the health system has registered Clippi-Health as a public/native SMART client and the complete flow has been tested against that system. Direct profiles must use a fixed loopback callback ending in `/oauth/callback`; profiles must never contain a client secret, access token, refresh token, portal password, or patient identifier.

The desktop app presents bundled profiles by name, provides their manual download path, and labels direct connection status. Manual-only profiles cannot accept a client ID until their endpoint and OAuth contract have been verified. A public client id entered for a verified direct profile is written to ignored `raw/connectors/`, not to the catalog. Running the helper directly is for development:

```bash
./hp smart list
./hp smart connect fhir-example
./hp smart import export.ndjson --source fhir-example --org "Example Health"
```
