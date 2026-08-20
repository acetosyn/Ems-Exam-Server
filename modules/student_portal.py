# modules/student_portal.py

from flask import Blueprint, render_template, redirect, url_for, session, request, jsonify
from pathlib import Path
from datetime import datetime
import json

from modules.supabase_results import save_exam_result_to_supabase, get_academic_settings
from modules.student_results import save_result, get_latest_result
from modules.excel_manager import read_results
from modules.class_config import get_subjects_for_class, normalize_class_level, normalize_class_arm, get_ss_track
from modules.api_routes import push_admin_notification
from push import get_latest_year, get_active_year_for_target, get_active_term_for_target, normalize_term, term_label


student_portal_bp = Blueprint("student_portal_bp", __name__)


# =========================================================
# SUBJECT BASE MAP
# =========================================================

BASE_SUBJECT_MAP = {
    "biology": "biology", "chemistry": "chemistry",

    "civic education": "civic", "civic": "civic",

    "computer science": "computer_science", "computer studies": "computer_science", "computer": "computer_science",

    "economics": "economics",

    "english language": "english", "english": "english",

    "financial accounting": "accounts", "financial account": "accounts", "accounting": "accounts", "accounts": "accounts",

    "geography": "geography", "government": "government",

    "literature-in-english": "literature", "literature in english": "literature", "literature": "literature",

    "mathematics": "mathematics", "maths": "mathematics",

    "physics": "physics",

    "technical drawing": "technical", "technical": "technical",

    "yoruba language": "yoruba", "yoruba": "yoruba",

    "history": "history",

    "irk": "irs", "irs": "irs",

    "cca": "cca",

    "arabic language": "arabic", "arabic": "arabic",

    "business studies": "business_studies",

    "poise": "poise",

    "islamiyyah": "islamiyyah",

    "hort & crop production": "hort_crop_production", "hort and crop production": "hort_crop_production",

    "digital tech.": "digital_tech", "digital tech": "digital_tech", "digital technology": "digital_tech",

    "inter science": "inter_science", "integrated science": "inter_science",

    "garment making": "garment_making",

    "soc. & cit. std": "soc_cit_std", "soc & cit std": "soc_cit_std", "social and citizenship studies": "soc_cit_std",

    "heritage & citizenship studies": "hcs", "hcs": "hcs",

    "p.h.e": "phe", "phe": "phe", "physical health education": "phe",

    "bst": "bst",

    "national value": "national_value", "national values": "national_value",

    "pvs": "pvs",

    "hausa language": "hausa", "hausa": "hausa",

    "cit & her. std": "cit_her_std", "cit and her std": "cit_her_std", "civic and heritage studies": "cit_her_std",

    "commerce": "commerce",

    "marketing": "marketing", "marketting": "marketing",

    "further mathematics": "further_mathematics", "further maths": "further_mathematics",

    "agricultural science": "agricultural_science", "agriculture": "agricultural_science",
}


# =========================================================
# BASIC STUDENT HELPERS
# =========================================================

def get_logged_in_student():
    if session.get("user_type") != "student":
        return None

    student = session.get("student")

    return student if isinstance(student, dict) else None


def get_student_full_name(student):
    full_name = student.get("full_name")

    if full_name:
        return str(full_name).strip()

    parts = [
        str(student.get("last_name", "")).strip(),
        str(student.get("first_name", "")).strip(),
        str(student.get("other_names", "")).strip(),
    ]

    return " ".join(value for value in parts if value).strip()


def get_student_sex(student):
    value = str(student.get("sex", "") or "").strip().upper()

    if value in {"M", "MALE"}:
        return "M"

    if value in {"F", "FEMALE"}:
        return "F"

    return value


# =========================================================
# STUDENT CLASS META
# =========================================================

def get_student_class_meta(student):
    class_level = normalize_class_level(
        student.get("class_category") or student.get("class_level") or student.get("class") or student.get("class_arm")
    )

    class_arm = normalize_class_arm(
        student.get("class_arm") or student.get("class") or student.get("class_category") or class_level,
        class_level,
    )

    if not class_level:
        class_level = normalize_class_level(class_arm)

    if not class_arm:
        class_arm = class_level

    return class_level, class_arm


