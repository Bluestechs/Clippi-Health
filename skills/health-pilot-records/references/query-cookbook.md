# Clippi-Health query cookbook

Run examples from the repository root. Put `--json` before the command.

## Orientation and provenance

```bash
./hp --json summary
./hp sources
./hp schema
```

```sql
SELECT key, org, kind, system, exported_at, coverage_from, coverage_to, record_counts, gaps
FROM sources ORDER BY key;
```

## Find records and retrieve citations

```bash
./hp search "small fiber" neuropathy --limit 25
./hp search copper zinc --kind note --since 2025-01-01
./hp show 41 --full
```

Search uses SQLite FTS5. For phrases and prefixes:

```bash
./hp search '"nerve conduction"' 'neuropath*'
```

## Lab series

```bash
./hp tests 'copper|zinc|cerulo'
./hp labs '^Copper$' --since 2024-01-01
```

```sql
SELECT date, test, value_num, comparator, units, ref_low, ref_high, flag, org, source, source_id
FROM labs_clean
WHERE test IN ('Copper', 'Zinc', 'Ceruloplasmin')
ORDER BY date, test;
```

Use `labs_clean` for ordinary trends. Audit excluded duplicates separately:

```sql
SELECT d.id, d.date, d.test, d.value_text, d.units, d.source, d.dup_of,
       kept.source AS kept_source, kept.source_file AS kept_file
FROM labs d LEFT JOIN labs kept ON kept.id=d.dup_of
WHERE d.dup_of IS NOT NULL ORDER BY d.date, d.test;
```

## OCR and correspondence evidence

Review rows kept out of charts:

```sql
SELECT import_status, count(*) AS n
FROM email_lab_evidence GROUP BY import_status ORDER BY n DESC;
```

```sql
SELECT collected_datetime, test, result, units, uncertain, verification_status,
       import_status, source_file, source_page
FROM email_lab_evidence
WHERE lower(test) LIKE '%a1c%' OR lower(test) LIKE '%ceruloplasmin%'
ORDER BY collected_datetime;
```

## FHIR source audit

```sql
SELECT source, resource_type, count(*) AS n
FROM fhir_resources GROUP BY source, resource_type ORDER BY source, n DESC;
```

Inspect one resource without dumping the entire export:

```sql
SELECT source, resource_type, resource_id, last_updated, source_file,
       json_extract(json, '$.code.text') AS code_text
FROM fhir_resources
WHERE resource_type='Observation'
ORDER BY last_updated DESC LIMIT 25;
```

## Timeline and visits

```bash
./hp timeline --since 2025-01-01
./hp encounters --since 2025-01-01
```

```sql
SELECT date, lane, title, detail, source, provenance
FROM events WHERE date >= '2025-01-01' ORDER BY date;
```

## Records supporting a topic

```bash
./hp topic Immune
```

For a custom term set:

```sql
SELECT d.id, d.date, d.kind, d.title, d.author, d.source, d.path
FROM documents_fts f JOIN documents d ON d.id=f.rowid
WHERE documents_fts MATCH 'copper AND neuropath*'
ORDER BY d.date;
```

Open each important result with `./hp show <id> --full` before citing it. A search hit establishes that text is present; it does not establish who asserted it, whether it was current, or whether it was clinically confirmed.
