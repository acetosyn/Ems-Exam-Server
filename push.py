# ============================================================
# push.py — EMIS CBT PORTAL PUSH SYSTEM
#
# Supports:
#   - Broad class push: JSS1, JSS2, JSS3, SS1, SS2, SS3
#   - Exact class-arm push: JSS1A, JSS2B, SS3_GOLD, SS3B, etc.
#   - Historical JSON source year -> independent Current / Active target year
#   - Current / Active target years restricted to 2025-2040
#   - Multi-subject batch push: one, many or complete subject set
#   - Per-target active years
#   - JSS strict FIRST / SECOND / THIRD routing
#   - SS hybrid routing: GENERAL root + optional FIRST / SECOND / THIRD
#   - SS term source fallback: selected term file -> root/general file
#   - Portal subject manifests
#   - Portal active map
#   - Backward compatibility with existing flat SS pushes
# ============================================================

import os
import json
import shutil

from pathlib import Path
from datetime import datetime
from flask import Blueprint, jsonify, request, session

from modules.class_config import (
    SUPPORTED_CLASSES, CLASS_ARMS,
    normalize_class_level, normalize_class_arm,
    get_subject_target_compatibility,
)


push_bp = Blueprint("push_bp", __name__)

BASE_DIR = Path(__file__).resolve().parent

# Source:
# JSS -> static/subjects/<YEAR>/subjects-json/JSS1/FIRST/file.json
# SS  -> static/subjects/<YEAR>/subjects-json/SS1/file.json
# SS  -> static/subjects/<YEAR>/subjects-json/SS1/FIRST/file.json
SUBJECTS_JSON_ROOT = BASE_DIR / "static" / "subjects"

# Portal:
# JSS -> static/portal/<YEAR>/JSS1A/FIRST/file.json
# SS  -> static/portal/<YEAR>/SS1_GOLD/file.json
# SS  -> static/portal/<YEAR>/SS1_GOLD/FIRST/file.json
PORTAL_ROOT = BASE_DIR / "static" / "portal"
PORTAL_ROOT.mkdir(parents=True, exist_ok=True)

LATEST_YEAR_FILE = PORTAL_ROOT / "latest_year.txt"
CLASS_ACTIVE_YEARS_FILE = PORTAL_ROOT / "class_active_years.json"
CLASS_ACTIVE_TERMS_FILE = PORTAL_ROOT / "class_active_terms.json"


# ============================================================
# TERM CONFIGURATION
# ============================================================

# JSS = strict term requirement.
TERM_AWARE_CLASSES = {"JSS1", "JSS2", "JSS3"}

# SS = optional / hybrid term support.
OPTIONAL_TERM_CLASSES = {"SS1", "SS2", "SS3"}

VALID_TERMS = {"FIRST", "SECOND", "THIRD"}
TERM_ORDER = {"FIRST": 1, "SECOND": 2, "THIRD": 3}

TARGET_YEAR_MIN = 2025
TARGET_YEAR_MAX = 2040
MAX_PUSH_BATCH = 500


def valid_target_year(value):
    try: return TARGET_YEAR_MIN <= int(str(value or "").strip()) <= TARGET_YEAR_MAX
    except (TypeError, ValueError): return False


# ============================================================
# JSON HELPERS
# ============================================================

def read_json(path, default=None):
    try:
        path = Path(path)
        if path.exists(): return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"JSON READ ERROR [{path}]: {exc}")
    return default


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=4, ensure_ascii=False), encoding="utf-8")


# ============================================================
# CLASS / ARM HELPERS
# ============================================================

def normalize_class(class_cat):
    """Backward-compatible broad class helper. SS3_GOLD -> SS3, JSS1A -> JSS1, JSS2 -> JSS2."""
    return normalize_class_level(class_cat)


def normalize_target(value, fallback_level=""):
    """Resolve broad class and preserve exact target. SS3_GOLD -> (SS3, SS3_GOLD), JSS1A -> (JSS1, JSS1A)."""
    level = normalize_class_level(fallback_level or value)
    arm = normalize_class_arm(value, level)

    if not level: level = normalize_class_level(arm)
    if not arm: arm = level
    if not level or not arm: return "", ""

    return level, arm


def get_payload_target(payload):
    """Supports old broad-class payloads and new exact class-arm payloads."""
    raw_level = payload.get("class_level") or payload.get("class_category") or payload.get("class") or ""
    raw_arm = payload.get("class_arm") or payload.get("target_arm") or payload.get("target_class") or payload.get("class_category") or raw_level

    class_level, target_arm = normalize_target(raw_arm, raw_level)
    if not class_level: class_level = normalize_class_level(raw_level)
    if not target_arm: target_arm = class_level

    return class_level, target_arm


def is_valid_target(class_level, target_arm):
    if not class_level or not target_arm or class_level not in SUPPORTED_CLASSES: return False
    if target_arm == class_level: return True
    return target_arm in CLASS_ARMS.get(class_level, [])


def get_student_target_meta(student):
    """Resolve logged-in student's broad class and exact class arm."""
    class_level = normalize_class_level(student.get("class_category") or student.get("class_level") or student.get("class") or "")
    raw_arm = student.get("class_arm") or student.get("class") or student.get("class_category") or class_level
    class_arm = normalize_class_arm(raw_arm, class_level)

    if not class_level: class_level = normalize_class_level(class_arm)
    if not class_arm: class_arm = class_level

    return class_level, class_arm


# ============================================================
# TERM HELPERS
# ============================================================

def is_term_aware_class(class_level):
    """JSS only: term is compulsory."""
    return str(class_level or "").upper().strip() in TERM_AWARE_CLASSES


