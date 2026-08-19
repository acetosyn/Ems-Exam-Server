# ============================================================
# push.py — EMIS CBT PORTAL PUSH SYSTEM
#
# Supports:
#   - Broad class push: JSS1, JSS2, JSS3, SS1, SS2, SS3
#   - Exact class-arm push: JSS1A, JSS2B, SS3_GOLD, SS3B, etc.
#   - Per-target active years
#   - Per-target active terms for JSS only
#   - JSS 1st / 2nd / 3rd Term routing
#   - Non-term-aware SS routing
#   - Portal subject manifests
#   - Portal active map
#   - Backward compatibility with existing year/class logic
# ============================================================

import os
import json
import shutil

from pathlib import Path
from datetime import datetime
from flask import Blueprint, jsonify, request, session

from modules.class_config import (
    SUPPORTED_CLASSES,
    CLASS_ARMS,
    normalize_class_level,
    normalize_class_arm,
)


push_bp = Blueprint("push_bp", __name__)

BASE_DIR = Path(__file__).resolve().parent

# Source:
# JSS -> static/subjects/<YEAR>/subjects-json/JSS1/FIRST/file.json
# SS  -> static/subjects/<YEAR>/subjects-json/SS1/file.json
SUBJECTS_JSON_ROOT = BASE_DIR / "static" / "subjects"

# Portal:
# JSS -> static/portal/<YEAR>/JSS1A/FIRST/file.json
# SS  -> static/portal/<YEAR>/SS1_GOLD/file.json
PORTAL_ROOT = BASE_DIR / "static" / "portal"
PORTAL_ROOT.mkdir(parents=True, exist_ok=True)

LATEST_YEAR_FILE = PORTAL_ROOT / "latest_year.txt"
CLASS_ACTIVE_YEARS_FILE = PORTAL_ROOT / "class_active_years.json"
CLASS_ACTIVE_TERMS_FILE = PORTAL_ROOT / "class_active_terms.json"


# ============================================================
# TERM CONFIGURATION
# ============================================================

TERM_AWARE_CLASSES = {"JSS1", "JSS2", "JSS3"}
VALID_TERMS = {"FIRST", "SECOND", "THIRD"}
TERM_ORDER = {"FIRST": 1, "SECOND": 2, "THIRD": 3}


# ============================================================
# JSON HELPERS
# ============================================================

def read_json(path, default=None):
    try:
        path = Path(path)

        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))

    except Exception as exc:
        print(f"JSON READ ERROR [{path}]: {exc}")

    return default


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=4, ensure_ascii=False),
        encoding="utf-8"
    )


# ============================================================
# CLASS / ARM HELPERS
# ============================================================

def normalize_class(class_cat):
    """
    Backward-compatible broad class helper.

    SS3_GOLD -> SS3
    JSS1A    -> JSS1
    JSS2     -> JSS2
    """
    return normalize_class_level(class_cat)


def normalize_target(value, fallback_level=""):
    """
    Resolve broad class and preserve exact target.

    SS3_GOLD -> ("SS3", "SS3_GOLD")
    SS3B     -> ("SS3", "SS3B")
    JSS1A    -> ("JSS1", "JSS1A")
    JSS1     -> ("JSS1", "JSS1")
    """
    level = normalize_class_level(fallback_level or value)
    arm = normalize_class_arm(value, level)

    if not level:
        level = normalize_class_level(arm)

    if not arm:
        arm = level

    if not level or not arm:
        return "", ""

    return level, arm


def get_payload_target(payload):
    """
    Supports old and new payloads.

    Old:
        {"class_category": "SS3"}

    New:
        {"class_level": "SS3", "class_arm": "SS3_GOLD"}
    """
    raw_level = (
        payload.get("class_level")
        or payload.get("class_category")
        or payload.get("class")
        or ""
    )

    raw_arm = (
        payload.get("class_arm")
        or payload.get("target_arm")
        or payload.get("target_class")
        or payload.get("class_category")
        or raw_level
    )

    class_level, target_arm = normalize_target(raw_arm, raw_level)

    if not class_level:
        class_level = normalize_class_level(raw_level)

    if not target_arm:
        target_arm = class_level

    return class_level, target_arm


