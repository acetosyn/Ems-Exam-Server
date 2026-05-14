# push.py — FULL JSS1–SS3 YEAR-AWARE EMIS PORTAL PUSH SYSTEM

import os
import json
import shutil
from flask import Blueprint, jsonify, request, session
from pathlib import Path

from modules.class_config import SUPPORTED_CLASSES


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
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=4), encoding="utf-8")


def normalize_class(class_cat):
    class_cat = str(class_cat or "").upper().strip()

    if class_cat in SUPPORTED_CLASSES:
        return class_cat

    for cls in SUPPORTED_CLASSES:
        if class_cat.startswith(cls):
            return cls

    return ""


# ============================================================
# GLOBAL LATEST YEAR — kept for backward compatibility
# ============================================================
def get_latest_year():
    if LATEST_YEAR_FILE.exists():
        return LATEST_YEAR_FILE.read_text(encoding="utf-8").strip()
    return None


def set_latest_year(year):
    LATEST_YEAR_FILE.write_text(str(year), encoding="utf-8")


def clear_latest_year():
    if LATEST_YEAR_FILE.exists():
        LATEST_YEAR_FILE.unlink()


# ============================================================
# CLASS ACTIVE YEAR
# ============================================================
def get_class_active_years():
    return read_json(CLASS_ACTIVE_YEARS_FILE, default={}) or {}


def save_class_active_years(data):
    write_json(CLASS_ACTIVE_YEARS_FILE, data)


def get_active_year_for_class(class_cat):
    class_cat = normalize_class(class_cat)
    if not class_cat:
        return None

    active_years = get_class_active_years()
    return active_years.get(class_cat)


def set_active_year_for_class(class_cat, year):
    class_cat = normalize_class(class_cat)
    if not class_cat:
        return

    active_years = get_class_active_years()
    active_years[class_cat] = str(year)
    save_class_active_years(active_years)

    set_latest_year(year)


def remove_active_year_for_class(class_cat):
    class_cat = normalize_class(class_cat)
    if not class_cat:
        return

    active_years = get_class_active_years()

    if class_cat in active_years:
        del active_years[class_cat]

    save_class_active_years(active_years)


# ============================================================
# RECALCULATE ACTIVE YEARS PER CLASS
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

        for class_folder in year_folder.iterdir():
            if not class_folder.is_dir():
                continue

            class_cat = normalize_class(class_folder.name)

            if not class_cat:
                continue

            pushed_file = class_folder / "pushed_subjects.json"

            if not pushed_file.exists():
                continue

            data = read_json(pushed_file, default={}) or {}
            subjects = data.get("subjects", [])

            if subjects:
                if class_cat not in active:
                    active[class_cat] = year
                else:
                    active[class_cat] = max(active[class_cat], year)

    save_class_active_years(active)

    if active:
        global_latest = max(active.values())
        set_latest_year(global_latest)
    else:
        clear_latest_year()

    return active


def recalculate_latest_year():
    active = recalculate_active_years()
    if not active:
        return None

    return max(active.values())


# ============================================================
# PUSHED SUBJECT LIST
# ============================================================
def load_pushed_list(year, class_cat):
    class_cat = normalize_class(class_cat)

    if not year or not class_cat:
        return []

    path = PORTAL_ROOT / str(year) / class_cat / "pushed_subjects.json"

    data = read_json(path, default={}) or {}

    if isinstance(data, dict):
        return data.get("subjects", [])

    if isinstance(data, list):
        return data

    return []


def save_pushed_list(year, class_cat, subjects):
    class_cat = normalize_class(class_cat)

    if not year or not class_cat:
        return

    folder = PORTAL_ROOT / str(year) / class_cat
    folder.mkdir(parents=True, exist_ok=True)

    path = folder / "pushed_subjects.json"

    write_json(path, {
        "year": str(year),
        "class_category": class_cat,
        "subjects": subjects
    })


# ============================================================
# SUBJECT NAME FROM FILE
# ============================================================
def subject_name_from_filename(filename):
    name = filename.replace(".json", "")

    for cls in SUPPORTED_CLASSES:
        suffix = f"_{cls.lower()}"
        if name.lower().endswith(suffix):
            name = name[: -len(suffix)]
            break

    return name.replace("_", " ").title()


