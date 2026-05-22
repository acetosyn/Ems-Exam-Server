# modules/student_portal.py

from flask import Blueprint, render_template, redirect, url_for, session, request, jsonify
from pathlib import Path
from datetime import datetime
import json
import os
from modules.supabase_results import save_exam_result_to_supabase, get_academic_settings
from modules.supabase_results import save_exam_result_to_supabase
from modules.student_results import save_result, get_latest_result
from modules.excel_manager import read_results
from modules.class_config import get_subjects_for_class
from push import get_latest_year


student_portal_bp = Blueprint("student_portal_bp", __name__)


# -----------------------------------------------------------
# SUBJECT NORMALIZATION
# Converts display subject names to JSON filename base names.
# Example:
#   English Language + JSS1 => english_jss1.json
# -----------------------------------------------------------
BASE_SUBJECT_MAP = {
    # Existing SS subjects
    "biology": "biology",
    "chemistry": "chemistry",

    "civic education": "civic",
    "civic": "civic",

    "computer science": "computer_science",
    "computer studies": "computer_science",
    "computer": "computer_science",

    "economics": "economics",

    "english language": "english",
    "english": "english",

    "financial accounting": "accounts",
    "financial account": "accounts",
    "accounting": "accounts",
    "accounts": "accounts",

    "geography": "geography",
    "government": "government",

    "literature-in-english": "literature",
    "literature in english": "literature",
    "literature": "literature",

    "mathematics": "mathematics",
    "maths": "mathematics",

    "physics": "physics",

    "technical drawing": "technical",
    "technical": "technical",

    # New JSS / full-school subjects
    "yoruba language": "yoruba",
    "yoruba": "yoruba",

    "history": "history",

    "irk": "irk",
    "irs": "irs",

    "cca": "cca",

    "arabic language": "arabic",
    "arabic": "arabic",

    "business studies": "business_studies",

    "poise": "poise",

    "islamiyyah": "islamiyyah",

    "hort & crop production": "hort_crop_production",
    "hort and crop production": "hort_crop_production",

    "digital tech.": "digital_tech",
    "digital tech": "digital_tech",
    "digital technology": "digital_tech",

    "inter science": "inter_science",
    "integrated science": "inter_science",

    "garment making": "garment_making",

    "soc. & cit. std": "soc_cit_std",
    "soc & cit std": "soc_cit_std",
    "social and citizenship studies": "soc_cit_std",

    "p.h.e": "phe",
    "phe": "phe",
    "physical health education": "phe",

    "bst": "bst",

    "national value": "national_value",
    "national values": "national_value",

    "pvs": "pvs",

    "hausa language": "hausa",
    "hausa": "hausa",

    "cit & her. std": "cit_her_std",
    "cit and her std": "cit_her_std",
    "civic and heritage studies": "cit_her_std",

    "commerce": "commerce",

    "marketing": "marketing",

    "further mathematics": "further_mathematics",
    "further maths": "further_mathematics",

    "agricultural science": "agricultural_science",
    "agriculture": "agricultural_science",
}


# =======================================================
# Helper — Student login validation
# =======================================================
def get_logged_in_student():
    if session.get("user_type") != "student":
        return None
    return session.get("student")


# =======================================================
# Helper — Build full name safely
# =======================================================
def get_student_full_name(student):
    full_name = student.get("full_name")

    if full_name:
        return str(full_name).strip()

    return " ".join([
        str(student.get("last_name", "")).strip(),
        str(student.get("first_name", "")).strip(),
        str(student.get("other_names", "")).strip(),
    ]).strip()


# =======================================================
# Helper — Normalize subject filename
# =======================================================
def normalize_subject_base(subject):
    key = str(subject or "").strip().lower()

    base_name = BASE_SUBJECT_MAP.get(key)

    if base_name:
        return base_name

    return (
        key.replace("&", "and")
           .replace(".", "")
           .replace("-", "_")
           .replace("/", "_")
           .replace(" ", "_")
    )


