# push.py — FINAL YEAR-AWARE EMIS PORTAL PUSH SYSTEM (2025–2026)
# -------------------------------------------------------------------
# Handles:
#   ✓ Push subjects into: static/portal/<YEAR>/<CLASS>/pushed_subjects.json
#   ✓ Tracks latest pushed YEAR for students
#   ✓ Students always receive correct latest pushed year (auto recalculated)
# -------------------------------------------------------------------

import os
import json
from flask import Blueprint, jsonify, request, session
from pathlib import Path

push_bp = Blueprint("push_bp", __name__)

BASE_DIR = Path(__file__).resolve().parent

# Where converted JSONs live
SUBJECTS_JSON_ROOT = BASE_DIR / "static" / "subjects"

# FINAL PUSH STORAGE
PORTAL_ROOT = BASE_DIR / "static" / "portal"
PORTAL_ROOT.mkdir(parents=True, exist_ok=True)

# WHERE WE STORE THE "LATEST YEAR"
LATEST_YEAR_FILE = PORTAL_ROOT / "latest_year.txt"


# ======================================================================
# Read latest pushed year
# ======================================================================
def get_latest_year():
    if LATEST_YEAR_FILE.exists():
        return LATEST_YEAR_FILE.read_text().strip()
    return None


# ======================================================================
# Write latest pushed year
# ======================================================================
def set_latest_year(year: str):
    LATEST_YEAR_FILE.write_text(str(year), encoding="utf-8")


# ======================================================================
# Remove latest year pointer
# ======================================================================
def clear_latest_year():
    if LATEST_YEAR_FILE.exists():
        LATEST_YEAR_FILE.unlink()


# ======================================================================
# Recalculate latest available year that STILL HAS pushed subjects
# ======================================================================
def recalculate_latest_year():
    """
    Looks inside static/portal/<YEAR>/<CLASS>/pushed_subjects.json
    and finds the most recent year with at least one pushed subject.
    """
    years = []

    for year_folder in PORTAL_ROOT.iterdir():
        if not year_folder.is_dir():
            continue

        year = year_folder.name

        # Check inside SS1/SS2/SS3
        for class_folder in year_folder.iterdir():
            if not class_folder.is_dir():
                continue

            p = class_folder / "pushed_subjects.json"
            if p.exists():
                try:
                    data = json.loads(p.read_text())
                    if data.get("subjects"):
                        years.append(year)
                        break
                except:
                    pass

    if not years:
        clear_latest_year()
        return None

    newest = max(years)  # pick the most recent
    set_latest_year(newest)
    return newest


# ======================================================================
# Load pushed subjects for YEAR + CLASS
# ======================================================================
def load_pushed_list(year: str, class_cat: str):
    path = PORTAL_ROOT / year / class_cat / "pushed_subjects.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("subjects", [])
    except:
        return []


# ======================================================================
# Save pushed list for YEAR + CLASS
# ======================================================================
def save_pushed_list(year: str, class_cat: str, subjects: list):
    folder = PORTAL_ROOT / year / class_cat
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "pushed_subjects.json"
    path.write_text(json.dumps({"subjects": subjects}, indent=4), encoding="utf-8")


# ======================================================================
# PUSH SUBJECTS
# ======================================================================
@push_bp.route("/push", methods=["POST"])
def push_subjects():
    payload = request.json

    raw_files = payload.get("files", [])
    target_class = payload.get("class_category")

    if not raw_files:
        return jsonify({"success": False, "error": "No files provided"}), 400

    if target_class not in ["SS1", "SS2", "SS3"]:
        return jsonify({"success": False, "error": "Invalid class"}), 400

    pushed_summary = []
    last_year_used = None

    for entry in raw_files:
        try:
            year, filename = entry.split(":", 1)
        except:
            return jsonify({"success": False, "error": f"Invalid entry: {entry}"}), 400

        year = str(year)
        last_year_used = year

        # READ SOURCE
        src = SUBJECTS_JSON_ROOT / year / "subjects-json" / target_class / filename
        if not src.exists():
            print(f"⚠ Missing JSON: {src}")
            continue

        try:
            content = json.loads(src.read_text(encoding="utf-8"))
        except:
            continue

        # WRITE TO PORTAL
        dst_folder = PORTAL_ROOT / year / target_class
        dst_folder.mkdir(parents=True, exist_ok=True)

        dst = dst_folder / filename
        dst.write_text(json.dumps(content, indent=4), encoding="utf-8")

        # UPDATE pushed list
        pushed_list = load_pushed_list(year, target_class)
        subject_name = filename.replace(".json", "").replace("_", " ").title()

        if subject_name not in pushed_list:
            pushed_list.append(subject_name)

        save_pushed_list(year, target_class, pushed_list)
        pushed_summary.append(subject_name)

    # FINAL: save last used year
    if last_year_used:
        set_latest_year(last_year_used)

    return jsonify({
        "success": True,
        "class": target_class,
        "subjects_pushed": pushed_summary,
        "latest_year": last_year_used
    })


