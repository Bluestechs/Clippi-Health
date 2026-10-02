#!/usr/bin/env python3
"""Clippi-Health — build a local SQLite database and a static dashboard from exported health records.

    python3 healthpilot.py            rebuild data/health.db and dashboard.html

Inputs (all under raw/, never modified):
  raw/fhir/<source>/        direct SMART/FHIR or user-supplied NDJSON plus source metadata
  raw/**/IHE_XDM/**/*.XML   standards-based C-CDA record downloads
  raw/apple/*.zip           Apple Health "Export All Health Data" (clinical labs + device data)
  raw/other/TidepoolExport*.json  Tidepool Export Data (JSON) → vitals_daily daily rows
  raw/imports/*.zip         user-selected local email/document exports (MBOX, EML, documents)
  raw/other/, raw/quest-pdfs/   any extra PDF/HTML/TXT files to index for search
  curated_events.csv        hand-maintained timeline events (optional)

Standard library only. Nothing leaves this machine.
"""
import csv
import base64
import hashlib
import html
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("CLIPPI_HEALTH_ROOT", SOURCE_ROOT)).expanduser().resolve()
RESOURCES = Path(os.environ.get("CLIPPI_HEALTH_RESOURCES", SOURCE_ROOT)).expanduser().resolve()
RAW = ROOT / "raw"
DATA = ROOT / "data"
DB_PATH = DATA / "health.db"
DASHBOARD = ROOT / "dashboard.html"
TEMPLATE = RESOURCES / "scripts" / "dashboard_template.html"
PLOTLY = RESOURCES / "vendor" / "plotly-basic.min.js"
LOGO = RESOURCES / "assets" / "icons" / "clippi-health.png"
PDFTEXT = RESOURCES / "scripts" / "pdftext.swift"
CURATED = ROOT / "curated_events.csv"

LANES = ["Diagnoses", "Symptoms", "Treatments", "Surgery & procedures", "Hospital & ED", "Imaging", "Pathology & reports", "Milestones"]

# ---------------------------------------------------------------------------
# Text and date helpers
# ---------------------------------------------------------------------------

def html_to_text(s):
    if not s:
        return ""
    s = re.sub(r"(?is)<(style|script|head|title)[^>]*>.*?</\1>", " ", s)
    s = re.sub(r"(?i)<br\s*/?>", "\n", s)
    s = re.sub(r"(?i)</(p|div|tr|li|h\d|table|section|ul|ol|paragraph|item|caption)>", "\n", s)
    s = re.sub(r"(?i)</t[dh]>", "  ", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s).replace("\xa0", " ").replace("\r", "")
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in s.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


DATE_FORMATS = [
    "%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y %I:%M %p", "%m/%d/%Y", "%b %d, %Y %I:%M %p",
    "%b %d, %Y", "%B %d, %Y", "%d-%b-%Y", "%Y%m%d%H%M%S", "%Y%m%d%H%M", "%Y%m%d",
]


def parse_when(s):
    """Return (YYYY-MM-DD, 'YYYY-MM-DD HH:MM' or None) from the many date shapes in the sources."""
    if not s:
        return None, None
    s = str(s).strip()
    m = re.match(r"(\d{4}-\d{2}-\d{2})(?:[T ](\d{2}:\d{2}))?", s)
    if m:
        if s.endswith("Z") and m.group(2):  # UTC instant -> local wall time
            dt = datetime.fromisoformat(s[:19] + "+00:00").astimezone()
            return dt.strftime("%Y-%m-%d"), dt.strftime("%Y-%m-%d %H:%M")
        return m.group(1), (f"{m.group(1)} {m.group(2)}" if m.group(2) else None)
    s = re.sub(r"[+-]\d{4}$", "", s).strip()  # C-CDA timezone suffix
    for fmt in DATE_FORMATS:
        try:
            dt = datetime.strptime(s, fmt)
        except ValueError:
            continue
        has_time = "%H" in fmt or "%I" in fmt
        return dt.strftime("%Y-%m-%d"), (dt.strftime("%Y-%m-%d %H:%M") if has_time else None)
    return None, None


def parse_value(text, numeric=None):
    """(value_num, comparator) from a lab value like '8.8', '<0.5', '>60'."""
    if isinstance(numeric, (int, float)):
        return float(numeric), None
    m = re.match(r"^\s*([<>]=?)?\s*(-?\d+(?:\.\d+)?)\s*$", str(text or ""))
    if not m:
        return None, None
    return float(m.group(2)), m.group(1)


def norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9%]+", " ", str(s or "").upper())).strip()

# ---------------------------------------------------------------------------
# Lab test names: map each source's spelling to one canonical test
# ---------------------------------------------------------------------------

