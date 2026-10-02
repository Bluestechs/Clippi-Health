#!/usr/bin/env python3
"""Tidepool diabetes device exports become daily chart rows.

Parses the user's own TidepoolExport.json files (Tidepool app -> Export Data ->
JSON: a top-level array of device datum in the Tidepool API data model) and rolls
them up to one row per day and metric in `vitals_daily`, reusing the metric names
Apple HealthKit device data already uses so the diabetes charts just work.

Standard library only. Nothing leaves this machine. The raw export remains
authoritative; these rows are a daily summary.

Mapping rules (see docs/DATA_MAPPING.md):
- Glucose (`cbg`, `smbg` incl. manual/linked) in mg/dL; mmol/L x 18.01559.
  Datum without a usable value+units pair is counted, never guessed.
- Insulin uses delivered doses only: bolus `normal` + `extended` (programmed
  `expected*` fields ignored); basal `rate` x `duration` (suspends deliver 0).
  Basal datum missing rate or duration is skipped, never zero-filled.
- Carbs come from pump wizard `carbInput` only; manual food logs are not merged.
- Day comes from local `deviceTime` when present, else UTC `time` plus the
  datum's `timezoneOffset`; undated datum is counted, never placed.
- Intraday samples (`cbg`, `smbg`, `bolus`, basal segments, wizard carbs) are
  also kept in `device_samples` at local wall-clock minute resolution, so the
  dashboard can draw a single-day overlay. Samples need a full timestamp;
  datum with only a date still counts toward daily rows.
- Datum ids dedupe across files, so overlapping 90-day exports do not double
  count (Tidepool also dedupes uploads server-side).
- Where Tidepool and Apple HealthKit cover the same day and metric, the Tidepool
  row is written last and wins; the choice is recorded in `sources.notes`.
"""
import json
import re
from datetime import datetime, timedelta

MGDL_PER_MMOLL = 18.01559
MS_PER_HOUR = 3600000.0
TIR_LOW, TIR_HIGH, TIR_MIN_READINGS = 70.0, 180.0, 12


def _num(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _glucose_mgdl(datum):
    value = _num(datum.get("value"))
    if value is None:
        return None
    units = str(datum.get("units") or "").strip().lower()
    if units in ("mg/dl", "mgdl"):
        return value
    if units in ("mmol/l", "mmoll", "mmol"):
        return value * MGDL_PER_MMOLL
    return None


def _local_moment(datum):
    """Local wall-clock moment for a datum, or None when it cannot be placed."""
    device_time = datum.get("deviceTime")
    if isinstance(device_time, str):
        match = re.match(r"(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})(?::\d{2})?", device_time.strip())
        if match:
            return datetime.strptime(match.group(1) + " " + match.group(2), "%Y-%m-%d %H:%M")
    stamp = datum.get("time")
    if not isinstance(stamp, str) or not stamp.strip():
        return None
    text = stamp.strip()
    try:
        moment = datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)
    except ValueError:
        return None
    offset = _num(datum.get("timezoneOffset"))
    if offset is not None and moment.tzinfo is not None:
        return (moment + timedelta(minutes=offset)).replace(tzinfo=None)
    if moment.tzinfo is not None:
        return moment.astimezone().replace(tzinfo=None)
    return moment


def _day(datum):
    device_time = datum.get("deviceTime")
    if isinstance(device_time, str):
        match = re.match(r"(\d{4}-\d{2}-\d{2})", device_time.strip())
        if match:
            return match.group(1)
    moment = _local_moment(datum)
    if moment is not None:
        return moment.strftime("%Y-%m-%d")
    stamp = datum.get("time")
    if isinstance(stamp, str):
        match = re.match(r"(\d{4}-\d{2}-\d{2})", stamp.strip())
        return match.group(1) if match else None
    return None


def _bolus_units(datum):
    normal = _num(datum.get("normal"))
    extended = _num(datum.get("extended"))
    if normal is None and extended is None:
        return None
    return (normal or 0.0) + (extended or 0.0)


def _basal_units(datum):
    rate = _num(datum.get("rate"))
    duration = _num(datum.get("duration"))
    if rate is None or duration is None or duration < 0:
        return None
    return rate * duration / MS_PER_HOUR


