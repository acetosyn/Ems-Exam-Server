# MODULE: Academic Records — Shared EMIS academic/student service layer
# PURPOSE: Common student, class, session, term and subject helpers for Attendance, CA/Test and Report Sheets.
# NOTE: This module creates NO new database. students2026.csv remains the single student source through student_lookup.py.

import re

from modules.class_config import SUPPORTED_CLASSES, STUDENT_DATABASE_CLASSES, TAHFEEZ_CLASSES, ISLAMIYAH_CLASSES, CLASS_ARMS_BY_LEVEL, normalize_class_level, normalize_class_arm, normalize_subject_key, normalize_subject_display, get_subjects_for_class, get_configured_subjects_for_class, get_ss_track
from modules.school_structure import normalize_school_class, class_label, is_islamiyah_class
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
# OPERATIONAL ROSTER CLASS NORMALIZATION
#
# Report Sheets / historical academic logic continues to use the
# secondary-only normalize_academic_class() compatibility boundary
# until Phase 4. Attendance and CA/Test use the operational helpers
# below so Starter → Primary6 and Tahfeez1 → Tahfeez5 can be loaded
# safely without making lower school inherit the SS assessment model.
# ============================================================

def normalize_database_class(class_level="", class_arm=""):
    """Normalize any regular class physically stored in students2026.csv."""
    level = normalize_class_level(class_level or class_arm)
    if level not in STUDENT_DATABASE_CLASSES: return "", ""
    arm = normalize_class_arm(class_arm or class_level, level) or level
    return level, arm


def normalize_operational_class(class_level="", class_arm=""):
    """Normalize a regular students2026 class or a parallel Tahfeez class."""
    raw = normalize_school_class(class_level or class_arm)
    if raw in TAHFEEZ_CLASSES or raw in ISLAMIYAH_CLASSES: return raw, raw
    return normalize_database_class(class_level, class_arm)


def get_operational_class_arms(class_level):
    level, _ = normalize_operational_class(class_level, class_level)
    if not level: return []
    if level in TAHFEEZ_CLASSES or level in ISLAMIYAH_CLASSES: return [level]
    return list(CLASS_ARMS_BY_LEVEL.get(level, [])) or [level]


