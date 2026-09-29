# Quest Diagnostics and Labcorp imports

Clippi-Health supports two local paths for Quest Diagnostics and Labcorp results:

1. Connect the laboratory in Apple Health Records, wait for the clinical records to download, then use **Health → profile → Export All Health Data** and import the ZIP in Clippi-Health.
2. Download official result PDFs from the laboratory's patient portal and import those files directly.

The Apple Health path is preferable when it includes the needed history because the export can retain structured FHIR clinical records. PDFs remain useful primary-source documents and work when a structured export is incomplete.

## Quest Diagnostics

Quest states that MyQuest results can be added to Apple Health. Its result menu also offers **Download PDF**, and MyQuest can request older electronic results dating back to January 1, 2010 when available.

- [Quest test-results and Apple Health guidance](https://www.questdiagnostics.com/patients/test-results)
- [Quest PDF download instructions](https://myquest.questdiagnostics.com/myquest-faq1/MyQuest/3056.htm?Highlight=fax)
- [MyQuest results](https://myquest.questdiagnostics.com/results)

Quest publishes a [FHIR API request form](https://privacyportal.onetrust.com/webform/168bf6fc-ead2-4217-a0df-7c602a1d8095/0f21ef1a-79a8-4bc0-80b1-89a1c16bf1af), but the public pages reviewed on September 29, 2026 do not provide the FHIR base URL, third-party app registration process, or native/public-client loopback requirements. Clippi-Health must obtain and validate those details before enabling direct OAuth. It will not borrow another application's client ID or automate the patient portal.

## Labcorp

Labcorp states that patients can view, download, and print reports in Labcorp Patient or MyLabcorp. Labcorp also supports Health Records on iPhone for users with a Labcorp Patient account.

- [Labcorp result access and downloads](https://www.labcorp.com/patients/tests/results)
- [MyLabcorp app and official-report downloads](https://www.labcorp.com/patients/mylabcorp)
- [Labcorp Health Records on iPhone announcement](https://ir.labcorp.com/news-releases/news-release-details/labcorp-enables-health-records-iphone)
- [Labcorp Patient](https://patient.labcorp.com)

Apple documents that Health Records connections use public FHIR APIs and the provider's patient-portal sign-in. This establishes that a patient-facing interoperability path exists, but Labcorp's public pages reviewed on September 29, 2026 do not publish third-party app registration or endpoint details. Clippi-Health must obtain and validate those details before enabling direct OAuth.

- [Apple: download health records on iPhone](https://support.apple.com/guide/iphone/iphc30019594/ios)
- [Apple: Health Records uses public FHIR APIs](https://support.apple.com/guide/healthregister/apda01f4d13a/web)

## Direct OAuth acceptance criteria

A Quest or Labcorp direct connector can be enabled only after the provider supplies:

- the production FHIR R4 base URL and SMART discovery metadata;
- a documented third-party app registration path;
- a Clippi-Health public client ID with PKCE and a fixed loopback redirect;
- patient-readable scopes for `Observation`, `DiagnosticReport`, `DocumentReference`, and related resources;
- permission to distribute the endpoint profile and public client identifier; and
- a synthetic sandbox or approved test account for an end-to-end validation.

Providers that require a client secret or hosted callback remain incompatible with Clippi-Health's local-only architecture.