def is_valid_target(class_level, target_arm):
    if not class_level or not target_arm:
        return False

    if class_level not in SUPPORTED_CLASSES:
        return False

    if target_arm == class_level:
        return True

    return target_arm in CLASS_ARMS.get(class_level, [])


def get_student_target_meta(student):
    """Resolve logged-in student's broad class and exact class arm."""

    class_level = normalize_class_level(
        student.get("class_category")
        or student.get("class_level")
        or student.get("class")
        or ""
    )

    raw_arm = (
        student.get("class_arm")
        or student.get("class")
        or student.get("class_category")
        or class_level
    )

    class_arm = normalize_class_arm(raw_arm, class_level)

    if not class_level:
        class_level = normalize_class_level(class_arm)

    if not class_arm:
        class_arm = class_level

    return class_level, class_arm


# ============================================================
# TERM HELPERS
# ============================================================

def is_term_aware_class(class_level):
    return str(class_level or "").upper().strip() in TERM_AWARE_CLASSES


def normalize_term(value):
    """Normalize term values to FIRST, SECOND or THIRD."""

    if value is None:
        return None

    value = str(value).strip().upper()

    if not value:
        return None

    aliases = {
        "1": "FIRST",
        "01": "FIRST",
        "1ST": "FIRST",
        "FIRST": "FIRST",
        "FIRST TERM": "FIRST",
        "1ST TERM": "FIRST",
        "TERM 1": "FIRST",
        "TERM1": "FIRST",

        "2": "SECOND",
        "02": "SECOND",
        "2ND": "SECOND",
        "SECOND": "SECOND",
        "SECOND TERM": "SECOND",
        "2ND TERM": "SECOND",
        "TERM 2": "SECOND",
        "TERM2": "SECOND",

        "3": "THIRD",
        "03": "THIRD",
        "3RD": "THIRD",
        "THIRD": "THIRD",
        "THIRD TERM": "THIRD",
        "3RD TERM": "THIRD",
        "TERM 3": "THIRD",
        "TERM3": "THIRD",
    }

    return aliases.get(value)


def term_label(term):
    term = normalize_term(term)

    labels = {
        "FIRST": "1st Term",
        "SECOND": "2nd Term",
        "THIRD": "3rd Term",
    }

    return labels.get(term, "—")


def get_payload_term(payload):
    return normalize_term(
        payload.get("term")
        or payload.get("exam_term")
        or payload.get("academic_term")
        or payload.get("target_term")
    )


# ============================================================
# GLOBAL LATEST YEAR
# ============================================================

def get_latest_year():
    if LATEST_YEAR_FILE.exists():
        year = LATEST_YEAR_FILE.read_text(encoding="utf-8").strip()
        return year or None

    return None


def set_latest_year(year):
    if not year:
        return

    PORTAL_ROOT.mkdir(parents=True, exist_ok=True)
    LATEST_YEAR_FILE.write_text(str(year), encoding="utf-8")


def clear_latest_year():
    if LATEST_YEAR_FILE.exists():
        LATEST_YEAR_FILE.unlink()


# ============================================================
# ACTIVE YEAR MAP
# ============================================================

def get_class_active_years():
    return read_json(CLASS_ACTIVE_YEARS_FILE, default={}) or {}


def save_class_active_years(data):
    write_json(CLASS_ACTIVE_YEARS_FILE, data or {})


def get_active_year_for_class(class_cat):
    """
    Backward-compatible public helper.

    SS3_GOLD -> SS3_GOLD first, then SS3
    JSS1A    -> JSS1A first, then JSS1
    """
    class_level, target_arm = normalize_target(class_cat)

    if not class_level:
        return None

    active_years = get_class_active_years()

    if target_arm and target_arm in active_years:
        return active_years.get(target_arm)

    return active_years.get(class_level)


