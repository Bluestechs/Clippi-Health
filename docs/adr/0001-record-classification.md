# ADR 0001: Classify notes and visits during import

Status: Accepted

Date: 2026-09-30

## Context

The dashboard previously showed zero clinical notes and visits even when imported C-CDA files had explicit encounter structures and an email attachment was named as chart notes. The importer flattened C-CDA XML into generic searchable documents, while the dashboard counted only `documents.kind=note` and `encounters`. Reinterpreting generic document text in the dashboard would make counts dependent on UI heuristics and risk treating appointments as completed visits.

## Decision

Classify records once, at import, using source evidence. Project a C-CDA encounter only from a dated `componentOf/encompassingEncounter`. Label its linked C-CDA document a note only when its document code is the LOINC episode-summary-note code. Label FHIR documents as notes from their explicit document type, and local files from narrowly recognized note filenames. Project FHIR encounters only when status is finished/completed, and link FHIR documents by explicit Encounter reference regardless of export order. Retain original sources and provenance. The dashboard reads the normalized kinds and encounter links; it does not guess from narrative text.

## Consequences

Counts become reproducible across the CLI, generated dictionary and dashboard, and cards can open the records they count. A multi-note PDF is one imported document. Incomplete exports still produce incomplete counts; the UI calls them indexed notes and documented visits and explains the source boundary. New source formats should add an evidence-based importer mapping and synthetic fixture before a dashboard count depends on them. No migration is required while the local database remains rebuildable from raw inputs.

See the [data mapping](../DATA_MAPPING.md) for the full source-to-table contract.
