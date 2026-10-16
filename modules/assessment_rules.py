# MODULE: Assessment Rules — central EMIS assessment-scheme resolver for CA/Test and future report activation
# NOTE: Lower-school/Tahfeez rules remain explicitly pending until the school approves their exact CA/Exam structure.

import json
from copy import deepcopy
from pathlib import Path

from modules.school_structure import school_section_for_class, normalize_school_class, ASSESSMENT_SCHEMES


BASE_DIR = Path(__file__).resolve().parent.parent
RULES_FILE = BASE_DIR / "static" / "data" / "academic" / "assessment_rules.json"


def _field(key, label, maximum):
    return {"key": str(key or "").strip().upper(), "label": str(label or key or "").strip(), "max": float(maximum)}


DEFAULT_RULES = {
    "JSS": {
        "key": "JSS", "label": "Junior Secondary", "status": "active", "school_section": "JUNIOR_SECONDARY",
        "ca_max": 60, "exam_max": 40, "total_max": 100,
        "fields": [_field("CA1", "CA1", 10), _field("CA2", "CA2", 10), _field("TEST1", "TEST1", 20), _field("TEST2", "TEST2", 20)],
        "source": "system_default",
    },
    "SS": {
        "key": "SS", "label": "Senior Secondary", "status": "active", "school_section": "SENIOR_SECONDARY",
        "ca_max": 30, "exam_max": 70, "total_max": 100,
        "fields": [_field("ASS1", "1ST ASS.", 5), _field("ASS2", "2ND ASS.", 5), _field("TEST", "TEST", 20)],
        "source": "system_default",
    },
    "EARLY_YEARS": {
        "key": "EARLY_YEARS", "label": "Early Years / Nursery", "status": "pending_school_scheme", "school_section": "EARLY_YEARS",
        "ca_max": None, "exam_max": None, "total_max": 100, "fields": [], "source": "pending_school_confirmation",
    },
    "PRIMARY": {
        "key": "PRIMARY", "label": "Primary School", "status": "pending_school_scheme", "school_section": "PRIMARY",
        "ca_max": None, "exam_max": None, "total_max": 100, "fields": [], "source": "pending_school_confirmation",
    },
    "TAHFEEZ": {
        "key": "TAHFEEZ", "label": "Tahfeez", "status": "pending_school_scheme", "school_section": "TAHFEEZ",
        "ca_max": None, "exam_max": None, "total_max": 100, "fields": [], "source": "pending_school_confirmation",
    },
    "ISLAMIYAH": {
        "key": "ISLAMIYAH", "label": "Islamiyah School", "status": "active_dedicated_module", "school_section": "ISLAMIYAH",
        "ca_max": 30, "exam_max": 70, "total_max": 100,
        "fields": [_field("CA", "CA", 30), _field("EXAM", "Exam", 70)], "source": "islamiyah_module",
        "dedicated_module": True,
    },
}


def assessment_key_for_class(class_level):
    level = normalize_school_class(class_level)
    if level.startswith("JSS"): return "JSS"
    if level.startswith("SS"): return "SS"
    section = school_section_for_class(level)
    if section in {"EARLY_YEARS", "PRIMARY", "TAHFEEZ", "ISLAMIYAH"}: return section
    return ""


def _normalize_fields(value):
    output = []
    if isinstance(value, dict):
        value = [{"key": key, "label": key, "max": maximum} for key, maximum in value.items()]
    for item in value or []:
        if not isinstance(item, dict): continue
        key = str(item.get("key") or item.get("name") or "").strip().upper()
        label = str(item.get("label") or key).strip()
        try: maximum = float(item.get("max"))
        except (TypeError, ValueError): continue
        if not key or maximum <= 0: continue
        output.append(_field(key, label, maximum))
    return output


def _load_overrides():
    if not RULES_FILE.exists(): return {}
    try:
        payload = json.loads(RULES_FILE.read_text(encoding="utf-8"))
        return payload.get("schemes", payload) if isinstance(payload, dict) else {}
    except Exception as error:
        print("[ASSESSMENT RULES] Unable to read assessment_rules.json:", error)
        return {}


def get_assessment_rule(class_level):
    key = assessment_key_for_class(class_level)
    if not key: return {"key": "", "label": "Unknown", "status": "unsupported", "fields": [], "ca_max": None, "exam_max": None, "total_max": 100, "entry_enabled": False, "message": "Unsupported class."}

    rule = deepcopy(DEFAULT_RULES[key])
    override = _load_overrides().get(key)
    if isinstance(override, dict):
        for field in ["label", "status", "ca_max", "exam_max", "total_max", "source"]:
            if field in override: rule[field] = override[field]
        if "fields" in override: rule["fields"] = _normalize_fields(override.get("fields"))

    rule["class_level"] = normalize_school_class(class_level)
    rule["fields"] = _normalize_fields(rule.get("fields"))
    if rule.get("ca_max") is None and rule["fields"]: rule["ca_max"] = round(sum(float(item["max"]) for item in rule["fields"]), 2)

    active = str(rule.get("status") or "").lower() in {"active", "configured"}
    rule["entry_enabled"] = bool(active and rule.get("fields") and not rule.get("dedicated_module"))
    if rule.get("dedicated_module"):
        rule["message"] = "Islamiyah uses its dedicated CA /30 + Exam /70 workspace."
    elif rule["entry_enabled"]:
        rule["message"] = "Assessment entry is active."
    else:
        rule["message"] = f"{rule.get('label') or 'This class'} roster and subjects are active, but the approved CA/Exam score structure has not yet been configured."
    return rule


def get_assessment_fields(class_level):
    return deepcopy(get_assessment_rule(class_level).get("fields") or [])


def assessment_fields_dict(class_level):
    return {item["key"]: item["max"] for item in get_assessment_fields(class_level)}


def assessment_entry_enabled(class_level):
    return bool(get_assessment_rule(class_level).get("entry_enabled"))


def get_all_assessment_rules():
    return {key: get_assessment_rule(next((level for level in ["JSS1", "SS1", "STARTER", "PRIMARY1", "TAHFEEZ1", "ISLAMIYAH1"] if assessment_key_for_class(level) == key), key)) for key in DEFAULT_RULES}
