# MODULE: Academic Records — Shared EMIS academic/student service layer
# PURPOSE: Common student, class, session, term and subject helpers for Attendance, CA/Test and Report Sheets.
# NOTE: This module creates NO new database. students2026.csv remains the single student source through student_lookup.py.

import re

from modules.class_config import SUPPORTED_CLASSES, CLASS_ARMS_BY_LEVEL, normalize_class_level, normalize_class_arm, normalize_subject_key, normalize_subject_display, get_subjects_for_class, get_ss_track
from modules.student_lookup import read_student_database, find_student_by_admission, normalize_admission_number
from modules.academic_settings import get_academic_settings

VALID_TERMS = ("FIRST", "SECOND", "THIRD")


# ============================================================
# BASIC HELPERS
# ============================================================

def clean(value): return str(value or "").strip()

def clean_upper(value): return clean(value).upper()

def safe_bool(value):
    if isinstance(value, bool): return value
    return clean_upper(value) in {"1", "TRUE", "YES", "Y", "ON"}


# ============================================================
# TERM NORMALIZATION
# ============================================================

def normalize_academic_term(value):
    """Convert common term formats to canonical EMIS FIRST / SECOND / THIRD."""
    raw = " ".join(clean_upper(value).replace("_", " ").replace("-", " ").split())
    aliases = {
        "FIRST": "FIRST", "FIRST TERM": "FIRST", "TERM 1": "FIRST", "TERM ONE": "FIRST", "1": "FIRST", "1ST": "FIRST", "1ST TERM": "FIRST",
        "SECOND": "SECOND", "SECOND TERM": "SECOND", "TERM 2": "SECOND", "TERM TWO": "SECOND", "2": "SECOND", "2ND": "SECOND", "2ND TERM": "SECOND",
        "THIRD": "THIRD", "THIRD TERM": "THIRD", "TERM 3": "THIRD", "TERM THREE": "THIRD", "3": "THIRD", "3RD": "THIRD", "3RD TERM": "THIRD",
    }
    return aliases.get(raw, "")


def academic_term_label(value):
    return {"FIRST": "FIRST TERM", "SECOND": "SECOND TERM", "THIRD": "THIRD TERM"}.get(normalize_academic_term(value), "")


def short_term_label(value):
    return {"FIRST": "1st Term", "SECOND": "2nd Term", "THIRD": "3rd Term"}.get(normalize_academic_term(value), "")


def is_valid_term(value): return normalize_academic_term(value) in VALID_TERMS


# ============================================================
# ACADEMIC SESSION
# ============================================================

def normalize_academic_session(value):
    """Normalize 2025-2026 / 2025 / 2026 to 2025/2026."""
    raw = clean(value)
    if not raw: return ""
    match = re.fullmatch(r"(\d{4})\s*[/\-]\s*(\d{4})", raw)
    if not match: return raw
    return f"{int(match.group(1)):04d}/{int(match.group(2)):04d}"


def is_valid_academic_session(value):
    match = re.fullmatch(r"(\d{4})/(\d{4})", normalize_academic_session(value))
    if not match: return False
    return int(match.group(2)) == int(match.group(1)) + 1


def get_current_academic_context(session_value="", term_value=""):
    """Explicit page values take priority; otherwise use the persistent global EMIS academic period."""
    try: settings = get_academic_settings() or {}
    except Exception as error:
        print("ACADEMIC SETTINGS READ ERROR:", error)
        settings = {}

    academic_session = normalize_academic_session(session_value or settings.get("current_session") or settings.get("session") or "")
    term = normalize_academic_term(term_value or settings.get("current_term") or settings.get("term") or "")
    current_year = clean(settings.get("current_year") or settings.get("year"))

    if not current_year and "/" in academic_session:
        current_year = clean(academic_session.split("/", 1)[0])

    return {
        "year": current_year, "current_year": current_year,
        "session": academic_session, "academic_session": academic_session, "current_session": academic_session,
        "term": term, "current_term": term,
        "term_label": academic_term_label(term), "current_term_label": academic_term_label(term), "short_term_label": short_term_label(term),
        "valid_session": is_valid_academic_session(academic_session), "valid_term": bool(term),
        "configured": bool(academic_session and term), "updated_at": clean(settings.get("updated_at")), "updated_by": clean(settings.get("updated_by")),
        "source": clean(settings.get("source")) or "local",
    }