# canonical name -> (group, canonical unit or None, [spellings seen across portal and laboratory sources])
LAB_TESTS = {
    "WBC": ("Blood counts", "K/uL", ["WBC", "WHITE BLOOD CELL COUNT", "LEUKOCYTES"]),
    "RBC": ("Blood counts", "M/uL", ["RBC", "RBC POC", "RED BLOOD CELL COUNT"]),
    "Hemoglobin": ("Blood counts", "g/dL", ["HGB", "HEMOGLOBIN"]),
    "Hematocrit": ("Blood counts", "%", ["HCT", "HEMATOCRIT"]),
    "Platelets": ("Blood counts", "K/uL", ["PLT", "PLATELETS", "PLATELET COUNT"]),
    "MCV": ("Blood counts", "fL", ["MCV"]),
    "MCH": ("Blood counts", "pg", ["MCH"]),
    "MCHC": ("Blood counts", "g/dL", ["MCHC"]),
    "MPV": ("Blood counts", "fL", ["MPV"]),
    "RDW": ("Blood counts", "%", ["RDW", "RDW CV"]),
    "RDW-SD": ("Blood counts", "fL", ["RDW SD", "RDWSD"]),
    "Neutrophils (abs)": ("Blood counts", "K/uL", ["NEUTROPHIL ABS", "NEUTROPHILS ABS", "NEUTROS ABS", "NEUTROS ABS AUTO", "NEUTROS ABS CELLS UL", "ABSOLUTE NEUTROPHILS"]),
    "Lymphocytes (abs)": ("Blood counts", "K/uL", ["LYMPHOCYTE ABS", "LYMPHOCYTES ABS", "LYMPHS ABS", "LYMPHS ABS AUTO", "ABSOLUTE LYMPHOCYTES"]),
    "Monocytes (abs)": ("Blood counts", "K/uL", ["MONOCYTE ABS", "MONOCYTES ABS", "MONOCYTE ABS AUTO", "ABSOLUTE MONOCYTES"]),
    "Eosinophils (abs)": ("Blood counts", "K/uL", ["EOSINOPHIL ABS", "EOSINOPHILS ABS", "EOS ABS", "EOS ABS AUTO", "ABSOLUTE EOSINOPHILS"]),
    "Basophils (abs)": ("Blood counts", "K/uL", ["BASOPHIL ABS", "BASOPHILS ABS", "BASOS ABS", "BASOS ABS AUTO", "ABSOLUTE BASOPHILS"]),
    "Neutrophils (%)": ("Blood counts", "%", ["NEUTROPHIL PCT", "NEUTROS PCT", "NEUTROS PCT AUTO"]),
    "Lymphocytes (%)": ("Blood counts", "%", ["LYMPHOCYTE PCT", "LYMPHS PCT", "LYMPHS PCT AUTO"]),
    "Monocytes (%)": ("Blood counts", "%", ["MONOCYTE PCT", "MONOS PCT", "MONOS PCT AUTO"]),
    "Eosinophils (%)": ("Blood counts", "%", ["EOSINOPHIL PCT", "EOS PCT", "EOS PCT AUTO"]),
    "Basophils (%)": ("Blood counts", "%", ["BASOPHIL PCT", "BASOS", "BASOS PCT AUTO"]),
    "Immature granulocytes (abs)": ("Blood counts", "K/uL", ["IMM GRAN ABS", "IMMATURE GRAN ABS"]),
    "Immature granulocytes (%)": ("Blood counts", "%", ["IMM GRAN PCT", "IMMATURE GRAN PERCENT"]),
    "NRBC (abs)": ("Blood counts", "K/uL", ["NRBC ABS"]),
    "Sodium": ("Metabolic", "mmol/L", ["SODIUM"]),
    "Potassium": ("Metabolic", "mmol/L", ["POTASSIUM", "POTASSIUM PL", "POTASSIUM PLASMA"]),
    "Chloride": ("Metabolic", "mmol/L", ["CHLORIDE"]),
    "CO2": ("Metabolic", "mmol/L", ["CO2", "CARBON DIOXIDE", "BICARBONATE"]),
    "BUN": ("Metabolic", "mg/dL", ["BUN", "BUN SERUM", "UREA NITROGEN BUN", "UREA NITROGEN"]),
    "Creatinine": ("Metabolic", "mg/dL", ["CREATININE", "CREATININE POC", "CREATININE POC BLD"]),
    "BUN/Creatinine ratio": ("Metabolic", None, ["BUN CREATININE RATIO", "BUN CREAT RATIO"]),
    "eGFR": ("Metabolic", "mL/min/1.73m2", ["EGFR", "GFR NON AFRICAN AMERICAN", "EGFR NON AFR AMERICAN"]),
    "eGFR (cystatin C)": ("Metabolic", "mL/min/1.73m2", ["EGFR BY CYSTATIN C", "EGFR CYSTATIN C"]),
    "Calcium": ("Metabolic", "mg/dL", ["CALCIUM"]),
    "Anion gap": ("Metabolic", "mmol/L", ["ANION GAP", "ANIONGAP"]),
    "Glucose": ("Diabetes", "mg/dL", ["GLUCOSE"]),
    "Glucose (point of care)": ("Diabetes", "mg/dL", ["GLUCOSE BLOOD POC", "POC GLUCOSE", "GLUCOSE POC", "POC GLUCOSE MONITOR"]),
    "Hemoglobin A1c": ("Diabetes", "%", ["HEMOGLOBIN A1C", "HEMOGLOBIN A1C POC", "HBA1C", "A1C"]),
    "Albumin": ("Liver", "g/dL", ["ALBUMIN"]),
    "Total protein": ("Liver", "g/dL", ["PROTEIN PL", "PROTEIN TOTAL", "TOTAL PROTEIN"]),
    "Globulin": ("Liver", "g/dL", ["GLOBULIN", "GLOBULIN TOTAL"]),
    "Albumin/globulin ratio": ("Liver", None, ["ALBUMIN GLOBULIN RATIO", "A G RATIO"]),
    "ALT": ("Liver", "U/L", ["ALT", "ALT SGPT"]),
    "AST": ("Liver", "U/L", ["AST", "AST SGOT"]),
    "Alkaline phosphatase": ("Liver", "U/L", ["ALK PHOS", "ALKALINE PHOSPHATASE"]),
    "Bilirubin, total": ("Liver", "mg/dL", ["BILIRUBIN TOTAL"]),
    "Cholesterol, total": ("Lipids", "mg/dL", ["CHOLESTEROL TOTAL", "CHOLESTEROL"]),
    "LDL cholesterol": ("Lipids", "mg/dL", ["LDL CHOLESTEROL", "LDL"]),
    "HDL cholesterol": ("Lipids", "mg/dL", ["HDL CHOLESTEROL", "HDL"]),
    "Non-HDL cholesterol": ("Lipids", "mg/dL", ["NON HDL CHOLESTEROL"]),
    "Cholesterol/HDL ratio": ("Lipids", None, ["CHOL HDLC RATIO"]),
    "Triglycerides": ("Lipids", "mg/dL", ["TRIGLYCERIDES"]),
    "TSH": ("Thyroid & hormones", "mIU/L", ["TSH"]),
    "Free T4": ("Thyroid & hormones", "ng/dL", ["FREE T4", "T4 FREE", "THYROXIN T4 FREE"]),
    "Free T3": ("Thyroid & hormones", "pg/mL", ["FREE T3", "T3 FREE"]),
    "IgG": ("Immunology", "mg/dL", ["IMMUNOGLOBULIN G", "IGG"]),
    "IgA": ("Immunology", "mg/dL", ["IMMUNOGLOBULIN A", "IGA"]),
    "IgM": ("Immunology", "mg/dL", ["IMMUNOGLOBULIN M", "IMMUNOGLUBLIN M", "IGM"]),
    "Calprotectin (fecal)": ("GI & pancreas", "mcg/g", ["CALPROTECTIN FECAL", "CALPROTECTIN STOOL"]),
    "Pancreatic elastase": ("GI & pancreas", "mcg/g", ["PANCREATIC ELASTASE 1", "PANCREATIC ELASTASE 1 MCG G"]),
    "Vitamin D, 25-OH": ("Vitamins & minerals", "ng/mL", ["VITAMIN D 25 OH", "25 HYDROXYD TOTAL", "VITAMIN D 25 HYDROXY TOTAL", "VITAMIN D 25 OH TOTAL IA"]),
    "Vitamin B12": ("Vitamins & minerals", "pg/mL", ["VITAMIN B12"]),
    "Folate": ("Vitamins & minerals", "ng/mL", ["FOLIC ACID", "FOLATE"]),
    "eGFR (African American formula)": ("Metabolic", "mL/min/1.73m2", ["EGFR AFRICAN AMERICAN"]),
    "T4, total": ("Thyroid & hormones", "mcg/dL", ["T4 THYROXINE TOTAL", "T4 TOTAL"]),
    "PSA, total": ("Thyroid & hormones", "ng/mL", ["PSA TOTAL", "PSA"]),
    "ESR": ("Inflammation", "mm/h", ["SED RATE BY MODIFIED WESTERGREN", "SED RATE", "ESR"]),
    "CRP": ("Inflammation", "mg/L", ["C REACTIVE PROTEIN", "CRP"]),
    "hs-CRP": ("Inflammation", "mg/L", ["HS CRP", "C REACTIVE PROTEIN CARDIAC"]),
    "Apolipoprotein B": ("Lipids", "mg/dL", ["APOLIPOPROTEIN B"]),
    "Lipoprotein(a)": ("Lipids", None, ["LIPOPROTEIN A"]),
    "Lipase": ("GI & pancreas", "U/L", ["LIPASE"]),
    "Amylase": ("GI & pancreas", "U/L", ["AMYLASE"]),
    "tTG IgA": ("GI & pancreas", None, ["TISSUE TRANSGLUTAMINASE AB IGA", "TTG ANTIBODY IGA", "TTG IGA AB"]),
    "tTG IgG": ("GI & pancreas", None, ["TTG ANTIBODY IGG", "TTG IGG AB"]),
    "ANA": ("Immunology", None, ["ANA SCREEN IFA", "ANA SCREEN", "ANA DIRECT"]),
    "IgE": ("Immunology", "IU/mL", ["IMMUNOGLOBULIN E", "IGE"]),
    "Gamma globulin": ("Immunology", "g/dL", ["GAMMA GLOBULIN"]),
    "Kappa light chain": ("Immunology", None, ["KAPPA"]),
    "Lambda light chain": ("Immunology", None, ["LAMBDA"]),
    "Kappa free light chain": ("Immunology", "mg/L", ["KAPPA FREE LIGHT CHAIN", "KAPPA FREE"]),
    "Lambda free light chain": ("Immunology", "mg/L", ["LAMBDA FREE LIGHT CHAIN", "LAMBDA FREE"]),
    "Kappa/lambda ratio": ("Immunology", None, ["KAPPA LAMBDA RATIO"]),
    "Kappa/lambda free ratio": ("Immunology", None, ["KAPPA LAMBDA FREE RATIO"]),
    "Ceruloplasmin": ("Vitamins & minerals", "mg/dL", ["CERULOPLASMIN"]),
    "Methylmalonic acid": ("Vitamins & minerals", None, ["METHYLMALONIC ACID", "METHYLMALONIC ACID GC MS MS"]),
    "Homocysteine": ("Vitamins & minerals", None, ["HOMOCYSTEINE", "HOMOCYSTEINE NUTRITIONAL AND CONGENITAL"]),
    "CCP antibody (IgG)": ("Immunology", None, ["CYCLIC CITRULLINATED PEPTIDE CCP AB IGG", "CCP AB IGG"]),
    "Zinc": ("Vitamins & minerals", "mcg/dL", ["ZINC"]),
    "Copper": ("Vitamins & minerals", "mcg/dL", ["COPPER", "COPPER SERUM"]),
    "Ferritin": ("Vitamins & minerals", "ng/mL", ["FERRITIN"]),
    "Iron": ("Vitamins & minerals", "mcg/dL", ["IRON", "IRON TOTAL"]),
    "Magnesium": ("Vitamins & minerals", "mg/dL", ["MAGNESIUM"]),
    "Vitamin A": ("Vitamins & minerals", "mcg/dL", ["VITAMIN A RETINOL", "VITAMIN A"]),
    "Vitamin E (alpha-tocopherol)": ("Vitamins & minerals", "mg/L", ["VITAMIN E ALPHA TOCOPHEROL", "TOCOPHEROL VIT E", "VIT E ALPHA TOCOPHEROL"]),
    "Vitamin K": ("Vitamins & minerals", None, ["VITAMIN K"]),
    "Vitamin B6": ("Vitamins & minerals", None, ["VITAMIN B6 PLASMA", "VITAMIN B6"]),
    "Cortisol": ("Thyroid & hormones", "mcg/dL", ["CORTISOL", "CORTISOL TOTAL"]),
    "Cortisol (AM)": ("Thyroid & hormones", "mcg/dL", ["CORTISOL A M", "CORTISOL AM"]),
    "CK": ("Metabolic", "U/L", ["CK", "CREATINE KINASE CK", "CPK", "CREATINE KINASE TOTAL", "CREATINE KINASE TOTAL SERUM"]),
}
LAB_TESTS["TSH"][2].append("TSH 3RD GENERATION")
LAB_TESTS["Vitamin D, 25-OH"][2].extend(["VITAMIN D 25 OH TOTAL", "VITAMIN D 25 HYDROXY TOTAL"])
ALIASES = {norm(sp): canon for canon, (_, _, spellings) in LAB_TESTS.items() for sp in spellings + [canon]}