# =======================================================
# Student Dashboard
# =======================================================
@student_portal_bp.route("/student_portal")
def student_portal():
    student = get_logged_in_student()
    if not student:
        return redirect(url_for("user_bp.student_login"))

    class_category = str(student.get("class_category", "")).upper().strip()
    subjects = get_subjects_for_class(class_category)

    return render_template(
        "students.html",
        student=student,
        subjects=subjects,
        class_category=class_category,
        exam_started=session.get("exam_started", False),
        exam_submitted=session.get("exam_submitted", False)
    )


# =======================================================
# Exam Dashboard — JSS1 to SS3 + Year Aware
# =======================================================
@student_portal_bp.route("/exam_dashboard")
def exam_dashboard():
    student = get_logged_in_student()
    if not student:
        return redirect(url_for("user_bp.student_login"))

    subject_raw = request.args.get("subject", "").strip()
    if not subject_raw:
        return redirect(url_for("student_portal_bp.student_portal"))

    subject_display = subject_raw.upper()

    # ------------------------------------------------------
    # 1. GET YEAR: querystring → latest_year.txt → current year
    # ------------------------------------------------------
    year = request.args.get("year")

    if not year:
        latest = get_latest_year()
        year = latest if latest else str(datetime.now().year)

    year = str(year).strip()

    # ------------------------------------------------------
    # 2. Student + subject meta
    # ------------------------------------------------------
    class_category = str(student.get("class_category", "")).upper().strip()

    if not class_category:
        return redirect(url_for("student_portal_bp.student_portal"))

    class_suffix = class_category.lower()

    full_name = get_student_full_name(student)
    admission_no = str(student.get("admission_number", "")).strip()

    # ------------------------------------------------------
    # 3. Normalize subject → JSON filename
    # ------------------------------------------------------
    base_name = normalize_subject_base(subject_raw)
    json_filename = f"{base_name}_{class_suffix}.json"

    # Example:
    # static/subjects/2026/subjects-json/JSS1/mathematics_jss1.json
    json_path = Path(
        f"static/subjects/{year}/subjects-json/{class_category}/{json_filename}"
    )

    exam_available = json_path.exists()

    # ------------------------------------------------------
    # 4. Check submission history
    # ------------------------------------------------------
    existing_results = read_results(class_category, subject_display, year)

    already_written = False
    for r in existing_results:
        name = str(r.get("Student Name", "")).upper().strip()
        adm = str(r.get("Admission No", "")).upper().strip()

        if name == full_name.upper() and adm == admission_no.upper():
            already_written = True
            break

    # ------------------------------------------------------
    # 5. Save to session for exam page/core JS
    # ------------------------------------------------------
    session["selected_subject"] = subject_display
    session["selected_year"] = year
    session["exam_submitted"] = already_written

    return render_template(
        "exam_dashboard.html",
        student=student,
        subject=subject_display,
        year=year,
        already_written=already_written,
        exam_available=exam_available,
        full_name=full_name,
        admission_number=admission_no,
        class_name=student.get("class"),
        class_category=class_category,
        system_id=student.get("id"),
        exam_started=session.get("exam_started", False),
        exam_submitted=session.get("exam_submitted", already_written)
    )


