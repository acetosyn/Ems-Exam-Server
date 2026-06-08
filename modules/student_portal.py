# modules/student_portal.py

from flask import Blueprint, render_template, redirect, url_for, session, request, jsonify
from pathlib import Path
from datetime import datetime
import json

from modules.supabase_results import save_exam_result_to_supabase, get_academic_settings
from modules.student_results import save_result, get_latest_result
from modules.excel_manager import read_results
from modules.class_config import (
    get_subjects_for_class,
    normalize_class_level,
    normalize_class_arm,
    get_ss_track,
)
from push import get_latest_year


student_portal_bp = Blueprint("student_portal_bp", __name__)


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
    "yoruba language": "yoruba",
    "yoruba": "yoruba",
    "history": "history",
    "irk": "irs",
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
    "heritage & citizenship studies": "hcs",
    "hcs": "hcs",
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
    "marketting": "marketing",
    "further mathematics": "further_mathematics",
    "further maths": "further_mathematics",
    "agricultural science": "agricultural_science",
    "agriculture": "agricultural_science",
}


def get_logged_in_student():
    if session.get("user_type") != "student":
        return None
    return session.get("student")


def get_student_full_name(student):
    full_name = student.get("full_name")

    if full_name:
        return str(full_name).strip()

    return " ".join([
        str(student.get("last_name", "")).strip(),
        str(student.get("first_name", "")).strip(),
        str(student.get("other_names", "")).strip(),
    ]).strip()


def get_student_class_meta(student):
    class_level = normalize_class_level(
        student.get("class_category")
        or student.get("class_level")
        or student.get("class")
    )

    class_arm = normalize_class_arm(
        student.get("class_arm")
        or student.get("class")
        or student.get("class_category"),
        class_level
    )

    if not class_level:
        class_level = normalize_class_level(class_arm)

    if not class_arm:
        class_arm = class_level

    return class_level, class_arm


def get_student_track(student):
    class_level, class_arm = get_student_class_meta(student)

    preferred_track = (
        student.get("track")
        or student.get("student_track")
        or student.get("stream")
        or student.get("ss_stream")
        or ""
    )

    return get_ss_track(class_arm, preferred_track)


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


def resolve_exam_year():
    year = request.args.get("year", "").strip()

    if not year:
        latest = get_latest_year()
        year = latest if latest else str(datetime.now().year)

    return str(year).strip()


def build_exam_json_path(year, class_level, subject):
    base_name = normalize_subject_base(subject)
    class_suffix = str(class_level or "").lower().strip()
    json_filename = f"{base_name}_{class_suffix}.json"

    return Path(
        f"static/subjects/{year}/subjects-json/{class_level}/{json_filename}"
    )