def get_active_year_for_target(target_arm, fallback_level=""):
    class_level, target_arm = normalize_target(target_arm, fallback_level)

    if not class_level:
        return None

    active_years = get_class_active_years()
    return active_years.get(target_arm) or active_years.get(class_level)


def set_active_year_for_class(class_cat, year):
    class_level, target_arm = normalize_target(class_cat)

    if not class_level or not target_arm:
        return

    active_years = get_class_active_years()
    active_years[target_arm] = str(year)

    save_class_active_years(active_years)
    set_latest_year(year)


def set_active_year_for_target(target_arm, year, class_level=""):
    class_level, target_arm = normalize_target(target_arm, class_level)

    if not class_level or not target_arm:
        return

    active_years = get_class_active_years()
    active_years[target_arm] = str(year)

    save_class_active_years(active_years)
    set_latest_year(year)


def remove_active_year_for_class(class_cat):
    class_level, target_arm = normalize_target(class_cat)

    if not class_level:
        return

    active_years = get_class_active_years()

    if target_arm in active_years:
        del active_years[target_arm]

    save_class_active_years(active_years)


# ============================================================
# ACTIVE TERM MAP — JSS ONLY
# ============================================================

def get_class_active_terms():
    return read_json(CLASS_ACTIVE_TERMS_FILE, default={}) or {}


def save_class_active_terms(data):
    write_json(CLASS_ACTIVE_TERMS_FILE, data or {})


def get_active_term_for_target(target_arm, fallback_level=""):
    class_level, target_arm = normalize_target(target_arm, fallback_level)

    if not class_level or not is_term_aware_class(class_level):
        return None

    active_terms = get_class_active_terms()
    term = active_terms.get(target_arm) or active_terms.get(class_level)

    return normalize_term(term)


def set_active_term_for_target(target_arm, term, class_level=""):
    class_level, target_arm = normalize_target(target_arm, class_level)
    term = normalize_term(term)

    if not class_level or not target_arm:
        return

    if not is_term_aware_class(class_level) or not term:
        return

    active_terms = get_class_active_terms()
    active_terms[target_arm] = term

    save_class_active_terms(active_terms)


def remove_active_term_for_target(target_arm, class_level=""):
    class_level, target_arm = normalize_target(target_arm, class_level)

    if not target_arm:
        return

    active_terms = get_class_active_terms()

    if target_arm in active_terms:
        del active_terms[target_arm]

    save_class_active_terms(active_terms)


# ============================================================
# PUSH MANIFEST HELPERS
# ============================================================

def extract_subjects_from_manifest(path):
    data = read_json(path, default={}) or {}

    if isinstance(data, dict):
        return data.get("subjects", []) or []

    if isinstance(data, list):
        return data

    return []


def manifest_has_subjects(path):
    return bool(extract_subjects_from_manifest(path))


# ============================================================
# RECALCULATE ACTIVE YEARS / TERMS
# ============================================================

