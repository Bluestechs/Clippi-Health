"""Build Sally Seastar's entirely fictional record using the normal import pipeline.

No personal store, network, credentials or existing health records are read. A seeded
generator creates FHIR and HealthKit-shaped inputs in a dedicated, marked demo folder.
"""
import csv
import json
import math
import os
import random
import zipfile
from datetime import date, datetime, time, timedelta
from pathlib import Path
from xml.sax.saxutils import quoteattr

MARKER = ".clippi-demo.json"
IDENTITY = {"format": "clippi-health-synthetic-demo", "version": 1}


def generate(root, today=None):
    root = Path(root)
    today = today or date.today()
    # Never seed into a personal store, even if someone runs the helper manually.
    if root.is_symlink():
        raise ValueError("The demo folder must not be a symbolic link.")
    root.mkdir(parents=True, exist_ok=True)
    marker = root / MARKER
    if marker.exists():
        if json.loads(marker.read_text(encoding="utf-8")) != IDENTITY:
            raise ValueError("Unrecognized demo folder.")
    elif any(root.iterdir()):
        raise ValueError("Demo data requires an empty folder or a marked demo store.")
    else:
        with marker.open("x", encoding="utf-8") as stream:
            json.dump(IDENTITY, stream)
    # Refuse links anywhere in a reused store before writing through a linked child.
    if any(p.is_symlink() for p in root.rglob("*")):
        raise ValueError("Symbolic links are not allowed in the demo store.")
    for child in ("raw/fhir/seastar", "raw/apple", "raw/imports", "raw/other", "data"):
        (root / child).mkdir(parents=True, exist_ok=True)
    (root / "clippi-health.json").write_text(json.dumps({"format": "clippi-health-record-store", "version": 1}), encoding="utf-8")
    rng = random.Random(73109)
    days_ago = lambda days: (today - timedelta(days=days)).isoformat()
    resources = []

    def add(kind, **fields):
        resource = {"resourceType": kind, "id": f"demo-{len(resources) + 1}", **fields}
        resources.append(resource)
        return resource["id"]

    add("Patient", name=[{"given": ["Sally"], "family": "Seastar"}], birthDate="1987-06-15", gender="female")
    for name, ago in [("Type 1 diabetes mellitus", 2400), ("Seasonal allergic rhinitis", 700), ("Vitamin D deficiency", 540)]:
        add("Condition", code={"text": name}, recordedDate=days_ago(ago))
    for name, directions in [
        ("Insulin lispro (pump)", "Fictional pump therapy entry; demonstration only."),
        ("Insulin glargine (backup)", "Fictional backup plan; demonstration only."),
        ("Glucagon rescue kit", "Fictional medication list entry."),
        ("Vitamin D3", "Fictional supplement list entry."),
    ]:
        add("MedicationRequest", medicationCodeableConcept={"text": name}, authoredOn=days_ago(180),
            dosageInstruction=[{"text": directions}], requester={"display": "Dr. Coral Reed (fictional)"})
    add("AllergyIntolerance", code={"text": "Penicillin"}, recordedDate=days_ago(1500),
        reaction=[{"manifestation": [{"text": "Rash (fictional history)"}], "severity": "mild"}])
    for name, ago in [("Influenza vaccine", 90), ("COVID-19 vaccine", 120), ("Tdap", 500)]:
        add("Immunization", vaccineCode={"text": name}, occurrenceDateTime=days_ago(ago))
    for name, ago in [("Retinal screening", 65), ("Diabetes foot examination", 30)]:
        add("Procedure", code={"text": name}, performedDateTime=days_ago(ago))
    # Nine quarterly panels give every lab chart a visible trend and reference range.
    tests = [
        ("Hemoglobin A1c", "%", 7.8, 6.6, 4.0, 5.6, .12),
        ("Glucose", "mg/dL", 172, 134, 65, 99, 20),
        ("Creatinine", "mg/dL", .84, .80, .5, 1.1, .04),
        ("eGFR", "mL/min/1.73m2", 92, 98, 60, 120, 3),
        ("LDL cholesterol", "mg/dL", 119, 88, 0, 99, 6),
        ("HDL cholesterol", "mg/dL", 52, 62, 50, 100, 3),
        ("Triglycerides", "mg/dL", 149, 104, 0, 149, 13),
        ("Vitamin D, 25-OH", "ng/mL", 23, 39, 30, 100, 3),
        ("TSH", "mIU/L", 2.3, 1.9, .4, 4.5, .25),
        ("ALT", "U/L", 26, 22, 7, 35, 3),
        ("Hemoglobin", "g/dL", 13.3, 13.8, 12, 16, .25),
        ("Urine albumin/creatinine ratio", "mg/g", 18, 12, 0, 29, 3),
    ]
    for visit in range(9):
        when = days_ago((8 - visit) * 90 + 7)
        for name, unit, start, end, low, high, noise in tests:
            value = round(start + (end - start) * visit / 8 + rng.uniform(-noise, noise), 2)
            add("Observation", status="final", category=[{"text": "laboratory"}], code={"text": name},
                effectiveDateTime=when, valueQuantity={"value": value, "unit": unit},
                referenceRange=[{"low": {"value": low}, "high": {"value": high}}],
                interpretation=[{"coding": [{"code": "H" if value > high else "L" if value < low else "N"}]}],
                note=[{"text": "Synthetic result for demonstration; not a clinical measurement."}])
        visit_id = add("Encounter", status="finished", type=[{"text": "Diabetes follow-up"}], period={"start": when + "T10:00:00Z"},
            serviceProvider={"display": "Seastar Diabetes Clinic (fictional)"})
        add("DocumentReference", date=when, description="Diabetes follow-up — Sally Seastar",
            type={"text": "Progress note"}, context={"encounter": [{"reference": "Encounter/" + visit_id}]},
            author=[{"display": "Dr. Coral Reed (fictional)"}],
            text={"div": "<div><p>FICTIONAL DEMONSTRATION RECORD — Sally Seastar.</p>"
                  "<p>Reviewed synthetic CGM trends, meal-related variability and activity patterns. "
                  "Pump and sensor use discussed. Routine retinal screening and foot examination recorded.</p>"
                  "<p>This sample illustrates searchable notes and longitudinal data. It is not medical advice.</p></div>"})
    for ago, title, body in [
        (65, "Retinal screening report", "Synthetic screening report: no retinopathy recorded in this fictional example."),
        (100, "Ankle X-ray report", "Fictional minor hiking injury. No acute fracture in this demonstration report."),
        (30, "Annual wellness visit", "Fictional review of sleep, walking, vaccinations and preventive screening."),
    ]:
        add("DiagnosticReport", code={"text": title}, effectiveDateTime=days_ago(ago), conclusion=body)
    folder = root / "raw/fhir/seastar"
    (folder / "healthpilot-source.json").write_text(json.dumps({
        "key": "fhir-seastar-demo", "org": "Seastar Diabetes Clinic (fictional)",
        "exported_at": today.isoformat(), "system": "Synthetic demo generator",
        "method": "Entirely generated sample data. No connection to a health system or personal records.",
    }), encoding="utf-8")
    (folder / "records.jsonl").write_text("\n".join(json.dumps(r) for r in resources) + "\n", encoding="utf-8")

    # A year of five-minute glucose readings plus daily activity and diabetes totals.
    # The app deliberately displays daily mean/min/max and TIR, just as for real imports.
    xml = ['<?xml version="1.0" encoding="UTF-8"?><HealthData>']

    def record(kind, value, unit, start, end=None, reason=None):
        attrs = {"type": kind, "value": str(value), "unit": unit, "sourceName": "Seastar simulated device",
                 "startDate": start.strftime("%Y-%m-%d %H:%M:%S +0000"),
                 "endDate": (end or start).strftime("%Y-%m-%d %H:%M:%S +0000")}
        metadata = f'<MetadataEntry key="HKInsulinDeliveryReason" value="{reason}"/>' if reason else ""
        xml.append("<Record " + " ".join(k + "=" + quoteattr(v) for k, v in attrs.items()) + ">" + metadata + "</Record>")

    for day in range(365):
        stamp = datetime.combine(today - timedelta(days=365 - day), time())
        baseline = 130 + 15 * math.sin(day / 19) + rng.uniform(-16, 16) - day / 60
        drift = 0
        for sample in range(288):
            hour = sample / 12
            meals = sum(height * math.exp(-((hour - peak) / .85) ** 2) for peak, height in [(8.5, 56), (13.5, 64), (19.5, 72)])
            activity = 53 * math.exp(-((hour - 16.5) / 1.0) ** 2) if day % 5 == 0 else 0
            drift = .85 * drift + rng.uniform(-6, 6)
            glucose = max(52, min(295, baseline + meals - activity + drift + 10 * math.sin(hour * 1.5)))
            record("HKQuantityTypeIdentifierBloodGlucose", round(glucose), "mg/dL", stamp + timedelta(minutes=sample * 5))
        for kind, unit, value in [
            ("BodyMass", "lb", 153 - day / 120 + rng.uniform(-1.8, 1.8)),
            ("BloodPressureSystolic", "mmHg", 116 + rng.uniform(-9, 9)),
            ("BloodPressureDiastolic", "mmHg", 74 + rng.uniform(-6, 6)),
            ("RestingHeartRate", "bpm", 63 + rng.uniform(-7, 7)),
            ("HeartRateVariabilitySDNN", "ms", 44 + rng.uniform(-12, 12)),
            ("OxygenSaturation", "%", 98 + rng.uniform(-1, 1)),
            ("StepCount", "count", rng.randint(3500, 12500)),
            ("DietaryCarbohydrates", "g", 155 + rng.uniform(-40, 50)),
        ]:
            record("HKQuantityTypeIdentifier" + kind, round(value, 1), unit, stamp + timedelta(hours=12))
        record("HKQuantityTypeIdentifierInsulinDelivery", round(18 + rng.uniform(-3, 3), 1), "IU", stamp, reason="1")
        for hour in (8, 13, 19):
            record("HKQuantityTypeIdentifierInsulinDelivery", round(rng.uniform(3, 7), 1), "IU",
                   stamp + timedelta(hours=hour), reason="2")
        wake = stamp + timedelta(hours=7)
        record("HKCategoryTypeIdentifierSleepAnalysis", "HKCategoryValueSleepAnalysisAsleepCore", "",
               wake - timedelta(hours=rng.uniform(6.2, 8.7)), wake)
    xml.append("</HealthData>")
    with zipfile.ZipFile(root / "raw/apple/seastar-simulated-health.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("apple_health_export/export.xml", "\n".join(xml))
    # Two weeks of pump/CGM datum in Tidepool export shape, exercising the same
    # pipeline as a real TidepoolExport.json: daily rows, intraday overlay, basics.
    # Exactly 288 CGM readings per day keeps full-day coverage assertions exact;
    # two fingersticks a day ride along as smbg.
    tidepool = []
    for ago in range(14, 0, -1):
        day = (today - timedelta(days=ago)).isoformat()
        baseline = 132 + 12 * math.sin(ago / 3) + rng.uniform(-10, 10)
        for sample in range(288):
            minutes = sample * 5
            hour = minutes / 60
            meals = sum(height * math.exp(-((hour - peak) / .9) ** 2)
                      for peak, height in [(8.5, 52), (13.5, 60), (19.5, 66)])
            glucose = max(58, min(290, baseline + meals + rng.uniform(-9, 9) + 8 * math.sin(hour * 1.6)))
            hh, mm = divmod(minutes, 60)
            tidepool.append({"type": "cbg", "id": f"demo-tidepool-cbg-{ago}-{sample}",
                             "value": round(glucose), "units": "mg/dL",
                             "deviceTime": f"{day}T{hh:02d}:{mm:02d}:00",
                             "time": f"{day}T{hh:02d}:{mm:02d}:00.000Z", "deviceId": "demo-cgm"})
        for hour in range(24):
            tidepool.append({"type": "basal", "id": f"demo-tidepool-basal-{ago}-{hour}",
                             "deliveryType": "scheduled", "rate": 0.8, "duration": 3600000,
                             "deviceTime": f"{day}T{hour:02d}:00:00",
                             "time": f"{day}T{hour:02d}:00:00.000Z", "deviceId": "demo-pump"})
        for meal_hour, grams in ((8, 45), (13, 60), (19, 70)):
            units = round(grams / 12 + rng.uniform(-0.5, 1.0), 1)
            tidepool.append({"type": "bolus", "id": f"demo-tidepool-bolus-{ago}-{meal_hour}",
                             "subType": "normal", "normal": units,
                             "deviceTime": f"{day}T{meal_hour:02d}:10:00",
                             "time": f"{day}T{meal_hour:02d}:10:00.000Z", "deviceId": "demo-pump"})
            tidepool.append({"type": "wizard", "id": f"demo-tidepool-wizard-{ago}-{meal_hour}",
                             "carbInput": grams, "bolus": units,
                             "deviceTime": f"{day}T{meal_hour:02d}:05:00",
                             "time": f"{day}T{meal_hour:02d}:05:00.000Z", "deviceId": "demo-pump"})
        for finger_hour, finger_minute in ((7, 30), (22, 15)):
            tidepool.append({"type": "smbg", "id": f"demo-tidepool-smbg-{ago}-{finger_hour}",
                             "value": round(max(58, min(290, baseline + rng.uniform(-12, 12)))),
                             "units": "mg/dL", "subType": "manual",
                             "deviceTime": f"{day}T{finger_hour:02d}:{finger_minute:02d}:00",
                             "time": f"{day}T{finger_hour:02d}:{finger_minute:02d}:00.000Z",
                             "deviceId": "demo-meter"})
    for maker in ("DemoCGM", "DemoPump"):
        tidepool.append({"type": "upload", "id": f"demo-tidepool-upload-{maker}",
                         "deviceManufacturers": [maker], "time": f"{today.isoformat()}T12:00:00.000Z"})
    (root / "raw/other/TidepoolExport.json").write_text(json.dumps(tidepool), encoding="utf-8")
    (root / "topics.json").write_text(json.dumps({"Diabetes": {
        "keywords": ["diabetes", "CGM", "insulin", "retinal"],
        "tests": ["A1c", "glucose", "creatinine", "albumin"],
        "status": "Fictional demo", "framing": "Sally's synthetic diabetes history; no real patient records.",
    }}), encoding="utf-8")
    with (root / "curated_events.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["date", "lane", "title", "detail", "org", "docs", "replaces"])
        writer.writeheader()
        for ago, lane, title in [(360, "Milestones", "Started a new CGM"), (270, "Treatments", "Pump education visit"),
                                 (150, "Milestones", "Started lunchtime walks"), (65, "Imaging", "Annual retinal screening"),
                                 (30, "Milestones", "Reviewed a year of CGM trends")]:
            writer.writerow({"date": days_ago(ago), "lane": lane, "title": title,
                             "detail": "Fictional event for Sally Seastar's demonstration record.", "org": "Demo"})
    (root / "case_study_notes.md").write_text(
        "# Sally Seastar — fictional demo\n\nAll values, dates, names and records are synthetic.\n\n"
        "## Things to explore\n\n- Compare A1c and glucose trends in Labs.\n"
        "- Open Vitals; drag across a chart to zoom, then double-click to reset.\n"
        "- Compare insulin, carbohydrates, steps and sleep.\n"
        "- Search Records for diabetes and open a visit note.\n\n"
        "Keep demo edits fictional. Starting a new demo session resets these sample notes and events.\n", encoding="utf-8")
    (root / "journal.md").write_text(
        f"# Fictional journal\n\n## {days_ago(14)} — Walking after lunch\nlane: Milestones\ntags: Diabetes\n"
        "Sally's fictional observation: a walk after lunch coincided with a gentler CGM rise.\n\n"
        f"## {days_ago(3)} — Reviewing the sensor charts\nlane: Milestones\ntags: Diabetes\n"
        "Synthetic journal entry: tried the 30-day chart view and compared sleep with glucose variability.\n", encoding="utf-8")


def main():
    target = os.environ.get("CLIPPI_HEALTH_ROOT")
    if not target:
        raise ValueError("CLIPPI_HEALTH_ROOT must point to a dedicated demo folder.")
    generate(Path(target))
    import healthpilot
    healthpilot.main()
    print("Sally Seastar's fictional demo is ready.")
    return 0


if __name__ == "__main__":
    main()