# =======================================================
# Submit Exam — JSS1 to SS3 + Year Aware + Supabase Save
# =======================================================
@student_portal_bp.route("/submit_exam", methods=["POST"])
def submit_exam():
    student = get_logged_in_student()
    if not student:
        return jsonify({"error": "Not logged in"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid"}), 400

    subject = str(data.get("subject", "")).upper().strip()
    class_category = str(student.get("class_category", "")).upper().strip()
    full_name = get_student_full_name(student)
    admission_no = str(student.get("admission_number", "")).strip()

    year = str(session.get("selected_year", datetime.now().year))

    # Get active academic session + term from Supabase settings
    try:
        academic_settings = get_academic_settings()
        academic_session = str(
            academic_settings.get("current_session", "2025/2026")
        ).strip()
        term = str(
            academic_settings.get("current_term", "SECOND TERM")
        ).upper().strip()

    except Exception as e:
        print("ACADEMIC SETTINGS FETCH ERROR:", e)
        academic_session = "2025/2026"
        term = "SECOND TERM"

    previous = read_results(class_category, subject, year)

    for r in previous:
        if (
            str(r.get("Student Name", "")).upper().strip() == full_name.upper()
            and str(r.get("Admission No", "")).upper().strip() == admission_no.upper()
        ):
            return jsonify({"error": "Exam already submitted"}), 403

    now = datetime.now()

    data.update({
        "student_id": student.get("id") or admission_no,
        "full_name": full_name,
        "admission_number": admission_no,
        "class_name": student.get("class"),
        "class_category": class_category,
        "year": year,
        "subject": subject,

        "academic_session": academic_session,
        "term": term,

        "submitted_at": now.strftime("%Y-%m-%d %H:%M"),
        "date_written": now.strftime("%Y-%m-%d"),
        "day_written": now.strftime("%A"),
        "time_written": now.strftime("%I:%M %p"),
    })

    # 1. Save locally as before
    save_result(data)

    # 2. Also save to Supabase
    try:
        save_exam_result_to_supabase(data)
    except Exception as e:
        print("SUPABASE SAVE ERROR:", e)

    session["exam_submitted"] = True
    session["exam_started"] = False

    return jsonify({
        "status": "ok",
        "academic_session": academic_session,
        "term": term
    })


# =======================================================
# Start Exam
# =======================================================
@student_portal_bp.route("/start_exam", methods=["POST"])
def start_exam():
    student = get_logged_in_student()
    if not student:
        return redirect(url_for("user_bp.student_login"))

    if session.get("exam_submitted"):
        return redirect(url_for("student_portal_bp.result"))

    session["exam_started"] = True

    subject = session.get("selected_subject")
    year = session.get("selected_year") or str(datetime.now().year)

    return redirect(url_for(
        "student_portal_bp.exam",
        subject=subject,
        year=year
    ))


# =======================================================
# Exam Page
# =======================================================
@student_portal_bp.route("/exam")
def exam():
    student = get_logged_in_student()
    if not student:
        return redirect(url_for("user_bp.student_login"))

    subject = request.args.get("subject", "").strip()
    year = request.args.get("year") or session.get("selected_year") or str(datetime.now().year)

    session["selected_year"] = str(year)

    return render_template(
        "exam.html",
        student=student,
        subject=subject,
        year=year,
        exam_started=session.get("exam_started", False)
    )


# =======================================================
# Result Page
# =======================================================
@student_portal_bp.route("/result")
def result():
    student = get_logged_in_student()
    if not student:
        return redirect(url_for("user_bp.student_login"))

    student_id = student.get("id") or student.get("admission_number")
    latest = get_latest_result(student_id)

    if not latest:
        latest = {
            "score": 0,
            "correct": 0,
            "incorrect": 0,
            "total": 0,
            "answered": 0,
            "skipped": 0,
            "flagged": 0,
            "tabSwitches": 0,
            "time_taken": 0,
            "subject": session.get("selected_subject", "Unknown"),
            "submitted_at": None,
            "status": "No record"
        }

    return render_template("result.html", student=student, result=latest)


# =======================================================
# API — Fetch pushed subjects
# =======================================================
@student_portal_bp.route("/api/student/subjects")
def api_student_subjects():
    student = get_logged_in_student()
    if not student:
        return jsonify({"subjects": []})

    class_cat = str(student.get("class_category", "")).upper().strip()
    year = request.args.get("year", "").strip()

    if not year:
        latest = get_latest_year()
        year = latest if latest else str(datetime.now().year)

    json_path = Path(f"static/portal/{year}/{class_cat}/pushed_subjects.json")

    if not json_path.exists():
        # fallback to official class subject list
        return jsonify({
            "subjects": get_subjects_for_class(class_cat)
        })

    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))

        if isinstance(data, dict):
            return jsonify({"subjects": data.get("subjects", [])})

        if isinstance(data, list):
            return jsonify({"subjects": data})

        return jsonify({"subjects": []})

    except Exception:
        return jsonify({"subjects": []})


@student_portal_bp.route("/back_to_exam_dashboard")
def back_to_exam_dashboard():
    subject = session.get("selected_subject")
    year = session.get("selected_year")

    if subject:
        return redirect(url_for(
            "student_portal_bp.exam_dashboard",
            subject=subject,
            year=year
        ))

    return redirect(url_for("student_portal_bp.student_portal"))