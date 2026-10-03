"""Configurable capture templates. These are entry fields, not diagnostic rules."""

import re
from datetime import date
from fastapi import HTTPException


def field(key, label, type="number", **kwargs):
    return {"key": key, "label": label, "type": type, "required": False, **kwargs}


MEASUREMENTS = [
    field("weight_kg", "Weight (kg)", min=0.1, max=400),
    field("height_cm", "Height / length (cm)", min=10, max=250),
    field("muac_cm", "MUAC (cm)", min=5, max=60),
]
DEFAULT_FORMS = {
    "growth": MEASUREMENTS
    + [
        field("bilateral_oedema", "Bilateral oedema recorded by clinician", "boolean"),
        field("feeding_advice", "Feeding advice", "text"),
    ],
    "iycf": [
        field("early_initiation", "Early initiation recorded", "boolean"),
        field("exclusive_breastfeeding", "Exclusive breastfeeding recorded", "boolean"),
        field("complementary_feeding", "Complementary feeding recorded", "boolean"),
        field("counselling_topic", "Counselling topic", "text"),
    ],
    "vitamin-a": [
        field("vitamin_a_given", "Vitamin A provided", "boolean"),
        field("vitamin_a_service_date", "Service date", "date"),
        field("service_notes", "Service / eligibility notes", "text"),
    ],
    "maternal": MEASUREMENTS[:2]
    + [
        field("haemoglobin_g_dl", "Haemoglobin (g/dL)", min=1, max=25),
        field("gestational_weeks", "Gestational age (weeks)", min=0, max=45),
        field("ifa_provided", "IFA provided", "boolean"),
        field("dietary_counselling", "Dietary counselling provided", "boolean"),
    ],
    "gifts": [
        field("school_id", "School", "school"),
        field("ifa_provided", "IFA provided", "boolean"),
        field("doses_recorded", "Number of doses recorded", min=0, max=365),
        field("nutrition_education", "Nutrition education provided", "boolean"),
    ],
    "rehabilitation": MEASUREMENTS
    + [
        field("treatment_notes", "Programme treatment notes", "text"),
        field("referral_destination", "Referral destination", "text"),
    ],
    "ncd": MEASUREMENTS[:2]
    + [
        field("systolic_mmhg", "Systolic BP (mmHg)", min=40, max=300),
        field("diastolic_mmhg", "Diastolic BP (mmHg)", min=20, max=200),
        field("dietary_plan", "Dietary plan", "text"),
    ],
}


def validate_schema(fields):
    seen = set()
    for f in fields:
        if set(f) - {"key", "label", "type", "required", "min", "max", "options"}:
            raise HTTPException(422, "Unknown programme field property")
        key = f.get("key", "")
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,59}", key) or key in seen:
            raise HTTPException(422, "Field keys must be unique lowercase identifiers")
        seen.add(key)
        if (
            not isinstance(f.get("label"), str)
            or not 1 <= len(f["label"]) <= 120
            or f.get("type") not in {"number", "text", "date", "boolean", "select", "school"}
        ):
            raise HTTPException(422, "Choose a supported field type and label")
        if not isinstance(f.get("required", False), bool):
            raise HTTPException(422, "Required must be a boolean")
        for k in ["min", "max"]:
            if k in f and (
                f["type"] != "number"
                or isinstance(f[k], bool)
                or not isinstance(f[k], (int, float))
            ):
                raise HTTPException(422, "Numeric limits must be numbers")
        if "min" in f and "max" in f and f["min"] > f["max"]:
            raise HTTPException(422, "Minimum exceeds maximum")
        if f["type"] == "select" and (
            not isinstance(f.get("options"), list)
            or not 1 <= len(f["options"]) <= 50
            or any(not isinstance(v, str) or len(v) > 120 for v in f["options"])
        ):
            raise HTTPException(422, "Select fields need 1–50 text options")


def validate_capture(programme, measurements):
    for f in programme.fields or []:
        value = measurements.get(f["key"])
        if value is None or value == "":
            if f.get("required"):
                raise HTTPException(422, f"{f['label']} is required")
            continue
        t = f["type"]
        valid = True
        if t == "number":
            valid = (
                not isinstance(value, bool)
                and isinstance(value, (float, int))
                and ("min" not in f or value >= f["min"])
                and ("max" not in f or value <= f["max"])
            )
        elif t == "boolean":
            valid = isinstance(value, bool)
        elif t == "select":
            valid = value in f["options"]
        elif t == "date":
            try:
                date.fromisoformat(value)
            except (TypeError, ValueError):
                valid = False
        elif t in {"text", "school"}:
            valid = isinstance(value, str) and len(value) <= 2000
        if not valid:
            raise HTTPException(422, f"Invalid entry for {f['label']}")
