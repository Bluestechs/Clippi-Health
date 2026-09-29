"""Import standards-based FHIR NDJSON without depending on a connector service.

Every resource is retained verbatim in ``fhir_resources``; common clinical resources
are also projected into the existing Clippi-Health tables.  The raw local export remains
the source of truth.
"""
import base64
import json
import mimetypes
import re
from collections import Counter
from datetime import datetime
from pathlib import Path


SCHEMA = """
CREATE TABLE fhir_resources(
  id INTEGER PRIMARY KEY, source TEXT, org TEXT, resource_key TEXT,
  resource_type TEXT, resource_id TEXT, last_updated TEXT,
  source_file TEXT, json TEXT,
  UNIQUE(source, resource_key));
CREATE INDEX fhir_resources_type ON fhir_resources(source, resource_type);
"""


def text_of(code):
    """Best human label from a FHIR CodeableConcept or coding list."""
    if isinstance(code, list):
        for item in code:
            if (value := text_of(item)):
                return value
        return None
    if not isinstance(code, dict):
        return str(code) if code else None
    if code.get("text"):
        return code["text"]
    for coding in code.get("coding") or []:
        if coding.get("display") or coding.get("code"):
            return coding.get("display") or coding.get("code")
    return code.get("display")


def date_of(resource, hp, *names):
    for name in names:
        value = resource.get(name)
        if isinstance(value, dict):
            value = value.get("start") or value.get("end")
        date = hp.parse_when(value)[0]
        if date:
            return date
    return None


def reference_name(value):
    if isinstance(value, list):
        return ", ".join(filter(None, (reference_name(v) for v in value))) or None
    if not isinstance(value, dict):
        return None
    return value.get("display") or value.get("reference")


def is_laboratory(observation):
    categories = observation.get("category") or []
    if isinstance(categories, dict):
        categories = [categories]
    codes = []
    for category in categories:
        codes.extend((c.get("code") or "").lower() for c in category.get("coding") or [])
        codes.append((category.get("text") or "").lower())
    return any(code in {"laboratory", "lab"} or "laborator" in code for code in codes)


def iter_resources(path):
    """Yield top-level resources and Bundle entries with stable line-based keys."""
    with path.open(encoding="utf-8-sig") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid FHIR JSON at {path}:{line_number}: {exc.msg}") from exc
            resources = [entry.get("resource") for entry in value.get("entry") or []] \
                if value.get("resourceType") == "Bundle" else [value]
            for index, resource in enumerate(resources):
                if not isinstance(resource, dict) or not resource.get("resourceType"):
                    continue
                suffix = f":{index}" if len(resources) > 1 else ""
                yield f"{path.name}:{line_number}{suffix}", resource


def patient_summary(resource):
    names = resource.get("name") or []
    name = names[0] if names else {}
    given = name.get("given") or []
    return {
        "firstName": given[0] if given else None,
        "lastName": name.get("family"),
        "birthDate": resource.get("birthDate"),
        "gender": resource.get("gender"),
    }


def resource_text(resource, hp):
    parts = []
    narrative = (resource.get("text") or {}).get("div")
    if narrative:
        parts.append(hp.html_to_text(narrative))
    for field in ("description", "conclusion", "clinicalStatus", "verificationStatus"):
        value = resource.get(field)
        if isinstance(value, dict):
            value = text_of(value)
        if value:
            parts.append(str(value))
    for note in resource.get("note") or []:
        if isinstance(note, dict) and note.get("text"):
            parts.append(note["text"])
    return "\n\n".join(dict.fromkeys(p for p in parts if p))