def recalculate_active_years():
    """
    Rebuild active year and JSS term maps from portal folders.

    SS:
        <YEAR>/<TARGET>/pushed_subjects.json

    JSS:
        <YEAR>/<TARGET>/<TERM>/pushed_subjects.json
    """
    target_records = {}

    if not PORTAL_ROOT.exists():
        clear_latest_year()
        save_class_active_years({})
        save_class_active_terms({})
        return {}

    for year_folder in PORTAL_ROOT.iterdir():
        if not year_folder.is_dir() or not year_folder.name.isdigit():
            continue

        year = year_folder.name

        for target_folder in year_folder.iterdir():
            if not target_folder.is_dir():
                continue

            class_level, target_arm = normalize_target(target_folder.name)

            if not class_level or not target_arm:
                continue

            has_subjects = False
            available_terms = []

            # SS and legacy flat JSS manifest.
            flat_manifest = target_folder / "pushed_subjects.json"

            if flat_manifest.exists() and manifest_has_subjects(flat_manifest):
                has_subjects = True

            # New JSS term-aware manifests.
            if is_term_aware_class(class_level):
                for term in ("FIRST", "SECOND", "THIRD"):
                    term_manifest = target_folder / term / "pushed_subjects.json"

                    if term_manifest.exists() and manifest_has_subjects(term_manifest):
                        has_subjects = True
                        available_terms.append(term)

            if not has_subjects:
                continue

            year_num = int(year)
            previous = target_records.get(target_arm)

            # Keep only information belonging to the latest year.
            if not previous or year_num > previous["year_num"]:
                target_records[target_arm] = {
                    "year": year,
                    "year_num": year_num,
                    "class_level": class_level,
                    "terms": available_terms,
                }

            elif year_num == previous["year_num"] and available_terms:
                previous["terms"] = list(set(previous["terms"] + available_terms))

    active_years = {}
    active_terms = {}

    for target_arm, record in target_records.items():
        active_years[target_arm] = record["year"]

        if is_term_aware_class(record["class_level"]) and record["terms"]:
            active_terms[target_arm] = max(
                record["terms"],
                key=lambda term: TERM_ORDER.get(term, 0)
            )

    save_class_active_years(active_years)
    save_class_active_terms(active_terms)

    if active_years:
        global_latest = str(max(int(year) for year in active_years.values()))
        set_latest_year(global_latest)
    else:
        clear_latest_year()

    return active_years


def recalculate_latest_year():
    active = recalculate_active_years()

    if not active:
        return None

    return str(max(int(year) for year in active.values()))


# ============================================================
# PORTAL PATH HELPERS
# ============================================================

def get_portal_target_folder(year, class_level, target_arm, term=None):
    """
    JSS -> portal/year/JSS1A/FIRST
    SS  -> portal/year/SS1_GOLD
    """
    folder = PORTAL_ROOT / str(year) / target_arm

    if is_term_aware_class(class_level):
        term = normalize_term(term)

        if not term:
            return None

        folder = folder / term

    return folder


def get_subject_source_path(year, class_level, filename, term=None):
    """
    JSS -> subjects/year/subjects-json/JSS1/FIRST/file.json
    SS  -> subjects/year/subjects-json/SS1/file.json
    """
    path = SUBJECTS_JSON_ROOT / str(year) / "subjects-json" / class_level

    if is_term_aware_class(class_level):
        term = normalize_term(term)

        if not term:
            return None

        path = path / term

    return path / filename


# ============================================================
# PUSHED SUBJECT LIST
# ============================================================

def load_pushed_list(year, class_cat, term=None):
    class_level, target_arm = normalize_target(class_cat)

    if not year or not target_arm:
        return []

    folder = get_portal_target_folder(year, class_level, target_arm, term)

    if folder is None:
        return []

    data = read_json(folder / "pushed_subjects.json", default={}) or {}

    if isinstance(data, dict):
        return data.get("subjects", []) or []

    if isinstance(data, list):
        return data

    return []


