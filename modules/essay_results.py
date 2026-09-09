# modules/essay_results.py
# EMIS — Essay / Theory Results Extension

import csv
import json
import re
from pathlib import Path
from datetime import datetime
from threading import Lock

from flask import jsonify, request, session
from openpyxl import load_workbook

from modules.class_config import SUPPORTED_CLASSES, normalize_class_level


# ============================================================
# PATHS / CONSTANTS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
RESULTS_DIR = BASE_DIR / "RESULTS"
DATABASE_DIR = BASE_DIR / "static" / "data" / "database"
SUBJECTS_ROOT = BASE_DIR / "static" / "subjects"

MASTER_CSV = DATABASE_DIR / "students2026.csv"

CLASS_DATABASES = {
    "JSS1": DATABASE_DIR / "JSS1_Students.xlsx", "JSS2": DATABASE_DIR / "JSS2_Students.xlsx", "JSS3": DATABASE_DIR / "JSS3_Students.xlsx",
    "SS1": DATABASE_DIR / "SS1_Students.xlsx", "SS2": DATABASE_DIR / "SS2_Students.xlsx", "SS3": DATABASE_DIR / "SS3_Students.xlsx",
}

VALID_TERMS = {"FIRST", "SECOND", "THIRD"}

DEFAULT_OBJECTIVE_MAX = 60.0
DEFAULT_ESSAY_MAX = 40.0
DEFAULT_TOTAL_MAX = 100.0

ESSAY_FILE_NAME = "essay_scores.json"
ESSAY_LOCK = Lock()


# ============================================================
# BASIC HELPERS
# ============================================================

def can_manage_results():
    return str(session.get("user_type", "")).lower() in {"admin", "teacher"}


def clean_text(value):
    return str(value or "").strip()


def normalize_class(value):
    return normalize_class_level(value)


def is_jss_class(value):
    return clean_text(normalize_class(value)).upper().startswith("JSS")


def normalize_term(value):
    raw = clean_text(value).upper().replace("_", " ").replace("-", " ")
    raw = " ".join(raw.split())

    aliases = {
        "FIRST": "FIRST", "FIRST TERM": "FIRST", "TERM 1": "FIRST", "TERM ONE": "FIRST", "1": "FIRST", "1ST": "FIRST", "1ST TERM": "FIRST",
        "SECOND": "SECOND", "SECOND TERM": "SECOND", "TERM 2": "SECOND", "TERM TWO": "SECOND", "2": "SECOND", "2ND": "SECOND", "2ND TERM": "SECOND",
        "THIRD": "THIRD", "THIRD TERM": "THIRD", "TERM 3": "THIRD", "TERM THREE": "THIRD", "3": "THIRD", "3RD": "THIRD", "3RD TERM": "THIRD",
    }

    return aliases.get(raw, "")


def term_label(value):
    return {"FIRST": "1st Term", "SECOND": "2nd Term", "THIRD": "3rd Term"}.get(normalize_term(value), "")


def score_float(value, default=None):
    if value is None or str(value).strip() == "": return default

    try: return round(float(str(value).replace("%", "").strip()), 2)
    except (TypeError, ValueError): return default


def score_output(value):
    value = score_float(value)

    if value is None: return None
    return int(value) if float(value).is_integer() else value


def normalize_admission(value):
    return clean_text(value).upper()


def normalize_name(value):
    return " ".join(clean_text(value).upper().split())


def normalize_subject_key(value):
    value = clean_text(value).lower()
    value = re.sub(r"\.json$", "", value)
    value = re.sub(r"_(jss|ss)[123]$", "", value)
    value = re.sub(r"[^a-z0-9]+", "", value)
    return value


def subject_folder_name(value):
    value = clean_text(value).lower().replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", "_", value).strip("_")
    return value or "subject"


def now_string():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ============================================================
# STUDENT NAME
# ============================================================