def binary_content(resource, hp, source, binary_by_id):
    """Return (text, generated path, format) for a DocumentReference attachment."""
    chunks, output, fmt = [], None, None
    for number, item in enumerate(resource.get("content") or [], 1):
        attachment = item.get("attachment") or {}
        binary = None
        url = attachment.get("url") or ""
        if url.startswith("Binary/"):
            binary = binary_by_id.get(url.split("/", 1)[1])
        data = attachment.get("data") or (binary or {}).get("data")
        content_type = attachment.get("contentType") or (binary or {}).get("contentType") or ""
        if not data:
            if url:
                chunks.append(f"Attachment reference retained in FHIR JSON: {url}")
            continue
        try:
            raw = base64.b64decode(data, validate=True)
        except (ValueError, TypeError):
            chunks.append("Attachment data was not valid base64; see the raw FHIR resource.")
            continue
        if len(raw) > 100 * 1024 * 1024:
            chunks.append("Attachment exceeds the 100 MB materialization limit; see the raw FHIR resource.")
            continue
        ext = mimetypes.guess_extension(content_type.split(";", 1)[0]) or ".bin"
        rid = re.sub(r"[^A-Za-z0-9._-]", "_", resource.get("id") or "document")
        dest = hp.DATA / "fhir_files" / source / f"{rid}-{number}{ext}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
        output, fmt = dest, ext.lstrip(".")
        if content_type.startswith("text/") or content_type in {"application/xml", "application/fhir+json", "application/json"}:
            decoded = raw.decode("utf-8", errors="replace")
            chunks.append(hp.html_to_text(decoded) if "html" in content_type or "xml" in content_type else decoded)
        elif content_type == "application/pdf":
            chunks.append(hp.pdf_text(dest) or "[PDF materialized; no text extractor was available.]")
        else:
            chunks.append(f"[{content_type or 'binary'} attachment materialized for local viewing.]")
    return "\n\n".join(chunks), (hp.rel(output) if output else None), fmt


def materialize(db, source, org, source_file, resources, hp):
    counts = Counter()
    binary_by_id = {r.get("id"): r for r in resources if r.get("resourceType") == "Binary" and r.get("id")}
    seen = set()
    for resource in resources:
        kind, rid = resource.get("resourceType"), resource.get("id")
        identity = (kind, rid) if rid else None
        if identity and identity in seen:
            continue
        if identity:
            seen.add(identity)
        provenance = f"FHIR bulk export — {kind} resource"
        if kind == "Patient" and not db.execute("SELECT 1 FROM meta WHERE key='patient'").fetchone():
            db.execute("INSERT INTO meta VALUES ('patient', ?)", [json.dumps(patient_summary(resource))])
        elif kind == "Observation" and is_laboratory(resource):
            hp.ingest_fhir_observation(db, resource, source, org, None, source_file, provenance)
            counts["labs"] += 1
        elif kind == "DiagnosticReport":
            order = text_of(resource.get("code"))
            for observation in resource.get("contained") or []:
                if observation.get("resourceType") == "Observation":
                    hp.ingest_fhir_observation(db, observation, source, org, order, source_file,
                                               provenance + " (contained Observation)")
                    counts["labs"] += 1
            text = resource_text(resource, hp)
            if text:
                hp.insert(db, "documents", source=source, org=org, kind="report",
                          date=date_of(resource, hp, "effectiveDateTime", "effectivePeriod", "issued"),
                          title=order or "Diagnostic report", text=text, path=source_file, format="fhir+ndjson",
                          source_id=rid, provenance=provenance)
                counts["reports"] += 1
        elif kind == "Condition":
            name = text_of(resource.get("code"))
            if name:
                hp.insert(db, "conditions", source=source, org=org, name=name,
                          noted=date_of(resource, hp, "recordedDate", "onsetDateTime", "onsetPeriod"), kind="fhir")
                counts["conditions"] += 1
        elif kind == "Procedure":
            name = text_of(resource.get("code"))
            if name:
                hp.insert(db, "procedures", source=source, org=org, name=name,
                          date=date_of(resource, hp, "performedDateTime", "performedPeriod"), kind="fhir")
                counts["procedures"] += 1
        elif kind in {"MedicationRequest", "MedicationStatement"}:
            name = text_of(resource.get("medicationCodeableConcept")) or reference_name(resource.get("medicationReference"))
            directions = "; ".join(filter(None, (d.get("text") for d in resource.get("dosageInstruction") or [])))
            if name:
                hp.insert(db, "medications", source=source, org=org, name=name, sig=directions or None,
                          date=date_of(resource, hp, "authoredOn", "effectiveDateTime", "effectivePeriod"),
                          provider=reference_name(resource.get("requester")))
                counts["medications"] += 1
        elif kind == "Immunization":
            name = text_of(resource.get("vaccineCode"))
            if name:
                hp.insert(db, "immunizations", source=source, org=org, name=name,
                          date=date_of(resource, hp, "occurrenceDateTime", "date"))
                counts["immunizations"] += 1
        elif kind == "AllergyIntolerance":
            name = text_of(resource.get("code"))
            reactions = "; ".join(filter(None, (text_of(r.get("manifestation")) for r in resource.get("reaction") or [])))
            severe = ", ".join(filter(None, (r.get("severity") for r in resource.get("reaction") or [])))
            if name:
                hp.insert(db, "allergies", source=source, org=org, name=name, reactions=reactions or None,
                          severe=severe or None, noted=date_of(resource, hp, "recordedDate", "onsetDateTime"))
                counts["allergies"] += 1
        elif kind == "Encounter":
            period = resource.get("period") or {}
            types = text_of(resource.get("type")) or text_of(resource.get("serviceType"))
            class_name = text_of(resource.get("class"))
            hp.insert(db, "encounters", source=source, org=org,
                      date=hp.parse_when(period.get("start"))[0], datetime=hp.parse_when(period.get("start"))[1],
                      type=types or class_name or "Encounter", provider=None,
                      dept=reference_name(resource.get("serviceProvider")), source_file=source_file, source_id=rid)
            counts["encounters"] += 1
        elif kind == "DocumentReference":
            text = resource_text(resource, hp)
            attachment_text, generated, fmt = binary_content(resource, hp, source, binary_by_id)
            hp.insert(db, "documents", source=source, org=org, kind="document",
                      date=date_of(resource, hp, "date", "content"),
                      title=resource.get("description") or text_of(resource.get("type")) or "Clinical document",
                      author=reference_name(resource.get("author")), text="\n\n".join(filter(None, [text, attachment_text])),
                      path=generated or source_file, format=fmt or "fhir+ndjson", source_id=rid, provenance=provenance)
            counts["documents"] += 1
        elif kind == "Composition":
            text = resource_text(resource, hp)
            if text:
                hp.insert(db, "documents", source=source, org=org, kind="document",
                          date=date_of(resource, hp, "date"), title=resource.get("title") or "Clinical composition",
                          author=reference_name(resource.get("author")), text=text, path=source_file,
                          format="fhir+ndjson", source_id=rid, provenance=provenance)
                counts["documents"] += 1
    return counts