# =========================================================
# STUDENT TRACK / STREAM
# =========================================================

def get_student_track(student):
    class_level, class_arm = get_student_class_meta(student)

    preferred_track = student.get("track") or student.get("student_track") or student.get("stream") or student.get("ss_stream") or ""

    return get_ss_track(class_arm, preferred_track)


# =========================================================
# REAL-TIME NOTIFICATION HELPERS
# =========================================================

def build_student_notification_payload(student, subject="", year="", term="", extra=None):
    class_level, class_arm = get_student_class_meta(student)

    payload = {
        "student_name": get_student_full_name(student),
        "admission_number": str(student.get("admission_number") or student.get("id") or "").strip(),
        "class": class_arm,
        "class_arm": class_arm,
        "class_category": class_level,
        "class_level": class_level,
        "stream": get_student_track(student),
        "subject": subject or "",
        "year": str(year or ""),
        "term": normalize_term(term) if term else "",
    }

    if isinstance(extra, dict):
        payload.update(extra)

    return payload


def notify_exam_event(event_type, student, message, subject="", year="", term="", extra=None):
    try:
        payload = build_student_notification_payload(student, subject=subject, year=year, term=term, extra=extra)
        push_admin_notification(event_type, message, payload)

    except Exception as error:
        print(f"ADMIN NOTIFICATION ERROR [{event_type}]:", error)


# =========================================================
# SUBJECT NORMALIZATION
# =========================================================

def normalize_subject_base(subject):
    key = str(subject or "").strip().lower()

    base_name = BASE_SUBJECT_MAP.get(key)

    if base_name:
        return base_name

    return key.replace("&", "and").replace(".", "").replace("-", "_").replace("/", "_").replace(" ", "_")


# =========================================================
# EXAM YEAR
# =========================================================

def resolve_exam_year():
    year = request.args.get("year", "").strip()

    if not year:
        latest = get_latest_year()
        year = latest if latest else str(datetime.now().year)

    return str(year).strip()


# =========================================================
# EXAM JSON PATH
# =========================================================

def build_exam_json_path(year, class_level, class_arm, subject, term=None):
    base_name = normalize_subject_base(subject)
    class_suffix = str(class_level or "").lower().strip()
    json_filename = f"{base_name}_{class_suffix}.json"

    if str(class_level).upper().startswith("JSS"):
        term = normalize_term(term)

        if not term:
            return None

        exact_path = Path("static") / "portal" / str(year) / class_arm / term / json_filename

        if exact_path.exists():
            return exact_path

        broad_path = Path("static") / "portal" / str(year) / class_level / term / json_filename

        if broad_path.exists():
            return broad_path

        return exact_path

    exact_path = Path("static") / "portal" / str(year) / class_arm / json_filename

    if exact_path.exists():
        return exact_path

    return Path("static") / "portal" / str(year) / class_level / json_filename


# =========================================================
# SUBJECT DISPLAY CLEANER
# =========================================================