def clean_subject_display_name(subject, class_level=""):
    value = str(subject or "").strip()

    if not value:
        return ""

    for suffix in ["JSS1", "JSS2", "JSS3", "SS1", "SS2", "SS3"]:
        value = value.replace(f"_{suffix}", "")
        value = value.replace(f"-{suffix}", "")
        value = value.replace(f" {suffix}", "")
        value = value.replace(f"_{suffix.lower()}", "")
        value = value.replace(f"-{suffix.lower()}", "")
        value = value.replace(f" {suffix.lower()}", "")

    value = value.replace("_", " ").replace("-", " ")
    value = " ".join(value.split())

    upper_value = value.upper().strip()

    aliases = {
        "ACCOUNT": "FINANCIAL ACCOUNT",
        "ACCOUNTS": "FINANCIAL ACCOUNT",
        "ACCOUNTING": "FINANCIAL ACCOUNT",
        "FINANCIAL ACCOUNT": "FINANCIAL ACCOUNT",
        "FINANCIAL ACCOUNTING": "FINANCIAL ACCOUNT",

        "ISLAMIYAH": "ISLAMIYYAH",
        "ISLAMIYYA": "ISLAMIYYAH",
        "ISLAMIYYAH": "ISLAMIYYAH",

        "MARKETTING": "MARKETING",
        "MARKETING": "MARKETING",

        "ARABIC": "ARABIC LANGUAGE",
        "ARABIC LANGUAGE": "ARABIC LANGUAGE",

        "ENGLISH": "ENGLISH LANGUAGE",
        "ENGLISH LANGUAGE": "ENGLISH LANGUAGE",

        "MATHS": "MATHEMATICS",
        "MATHEMATICS": "MATHEMATICS",

        # Keep both valid here.
        # Final JSS/SS display is handled below.
        "IRK": "IRK",
        "IRS": "IRS",

        "TECHNICAL": "TECHNICAL DRAWING",
        "TECHNICAL DRAWING": "TECHNICAL DRAWING",

        "CIVIC": "CIVIC EDUCATION",
        "CIVIC EDUCATION": "CIVIC EDUCATION",

        "COMPUTER": "COMPUTER SCIENCE",
        "COMPUTER STUDIES": "COMPUTER SCIENCE",
        "COMPUTER SCIENCE": "COMPUTER SCIENCE",

        "AGRICULTURE": "AGRICULTURAL SCIENCE",
        "AGRICULTURAL SCIENCE": "AGRICULTURAL SCIENCE",

        "DIGITAL TECH": "DIGITAL TECH.",
        "DIGITAL TECH.": "DIGITAL TECH.",
        "DIGITAL TECHNOLOGY": "DIGITAL TECH.",

        # Keep the subject family normalized first.
        # Final JSS/SS display is handled below.
        "CIT AND HER STD": "CIT_HER_STD",
        "CIT & HER STD": "CIT_HER_STD",
        "CIT & HER. STD": "CIT_HER_STD",
        "CITIZENSHIP AND HERITAGE STUDIES": "CIT_HER_STD",

        "SOC AND CIT STD": "SOC_CIT_STD",
        "SOC & CIT STD": "SOC_CIT_STD",
        "SOC. & CIT. STD": "SOC_CIT_STD",
        "SOCIAL AND CITIZENSHIP STUDIES": "SOC_CIT_STD",

        "POISE": "POISE",
    }

    cleaned = aliases.get(upper_value, upper_value)

    if str(class_level).upper().startswith("JSS") and cleaned == "IRS":
        return "IRK"

    if str(class_level).upper().startswith("SS") and cleaned == "IRK":
        return "IRS"

    if str(class_level).upper().startswith("JSS") and cleaned in ["CIT_HER_STD", "SOC_CIT_STD"]:
        return "SOC. & CIT. STD"

    if str(class_level).upper().startswith("SS") and cleaned in ["CIT_HER_STD", "SOC_CIT_STD"]:
        return "CIT & HER. STD"

    return cleaned


def unique_clean_subjects(subjects, class_level=""):
    seen = set()
    cleaned = []

    for subject in subjects:
        if isinstance(subject, dict):
            subject = (
                subject.get("subject")
                or subject.get("name")
                or subject.get("title")
            )

        name = clean_subject_display_name(subject, class_level)

        if not name:
            continue

        key = name.lower()

        if key in seen:
            continue

        seen.add(key)
        cleaned.append(name)

    compulsory_subjects = ["POISE", "ISLAMIYYAH"]

    for subject in compulsory_subjects:
        key = subject.lower()
        if key not in seen:
            seen.add(key)
            cleaned.append(subject)

    return cleaned


def filter_subjects_by_class_rules(subjects, class_level, class_arm, student=None):
    """
    Strict safety filter.

    Even if pushed_subjects.json contains wrong/mixed subjects,
    this function removes subjects that do not belong to the student's track.
    """
    track = get_student_track(student or {}) if student else get_ss_track(class_arm)

    allowed_subjects = get_subjects_for_class(
        class_level,
        class_arm,
        preferred_track=track
    )

    allowed_clean = unique_clean_subjects(allowed_subjects, class_level)
    allowed_keys = {
        clean_subject_display_name(subject, class_level).lower()
        for subject in allowed_clean
    }

    incoming_clean = unique_clean_subjects(subjects, class_level)

    if not str(class_level).startswith("SS"):
        return incoming_clean

    filtered = [
        subject for subject in incoming_clean
        if clean_subject_display_name(subject, class_level).lower() in allowed_keys
    ]

    if filtered:
        return unique_clean_subjects(filtered, class_level)

    return allowed_clean