def parse_tidepool_data(items):
    """Roll datum dicts up to vitals_daily rows plus intraday overlay samples."""
    glucose = {}  # day -> [sum, n, min, max]
    in_range = {}  # day -> [in_range, n]
    basal = {}
    bolus = {}
    carbs = {}
    samples = []  # [local "YYYY-MM-DD HH:MM", kind, value, unit, detail]
    type_counts = {}
    dates = []
    seen = set()
    n_datum = 0
    for datum in items:
        if not isinstance(datum, dict):
            continue
        identity = datum.get("id") or datum.get("guid")
        key = identity if identity else json.dumps(datum, sort_keys=True, default=str)
        if key in seen:
            continue
        seen.add(key)
        n_datum += 1
        kind = datum.get("type")
        type_counts[kind if isinstance(kind, str) else "unknown"] = type_counts.get(
            kind if isinstance(kind, str) else "unknown", 0) + 1
        day = _day(datum)
        if day is None:
            continue
        moment = _local_moment(datum)
        stamp = moment.strftime("%Y-%m-%d %H:%M") if moment is not None else None
        if kind in ("cbg", "smbg"):
            value = _glucose_mgdl(datum)
            if value is None:
                continue
            cell = glucose.setdefault(day, [0.0, 0, float("inf"), float("-inf")])
            cell[0] += value
            cell[1] += 1
            cell[2] = min(cell[2], value)
            cell[3] = max(cell[3], value)
            tally = in_range.setdefault(day, [0, 0])
            tally[0] += TIR_LOW <= value <= TIR_HIGH
            tally[1] += 1
            dates.append(day)
            if stamp is not None:
                samples.append([stamp, kind, round(value, 1), "mg/dL", None])
        elif kind == "bolus":
            units = _bolus_units(datum)
            if units is None:
                continue
            bolus[day] = bolus.get(day, 0.0) + units
            dates.append(day)
            if stamp is not None:
                samples.append([stamp, "bolus", round(units, 2), "U", None])
        elif kind == "basal":
            units = _basal_units(datum)
            if units is None:
                continue
            basal[day] = basal.get(day, 0.0) + units
            dates.append(day)
            if stamp is not None:
                samples.append([stamp, "basal", _num(datum.get("rate")), "U/hr",
                                _num(datum.get("duration"))])
        elif kind == "wizard":
            grams = _num(datum.get("carbInput"))
            if grams is None:
                continue
            carbs[day] = carbs.get(day, 0.0) + grams
            dates.append(day)
            if stamp is not None:
                samples.append([stamp, "carbs", grams, "g", None])
    rows = []
    for day, (total, n, low, high) in glucose.items():
        rows.append([day, "CGM / meter glucose", round(total / n, 2), round(low, 2), round(high, 2), n, "mg/dL"])
    for day, (hits, n) in in_range.items():
        if n >= TIR_MIN_READINGS:
            rows.append([day, "Glucose time in range 70–180", round(100.0 * hits / n, 1), None, None, n, "%"])
    for day in set(basal) | set(bolus):
        rows.append([day, "Insulin", round(basal.get(day, 0.0) + bolus.get(day, 0.0), 1),
                     None, None, None, "U"])
    for day, total in basal.items():
        rows.append([day, "Insulin basal", round(total, 1), None, None, None, "U"])
    for day, total in bolus.items():
        rows.append([day, "Insulin bolus", round(total, 1), None, None, None, "U"])
    for day, total in carbs.items():
        rows.append([day, "Carbs logged", round(total, 1), None, None, None, "g"])
    samples.sort()
    return {"rows": rows, "samples": samples, "type_counts": type_counts, "n_datum": n_datum,
            "coverage": (min(dates), max(dates)) if dates else (None, None)}


def _candidate_files(root):
    other = root / "raw" / "other"
    if not other.exists():
        return []
    return sorted(path for path in other.rglob("*.json")
                  if path.is_file() and "tidepool" in path.name.lower()
                  and not any(part.startswith(".") for part in path.parts))


def _load_datum(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"  skip unreadable Tidepool file {path.name}: {exc}")
        return None
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in ("data", "results", "items", "datum"):
            items = value.get(key)
            if isinstance(items, list):
                return items
        if isinstance(value.get("type"), str):
            return [value]
    print(f"  skip {path.name}: not a Tidepool datum array")
    return None


def ingest_tidepool(db, root, hp):
    """Parse raw/other/*tidepool*.json exports into vitals_daily. Returns counts."""
    paths = _candidate_files(root)
    items = []
    loaded = []
    for path in paths:
        datum = _load_datum(path)
        if datum:
            items.extend(datum)
            loaded.append(path)
    if not loaded:
        for path in paths:
            print(f"  Tidepool {path.name}: no device datum found")
        return {}
    parsed = parse_tidepool_data(items)
    db.executemany("INSERT OR REPLACE INTO vitals_daily VALUES (?,?,?,?,?,?,?)", parsed["rows"])
    db.executemany("INSERT INTO device_samples VALUES (?,?,?,?,?,?)",
                   [(stamp[:10], stamp, kind, value, unit, detail)
                    for stamp, kind, value, unit, detail in parsed["samples"]])
    counts = dict(parsed["type_counts"])
    counts["vitals_daily rows"] = len(parsed["rows"])
    counts["device samples"] = len(parsed["samples"])
    counts["files"] = len(loaded)
    newest = max(loaded, key=lambda path: path.stat().st_mtime)
    hp.insert(
        db, "sources", key="tidepool", org="Tidepool", kind="Tidepool export",
        system="Tidepool app Export Data (JSON): direct pump/CGM export",
        method="Manual TidepoolExport.json copied to raw/other; delivered insulin only "
               "(bolus normal + extended, basal rate x duration); glucose in mg/dL.",
        path="; ".join(hp.rel(path) for path in loaded),
        exported_at=datetime.fromtimestamp(newest.stat().st_mtime).isoformat(timespec="minutes"),
        coverage_from=parsed["coverage"][0], coverage_to=parsed["coverage"][1],
        record_counts=json.dumps(counts),
        notes="Raw export remains authoritative; daily rows are a summary. Where Tidepool "
              "and Apple HealthKit cover the same day and metric, the Tidepool value is used.",
    )
    return counts