def validate_operational_class_selection(class_level="", class_arm="", require_arm=False):
    level, arm = normalize_operational_class(class_level, class_arm)
    if not level: return {"valid": False, "class_level": "", "class_arm": "", "message": "Invalid class level."}
    configured_arms = get_operational_class_arms(level)
    if require_arm and not clean(class_arm): return {"valid": False, "class_level": level, "class_arm": "", "message": f"Class selection is required for {class_label(level)}."}
    if class_arm and arm not in configured_arms: return {"valid": False, "class_level": level, "class_arm": arm, "message": f"{arm} is not a configured class for {class_label(level)}."}
    return {"valid": True, "class_level": level, "class_arm": arm, "message": "", "is_tahfeez": level in TAHFEEZ_CLASSES, "is_islamiyah": level in ISLAMIYAH_CLASSES}


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

    level, arm = normalize_database_class(
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


def student_matches_database_class(student, class_level="", class_arm=""):
    if not isinstance(student, dict): return False
    requested_level, requested_arm = normalize_database_class(class_level, class_arm)
    if not requested_level: return False
    student_level, student_arm = normalize_database_class(student.get("class_level") or student.get("class_category") or student.get("class"), student.get("class_arm") or student.get("class"))
    if student_level != requested_level: return False
    if class_arm and student_arm != requested_arm: return False
    return True


def get_database_students_for_class(class_level, class_arm="", active_only=True):
    validation = validate_operational_class_selection(class_level, class_arm)
    if not validation.get("valid") or validation.get("class_level") in TAHFEEZ_CLASSES: return []
    rows = [student for student in get_all_students(active_only=active_only) if student_matches_database_class(student, validation["class_level"], class_arm)]
    rows.sort(key=lambda student: (clean(student.get("last_name")).lower(), clean(student.get("first_name")).lower(), clean(student.get("other_names")).lower(), clean(student.get("admission_number")).lower()))
    for student in rows: student["roster_source"] = "students2026.csv"
    return rows


def get_operational_students_for_class(class_level, class_arm="", active_only=True):
    """Return Attendance/CA roster from students2026.csv or the parallel tahfeez2026.csv."""
    level, arm = normalize_operational_class(class_level, class_arm)
    if not level: return []
    if level in TAHFEEZ_CLASSES:
        try:
            from modules.tahfeez_database import get_tahfeez_students_by_class
            rows = [dict(student) for student in get_tahfeez_students_by_class(level, active_only=active_only)]
            for student in rows:
                student["class"] = arm; student["class_arm"] = arm; student["class_level"] = level; student["class_category"] = level; student["roster_source"] = "tahfeez2026.csv"
            return rows
        except Exception as error:
            print("[ACADEMIC RECORDS] Tahfeez roster read error:", error)
            return []
    if level in ISLAMIYAH_CLASSES:
        try:
            from modules.islamiyah_database import read_register
            rows = []
            for source in read_register():
                if normalize_school_class(source.get("Islamiyah_Class")) != level: continue
                academy_id = clean(source.get("Admission_number")); regular_id = clean(source.get("Regular_Admission_number"))
                row = {
                    "admission_number": academy_id, "id": academy_id, "academy_admission_number": academy_id, "regular_admission_number": regular_id,
                    "last_name": clean(source.get("Last_name")), "first_name": clean(source.get("First_name")), "other_names": clean(source.get("Other_names")),
                    "full_name": " ".join(part for part in [clean(source.get("Last_name")), clean(source.get("First_name")), clean(source.get("Other_names"))] if part),
                    "phone": clean(source.get("Phone")), "sex": clean_upper(source.get("Sex")), "class": level, "class_arm": level, "class_level": level, "class_category": level,
                    "regular_class": clean(source.get("Regular_Class")), "regular_class_level": clean_upper(source.get("Regular_Class_category")),
                    "status": "ACTIVE", "is_active": True, "roster_source": "tahfeez2026.csv / Islamiyyah roster",
                }
                rows.append(row)
            rows.sort(key=lambda student: (clean(student.get("last_name")).lower(), clean(student.get("first_name")).lower(), clean(student.get("admission_number")).lower()))
            return rows
        except Exception as error:
            print("[ACADEMIC RECORDS] Islamiyyah roster read error:", error)
            return []
    return get_database_students_for_class(level, arm, active_only=active_only)


def operational_roster_source(class_level):
    level, _ = normalize_operational_class(class_level, class_level)
    return "tahfeez2026.csv" if level in TAHFEEZ_CLASSES else "tahfeez2026.csv / Islamiyyah roster" if level in ISLAMIYAH_CLASSES else "students2026.csv" if level else ""


# ============================================================
# PHASE 4 REPORT / HISTORY OPERATIONAL HELPERS
#
# Report Sheets can now see every active regular-school class and the
# parallel Tahfeez roster. Assessment generation is still controlled by
# assessment_rules.py, so exposing a roster here never invents a score scheme.
# ============================================================

def normalize_report_class(class_level="", class_arm=""):
    return normalize_operational_class(class_level, class_arm)


def validate_report_class_selection(class_level="", class_arm="", require_arm=False):
    return validate_operational_class_selection(class_level, class_arm, require_arm=require_arm)


def get_report_class_arms(class_level):
    return get_operational_class_arms(class_level)


def get_report_students_for_class(class_level, class_arm="", active_only=True):
    return get_operational_students_for_class(class_level, class_arm, active_only=active_only)


def report_roster_source(class_level):
    return operational_roster_source(class_level)


def get_report_subjects_for_selection(class_level, class_arm="", preferred_track=""):
    return get_operational_subjects_for_selection(class_level, class_arm, preferred_track)


def get_report_subjects_for_student(student, class_level="", class_arm="", preferred_track=""):
    """Resolve the configured subject pool for a report student.

    Tahfeez rows carry the pupil's regular profile as metadata, so the requested
    report class must remain authoritative instead of accidentally resolving the
    regular Primary/JSS class.
    """
    requested_level, requested_arm = normalize_report_class(class_level, class_arm)
    if requested_level:
        preferred = preferred_track
        if requested_level.startswith("SS") and isinstance(student, dict):
            preferred = preferred or student.get("track") or student.get("ss_stream") or student.get("stream") or ""
        return get_report_subjects_for_selection(requested_level, requested_arm, preferred)
    if not isinstance(student, dict): return []
    level, arm = normalize_report_class(student.get("class_level") or student.get("class_category") or student.get("class"), student.get("class_arm") or student.get("class"))
    return get_report_subjects_for_selection(level, arm, preferred_track)


def get_operational_subjects_for_selection(class_level, class_arm="", preferred_track=""):
    level, arm = normalize_operational_class(class_level, class_arm)
    if not level: return []
    if level in TAHFEEZ_CLASSES or level in ISLAMIYAH_CLASSES: return get_configured_subjects_for_class(level, active_only=True)
    return get_subjects_for_class(level, arm, preferred_track)


def subject_is_valid_for_operational_class(subject, class_level, class_arm="", preferred_track=""):
    wanted = normalize_subject_key(subject)
    if not wanted: return False
    allowed = {normalize_subject_key(item) for item in get_operational_subjects_for_selection(class_level, class_arm, preferred_track)}
    return wanted in allowed


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
    level, arm = normalize_report_class(class_level, class_arm)

    return {
        "admission_number": normalize_admission_number(admission_number),
        "session": normalize_academic_session(academic_session),
        "term": normalize_academic_term(term),
        "class_level": level, "class_arm": arm,
        "subject": normalize_subject_display(subject) if subject else "",
        "subject_key": normalize_subject_key(subject) if subject else "",
    }