def build_student_name(row):
    direct = clean_text(row.get("Student Name") or row.get("student_name") or row.get("full_name") or row.get("Name"))

    if direct: return direct

    last_name = clean_text(row.get("Last_name") or row.get("Last Name") or row.get("last_name"))
    first_name = clean_text(row.get("First_name") or row.get("First Name") or row.get("first_name"))
    other_names = clean_text(row.get("Other_names") or row.get("Other Names") or row.get("other_names"))

    return " ".join(part for part in (last_name, first_name, other_names) if part)


# ============================================================
# STUDENT ROW NORMALIZATION
# ============================================================

def normalize_student_row(row, class_level=""):
    class_level = normalize_class(class_level or row.get("Class_category") or row.get("Class Category") or row.get("Class Level") or row.get("Class"))
    class_arm = clean_text(row.get("Class") or row.get("Class_arm") or row.get("Class Arm") or class_level).upper()

    return {
        "admission_number": clean_text(row.get("Admission_number") or row.get("Admission No") or row.get("admission_number") or row.get("student_id")),
        "student_name": build_student_name(row),
        "class_level": class_level,
        "class_category": class_level,
        "class_arm": class_arm or class_level,
        "sex": clean_text(row.get("Sex") or row.get("sex")),
    }


# ============================================================
# READ CLASS XLSX DATABASE
# ============================================================

def read_class_xlsx(class_level):
    class_level = normalize_class(class_level)
    path = CLASS_DATABASES.get(class_level)

    if not path or not path.exists(): return []

    try:
        wb = load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))

        if len(rows) < 2:
            wb.close()
            return []

        headers = [clean_text(value) for value in rows[0]]
        students = []

        for values in rows[1:]:
            row = dict(zip(headers, list(values) + [None] * max(0, len(headers) - len(values))))
            student = normalize_student_row(row, class_level)

            if student["admission_number"] or student["student_name"]: students.append(student)

        wb.close()
        return students

    except Exception as error:
        print(f"ESSAY STUDENT XLSX READ ERROR [{path}]:", error)
        return []


# ============================================================
# READ MASTER CSV FALLBACK
# ============================================================

def read_master_csv(class_level):
    class_level = normalize_class(class_level)

    if not MASTER_CSV.exists(): return []

    try:
        students = []

        with MASTER_CSV.open("r", encoding="utf-8-sig", newline="") as file:
            for row in csv.DictReader(file):
                row_class = normalize_class(row.get("Class_category") or row.get("Class") or "")

                if row_class != class_level: continue

                student = normalize_student_row(row, class_level)

                if student["admission_number"] or student["student_name"]: students.append(student)

        return students

    except Exception as error:
        print("ESSAY MASTER CSV READ ERROR:", error)
        return []


# ============================================================
# GET CLASS ROSTER
# ============================================================

def get_class_roster(class_level, arm=""):
    class_level = normalize_class(class_level)
    arm = clean_text(arm).upper()

    students = read_class_xlsx(class_level)

    if not students: students = read_master_csv(class_level)

    unique = {}
    for student in students:
        key = normalize_admission(student.get("admission_number")) or normalize_name(student.get("student_name"))

        if not key: continue
        unique[key] = student

    students = list(unique.values())

    if arm and arm.lower() != "all":
        students = [student for student in students if clean_text(student.get("class_arm")).upper() == arm]

    students.sort(key=lambda student: (
        clean_text(student.get("student_name")).lower(),
        clean_text(student.get("admission_number")).lower(),
    ))

    return students


# ============================================================
# RESULT DIRECTORY
# ============================================================

def get_subject_result_dir(year, class_level, subject, term=""):
    class_level = normalize_class(class_level)
    subject_folder = subject_folder_name(subject)

    root = RESULTS_DIR / str(year) / "CLASS" / class_level

    if is_jss_class(class_level):
        term = normalize_term(term)
        if not term: return None

        return root / term / subject_folder

    return root / subject_folder


