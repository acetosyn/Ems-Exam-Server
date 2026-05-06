# modules/student_portal.py

from flask import Blueprint, render_template, redirect, url_for, session, request, jsonify
from pathlib import Path
from datetime import datetime
from modules.student_results import save_result, get_latest_result
from modules.excel_manager import read_results
from push import get_latest_year 

student_portal_bp = Blueprint('student_portal_bp', __name__)

DEFAULT_SUBJECTS = [
    "BIOLOGY",
    "CHEMISTRY",
    "CIVIC EDUCATION",
    "COMPUTER SCIENCE",
    "ECONOMICS",
    "ENGLISH LANGUAGE",
    "FINANCIAL ACCOUNTING",
    "GEOGRAPHY",
    "GOVERNMENT",
    "LITERATURE-IN-ENGLISH",
    "MATHEMATICS",
    "PHYSICS",
    "TECHNICAL DRAWING"
]

# -----------------------------------------------------------
# SUBJECT NORMALIZATION (NO CLASS — JUST BASE NAME)
# -----------------------------------------------------------
BASE_SUBJECT_MAP = {
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
}

# =======================================================
# Helper — Student login validation
# =======================================================
def get_logged_in_student():
    if session.get('user_type') != 'student':
        return None
    return session.get('student')


# =======================================================
# Student Dashboard
# =======================================================
@student_portal_bp.route('/student_portal')
def student_portal():
    student = get_logged_in_student()
    if not student:
        return redirect(url_for('user_bp.student_login'))

    return render_template(
        'students.html',
        student=student,
        subjects=DEFAULT_SUBJECTS,
        exam_started=session.get('exam_started', False),
        exam_submitted=session.get('exam_submitted', False)
    )


# =======================================================
# Exam Dashboard (UPDATED WITH TRUE LATEST YEAR LOGIC)
# =======================================================
@student_portal_bp.route('/exam_dashboard')
def exam_dashboard():
      # ⭐ import inside to avoid circular imports

    student = get_logged_in_student()
    if not student:
        return redirect(url_for('user_bp.student_login'))

    subject_raw = request.args.get('subject', '').strip().upper()
    if not subject_raw:
        return redirect(url_for('student_portal_bp.student_portal'))

    # ------------------------------------------------------
    # 1️⃣ GET YEAR: Priority = querystring → latest_year.txt → current year
    # ------------------------------------------------------
    year = request.args.get("year")

    if not year:
        # Load from portal/latest_year.txt
        latest = get_latest_year()
        if latest:
            year = latest
        else:
            year = str(datetime.now().year)  # LAST fallback (rare)

    # Ensure string
    year = str(year)

    # ------------------------------------------------------
    # Student + subject meta
    # ------------------------------------------------------
    class_category = student.get("class_category")  # SS1 / SS2 / SS3
    class_suffix   = class_category.lower()

    full_name    = student.get("full_name")
    admission_no = student.get("admission_number")

    # ------------------------------------------------------
    # Normalize subject → base folder name
    # ------------------------------------------------------
    key       = subject_raw.lower()
    base_name = BASE_SUBJECT_MAP.get(key)

    if not base_name:
        base_name = key.replace(" ", "_").replace("-", "_")

    json_filename = f"{base_name}_{class_suffix}.json"

    # ------------------------------------------------------
    # Check JSON exists for THIS YEAR (correct dynamic year!)
    # ------------------------------------------------------
    json_path = Path(f"static/subjects/{year}/subjects-json/{class_category}/{json_filename}")
    exam_available = json_path.exists()

    # ------------------------------------------------------
    # Check submission history (YEAR AWARE)
    # ------------------------------------------------------
    existing_results = read_results(class_category, subject_raw, year)

    already_written = False
    for r in existing_results:
        name = str(r.get("Student Name", "")).upper()
        adm  = str(r.get("Admission No", "")).upper()

        if name == full_name.upper() and adm == admission_no.upper():
            already_written = True
            break

    # ------------------------------------------------------
    # SAVE to session for later exam loading
    # ------------------------------------------------------
    session['selected_subject'] = subject_raw
    session['selected_year']    = year          # ⭐ important
    session['exam_submitted']   = already_written

    # ------------------------------------------------------
    # Render dashboard
    # ------------------------------------------------------
    return render_template(
        'exam_dashboard.html',
        student=student,
        subject=subject_raw,
        year=year,                            # ⭐ correct dynamic year
        already_written=already_written,
        exam_available=exam_available,
        full_name=full_name,
        admission_number=admission_no,
        class_name=student.get("class"),
        class_category=class_category,
        system_id=student.get("id"),
        exam_started=session.get('exam_started', False),
        exam_submitted=session.get('exam_submitted', already_written)
    )