def is_optional_term_class(class_level):
    """SS only: term is optional; root/general mode remains supported."""
    return str(class_level or "").upper().strip() in OPTIONAL_TERM_CLASSES


def supports_term_folders(class_level):
    """True for every class that can use FIRST / SECOND / THIRD folders."""
    return is_term_aware_class(class_level) or is_optional_term_class(class_level)


def normalize_term(value):
    """Normalize term values to FIRST, SECOND or THIRD."""
    if value is None: return None

    value = str(value).strip().upper()
    if not value: return None

    aliases = {
        "1": "FIRST", "01": "FIRST", "1ST": "FIRST", "FIRST": "FIRST", "FIRST TERM": "FIRST", "1ST TERM": "FIRST", "TERM 1": "FIRST", "TERM1": "FIRST",
        "2": "SECOND", "02": "SECOND", "2ND": "SECOND", "SECOND": "SECOND", "SECOND TERM": "SECOND", "2ND TERM": "SECOND", "TERM 2": "SECOND", "TERM2": "SECOND",
        "3": "THIRD", "03": "THIRD", "3RD": "THIRD", "THIRD": "THIRD", "THIRD TERM": "THIRD", "3RD TERM": "THIRD", "TERM 3": "THIRD", "TERM3": "THIRD",
    }

    return aliases.get(value)


def term_label(term):
    labels = {"FIRST": "1st Term", "SECOND": "2nd Term", "THIRD": "3rd Term"}
    return labels.get(normalize_term(term), "—")


def get_payload_term(payload):
    return normalize_term(payload.get("term") or payload.get("exam_term") or payload.get("academic_term") or payload.get("target_term"))


# ============================================================
# GLOBAL LATEST YEAR
# ============================================================

def get_latest_year():
    if not LATEST_YEAR_FILE.exists(): return None
    year = LATEST_YEAR_FILE.read_text(encoding="utf-8").strip()
    return year if valid_target_year(year) else None


def set_latest_year(year):
    if not valid_target_year(year): return
    PORTAL_ROOT.mkdir(parents=True, exist_ok=True); LATEST_YEAR_FILE.write_text(str(year), encoding="utf-8")

def clear_latest_year():
    if LATEST_YEAR_FILE.exists(): LATEST_YEAR_FILE.unlink()


# ============================================================
# ACTIVE YEAR MAP
# ============================================================

def get_class_active_years():
    data = read_json(CLASS_ACTIVE_YEARS_FILE, default={}) or {}
    if not isinstance(data, dict): return {}
    return {str(target): str(year) for target, year in data.items() if valid_target_year(year)}


def save_class_active_years(data):
    clean = {str(target): str(year) for target, year in (data or {}).items() if valid_target_year(year)}
    write_json(CLASS_ACTIVE_YEARS_FILE, clean)

def get_active_year_for_class(class_cat):
    """Exact arm first, then broad class fallback."""
    class_level, target_arm = normalize_target(class_cat)
    if not class_level: return None

    active_years = get_class_active_years()

    if target_arm and target_arm in active_years: return active_years.get(target_arm)

    return active_years.get(class_level)


def get_active_year_for_target(target_arm, fallback_level=""):
    class_level, target_arm = normalize_target(target_arm, fallback_level)
    if not class_level: return None

    active_years = get_class_active_years()

    return active_years.get(target_arm) or active_years.get(class_level)


def set_active_year_for_class(class_cat, year):
    class_level, target_arm = normalize_target(class_cat)
    if not class_level or not target_arm or not valid_target_year(year): return
    active_years = get_class_active_years(); active_years[target_arm] = str(year)
    save_class_active_years(active_years); set_latest_year(year)

def set_active_year_for_target(target_arm, year, class_level=""):
    class_level, target_arm = normalize_target(target_arm, class_level)
    if not class_level or not target_arm or not valid_target_year(year): return
    active_years = get_class_active_years(); active_years[target_arm] = str(year)
    save_class_active_years(active_years); set_latest_year(year)

def remove_active_year_for_class(class_cat):
    class_level, target_arm = normalize_target(class_cat)
    if not class_level: return

    active_years = get_class_active_years()

    if target_arm in active_years: del active_years[target_arm]

    save_class_active_years(active_years)


# ============================================================
# ACTIVE TERM MAP — JSS STRICT + SS OPTIONAL
# ============================================================

def get_class_active_terms():
    return read_json(CLASS_ACTIVE_TERMS_FILE, default={}) or {}


def save_class_active_terms(data):
    write_json(CLASS_ACTIVE_TERMS_FILE, data or {})


def get_active_term_for_target(target_arm, fallback_level=""):
    class_level, target_arm = normalize_target(target_arm, fallback_level)

    if not class_level or not supports_term_folders(class_level): return None

    active_terms = get_class_active_terms()

    # Key presence matters.
    # SS can explicitly store null for GENERAL mode.
    # This prevents a broad-class term from overriding an exact-arm GENERAL push.
    if target_arm in active_terms: return normalize_term(active_terms.get(target_arm))
    if class_level in active_terms: return normalize_term(active_terms.get(class_level))

    return None


def set_active_term_for_target(target_arm, term, class_level=""):
    class_level, target_arm = normalize_target(target_arm, class_level)
    term = normalize_term(term)

    if not class_level or not target_arm or not supports_term_folders(class_level) or not term: return

    active_terms = get_class_active_terms()
    active_terms[target_arm] = term

    save_class_active_terms(active_terms)


def set_general_term_for_target(target_arm, class_level=""):
    """SS only: explicitly mark a target as using the root/general portal folder."""
    class_level, target_arm = normalize_target(target_arm, class_level)

    if not class_level or not target_arm or not is_optional_term_class(class_level): return

    active_terms = get_class_active_terms()
    active_terms[target_arm] = None

    save_class_active_terms(active_terms)