def read_pushed_subjects_file(json_path, class_level):
    if not json_path.exists():
        return []

    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))

        if isinstance(data, dict):
            subjects = data.get("subjects", [])
        elif isinstance(data, list):
            subjects = data
        else:
            subjects = []

        return unique_clean_subjects(subjects, class_level)

    except Exception as e:
        print("PUSHED SUBJECT READ ERROR:", e)
        return []


def get_student_subjects_for_portal(student, year=None):
    class_level, class_arm = get_student_class_meta(student)

    if not class_level:
        return []

    if not year:
        latest = get_latest_year()
        year = latest if latest else str(datetime.now().year)

    # 1. Exact class-arm push first.
    # Example:
    # static/portal/2026/SS3_GOLD/pushed_subjects.json
    exact_arm_path = Path(
        f"static/portal/{year}/{class_arm}/pushed_subjects.json"
    )

    exact_subjects = read_pushed_subjects_file(exact_arm_path, class_level)

    if exact_subjects:
        return filter_subjects_by_class_rules(
            exact_subjects,
            class_level,
            class_arm,
            student
        )

    # 2. SS classes must NOT use broad SS pushed JSON.
    # This prevents SS3_GOLD from receiving Literature/Government/Commerce.
    if str(class_level).startswith("SS"):
        return unique_clean_subjects(
            get_subjects_for_class(
                class_level,
                class_arm,
                preferred_track=get_student_track(student)
            ),
            class_level
        )

    # 3. JSS can use broad pushed subjects safely.
    broad_path = Path(
        f"static/portal/{year}/{class_level}/pushed_subjects.json"
    )

    broad_subjects = read_pushed_subjects_file(broad_path, class_level)

    if broad_subjects:
        return unique_clean_subjects(broad_subjects, class_level)

    # 4. Final fallback from class_config.py.
    return unique_clean_subjects(
        get_subjects_for_class(class_level, class_arm),
        class_level
    )


@student_portal_bp.route("/student_portal")
def student_portal():
    student = get_logged_in_student()
    if not student:
        return redirect(url_for("user_bp.student_login"))

    year = resolve_exam_year()
    class_level, class_arm = get_student_class_meta(student)
    subjects = get_student_subjects_for_portal(student, year)

    return render_template(
        "students.html",
        student=student,
        subjects=subjects,
        class_category=class_level,
        class_level=class_level,
        class_arm=class_arm,
        year=year,
        exam_started=session.get("exam_started", False),
        exam_submitted=session.get("exam_submitted", False)
    )


@student_portal_bp.route("/exam_dashboard")
def exam_dashboard():
    student = get_logged_in_student()
    if not student:
        return redirect(url_for("user_bp.student_login"))

    subject_raw = request.args.get("subject", "").strip()
    if not subject_raw:
        return redirect(url_for("student_portal_bp.student_portal"))

    subject_display = clean_subject_display_name(subject_raw)
    year = resolve_exam_year()

    class_level, class_arm = get_student_class_meta(student)

    if not class_level:
        return redirect(url_for("student_portal_bp.student_portal"))

    allowed_subjects = get_student_subjects_for_portal(student, year)
    allowed_keys = {
        clean_subject_display_name(subject, class_level).lower()
        for subject in allowed_subjects
    }

    if subject_display.lower() not in allowed_keys:
        return redirect(url_for("student_portal_bp.student_portal"))

    full_name = get_student_full_name(student)
    admission_no = str(student.get("admission_number", "")).strip()

    json_path = build_exam_json_path(year, class_level, subject_display)
    exam_available = json_path.exists()

    existing_results = read_results(class_arm or class_level, subject_display, year)

    already_written = False
    for r in existing_results:
        name = str(r.get("Student Name", "")).upper().strip()
        adm = str(r.get("Admission No", "")).upper().strip()

        if name == full_name.upper() and adm == admission_no.upper():
            already_written = True
            break

    session["selected_subject"] = subject_display
    session["selected_year"] = year
    session["selected_class_level"] = class_level
    session["selected_class_arm"] = class_arm
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
        class_name=class_arm,
        class_arm=class_arm,
        class_category=class_level,
        class_level=class_level,
        system_id=student.get("id"),
        exam_started=session.get("exam_started", False),
        exam_submitted=session.get("exam_submitted", already_written)
    )