def clean_subject_display_name(subject, class_level=""):
    value = str(subject or "").strip()

    if not value:
        return ""

    for suffix in ["JSS1", "JSS2", "JSS3", "SS1", "SS2", "SS3"]:
        value = value.replace(f"_{suffix}", "").replace(f"-{suffix}", "").replace(f" {suffix}", "")
        value = value.replace(f"_{suffix.lower()}", "").replace(f"-{suffix.lower()}", "").replace(f" {suffix.lower()}", "")

    value = value.replace("_", " ").replace("-", " ")
    value = " ".join(value.split())

    upper_value = value.upper().strip()

    aliases = {
        "ACCOUNT": "FINANCIAL ACCOUNT", "ACCOUNTS": "FINANCIAL ACCOUNT", "ACCOUNTING": "FINANCIAL ACCOUNT",
        "FINANCIAL ACCOUNT": "FINANCIAL ACCOUNT", "FINANCIAL ACCOUNTING": "FINANCIAL ACCOUNT",

        "ISLAMIYAH": "ISLAMIYYAH", "ISLAMIYYA": "ISLAMIYYAH", "ISLAMIYYAH": "ISLAMIYYAH",

        "MARKETTING": "MARKETING", "MARKETING": "MARKETING",

        "ARABIC": "ARABIC LANGUAGE", "ARABIC LANGUAGE": "ARABIC LANGUAGE",

        "ENGLISH": "ENGLISH LANGUAGE", "ENGLISH LANGUAGE": "ENGLISH LANGUAGE",

        "MATHS": "MATHEMATICS", "MATHEMATICS": "MATHEMATICS",

        "IRK": "IRK", "IRS": "IRS",

        "TECHNICAL": "TECHNICAL DRAWING", "TECHNICAL DRAWING": "TECHNICAL DRAWING",

        "CIVIC": "CIVIC EDUCATION", "CIVIC EDUCATION": "CIVIC EDUCATION",

        "COMPUTER": "COMPUTER SCIENCE", "COMPUTER STUDIES": "COMPUTER SCIENCE", "COMPUTER SCIENCE": "COMPUTER SCIENCE",

        "AGRICULTURE": "AGRICULTURAL SCIENCE", "AGRICULTURAL SCIENCE": "AGRICULTURAL SCIENCE",

        "DIGITAL TECH": "DIGITAL TECH.", "DIGITAL TECH.": "DIGITAL TECH.", "DIGITAL TECHNOLOGY": "DIGITAL TECH.",

        "CIT AND HER STD": "CIT_HER_STD", "CIT & HER STD": "CIT_HER_STD", "CIT & HER. STD": "CIT_HER_STD",
        "CITIZENSHIP AND HERITAGE STUDIES": "CIT_HER_STD",

        "SOC AND CIT STD": "SOC_CIT_STD", "SOC & CIT STD": "SOC_CIT_STD", "SOC. & CIT. STD": "SOC_CIT_STD",
        "SOCIAL AND CITIZENSHIP STUDIES": "SOC_CIT_STD",

        "POISE": "POISE",
    }

    cleaned = aliases.get(upper_value, upper_value)

    if str(class_level).upper().startswith("JSS") and cleaned == "IRS":
        return "IRK"

    if str(class_level).upper().startswith("SS") and cleaned == "IRK":
        return "IRS"

    if str(class_level).upper().startswith("JSS") and cleaned in {"CIT_HER_STD", "SOC_CIT_STD"}:
        return "SOC. & CIT. STD"

    if str(class_level).upper().startswith("SS") and cleaned in {"CIT_HER_STD", "SOC_CIT_STD"}:
        return "CIT & HER. STD"

    return cleaned


# =========================================================
# UNIQUE SUBJECT CLEANER
# =========================================================

def unique_clean_subjects(subjects, class_level=""):
    seen = set()
    cleaned = []

    for subject in subjects:
        if isinstance(subject, dict):
            subject = subject.get("subject") or subject.get("name") or subject.get("title")

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


# =========================================================
# TRACK SAFETY FILTER
# =========================================================

def filter_subjects_by_class_rules(subjects, class_level, class_arm, student=None):
    track = get_student_track(student or {}) if student else get_ss_track(class_arm)

    allowed_subjects = get_subjects_for_class(class_level, class_arm, preferred_track=track)
    allowed_clean = unique_clean_subjects(allowed_subjects, class_level)

    allowed_keys = {clean_subject_display_name(subject, class_level).lower() for subject in allowed_clean}
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


# =========================================================
# PUSHED SUBJECT FILE
# =========================================================

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

    except Exception as error:
        print("PUSHED SUBJECT READ ERROR:", error)
        return []


# =========================================================
# STUDENT PORTAL SUBJECTS
# =========================================================