def remove_active_term_for_target(target_arm, class_level=""):
    class_level, target_arm = normalize_target(target_arm, class_level)
    if not target_arm: return

    active_terms = get_class_active_terms()

    if target_arm in active_terms: del active_terms[target_arm]

    save_class_active_terms(active_terms)


# ============================================================
# PUSH MANIFEST HELPERS
# ============================================================

def extract_subjects_from_manifest(path):
    data = read_json(path, default={}) or {}

    if isinstance(data, dict): return data.get("subjects", []) or []
    if isinstance(data, list): return data

    return []


def manifest_has_subjects(path):
    return bool(extract_subjects_from_manifest(path))


# ============================================================
# RECALCULATE ACTIVE YEARS / TERMS
# ============================================================

def recalculate_active_years():
    """
    Rebuild active year / term maps from portal folders.

    JSS:
        <YEAR>/<TARGET>/<TERM>/pushed_subjects.json

    SS general:
        <YEAR>/<TARGET>/pushed_subjects.json

    SS term:
        <YEAR>/<TARGET>/<TERM>/pushed_subjects.json

    For SS, an existing explicit active term is preserved when possible.
    If SS is explicitly in GENERAL mode and a flat manifest exists,
    GENERAL remains active.
    """

    target_records = {}
    previous_active_terms = get_class_active_terms()

    if not PORTAL_ROOT.exists():
        clear_latest_year()
        save_class_active_years({})
        save_class_active_terms({})
        return {}

    for year_folder in PORTAL_ROOT.iterdir():
        if not year_folder.is_dir() or not valid_target_year(year_folder.name): continue

        year = year_folder.name

        for target_folder in year_folder.iterdir():
            if not target_folder.is_dir(): continue

            class_level, target_arm = normalize_target(target_folder.name)

            if not class_level or not target_arm: continue

            flat_manifest = target_folder / "pushed_subjects.json"
            has_flat = flat_manifest.exists() and manifest_has_subjects(flat_manifest)

            available_terms = []

            if supports_term_folders(class_level):
                for term in ("FIRST", "SECOND", "THIRD"):
                    term_manifest = target_folder / term / "pushed_subjects.json"

                    if term_manifest.exists() and manifest_has_subjects(term_manifest):
                        available_terms.append(term)

            if not has_flat and not available_terms: continue

            year_num = int(year)
            previous = target_records.get(target_arm)

            if not previous or year_num > previous["year_num"]:
                target_records[target_arm] = {
                    "year": year, "year_num": year_num,
                    "class_level": class_level,
                    "terms": available_terms,
                    "has_flat": has_flat,
                }

            elif year_num == previous["year_num"]:
                previous["terms"] = list(set(previous["terms"] + available_terms))
                previous["has_flat"] = bool(previous.get("has_flat") or has_flat)

    active_years, active_terms = {}, {}

    for target_arm, record in target_records.items():
        class_level = record["class_level"]
        available_terms = record["terms"]
        has_flat = record["has_flat"]

        active_years[target_arm] = record["year"]

        if not supports_term_folders(class_level): continue

        has_exact_saved = target_arm in previous_active_terms
        has_broad_saved = class_level in previous_active_terms

        saved_term = normalize_term(
            previous_active_terms.get(target_arm)
            if has_exact_saved
            else previous_active_terms.get(class_level)
        )

        # Preserve a previously selected term if that term still exists.
        if saved_term and saved_term in available_terms:
            active_terms[target_arm] = saved_term
            continue

        # JSS cannot use GENERAL mode.
        # If the saved term disappeared, use the highest available term.
        if is_term_aware_class(class_level):
            if available_terms:
                active_terms[target_arm] = max(available_terms, key=lambda item: TERM_ORDER.get(item, 0))

            continue

        # SS supports GENERAL mode.
        if is_optional_term_class(class_level):
            saved_general = (
                has_exact_saved and previous_active_terms.get(target_arm) is None
            ) or (
                not has_exact_saved
                and has_broad_saved
                and previous_active_terms.get(class_level) is None
            )

            if has_flat and (saved_general or not saved_term):
                active_terms[target_arm] = None

            elif available_terms:
                active_terms[target_arm] = max(available_terms, key=lambda item: TERM_ORDER.get(item, 0))

            elif has_flat:
                active_terms[target_arm] = None

    save_class_active_years(active_years)
    save_class_active_terms(active_terms)

    if active_years:
        set_latest_year(str(max(int(year) for year in active_years.values())))
    else:
        clear_latest_year()

    return active_years


def recalculate_latest_year():
    active = recalculate_active_years()

    return str(max(int(year) for year in active.values())) if active else None


# ============================================================
# PORTAL / SOURCE PATH HELPERS
# ============================================================

def get_portal_target_folder(year, class_level, target_arm, term=None):
    """
    JSS:
        portal/year/JSS1A/FIRST

    SS general:
        portal/year/SS1_GOLD

    SS term:
        portal/year/SS1_GOLD/FIRST
    """

    folder = PORTAL_ROOT / str(year) / target_arm
    normalized_term = normalize_term(term)

    # JSS requires a term.
    if is_term_aware_class(class_level):
        if not normalized_term: return None

        return folder / normalized_term

    # SS term selected.
    if is_optional_term_class(class_level) and normalized_term:
        return folder / normalized_term

    # SS GENERAL.
    return folder


