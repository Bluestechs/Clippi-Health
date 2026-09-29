# Security policy

## Reporting a vulnerability

Please use [GitHub private vulnerability reporting](https://github.com/bennydogg/clippi-health/security/advisories/new) so a report can be assessed before public disclosure. Do not open a public issue for a suspected vulnerability.

Describe the affected version, prerequisites, impact, and a minimal reproduction. Use synthetic records only. Never attach real health records, credentials, OAuth tokens, signing material, or other personal information.

## Supported versions

Security fixes are made on the latest release and `main`. Clippi-Health has not reached a stable 1.0 release, so older builds are not maintained after a fix is available.

## Security scope

Clippi-Health is designed for one user on a single-user computer. The application and its helper processes run with that user's operating-system permissions. It is not a multi-user service or a network authorization boundary.

Reports are especially useful when they show that untrusted imported records, a health-system response, a web page, or a build dependency can:

- execute code or commands;
- read or change files outside the selected local data area;
- disclose health data or credentials over the network;
- bypass SMART-on-FHIR state, PKCE, redirect, or endpoint validation;
- escape the Electron renderer sandbox or preload boundary; or
- compromise a signed installer or release artifact.

Resource exhaustion from a file the same local user deliberately imports is considered lower severity unless it crosses a trust boundary, persists, or can be triggered remotely.