# ============================================================
# CLASS NORMALIZATION
# ============================================================

def normalize_academic_class(class_level="", class_arm=""):
    """Return canonical broad class and exact class arm."""
    level = normalize_class_level(class_level or class_arm)
    if level not in SUPPORTED_CLASSES: return "", ""

    arm = normalize_class_arm(class_arm or class_level, level)
    if not arm: arm = level
    return level, arm


def is_supported_class(class_level): return normalize_class_level(class_level) in SUPPORTED_CLASSES


def get_available_class_arms(class_level):
    level = normalize_class_level(class_level)
    return list(CLASS_ARMS_BY_LEVEL.get(level, [])) if level else []


def validate_class_selection(class_level="", class_arm="", require_arm=False):
    level, arm = normalize_academic_class(class_level, class_arm)

    if not level:
        return {"valid": False, "class_level": "", "class_arm": "", "message": "Invalid class level."}

    configured_arms = get_available_class_arms(level)

    if require_arm and not clean(class_arm):
        return {"valid": False, "class_level": level, "class_arm": "", "message": f"Class arm is required for {level}."}

    if class_arm and arm not in configured_arms:
        return {"valid": False, "class_level": level, "class_arm": arm, "message": f"{arm} is not a configured class arm for {level}."}

    return {"valid": True, "class_level": level, "class_arm": arm, "message": ""}


# ============================================================
# STUDENT HELPERS
# ============================================================

def student_display_name(student):
    if not isinstance(student, dict): return ""

    full_name = clean(student.get("full_name"))
    if full_name: return full_name

    return " ".join(part for part in [
        clean(student.get("last_name")), clean(student.get("first_name")), clean(student.get("other_names"))
    ] if part).strip()


def student_frontend_record(student):
    """Return one standard student structure used by Attendance, CA and Reports."""
    if not isinstance(student, dict): return {}

    level, arm = normalize_academic_class(
        student.get("class_level") or student.get("class_category") or student.get("class"),
        student.get("class_arm") or student.get("class")
    )

    admission = clean(student.get("admission_number") or student.get("id"))
    preferred_track = clean_upper(student.get("track") or student.get("student_track") or student.get("stream") or student.get("ss_stream"))
    track = get_ss_track(arm, preferred_track) if level.startswith("SS") else ""
    status = clean_upper(student.get("status") or "ACTIVE")

    return {
        "admission_number": admission, "id": admission,
        "last_name": clean(student.get("last_name")), "first_name": clean(student.get("first_name")),
        "other_names": clean(student.get("other_names")), "full_name": student_display_name(student),
        "phone": clean(student.get("phone")), "sex": clean_upper(student.get("sex")),
        "class": arm, "class_arm": arm, "class_category": level, "class_level": level,
        "stream": track, "ss_stream": track, "status": status, "is_active": status == "ACTIVE",
    }


def get_all_students(active_only=True):
    """Return normalized students from students2026.csv."""
    students = read_student_database()

    if active_only:
        students = [student for student in students if student.get("is_active", True)]

    rows = [student_frontend_record(student) for student in students]
    rows.sort(key=lambda student: (
        clean(student.get("class_level")), clean(student.get("class_arm")),
        clean(student.get("last_name")).lower(), clean(student.get("first_name")).lower(),
        clean(student.get("admission_number")).lower()
    ))
    return rows


def get_student(admission_number, active_only=True):
    """Find one student using the globally unique admission number."""
    admission = normalize_admission_number(admission_number)
    if not admission: return None

    student = find_student_by_admission(admission)
    if not student: return None

    row = student_frontend_record(student)
    if active_only and not row.get("is_active", True): return None
    return row