def get_subject_source_path(year, class_level, filename, term=None):
    """
    JSS:
        strict term path only.

    SS:
        term selected -> SS/<TERM>/file.json first
        if missing    -> SS/file.json fallback
        no term       -> SS/file.json
    """

    class_folder = SUBJECTS_JSON_ROOT / str(year) / "subjects-json" / class_level
    normalized_term = normalize_term(term)

    # JSS = strict term source.
    if is_term_aware_class(class_level):
        if not normalized_term: return None

        return class_folder / normalized_term / filename

    # SS = term-specific source first, then root/general fallback.
    if is_optional_term_class(class_level) and normalized_term:
        term_path = class_folder / normalized_term / filename

        if term_path.exists(): return term_path

        return class_folder / filename

    # SS general/root.
    return class_folder / filename


def is_term_specific_source(path, term):
    path, normalized_term = Path(path), normalize_term(term)

    return bool(normalized_term and path.parent.name.upper() == normalized_term)


# ============================================================
# PUSHED SUBJECT LIST
# ============================================================

def load_pushed_list(year, class_cat, term=None):
    class_level, target_arm = normalize_target(class_cat)

    if not year or not target_arm: return []

    folder = get_portal_target_folder(year, class_level, target_arm, term)

    if folder is None: return []

    data = read_json(folder / "pushed_subjects.json", default={}) or {}

    if isinstance(data, dict): return data.get("subjects", []) or []
    if isinstance(data, list): return data

    return []


def load_pushed_list_with_fallback(year, class_cat, class_level="", term=None):
    """
    Priority:

    1. Exact class-arm + selected term
    2. Broad class + selected term

    SS only:
    3. Exact class-arm GENERAL
    4. Broad class GENERAL

    GENERAL fallback is only used when the selected SS term has
    no pushed manifest.
    """

    resolved_level, target_arm = normalize_target(class_cat, class_level)
    normalized_term = normalize_term(term)

    # Selected term / normal lookup.
    subjects = load_pushed_list(year, target_arm, normalized_term)

    # Exact arm -> broad class fallback.
    if not subjects and target_arm != resolved_level:
        subjects = load_pushed_list(year, resolved_level, normalized_term)

    # JSS ends here.
    # SS GENERAL mode also ends here because normalized_term is None.
    if subjects or not is_optional_term_class(resolved_level) or not normalized_term:
        return subjects

    # SS selected term had no manifest.
    # Fall back to existing GENERAL/root pushed subjects.
    subjects = load_pushed_list(year, target_arm, None)

    if not subjects and target_arm != resolved_level:
        subjects = load_pushed_list(year, resolved_level, None)

    return subjects


def save_pushed_list(year, class_cat, subjects, class_level="", term=None):
    resolved_level, target_arm = normalize_target(class_cat, class_level)

    if not year or not target_arm: return

    normalized_term = normalize_term(term)

    # JSS always requires a term.
    if is_term_aware_class(resolved_level) and not normalized_term:
        raise ValueError(f"Term is required for {resolved_level}")

    folder = get_portal_target_folder(year, resolved_level, target_arm, normalized_term)

    if folder is None:
        raise ValueError(f"Unable to resolve portal folder for {target_arm}")

    folder.mkdir(parents=True, exist_ok=True)

    manifest_term = normalized_term if supports_term_folders(resolved_level) and normalized_term else None

    write_json(folder / "pushed_subjects.json", {
        "year": str(year),

        "class_level": resolved_level,
        "class_category": resolved_level,

        "class_arm": target_arm,
        "target_arm": target_arm,

        "term": manifest_term,
        "term_label": term_label(manifest_term) if manifest_term else None,

        "term_required": is_term_aware_class(resolved_level),
        "term_optional": is_optional_term_class(resolved_level),

        "subjects": subjects or [],

        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "updated_by": session.get("username", "system"),
    })


# ============================================================
# SUBJECT NAME HELPERS
# ============================================================

def subject_name_from_filename(filename):
    name = str(filename or "").replace(".json", "")

    for cls in SUPPORTED_CLASSES:
        suffix = f"_{cls.lower()}"

        if name.lower().endswith(suffix):
            name = name[:-len(suffix)]
            break

    aliases = {
        "accounts": "Financial Account",
        "account": "Financial Account",
        "financial_account": "Financial Account",
        "financial_accounting": "Financial Account",

        "english": "English Language",

        "maths": "Mathematics",
        "mathematics": "Mathematics",

        "computer": "Computer Science",
        "computer_science": "Computer Science",

        "civic": "Civic Education",

        "technical": "Technical Drawing",
        "technical_drawing": "Technical Drawing",

        "agriculture": "Agricultural Science",
        "agricultural_science": "Agricultural Science",

        "irs": "IRS",
        "irk": "IRK",
    }

    key = name.lower().strip()

    return aliases.get(key, name.replace("_", " ").title())


def get_subject_name_from_json(content, filename):
    """Prefer the actual subject stored inside the JSON."""

    if isinstance(content, dict):
        subject = str(content.get("subject", "")).strip()

        if subject: return subject

    return subject_name_from_filename(filename)


# ============================================================
# API — PUSH SUBJECTS
# ============================================================