# Tests without an alias entry still get a group from their name (applied to the normalized name, in order).
GROUP_RULES = [
    (r"^(COMMENTS?$|CLIENT CONTACT|FASTING SPECIMEN|\d+ HOUR SPECIMEN|NEGATIVE CONTROL|REPORT ALWAYS|PLEASE NOTE|NOTE$|"
     r"DISCLAIMER|METHODOLOGY|INTERPRETATION$)", "Comments & admin"),
    (r"(GLUTAMIC ACID DECARBOXYLASE|GAD65|IA 2 ANTIBODY|ISLET CELL|INSULIN ANTIBOD|ZINC TRANSPORTER)", "Diabetes"),
    (r"^(CD\d|HLA DR|T CELL RECEPTOR|DNTS|S PNEUMO|TETANUS|KAPPA|LAMBDA|GAMMA GLOBULIN|ALPHA \d GLOBULIN|BETA \d GLOBULIN|"
     r"IMMUNOGLOBULIN|IG[GAME]\b|CYCLIC CITRULLINATED|RHEUMATOID|COMPLEMENT|SMOOTH MUSCLE|MITOCHONDRIA|ANA\b|ANTI)", "Immunology"),
    (r"(EBV|EPSTEIN|CYTOMEGALO|CMV|HIV|HEPATITIS|HELICOBACTER|SARS|COVID|LYME|SYPHILIS|RPR|QUANTIFERON|VARICELLA|"
     r"MEASLES|MUMPS|RUBELLA|INTERPRETATION|MESSAGE SIGNATURE)", "Infectious serology"),
    (r"^(LEAD|MERCURY|ARSENIC|CADMIUM|ALUMINUM|THALLIUM)\b", "Metals & toxicology"),
    (r"(CORTISOL|ACTH|PSA|TESTOSTERONE|ESTRADIOL|PROLACTIN|DHEA|INSULIN|C PEPTIDE|IGF|THYRO|T3\b|T4\b)", "Thyroid & hormones"),
    (r"(VITAMIN|TOCOPHEROL|RETINOL|FOLATE|B12|B6\b|THIAMINE|FERRITIN|IRON|TIBC|TRANSFERRIN|MAGNESIUM|PHOSPH|SELENIUM|COPPER|ZINC)",
     "Vitamins & minerals"),
    (r"(SED RATE|ESR\b|C REACTIVE|CRP|PROCALCITONIN)", "Inflammation"),
    (r"(LDL|HDL|CHOLESTEROL|APOLIPO|LP PLA2|LIPOPROTEIN|TRIGLYCERIDE|MYELOPEROXIDASE)", "Lipids"),
    (r"(A1C|GLUCOSE|FRUCTOSAMINE)", "Diabetes"),
    (r"(LIPASE|AMYLASE|ELASTASE|CALPROTECTIN|TRANSGLUTAMINASE|TTG|GLIADIN|ANTITRYPSIN|PYLORI|BILE ACID)", "GI & pancreas"),
    (r"(\bALT\b|\bAST\b|ALKALINE|BILIRUBIN|GGT|ALBUMIN|PROTEIN)", "Liver"),
    (r"(HEMOGLOBIN|HEMATOCRIT|PLATELET|RBC|WBC|NEUTRO|LYMPH|MONO|EOS|BASO|RETIC|MCV|MCH|RDW|MPV)", "Blood counts"),
    (r"(SODIUM|POTASSIUM|CHLORIDE|CO2|BUN|CREATININE|CALCIUM|EGFR|ANION)", "Metabolic"),
]

# Differential names that mean % or absolute depending on the unit (Quest: "NEUTROPHILS" is %).
DIFF_CELLS = {"NEUTROPHILS": "Neutrophils", "LYMPHOCYTES": "Lymphocytes", "MONOCYTES": "Monocytes",
              "EOSINOPHILS": "Eosinophils", "BASOPHILS": "Basophils"}

# Urinalysis LOINC codes: Quest reuses blood-test names ("GLUCOSE", "WBC") for urine results.
URINE_LOINC = {"25428-4", "5792-7", "5821-4", "13945-1", "5808-1", "20454-5", "2888-6", "5804-0", "5770-3",
               "2514-8", "5797-6", "5803-2", "5811-5", "5769-5", "5778-6", "5767-9", "5794-3", "5802-4",
               "5799-2", "11277-1", "5796-8", "630-4", "5818-1", "20405-7"}
URINE_NAME = re.compile(r",\s*ur\b|\bur ql\b|,?\s*\burine\b", re.I)

UNIT_FACTORS = {  # (canonical unit, raw unit) -> multiplier
    ("K/uL", "K/cumm"): 1, ("K/uL", "10*3/uL"): 1, ("K/uL", "Thousand/uL"): 1, ("K/uL", "x10E3/uL"): 1,
    ("K/uL", "cells/uL"): 0.001, ("K/uL", "cells/µL"): 0.001, ("K/uL", "/uL"): 0.001,
    ("M/uL", "M/cumm"): 1, ("M/uL", "10*6/uL"): 1, ("M/uL", "Million/uL"): 1, ("M/uL", "x10E6/uL"): 1,
    ("U/L", "Units/L"): 1, ("mL/min/1.73m2", "mL/min/1.73 m2"): 1, ("%", "% of total Hgb"): 1,
}

ADMIN_COMPONENTS = {"DISCLAIMER", "POC DEVICE NUMBER", "METHODOLOGY", "VENOUS CAPILLARY", "MISC CORE",
                    "UA REFLEX COMMENT", "CASE PATHOLOGIST", "GUARDIAN FIRST NAME", "GUARDIAN LAST NAME"}


def urine_name(name):
    words = URINE_NAME.sub(" ", name).split()
    body = " ".join(w if w in ("WBC", "RBC") else ("pH" if w.upper() == "PH" else w.lower()) for w in words)
    return f"Urine {body}".strip()


def canonical_test(name, common=None, unit=None, loinc=None):
    """(canonical name, group, canonical unit) for a raw test name."""
    if loinc in URINE_LOINC or URINE_NAME.search(name or ""):
        return urine_name(name or common or ""), "Urinalysis", None
    for cand in (name, common):
        n = norm(cand)
        if n in DIFF_CELLS:
            canon = DIFF_CELLS[n] + (" (%)" if (unit or "").strip() == "%" else " (abs)")
            group, cunit, _ = LAB_TESTS[canon]
            return canon, group, cunit
        if n in ALIASES:
            canon = ALIASES[n]
            group, cunit, _ = LAB_TESTS[canon]
            return canon, group, cunit
    raw = (name or common or "?").strip()
    group = next((g for pat, g in GROUP_RULES if re.search(pat, norm(raw))), "Other")
    return raw, group, None


def clean_unit(u):
    return re.sub(r"\s*\(?calc\)?", "", u or "").strip()


def convert_unit(value, raw_unit, canon_unit):
    raw_unit = (raw_unit or "").strip()
    if value is None or not canon_unit or raw_unit == canon_unit:
        return value, (canon_unit or raw_unit)
    f = UNIT_FACTORS.get((canon_unit, raw_unit))
    if f is None:
        return value, raw_unit
    return round(value * f, 4), canon_unit

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

from email_records import SCHEMA as EMAIL_SCHEMA, ingest_exports
from fhir_records import SCHEMA as FHIR_SCHEMA, ingest_exports as ingest_fhir_exports
from archive_records import ingest_archives
from tidepool_records import ingest_tidepool

SCHEMA_VERSION = "5"
SCHEMA = """
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE sources(
  key TEXT PRIMARY KEY, org TEXT, kind TEXT, system TEXT, method TEXT, path TEXT,
  exported_at TEXT, coverage_from TEXT, coverage_to TEXT, record_counts TEXT, gaps TEXT, notes TEXT);
CREATE TABLE labs(
  id INTEGER PRIMARY KEY, source TEXT, org TEXT, order_name TEXT, result_type TEXT,
  date TEXT, collected_at TEXT, test TEXT, test_group TEXT, test_raw TEXT, loinc TEXT,
  value_text TEXT, value_num REAL, comparator TEXT, units TEXT, units_raw TEXT,
  ref_low REAL, ref_high REAL, ref_text TEXT, flag TEXT, comment TEXT,
  lab TEXT, provider TEXT, source_file TEXT, source_id TEXT, provenance TEXT, dup_of INTEGER);
CREATE TABLE encounters(
  id INTEGER PRIMARY KEY, source TEXT, org TEXT, date TEXT, datetime TEXT, type TEXT,
  provider TEXT, dept TEXT, source_file TEXT, source_id TEXT);
CREATE TABLE documents(
  id INTEGER PRIMARY KEY, source TEXT, org TEXT, kind TEXT, date TEXT, title TEXT,
  author TEXT, dept TEXT, encounter_id INTEGER, parent_id INTEGER, text TEXT, path TEXT,
  format TEXT, source_id TEXT, provenance TEXT);
CREATE VIRTUAL TABLE documents_fts USING fts5(title, text, content='documents', content_rowid='id');
CREATE TABLE conditions(id INTEGER PRIMARY KEY, source TEXT, org TEXT, name TEXT, noted TEXT, kind TEXT);
CREATE TABLE procedures(id INTEGER PRIMARY KEY, source TEXT, org TEXT, name TEXT, date TEXT, kind TEXT);
CREATE TABLE medications(id INTEGER PRIMARY KEY, source TEXT, org TEXT, name TEXT, sig TEXT, date TEXT, provider TEXT);
CREATE TABLE immunizations(id INTEGER PRIMARY KEY, source TEXT, org TEXT, name TEXT, date TEXT);
CREATE TABLE allergies(id INTEGER PRIMARY KEY, source TEXT, org TEXT, name TEXT, reactions TEXT, severe TEXT, noted TEXT);
CREATE TABLE vitals_daily(date TEXT, metric TEXT, value REAL, min REAL, max REAL, n INTEGER, unit TEXT,
  PRIMARY KEY(date, metric));
CREATE TABLE device_samples(date TEXT, time TEXT, kind TEXT, value REAL, unit TEXT, detail REAL);
CREATE INDEX device_samples_date ON device_samples(date);
CREATE TABLE events(
  id INTEGER PRIMARY KEY, date TEXT, lane TEXT, title TEXT, detail TEXT, org TEXT,
  source TEXT, doc_ids TEXT, curated INTEGER DEFAULT 0, provenance TEXT);
CREATE VIEW labs_clean AS SELECT * FROM labs WHERE dup_of IS NULL;
CREATE INDEX labs_test_date ON labs(test, date);
CREATE INDEX documents_date ON documents(date);
CREATE INDEX documents_kind ON documents(kind);
CREATE INDEX encounters_date ON encounters(date);
"""

