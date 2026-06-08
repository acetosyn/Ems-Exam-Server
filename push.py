# push.py — EMIS PORTAL PUSH SYSTEM
# Supports:
#   - Broad class push: JSS1, SS1, SS3
#   - Exact class-arm push: JSS1A, SS3_GOLD, SS3B
#   - Per-target active years
#   - Backward compatibility with old push.js

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
    is_valid_class_arm,
)

push_bp = Blueprint("push_bp", __name__)

BASE_DIR = Path(__file__).resolve().parent

SUBJECTS_JSON_ROOT = BASE_DIR / "static" / "subjects"
PORTAL_ROOT = BASE_DIR / "static" / "portal"
PORTAL_ROOT.mkdir(parents=True, exist_ok=True)

LATEST_YEAR_FILE = PORTAL_ROOT / "latest_year.txt"
CLASS_ACTIVE_YEARS_FILE = PORTAL_ROOT / "class_active_years.json"


# ============================================================
# JSON HELPERS
# ============================================================
def read_json(path, default=None):
    try:
        path = Path(path)
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"JSON READ ERROR [{path}]:", e)

    return default


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=4, ensure_ascii=False), encoding="utf-8")


# ============================================================
# CLASS / ARM HELPERS
# ============================================================
def normalize_class(class_cat):
    """
    Backward-compatible helper.
    Returns broad class level only:
    SS3_GOLD -> SS3
    JSS1A -> JSS1
    """
    return normalize_class_level(class_cat)