@push_bp.route("/push", methods=["POST"])
def push_subjects():
    payload = request.get_json(silent=True) or {}
    raw_files = payload.get("files", []); class_level, target_arm = get_payload_target(payload); term = get_payload_term(payload)
    target_year = str(payload.get("target_year") or payload.get("year") or "").strip()

    # ========================================================
    # VALIDATE CURRENT / ACTIVE TARGET + BATCH
    # ========================================================
    if not isinstance(raw_files, list): return jsonify({"success": False, "error": "files must be a JSON array"}), 400
    if not raw_files: return jsonify({"success": False, "error": "No files provided"}), 400
    if len(raw_files) > MAX_PUSH_BATCH: return jsonify({"success": False, "error": f"Too many files in one push. Maximum batch size is {MAX_PUSH_BATCH}."}), 400
    if not valid_target_year(target_year): return jsonify({"success": False, "error": f"Current / Active Year must be between {TARGET_YEAR_MIN} and {TARGET_YEAR_MAX}"}), 400
    if not is_valid_target(class_level, target_arm): return jsonify({"success": False, "error": f"Invalid class target: {target_arm or class_level}"}), 400
    if is_term_aware_class(class_level) and not term: return jsonify({"success": False, "error": f"Term is required for {class_level}", "term_required": True}), 400

    # De-duplicate repeated checkbox / queue entries while preserving order.
    normalized_files, seen_entries = [], set()
    for entry in raw_files:
        value = str(entry or "").strip()
        if not value or value in seen_entries: continue
        seen_entries.add(value); normalized_files.append(value)
    raw_files = normalized_files

    if not raw_files: return jsonify({"success": False, "error": "No valid file entries were supplied"}), 400

    requested_count = len(raw_files)
    pushed_summary, failed, warnings, source_years_used = [], [], [], set()

    # ========================================================
    # PROCESS SOURCE JSON -> ACTIVE TARGET YEAR
    # ========================================================
    for entry in raw_files:
        try: source_year, filename = str(entry).split(":", 1)
        except Exception:
            failed.append({"entry": entry, "reason": "Invalid entry format. Expected SOURCE_YEAR:FILENAME"}); continue

        source_year, filename = str(source_year).strip(), os.path.basename(str(filename).strip())
        if not source_year.isdigit(): failed.append({"entry": entry, "reason": "Invalid source JSON year"}); continue
        if not filename.lower().endswith(".json"): failed.append({"entry": entry, "reason": "Only JSON files can be pushed"}); continue

        # SOURCE YEAR is only for locating the historical JSON repository file.
        src = get_subject_source_path(source_year, class_level, filename, term)
        if not src or not src.exists():
            failed.append({"entry": entry, "source_year": source_year, "target_year": target_year, "reason": f"Missing source JSON: {src}"}); print(f"Missing JSON: {src}"); continue

        try: content = json.loads(src.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            failed.append({"entry": entry, "source_year": source_year, "target_year": target_year, "reason": f"Invalid JSON: {exc}"}); print(f"Invalid JSON {src}: {exc}"); continue

        if not isinstance(content, dict): failed.append({"entry": entry, "source_year": source_year, "target_year": target_year, "reason": "JSON root must be an object"}); continue

        # ====================================================
        # TERM VERIFICATION / NORMALIZATION
        # ====================================================
        if term:
            json_term = normalize_term(content.get("term") or content.get("exam_term") or content.get("academic_term") or content.get("term_name"))
            if is_term_specific_source(src, term) and json_term and json_term != term:
                failed.append({"entry": entry, "source_year": source_year, "target_year": target_year, "reason": f"Term mismatch: JSON is {term_label(json_term)}, target is {term_label(term)}"}); continue
            content["term"], content["term_label"] = term, term_label(term)

        elif is_optional_term_class(class_level):
            for key in ("term", "term_label", "exam_term", "academic_term", "term_name"): content.pop(key, None)

        # ====================================================
        # PORTAL COPY METADATA
        # Source JSON is never modified. The copied exam belongs
        # to the selected Current / Active target year.
        # ====================================================
        content["source_year"] = source_year; content["year"] = target_year; content["active_year"] = target_year; content["result_year"] = target_year
        content["class_category"] = class_level; content["class_level"] = class_level

        # ====================================================
        # SUBJECT / TARGET COMPATIBILITY
        # ====================================================
        subject_name = get_subject_name_from_json(content, filename)
        compatibility = get_subject_target_compatibility(class_level, target_arm, subject_name)

        if not compatibility.get("allowed", True):
            failed.append({"entry": entry, "source_year": source_year, "target_year": target_year, "subject": subject_name, "class_level": class_level, "class_arm": target_arm, "reason": compatibility.get("reason") or f"{subject_name} cannot be pushed to {target_arm}."})
            print(f"[PUSH BLOCKED] {subject_name} -> {target_arm}: {compatibility.get('reason') or 'Incompatible subject target'}"); continue

        pending_warning = str(compatibility.get("warning") or "").strip()

        # ====================================================
        # DESTINATION — ALWAYS CURRENT / ACTIVE TARGET YEAR
        # ====================================================
        dst_folder = get_portal_target_folder(target_year, class_level, target_arm, term)
        if dst_folder is None:
            failed.append({"entry": entry, "source_year": source_year, "target_year": target_year, "subject": subject_name, "reason": "Unable to resolve destination"}); continue

        dst_folder.mkdir(parents=True, exist_ok=True); dst = dst_folder / filename
        try: dst.write_text(json.dumps(content, indent=4, ensure_ascii=False), encoding="utf-8")
        except Exception as exc:
            failed.append({"entry": entry, "source_year": source_year, "target_year": target_year, "subject": subject_name, "reason": f"Failed to write portal JSON: {exc}"}); continue

        # ====================================================
        # TARGET-YEAR SUBJECT MANIFEST
        # ====================================================
        pushed_list = load_pushed_list(target_year, target_arm, term)
        if subject_name not in pushed_list: pushed_list.append(subject_name)

        try: save_pushed_list(target_year, target_arm, pushed_list, class_level, term)
        except Exception as exc:
            failed.append({"entry": entry, "source_year": source_year, "target_year": target_year, "subject": subject_name, "reason": f"Failed to update subject manifest: {exc}"})
            try:
                if dst.exists(): dst.unlink()
            except Exception: pass
            continue

        if subject_name not in pushed_summary: pushed_summary.append(subject_name)
        source_years_used.add(source_year)

        if pending_warning:
            warning_item = {"entry": entry, "source_year": source_year, "year": target_year, "target_year": target_year, "subject": subject_name, "class_level": class_level, "class_arm": target_arm, "term": term, "message": pending_warning}
            duplicate_warning = any(item.get("source_year") == source_year and item.get("target_year") == target_year and item.get("subject") == subject_name and item.get("class_arm") == target_arm and item.get("term") == term and item.get("message") == pending_warning for item in warnings)
            if not duplicate_warning: warnings.append(warning_item)

    # ========================================================
    # ACTIVE YEAR / ACTIVE TERM
    # ========================================================
    success = bool(pushed_summary); active_year = target_year if success else None
    if success:
        set_active_year_for_target(target_arm, target_year, class_level)
        if term and supports_term_folders(class_level): set_active_term_for_target(target_arm, term, class_level)
        elif is_optional_term_class(class_level): set_general_term_for_target(target_arm, class_level)

    return jsonify({
        "success": success, "source_years": sorted(source_years_used, key=lambda value: int(value)), "target_year": target_year, "active_year": active_year,
        "class": class_level, "class_level": class_level, "class_category": class_level, "class_arm": target_arm, "target_arm": target_arm,
        "term": term, "term_label": term_label(term) if term else None, "term_required": is_term_aware_class(class_level), "term_optional": is_optional_term_class(class_level),
        "batch": True, "requested_count": requested_count, "processed_count": len(pushed_summary) + len(failed),
        "subjects_pushed": pushed_summary, "subject_count": len(pushed_summary), "failed": failed, "failed_count": len(failed), "warnings": warnings, "warning_count": len(warnings),
        "active_term": term if success and term and supports_term_folders(class_level) else None, "latest_year": get_latest_year(),
        "class_active_years": get_class_active_years(), "class_active_terms": get_class_active_terms(),
    })

# ============================================================
# API — CLEAR PORTAL
# ============================================================

@push_bp.route("/clear", methods=["POST"])
def clear_portal():
    payload = request.get_json(silent=True) or {}

    year = str(payload.get("year", "")).strip()

    raw_target = (
        payload.get("class_arm")
        or payload.get("target_arm")
        or payload.get("class_category")
        or payload.get("class_level")
        or ""
    )

    raw_target = str(raw_target).upper().strip()
    term = get_payload_term(payload)

    if not year:
        return jsonify({
            "success": False,
            "error": "Year is required",
        }), 400

    # --------------------------------------------------------
    # CLEAR ALL YEARS + ALL TARGETS
    # --------------------------------------------------------

    if year.upper() == "ALL" and raw_target == "ALL":
        if PORTAL_ROOT.exists(): shutil.rmtree(PORTAL_ROOT)

        PORTAL_ROOT.mkdir(parents=True, exist_ok=True)

        clear_latest_year()
        save_class_active_years({})
        save_class_active_terms({})

        return jsonify({
            "success": True,
            "cleared": "ALL",
            "latest_year": None,
            "class_active_years": {},
            "class_active_terms": {},
        })

    # --------------------------------------------------------
    # CLEAR ONE YEAR FOR ALL TARGETS
    # --------------------------------------------------------

    if raw_target == "ALL":
        year_folder = PORTAL_ROOT / year

        if year_folder.exists(): shutil.rmtree(year_folder)

        active = recalculate_active_years()

        return jsonify({
            "success": True,
            "cleared": f"{year}-ALL",

            "latest_year": get_latest_year(),
            "class_active_years": active,
            "class_active_terms": get_class_active_terms(),
        })

    # --------------------------------------------------------
    # RESOLVE TARGET
    # --------------------------------------------------------

    class_level, target_arm = get_payload_target(payload)

    if not is_valid_target(class_level, target_arm):
        return jsonify({
            "success": False,
            "error": f"Invalid class target: {target_arm or class_level}",
        }), 400

    # --------------------------------------------------------
    # JSS — SELECTED TERM REQUIRED
    # --------------------------------------------------------

    if is_term_aware_class(class_level):
        if not term:
            return jsonify({
                "success": False,
                "error": f"Term is required when clearing {class_level}",
                "term_required": True,
            }), 400

        target_folder = PORTAL_ROOT / year / target_arm / term

        if target_folder.exists(): shutil.rmtree(target_folder)

        active = recalculate_active_years()

        return jsonify({
            "success": True,
            "cleared": f"{year}-{target_arm}-{term}",

            "class": class_level,
            "class_level": class_level,
            "class_category": class_level,

            "class_arm": target_arm,
            "target_arm": target_arm,

            "term": term,
            "term_label": term_label(term),

            "latest_year": get_latest_year(),
            "class_active_years": active,
            "class_active_terms": get_class_active_terms(),
        })

    # --------------------------------------------------------
    # SS — TERM SUPPLIED = CLEAR ONLY THAT TERM
    # --------------------------------------------------------

    if is_optional_term_class(class_level) and term:
        target_folder = PORTAL_ROOT / year / target_arm / term

        if target_folder.exists(): shutil.rmtree(target_folder)

        active = recalculate_active_years()

        return jsonify({
            "success": True,
            "cleared": f"{year}-{target_arm}-{term}",

            "class": class_level,
            "class_level": class_level,
            "class_category": class_level,

            "class_arm": target_arm,
            "target_arm": target_arm,

            "term": term,
            "term_label": term_label(term),

            "latest_year": get_latest_year(),
            "class_active_years": active,
            "class_active_terms": get_class_active_terms(),
        })

    # --------------------------------------------------------
    # SS — NO TERM = EXISTING / LEGACY CLEAR BEHAVIOUR
    #
    # Clears the entire target including any term folders.
    # --------------------------------------------------------

    target_folder = PORTAL_ROOT / year / target_arm

    if target_folder.exists(): shutil.rmtree(target_folder)

    active = recalculate_active_years()

    return jsonify({
        "success": True,
        "cleared": f"{year}-{target_arm}",

        "class": class_level,
        "class_level": class_level,
        "class_category": class_level,

        "class_arm": target_arm,
        "target_arm": target_arm,

        "term": None,
        "term_label": None,

        "latest_year": get_latest_year(),
        "class_active_years": active,
        "class_active_terms": get_class_active_terms(),
    })


# ============================================================
# STUDENT FETCH — GET PUSHED SUBJECTS
# ============================================================

@push_bp.route("/get_pushed_subjects", methods=["GET"])
def student_get_pushed():
    student = session.get("student")

    if not student:
        return jsonify({"subjects": []})

    class_level, class_arm = get_student_target_meta(student)

    if not class_level:
        return jsonify({"subjects": []})

    # --------------------------------------------------------
    # ACTIVE YEAR
    # --------------------------------------------------------

    active_year = get_active_year_for_target(class_arm, class_level)

    if not active_year:
        active_years = recalculate_active_years()

        active_year = (
            active_years.get(class_arm)
            or active_years.get(class_level)
        )

    if not active_year:
        return jsonify({
            "class": class_level,
            "class_level": class_level,
            "class_category": class_level,

            "class_arm": class_arm,

            "active_year": None,
            "active_term": None,

            "term": None,
            "term_label": None,

            "subjects": [],
        })

    # --------------------------------------------------------
    # ACTIVE TERM
    # --------------------------------------------------------

    requested_term = normalize_term(request.args.get("term"))
    active_term = None

    # JSS = term compulsory.
    if is_term_aware_class(class_level):
        active_term = (
            requested_term
            or get_active_term_for_target(class_arm, class_level)
        )

        if not active_term:
            recalculate_active_years()
            active_term = get_active_term_for_target(class_arm, class_level)

        if not active_term:
            return jsonify({
                "class": class_level,
                "class_level": class_level,
                "class_category": class_level,

                "class_arm": class_arm,

                "active_year": active_year,

                "active_term": None,
                "term": None,
                "term_label": None,

                "subjects": [],
            })

    # SS = selected active term OR GENERAL.
    elif is_optional_term_class(class_level):
        active_term = (
            requested_term
            if requested_term
            else get_active_term_for_target(class_arm, class_level)
        )

    # --------------------------------------------------------
    # LOAD ASSIGNED SUBJECTS
    # --------------------------------------------------------

    pushed_list = load_pushed_list_with_fallback(
        active_year,
        class_arm,
        class_level,
        active_term,
    )

    subjects = [{
        "subject": subject,
        "year": active_year,

        "class": class_arm,
        "class_level": class_level,
        "class_arm": class_arm,

        "term": active_term,
        "term_label": term_label(active_term) if active_term else None,
    } for subject in pushed_list]

    return jsonify({
        "class": class_level,
        "class_level": class_level,
        "class_category": class_level,

        "class_arm": class_arm,

        "active_year": active_year,

        "active_term": active_term,
        "term": active_term,

        "term_label": term_label(active_term) if active_term else None,

        "term_required": is_term_aware_class(class_level),
        "term_optional": is_optional_term_class(class_level),

        "subjects": subjects,
    })


# ============================================================
# API — LATEST ACTIVE YEAR
# ============================================================

@push_bp.route("/push_latest_year", methods=["GET"])
def push_latest_year():
    active_years = get_class_active_years()
    if not active_years: active_years = recalculate_active_years()
    latest = get_latest_year() or (str(max(int(year) for year in active_years.values())) if active_years else None)
    return jsonify({"year": latest, "latest_year": latest, "class_active_years": active_years, "class_active_terms": get_class_active_terms()})


# ============================================================
# API — ACTIVE YEAR FOR CLASS / ARM
#
# Examples:
# /push_active_year?class=SS3_GOLD
# /push_active_year?class=JSS1A
# ============================================================

@push_bp.route("/push_active_year", methods=["GET"])
def push_active_year():
    raw_class = request.args.get("class", "")
    class_level, target_arm = normalize_target(raw_class)

    if not class_level:
        return jsonify({"error": "Invalid class"}), 400

    active_year = get_active_year_for_target(
        target_arm,
        class_level,
    )

    if not active_year:
        active = recalculate_active_years()

        active_year = (
            active.get(target_arm)
            or active.get(class_level)
        )

    active_term = (
        get_active_term_for_target(target_arm, class_level)
        if supports_term_folders(class_level)
        else None
    )

    return jsonify({
        "class": class_level,
        "class_level": class_level,
        "class_category": class_level,

        "class_arm": target_arm,
        "target_arm": target_arm,

        "year": active_year,
        "active_year": active_year,

        "term": active_term,
        "active_term": active_term,

        "term_label": term_label(active_term) if active_term else None,

        "term_required": is_term_aware_class(class_level),
        "term_optional": is_optional_term_class(class_level),
    })


# ============================================================
# API — PORTAL ACTIVE MAP
# ============================================================

@push_bp.route("/portal_active_map", methods=["GET"])
def portal_active_map():
    active_years = get_class_active_years()

    if not active_years:
        active_years = recalculate_active_years()

    active_terms = get_class_active_terms()
    details = {}

    for target_arm, year in active_years.items():
        class_level, resolved_arm = normalize_target(target_arm)

        if not class_level:
            continue

        active_term = (
            get_active_term_for_target(resolved_arm, class_level)
            if supports_term_folders(class_level)
            else None
        )

        subjects = load_pushed_list_with_fallback(
            year,
            resolved_arm,
            class_level,
            active_term,
        )

        details[resolved_arm] = {
            "year": year,

            "class_level": class_level,
            "class_category": class_level,

            "class_arm": resolved_arm,
            "target_arm": resolved_arm,

            "term": active_term,
            "active_term": active_term,

            "term_label": term_label(active_term) if active_term else None,

            "term_aware": supports_term_folders(class_level),
            "term_required": is_term_aware_class(class_level),
            "term_optional": is_optional_term_class(class_level),

            "subjects": subjects,
            "subject_count": len(subjects),
        }

    return jsonify({
        "success": True,

        "latest_year": get_latest_year(),

        "class_active_years": active_years,
        "class_active_terms": active_terms,

        "active_map": details,
    })


# ============================================================
# DETECT AVAILABLE SUBJECT YEARS
# ============================================================

def get_available_subject_years():
    years = []

    if not SUBJECTS_JSON_ROOT.exists():
        return years

    for year_dir in SUBJECTS_JSON_ROOT.iterdir():
        if not year_dir.is_dir():
            continue

        year = year_dir.name

        if not year.isdigit():
            continue

        subjects_json_dir = year_dir / "subjects-json"

        if not subjects_json_dir.exists():
            continue

        found_json = False

        for _, _, files in os.walk(subjects_json_dir):
            if any(filename.lower().endswith(".json") for filename in files):
                found_json = True
                break

        if found_json:
            years.append(int(year))

    return sorted(years)


# ============================================================
# API — AVAILABLE YEARS
# ============================================================

@push_bp.route("/available-years", methods=["GET"])
def available_waec_years():
    return jsonify({
        "years": get_available_subject_years(),
    })


# ============================================================
# API — AVAILABLE TERMS FOR YEAR + CLASS
#
# Examples:
#
# /available-terms?year=2026&class=JSS1
# /available-terms?year=2026&class=SS1
#
# JSS:
# term_required = true
#
# SS:
# term_optional = true
# general_available indicates whether SS root JSONs exist.
# ============================================================

@push_bp.route("/available-terms", methods=["GET"])
def available_terms():
    year = str(request.args.get("year", "")).strip()
    raw_class = str(request.args.get("class", "")).strip()

    class_level = normalize_class_level(raw_class)

    if not year or not year.isdigit():
        return jsonify({
            "success": False,
            "error": "Invalid year",
            "terms": [],
        }), 400

    if not class_level:
        return jsonify({
            "success": False,
            "error": "Invalid class",
            "terms": [],
        }), 400

    class_folder = (
        SUBJECTS_JSON_ROOT
        / year
        / "subjects-json"
        / class_level
    )

    # --------------------------------------------------------
    # GENERAL / ROOT SS AVAILABILITY
    # --------------------------------------------------------

    general_available = False

    if class_folder.exists() and class_folder.is_dir():
        try:
            general_available = any(
                file.is_file()
                and file.suffix.lower() == ".json"
                and file.name.lower() != "pushed_subjects.json"
                for file in class_folder.iterdir()
            )

        except OSError:
            general_available = False

    # --------------------------------------------------------
    # FIRST / SECOND / THIRD AVAILABILITY
    # --------------------------------------------------------

    available = []

    if supports_term_folders(class_level):
        for term in ("FIRST", "SECOND", "THIRD"):
            term_folder = class_folder / term

            if not term_folder.exists() or not term_folder.is_dir():
                continue

            try:
                has_json = any(
                    file.is_file()
                    and file.suffix.lower() == ".json"
                    and file.name.lower() != "pushed_subjects.json"
                    for file in term_folder.iterdir()
                )

            except OSError:
                has_json = False

            if has_json:
                available.append({
                    "term": term,
                    "label": term_label(term),
                })

    return jsonify({
        "success": True,

        "year": year,

        "class_level": class_level,
        "class_category": class_level,

        "term_aware": supports_term_folders(class_level),
        "term_required": is_term_aware_class(class_level),
        "term_optional": is_optional_term_class(class_level),

        "general_available": (
            general_available
            if is_optional_term_class(class_level)
            else False
        ),

        "terms": available,
    })


# ============================================================
# API — ACTIVE TERM FOR CLASS / ARM
#
# Examples:
#
# /push_active_term?class=JSS1A
# /push_active_term?class=SS1_GOLD
#
# For SS, active_term = null means GENERAL mode.
# ============================================================

@push_bp.route("/push_active_term", methods=["GET"])
def push_active_term():
    raw_class = request.args.get("class", "")
    class_level, target_arm = normalize_target(raw_class)

    if not class_level:
        return jsonify({
            "error": "Invalid class",
        }), 400

    if not supports_term_folders(class_level):
        return jsonify({
            "class": class_level,
            "class_level": class_level,
            "class_category": class_level,

            "class_arm": target_arm,
            "target_arm": target_arm,

            "term_aware": False,
            "term_required": False,
            "term_optional": False,

            "term": None,
            "active_term": None,
            "term_label": None,
        })

    active_terms = get_class_active_terms()

    # Key presence is important because SS GENERAL is intentionally
    # represented as:
    #
    # "SS1_GOLD": null
    #
    # so null should not be mistaken for "not configured".
    exact_known = target_arm in active_terms
    broad_known = class_level in active_terms

    if not exact_known and not broad_known:
        recalculate_active_years()

    active_term = get_active_term_for_target(
        target_arm,
        class_level,
    )

    return jsonify({
        "class": class_level,
        "class_level": class_level,
        "class_category": class_level,

        "class_arm": target_arm,
        "target_arm": target_arm,

        "term_aware": True,
        "term_required": is_term_aware_class(class_level),
        "term_optional": is_optional_term_class(class_level),

        "term": active_term,
        "active_term": active_term,

        "term_label": term_label(active_term) if active_term else None,
    })