SCHEMA += EMAIL_SCHEMA + FHIR_SCHEMA


def insert(db, table, **row):
    cols = ", ".join(row)
    marks = ", ".join("?" for _ in row)
    return db.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", list(row.values())).lastrowid


def rel(p):
    return str(Path(p).resolve().relative_to(ROOT))

# ---------------------------------------------------------------------------
# PDF text (macOS PDFKit via a tiny Swift script; cached by content hash)
# ---------------------------------------------------------------------------

def pdf_text(path):
    cache_dir = DATA / "pdf_text_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()[:24]
    cached = cache_dir / f"{digest}.txt"
    if cached.exists():
        return cached.read_text(encoding="utf-8")
    text = ""
    try:
        from pypdf import PdfReader
        text = "\n\n".join(page.extract_text() or "" for page in PdfReader(path).pages).strip()
    except Exception:
        # PDFs are untrusted imports. An unsupported or malformed file remains available as a
        # source document even when the portable extractor cannot read its text.
        pass
    if not text and PDFTEXT.exists():
        module_cache = Path(tempfile.gettempdir()) / "healthpilot-swift-cache"
        env = dict(os.environ, CLANG_MODULE_CACHE_PATH=str(module_cache))
        try:
            out = subprocess.run(["swift", "-module-cache-path", str(module_cache), str(PDFTEXT), str(path)],
                                 capture_output=True, text=True, timeout=120, env=env)
            text = out.stdout.strip() if out.returncode == 0 else ""
        except (OSError, subprocess.TimeoutExpired):
            text = ""
    if text:
        cached.write_text(text, encoding="utf-8")
    return text

# ---------------------------------------------------------------------------
# C-CDA documents (standards-based "Download My Record" / IHE XDM folders)
# ---------------------------------------------------------------------------

V3 = "{urn:hl7-org:v3}"


def document_kind_from_filename(filename, default="document"):
    """Tag an explicitly named note file, never a message or a mention inside its text."""
    stem = Path(filename).stem
    return "note" if re.search(r"\b(?:chart|clinical|progress|consultation|visit|discharge)\s+notes?\b", stem, re.I) else default


def ingest_all_ccda(db):
    """C-CDA documents in uncompressed IHE XDM folders or MyChart record ZIPs under raw/."""
    orgs = db.execute("SELECT key, org FROM sources").fetchall()
    n = 0
    added_sources = set()
    for path in sorted({p.resolve() for p in RAW.rglob("*") if "IHE_XDM" in p.parts and p.suffix.lower() == ".xml"
                        and p.name.upper().startswith("DOC")}):
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError:
            continue
        custodian = root.findtext(f".//{V3}custodian//{V3}name") or ""
        matched = next(((k, o) for k, o in orgs if o and custodian and
                        (o.lower() in custodian.lower() or custodian.lower() in o.lower())), None)
        if matched:
            key, org = matched
        else:
            org = custodian or "C-CDA record download"
            slug = re.sub(r"[^a-z0-9]+", "-", org.lower()).strip("-")[:32] or "records"
            key = f"ccda-{slug}"
            if not db.execute("SELECT 1 FROM sources WHERE key=?", [key]).fetchone():
                package = next((parent.parent for parent in path.parents if parent.name == "IHE_XDM"), path.parent)
                insert(db, "sources", key=key, org=org, kind="C-CDA record download", system="HL7 C-CDA",
                       method="IHE XDM package containing HL7 ClinicalDocument XML; section narrative flattened for search",
                       path=rel(package), exported_at=datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="minutes"),
                       gaps=json.dumps({"summary": "Coverage is limited to the supplied C-CDA package."}),
                       notes="The original XML remains authoritative; only section narrative is projected into documents.")
                orgs.append((key, org))
            added_sources.add(key)
        n += ingest_ccda(db, root, path, key, org)

    # MyChart normally delivers a requested computer-readable record as a ZIP. Read the IHE XDM
    # documents directly so the user can select that download without unpacking or rearranging it.
    portal_zips = sorted(path for path in (RAW / "other").rglob("*")
                         if path.is_file() and path.suffix.lower() == ".zip") if (RAW / "other").exists() else []
    for zpath in portal_zips:
        try:
            with zipfile.ZipFile(zpath) as archive:
                infos = [info for info in archive.infolist()
                         if "/IHE_XDM/" in ("/" + info.filename.replace("\\", "/")).upper()
                         and Path(info.filename).name.upper().startswith("DOC")
                         and Path(info.filename).suffix.lower() == ".xml"]
                for info in sorted(infos, key=lambda item: item.filename):
                    if info.file_size > 100 * 1024 * 1024:
                        continue
                    try:
                        root = ET.fromstring(archive.read(info))
                    except (ET.ParseError, RuntimeError, zipfile.BadZipFile):
                        continue
                    custodian = root.findtext(f".//{V3}custodian//{V3}name") or ""
                    matched = next(((k, o) for k, o in orgs if o and custodian and
                                    (o.lower() in custodian.lower() or custodian.lower() in o.lower())), None)
                    if matched:
                        key, org = matched
                    else:
                        org = custodian or "C-CDA record download"
                        slug = re.sub(r"[^a-z0-9]+", "-", org.lower()).strip("-")[:32] or "records"
                        key = f"ccda-{slug}"
                        if not db.execute("SELECT 1 FROM sources WHERE key=?", [key]).fetchone():
                            insert(db, "sources", key=key, org=org, kind="C-CDA record download", system="HL7 C-CDA",
                                   method="MyChart record ZIP containing an IHE XDM package with HL7 ClinicalDocument XML; section narrative flattened for search",
                                   path=rel(zpath), exported_at=datetime.fromtimestamp(zpath.stat().st_mtime).isoformat(timespec="minutes"),
                                   gaps=json.dumps({"summary": "Coverage is limited to the supplied C-CDA package."}),
                                   notes="The original ZIP and XML remain authoritative; only section narrative is projected into documents.")
                            orgs.append((key, org))
                        added_sources.add(key)
                    n += ingest_ccda(db, root, f"{rel(zpath)}!/{info.filename}", key, org)
        except (OSError, zipfile.BadZipFile):
            continue
    for key in added_sources:
        count, first, last = db.execute(
            "SELECT count(*), min(date), max(date) FROM documents WHERE source=? AND kind IN ('ccda', 'note')", [key]).fetchone()
        visit_count = db.execute("SELECT count(*) FROM encounters WHERE source=?", [key]).fetchone()[0]
        db.execute("UPDATE sources SET coverage_from=?, coverage_to=?, record_counts=? WHERE key=?",
                   [first, last, json.dumps({"documents": count, "encounters": visit_count}), key])
    return n