def save_pushed_list(year, class_cat, subjects, class_level="", term=None):
    resolved_level, target_arm = normalize_target(class_cat, class_level)

    if not year or not target_arm:
        return

    normalized_term = normalize_term(term)

    if is_term_aware_class(resolved_level) and not normalized_term:
        raise ValueError(f"Term is required for {resolved_level}")

    folder = get_portal_target_folder(
        year,
        resolved_level,
        target_arm,
        normalized_term
    )

    if folder is None:
        raise ValueError(f"Unable to resolve portal folder for {target_arm}")

    folder.mkdir(parents=True, exist_ok=True)

    write_json(folder / "pushed_subjects.json", {
        "year": str(year),
        "class_level": resolved_level,
        "class_category": resolved_level,
        "class_arm": target_arm,
        "target_arm": target_arm,
        "term": normalized_term if is_term_aware_class(resolved_level) else None,
        "term_label": (
            term_label(normalized_term)
            if is_term_aware_class(resolved_level)
            else None
        ),
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

        if subject:
            return subject

    return subject_name_from_filename(filename)


# ============================================================
# API — PUSH SUBJECTS
# ============================================================

@push_bp.route("/push", methods=["POST"])
def push_subjects():
    payload = request.get_json(silent=True) or {}

    raw_files = payload.get("files", [])
    class_level, target_arm = get_payload_target(payload)
    term = get_payload_term(payload)

    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    if not raw_files:
        return jsonify({
            "success": False,
            "error": "No files provided",
        }), 400

    if not is_valid_target(class_level, target_arm):
        return jsonify({
            "success": False,
            "error": f"Invalid class target: {target_arm or class_level}",
        }), 400

    if is_term_aware_class(class_level):
        if not term:
            return jsonify({
                "success": False,
                "error": f"Term is required for {class_level}",
                "term_required": True,
            }), 400
    else:
        # SS must never accidentally inherit a JSS term.
        term = None

    pushed_summary = []
    failed = []
    years_used = set()

    # --------------------------------------------------------
    # Process selected JSON files
    # --------------------------------------------------------

    for entry in raw_files:
        try:
            year, filename = str(entry).split(":", 1)

        except Exception:
            failed.append({
                "entry": entry,
                "reason": "Invalid entry format. Expected YEAR:FILENAME",
            })
            continue

        year = str(year).strip()
        filename = os.path.basename(str(filename).strip())

        if not year.isdigit():
            failed.append({
                "entry": entry,
                "reason": "Invalid year",
            })
            continue

        if not filename.lower().endswith(".json"):
            failed.append({
                "entry": entry,
                "reason": "Only JSON files can be pushed",
            })
            continue

        src = get_subject_source_path(year, class_level, filename, term)

        if not src or not src.exists():
            failed.append({
                "entry": entry,
                "reason": f"Missing source JSON: {src}",
            })

            print(f"Missing JSON: {src}")
            continue

        # ----------------------------------------------------
        # Load source JSON
        # ----------------------------------------------------

        try:
            content = json.loads(src.read_text(encoding="utf-8"))

        except Exception as exc:
            failed.append({
                "entry": entry,
                "reason": f"Invalid JSON: {exc}",
            })

            print(f"Invalid JSON {src}: {exc}")
            continue

        if not isinstance(content, dict):
            failed.append({
                "entry": entry,
                "reason": "JSON root must be an object",
            })
            continue

        # ----------------------------------------------------
        # JSS term verification
        # ----------------------------------------------------

        if is_term_aware_class(class_level):
            json_term = normalize_term(
                content.get("term")
                or content.get("exam_term")
                or content.get("academic_term")
            )

            if json_term and json_term != term:
                failed.append({
                    "entry": entry,
                    "reason": (
                        f"Term mismatch: JSON is {term_label(json_term)}, "
                        f"target is {term_label(term)}"
                    ),
                })
                continue

            content["term"] = term
            content["term_label"] = term_label(term)

        content["class_category"] = class_level

        # ----------------------------------------------------
        # Destination
        # ----------------------------------------------------

        dst_folder = get_portal_target_folder(
            year,
            class_level,
            target_arm,
            term
        )

        if dst_folder is None:
            failed.append({
                "entry": entry,
                "reason": "Unable to resolve destination",
            })
            continue

        dst_folder.mkdir(parents=True, exist_ok=True)
        dst = dst_folder / filename

        try:
            dst.write_text(
                json.dumps(content, indent=4, ensure_ascii=False),
                encoding="utf-8"
            )

        except Exception as exc:
            failed.append({
                "entry": entry,
                "reason": f"Failed to write portal JSON: {exc}",
            })
            continue

        # ----------------------------------------------------
        # Portal subject manifest
        # ----------------------------------------------------

        pushed_list = load_pushed_list(year, target_arm, term)
        subject_name = get_subject_name_from_json(content, filename)

        if subject_name not in pushed_list:
            pushed_list.append(subject_name)

        try:
            save_pushed_list(
                year,
                target_arm,
                pushed_list,
                class_level,
                term
            )

        except Exception as exc:
            failed.append({
                "entry": entry,
                "reason": f"Failed to update subject manifest: {exc}",
            })

            # Remove copied JSON if manifest failed.
            try:
                if dst.exists():
                    dst.unlink()
            except Exception:
                pass

            continue

        if subject_name not in pushed_summary:
            pushed_summary.append(subject_name)

        years_used.add(year)

    # --------------------------------------------------------
    # Active year / term
    # --------------------------------------------------------

    active_year = None
    success = bool(pushed_summary)

    if years_used and success:
        active_year = str(max(int(year) for year in years_used))

        set_active_year_for_target(
            target_arm,
            active_year,
            class_level
        )

        if is_term_aware_class(class_level):
            set_active_term_for_target(
                target_arm,
                term,
                class_level
            )

    return jsonify({
        "success": success,

        "class": class_level,
        "class_level": class_level,
        "class_category": class_level,

        "class_arm": target_arm,
        "target_arm": target_arm,

        "term": term,
        "term_label": term_label(term) if term else None,

        "subjects_pushed": pushed_summary,
        "subject_count": len(pushed_summary),

        "failed": failed,
        "failed_count": len(failed),

        "active_year": active_year,

        "active_term": (
            term
            if is_term_aware_class(class_level) and success
            else None
        ),

        "latest_year": get_latest_year(),
        "class_active_years": get_class_active_years(),
        "class_active_terms": get_class_active_terms(),
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
    # Clear ALL years + ALL targets
    # --------------------------------------------------------

    if year.upper() == "ALL" and raw_target == "ALL":
        if PORTAL_ROOT.exists():
            shutil.rmtree(PORTAL_ROOT)

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
    # Clear one year for ALL targets
    # --------------------------------------------------------

    if raw_target == "ALL":
        year_folder = PORTAL_ROOT / year

        if year_folder.exists():
            shutil.rmtree(year_folder)

        active = recalculate_active_years()

        return jsonify({
            "success": True,
            "cleared": f"{year}-ALL",
            "latest_year": get_latest_year(),
            "class_active_years": active,
            "class_active_terms": get_class_active_terms(),
        })

    # --------------------------------------------------------
    # Resolve target
    # --------------------------------------------------------

    class_level, target_arm = get_payload_target(payload)

    if not is_valid_target(class_level, target_arm):
        return jsonify({
            "success": False,
            "error": f"Invalid class target: {target_arm or class_level}",
        }), 400

    # --------------------------------------------------------
    # JSS — clear selected term only
    # --------------------------------------------------------

    if is_term_aware_class(class_level):
        if not term:
            return jsonify({
                "success": False,
                "error": f"Term is required when clearing {class_level}",
                "term_required": True,
            }), 400

        target_folder = PORTAL_ROOT / year / target_arm / term

        if target_folder.exists():
            shutil.rmtree(target_folder)

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
    # SS — clear entire target
    # --------------------------------------------------------

    target_folder = PORTAL_ROOT / year / target_arm

    if target_folder.exists():
        shutil.rmtree(target_folder)

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
    # Active year
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
            "subjects": [],
        })

    # --------------------------------------------------------
    # JSS active term
    # --------------------------------------------------------

    active_term = None

    if is_term_aware_class(class_level):
        requested_term = normalize_term(request.args.get("term"))

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
                "subjects": [],
            })

    # --------------------------------------------------------
    # Load assigned subjects
    # --------------------------------------------------------

    pushed_list = load_pushed_list(
        active_year,
        class_arm,
        active_term
    )

    # Exact arm -> broad class fallback.
    if not pushed_list and class_arm != class_level:
        pushed_list = load_pushed_list(
            active_year,
            class_level,
            active_term
        )

    subjects = []

    for subject in pushed_list:
        subjects.append({
            "subject": subject,
            "year": active_year,

            "class": class_arm,
            "class_level": class_level,
            "class_arm": class_arm,

            "term": active_term,
            "term_label": (
                term_label(active_term)
                if active_term
                else None
            ),
        })

    return jsonify({
        "class": class_level,
        "class_level": class_level,
        "class_category": class_level,

        "class_arm": class_arm,

        "active_year": active_year,

        "active_term": active_term,
        "term": active_term,

        "term_label": (
            term_label(active_term)
            if active_term
            else None
        ),

        "subjects": subjects,
    })