# ============================================================
# FIND EXISTING SUBJECT RESULT DIRECTORY
#
# Handles cases where the real result folder already exists with
# a slightly different spelling / underscore convention.
# ============================================================

def find_subject_result_dir(year, class_level, subject, term="", create=False):
    class_level = normalize_class(class_level)
    subject_key = normalize_subject_key(subject)

    root = RESULTS_DIR / str(year) / "CLASS" / class_level

    if is_jss_class(class_level):
        term = normalize_term(term)

        if not term: return None

        root = root / term

    if root.exists():
        for folder in root.iterdir():
            if folder.is_dir() and normalize_subject_key(folder.name) == subject_key:
                return folder

    preferred = get_subject_result_dir(year, class_level, subject, term)

    if preferred and create: preferred.mkdir(parents=True, exist_ok=True)

    return preferred


# ============================================================
# ESSAY STORAGE PATH
# ============================================================

def get_essay_score_path(year, class_level, subject, term="", create=False):
    folder = find_subject_result_dir(year, class_level, subject, term, create=create)

    return folder / ESSAY_FILE_NAME if folder else None


# ============================================================
# READ ESSAY STORE
# ============================================================

def read_essay_store(year, class_level, subject, term=""):
    path = get_essay_score_path(year, class_level, subject, term)

    if not path or not path.exists():
        return {
            "version": 1,
            "year": str(year),
            "class_level": normalize_class(class_level),
            "term": normalize_term(term) if is_jss_class(class_level) else "",
            "subject": clean_text(subject),
            "objective_max": DEFAULT_OBJECTIVE_MAX,
            "essay_max": DEFAULT_ESSAY_MAX,
            "total_max": DEFAULT_TOTAL_MAX,
            "scores": {},
        }

    try:
        with path.open("r", encoding="utf-8-sig") as file:
            data = json.load(file)

        if not isinstance(data, dict): data = {}
        if not isinstance(data.get("scores"), dict): data["scores"] = {}

        return data

    except Exception as error:
        print(f"ESSAY STORE READ ERROR [{path}]:", error)

        return {
            "version": 1,
            "year": str(year),
            "class_level": normalize_class(class_level),
            "term": normalize_term(term) if is_jss_class(class_level) else "",
            "subject": clean_text(subject),
            "objective_max": DEFAULT_OBJECTIVE_MAX,
            "essay_max": DEFAULT_ESSAY_MAX,
            "total_max": DEFAULT_TOTAL_MAX,
            "scores": {},
        }


# ============================================================
# WRITE ESSAY STORE — ATOMIC
# ============================================================

def write_essay_store(year, class_level, subject, term, data):
    path = get_essay_score_path(year, class_level, subject, term, create=True)

    if not path: raise ValueError("Could not resolve essay score path")

    path.parent.mkdir(parents=True, exist_ok=True)

    temporary = path.with_suffix(".tmp")

    with ESSAY_LOCK:
        with temporary.open("w", encoding="utf-8") as file:
            json.dump(data, file, indent=2, ensure_ascii=False)

        temporary.replace(path)

    return path


# ============================================================
# MASTER EXAM JSON DIRECTORY
# ============================================================

def get_subject_json_directory(year, class_level, term=""):
    class_level = normalize_class(class_level)

    directory = SUBJECTS_ROOT / str(year) / "subjects-json" / class_level

    if is_jss_class(class_level):
        term = normalize_term(term)

        if not term: return None

        directory = directory / term

    return directory


# ============================================================
# FIND SUBJECT JSON
# ============================================================

def find_subject_json(year, class_level, subject, term=""):
    directory = get_subject_json_directory(year, class_level, term)

    if not directory or not directory.exists(): return None, {}

    requested_key = normalize_subject_key(subject)

    for path in sorted(directory.glob("*.json")):
        if path.name.lower() == "pushed_subjects.json": continue

        try:
            with path.open("r", encoding="utf-8-sig") as file:
                data = json.load(file)

            if not isinstance(data, dict): continue

            subject_name = data.get("subject") or path.stem

            if normalize_subject_key(path.stem) == requested_key or normalize_subject_key(subject_name) == requested_key:
                return path, data

        except Exception:
            continue

    return None, {}