def ingest_ccda(db, root, path, key, org):
    path_text = str(path)
    fallback_title = Path(path_text.split("!/", 1)[-1]).stem
    title = (root.findtext(f"{V3}title") or fallback_title).strip()
    # Prefer the visit date (encompassingEncounter / serviceEvent) over the date the file was generated.
    date = None
    for xp in (f"{V3}componentOf/{V3}encompassingEncounter/{V3}effectiveTime/{V3}low",
               f"{V3}componentOf/{V3}encompassingEncounter/{V3}effectiveTime",
               f"{V3}documentationOf/{V3}serviceEvent/{V3}effectiveTime/{V3}high",
               f"{V3}effectiveTime"):
        el = root.find(xp)
        date = parse_when(el.get("value") if el is not None else None)[0]
        if date:
            break
    parts = []
    for sec in root.iter(f"{V3}section"):
        st = (sec.findtext(f"{V3}title") or "").strip()
        body = sec.find(f"{V3}text")
        txt = html_to_text(re.sub(r"<(/?)ns\d+:", r"<\1", ET.tostring(body, encoding="unicode"))) if body is not None else ""
        if txt:
            parts.append(f"## {st}\n{txt}" if st else txt)
    text = "\n\n".join(parts)
    if not parts or db.execute("SELECT 1 FROM documents WHERE kind IN ('ccda', 'note') AND text=?", [text]).fetchone():
        return 0  # empty, or the same document already came in via another download
    idel = root.find(f"{V3}id")
    stored_path = path_text if "!/" in path_text else rel(path)
    encounter = root.find(f"{V3}componentOf/{V3}encompassingEncounter")
    encounter_id = None
    if encounter is not None:
        effective = encounter.find(f"{V3}effectiveTime")
        low = effective.find(f"{V3}low") if effective is not None else None
        when = low.get("value") if low is not None else (effective.get("value") if effective is not None else None)
        visit_date, visit_datetime = parse_when(when)
        if visit_date:
            coded = encounter.find(f"{V3}code")
            visit_type = (coded.get("displayName") or coded.get("code")) if coded is not None else None
            encounter_source_id = encounter.find(f"{V3}id")
            encounter_id = insert(db, "encounters", source=key, org=org, date=visit_date,
                                  datetime=visit_datetime, type=visit_type or "Encounter",
                                  source_file=stored_path,
                                  source_id=(encounter_source_id.get("root") or encounter_source_id.get("extension"))
                                  if encounter_source_id is not None else None)
    document_code = root.find(f"{V3}code")
    # LOINC 34133-9 names an episode summary note. Tag it as a clinical note only
    # when the file also identifies a specific encounter; longitudinal summaries stay C-CDA.
    kind = "note" if encounter_id and document_code is not None and document_code.get("code") == "34133-9" \
        and document_code.get("codeSystem") == "2.16.840.1.113883.6.1" else "ccda"
    insert(db, "documents", source=key, org=org, kind=kind, date=date, title=title, text=text, path=stored_path,
           encounter_id=encounter_id,
           format="xml", source_id=(idel.get("root") if idel is not None else None),
           provenance="C-CDA ClinicalDocument (HL7 standard) from a record-download package; section text flattened; "
                      "encounter projected only from encompassingEncounter; note type from document LOINC code")
    return 1

# ---------------------------------------------------------------------------
# Apple Health: clinical lab records (FHIR) + device data (export.xml)
# ---------------------------------------------------------------------------

def fhir_code(code):
    code = code or {}
    codings = code.get("coding") or []
    loinc = next((c.get("code") for c in codings if "loinc" in (c.get("system") or "")), None)
    name = code.get("text") or next((c.get("display") for c in codings if c.get("display")), None)
    return name, loinc


def first_coding(x):
    if isinstance(x, list):
        x = x[0] if x else {}
    codings = (x or {}).get("coding") or []
    return codings[0].get("code") if codings else None


def ingest_fhir_observation(db, obs, key, org, order_name, source_file, provenance):
    name, loinc = fhir_code(obs.get("code"))
    vq = obs.get("valueQuantity") or {}
    raw_value = vq.get("value")
    units_raw = clean_unit(vq.get("unit") or vq.get("code"))
    coded_value, _ = fhir_code(obs.get("valueCodeableConcept"))
    scalar_value = next((obs.get(k) for k in ("valueInteger", "valueDecimal", "valueBoolean") if k in obs), None)
    value_text = obs.get("valueString") or coded_value or ("" if raw_value is None and scalar_value is None
                                                            else str(scalar_value if raw_value is None else f"{vq.get('comparator') or ''}{raw_value}"))
    num, comp = parse_value(value_text, raw_value if isinstance(raw_value, (int, float)) else None)
    comp = vq.get("comparator") or comp
    canon, group, cunit = canonical_test(name, None, units_raw, loinc)
    value_num, units = convert_unit(num, units_raw, cunit)
    rr = (obs.get("referenceRange") or [{}])[0]
    lo = convert_unit((rr.get("low") or {}).get("value"), units_raw, cunit)[0]
    hi = convert_unit((rr.get("high") or {}).get("value"), units_raw, cunit)[0]
    interp = first_coding(obs.get("interpretation"))
    flag = {"H": "High", "HH": "High", "L": "Low", "LL": "Low", "A": "Abnormal", "AA": "Abnormal"}.get(interp)
    date, when = parse_when(obs.get("effectiveDateTime") or obs.get("issued"))
    comment = obs.get("comments") or obs.get("note")
    if isinstance(comment, list):
        comment = "\n".join(c.get("text", "") for c in comment if isinstance(c, dict))
    insert(db, "labs", source=key, org=org, order_name=order_name, result_type="LAB", date=date, collected_at=when,
           test=canon, test_group=group, test_raw=name, value_text=value_text, value_num=value_num, comparator=comp,
           units=units, units_raw=units_raw, ref_low=lo, ref_high=hi, ref_text=rr.get("text"), flag=flag,
           comment=(comment or None), lab=org, provider=None, source_file=source_file, loinc=loinc,
           source_id=obs.get("id"), provenance=provenance)


def ingest_apple_clinical(db, zpath):
    z = zipfile.ZipFile(zpath)
    counts = defaultdict(int)
    src = f"{rel(zpath)}!clinical-records"
    for name in sorted(n for n in z.namelist() if "/clinical-records/" in n and n.endswith(".json")):
        res = json.loads(z.read(name))
        rt = res.get("resourceType")
        if rt == "Observation":
            ingest_fhir_observation(db, res, "apple", "Quest Diagnostics (Apple Health)", None, f"{rel(zpath)}!{name}",
                                    "apple:clinical-records — FHIR DSTU2 Observation fetched by the Health app from the "
                                    "MyQuest connection (no performer field; attributed to Quest because the only other "
                                    "connected lab, LabCorp, delivers DiagnosticReports with labcorp.com identifiers)")
            counts["labs (Quest)"] += 1
        elif rt == "DiagnosticReport":
            systems = " ".join(i.get("system") or "" for i in res.get("identifier") or [])
            org = "LabCorp (Apple Health)" if "labcorp" in systems.lower() else "Lab (Apple Health)"
            order, _ = fhir_code(res.get("code"))
            for obs in res.get("contained") or []:
                if obs.get("resourceType") == "Observation":
                    ingest_fhir_observation(db, obs, "apple", org, order, f"{rel(zpath)}!{name}",
                                            "apple:clinical-records — Observation contained in a FHIR DSTU2 "
                                            "DiagnosticReport fetched by the Health app (LabCorp identifiers)")
                    counts["labs (LabCorp)"] += 1
        elif rt == "Immunization":
            vname, _ = fhir_code(res.get("vaccineCode"))
            insert(db, "immunizations", source="apple", org="Apple Health", name=vname,
                   date=parse_when(res.get("date") or res.get("occurrenceDateTime"))[0])
            counts["immunizations"] += 1
        elif rt == "Patient" and not db.execute("SELECT 1 FROM meta WHERE key='patient'").fetchone():
            db.execute("INSERT INTO meta VALUES ('patient', ?)", [json.dumps({"birthDate": res.get("birthDate")})])
    insert(db, "sources", key="apple", org="Apple Health", kind="Apple Health export",
           system="Apple Health app (iPhone): Health Records (FHIR) + HealthKit device data",
           method="'Export All Health Data' zip. clinical-records/*.json are FHIR DSTU2 resources the Health app pulled from "
                  "connected lab portals (MyQuest, LabCorp) → labs, immunizations. export.xml is every HealthKit sample "
                  "(Apple Watch, Dexcom CGM, Loop, scales, apps) → vitals_daily, rolled up to one row per day and metric",
           path=src, exported_at=datetime.fromtimestamp(zpath.stat().st_mtime).isoformat(timespec="minutes"),
           record_counts=json.dumps(dict(counts)),
           notes="Lab rows carry LOINC codes. Reference ranges and flags are as the lab reported them. "
                 "Device data is summarized per day (mean/min/max or daily total); raw samples stay in the zip.")
    return dict(counts)


# HealthKit type -> (metric key, unit, how to roll up a day)
VITAL_TYPES = {
    "HKQuantityTypeIdentifierBodyMass": ("Weight", "lb", "mean"),
    "HKQuantityTypeIdentifierBloodPressureSystolic": ("BP systolic", "mmHg", "mean"),
    "HKQuantityTypeIdentifierBloodPressureDiastolic": ("BP diastolic", "mmHg", "mean"),
    "HKQuantityTypeIdentifierRestingHeartRate": ("Resting heart rate", "bpm", "mean"),
    "HKQuantityTypeIdentifierHeartRateVariabilitySDNN": ("HRV (SDNN)", "ms", "mean"),
    "HKQuantityTypeIdentifierBloodGlucose": ("CGM / meter glucose", "mg/dL", "mean"),
    "HKQuantityTypeIdentifierOxygenSaturation": ("Blood oxygen", "%", "mean"),
    "HKQuantityTypeIdentifierVO2Max": ("VO2 max", "mL/kg/min", "mean"),
    "HKQuantityTypeIdentifierBodyFatPercentage": ("Body fat", "%", "mean"),
    "HKQuantityTypeIdentifierStepCount": ("Steps", "steps", "sum"),
    "HKQuantityTypeIdentifierInsulinDelivery": ("Insulin", "U", "sum"),
    "HKQuantityTypeIdentifierDietaryCarbohydrates": ("Carbs logged", "g", "sum"),
}
SLEEP = "HKCategoryTypeIdentifierSleepAnalysis"


def to_unit(value, unit, metric):
    if metric == "Weight" and unit == "kg":
        return value * 2.20462
    if unit == "%" or (metric in ("Blood oxygen", "Body fat") and value <= 1):
        return value * 100 if value <= 1 else value
    if metric == "CGM / meter glucose" and unit == "mmol<180.1558800000541>/L":
        return value * 18.016
    return value