# ============================================================
# API — LATEST ACTIVE YEAR
# ============================================================

@push_bp.route("/push_latest_year", methods=["GET"])
def push_latest_year():
    active_years = get_class_active_years()

    if not active_years:
        active_years = recalculate_active_years()

    latest = get_latest_year()

    return jsonify({
        "year": latest,
        "latest_year": latest,
        "class_active_years": active_years,
        "class_active_terms": get_class_active_terms(),
    })


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
        return jsonify({
            "error": "Invalid class",
        }), 400

    active_year = get_active_year_for_target(
        target_arm,
        class_level
    )

    if not active_year:
        active = recalculate_active_years()
        active_year = (
            active.get(target_arm)
            or active.get(class_level)
        )

    active_term = None

    if is_term_aware_class(class_level):
        active_term = get_active_term_for_target(
            target_arm,
            class_level
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

        "term_label": (
            term_label(active_term)
            if active_term
            else None
        ),
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

        active_term = None

        if is_term_aware_class(class_level):
            active_term = normalize_term(
                active_terms.get(resolved_arm)
                or active_terms.get(class_level)
            )

        subjects = load_pushed_list(
            year,
            resolved_arm,
            active_term
        )

        if not subjects and resolved_arm != class_level:
            subjects = load_pushed_list(
                year,
                class_level,
                active_term
            )

        details[resolved_arm] = {
            "year": year,

            "class_level": class_level,
            "class_category": class_level,

            "class_arm": resolved_arm,
            "target_arm": resolved_arm,

            "term": active_term,
            "active_term": active_term,

            "term_label": (
                term_label(active_term)
                if active_term
                else None
            ),

            "term_aware": is_term_aware_class(class_level),

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
# Example:
# /available-terms?year=2026&class=JSS1
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

    # SS classes are intentionally not term-folder aware.
    if not is_term_aware_class(class_level):
        return jsonify({
            "success": True,
            "year": year,
            "class_level": class_level,
            "class_category": class_level,
            "term_aware": False,
            "terms": [],
        })

    class_folder = (
        SUBJECTS_JSON_ROOT
        / year
        / "subjects-json"
        / class_level
    )

    available = []

    for term in ("FIRST", "SECOND", "THIRD"):
        term_folder = class_folder / term

        if not term_folder.exists() or not term_folder.is_dir():
            continue

        has_json = any(
            file.is_file() and file.suffix.lower() == ".json"
            for file in term_folder.iterdir()
        )

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

        "term_aware": True,
        "terms": available,
    })


# ============================================================
# API — ACTIVE TERM FOR CLASS / ARM
#
# Example:
# /push_active_term?class=JSS1A
# ============================================================

@push_bp.route("/push_active_term", methods=["GET"])
def push_active_term():
    raw_class = request.args.get("class", "")
    class_level, target_arm = normalize_target(raw_class)

    if not class_level:
        return jsonify({
            "error": "Invalid class",
        }), 400

    if not is_term_aware_class(class_level):
        return jsonify({
            "class": class_level,
            "class_level": class_level,
            "class_category": class_level,

            "class_arm": target_arm,
            "target_arm": target_arm,

            "term_aware": False,

            "term": None,
            "active_term": None,
            "term_label": None,
        })

    active_term = get_active_term_for_target(
        target_arm,
        class_level
    )

    if not active_term:
        recalculate_active_years()

        active_term = get_active_term_for_target(
            target_arm,
            class_level
        )

    return jsonify({
        "class": class_level,
        "class_level": class_level,
        "class_category": class_level,

        "class_arm": target_arm,
        "target_arm": target_arm,

        "term_aware": True,

        "term": active_term,
        "active_term": active_term,

        "term_label": (
            term_label(active_term)
            if active_term
            else None
        ),
    })