def student_matches_class(student, class_level="", class_arm=""):
    if not isinstance(student, dict): return False

    requested_level, requested_arm = normalize_academic_class(class_level, class_arm)
    if not requested_level: return False

    student_level, student_arm = normalize_academic_class(
        student.get("class_level") or student.get("class_category") or student.get("class"),
        student.get("class_arm") or student.get("class")
    )

    if student_level != requested_level: return False
    if class_arm and student_arm != requested_arm: return False
    return True


def get_students_for_class(class_level, class_arm="", active_only=True):
    """Main roster helper for Attendance, CA/Test and Report Sheets."""
    validation = validate_class_selection(class_level, class_arm)
    if not validation["valid"]: return []

    students = get_all_students(active_only=active_only)
    rows = [
        student for student in students
        if student_matches_class(student, validation["class_level"], class_arm)
    ]

    rows.sort(key=lambda student: (
        clean(student.get("last_name")).lower(), clean(student.get("first_name")).lower(),
        clean(student.get("other_names")).lower(), clean(student.get("admission_number")).lower()
    ))
    return rows


def get_class_roster_summary(class_level, class_arm=""):
    students = get_students_for_class(class_level, class_arm, active_only=True)
    male = sum(1 for student in students if clean_upper(student.get("sex")) == "M")
    female = sum(1 for student in students if clean_upper(student.get("sex")) == "F")
    level, arm = normalize_academic_class(class_level, class_arm)

    return {
        "class_level": level, "class_arm": arm, "total": len(students),
        "male": male, "female": female, "students": students,
    }


# ============================================================
# STUDENT TRACK
# ============================================================

def get_student_track(student, preferred_track=""):
    if not isinstance(student, dict): return ""

    level, arm = normalize_academic_class(
        student.get("class_level") or student.get("class_category") or student.get("class"),
        student.get("class_arm") or student.get("class")
    )

    if not level.startswith("SS"): return ""

    preferred = clean_upper(
        preferred_track or student.get("track") or student.get("student_track")
        or student.get("stream") or student.get("ss_stream")
    )

    return get_ss_track(arm, preferred)


# ============================================================
# SUBJECT HELPERS
# ============================================================

def normalize_academic_subject(subject): return normalize_subject_display(subject)

def academic_subject_key(subject): return normalize_subject_key(subject)


def get_subjects_for_selection(class_level, class_arm="", preferred_track=""):
    """Return official configured subjects for a class/arm/track."""
    level, arm = normalize_academic_class(class_level, class_arm)
    if not level: return []
    return get_subjects_for_class(level, arm, preferred_track)


def get_subjects_for_student(student, preferred_track=""):
    """Resolve official subjects from the student's class arm and track."""
    if not isinstance(student, dict): return []

    level, arm = normalize_academic_class(
        student.get("class_level") or student.get("class_category") or student.get("class"),
        student.get("class_arm") or student.get("class")
    )

    track = get_student_track(student, preferred_track)
    return get_subjects_for_class(level, arm, track)


def subject_is_valid_for_class(subject, class_level, class_arm="", preferred_track=""):
    wanted = normalize_subject_key(subject)
    if not wanted: return False

    allowed_keys = {
        normalize_subject_key(item)
        for item in get_subjects_for_selection(class_level, class_arm, preferred_track)
    }

    return wanted in allowed_keys


# ============================================================
# STANDARD ACADEMIC RECORD KEY
# ============================================================

def build_academic_record_key(admission_number, academic_session, term, class_level="", class_arm="", subject=""):
    """Create one normalized identity structure shared by Attendance, CA/Test and Report Sheets."""
    level, arm = normalize_academic_class(class_level, class_arm)

    return {
        "admission_number": normalize_admission_number(admission_number),
        "session": normalize_academic_session(academic_session),
        "term": normalize_academic_term(term),
        "class_level": level, "class_arm": arm,
        "subject": normalize_subject_display(subject) if subject else "",
        "subject_key": normalize_subject_key(subject) if subject else "",
    }