def parse_apple_vitals(zpath):
    """Stream export.xml once and roll device data up to one row per day and metric."""
    z = zipfile.ZipFile(zpath)
    xml_name = next(n for n in z.namelist() if n.endswith("/export.xml"))
    means = defaultdict(lambda: [0.0, 0, float("inf"), float("-inf")])  # (date, metric) -> sum, n, min, max
    sums = defaultdict(float)  # (date, metric, source) -> total   (max across sources avoids double-counting)
    insulin = defaultdict(lambda: defaultdict(float))  # (date, source) -> totals by recorded delivery reason
    glucose_in_range = defaultdict(lambda: [0, 0])
    sleep = defaultdict(float)  # (night, source) -> hours asleep
    type_counts = defaultdict(int)
    with z.open(xml_name) as fh:
        ctx = ET.iterparse(fh, events=("start", "end"))
        _, root = next(ctx)
        for i, (ev, el) in enumerate(ctx):
            if ev != "end":
                continue
            if el.tag == "Record":
                t = el.get("type")
                type_counts[t] += 1
                if t in VITAL_TYPES:
                    metric, _, how = VITAL_TYPES[t]
                    try:
                        v = to_unit(float(el.get("value")), el.get("unit"), metric)
                    except (TypeError, ValueError):
                        v = None
                    if v is not None:
                        day = el.get("startDate", "")[:10]
                        if how == "sum":
                            sums[(day, metric, el.get("sourceName"))] += v
                            if metric == "Insulin":
                                reasons = {m.get("value") for m in el.findall("MetadataEntry")
                                           if m.get("key") in ("HKInsulinDeliveryReason", "HKMetadataKeyInsulinDeliveryReason")}
                                reason = next(iter(reasons)) if len(reasons) == 1 else None
                                label = {"1": "Insulin basal", "2": "Insulin bolus"}.get(reason, "Insulin unspecified")
                                insulin[(day, el.get("sourceName"))][label] += v
                        else:
                            m = means[(day, metric)]
                            m[0] += v; m[1] += 1; m[2] = min(m[2], v); m[3] = max(m[3], v)
                            if metric == "CGM / meter glucose":
                                g = glucose_in_range[day]
                                g[0] += 70 <= v <= 180; g[1] += 1
                elif t == SLEEP and "Asleep" in (el.get("value") or ""):
                    s, e = el.get("startDate"), el.get("endDate")
                    try:
                        fmt = "%Y-%m-%d %H:%M:%S %z"
                        hrs = (datetime.strptime(e, fmt) - datetime.strptime(s, fmt)).total_seconds() / 3600
                        sleep[(e[:10], el.get("sourceName"))] += hrs
                    except (TypeError, ValueError):
                        pass
                root.clear()
            elif i % 5000 == 0:
                root.clear()
    rows = []
    for (day, metric), (tot, n, lo, hi) in means.items():
        unit = next(u for _, (m, u, _) in VITAL_TYPES.items() if m == metric)
        rows.append([day, metric, round(tot / n, 2), round(lo, 2), round(hi, 2), n, unit])
    best = {}
    for (day, metric, _src), tot in sums.items():
        best[(day, metric)] = max(best.get((day, metric), 0), tot)
    for (day, metric), tot in best.items():
        unit = next(u for _, (m, u, _) in VITAL_TYPES.items() if m == metric)
        rows.append([day, metric, round(tot, 1), None, None, None, unit])
    # Keep each day's breakdown from the SAME source as the chosen daily total. Taking
    # independent maxima for basal and bolus could combine duplicate feeds into excess insulin.
    chosen_insulin = {}
    for (day, source), parts in insulin.items():
        rank = (sums[(day, "Insulin", source)], -parts.get("Insulin unspecified", 0), source or "")
        if day not in chosen_insulin or rank > chosen_insulin[day][0]:
            chosen_insulin[day] = (rank, parts)
    for day, (_, parts) in chosen_insulin.items():
        for metric, total in parts.items():
            rows.append([day, metric, round(total, 1), None, None, None, "U"])
    for day, (inr, n) in glucose_in_range.items():
        if n >= 12:  # enough readings to call it a CGM day
            rows.append([day, "Glucose time in range 70–180", round(100 * inr / n, 1), None, None, n, "%"])
    nights = {}
    for (night, _src), hrs in sleep.items():
        nights[night] = max(nights.get(night, 0), hrs)
    for night, hrs in nights.items():
        if 0.5 <= hrs <= 16:
            rows.append([night, "Sleep", round(hrs, 2), None, None, None, "h"])
    return {"rows": rows, "type_counts": dict(sorted(type_counts.items(), key=lambda x: -x[1]))}


def apple_vitals(zpath):
    st = zpath.stat()
    # v2 retains insulin delivery reasons; v1 caches only contained the combined daily total.
    cache = DATA / f"apple_vitals_v2_{st.st_size}_{int(st.st_mtime)}.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    print(f"  parsing {zpath.name} device data (one-time, several minutes)…", flush=True)
    result = parse_apple_vitals(zpath)
    for old in DATA.glob("apple_vitals_*.json"):
        old.unlink()
    cache.write_text(json.dumps(result), encoding="utf-8")
    return result

# ---------------------------------------------------------------------------
# Extra files, curated events, de-duplication, derived timeline
# ---------------------------------------------------------------------------

def ingest_loose_files(db):
    n = 0
    for folder in (RAW / "other", RAW / "quest-pdfs"):
        for p in sorted(folder.rglob("*")) if folder.exists() else []:
            ext = p.suffix.lower()
            if ext not in (".pdf", ".html", ".htm", ".txt", ".md") or any((a / "IHE_XDM").is_dir() for a in p.parents):
                continue
            text = pdf_text(p) if ext == ".pdf" else (html_to_text(p.read_text(encoding="utf-8", errors="replace"))
                                                     if ext in (".html", ".htm") else p.read_text(encoding="utf-8", errors="replace"))
            date = parse_when(re.search(r"\d{4}-\d{2}-\d{2}", p.name).group(0))[0] if re.search(r"\d{4}-\d{2}-\d{2}", p.name) else None
            insert(db, "documents", source=folder.name, org=folder.name,
                   kind=document_kind_from_filename(p.name), date=date,
                   title=p.stem, text=text, path=rel(p), format=ext.lstrip("."),
                   provenance=f"raw/{folder.name} — file added by hand (date taken from the file name when it has one)")
            n += 1
    return n


JOURNAL = ROOT / "journal.md"


def ingest_journal(db):
    """journal.md — the patient's own dated observations. Each `## YYYY-MM-DD — headline` starts an entry;
    optional first lines `lane: <timeline lane>` (default Symptoms) and `tags: Immune, Neuro` link it to topics.
    Each entry becomes a searchable document (kind=journal) and a hand-curated timeline event."""
    if not JOURNAL.exists():
        return 0
    entries = re.split(r"^## +(?=\d{4}-\d{2}-\d{2})", JOURNAL.read_text(encoding="utf-8"), flags=re.M)[1:]
    n = 0
    for raw in entries:
        head, _, body = raw.partition("\n")
        m = re.match(r"(\d{4}-\d{2}-\d{2})\s*[—–-]*\s*(.*)", head.strip())
        if not m:
            continue
        date, title = m.group(1), m.group(2).strip() or "Journal entry"
        lane, tags, lines = "Symptoms", "", []
        for ln in body.strip("\n").split("\n"):
            lm = re.match(r"^(lane|tags):\s*(.+)$", ln.strip(), re.I)
            if lm and not lines:
                if lm.group(1).lower() == "lane" and lm.group(2).strip() in LANES:
                    lane = lm.group(2).strip()
                elif lm.group(1).lower() == "tags":
                    tags = lm.group(2).strip()
                continue
            lines.append(ln)
        text = "\n".join(lines).strip()
        did = insert(db, "documents", source="journal", org="Patient", kind="journal", date=date, title=title,
                     author="Patient", text=(f"tags: {tags}\n\n" if tags else "") + text, path=rel(JOURNAL), format="md",
                     provenance="journal.md — written by the patient (not a clinical record)")
        insert(db, "events", date=date, lane=lane, title=title, detail=text[:600], org="Patient", source="journal",
               doc_ids=json.dumps([did]), curated=1, provenance="journal")
        n += 1
    if n:
        insert(db, "sources", key="journal", org="Patient", kind="Patient journal", system="journal.md in this folder",
               method="Markdown entries written by the patient; `## YYYY-MM-DD — headline`, optional lane:/tags: lines",
               path=rel(JOURNAL), exported_at=datetime.fromtimestamp(JOURNAL.stat().st_mtime).isoformat(timespec="minutes"),
               record_counts=json.dumps({"entries": n}),
               notes="Patient-authored. Not a clinical record; shown as such wherever it appears.")
        cov = db.execute("SELECT min(date), max(date) FROM documents WHERE source='journal'").fetchone()
        db.execute("UPDATE sources SET coverage_from=?, coverage_to=? WHERE key='journal'", cov)
    return n