def get_student_subjects_for_portal(student, year=None):
    class_level, class_arm = get_student_class_meta(student)

    if not class_level:
        return []

    if year:
        year = str(year).strip()
    else:
        year = get_active_year_for_target(class_arm, class_level)

        if not year and class_arm != class_level:
            year = get_active_year_for_target(class_level, class_level)

        if not year:
            year = get_latest_year()

        if not year:
            year = str(datetime.now().year)

    year = str(year).strip()

    active_term = None

    if str(class_level).upper().startswith("JSS"):
        requested_term = normalize_term(request.args.get("term"))

        active_term = requested_term or get_active_term_for_target(class_arm, class_level)

        if not active_term and class_arm != class_level:
            active_term = get_active_term_for_target(class_level, class_level)

    exact_arm_candidates = []

    for candidate in [class_arm, str(class_arm or "").replace("/", "")]:
        candidate = str(candidate or "").strip()

        if candidate and candidate not in exact_arm_candidates:
            exact_arm_candidates.append(candidate)

    if str(class_level).upper().startswith("JSS"):
        if active_term:
            for arm_folder in exact_arm_candidates:
                exact_arm_path = Path("static") / "portal" / year / arm_folder / active_term / "pushed_subjects.json"
                exact_subjects = read_pushed_subjects_file(exact_arm_path, class_level)

                if exact_subjects:
                    return filter_subjects_by_class_rules(exact_subjects, class_level, class_arm, student)

        if active_term:
            broad_path = Path("static") / "portal" / year / class_level / active_term / "pushed_subjects.json"
            broad_subjects = read_pushed_subjects_file(broad_path, class_level)

            if broad_subjects:
                return unique_clean_subjects(broad_subjects, class_level)

        for arm_folder in exact_arm_candidates:
            legacy_exact_path = Path("static") / "portal" / year / arm_folder / "pushed_subjects.json"
            legacy_exact_subjects = read_pushed_subjects_file(legacy_exact_path, class_level)

            if legacy_exact_subjects:
                return filter_subjects_by_class_rules(legacy_exact_subjects, class_level, class_arm, student)

        legacy_broad_path = Path("static") / "portal" / year / class_level / "pushed_subjects.json"
        legacy_broad_subjects = read_pushed_subjects_file(legacy_broad_path, class_level)

        if legacy_broad_subjects:
            return unique_clean_subjects(legacy_broad_subjects, class_level)

        return unique_clean_subjects(get_subjects_for_class(class_level, class_arm), class_level)

    for arm_folder in exact_arm_candidates:
        exact_arm_path = Path("static") / "portal" / year / arm_folder / "pushed_subjects.json"
        exact_subjects = read_pushed_subjects_file(exact_arm_path, class_level)

        if exact_subjects:
            return filter_subjects_by_class_rules(exact_subjects, class_level, class_arm, student)

    return unique_clean_subjects(
        get_subjects_for_class(class_level, class_arm, preferred_track=get_student_track(student)),
        class_level,
    )


# =========================================================
# STUDENT PORTAL PAGE
# =========================================================

@student_portal_bp.route("/student_portal")
def student_portal():
    student = get_logged_in_student()

    if not student:
        return redirect(url_for("user_bp.student_login"))

    year = resolve_exam_year()
    class_level, class_arm = get_student_class_meta(student)

    return render_template(
        "students.html",
        student=student,
        subjects=get_student_subjects_for_portal(student, year),
        sex=get_student_sex(student),
        class_category=class_level,
        class_level=class_level,
        class_arm=class_arm,
        stream=get_student_track(student),
        year=year,
        exam_started=session.get("exam_started", False),
        exam_submitted=session.get("exam_submitted", False),
    )


# =========================================================
# EXAM DASHBOARD
# =========================================================