def ingest_exports(db, root, hp):
    totals = {}
    base = root / "raw" / "fhir"
    for config_path in sorted(base.glob("*/healthpilot-source.json")):
        folder = config_path.parent
        config = json.loads(config_path.read_text())
        source, org = config["key"], config["org"]
        if not re.fullmatch(r"fhir-[a-z0-9_-]+", source):
            raise ValueError(f"FHIR source key must match fhir-[a-z0-9_-]+: {source}")
        paths = sorted(list(folder.glob("*.jsonl")) + list(folder.glob("*.ndjson")))
        if not paths:
            raise ValueError(f"No .jsonl or .ndjson FHIR export in {folder}")
        resources = []
        raw_counts = Counter()
        for path in paths:
            source_file = hp.rel(path)
            for resource_key, resource in iter_resources(path):
                kind = resource["resourceType"]
                hp.insert(db, "fhir_resources", source=source, org=org, resource_key=resource_key,
                          resource_type=kind, resource_id=resource.get("id"),
                          last_updated=(resource.get("meta") or {}).get("lastUpdated"), source_file=source_file,
                          json=json.dumps(resource, separators=(",", ":"), ensure_ascii=False))
                resources.append(resource)
                raw_counts[kind] += 1
        counts = materialize(db, source, org, hp.rel(folder), resources, hp)
        counts["fhir_resources"] = sum(raw_counts.values())
        counts["resource_types"] = dict(sorted(raw_counts.items()))
        dates = db.execute("""SELECT min(d), max(d) FROM (
            SELECT date d FROM labs WHERE source=? UNION ALL SELECT date FROM documents WHERE source=?
            UNION ALL SELECT date FROM encounters WHERE source=? UNION ALL SELECT noted FROM conditions WHERE source=?
            UNION ALL SELECT date FROM procedures WHERE source=? UNION ALL SELECT date FROM immunizations WHERE source=?)""",
            [source] * 6).fetchone()
        exported = config.get("exported_at") or datetime.fromtimestamp(max(p.stat().st_mtime for p in paths)).isoformat(timespec="minutes")
        system = config.get("system") or "FHIR NDJSON"
        method = config.get("method") or "FHIR NDJSON supplied directly by the user."
        hp.insert(db, "sources", key=source, org=org, kind="FHIR record export", system=system,
                  method=method + " All FHIR resources are retained verbatim; common clinical resources are projected into query tables.",
                  path=hp.rel(folder), exported_at=exported, coverage_from=dates[0], coverage_to=dates[1],
                  record_counts=json.dumps(counts), gaps=json.dumps({"summary": "Coverage is limited to resources returned by the connected portal."}),
                  notes="FHIR resource JSON remains authoritative in fhir_resources and the raw JSONL export. "
                        "Unsupported resource types remain queryable there even when not projected into a specialized table.")
        totals[source] = counts
    return totals