# =======================================================
# SUBMIT EXAM (YEAR-AWARE)
# =======================================================
@student_portal_bp.route('/submit_exam', methods=['POST'])
def submit_exam():
    student = get_logged_in_student()
    if not student:
        return jsonify({"error": "Not logged in"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid"}), 400

    subject = data.get("subject", "").upper()
    class_category = student.get("class_category")
    full_name = student.get("full_name")
    admission_no = student.get("admission_number")

    # Get YEAR from session
    year = session.get("selected_year", str(datetime.now().year))

    # ---------------------------------------------------
    # YEAR-AWARE duplicate check
    # ---------------------------------------------------
    previous = read_results(class_category, subject, year)
    for r in previous:
        if (
            str(r.get("Student Name", "")).upper() == full_name.upper() and
            str(r.get("Admission No", "")).upper() == admission_no.upper()
        ):
            return jsonify({"error": "Exam already submitted"}), 403

    # ---------------------------------------------------
    # Add required result fields
    # ---------------------------------------------------
    data.update({
        "student_id": student.get("id"),
        "full_name": full_name,
        "admission_number": admission_no,
        "class_name": student.get("class"),
        "class_category": class_category,
        "year": year,                    # ✅ REQUIRED
    })

    save_result(data)

    session['exam_submitted'] = True
    session['exam_started'] = False

    return jsonify({"status": "ok"})



@student_portal_bp.route('/start_exam', methods=['POST'])
def start_exam():
    student = get_logged_in_student()
    if not student:
        return redirect(url_for('user_bp.student_login'))

    # If already submitted, do not allow restart
    if session.get('exam_submitted'):
        return redirect(url_for('student_portal_bp.result'))

    # Mark exam as started
    session['exam_started'] = True

    # -----------------------------------------------------
    # Get subject + year from session (set by exam_dashboard)
    # -----------------------------------------------------
    subject = session.get("selected_subject")

    # MOST IMPORTANT: year must be EXACT from session
    year = session.get("selected_year")
    if not year:
        # LAST fallback (rare)
        year = str(datetime.now().year)

    # Redirect to /exam with correct year + subject
    return redirect(url_for(
        'student_portal_bp.exam',
        subject=subject,
        year=year
    ))



# =======================================================
# EXAM PAGE — YEAR-AWARE & STRICT
# =======================================================
@student_portal_bp.route('/exam')
def exam():
    student = get_logged_in_student()
    if not student:
        return redirect(url_for('user_bp.student_login'))

    # Subject
    subject = request.args.get("subject", "").strip()

    # YEAR passed from start_exam redirect
    year = request.args.get("year")

    if not year:
        # HARD fallback — but normally will NEVER run
        year = session.get("selected_year")

    if not year:
        year = str(datetime.now().year)

    # Always store year in session for exam-core.js to read
    session['selected_year'] = str(year)

    return render_template(
        'exam.html',
        student=student,
        subject=subject,
        year=year,   # ⭐ Sent to <meta name="exam-year">
        exam_started=session.get('exam_started', False)
    )



# =======================================================
# RESULT PAGE
# =======================================================
@student_portal_bp.route('/result')
def result():
    student = get_logged_in_student()
    if not student:
        return redirect(url_for('user_bp.student_login'))

    latest = get_latest_result(student.get("id"))

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

    class_cat = student.get("class_category")
    year = request.args.get("year", "")

    if not year:
        return jsonify({"subjects": []})

    json_path = Path(f"static/portal/{year}/{class_cat}/pushed_subjects.json")

    if not json_path.exists():
        return jsonify({"subjects": []})

    import json
    try:
        data = json.loads(json_path.read_text())
        return jsonify({"subjects": data.get("subjects", [])})
    except:
        return jsonify({"subjects": []})



@student_portal_bp.route("/back_to_exam_dashboard")
def back_to_exam_dashboard():
    return redirect(url_for("student_portal_bp.exam_dashboard"))