# ============================================================
# ESSAY AVAILABILITY
# ============================================================

def get_exam_essay_config(year, class_level, subject, term=""):
    _, data = find_subject_json(year, class_level, subject, term)

    essay = data.get("essay") if isinstance(data, dict) else None
    questions = essay.get("questions", []) if isinstance(essay, dict) else []

    available = isinstance(questions, list) and len(questions) > 0

    essay_max = score_float(
        essay.get("max_score") if isinstance(essay, dict) else None,
        DEFAULT_ESSAY_MAX,
    )

    if essay_max is None or essay_max <= 0: essay_max = DEFAULT_ESSAY_MAX

    objective_max = round(DEFAULT_TOTAL_MAX - essay_max, 2) if available else DEFAULT_TOTAL_MAX

    return {
        "essay_available": available,
        "essay_questions": len(questions) if isinstance(questions, list) else 0,
        "essay_title": clean_text(essay.get("title")) if isinstance(essay, dict) else "",
        "objective_max": objective_max,
        "essay_max": essay_max if available else 0.0,
        "total_max": DEFAULT_TOTAL_MAX,
    }


# ============================================================
# READ OBJECTIVE RESULTS DIRECTLY
# ============================================================

def read_objective_results(year, class_level, subject, term=""):
    folder = find_subject_result_dir(year, class_level, subject, term)

    if not folder: return []

    path = folder / "results.xlsx"

    if not path.exists(): return []

    try:
        wb = load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))

        if len(rows) < 2:
            wb.close()
            return []

        headers = [clean_text(value) for value in rows[0]]
        results = []

        for values in rows[1:]:
            values = list(values)
            values += [None] * max(0, len(headers) - len(values))

            row = dict(zip(headers, values[:len(headers)]))

            if row.get("Student Name") or row.get("Admission No"): results.append(row)

        wb.close()
        return results

    except Exception as error:
        print(f"ESSAY OBJECTIVE READ ERROR [{path}]:", error)
        return []


# ============================================================
# OBJECTIVE LOOKUP
# ============================================================

def build_objective_lookup(records):
    lookup = {}

    for row in records:
        admission = normalize_admission(row.get("Admission No") or row.get("Admission_number") or row.get("admission_number"))
        name = normalize_name(row.get("Student Name") or row.get("student_name") or row.get("full_name"))

        if admission: lookup[f"ADM::{admission}"] = row
        if name: lookup[f"NAME::{name}"] = row

    return lookup


def find_objective_record(lookup, admission="", student_name=""):
    admission = normalize_admission(admission)
    student_name = normalize_name(student_name)

    if admission and f"ADM::{admission}" in lookup: return lookup[f"ADM::{admission}"]
    if student_name and f"NAME::{student_name}" in lookup: return lookup[f"NAME::{student_name}"]

    return None


# ============================================================
# OBJECTIVE CALCULATION
#
# Example:
#   64 correct / 80 questions
#   Objective component = 60
#
#   64 / 80 × 60 = 48
# ============================================================

def calculate_objective_component(row, objective_max):
    if not isinstance(row, dict): return None, None, None

    correct = score_float(row.get("Correct") or row.get("correct"))
    total_questions = score_float(row.get("Total") or row.get("total") or row.get("total_questions"))

    if correct is not None and total_questions is not None and total_questions > 0:
        score = round((correct / total_questions) * float(objective_max), 2)
        return score, correct, total_questions

    percentage = score_float(
        row.get("Score (%)")
        or row.get("Score Number")
        or row.get("score_percentage")
        or row.get("percentage")
    )

    if percentage is not None:
        score = round((percentage / 100.0) * float(objective_max), 2)
        return score, correct, total_questions

    return None, correct, total_questions