def normalize_target(value, fallback_level=""):
    """
    Preserves exact target:
    SS3_GOLD -> SS3_GOLD
    SS3B -> SS3B
    JSS1A -> JSS1A
    SS3 -> SS3
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
    Supports both new and old payloads.

    Old:
      { class_category: "SS3" }

    New:
      { class_level: "SS3", class_arm: "SS3_GOLD" }
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
    class_level = normalize_class_level(
        student.get("class_category")
        or student.get("class_level")
        or student.get("class")
        or ""
    )

    class_arm = normalize_class_arm(
        student.get("class_arm")
        or student.get("class")
        or student.get("class_category")
        or class_level,
        class_level
    )

    if not class_level:
        class_level = normalize_class_level(class_arm)

    if not class_arm:
        class_arm = class_level

    return class_level, class_arm


# ============================================================
# GLOBAL LATEST YEAR — backward compatibility
# ============================================================
def get_latest_year():
    if LATEST_YEAR_FILE.exists():
        year = LATEST_YEAR_FILE.read_text(encoding="utf-8").strip()
        return year or None
    return None


def set_latest_year(year):
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

    Accepts:
      SS3_GOLD -> checks SS3_GOLD first, then SS3
      SS3      -> checks SS3
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
    """
    Backward-compatible name, but now preserves arm.
    """
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
# RECALCULATE ACTIVE YEARS
# ============================================================
def recalculate_active_years():
    active = {}

    if not PORTAL_ROOT.exists():
        clear_latest_year()
        save_class_active_years({})
        return {}

    for year_folder in PORTAL_ROOT.iterdir():
        if not year_folder.is_dir():
            continue

        year = year_folder.name

        if not year.isdigit():
            continue

        for target_folder in year_folder.iterdir():
            if not target_folder.is_dir():
                continue

            target_name = target_folder.name
            class_level, target_arm = normalize_target(target_name)

            if not class_level or not target_arm:
                continue

            pushed_file = target_folder / "pushed_subjects.json"

            if not pushed_file.exists():
                continue

            data = read_json(pushed_file, default={}) or {}

            if isinstance(data, dict):
                subjects = data.get("subjects", [])
            elif isinstance(data, list):
                subjects = data
            else:
                subjects = []

            if subjects:
                previous_year = active.get(target_arm)

                if not previous_year:
                    active[target_arm] = year
                else:
                    active[target_arm] = str(max(int(previous_year), int(year)))

    save_class_active_years(active)

    if active:
        global_latest = str(max(int(y) for y in active.values()))
        set_latest_year(global_latest)
    else:
        clear_latest_year()

    return active


def recalculate_latest_year():
    active = recalculate_active_years()

    if not active:
        return None

    return str(max(int(y) for y in active.values()))


# ============================================================
# PUSHED SUBJECT LIST
# ============================================================
def load_pushed_list(year, class_cat):
    class_level, target_arm = normalize_target(class_cat)

    if not year or not target_arm:
        return []

    path = PORTAL_ROOT / str(year) / target_arm / "pushed_subjects.json"
    data = read_json(path, default={}) or {}

    if isinstance(data, dict):
        return data.get("subjects", []) or []

    if isinstance(data, list):
        return data

    return []


def save_pushed_list(year, class_cat, subjects, class_level=""):
    resolved_level, target_arm = normalize_target(class_cat, class_level)

    if not year or not target_arm:
        return

    folder = PORTAL_ROOT / str(year) / target_arm
    folder.mkdir(parents=True, exist_ok=True)

    path = folder / "pushed_subjects.json"

    write_json(path, {
        "year": str(year),
        "class_level": resolved_level,
        "class_category": resolved_level,
        "class_arm": target_arm,
        "target_arm": target_arm,
        "subjects": subjects or [],
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "updated_by": session.get("username", "system"),
    })


# ============================================================
# SUBJECT NAME FROM FILE
# ============================================================
def subject_name_from_filename(filename):
    name = str(filename or "").replace(".json", "")

    for cls in SUPPORTED_CLASSES:
        suffix = f"_{cls.lower()}"
        if name.lower().endswith(suffix):
            name = name[: -len(suffix)]
            break

    aliases = {
        "accounts": "Financial Account",
        "account": "Financial Account",
        "financial_account": "Financial Account",
        "financial_accounting": "Financial Account",
        "english": "English Language",
        "maths": "Mathematics",
        "computer": "Computer Science",
        "computer_science": "Computer Science",
        "civic": "Civic Education",
        "technical": "Technical Drawing",
        "irs": "IRS",
        "irk": "IRK",
    }

    key = name.lower().strip()
    return aliases.get(key, name.replace("_", " ").title())


# ============================================================
# API — PUSH SUBJECTS
# ============================================================
@push_bp.route("/push", methods=["POST"])
def push_subjects():
    payload = request.get_json(silent=True) or {}

    raw_files = payload.get("files", [])

    class_level, target_arm = get_payload_target(payload)

    if not raw_files:
        return jsonify({
            "success": False,
            "error": "No files provided"
        }), 400

    if not is_valid_target(class_level, target_arm):
        return jsonify({
            "success": False,
            "error": f"Invalid class target: {target_arm or class_level}"
        }), 400

    pushed_summary = []
    failed = []
    years_used = set()

    for entry in raw_files:
        try:
            year, filename = str(entry).split(":", 1)
        except Exception:
            failed.append({
                "entry": entry,
                "reason": "Invalid entry format. Expected YEAR:FILENAME"
            })
            continue

        year = str(year).strip()
        filename = os.path.basename(str(filename).strip())

        if not year.isdigit():
            failed.append({
                "entry": entry,
                "reason": "Invalid year"
            })
            continue

        if not filename.lower().endswith(".json"):
            failed.append({
                "entry": entry,
                "reason": "Only JSON files can be pushed"
            })
            continue

        years_used.add(year)

        # Source stays broad class level:
        # static/subjects/<year>/subjects-json/SS3/physics_ss3.json
        src = SUBJECTS_JSON_ROOT / year / "subjects-json" / class_level / filename

        if not src.exists():
            failed.append({
                "entry": entry,
                "reason": f"Missing source JSON: {src}"
            })
            print(f"Missing JSON: {src}")
            continue

        try:
            content = json.loads(src.read_text(encoding="utf-8"))
        except Exception as e:
            failed.append({
                "entry": entry,
                "reason": f"Invalid JSON: {e}"
            })
            print(f"Invalid JSON {src}: {e}")
            continue

        # Destination preserves target arm:
        # static/portal/<year>/SS3_GOLD/physics_ss3.json
        dst_folder = PORTAL_ROOT / year / target_arm
        dst_folder.mkdir(parents=True, exist_ok=True)

        dst = dst_folder / filename
        dst.write_text(json.dumps(content, indent=4, ensure_ascii=False), encoding="utf-8")

        pushed_list = load_pushed_list(year, target_arm)
        subject_name = subject_name_from_filename(filename)

        if subject_name not in pushed_list:
            pushed_list.append(subject_name)

        save_pushed_list(year, target_arm, pushed_list, class_level)

        if subject_name not in pushed_summary:
            pushed_summary.append(subject_name)

    active_year = None

    if years_used:
      active_year = str(max(int(y) for y in years_used))
      set_active_year_for_target(target_arm, active_year, class_level)

    return jsonify({
        "success": True,
        "class": class_level,
        "class_level": class_level,
        "class_category": class_level,
        "class_arm": target_arm,
        "target_arm": target_arm,
        "subjects_pushed": pushed_summary,
        "failed": failed,
        "active_year": active_year,
        "latest_year": get_latest_year(),
        "class_active_years": get_class_active_years()
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

    if not year:
        return jsonify({
            "success": False,
            "error": "Year is required"
        }), 400

    # Clear all years and all targets
    if year == "ALL" and raw_target == "ALL":
        if PORTAL_ROOT.exists():
            shutil.rmtree(PORTAL_ROOT)

        PORTAL_ROOT.mkdir(parents=True, exist_ok=True)
        clear_latest_year()
        save_class_active_years({})

        return jsonify({
            "success": True,
            "cleared": "ALL",
            "latest_year": None,
            "class_active_years": {}
        })

    # Clear one year for all targets
    if raw_target == "ALL":
        year_folder = PORTAL_ROOT / year

        if year_folder.exists():
            shutil.rmtree(year_folder)

        active = recalculate_active_years()

        return jsonify({
            "success": True,
            "cleared": f"{year}-ALL",
            "latest_year": get_latest_year(),
            "class_active_years": active
        })

    class_level, target_arm = get_payload_target(payload)

    if not is_valid_target(class_level, target_arm):
        return jsonify({
            "success": False,
            "error": f"Invalid class target: {target_arm or class_level}"
        }), 400

    # Clear one year + one target
    target_folder = PORTAL_ROOT / year / target_arm

    if target_folder.exists():
        shutil.rmtree(target_folder)

    target_folder.mkdir(parents=True, exist_ok=True)
    save_pushed_list(year, target_arm, [], class_level)

    active = recalculate_active_years()

    return jsonify({
        "success": True,
        "cleared": f"{year}-{target_arm}",
        "class": class_level,
        "class_level": class_level,
        "class_category": class_level,
        "class_arm": target_arm,
        "target_arm": target_arm,
        "latest_year": get_latest_year(),
        "class_active_years": active
    })


# ============================================================
# STUDENT FETCH — GET PUSHED SUBJECTS
# Kept for backward compatibility.
# Your student_portal.py now has stronger routing.
# ============================================================
@push_bp.route("/get_pushed_subjects", methods=["GET"])
def student_get_pushed():
    student = session.get("student")

    if not student:
        return jsonify({"subjects": []})

    class_level, class_arm = get_student_target_meta(student)

    if not class_level:
        return jsonify({"subjects": []})

    active_year = get_active_year_for_target(class_arm, class_level)

    if not active_year:
        active_years = recalculate_active_years()
        active_year = active_years.get(class_arm) or active_years.get(class_level)

    if not active_year:
        return jsonify({"subjects": []})

    pushed_list = load_pushed_list(active_year, class_arm)

    # JSS broad fallback
    if not pushed_list and class_level.startswith("JSS"):
        pushed_list = load_pushed_list(active_year, class_level)

    return jsonify({
        "class": class_level,
        "class_level": class_level,
        "class_category": class_level,
        "class_arm": class_arm,
        "active_year": active_year,
        "subjects": [
            {
                "subject": subject,
                "year": active_year,
                "class": class_arm,
                "class_level": class_level,
                "class_arm": class_arm,
            }
            for subject in pushed_list
        ]
    })


# ============================================================
# API — Latest active year, backward compatible
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
        "class_active_years": active_years
    })


# ============================================================
# API — Active year for a specific class / arm
# /api/push_active_year?class=SS3_GOLD
# /api/push_active_year?class=SS3
# ============================================================
@push_bp.route("/push_active_year", methods=["GET"])
def push_active_year():
    raw_class = request.args.get("class", "")
    class_level, target_arm = normalize_target(raw_class)

    if not class_level:
        return jsonify({"error": "Invalid class"}), 400

    active_year = get_active_year_for_target(target_arm, class_level)

    if not active_year:
        active = recalculate_active_years()
        active_year = active.get(target_arm) or active.get(class_level)

    return jsonify({
        "class": class_level,
        "class_level": class_level,
        "class_category": class_level,
        "class_arm": target_arm,
        "target_arm": target_arm,
        "year": active_year
    })


# ============================================================
# API — Portal active map
# Useful for admin/teacher dashboard
# ============================================================
@push_bp.route("/portal_active_map", methods=["GET"])
def portal_active_map():
    active = get_class_active_years()

    if not active:
        active = recalculate_active_years()

    details = {}

    for target_arm, year in active.items():
        class_level, resolved_arm = normalize_target(target_arm)
        subjects = load_pushed_list(year, resolved_arm)

        details[resolved_arm] = {
            "year": year,
            "class_level": class_level,
            "class_category": class_level,
            "class_arm": resolved_arm,
            "target_arm": resolved_arm,
            "subjects": subjects,
            "subject_count": len(subjects),
        }

    return jsonify({
        "success": True,
        "latest_year": get_latest_year(),
        "class_active_years": active,
        "active_map": details
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
            for f in files:
                if f.lower().endswith(".json"):
                    found_json = True
                    break

            if found_json:
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
        "years": get_available_subject_years()
    })