def dedupe_labs(db):
    """Same dated test/value/unit/comparator; prefer FHIR sources, then Apple, then email OCR."""
    seen = {}
    dups = 0
    db.execute("UPDATE labs SET dup_of=NULL")
    order = "CASE WHEN source LIKE 'email-%' THEN 2 WHEN source='apple' THEN 1 ELSE 0 END, id"
    for lid, date, test, num, text, unit, comparator in db.execute(
            f"SELECT id, date, test, value_num, value_text, units, comparator FROM labs ORDER BY {order}"):
        if not date:
            continue
        k = (date, test.lower(), round(num, 4) if num is not None else (text or "").strip().lower(),
             (unit or "").strip(), comparator or "")
        if k in seen:
            db.execute("UPDATE labs SET dup_of=? WHERE id=?", [seen[k], lid])
            dups += 1
        else:
            seen[k] = lid
    return dups


SIGNIFICANT_ENCOUNTERS = [
    (r"surgery|anesthesia|procedure", "Surgery & procedures"),
    (r"infusion", "Surgery & procedures"),
    (r"emergency|hospital visit|admission|inpatient|observation|hospital encounter", "Hospital & ED"),
]


def build_events(db):
    # Diagnoses: problem-list entries with a noted date (one per name)
    seen = set()
    for name, noted, org, src in db.execute(
            "SELECT name, noted, org, source FROM conditions WHERE kind='problem' AND noted IS NOT NULL ORDER BY noted"):
        if name.lower() in seen:
            continue
        seen.add(name.lower())
        insert(db, "events", date=noted, lane="Diagnoses", title=name, detail="Added to problem list",
               org=org, source=src, doc_ids="[]", provenance="problem_list")
    for name, date, org, src in db.execute("SELECT name, date, org, source FROM procedures WHERE date IS NOT NULL"):
        if db.execute("SELECT 1 FROM documents WHERE kind='report' AND date=? AND lower(title)=lower(?)", [date, name]).fetchone() \
                or re.match(r"(US|XR|CT|MRI|MR)\b", name, re.I):
            continue
        insert(db, "events", date=date, lane="Surgery & procedures", title=name.title(),
               detail="From surgical history", org=org, source=src, doc_ids="[]", provenance="surgical_history")
    # Significant visits, with their notes attached
    grouped = {}
    for eid, date, typ, dept, prov, org, src in db.execute(
            "SELECT id, date, type, dept, provider, org, source FROM encounters WHERE date IS NOT NULL"):
        lane = next((ln for pat, ln in SIGNIFICANT_ENCOUNTERS if re.search(pat, typ or "", re.I)), None)
        if not lane or date > datetime.now().strftime("%Y-%m-%d"):
            continue
        docs = [r[0] for r in db.execute("SELECT id FROM documents WHERE encounter_id=? AND kind='note'", [eid])]
        titles = [r[0] for r in db.execute("SELECT DISTINCT title FROM documents WHERE encounter_id=? AND kind='note'", [eid])]
        addressed = [m.group(1) for (t,) in db.execute("SELECT text FROM documents WHERE encounter_id=? AND kind='avs'", [eid])
                     for m in [re.search(r"following issues were addressed:\s*(.+?)\.", t or "", re.S)] if m]
        g = grouped.setdefault((date, lane), {"types": [], "depts": [], "provs": [], "docs": [], "titles": [], "addressed": [],
                                              "org": org, "src": src})
        g["types"].append(typ); g["depts"].append(dept); g["provs"].append(prov); g["docs"] += docs; g["titles"] += titles
        g["addressed"] += addressed
    for (date, lane), g in list(grouped.items()):
        proc = grouped.get((date, "Surgery & procedures"))
        admitted = any(re.search(r"discharge summary", t, re.I) for t in g["titles"])
        if lane == "Hospital & ED" and proc and not admitted and not any(re.search("emergency", t, re.I) for t in g["types"]):
            for k in ("provs", "docs", "titles", "addressed"):
                proc[k] += g[k]
            del grouped[(date, lane)]
    for (date, lane), g in grouped.items():
        src = g["src"]
        uniq = lambda xs: list(dict.fromkeys(x for x in xs if x))
        title = " / ".join(uniq(g["types"])) + (f" — {uniq(g['depts'])[0]}" if uniq(g["depts"]) else "")
        detail = "; ".join(filter(None, ["Addressed: " + ", ".join(uniq(g["addressed"])) if uniq(g["addressed"]) else "",
                                         "Providers: " + ", ".join(uniq(g["provs"])) if uniq(g["provs"]) else "",
                                         "Notes: " + ", ".join(uniq(g["titles"])) if uniq(g["titles"]) else ""]))
        insert(db, "events", date=date, lane=lane, title=title, detail=detail, org=g["org"], source=src,
               doc_ids=json.dumps(g["docs"]), provenance="encounter")
    # Imaging and pathology/other reports
    for did, date, title, text, org, src, path in db.execute(
            "SELECT id, date, title, text, org, source, path FROM documents WHERE kind='report' AND date IS NOT NULL"):
        rtype = db.execute("SELECT result_type FROM labs WHERE source_file=? LIMIT 1", [path]).fetchone()
        is_imaging = re.search(r"\b(XR|CT|MRI|MR|US|ULTRASOUND|X-RAY|DEXA|NM|PET|FLUORO|MAMMO|ECHO)\b", title or "", re.I)
        if rtype and rtype[0] == "LAB" and not re.search(r"patholog|biopsy|surgical", (title or "") + text[:200], re.I):
            continue
        lane = "Imaging" if is_imaging else "Pathology & reports"
        impression = re.search(r"Impression:\n(.+?)(?:\n\n|$)", text, re.S)
        final_dx = re.search(r"Final Diagnosis:?\n(.+?)(?:\n\n|$)", text, re.S)
        detail = ((final_dx or impression).group(1) if (final_dx or impression) else text[:400]).strip()[:600]
        same = db.execute("SELECT id, title, doc_ids FROM events WHERE date=? AND lane=? AND detail=?", [date, lane, detail]).fetchone()
        if same:
            db.execute("UPDATE events SET title=?, doc_ids=? WHERE id=?",
                       [f"{same[1]} + {title}", json.dumps(json.loads(same[2]) + [did]), same[0]])
            continue
        insert(db, "events", date=date, lane=lane, title=title, detail=detail, org=org, source=src,
               doc_ids=json.dumps([did]), provenance="report")
    # Hand-curated events. `docs` lists source files (stable across rebuilds); `replaces` removes the
    # auto-generated events this row supersedes: "*" = same lane and day, other text = same lane, title contains it.
    if CURATED.exists():
        doc_by_path = {path: did for did, path in db.execute("SELECT id, path FROM documents")}
        with CURATED.open(newline="", encoding="utf-8-sig") as fh:
            for row in csv.DictReader(fh):
                date = parse_when(row.get("date"))[0]
                if not date or not row.get("title"):
                    continue
                lane = row.get("lane") if row.get("lane") in LANES else "Milestones"
                replaces = (row.get("replaces") or "").strip()
                if replaces == "*":
                    db.execute("DELETE FROM events WHERE curated=0 AND lane=? AND date=?", [lane, date])
                elif replaces:
                    db.execute("DELETE FROM events WHERE curated=0 AND lane=? AND lower(title) LIKE ?", [lane, f"%{replaces.lower()}%"])
                doc_ids = []
                for ref in filter(None, (x.strip() for x in (row.get("docs") or "").split(";"))):
                    if "|" in ref:
                        d, t = ref.split("|", 1)
                        found = [r[0] for r in db.execute("SELECT id FROM documents WHERE date=? AND title=?", [d.strip(), t.strip()])]
                    else:
                        found = [doc_by_path[ref]] if ref in doc_by_path else []
                    if not found:
                        print(f"  warning: curated event '{row['title']}' cites a record that wasn't found: {ref}")
                    doc_ids += found
                insert(db, "events", date=date, lane=lane, title=row["title"], detail=row.get("detail") or "",
                       org=row.get("org") or "", source="curated", doc_ids=json.dumps(doc_ids), curated=1,
                       provenance="curated")

# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

def rows(db, sql, *args):
    cur = db.execute(sql, args)
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur]


def short_org(org, source):
    import reports
    return reports.short_org(org, source)


def dashboard_topics(db):
    """Topic membership for the dashboard's tags and one-click filters (same matching as the case study)."""
    import reports
    out = []
    for name, t in reports.load_topics().items():
        docs = reports.topic_docs(db, t, name=name)
        tests = reports.topic_tests(db, t)
        collapse = reports.rx(list((t.get("collapse") or {}).keys()))
        chart = [x["test"] for x in sorted(tests, key=lambda x: -x["n"])
                 if not (collapse and collapse.search(x["test"]))
                 and db.execute("SELECT count(*) FROM labs_clean WHERE test=? AND value_num IS NOT NULL", [x["test"]]).fetchone()[0] >= 2][:12]
        kw = reports.rx(t.get("keywords"))
        out.append({"name": name, "status": t.get("status", ""), "framing": t.get("framing", ""),
                    "docs": [d["id"] for d in docs], "tests": [x["test"] for x in tests], "chart_tests": chart,
                    "latest": docs[-1]["date"] if docs else None,
                    "problems": [c["name"] for c in rows(db, "SELECT DISTINCT name FROM conditions") if kw and kw.search(c["name"])]})
    return out