# ============================================================
# FIND SAVED ESSAY SCORE
# ============================================================

def find_saved_score(store, admission="", student_name=""):
    scores = store.get("scores", {}) if isinstance(store, dict) else {}

    if not isinstance(scores, dict): return None, None

    admission_key = normalize_admission(admission)
    name_key = normalize_name(student_name)

    if admission_key and admission_key in scores:
        entry = scores.get(admission_key)
        return score_float(entry.get("score")) if isinstance(entry, dict) else score_float(entry), entry

    for key, entry in scores.items():
        if not isinstance(entry, dict): continue

        entry_admission = normalize_admission(entry.get("admission_number"))
        entry_name = normalize_name(entry.get("student_name"))

        if admission_key and entry_admission == admission_key: return score_float(entry.get("score")), entry
        if not admission_key and name_key and entry_name == name_key: return score_float(entry.get("score")), entry

    return None, None


# ============================================================
# BUILD COMBINED SCORE
# ============================================================

def build_score_components(objective_row, essay_score, config):
    essay_available = bool(config.get("essay_available"))
    objective_max = score_float(config.get("objective_max"), DEFAULT_OBJECTIVE_MAX)
    essay_max = score_float(config.get("essay_max"), DEFAULT_ESSAY_MAX if essay_available else 0.0)

    objective_score, correct, total_questions = calculate_objective_component(objective_row, objective_max)

    has_objective = objective_score is not None
    has_essay = essay_score is not None

    if not essay_available:
        final_score = objective_score
        state = "COMPLETE" if has_objective else "PENDING"

    elif has_objective and has_essay:
        final_score = round(objective_score + essay_score, 2)
        state = "COMPLETE"

    elif has_objective:
        final_score = None
        state = "AWAITING ESSAY"

    elif has_essay:
        final_score = None
        state = "AWAITING OBJECTIVE"

    else:
        final_score = None
        state = "PENDING"

    final_status = ""

    if state == "COMPLETE" and final_score is not None:
        final_status = "PASS" if final_score >= 50 else "FAIL"

    return {
        "has_objective": has_objective,
        "objective_score": score_output(objective_score),
        "objective_max": score_output(objective_max),
        "objective_correct": score_output(correct),
        "objective_total": score_output(total_questions),

        "essay_available": essay_available,
        "has_essay": essay_available,
        "essay_score": score_output(essay_score),
        "essay_max": score_output(essay_max),

        "final_score": score_output(final_score),
        "combined_score": score_output(final_score),
        "total_score": score_output(final_score),
        "total_max": 100,

        "result_state": state,
        "final_status": final_status,
    }


# ============================================================
# ENRICH EXISTING ADMIN OBJECTIVE RESULTS
#
# Called from api_routes.py after existing result rows are read.
# ============================================================

def enrich_results_with_essay(records, class_level, subject, year, term=""):
    if not isinstance(records, list): return records

    class_level = normalize_class(class_level)

    if not class_level or class_level not in SUPPORTED_CLASSES: return records

    term = normalize_term(term) if is_jss_class(class_level) else ""

    config = get_exam_essay_config(year, class_level, subject, term)
    store = read_essay_store(year, class_level, subject, term)

    for row in records:
        if not isinstance(row, dict): continue

        admission = row.get("Admission No") or row.get("Admission_number") or row.get("admission_number")
        student_name = row.get("Student Name") or row.get("student_name") or row.get("full_name")

        essay_score, _ = find_saved_score(store, admission, student_name)
        components = build_score_components(row, essay_score, config)

        row.update(components)

        row["Essay Available"] = components["essay_available"]
        row["Essay Score"] = components["essay_score"] if components["essay_score"] is not None else ""
        row["Essay Max"] = components["essay_max"]

        row["Objective Score"] = components["objective_score"] if components["objective_score"] is not None else ""
        row["Objective Max"] = components["objective_max"]

        row["Final Score"] = components["final_score"] if components["final_score"] is not None else ""
        row["Final Max"] = 100
        row["Result State"] = components["result_state"]

    return records