@student_portal_bp.route("/submit_exam", methods=["POST"])
def submit_exam():
    student = get_logged_in_student()
    if not student:
        return jsonify({"error": "Not logged in"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid"}), 400

    subject = clean_subject_display_name(data.get("subject"))

    class_level, class_arm = get_student_class_meta(student)

    allowed_subjects = get_student_subjects_for_portal(student)
    allowed_keys = {
        clean_subject_display_name(subject_item, class_level).lower()
        for subject_item in allowed_subjects
    }

    if subject.lower() not in allowed_keys:
        return jsonify({"error": "Subject is not assigned to your class arm"}), 403

    full_name = get_student_full_name(student)
    admission_no = str(student.get("admission_number", "")).strip()
    year = str(session.get("selected_year", datetime.now().year))

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

    previous = read_results(class_arm or class_level, subject, year)

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
        "class_name": class_arm,
        "class": class_arm,
        "class_arm": class_arm,
        "class_category": class_level,
        "class_level": class_level,
        "stream": get_student_track(student),
        "year": year,
        "subject": subject,
        "academic_session": academic_session,
        "term": term,
        "submitted_at": now.strftime("%Y-%m-%d %H:%M"),
        "date_written": now.strftime("%Y-%m-%d"),
        "day_written": now.strftime("%A"),
        "time_written": now.strftime("%I:%M %p"),
    })

    save_result(data)

    try:
        save_exam_result_to_supabase(data)
    except Exception as e:
        print("SUPABASE SAVE ERROR:", e)

    session["exam_submitted"] = True
    session["exam_started"] = False

    return jsonify({
        "status": "ok",
        "academic_session": academic_session,
        "term": term,
        "class_level": class_level,
        "class_arm": class_arm
    })


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


@student_portal_bp.route("/exam")
def exam():
    student = get_logged_in_student()
    if not student:
        return redirect(url_for("user_bp.student_login"))

    subject = request.args.get("subject", "").strip()
    year = request.args.get("year") or session.get("selected_year") or str(datetime.now().year)

    class_level, class_arm = get_student_class_meta(student)

    session["selected_year"] = str(year)
    session["selected_class_level"] = class_level
    session["selected_class_arm"] = class_arm

    return render_template(
        "exam.html",
        student=student,
        subject=subject,
        year=year,
        class_level=class_level,
        class_category=class_level,
        class_arm=class_arm,
        exam_started=session.get("exam_started", False)
    )


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


@student_portal_bp.route("/api/student/subjects")
def api_student_subjects():
    student = get_logged_in_student()
    if not student:
        return jsonify({"subjects": []})

    year = request.args.get("year", "").strip()

    if not year:
        latest = get_latest_year()
        year = latest if latest else str(datetime.now().year)

    class_level, class_arm = get_student_class_meta(student)
    subjects = get_student_subjects_for_portal(student, year)

    return jsonify({
        "subjects": subjects,
        "class_level": class_level,
        "class_category": class_level,
        "class_arm": class_arm,
        "stream": get_student_track(student),
        "year": year
    })


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