@student_portal_bp.route("/exam_dashboard")
def exam_dashboard():
    student = get_logged_in_student()

    if not student:
        return redirect(url_for("user_bp.student_login"))

    subject_raw = request.args.get("subject", "").strip()

    if not subject_raw:
        return redirect(url_for("student_portal_bp.student_portal"))

    class_level, class_arm = get_student_class_meta(student)

    if not class_level:
        return redirect(url_for("student_portal_bp.student_portal"))

    requested_year = request.args.get("year", "").strip()

    if requested_year:
        year = requested_year
    else:
        year = get_active_year_for_target(class_arm, class_level)

        if not year and class_arm != class_level:
            year = get_active_year_for_target(class_level, class_level)

        if not year:
            year = get_latest_year()

        if not year:
            year = str(datetime.now().year)

    year = str(year).strip()

    active_term = None

    if str(class_level).upper().startswith("JSS"):
        requested_term = normalize_term(request.args.get("term"))

        active_term = requested_term or get_active_term_for_target(class_arm, class_level)

        if not active_term and class_arm != class_level:
            active_term = get_active_term_for_target(class_level, class_level)

    subject_display = clean_subject_display_name(subject_raw, class_level)

    allowed_subjects = get_student_subjects_for_portal(student, year)
    allowed_keys = {clean_subject_display_name(subject, class_level).lower() for subject in allowed_subjects}

    if subject_display.lower() not in allowed_keys:
        return redirect(url_for("student_portal_bp.student_portal", year=year))

    full_name = get_student_full_name(student)
    admission_no = str(student.get("admission_number", "")).strip()
    sex = get_student_sex(student)

    json_path = build_exam_json_path(year, class_level, class_arm, subject_display, active_term)
    exam_available = bool(json_path and json_path.exists())

    print("\n" + "=" * 90)
    print("STUDENT EXAM AVAILABILITY CHECK")
    print(f"Student       : {full_name}")
    print(f"Admission No  : {admission_no}")
    print(f"Class Level   : {class_level}")
    print(f"Class Arm     : {class_arm}")
    print(f"Subject       : {subject_display}")
    print(f"Year          : {year}")
    print(f"Active Term   : {active_term}")
    print(f"JSON Path     : {json_path}")
    print(f"JSON Exists   : {exam_available}")
    print("=" * 90 + "\n")

    existing_results = read_results(class_arm or class_level, subject_display, year)
    already_written = False

    for result_row in existing_results:
        result_admission = str(result_row.get("Admission No", "")).strip().lower()

        if result_admission and result_admission == admission_no.lower():
            already_written = True
            break

    session["selected_subject"] = subject_display
    session["selected_year"] = year
    session["selected_class_level"] = class_level
    session["selected_class_arm"] = class_arm
    session["selected_term"] = active_term
    session["exam_submitted"] = already_written

    return render_template(
        "exam_dashboard.html",
        student=student,
        subject=subject_display,
        year=year,
        term=active_term,
        active_term=active_term,
        term_label=term_label(active_term) if active_term else None,
        already_written=already_written,
        exam_available=exam_available,
        full_name=full_name,
        admission_number=admission_no,
        sex=sex,
        class_name=class_arm,
        class_arm=class_arm,
        class_category=class_level,
        class_level=class_level,
        stream=get_student_track(student),
        system_id=student.get("id"),
        exam_started=session.get("exam_started", False),
        exam_submitted=session.get("exam_submitted", already_written),
    )

# =========================================================
# START EXAM
# =========================================================

@student_portal_bp.route("/start_exam", methods=["POST"])
def start_exam():
    student = get_logged_in_student()

    if not student:
        return redirect(url_for("user_bp.student_login"))

    if session.get("exam_submitted"):
        return redirect(url_for("student_portal_bp.result"))

    subject = session.get("selected_subject")
    year = session.get("selected_year") or str(datetime.now().year)
    term = normalize_term(session.get("selected_term"))

    if not subject:
        return redirect(url_for("student_portal_bp.student_portal"))

    class_level, class_arm = get_student_class_meta(student)

    # =====================================================
    # JSS TERM RESOLUTION
    # =====================================================

    if str(class_level or "").upper().startswith("JSS"):
        if not term:
            term = get_active_term_for_target(class_arm, class_level)

        if not term and class_arm != class_level:
            term = get_active_term_for_target(class_level, class_level)

        if not term:
            print("[START EXAM ERROR] Missing JSS term:", {"subject": subject, "year": year, "class_level": class_level, "class_arm": class_arm})
            return redirect(url_for("student_portal_bp.exam_dashboard", subject=subject, year=year))

    else:
        term = ""

    # =====================================================
    # PREPARE EXAM SESSION
    #
    # IMPORTANT:
    # Do NOT send exam_start notification here.
    # This route only admits the student into the exam page.
    #
    # exam-core.js will POST the real exam_start event only
    # after questions successfully load and the timer begins.
    # =====================================================

    session["selected_subject"] = subject
    session["selected_year"] = str(year)
    session["selected_class_level"] = class_level
    session["selected_class_arm"] = class_arm
    session["selected_term"] = term

    # Keep this False here because the actual exam has not
    # started yet. JS starts it after successful question load.
    session["exam_started"] = False

    return redirect(url_for("student_portal_bp.exam", subject=subject, year=year, term=term))