# ======================================================================
# CLEAR PORTAL (YEAR + CLASS) — FIXED VERSION
# ======================================================================
@push_bp.route("/clear", methods=["POST"])
def clear_portal():
    import shutil

    payload = request.json
    year = str(payload.get("year"))
    target_class = payload.get("class_category")

    if target_class not in ["SS1", "SS2", "SS3", "ALL"]:
        return jsonify({"success": False, "error": "Invalid class"}), 400

    # ============================================================
    # 1️⃣ CLEAR EVERYTHING (ALL YEARS + ALL CLASSES)
    # ============================================================
    if year == "ALL" and target_class == "ALL":
        if PORTAL_ROOT.exists():
            shutil.rmtree(PORTAL_ROOT)  # remove entire portal directory
        PORTAL_ROOT.mkdir(parents=True, exist_ok=True)

        clear_latest_year()
        return jsonify({"success": True, "cleared": "ALL"})


    # ============================================================
    # 2️⃣ CLEAR SPECIFIC YEAR + ALL CLASSES
    # ============================================================
    if target_class == "ALL":
        year_folder = PORTAL_ROOT / year
        if year_folder.exists():
            shutil.rmtree(year_folder)  # delete entire year folder
        recalculate_latest_year()

        return jsonify({
            "success": True,
            "cleared": f"{year}-ALL"
        })


    # ============================================================
    # 3️⃣ CLEAR SPECIFIC YEAR + SPECIFIC CLASS
    # ============================================================
    class_folder = PORTAL_ROOT / year / target_class
    if class_folder.exists():
        shutil.rmtree(class_folder)  # remove class folder completely

    # After deletion, recreate class folder empty (optional)
    class_folder.mkdir(parents=True, exist_ok=True)

    # Save an empty pushed list
    save_pushed_list(year, target_class, [])

    # Recalculate latest year properly
    recalculate_latest_year()

    return jsonify({
        "success": True,
        "cleared": f"{year}-{target_class}"
    })


# ======================================================================
# STUDENT FETCH — ALWAYS GET TRUE LATEST YEAR
# ======================================================================
@push_bp.route("/get_pushed_subjects", methods=["GET"])
def student_get_pushed():
    student = session.get("student")
    if not student:
        return jsonify({"subjects": []})

    class_cat = student.get("class_category")

    latest_year = get_latest_year()
    if not latest_year:
        return jsonify({"subjects": []})

    pushed_list = load_pushed_list(latest_year, class_cat)

    return jsonify({
        "subjects": [
            {"subject": s, "year": latest_year, "class": class_cat}
            for s in pushed_list
        ]
    })



# ======================================================================
# Detect available WAEC years (subjects-json has at least one .json)
# ======================================================================
def get_available_subject_years():
    """
    Scans static/subjects/<YEAR>/subjects-json/** for JSON files.
    Returns sorted list of available years.
    """

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

        for root, _, files in os.walk(subjects_json_dir):
            for f in files:
                if f.endswith(".json"):
                    found_json = True
                    break
            if found_json:
                break

        if found_json:
            years.append(int(year))

    return sorted(years)


# ======================================================================
# API — Available WAEC Years (for Admin UI)
# ======================================================================
@push_bp.route("/available-years", methods=["GET"])
def available_waec_years():
    years = get_available_subject_years()
    return jsonify({
        "years": years
    })