# ============================================================
# BUILD ESSAY ROSTER
# ============================================================

def build_essay_roster(year, class_level, subject, term="", arm=""):
    class_level = normalize_class(class_level)
    term = normalize_term(term) if is_jss_class(class_level) else ""

    config = get_exam_essay_config(year, class_level, subject, term)
    store = read_essay_store(year, class_level, subject, term)

    objective_records = read_objective_results(year, class_level, subject, term)
    objective_lookup = build_objective_lookup(objective_records)

    students = get_class_roster(class_level, arm)

    roster = []

    for student in students:
        admission = student.get("admission_number", "")
        student_name = student.get("student_name", "")

        objective = find_objective_record(objective_lookup, admission, student_name)
        essay_score, saved_entry = find_saved_score(store, admission, student_name)

        components = build_score_components(objective, essay_score, config)

        roster.append({
            **student,
            **components,
            "essay_saved": saved_entry is not None,
            "essay_updated_at": clean_text(saved_entry.get("updated_at")) if isinstance(saved_entry, dict) else "",
        })

    return roster, config


# ============================================================
# REGISTER ROUTES ON EXISTING api_bp
#
# This keeps all endpoints under the same existing API blueprint.
# No second Blueprint registration is required in app.py.
# ============================================================

def register_essay_routes(api_bp):

    # ========================================================
    # GET ESSAY ROSTER / SCORES
    #
    # /api/results/essay
    #   ?year=2017
    #   &class=JSS1
    #   &term=FIRST
    #   &subject=mathematics
    #   &arm=JSS1A
    # ========================================================

    @api_bp.route("/api/results/essay", methods=["GET"])
    def get_essay_scores():
        if not can_manage_results(): return jsonify({"error": "Unauthorized", "students": []}), 403

        year = clean_text(request.args.get("year"))
        class_level = normalize_class(request.args.get("class") or request.args.get("class_level"))
        subject = clean_text(request.args.get("subject"))
        term = normalize_term(request.args.get("term"))
        arm = clean_text(request.args.get("arm"))

        if not year or not year.isdigit(): return jsonify({"error": "Invalid or missing year", "students": []}), 400
        if class_level not in SUPPORTED_CLASSES: return jsonify({"error": "Invalid or missing class", "students": []}), 400
        if not subject: return jsonify({"error": "Subject is required", "students": []}), 400
        if is_jss_class(class_level) and not term: return jsonify({"error": "Term is required for JSS essay scores", "students": []}), 400

        if not is_jss_class(class_level): term = ""

        try:
            students, config = build_essay_roster(year, class_level, subject, term, arm)

            return jsonify({
                "success": True,
                "year": year,
                "class": class_level,
                "class_level": class_level,
                "arm": arm,
                "term": term,
                "term_label": term_label(term),
                "subject": subject,

                "essay_available": config["essay_available"],
                "essay_questions": config["essay_questions"],
                "essay_title": config["essay_title"],

                "objective_max": score_output(config["objective_max"]),
                "essay_max": score_output(config["essay_max"]),
                "total_max": 100,

                "student_count": len(students),
                "students": students,
            }), 200

        except Exception as error:
            print("GET ESSAY SCORES ERROR:", error)
            return jsonify({"error": "Failed to load essay scores", "details": str(error), "students": []}), 500


    # ========================================================
    # SAVE ESSAY SCORES
    #
    # POST /api/results/essay/save
    # ========================================================

    @api_bp.route("/api/results/essay/save", methods=["POST"])
    def save_essay_scores():
        if not can_manage_results(): return jsonify({"error": "Unauthorized"}), 403

        data = request.get_json(silent=True) or {}

        year = clean_text(data.get("year"))
        class_level = normalize_class(data.get("class") or data.get("class_level"))
        subject = clean_text(data.get("subject"))
        term = normalize_term(data.get("term"))
        scores = data.get("scores", [])

        if not year or not year.isdigit(): return jsonify({"error": "Invalid or missing year"}), 400
        if class_level not in SUPPORTED_CLASSES: return jsonify({"error": "Invalid or missing class"}), 400
        if not subject: return jsonify({"error": "Subject is required"}), 400
        if is_jss_class(class_level) and not term: return jsonify({"error": "Term is required for JSS essay scores"}), 400
        if not isinstance(scores, list) or not scores: return jsonify({"error": "No essay scores supplied"}), 400

        if not is_jss_class(class_level): term = ""

        config = get_exam_essay_config(year, class_level, subject, term)

        if not config["essay_available"]:
            return jsonify({"error": "This examination does not contain an essay / theory section"}), 400

        essay_max = score_float(config.get("essay_max"), DEFAULT_ESSAY_MAX)

        roster = get_class_roster(class_level)
        valid_students = {}

        for student in roster:
            admission_key = normalize_admission(student.get("admission_number"))

            if admission_key: valid_students[admission_key] = student

        store = read_essay_store(year, class_level, subject, term)

        store.update({
            "version": 1,
            "year": year,
            "class_level": class_level,
            "class_category": class_level,
            "term": term,
            "term_label": term_label(term),
            "subject": subject,
            "objective_max": score_output(config["objective_max"]),
            "essay_max": score_output(essay_max),
            "total_max": 100,
            "updated_at": now_string(),
        })

        if not isinstance(store.get("scores"), dict): store["scores"] = {}

        saved = 0
        cleared = 0
        rejected = []

        for item in scores:
            if not isinstance(item, dict): continue

            admission = clean_text(item.get("admission_number") or item.get("Admission_number"))
            admission_key = normalize_admission(admission)

            student_name = clean_text(item.get("student_name"))
            class_arm = clean_text(item.get("class_arm")).upper()

            if not admission_key:
                rejected.append({"student_name": student_name, "reason": "Missing admission number"})
                continue

            roster_student = valid_students.get(admission_key)

            if not roster_student:
                rejected.append({"admission_number": admission, "student_name": student_name, "reason": "Student was not found in the class database"})
                continue

            value = item.get("score")

            # Null / blank removes an existing essay score.
            if value is None or str(value).strip() == "":
                if admission_key in store["scores"]:
                    store["scores"].pop(admission_key, None)
                    cleared += 1

                continue

            score = score_float(value)

            if score is None:
                rejected.append({"admission_number": admission, "student_name": student_name, "reason": "Invalid score"})
                continue

            if score < 0 or score > essay_max:
                rejected.append({
                    "admission_number": admission,
                    "student_name": student_name,
                    "reason": f"Essay score must be between 0 and {score_output(essay_max)}",
                })
                continue

            store["scores"][admission_key] = {
                "admission_number": roster_student.get("admission_number") or admission,
                "student_name": roster_student.get("student_name") or student_name,
                "class_arm": roster_student.get("class_arm") or class_arm,
                "score": score_output(score),
                "updated_at": now_string(),
                "updated_by": clean_text(session.get("username") or session.get("user_name") or session.get("user_type") or "teacher"),
            }

            saved += 1

        if not saved and not cleared and rejected:
            return jsonify({"error": "No valid essay scores were saved", "rejected": rejected}), 400

        path = write_essay_store(year, class_level, subject, term, store)

        return jsonify({
            "success": True,
            "message": "Essay scores saved successfully.",
            "saved_count": saved,
            "cleared_count": cleared,
            "rejected_count": len(rejected),
            "rejected": rejected,
            "year": year,
            "class": class_level,
            "term": term,
            "subject": subject,
            "essay_max": score_output(essay_max),
            "path": str(path),
        }), 200