# =========================================================
# EXAM PAGE
# =========================================================

@student_portal_bp.route("/exam")
def exam():
    student = get_logged_in_student()

    if not student:
        return redirect(url_for("user_bp.student_login"))

    subject = request.args.get("subject", "").strip()

    year = request.args.get("year") or session.get("selected_year") or str(datetime.now().year)

    class_level, class_arm = get_student_class_meta(student)
    sex = get_student_sex(student)

    if not class_level:
        return redirect(url_for("student_portal_bp.student_portal"))

    active_term = None

    if str(class_level).upper().startswith("JSS"):
        active_term = normalize_term(request.args.get("term") or session.get("selected_term"))

        if not active_term:
            active_term = get_active_term_for_target(class_arm, class_level)

        if not active_term and class_arm != class_level:
            active_term = get_active_term_for_target(class_level, class_level)

        if not active_term:
            print("[EXAM PAGE ERROR] Missing active JSS term:", {
                "subject": subject,
                "year": year,
                "class_level": class_level,
                "class_arm": class_arm,
                "session_term": session.get("selected_term"),
                "query_term": request.args.get("term"),
            })

            return redirect(url_for("student_portal_bp.exam_dashboard", subject=subject, year=year))

    session["selected_subject"] = subject
    session["selected_year"] = str(year)
    session["selected_class_level"] = class_level
    session["selected_class_arm"] = class_arm
    session["selected_term"] = active_term

    print("\n" + "=" * 90)
    print("EMIS EXAM PAGE RUNTIME")
    print(f"Subject      : {subject}")
    print(f"Year         : {year}")
    print(f"Class Level  : {class_level}")
    print(f"Class Arm    : {class_arm}")
    print(f"Active Term  : {active_term}")
    print("=" * 90 + "\n")

    return render_template(
        "exam.html",
        student=student,
        subject=subject,
        year=str(year),
        term=active_term,
        active_term=active_term,
        term_label=term_label(active_term) if active_term else None,
        sex=sex,
        class_level=class_level,
        class_category=class_level,
        class_arm=class_arm,
        stream=get_student_track(student),
        exam_started=session.get("exam_started", False),
    )


# =========================================================
# SUBMIT EXAM
# =========================================================