def build_dashboard(db):
    patient = json.loads((db.execute("SELECT value FROM meta WHERE key='patient'").fetchone() or ["{}"])[0])
    org_short = {r["key"]: short_org(r["org"], r["key"]) for r in rows(db, "SELECT key, org FROM sources")}
    labs = [{"t": r["test"], "g": r["test_group"], "d": r["collected_at"] or r["date"], "v": r["value_num"],
             "vt": r["value_text"], "c": r["comparator"], "u": r["units"], "lo": r["ref_low"], "hi": r["ref_high"],
             "rt": r["ref_text"], "f": r["flag"], "o": short_org(r["org"], r["source"]), "on": r["order_name"],
             "cm": r["comment"]}
            for r in rows(db, "SELECT * FROM labs_clean WHERE date IS NOT NULL ORDER BY date, test")]
    docs = [{"id": r["id"], "k": r["kind"], "d": r["date"], "ti": r["title"], "a": r["author"], "dp": r["dept"],
             "o": org_short.get(r["source"], r["org"]), "p": r["path"], "x": r["text"] or "", "e": r["encounter_id"]}
            for r in rows(db, "SELECT * FROM documents ORDER BY date DESC")]
    data = {
        "demo": (ROOT / ".clippi-demo.json").exists(),
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "patient": patient,
        "sources": [dict(r, short=org_short[r["key"]]) for r in rows(db, "SELECT * FROM sources")],
        "labs": labs,
        "docs": docs,
        "events": [dict(r, o=org_short.get(r["source"], r["org"] or "")) for r in
                   rows(db, "SELECT date, lane, title, detail, org, source, doc_ids, curated FROM events ORDER BY date")],
        "encounters": [dict(r, o=org_short.get(r["source"], r["source"])) for r in
                       rows(db, "SELECT id, date, type, dept, provider, source FROM encounters ORDER BY date DESC")],
        "problems": [dict(r, o=org_short.get(r["source"], r["source"])) for r in
                     rows(db, "SELECT name, noted, kind, source, org FROM conditions ORDER BY kind, noted DESC")],
        "procedures": [dict(r, o=org_short.get(r["source"], r["source"])) for r in
                       rows(db, "SELECT name, date, source, org FROM procedures ORDER BY date DESC")],
        "meds": [dict(r, o=org_short.get(r["source"], r["source"])) for r in
                 rows(db, "SELECT name, sig, date, provider, source, org FROM medications ORDER BY name")],
        "immunizations": [dict(r, o=org_short.get(r["source"], r["source"])) for r in
                          rows(db, "SELECT name, date, source, org FROM immunizations ORDER BY date DESC")],
        "allergies": rows(db, "SELECT name, reactions, severe, noted FROM allergies"),
        "vitals": rows(db, "SELECT date, metric, value, min, max, n, unit FROM vitals_daily ORDER BY metric, date"),
        "samples": [[r["time"], r["kind"], r["value"], r["detail"]] for r in
                    rows(db, "SELECT time, kind, value, detail FROM device_samples ORDER BY time")],
        "lanes": LANES,
        "topics": dashboard_topics(db),
    }
    payload = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    page = TEMPLATE.read_text(encoding="utf-8")
    page = page.replace("/*__PLOTLY__*/", PLOTLY.read_text(encoding="utf-8").replace("</script", "<\\/script"))
    page = page.replace("/*__DATA__*/null", payload)
    page = page.replace("__LOGO_BASE64__", base64.b64encode(LOGO.read_bytes()).decode("ascii"))
    DASHBOARD.write_text(page, encoding="utf-8")
    return len(page)

# ---------------------------------------------------------------------------

def export_tables(db):
    """Plain CSV copies of every table (documents without their text — that lives in data/records/)."""
    out = DATA / "export"
    out.mkdir(exist_ok=True)
    queries = {
        "labs": "SELECT * FROM labs_clean ORDER BY date, test",
        "labs_with_duplicates": "SELECT * FROM labs ORDER BY date, test",
        "email_lab_evidence": "SELECT * FROM email_lab_evidence ORDER BY id",
        "fhir_resources": "SELECT id, source, org, resource_type, resource_id, last_updated, source_file, "
                          "length(json) AS json_chars FROM fhir_resources ORDER BY source, id",
        "documents": "SELECT id, source, org, kind, date, title, author, dept, encounter_id, parent_id, path, format, "
                     "source_id, provenance, length(text) AS text_chars FROM documents ORDER BY date, id",
        "encounters": "SELECT * FROM encounters ORDER BY date",
        "conditions": "SELECT * FROM conditions ORDER BY kind, noted",
        "procedures": "SELECT * FROM procedures ORDER BY date",
        "medications": "SELECT * FROM medications ORDER BY name",
        "immunizations": "SELECT * FROM immunizations ORDER BY date",
        "allergies": "SELECT * FROM allergies",
        "events": "SELECT * FROM events ORDER BY date",
        "vitals_daily": "SELECT * FROM vitals_daily ORDER BY metric, date",
        "device_samples": "SELECT * FROM device_samples ORDER BY time",
        "sources": "SELECT * FROM sources",
    }
    for name, sql in queries.items():
        cur = db.execute(sql)
        with (out / f"{name}.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow([c[0] for c in cur.description])
            w.writerows(cur)
    return len(queries)


def write_records(db):
    """One markdown file per document, with its metadata as front matter, so records can be read or grepped as files."""
    out = DATA / "records"
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir()
    keys = ("id", "kind", "date", "title", "author", "dept", "source", "org", "encounter_id", "parent_id",
            "path", "format", "source_id", "provenance")
    n = 0
    for r in rows(db, "SELECT * FROM documents ORDER BY id"):
        slug = re.sub(r"[^A-Za-z0-9]+", "-", r["title"] or "untitled").strip("-")[:60]
        p = out / f"{r['date'] or 'undated'}_{r['kind']}_{r['id']:04d}_{slug}.md"
        front = "\n".join(f"{k}: {json.dumps(r[k])}" for k in keys)
        p.write_text(f"---\n{front}\n---\n\n{r['text'] or ''}\n", encoding="utf-8")
        n += 1
    return n


def main():
    DATA.mkdir(exist_ok=True)
    tmp = DB_PATH.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.executescript(SCHEMA)

    for source, counts in ingest_fhir_exports(db, ROOT, sys.modules[__name__]).items():
        print(f"FHIR {source}: {counts}")
    print(f"C-CDA documents: {ingest_all_ccda(db)}")

    for zpath in sorted((RAW / "apple").glob("*.zip")):
        print(f"Apple Health {zpath.name}: {ingest_apple_clinical(db, zpath)}")
        vit = apple_vitals(zpath)
        db.executemany("INSERT OR REPLACE INTO vitals_daily VALUES (?,?,?,?,?,?,?)", vit["rows"])
        db.execute("INSERT OR REPLACE INTO meta VALUES ('apple_record_types', ?)", [json.dumps(vit["type_counts"])])
        print(f"  device data: {len(vit['rows'])} day-metric rows")
        cov = db.execute("SELECT min(d), max(d) FROM (SELECT date d FROM labs WHERE source='apple' "
                         "UNION ALL SELECT date FROM vitals_daily)").fetchone()
        counts = json.loads(db.execute("SELECT record_counts FROM sources WHERE key='apple'").fetchone()[0])
        counts["vitals_daily rows"] = len(vit["rows"])
        db.execute("UPDATE sources SET coverage_from=?, coverage_to=?, record_counts=? WHERE key='apple'",
                   [cov[0], cov[1], json.dumps(counts)])

    n_loose = ingest_loose_files(db)
    if n_loose:
        print(f"Loose documents: {n_loose}")
    tidepool_counts = ingest_tidepool(db, ROOT, sys.modules[__name__])
    if tidepool_counts:
        print(f"Tidepool export: {tidepool_counts}")
    for source, counts in ingest_archives(db, ROOT, sys.modules[__name__]).items():
        print(f"Local archive {source}: {counts}")
    n_journal = ingest_journal(db)
    if n_journal:
        print(f"Journal entries: {n_journal}")
    for source, counts in ingest_exports(db, ROOT, sys.modules[__name__]).items():
        print(f"Email {source}: {counts}")
    print(f"Duplicate lab rows merged: {dedupe_labs(db)}")
    build_events(db)
    db.execute("INSERT INTO documents_fts(documents_fts) VALUES ('rebuild')")
    db.execute("INSERT INTO meta VALUES ('built_at', ?)", [datetime.now().isoformat(timespec="seconds")])
    db.execute("INSERT INTO meta VALUES ('schema_version', ?)", [SCHEMA_VERSION])
    db.commit()
    db.close()
    tmp.replace(DB_PATH)

    db = sqlite3.connect(DB_PATH)
    size = build_dashboard(db)
    export_tables(db)
    n_records = write_records(db)
    import reports
    reports.build_all(db, VITAL_TYPES)
    n = lambda sql: db.execute(sql).fetchone()[0]
    print(f"\n{DB_PATH.relative_to(ROOT)}: {n('SELECT count(*) FROM labs_clean')} lab results "
          f"({n('SELECT count(DISTINCT test) FROM labs_clean')} tests), {n('SELECT count(*) FROM documents')} documents, "
          f"{n('SELECT count(*) FROM events')} timeline events")
    print(f"{DASHBOARD.name}: {size / 1e6:.1f} MB — open it in a browser")
    print(f"data/DATA_DICTIONARY.md, data/CASE_STUDY.md, data/export/*.csv, data/records/ ({n_records} files)")


if __name__ == "__main__":
    sys.exit(main())
