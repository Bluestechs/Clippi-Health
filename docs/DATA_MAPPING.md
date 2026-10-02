# Data dictionary and import mapping (DDR)

This is the durable, source-independent map for the local record model. The generated `data/DATA_DICTIONARY.md` describes the actual database, columns, counts, provenance and source gaps after each rebuild. It is private and disposable; this document can be committed without patient records.

## Data flow

`User-selected local export → raw source retained locally → parser and source classification → data/health.db → generated dictionary, searchable records and dashboard.` All projections carry a `source` key and a source file/path or resource id when supplied. SQLite row ids are regenerated; use `source_id` or source path plus title/date for durable references.

| Input and evidence | Projection | Rule and limit |
| --- | --- | --- |
| FHIR Observation with laboratory category; DiagnosticReport-contained Observation | `labs`; original in `fhir_resources` | Normalize test names and compatible units; use source observation dates. `labs_clean` excludes exact cross-source duplicates. |
| Verified, dated primary lab-report row in a supplied correspondence export | `labs` and `email_lab_evidence` | Uncertain readings, historical reprints, letters, undated rows and plausible duplicate values remain evidence only. Email transmission date is never a specimen date. |
| Apple Health clinical-record export and device samples | `labs`, `immunizations`, `vitals_daily` | Clinical FHIR records keep reported values. Device samples are daily aggregates; the raw export remains authoritative. |
| Tidepool Export Data JSON (`*tidepool*.json` in `raw/other/`) | `vitals_daily` daily glucose/insulin/carb rows, `device_samples` intraday samples, plus a `sources` entry | Delivered insulin only (bolus normal + extended; basal rate × duration); glucose in mg/dL (mmol/L × 18.01559); day/time from deviceTime else UTC time + offset; ids dedupe across files. Tidepool replaces Apple HealthKit on an overlapping day+metric; the raw export stays authoritative. |
| FHIR Encounter with `finished` or `completed` status | `encounters`; original in `fhir_resources` | Planned, in-progress and unknown-status resources remain raw only; no completed visit inferred from a date or message. |
| C-CDA `componentOf/encompassingEncounter` with an effective start date | `encounters` | Uses the explicit encounter date, code and source id when present. A C-CDA service event without an encompassing encounter does not create a visit. |
| FHIR DocumentReference/Composition with an explicit note document type | `documents.kind=note`; original FHIR resource retained | Uses the source `type` label; titles and body mentions alone do not establish note type. Composition section narrative is indexed. An explicit Encounter reference links the note after all resources are imported. |
| C-CDA with an encompassing encounter and LOINC `34133-9` episode-summary-note document code | `documents.kind=note`, linked by `encounter_id` | Other C-CDA summaries stay `kind=ccda`. Section narrative is flattened for search; original XML remains authoritative. |
| Local file or email attachment explicitly named chart/clinical/progress/consultation/visit/discharge note | `documents.kind=note` | This labels the imported file as a note. A multi-note file remains one document; it is not split into invented visits or individual notes. |
| Other local files, C-CDA summaries, emails and attachments | `documents` with `document`, `ccda`, `message` or `attachment` kind | Email attachment `date` is the enclosing email date. Authorship is not inferred from the sender; source text and provenance remain available. |
| Patient journal and hand-curated timeline | `documents.kind=journal` and `events` | Patient-authored and curated content remains distinguishable from clinical source records. |

## Dashboard count contract

The **All lab results** card counts `labs_clean` rows and opens the unfiltered lab test list. **Clinical notes** counts `documents.kind=note` and opens that records filter. **Documented visits** counts dated `encounters` through today and opens their source-linked list. **All records** counts every searchable `documents` row and clears record filters. A zero means none were indexed from supplied sources; it never means the person had no such care. Timeline events are a separate curated/derived summary and are not a visit count.

## Coverage and review

An export may include only a subset of the health system record. C-CDA sections, correspondence, and an attachment can describe care without supplying a structured encounter. Such narrative is searchable, but it cannot be promoted to a visit based on keywords. Scanned or unsupported files may have no extracted text. The generated dictionary lists actual counts and source gaps; inspect the original source before relying on an individual record. Curated timeline links can become stale when a referenced source is absent and should be reviewed rather than silently presented as verified source links.

The classification decision and its alternatives are recorded in [ADR 0001](adr/0001-record-classification.md).