@student_portal_bp.route("/submit_exam", methods=["POST"])
def submit_exam():
    student = get_logged_in_student()

    if not student:
        return jsonify({"error": "Not logged in"}), 401

    data = request.get_json(silent=True) or {}

    if not data:
        return jsonify({"error": "Invalid request"}), 400

    class_level, class_arm = get_student_class_meta(student)
    subject = clean_subject_display_name(data.get("subject"), class_level)

    if not subject:
        return jsonify({"error": "Subject is required"}), 400

    allowed_subjects = get_student_subjects_for_portal(student)
    allowed_keys = {clean_subject_display_name(subject_item, class_level).lower() for subject_item in allowed_subjects}

    if subject.lower() not in allowed_keys:
        return jsonify({"error": "Subject is not assigned to your class arm"}), 403

    full_name = get_student_full_name(student)
    admission_no = str(student.get("admission_number", "")).strip()
    sex = get_student_sex(student)
    year = str(session.get("selected_year") or datetime.now().year).strip()

    # =====================================================
    # ACADEMIC SESSION / TERM
    # =====================================================

    try:
        academic_settings = get_academic_settings() or {}
        academic_session = str(academic_settings.get("current_session") or "2025/2026").strip()
        term = normalize_term(academic_settings.get("current_term") or "")
    except Exception as error:
        print("ACADEMIC SETTINGS FETCH ERROR:", error)
        academic_session = "2025/2026"
        term = normalize_term(session.get("selected_term"))

    if str(class_level or "").upper().startswith("JSS"):
        term = term or normalize_term(session.get("selected_term"))

        if not term:
            return jsonify({"error": "No active term is available for this JSS examination"}), 400
    else:
        term = ""

    # Keep selected term synchronized.
    session["selected_term"] = term

    # =====================================================
    # PREVENT DUPLICATE SUBMISSION
    # =====================================================

    previous = read_results(class_arm or class_level, subject, year, term)

    for result_row in previous:
        existing_admission = str(result_row.get("Admission No", "")).strip().lower()

        if existing_admission and existing_admission == admission_no.lower():
            return jsonify({"error": "Exam already submitted"}), 403

    now = datetime.now()

    # =====================================================
    # RESULT PENDING NOTIFICATION
    # =====================================================

    notify_exam_event(
        "result_pending",
        student,
        f"{full_name}'s {subject} result is being processed.",
        subject=subject,
        year=year,
        term=term,
    )

    # =====================================================
    # COMPLETE RESULT PAYLOAD
    # =====================================================

    data.update({
        "student_id": student.get("id") or admission_no,
        "full_name": full_name,
        "admission_number": admission_no,
        "sex": sex,
        "gender": sex,

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

    # =====================================================
    # LOCAL RESULT SAVE
    # =====================================================

    try:
        save_result(data)
    except Exception as error:
        print("LOCAL RESULT SAVE ERROR:", error)
        return jsonify({"error": "Could not save examination result"}), 500

    # =====================================================
    # SUPABASE RESULT SAVE
    # =====================================================

    try:
        save_exam_result_to_supabase(data)
    except Exception as error:
        print("SUPABASE SAVE ERROR:", error)

    # =====================================================
    # UPDATE EXAM SESSION STATE
    # =====================================================

    session["exam_submitted"] = True
    session["exam_started"] = False

    # =====================================================
    # SCORE / STATUS
    # =====================================================

    score = data.get("score", data.get("score_percentage", data.get("percentage", data.get("Score (%)", ""))))
    status = str(data.get("status") or data.get("Status") or "").strip().upper()

    if not status:
        try:
            numeric_score = float(str(score).replace("%", "").strip())
            status = "PASS" if numeric_score >= 50 else "FAIL"
        except (TypeError, ValueError):
            status = ""

    # =====================================================
    # RESULT EVENT PAYLOAD
    # =====================================================

    result_extra = {
        "score": score,
        "status": status,
        "academic_session": academic_session,
        "submitted_at": data.get("submitted_at", ""),
    }

    # =====================================================
    # EXAM SUBMITTED NOTIFICATION
    # =====================================================

    notify_exam_event(
        "exam_end",
        student,
        f"{full_name} submitted {subject}.",
        subject=subject,
        year=year,
        term=term,
        extra=result_extra,
    )

    # =====================================================
    # RESULT AVAILABLE NOTIFICATION
    # =====================================================

    notify_exam_event(
        "result_available",
        student,
        f"{full_name}'s {subject} result is now available.",
        subject=subject,
        year=year,
        term=term,
        extra=result_extra,
    )

    # =====================================================
    # RESPONSE
    # =====================================================

    return jsonify({
        "status": "ok",
        "message": "Exam submitted successfully",
        "academic_session": academic_session,
        "term": term,
        "class_level": class_level,
        "class_arm": class_arm,
        "subject": subject,
        "score": score,
        "result_status": status,
        "sex": sex,
    }), 200

# =========================================================
# RESULT PAGE
# =========================================================

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
            "status": "No record",
        }

    return render_template("result.html", student=student, result=latest, sex=get_student_sex(student))


# =========================================================
# SUBJECTS API
# =========================================================

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
        "sex": get_student_sex(student),
        "year": year,
    })


# =========================================================
# BACK TO EXAM DASHBOARD
# =========================================================

@student_portal_bp.route("/back_to_exam_dashboard")
def back_to_exam_dashboard():
    subject = session.get("selected_subject")
    year = session.get("selected_year")

    if subject:
        return redirect(url_for("student_portal_bp.exam_dashboard", subject=subject, year=year))

    return redirect(url_for("student_portal_bp.student_portal"))