# ============================================================
# API — PUSH SUBJECTS
# ============================================================
@push_bp.route("/push", methods=["POST"])
def push_subjects():
    payload = request.get_json() or {}

    raw_files = payload.get("files", [])
    target_class = normalize_class(payload.get("class_category"))

    if not raw_files:
        return jsonify({"success": False, "error": "No files provided"}), 400

    if not target_class:
        return jsonify({"success": False, "error": "Invalid class"}), 400

    pushed_summary = []
    last_year_used = None

    for entry in raw_files:
        try:
            year, filename = entry.split(":", 1)
        except Exception:
            return jsonify({
                "success": False,
                "error": f"Invalid entry: {entry}"
            }), 400

        year = str(year).strip()
        last_year_used = year

        src = SUBJECTS_JSON_ROOT / year / "subjects-json" / target_class / filename

        if not src.exists():
            print(f"Missing JSON: {src}")
            continue

        try:
            content = json.loads(src.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Invalid JSON {src}: {e}")
            continue

        dst_folder = PORTAL_ROOT / year / target_class
        dst_folder.mkdir(parents=True, exist_ok=True)

        dst = dst_folder / filename
        dst.write_text(json.dumps(content, indent=4), encoding="utf-8")

        pushed_list = load_pushed_list(year, target_class)
        subject_name = subject_name_from_filename(filename)

        if subject_name not in pushed_list:
            pushed_list.append(subject_name)

        save_pushed_list(year, target_class, pushed_list)

        pushed_summary.append(subject_name)

    if last_year_used:
        set_active_year_for_class(target_class, last_year_used)

    return jsonify({
        "success": True,
        "class": target_class,
        "subjects_pushed": pushed_summary,
        "active_year": last_year_used,
        "latest_year": get_latest_year(),
        "class_active_years": get_class_active_years()
    })


# ============================================================
# API — CLEAR PORTAL
# ============================================================
@push_bp.route("/clear", methods=["POST"])
def clear_portal():
    payload = request.get_json() or {}

    year = str(payload.get("year", "")).strip()
    target_class_raw = str(payload.get("class_category", "")).upper().strip()

    if target_class_raw != "ALL":
        target_class = normalize_class(target_class_raw)
        if not target_class:
            return jsonify({"success": False, "error": "Invalid class"}), 400
    else:
        target_class = "ALL"

    # Clear all years and all classes
    if year == "ALL" and target_class == "ALL":
        if PORTAL_ROOT.exists():
            shutil.rmtree(PORTAL_ROOT)

        PORTAL_ROOT.mkdir(parents=True, exist_ok=True)
        clear_latest_year()
        save_class_active_years({})

        return jsonify({
            "success": True,
            "cleared": "ALL",
            "class_active_years": {}
        })

    # Clear one year for all classes
    if target_class == "ALL":
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

    # Clear one year + one class
    class_folder = PORTAL_ROOT / year / target_class

    if class_folder.exists():
        shutil.rmtree(class_folder)

    class_folder.mkdir(parents=True, exist_ok=True)
    save_pushed_list(year, target_class, [])

    active = recalculate_active_years()

    return jsonify({
        "success": True,
        "cleared": f"{year}-{target_class}",
        "latest_year": get_latest_year(),
        "class_active_years": active
    })


# ============================================================
# STUDENT FETCH — GET ACTIVE YEAR FOR STUDENT CLASS
# ============================================================
@push_bp.route("/get_pushed_subjects", methods=["GET"])
def student_get_pushed():
    student = session.get("student")

    if not student:
        return jsonify({"subjects": []})

    class_cat = normalize_class(student.get("class_category"))

    if not class_cat:
        return jsonify({"subjects": []})

    active_year = get_active_year_for_class(class_cat)

    if not active_year:
        active_years = recalculate_active_years()
        active_year = active_years.get(class_cat)

    if not active_year:
        return jsonify({"subjects": []})

    pushed_list = load_pushed_list(active_year, class_cat)

    return jsonify({
        "class": class_cat,
        "active_year": active_year,
        "subjects": [
            {
                "subject": subject,
                "year": active_year,
                "class": class_cat
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
# API — Active year for a specific class
# /api/push_active_year?class=JSS1
# ============================================================
@push_bp.route("/push_active_year", methods=["GET"])
def push_active_year():
    class_cat = normalize_class(request.args.get("class", ""))

    if not class_cat:
        return jsonify({"error": "Invalid class"}), 400

    active_year = get_active_year_for_class(class_cat)

    if not active_year:
        active = recalculate_active_years()
        active_year = active.get(class_cat)

    return jsonify({
        "class": class_cat,
        "year": active_year
    })


# ============================================================
# Detect available subject years
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
# API — Available Years
# ============================================================
@push_bp.route("/available-years", methods=["GET"])
def available_waec_years():
    return jsonify({
        "years": get_available_subject_years()
    })