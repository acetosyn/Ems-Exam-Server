# MODULE: Report Sheet Manager — EMIS academic report aggregation, grading, statistics and cumulative results

import csv
import io
import json
import os
import uuid
import copy
from pathlib import Path
from datetime import datetime
from threading import RLock, Thread
from functools import wraps

from flask import Blueprint, jsonify, request, session, Response, send_file

from modules.academic_records import clean, clean_upper, normalize_academic_session, normalize_academic_term, academic_term_label, get_current_academic_context, normalize_academic_class, validate_class_selection, get_students_for_class, get_student, get_subjects_for_selection, get_subjects_for_student, normalize_academic_subject, academic_subject_key, normalize_report_class, validate_report_class_selection, get_report_students_for_class, get_report_subjects_for_selection, get_report_subjects_for_student, report_roster_source
from modules.student_lookup import normalize_admission_number
from modules.result_sync import queue_emis_event_safely
from modules.attendance_manager import get_student_attendance_summary, get_attendance_summary_map
from modules.ca_test_manager import get_ca_scores_map, get_ca_available_contexts
from modules.api_routes import read_results_term_aware, normalize_result_record, enrich_records_with_essay, get_subject_folders
from modules.teacher_assignment_manager import teacher_can_access_report_class, teacher_allowed_report_subjects, teacher_report_scope
from modules.islamiyah_manager import get_report_islamiyah_row, get_report_sync_roster, seed_register_enrollments
from modules.assessment_rules import get_assessment_rule, assessment_entry_enabled
from modules.grading_system import grade_score_for_class, grading_system_for_class, grading_system_ready
from modules.class_config import STUDENT_DATABASE_CLASSES, TAHFEEZ_CLASSES, ISLAMIYAH_CLASSES, CLASS_ARMS_BY_LEVEL
from modules.school_structure import class_label, school_section_for_class
from modules.subject_registry import add_registered_subject, build_subject_sync_payload
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


report_sheet_bp = Blueprint("report_sheet_bp", __name__)

BASE_DIR = Path(__file__).resolve().parent.parent
REPORT_DIR = BASE_DIR / "static" / "data" / "report_sheets"
SNAPSHOT_FILE = REPORT_DIR / "generated_reports.jsonl"
DETAILS_FILE = REPORT_DIR / "report_details.json"
DEFAULTS_FILE = REPORT_DIR / "report_defaults.json"
USAGE_FILE = REPORT_DIR / "report_usage.jsonl"
PORTAL_ACTIVE_YEARS_FILE = BASE_DIR / "static" / "portal" / "class_active_years.json"
REPORT_LOCK = RLock()
ADMIN_DELETE_AUDIT_FILE = REPORT_DIR / "admin_delete_audit.jsonl"

GRADE_SCALE = [
    ("A", 80, 100, "Excellent"),
    ("B", 70, 79.99, "Very Good"),
    ("C", 60, 69.99, "Good"),
    ("D", 45, 59.99, "Pass"),
    ("E", 40, 44.99, "Pass"),
    ("F", 0, 39.99, "Fail"),
]


# ============================================================
# ACCESS / BASIC HELPERS
# ============================================================

def report_staff_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if clean(session.get("user_type")).lower() not in {"admin", "teacher", "teacher_admin"}:
            return jsonify({"success": False, "message": "Unauthorized."}), 403
        return view(*args, **kwargs)
    return wrapped


def report_role(): return clean(session.get("user_type")).lower()
def report_teacher_id(): return clean(session.get("teacher_id") or session.get("username")).upper()
def teacher_scope_denied(academic_session, class_level, class_arm=""):
    role=report_role(); section=school_section_for_class(class_level)
    if role == "teacher_admin" and section in {"TAHFEEZ", "ISLAMIYAH"}: return jsonify({"success": False, "message": "Access denied. Teacher Admin accounts do not have Tahfeez or Islamiyyah access."}), 403
    if role != "teacher": return None
    if not teacher_can_access_report_class(report_teacher_id(), academic_session, class_level, class_arm): return jsonify({"success": False, "message": "Access denied. This class is not assigned to your Teacher ID."}), 403
    return None
def official_generation_denied():
    return None if report_role() in {"admin", "teacher_admin"} else (jsonify({"success": False, "message": "Only Admin or Teacher Admin can generate, print or export official report sheets."}), 403)

def central_admin_required_response(): return None if report_role() == "admin" else (jsonify({"success": False, "message": "Central Administrator access is required for destructive Report Sheet actions."}), 403)

def _admin_delete_actor(): return clean(session.get("admin_username") or session.get("username") or session.get("user") or "Admin")

def _scope_matches_values(source_session, source_term, source_level, source_arm, academic_session="", term="", class_level="", class_arm="", delete_all=False):
    if delete_all: return True
    if academic_session and normalize_academic_session(source_session) != normalize_academic_session(academic_session): return False
    if term and normalize_academic_term(source_term) != normalize_academic_term(term): return False
    if class_level and clean_upper(source_level) != clean_upper(class_level): return False
    if class_arm and clean_upper(source_arm) != clean_upper(class_arm): return False
    return bool(academic_session or term or class_level or class_arm)

def _scope_matches_key(key, academic_session="", term="", class_level="", class_arm="", delete_all=False):
    parts = str(key or "").split("|") + ["", "", "", "", ""]
    return _scope_matches_values(parts[0], parts[1], parts[2], parts[3], academic_session, term, class_level, class_arm, delete_all)

def _rewrite_jsonl_scope(path, academic_session="", term="", class_level="", class_arm="", delete_all=False):
    if not path.exists(): return 0
    rows=[]
    with REPORT_LOCK:
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                row=json.loads(line)
                if isinstance(row,dict): rows.append(row)
            except Exception: pass
        kept=[row for row in rows if not _scope_matches_values(row.get("session"),row.get("term"),row.get("class_level"),row.get("class_arm"),academic_session,term,class_level,class_arm,delete_all)]
        path.write_text("".join(json.dumps(row,ensure_ascii=False)+"\n" for row in kept),encoding="utf-8")
    return len(rows)-len(kept)

def _delete_json_store_scope(path, academic_session="", term="", class_level="", class_arm="", delete_all=False):
    store=_read_json_store(path); removed=[key for key in list(store) if _scope_matches_key(key,academic_session,term,class_level,class_arm,delete_all)]
    if removed:
        for key in removed: store.pop(key,None)
        _write_json_store(path,store)
    return len(removed)

def delete_report_sheet_scope(academic_session="", term="", class_level="", class_arm="", delete_all=False):
    counts={"snapshots":_rewrite_jsonl_scope(SNAPSHOT_FILE,academic_session,term,class_level,class_arm,delete_all),"manual_records":_delete_json_store_scope(MANUAL_FILE,academic_session,term,class_level,class_arm,delete_all),"report_details":_delete_json_store_scope(DETAILS_FILE,academic_session,term,class_level,class_arm,delete_all),"report_defaults":_delete_json_store_scope(DEFAULTS_FILE,academic_session,term,class_level,class_arm,delete_all),"usage_records":_rewrite_jsonl_scope(USAGE_FILE,academic_session,term,class_level,class_arm,delete_all)}
    try:
        from modules.academic_history import delete_history_scope
        counts.update(delete_history_scope(academic_session,term,class_level,class_arm,delete_all))
    except Exception as error: counts["history_warning"]=str(error)
    return counts

def _write_admin_delete_audit(action, scope, counts):
    ensure_report_dir(); row={"audit_id":uuid.uuid4().hex,"deleted_at":now_string(),"deleted_by":_admin_delete_actor(),"action":clean(action),"scope":scope,"counts":counts}
    with REPORT_LOCK:
        with ADMIN_DELETE_AUDIT_FILE.open("a",encoding="utf-8") as file: file.write(json.dumps(row,ensure_ascii=False)+"\n")
    return row

def teacher_filtered_subject_scope(scope, academic_session, class_level, class_arm=""):
    if report_role() != "teacher" or not isinstance(scope, dict): return scope
    allowed = set(teacher_allowed_report_subjects(report_teacher_id(), academic_session, class_level, class_arm)); result = dict(scope)
    subject_key = lambda row: academic_subject_key((row.get("key") or row.get("name")) if isinstance(row, dict) else row)
    available = [row for row in (scope.get("available_subjects") or []) if subject_key(row) in allowed]; selected = [row for row in (scope.get("selected_subjects") or []) if subject_key(row) in allowed]
    result["available_subjects"] = available; result["selected_subjects"] = selected; result["selected_keys"] = [subject_key(row) for row in selected if subject_key(row)]
    return result

def teacher_visible_manual_record(record, academic_session, class_level, class_arm=""):
    if report_role() != "teacher" or not isinstance(record, dict): return record
    allowed = set(teacher_allowed_report_subjects(report_teacher_id(), academic_session, class_level, class_arm)); filtered = dict(record); subjects = record.get("subjects") if isinstance(record.get("subjects"), dict) else {}
    filtered["subjects"] = {key:value for key,value in subjects.items() if academic_subject_key(key) in allowed}; return filtered

def role_manual_class_readiness(academic_session, term, class_level, class_arm):
    readiness = manual_class_readiness(academic_session, term, class_level, class_arm)
    if report_role() != "teacher": return readiness
    allowed=set(teacher_allowed_report_subjects(report_teacher_id(), academic_session, class_level, class_arm)); rows=[]
    for source in readiness.get("students", []):
        row=dict(source); missing_subjects=[key for key in row.get("missing_subjects",[]) if academic_subject_key(key) in allowed]; missing_fields=[item for item in row.get("missing_fields",[]) if academic_subject_key(str(item).split(":",1)[0]) in allowed]; incomplete_keys=set(missing_subjects)|{str(item).split(":",1)[0] for item in missing_fields}; row["missing_subjects"]=missing_subjects; row["missing_fields"]=missing_fields; row["required_subjects"]=len(allowed); row["completed_subjects"]=max(0,len(allowed)-len(incomplete_keys)); row["complete"]=bool(allowed and not missing_subjects and not missing_fields and not row.get("excluded")); rows.append(row)
    eligible=[row for row in rows if not row.get("excluded")]; ready=[row for row in eligible if row.get("complete")]; pending=[row for row in eligible if not row.get("complete")]; result=dict(readiness); result.update({"students":rows,"eligible_students":len(eligible),"ready_students":len(ready),"remaining_students":len(pending),"progress_percent":round((len(ready)/len(eligible))*100,1) if eligible else 0,"class_ready":bool(eligible) and not pending,"ready_admissions":[row.get("admission_number") for row in ready],"eligible_admissions":[row.get("admission_number") for row in eligible],"pending":pending,"subject_scope":teacher_filtered_subject_scope(readiness.get("subject_scope") or {},academic_session,class_level,class_arm)}); return result

def now_string(): return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def normalize_next_term_date(value):
    text = clean(value)
    if not text: return ""
    try: return datetime.strptime(text[:10], "%Y-%m-%d").strftime("%Y-%m-%d")
    except (TypeError, ValueError): return ""


def next_term_required_response(value):
    raw, normalized = clean(value), normalize_next_term_date(value)
    if normalized: return normalized, None
    message = "Set Next Term Begins before loading students or generating report sheets." if not raw else "Enter a valid Next Term Begins date before loading students or generating report sheets."
    return "", (jsonify({"success": False, "status": "next_term_required", "message": message}), 400)


def apply_requested_next_term(payload, next_term):
    if not isinstance(payload, dict) or not next_term: return payload
    payload["next_term"] = next_term
    for report in payload.get("reports", []) if isinstance(payload.get("reports"), list) else []: report["next_term"] = next_term
    return payload


def safe_float(value, default=0.0):
    try:
        if value in (None, ""): return default
        return float(str(value).replace("%", "").replace(",", "").strip())
    except (TypeError, ValueError): return default


def pretty_number(value):
    number = safe_float(value)
    return int(number) if number.is_integer() else round(number, 2)


def request_class_values(source=None):
    source = source or request.args
    class_level = source.get("class_level") or source.get("class_category") or source.get("level") or source.get("class") or ""
    class_arm = source.get("class_arm") or source.get("arm") or source.get("class_name") or source.get("class") or ""
    return class_level, class_arm


def resolve_context(session_value="", term_value=""):
    # Normal Teachers always work inside the centrally configured active academic period.
    # Admin / Teacher Admin may still select historical periods for official report work.
    context = get_current_academic_context("", "") if report_role() == "teacher" else get_current_academic_context(session_value, term_value)
    return normalize_academic_session(context.get("academic_session") or context.get("session")), normalize_academic_term(context.get("term"))


def resolve_class(class_level="", class_arm="", require_arm=True):
    level, arm = normalize_report_class(class_level or class_arm, class_arm or class_level)
    result = validate_report_class_selection(level, class_arm or arm, require_arm=require_arm)
    if not result.get("valid"): return "", "", result.get("message") or "Invalid class selection."
    return result["class_level"], result["class_arm"], ""


# ============================================================
# RESULT YEAR RESOLUTION — SESSION YEAR + ACTIVE PORTAL FALLBACK
# ============================================================

def read_portal_active_years():
    try:
        if not PORTAL_ACTIVE_YEARS_FILE.exists(): return {}
        data = json.loads(PORTAL_ACTIVE_YEARS_FILE.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except Exception as error:
        print("REPORT ACTIVE YEAR READ ERROR:", error); return {}


def get_portal_active_result_year(class_level="", class_arm=""):
    level, arm = normalize_academic_class(class_level or class_arm, class_arm or class_level)
    active_years = read_portal_active_years()
    return clean(active_years.get(arm) or active_years.get(level))


def session_result_year(academic_session=""):
    academic_session = normalize_academic_session(academic_session)
    if "/" in academic_session:
        first = clean(academic_session.split("/", 1)[0])
        if first.isdigit(): return first
    return ""


def resolve_result_year(academic_session="", explicit_year="", class_level="", class_arm=""):
    explicit = clean(explicit_year)
    if explicit: return explicit

    # Report session is authoritative for historical report generation:
    # 2026/2027 -> RESULTS/2026. Active portal year is a fallback when
    # the session does not provide a usable start year.
    session_year = session_result_year(academic_session)
    if session_year: return session_year

    active_year = get_portal_active_result_year(class_level, class_arm)
    if active_year: return active_year

    return str(datetime.now().year)


# ============================================================
# GRADING / COMMENTS
# ============================================================

def grade_for_score(score, class_level=""):
    if class_level:
        return grade_score_for_class(score, class_level)
    score = safe_float(score)
    for grade, minimum, maximum, comment in GRADE_SCALE:
        if minimum <= score <= maximum: return grade, comment
    return "F", "Fail"


def teacher_remark(average):
    average = safe_float(average)

    if average >= 80: return "An excellent student with great potentials."
    if average >= 70: return "A very good performance. Keep it up."
    if average >= 60: return "A good result with room for more improvement."
    if average >= 45: return "An average performance. More effort is needed."
    return "Poor performance. Serious improvement is required."


def principal_remark(average):
    average = safe_float(average)

    if average >= 80: return "An excellent result."
    if average >= 70: return "A very good result. Keep it up."
    if average >= 60: return "Good result."
    if average >= 45: return "Average performance."
    return "Unsatisfactory performance."


def compute_position(score, scores):
    score = safe_float(score)
    return sum(1 for other in scores if safe_float(other) > score) + 1


def ordinal(number):
    number = int(number or 0)

    if not number: return "--"
    if 10 <= number % 100 <= 20: suffix = "th"
    else: suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")

    return f"{number}{suffix}"


# ============================================================
# EXAM RESULT HELPERS
# ============================================================

def exam_percentage(row):
    if not isinstance(row, dict): return None

    # Essay-enriched CBT records expose result_state. Never convert an
    # objective-only "AWAITING ESSAY" record into a false final exam score.
    result_state = clean_upper(row.get("result_state") or row.get("Result State") or row.get("result_status"))
    if result_state and result_state != "COMPLETE": return None

    final_candidates = ["final_score", "combined_score", "total_score", "Final Score (%)", "Final Score", "Combined Score (%)", "Combined Score", "Overall Score (%)", "Overall Score"]
    for field in final_candidates:
        value = row.get(field)
        if value not in (None, ""): return max(0.0, min(100.0, safe_float(value)))

    # Legacy objective-only results may not have essay enrichment/state.
    if not result_state:
        for field in ["Score (%)", "Score Number", "score_percentage", "percentage", "score"]:
            value = row.get(field)
            if value not in (None, ""): return max(0.0, min(100.0, safe_float(value)))

    return None


def scale_exam_score(row, class_level):
    percentage = exam_percentage(row)
    if percentage is None: return None
    maximum = optional_float((get_assessment_rule(class_level) or {}).get("exam_max"))
    if maximum is None: return None
    return round((percentage / 100) * maximum, 2)


def result_row_timestamp(row):
    value = clean(row.get("Submitted At") or row.get("submitted_at"))

    if not value: return datetime.min

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S"):
        try: return datetime.strptime(value[:19], fmt)
        except ValueError: pass

    return datetime.min


def exam_row_matches(row, academic_session, class_level, class_arm):
    row_level, row_arm = normalize_academic_class(row.get("Class Level") or row.get("Class Category") or row.get("Class"), row.get("Class Arm") or row.get("Class"))

    if row_level != class_level: return False
    if row_arm and row_arm != class_level and row_arm != class_arm: return False

    # Result year + term are already enforced by the RESULTS folder being read.
    # A reused historical JSON may carry an old Session value, so Session metadata
    # must not reject a valid result saved in the selected current result year.
    return True


def load_exam_results_map(academic_session, term, class_level, class_arm, result_year):
    academic_session = normalize_academic_session(academic_session)
    term = normalize_academic_term(term)
    level, arm = normalize_report_class(class_level, class_arm)
    # Current CBT/Essay result storage is still a secondary-school engine.
    # Lower School/Tahfeez become report-ready through configured assessment
    # rules and Manual/Hybrid entry without pretending that a CBT source exists.
    if not (level.startswith("JSS") or level.startswith("SS")): return {}, {}

    exam_map, subject_names = {}, {}
    subject_folders = get_subject_folders(result_year, level, term)

    for subject_folder in subject_folders:
        try:
            rows = read_results_term_aware(level, subject_folder, result_year, term)

            for row in rows:
                normalize_result_record(row, level, subject_folder, result_year, term)

            enrich_records_with_essay(rows, level, subject_folder, result_year, term)

        except Exception as error:
            print(f"REPORT EXAM READ ERROR [{result_year}/{level}/{term}/{subject_folder}]:", error)
            continue

        for row in rows:
            if not exam_row_matches(row, academic_session, level, arm): continue

            admission = normalize_admission_number(row.get("Admission No") or row.get("admission_number") or row.get("student_id"))
            subject = normalize_academic_subject(row.get("Subject") or subject_folder)
            subject_key = academic_subject_key(subject)

            if not admission or not subject_key: continue

            exam_map.setdefault(admission, {})
            subject_names[subject_key] = subject

            previous = exam_map[admission].get(subject_key)

            if not previous or result_row_timestamp(row) >= result_row_timestamp(previous):
                exam_map[admission][subject_key] = row

    return exam_map, subject_names


# ============================================================
# REPORT SUBJECT ROW / PARTIAL DATA HELPERS
# ============================================================

def optional_float(value):
    if value in (None, ""): return None
    try: return float(str(value).replace("%", "").replace(",", "").strip())
    except (TypeError, ValueError): return None


def pretty_optional(value):
    number = optional_float(value)
    return pretty_number(number) if number is not None else None


def _assessment_component_values(ca, class_level):
    ca = ca if isinstance(ca, dict) else {}; rule = get_assessment_rule(class_level) or {}; components = ca.get("components") if isinstance(ca.get("components"), dict) else {}; values, definitions = {}, []
    for field in rule.get("fields") or []:
        if not isinstance(field, dict): continue
        raw_key = clean_upper(field.get("key")); key = raw_key.lower(); label = clean(field.get("label") or raw_key); maximum = optional_float(field.get("max"))
        value = components.get(key) if key in components else components.get(raw_key)
        if value in (None, ""): value = ca.get(key) if key in ca else ca.get(raw_key)
        value = pretty_optional(value)
        values[key] = value; definitions.append({"key": key, "raw_key": raw_key, "label": label, "max": maximum, "value": value})
    return values, definitions


def build_subject_row(class_level, subject_key, ca=None, exam_row=None, subject_name=""):
    """Build a scheme-aware subject row without treating unconfigured lower school as SS."""
    ca, exam_row = ca if isinstance(ca, dict) else {}, exam_row if isinstance(exam_row, dict) else {}; rule = get_assessment_rule(class_level) or {}; mode = clean_upper(rule.get("key")) or "UNKNOWN"
    subject = normalize_academic_subject(ca.get("subject") or exam_row.get("Subject") or subject_name or subject_key); values, definitions = _assessment_component_values(ca, class_level)
    has_ca, has_exam = bool(ca), bool(exam_row); ca_complete = bool(ca.get("complete")) if has_ca else False; ca_total = optional_float(ca.get("ca_total")) if has_ca else None; exam_score = scale_exam_score(exam_row, class_level) if has_exam else None; exam_complete = exam_score is not None
    complete = bool(ca_complete and exam_complete); total = round((ca_total or 0) + exam_score, 2) if complete else None; grade, comment = grade_for_score(total, class_level) if total is not None else ("-", "Pending")
    row = {"subject": subject, "subject_key": subject_key, "mode": mode, "assessment_mode": mode, "assessment_status": clean(rule.get("status")), "has_ca": has_ca, "has_exam": has_exam, "exam_complete": exam_complete, "ca_complete": ca_complete, "complete": complete, "components": values, "component_fields": definitions, "ca_total": pretty_optional(ca_total), "ca_max": pretty_optional(rule.get("ca_max")), "exam": pretty_optional(exam_score), "exam_max": pretty_optional(rule.get("exam_max")), "total": pretty_optional(total), "total_max": pretty_optional(rule.get("total_max") or 100), "grade": grade, "comment": comment, "position": 0, "position_text": "--", "out_of": 0, "lowest": None, "highest": None, "class_average": None}
    # Legacy keys remain for the established JSS/SS Report Sheet renderer.
    if mode == "JSS": row.update({"ca1": values.get("ca1"), "ca2": values.get("ca2"), "test1": values.get("test1"), "test2": values.get("test2")})
    elif mode == "SS": row.update({"ass1": values.get("ass1"), "ass2": values.get("ass2"), "test": values.get("test")})
    return row


def expected_subject_map(student, class_level, class_arm):
    subjects = get_report_subjects_for_student(student, class_level, class_arm) or get_report_subjects_for_selection(class_level, class_arm)
    output = {}
    for subject in subjects:
        key = academic_subject_key(subject)
        if key: output[key] = normalize_academic_subject(subject)
    return output


# ============================================================
# STUDENT-SPECIFIC REPORT SUBJECT RESOLUTION
# ============================================================

def resolve_report_subject_keys(allowed_subjects, ca_records=None, exam_records=None):
    """Return only subjects this student actually has CA/Test and/or Exam records for, ordered by the configured class/stream subject pool."""
    allowed_subjects = allowed_subjects if isinstance(allowed_subjects, dict) else {}; ca_records = ca_records if isinstance(ca_records, dict) else {}; exam_records = exam_records if isinstance(exam_records, dict) else {}
    actual_keys = set(ca_records) | set(exam_records)
    if not actual_keys: return [], []
    if not allowed_subjects: return sorted(actual_keys), []
    ordered = [key for key in allowed_subjects if key in actual_keys]
    excluded = sorted(actual_keys - set(allowed_subjects))
    return ordered, excluded


# ============================================================
# SOURCE STATUS
# ============================================================

def build_student_source_status(student, ca_records, exam_records, attendance):
    ca_records = ca_records if isinstance(ca_records, dict) else {}; exam_records = exam_records if isinstance(exam_records, dict) else {}
    ca_keys, exam_keys = set(ca_records), set(exam_records); complete_ca_keys = {key for key, record in ca_records.items() if isinstance(record, dict) and record.get("complete")}
    complete_exam_keys = {key for key, record in exam_records.items() if isinstance(record, dict) and exam_percentage(record) is not None}
    matched = sorted(ca_keys & exam_keys); matched_complete = sorted(complete_ca_keys & complete_exam_keys)

    if matched_complete: status, label = "ready", "CA/Test + Final CBT Found"
    elif ca_keys and exam_keys and not complete_exam_keys: status, label = "exam_pending", "CBT Found • Final Exam Score Pending"
    elif ca_keys and exam_keys: status, label = "partial_ca", "Academic Scores Partially Ready"
    elif ca_keys: status, label = "missing_exam", "CA/Test Found • Exam Pending"
    elif exam_keys: status, label = "missing_ca", "CBT Found • CA/Test Missing"
    elif attendance: status, label = "scores_pending", "Attendance Found • Scores Pending"
    else: status, label = "scores_pending", "Scores Pending"

    return {**student, "status": status, "status_label": label, "has_ca": bool(ca_keys), "has_complete_ca": bool(complete_ca_keys), "has_exam": bool(exam_keys), "has_complete_exam": bool(complete_exam_keys), "has_attendance": bool(attendance), "ca_subjects": sorted(ca_keys), "ca_complete_subjects": sorted(complete_ca_keys), "exam_subjects": sorted(exam_keys), "exam_complete_subjects": sorted(complete_exam_keys), "matched_subjects": matched, "matched_complete_subjects": matched_complete, "missing_ca_subjects": sorted(complete_exam_keys - ca_keys), "missing_exam_subjects": sorted(ca_keys - complete_exam_keys)}


# ============================================================
# CORE TERM REPORT GENERATOR — PARTIAL DATA SAFE
# ============================================================

def build_term_report_payload(academic_session, term, class_level, class_arm, result_year="", admission_number="", include_cumulative=True):
    academic_session, term = normalize_academic_session(academic_session), normalize_academic_term(term)
    level, arm = normalize_report_class(class_level, class_arm); result_year = resolve_result_year(academic_session, result_year, level, arm); rule = get_assessment_rule(level) or {}; generation_enabled = assessment_entry_enabled(level)
    students = get_report_students_for_class(level, arm, active_only=True)
    if admission_number:
        wanted = normalize_admission_number(admission_number); students = [student for student in students if normalize_admission_number(student.get("admission_number")) == wanted]

    attendance_map = get_attendance_summary_map(academic_session, term, level, arm); ca_map = get_ca_scores_map(academic_session, term, level, arm) if generation_enabled else {}; exam_map, exam_subject_names = load_exam_results_map(academic_session, term, level, arm, result_year) if generation_enabled else ({}, {})
    ca_contexts = [] if ca_map or not generation_enabled else get_ca_available_contexts(level, arm); reports, blocked, source_students, readiness_warnings, subject_scores, subject_catalog = [], [], [], [], {}, set()

    # Starter/Nursery/Primary/Tahfeez rosters are active now, but report score
    # generation remains safely locked until the school's assessment scheme is
    # configured. This lets the UI load real students without inventing marks.
    if not generation_enabled:
        for student in students:
            admission = normalize_admission_number(student.get("admission_number")); attendance = attendance_map.get(admission, {}); source_students.append({**student, "status": "assessment_pending", "status_label": rule.get("message") or "Assessment scheme pending", "has_ca": False, "has_complete_ca": False, "has_exam": False, "has_complete_exam": False, "has_attendance": bool(attendance), "ca_subjects": [], "ca_complete_subjects": [], "exam_subjects": [], "exam_complete_subjects": [], "matched_subjects": [], "matched_complete_subjects": [], "missing_ca_subjects": [], "missing_exam_subjects": [], "assessment_pending": True})
        summary = {"students_in_class": len(students), "generated": 0, "blocked": len(students), "complete_reports": 0, "partial_reports": 0, "reports_with_ca": 0, "reports_with_exam": 0, "reports_with_attendance": sum(1 for student in students if attendance_map.get(normalize_admission_number(student.get("admission_number")))), "subjects": len(get_report_subjects_for_selection(level, arm)), "class_average": None, "highest_average": None, "lowest_average": None, "missing_ca": len(students), "missing_exam": len(students), "missing_attendance": sum(1 for student in students if not attendance_map.get(normalize_admission_number(student.get("admission_number"))))}
        return {"success": True, "generation_enabled": False, "status": "assessment_scheme_pending", "assessment": rule, "assessment_message": rule.get("message"), "roster_source": report_roster_source(level), "session": academic_session, "term": term, "term_label": academic_term_label(term), "result_year": result_year, "class_level": level, "class_arm": arm, "students": source_students, "reports": [], "blocked_students": source_students, "readiness_warnings": [], "summary": summary, "source_status": {"students": bool(students), "ca_test": False, "exam_results": False, "attendance": bool(attendance_map), "assessment_ready": False, "assessment_pending": True, "roster_source": report_roster_source(level)}, "ca_available_contexts": []}

    for student in students:
        admission = normalize_admission_number(student.get("admission_number")); student_ca = ca_map.get(admission, {}); student_exam = exam_map.get(admission, {}); attendance = attendance_map.get(admission, {})
        source = build_student_source_status(student, student_ca, student_exam, attendance); source_students.append(source)
        expected = expected_subject_map(student, level, arm); subject_keys, excluded_subjects = resolve_report_subject_keys(expected, student_ca, student_exam); subject_rows = []
        for subject_key in subject_keys:
            row = build_subject_row(level, subject_key, student_ca.get(subject_key), student_exam.get(subject_key), expected.get(subject_key) or exam_subject_names.get(subject_key) or subject_key); subject_rows.append(row); subject_catalog.add(subject_key)
            if row.get("total") is not None: subject_scores.setdefault(subject_key, []).append(safe_float(row.get("total")))
        complete_rows = [row for row in subject_rows if row.get("complete") and row.get("total") is not None]; all_subjects_complete = bool(subject_rows) and len(complete_rows) == len(subject_rows); provisional_total = round(sum(safe_float(row.get("total")) for row in complete_rows), 2) if complete_rows else None; provisional_maximum = round(sum(safe_float(row.get("total_max"), 100) for row in complete_rows), 2) if complete_rows else None; provisional_average = round(provisional_total / provisional_maximum * 100, 2) if provisional_total is not None and provisional_maximum else None; total_score = provisional_total if all_subjects_complete else None; maximum_score = provisional_maximum if all_subjects_complete else None; average = provisional_average if all_subjects_complete else None; final_grade = grade_for_score(average, level)[0] if average is not None else "-"
        if not source.get("has_ca") or not source.get("has_exam") or not all_subjects_complete:
            missing = [];
            if not source.get("has_ca"): missing.append("CA/Test")
            if not source.get("has_exam"): missing.append("Exam")
            if not source.get("has_attendance"): missing.append("Attendance")
            if source.get("has_ca") and not source.get("has_complete_ca"): missing.append("Complete CA")
            readiness_warnings.append({"admission_number": student.get("admission_number"), "full_name": student.get("full_name"), "missing": missing, "status": source.get("status"), "status_label": source.get("status_label")})
        reports.append({"admission_number": student.get("admission_number"), "full_name": student.get("full_name"), "last_name": student.get("last_name"), "first_name": student.get("first_name"), "other_names": student.get("other_names"), "sex": student.get("sex"), "class_level": level, "class_arm": arm, "session": academic_session, "term": term, "term_label": academic_term_label(term), "result_year": result_year, "assessment": rule, "assessment_mode": clean_upper(rule.get("key")), "roster_source": report_roster_source(level), "subjects": subject_rows, "subject_count": len(subject_rows), "subjects_complete": len(complete_rows), "academic_complete": all_subjects_complete, "academic_partial": bool(student_ca or student_exam) and not all_subjects_complete, "has_ca": bool(student_ca), "has_exam": bool(student_exam), "has_attendance": bool(attendance), "total_score": pretty_optional(total_score), "maximum_score": pretty_optional(maximum_score), "average": pretty_optional(average), "provisional_total": pretty_optional(provisional_total), "provisional_maximum": pretty_optional(provisional_maximum), "provisional_average": pretty_optional(provisional_average), "grade": final_grade, "position": 0, "position_text": "--", "out_of": 0, "attendance": attendance, "teacher_remark": teacher_remark(average) if average is not None else "", "principal_remark": principal_remark(average) if average is not None else "", "missing_ca_subjects": source["missing_ca_subjects"], "missing_exam_subjects": source["missing_exam_subjects"], "excluded_subjects": excluded_subjects, "source_status": source.get("status"), "source_status_label": source.get("status_label")})

    for report in reports:
        for row in report.get("subjects", []):
            if row.get("total") is None: continue
            scores = subject_scores.get(row.get("subject_key"), [])
            if not scores: continue
            position = compute_position(row.get("total"), scores); row.update({"position": position, "position_text": ordinal(position), "out_of": len(scores), "lowest": pretty_number(min(scores)), "highest": pretty_number(max(scores)), "class_average": pretty_number(sum(scores) / len(scores))})
    averages = [safe_float(report.get("average")) for report in reports if report.get("average") is not None]
    for report in reports:
        if report.get("average") is None: continue
        position = compute_position(report.get("average"), averages); report["position"] = position; report["position_text"] = ordinal(position); report["out_of"] = len(averages)
    summary = {"students_in_class": len(students), "generated": len(reports), "blocked": len(blocked), "complete_reports": sum(1 for report in reports if report.get("academic_complete")), "partial_reports": sum(1 for report in reports if not report.get("academic_complete")), "reports_with_ca": sum(1 for report in reports if report.get("has_ca")), "reports_with_exam": sum(1 for report in reports if report.get("has_exam")), "reports_with_attendance": sum(1 for report in reports if report.get("has_attendance")), "subjects": len(subject_catalog), "class_average": pretty_number(sum(averages) / len(averages)) if averages else None, "highest_average": pretty_number(max(averages)) if averages else None, "lowest_average": pretty_number(min(averages)) if averages else None, "missing_ca": sum(1 for item in source_students if not item.get("has_ca")), "missing_exam": sum(1 for item in source_students if not item.get("has_exam")), "missing_attendance": sum(1 for item in source_students if not item.get("has_attendance"))}
    payload = {"success": bool(reports), "generation_enabled": True, "assessment": rule, "assessment_message": rule.get("message"), "roster_source": report_roster_source(level), "session": academic_session, "term": term, "term_label": academic_term_label(term), "result_year": result_year, "class_level": level, "class_arm": arm, "students": source_students, "reports": reports, "blocked_students": blocked, "readiness_warnings": readiness_warnings, "summary": summary, "source_status": {"students": bool(students), "ca_test": bool(ca_map), "exam_results": bool(exam_map), "attendance": bool(attendance_map), "assessment_ready": True, "assessment_pending": False, "roster_source": report_roster_source(level), "ca_context_mismatch": bool(not ca_map and ca_contexts)}, "ca_available_contexts": ca_contexts}
    if term == "THIRD" and include_cumulative and reports: attach_cumulative_results(payload, academic_session, level, arm, result_year)
    return payload


# ============================================================
# THIRD TERM CUMULATIVE ENGINE — PARTIAL DATA SAFE
# ============================================================

def report_map(payload): return {normalize_admission_number(report.get("admission_number")): report for report in (payload or {}).get("reports", []) if normalize_admission_number(report.get("admission_number"))}


def subject_total_map(report):
    return {row.get("subject_key"): safe_float(row.get("total")) for row in (report or {}).get("subjects", []) if row.get("subject_key") and row.get("total") is not None}


# ============================================================
# TRUE ANNUAL SUBJECT ENGINE — 1ST + 2ND + 3RD TERM TRACEABLE
# ============================================================

def _annual_subject_map(report): return {clean_upper(row.get("subject_key") or row.get("subject")): row for row in (report or {}).get("subjects", []) if clean_upper(row.get("subject_key") or row.get("subject"))}
def _annual_mean(values): values = [optional_float(value) for value in values]; values = [value for value in values if value is not None]; return round(sum(values) / len(values), 2) if values else None

def _annual_component_value(row, key):
    row = row if isinstance(row, dict) else {}; components = row.get("components") if isinstance(row.get("components"), dict) else {}; key = clean(key).lower(); return optional_float(components.get(key) if key in components else components.get(key.upper()) if key.upper() in components else row.get(key))

def _annual_component_keys(report, base_row=None):
    assessment = (report or {}).get("assessment") if isinstance((report or {}).get("assessment"), dict) else {}; keys = [clean_upper(field.get("key")).lower() for field in assessment.get("fields") or [] if isinstance(field, dict) and clean_upper(field.get("key"))]
    if keys: return keys
    mode = clean_upper((base_row or {}).get("mode") or (base_row or {}).get("assessment_mode") or (report or {}).get("assessment_mode")); return ["ca1","ca2","test1","test2"] if mode == "JSS" else ["ass1","ass2","test"] if mode == "SS" else []

def cumulative_next_class_name(class_level):
    raw = clean_upper(class_level).replace("_", " ").replace("-", " "); key = "".join(ch for ch in raw if ch.isalnum())
    direct = {"CRECHE":"STARTER","STARTER":"PRE-CLASS","PRECLASS":"NURSERY 1","NURSERY1":"NURSERY 2","NURSERY2":"PRIMARY 1","JSS1":"JSS2","JSS2":"JSS3","JSS3":"SS1","SS1":"SS2","SS2":"SS3","SS3":"GRADUATED","TAHFEEZ1":"TAHFEEZ2","TAHFEEZ2":"TAHFEEZ3","TAHFEEZ3":"TAHFEEZ4","TAHFEEZ4":"TAHFEEZ5","TAHFEEZ5":"COMPLETED TAHFEEZ"}
    if key in direct: return direct[key]
    for prefix, label in (("PRIMARY", "PRIMARY"), ("BASIC", "BASIC")):
        if key.startswith(prefix):
            number = optional_float(key[len(prefix):]); number = int(number) if number is not None else 0
            if 1 <= number < 5: return f"{label} {number + 1}"
            if number >= 5: return "JSS1"
    return "NEXT CLASS"

def cumulative_current_class_name(class_level):
    raw = clean_upper(class_level).replace("_", " ").replace("-", " "); return class_label(class_level) or raw or "CURRENT CLASS"

def cumulative_promotion_decision(annual_average, complete=True, class_level=""):
    average = optional_float(annual_average)
    if not complete or average is None: return "PENDING", ""
    if average >= 45:
        next_class = cumulative_next_class_name(class_level)
        if next_class == "GRADUATED": return "GRADUATED", ""
        if next_class == "COMPLETED TAHFEEZ": return "GRADUATED", "COMPLETED TAHFEEZ"
        return "PROMOTED", f"TO {next_class}"
    return "REPEATED", f"REMAIN IN {cumulative_current_class_name(class_level)}"

def build_true_cumulative_report(third_report, first_report, second_report, class_level, promotion_status="PENDING", promotion_note=""):
    """Create a separate annual report copy without changing the real Third Term sheet.

    Every CA/Test/Exam value shown on this cumulative copy is the arithmetic mean of that
    component across the available First, Second and Third Term records. The raw term rows
    remain untouched so normal Third Term printing stays identical to First/Second Term.
    """
    third_report, first_report, second_report = third_report if isinstance(third_report, dict) else {}, first_report if isinstance(first_report, dict) else {}, second_report if isinstance(second_report, dict) else {}; output = copy.deepcopy(third_report); term_reports = [first_report, second_report, third_report]; term_maps = [_annual_subject_map(report) for report in term_reports]; ordered = []
    for report in [third_report, first_report, second_report]:
        for row in report.get("subjects", []) if isinstance(report, dict) else []:
            key = clean_upper(row.get("subject_key") or row.get("subject")); name = clean(row.get("subject") or row.get("subject_key"));
            if key and all(item[0] != key for item in ordered): ordered.append((key, name))
    rows = []
    for key, name in ordered:
        term_rows = [mapping.get(key) for mapping in term_maps]; base = next((row for row in [term_rows[2], term_rows[0], term_rows[1]] if isinstance(row, dict)), {}) or {}; row = copy.deepcopy(base); component_keys = _annual_component_keys(third_report or first_report or second_report, base); totals = [optional_float((item or {}).get("total")) for item in term_rows]; available_totals = [value for value in totals if value is not None]; annual_average = _annual_mean(totals); grade, comment = grade_for_score(annual_average, class_level) if annual_average is not None else ("-", "Pending")
        cumulative_components = {component: pretty_optional(_annual_mean([_annual_component_value(item, component) for item in term_rows])) for component in component_keys}; ca_total = _annual_mean([optional_float((item or {}).get("ca_total")) for item in term_rows]); exam = _annual_mean([optional_float((item or {}).get("exam")) for item in term_rows]); terms_available = len(available_totals); proof = " + ".join(str(pretty_number(value)) if value is not None else "—" for value in totals)
        row.update({"subject": name or clean(base.get("subject")) or key, "subject_key": clean(base.get("subject_key")) or key, "cumulative_components": cumulative_components, "cumulative_ca_total": pretty_optional(ca_total), "cumulative_exam": pretty_optional(exam), "first_term_total": pretty_optional(totals[0]), "second_term_total": pretty_optional(totals[1]), "third_term_total": pretty_optional(totals[2]), "cumulative_three_term_total": pretty_optional(sum(available_totals) if available_totals else None), "cumulative_total_100": pretty_optional(annual_average), "cumulative_total": pretty_optional(sum(available_totals) if available_totals else None), "cumulative_average": pretty_optional(annual_average), "cumulative_grade": grade, "cumulative_comment": comment if terms_available == 3 else f"{terms_available}/3 terms • {comment}", "terms_available": terms_available, "cumulative_proof": f"{proof} ÷ {terms_available} = {pretty_number(annual_average)}%" if annual_average is not None and terms_available else "Pending term data", "cumulative_position": 0, "cumulative_position_text": "--", "cumulative_out_of": 0, "cumulative_class_average": None, "cumulative_lowest": None, "cumulative_highest": None})
        rows.append(row)
    output["subjects"] = rows; output["subject_count"] = len(rows); output["report_variant"] = "cumulative"; output["is_cumulative_report"] = True; output["show_promotion_decision"] = True; output["promotion_status"] = promotion_status; output["promotion_note"] = promotion_note; output["attendance"] = copy.deepcopy(output.get("cumulative_attendance") or output.get("attendance") or {}); output["teacher_remark"] = teacher_remark(optional_float(output.get("cumulative_average"))) if optional_float(output.get("cumulative_average")) is not None else output.get("teacher_remark", ""); output["principal_remark"] = principal_remark(optional_float(output.get("cumulative_average"))) if optional_float(output.get("cumulative_average")) is not None else output.get("principal_remark", "")
    return output

def finalize_true_cumulative_subject_statistics(reports):
    subject_scores = {}
    for report in reports or []:
        for row in report.get("subjects", []):
            key = clean_upper(row.get("subject_key") or row.get("subject")); average = optional_float(row.get("cumulative_average"));
            if key and row.get("terms_available") == 3 and average is not None: subject_scores.setdefault(key, []).append(average)
    for report in reports or []:
        for row in report.get("subjects", []):
            key = clean_upper(row.get("subject_key") or row.get("subject")); average = optional_float(row.get("cumulative_average")); scores = subject_scores.get(key, [])
            if row.get("terms_available") != 3 or average is None or not scores: continue
            position = compute_position(average, scores); row.update({"cumulative_position": position, "cumulative_position_text": ordinal(position), "cumulative_out_of": len(scores), "cumulative_lowest": pretty_optional(min(scores)), "cumulative_highest": pretty_optional(max(scores)), "cumulative_class_average": pretty_optional(sum(scores) / len(scores))})
    return reports


def combine_attendance_summaries(*items):
    output = {"days_open": 0, "present": 0, "absent": 0, "late": 0, "sick": 0, "excused": 0, "unmarked": 0, "present_credit": 0, "absent_total": 0, "attendance_percentage": 0}
    for item in items:
        if not isinstance(item, dict): continue
        for key in ["days_open", "present", "absent", "late", "sick", "excused", "unmarked", "present_credit", "absent_total"]: output[key] += int(safe_float(item.get(key)))
    output["attendance_percentage"] = round((output["present_credit"] / output["days_open"]) * 100, 1) if output["days_open"] else 0
    return output


def attach_cumulative_results(third_payload, academic_session, class_level, class_arm, result_year, mode="auto", first_payload=None, second_payload=None):
    """Attach First/Second/Third term annual data to a Third Term payload.

    mode controls where First/Second Term values come from. Automatic uses the verified EMIS sources,
    Manual uses saved teacher-entered records, and Hybrid uses automatic data with approved manual gaps.
    Islamiyyah is always injected afterwards from the dedicated Academy source and is never manually editable here.
    """
    mode = clean(mode or "auto").lower(); first, second = first_payload if isinstance(first_payload, dict) else None, second_payload if isinstance(second_payload, dict) else None
    if first is None or second is None:
        if mode == "manual": first = first or build_manual_report_payload(academic_session, "FIRST", class_level, class_arm); second = second or build_manual_report_payload(academic_session, "SECOND", class_level, class_arm)
        elif mode == "hybrid": first = first or build_hybrid_report_payload(academic_session, "FIRST", class_level, class_arm, result_year); second = second or build_hybrid_report_payload(academic_session, "SECOND", class_level, class_arm, result_year)
        else: first = first or build_term_report_payload(academic_session, "FIRST", class_level, class_arm, result_year, include_cumulative=False); second = second or build_term_report_payload(academic_session, "SECOND", class_level, class_arm, result_year, include_cumulative=False)
    first_map, second_map = report_map(first), report_map(second)
    for report in third_payload.get("reports", []):
        admission = normalize_admission_number(report.get("admission_number")); first_report, second_report = first_map.get(admission), second_map.get(admission); first_subjects, second_subjects = subject_total_map(first_report), subject_total_map(second_report)
        for row in report.get("subjects", []):
            key = row.get("subject_key"); first_total, second_total = first_subjects.get(key), second_subjects.get(key); third_total = optional_float(row.get("total")); available = [value for value in [first_total, second_total, third_total] if value is not None]
            cumulative_average = round(sum(available) / len(available), 2) if available else None; cumulative_grade, cumulative_comment = grade_for_score(cumulative_average, class_level) if cumulative_average is not None else ("-", "Pending")
            row.update({"first_term_total": pretty_optional(first_total), "second_term_total": pretty_optional(second_total), "third_term_total": pretty_optional(third_total), "cumulative_total": pretty_optional(sum(available) if available else None), "cumulative_average": pretty_optional(cumulative_average), "cumulative_grade": cumulative_grade, "cumulative_comment": cumulative_comment, "terms_available": len(available)})
        term_averages = [optional_float((first_report or {}).get("average")), optional_float((second_report or {}).get("average")), optional_float(report.get("average"))]; valid_averages = [value for value in term_averages if value is not None]
        cumulative_average = round(sum(valid_averages) / len(valid_averages), 2) if valid_averages else None; cumulative_grade = grade_for_score(cumulative_average, class_level)[0] if cumulative_average is not None else "-"
        term_reports = [first_report, second_report, report]; term_scores = [optional_float((item or {}).get("total_score")) for item in term_reports]; term_maximums = [int((item or {}).get("subject_count") or len((item or {}).get("subjects") or [])) * 100 if item else None for item in term_reports]; valid_score_pairs = [(score, maximum) for score, maximum in zip(term_scores, term_maximums) if score is not None and maximum]
        cumulative_score = round(sum(score for score, _ in valid_score_pairs), 2) if valid_score_pairs else None; cumulative_max = round(sum(maximum for _, maximum in valid_score_pairs), 2) if valid_score_pairs else None; cumulative_score_percentage = round(cumulative_score / cumulative_max * 100, 2) if cumulative_score is not None and cumulative_max else None
        report["first_term_average"], report["second_term_average"], report["third_term_average"] = pretty_optional(term_averages[0]), pretty_optional(term_averages[1]), pretty_optional(term_averages[2]); report["first_term_score"], report["second_term_score"], report["third_term_score"] = pretty_optional(term_scores[0]), pretty_optional(term_scores[1]), pretty_optional(term_scores[2]); report["first_term_max"], report["second_term_max"], report["third_term_max"] = term_maximums[0], term_maximums[1], term_maximums[2]; report["cumulative_score"], report["cumulative_max"], report["cumulative_score_percentage"] = pretty_optional(cumulative_score), pretty_optional(cumulative_max), pretty_optional(cumulative_score_percentage); report["cumulative_average"], report["cumulative_grade"] = pretty_optional(cumulative_average), cumulative_grade; report["cumulative_terms_available"], report["cumulative_complete"] = len(valid_averages), len(valid_averages) == 3
        report["cumulative_attendance"] = combine_attendance_summaries((first_report or {}).get("attendance"), (second_report or {}).get("attendance"), report.get("attendance")); report["cumulative_source_mode"] = mode
    cumulative_averages = [safe_float(report.get("cumulative_average")) for report in third_payload.get("reports", []) if report.get("cumulative_complete") and report.get("cumulative_average") is not None]
    class_average = round(sum(cumulative_averages) / len(cumulative_averages), 2) if cumulative_averages else None; class_highest = max(cumulative_averages) if cumulative_averages else None; class_lowest = min(cumulative_averages) if cumulative_averages else None
    for report in third_payload.get("reports", []):
        report["cumulative_class_average"], report["cumulative_highest_average"], report["cumulative_lowest_average"] = pretty_optional(class_average), pretty_optional(class_highest), pretty_optional(class_lowest); report["cumulative_no_in_class"] = len(cumulative_averages); report["cumulative_combined_stream"] = len(cumulative_averages)
        if not report.get("cumulative_complete") or report.get("cumulative_average") is None: report["cumulative_position"], report["cumulative_position_text"], report["cumulative_out_of"] = 0, "--", 0; continue
        position = compute_position(report.get("cumulative_average"), cumulative_averages); report["cumulative_position"], report["cumulative_position_text"], report["cumulative_out_of"] = position, ordinal(position), len(cumulative_averages)
    third_payload["cumulative"], third_payload["cumulative_terms"], third_payload["cumulative_source_mode"] = True, ["FIRST", "SECOND", "THIRD"], mode
    third_payload["cumulative_summary"] = {"class_average": pretty_optional(class_average), "highest_average": pretty_optional(class_highest), "lowest_average": pretty_optional(class_lowest), "complete_students": len(cumulative_averages), "mode": mode}


# ============================================================
# SAVED REPORT SNAPSHOTS
# ============================================================

def ensure_report_dir():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    return REPORT_DIR


def save_report_snapshots(reports, generated_by=""):
    ensure_report_dir()
    saved = []

    with REPORT_LOCK:
        with SNAPSHOT_FILE.open("a", encoding="utf-8") as file:
            for report in reports:
                snapshot = {
                    "snapshot_id": uuid.uuid4().hex, "generated_at": now_string(),
                    "generated_by": clean(generated_by) or clean(session.get("admin_username") or session.get("username") or session.get("user") or "Staff"),
                    "session": report.get("session"), "term": report.get("term"), "class_level": report.get("class_level"),
                    "class_arm": report.get("class_arm"), "admission_number": report.get("admission_number"),
                    "full_name": report.get("full_name"), "report": report,
                }

                file.write(json.dumps(snapshot, ensure_ascii=False) + "\n")
                saved.append(snapshot)

    return saved


def read_saved_report_snapshots():
    if not SNAPSHOT_FILE.exists(): return []

    rows = []

    with REPORT_LOCK:
        with SNAPSHOT_FILE.open("r", encoding="utf-8") as file:
            for line in file:
                try:
                    item = json.loads(line)
                    if isinstance(item, dict): rows.append(item)
                except Exception: continue

    return rows[::-1]


# ============================================================
# API — CONFIG / STUDENTS / SOURCE STATUS
# ============================================================

@report_sheet_bp.route("/api/report-sheets/config")
@report_staff_required
def api_report_config():
    academic_session, term = resolve_context(request.args.get("session"), request.args.get("term")); class_level, class_arm = request_class_values(); level, arm = normalize_report_class(class_level, class_arm); classes = list(STUDENT_DATABASE_CLASSES) + list(TAHFEEZ_CLASSES) + list(ISLAMIYAH_CLASSES); arms = {item: list(CLASS_ARMS_BY_LEVEL.get(item, [])) or [item] for item in classes}; rule = get_assessment_rule(level) if level else {}
    if report_role() == "teacher":
        scope = teacher_report_scope(report_teacher_id(), academic_session); classes = [item for item in classes if item in scope.get("class_levels", [])]; arms = {item: ([arm for arm in arms.get(item, []) if not scope.get("class_arms", {}).get(item) or arm in scope.get("class_arms", {}).get(item, [])]) for item in classes}
        if level and level not in classes: level, arm = "", ""
    elif report_role() == "teacher_admin":
        classes = [item for item in classes if school_section_for_class(item) not in {"TAHFEEZ", "ISLAMIYAH"}]; arms = {item:arms.get(item,[]) for item in classes}
        if level and level not in classes: level, arm = "", ""
    subjects = get_report_subjects_for_selection(level, arm) if level else []
    if report_role() == "teacher" and level:
        allowed = set(teacher_allowed_report_subjects(report_teacher_id(), academic_session, level, arm)); subjects = [subject for subject in subjects if academic_subject_key(subject) in allowed or clean_upper(subject) in allowed]
    access_scope = teacher_report_scope(report_teacher_id(), academic_session) if report_role() == "teacher" else {}
    return jsonify({"success": True, "session": academic_session, "term": term, "term_label": academic_term_label(term), "class_level": level, "class_arm": arm, "classes": classes, "class_labels": {item: class_label(item) for item in classes}, "class_sections": {item: school_section_for_class(item) for item in classes}, "class_arms": arms, "subjects": subjects, "assessment": rule, "grading": {"system": grading_system_for_class(level), "ready": grading_system_ready(grading_system_for_class(level))} if level else {}, "generation_enabled": assessment_entry_enabled(level) if level else False, "roster_source": report_roster_source(level) if level else "", "result_year": resolve_result_year(academic_session, request.args.get("year"), level, arm), "access": {"role": report_role(), "teacher_id": report_teacher_id() if report_role() == "teacher" else "", "restricted": report_role() == "teacher", "scope": access_scope}})


@report_sheet_bp.route("/api/report-sheets/students")
@report_staff_required
def api_report_students():
    class_level, class_arm = request_class_values()
    level, arm, error = resolve_class(class_level, class_arm, require_arm=True)

    if error: return jsonify({"success": False, "message": error, "students": []}), 400
    academic_session, term = resolve_context(request.args.get("session"), request.args.get("term")); next_term = clean(request.args.get("next_term")); next_term_error = None if report_role() == "teacher" else next_term_required_response(next_term)[1]
    if not academic_session or not term: return jsonify({"success": False, "message": "Academic session and term are required.", "students": []}), 400
    if next_term_error: return next_term_error
    denied = teacher_scope_denied(academic_session, level, arm)
    if denied: return denied
    if report_role() != "teacher": save_report_defaults(academic_session, term, level, arm, {"next_term": next_term})

    students = get_report_students_for_class(level, arm, active_only=True); rule = get_assessment_rule(level) or {}; subject_scope = teacher_filtered_subject_scope(get_report_subject_scope(level, arm), academic_session, level, arm)
    # Fast Manual Workstation bootstrap: return the saved class subject scope with the roster.
    # The browser can therefore show students + subject selection immediately without waiting
    # for the heavier CA/Exam source-status scan or a second subject-scope request.
    teacher_subject_keys = teacher_allowed_report_subjects(report_teacher_id(), academic_session, level, arm) if report_role() == "teacher" else []
    return jsonify({"success": True, "class_level": level, "class_arm": arm, "students": students, "count": len(students), "subjects": [item.get("name") for item in subject_scope.get("available_subjects", []) if item.get("name")], "manual_subject_scope": subject_scope, "manual_score_fields": manual_score_fields(level), "assessment": rule, "grading": {"system": grading_system_for_class(level), "ready": grading_system_ready(grading_system_for_class(level))}, "generation_enabled": assessment_entry_enabled(level), "roster_source": report_roster_source(level), "access": {"role": report_role(), "teacher_id": report_teacher_id() if report_role() == "teacher" else "", "restricted": report_role() == "teacher", "allowed_subject_keys": teacher_subject_keys}})


def build_manual_prefill_bootstrap(payload, class_level, class_arm):
    """Build the complete lightweight Manual Workstation cache during class loading.

    The expensive academic scan has already happened inside Source Status.  We therefore
    return automatic scores, the class subject scope and saved manual drafts in the same
    response.  Student switching can then be rendered entirely in the browser without a
    second Flask request, CSV read, subject-registry pass or workbook scan.
    """
    academic_session = normalize_academic_session(payload.get("session")) if isinstance(payload, dict) else ""; score_fields = manual_score_fields(class_level); prefill = {}; scope = teacher_filtered_subject_scope(get_report_subject_scope(class_level, class_arm), academic_session, class_level, class_arm); allowed = set(teacher_allowed_report_subjects(report_teacher_id(), academic_session, class_level, class_arm)) if report_role() == "teacher" else set()
    for report in payload.get("reports", []) if isinstance(payload, dict) else []:
        admission = normalize_admission_number(report.get("admission_number")); rows = {}
        if not admission: continue
        for row in report.get("subjects", []) if isinstance(report.get("subjects"), list) else []:
            subject_key = academic_subject_key(row.get("subject_key") or row.get("subject"))
            if not subject_key or clean_upper(subject_key) in {"ISLAMIYYAH", "ISLAMIYAH"} or (allowed and subject_key not in allowed): continue
            item = {"subject": row.get("subject"), "subject_key": subject_key}; components = row.get("components") if isinstance(row.get("components"), dict) else {}
            for field in score_fields:
                value = row.get(field)
                if value in (None, "") and field != "exam": value = components.get(field)
                if value not in (None, ""): item[field] = value
            if any(value not in (None, "") for key, value in item.items() if key not in {"subject", "subject_key"}): rows[subject_key] = item
        prefill[admission] = rows

    term = normalize_academic_term(payload.get("term")) if isinstance(payload, dict) else ""
    store = _read_json_store(MANUAL_FILE); records = {}
    for student in payload.get("students", []) if isinstance(payload, dict) else []:
        admission = normalize_admission_number(student.get("admission_number"))
        if not admission: continue
        record = store.get(manual_context_key(academic_session, term, class_level, class_arm, admission), {})
        records[admission] = teacher_visible_manual_record(record if isinstance(record, dict) else {}, academic_session, class_level, class_arm)

    return {
        "ready": True,
        "score_fields": score_fields,
        "subject_scope": scope,
        "available_subjects": list(scope.get("available_subjects") or []),
        "selected_subjects": list(scope.get("selected_subjects") or []),
        "automatic_scores_by_admission": prefill,
        "manual_records_by_admission": records,
        "class_readiness": role_manual_class_readiness(academic_session, term, class_level, class_arm),
    }


@report_sheet_bp.route("/api/report-sheets/source-status")
@report_staff_required
def api_report_source_status():
    class_level, class_arm = request_class_values()
    level, arm, error = resolve_class(class_level, class_arm, require_arm=True)

    if error: return jsonify({"success": False, "message": error}), 400

    academic_session, term = resolve_context(request.args.get("session"), request.args.get("term"))
    denied = teacher_scope_denied(academic_session, level, arm)
    if denied: return denied
    year = resolve_result_year(academic_session, request.args.get("year"), level, arm)

    payload = build_term_report_payload(academic_session, term, level, arm, year, include_cumulative=False)

    manual_bootstrap = build_manual_prefill_bootstrap(payload, level, arm) if payload.get("generation_enabled", True) else {"ready": True, "score_fields": {}, "subject_scope": get_report_subject_scope(level, arm), "available_subjects": [], "selected_subjects": [], "automatic_scores_by_admission": {}, "manual_records_by_admission": {}}
    return jsonify({"success": True, "result_year": payload.get("result_year") or year, "session": academic_session, "term": term, "class_level": level, "class_arm": arm, "students": payload.get("students", []), "source_status": payload.get("source_status", {}), "summary": payload.get("summary", {}), "blocked_students": payload.get("blocked_students", []), "readiness_warnings": payload.get("readiness_warnings", []), "ca_available_contexts": payload.get("ca_available_contexts", []), "assessment": payload.get("assessment", {}), "grading": {"system": grading_system_for_class(level), "ready": grading_system_ready(grading_system_for_class(level))}, "generation_enabled": payload.get("generation_enabled", True), "roster_source": payload.get("roster_source", report_roster_source(level)), "manual_bootstrap": manual_bootstrap})


@report_sheet_bp.route("/api/report-sheets/islamiyah-status")
@report_staff_required
def api_report_islamiyah_status():
    class_level, class_arm = request_class_values(); level, arm, error = resolve_class(class_level, class_arm, require_arm=True)
    if error: return jsonify({"success": False, "message": error, "students": []}), 400
    academic_session, term = resolve_context(request.args.get("session"), request.args.get("term")); denied = teacher_scope_denied(academic_session, level, arm)
    if denied: return denied
    if report_role() == "teacher": return jsonify({"success": True, "session": academic_session, "term": term, "class_level": level, "class_arm": arm, "students": [], "count": 0, "complete_students": 0, "pending_students": 0, "authoritative_source": "RESTRICTED", "editable_in_report_sheets": False})
    roster = get_report_students_for_class(level, arm, active_only=True); students = []
    for student in roster:
        admission = normalize_admission_number(student.get("admission_number")); row = get_report_islamiyah_row(admission, academic_session, term)
        if row is None: status = {"islamiyah_status": "pending", "complete": False, "islamiyah_class_label": "Awaiting Islamiyyah score", "islamiyah_subject_count": 1, "islamiyah_subjects_complete": 0, "ca": None, "exam": None, "total": None, "source": "ISLAMIYYAH_SCHOOL"}
        else: status = row
        students.append({"admission_number": student.get("admission_number"), "full_name": student.get("full_name"), "class_arm": arm, "status": status.get("islamiyah_status") or "pending", "complete": bool(status.get("complete")), "islamiyah_class_label": status.get("islamiyah_class_label"), "subject_count": status.get("islamiyah_subject_count", 1), "subjects_complete": status.get("islamiyah_subjects_complete", 0), "ca_average": status.get("ca_total") if status.get("ca_total") is not None else status.get("ca"), "exam_average": status.get("exam"), "total": status.get("total"), "pending_subjects": [item.get("subject") for item in (status.get("islamiyah_components") or []) if not item.get("complete")], "score_source": status.get("score_source") or ("regular_school" if status.get("source") == "ISLAMIYYAH_SCHOOL_REGULAR_DATABASE" else "academy"), "source_label": "Regular School DB" if status.get("source") == "ISLAMIYYAH_SCHOOL_REGULAR_DATABASE" else "Academy DB"})
    return jsonify({"success": True, "session": academic_session, "term": term, "class_level": level, "class_arm": arm, "students": students, "count": len(students), "complete_students": sum(1 for row in students if row.get("complete")), "pending_students": sum(1 for row in students if not row.get("complete")), "authoritative_source": "ISLAMIYYAH_SCHOOL", "editable_in_report_sheets": False})


# ============================================================
# API — PREVIEW / GENERATE
# ============================================================

@report_sheet_bp.route("/api/report-sheets/preview", methods=["POST"])
@report_staff_required
def api_report_preview():
    denied = official_generation_denied()
    if denied: return denied
    data = request.get_json(silent=True) or {}
    class_level, class_arm = request_class_values(data)
    level, arm, error = resolve_class(class_level, class_arm, require_arm=True)

    if error: return jsonify({"success": False, "message": error}), 400

    academic_session, term = resolve_context(data.get("session"), data.get("term"))

    if not academic_session or not term:
        return jsonify({"success": False, "message": "Academic session and term are required."}), 400
    next_term, next_term_error = next_term_required_response(data.get("next_term"))
    if next_term_error: return next_term_error
    save_report_defaults(academic_session, term, level, arm, {**({"form_teacher": data.get("form_teacher")} if "form_teacher" in data else {}), "next_term": next_term})
    rule = get_assessment_rule(level) or {}
    if not assessment_entry_enabled(level):
        return jsonify({"success": False, "status": "assessment_scheme_pending", "message": rule.get("message") or f"The assessment scheme for {class_label(level)} is not configured yet.", "assessment": rule, "class_level": level, "class_arm": arm, "roster_source": report_roster_source(level)}), 409

    payload = build_term_report_payload(
        academic_session, term, level, arm, data.get("year"), data.get("admission_number") or data.get("admission"),
        include_cumulative=True, admission_numbers=data.get("admission_numbers") or data.get("admissions")
    )
    payload = apply_requested_next_term(payload, next_term)

    return jsonify(payload)


@report_sheet_bp.route("/api/report-sheets/generate", methods=["POST"])
@report_staff_required
def api_report_generate():
    denied = official_generation_denied()
    if denied: return denied
    data = request.get_json(silent=True) or {}
    class_level, class_arm = request_class_values(data)
    level, arm, error = resolve_class(class_level, class_arm, require_arm=True)

    if error: return jsonify({"success": False, "message": error}), 400

    academic_session, term = resolve_context(data.get("session"), data.get("term"))

    if not academic_session or not term:
        return jsonify({"success": False, "message": "Academic session and term are required."}), 400
    next_term, next_term_error = next_term_required_response(data.get("next_term"))
    if next_term_error: return next_term_error
    save_report_defaults(academic_session, term, level, arm, {**({"form_teacher": data.get("form_teacher")} if "form_teacher" in data else {}), "next_term": next_term})
    rule = get_assessment_rule(level) or {}
    if not assessment_entry_enabled(level):
        return jsonify({"success": False, "status": "assessment_scheme_pending", "message": rule.get("message") or f"The assessment scheme for {class_label(level)} is not configured yet.", "assessment": rule, "class_level": level, "class_arm": arm, "roster_source": report_roster_source(level)}), 409

    payload = build_term_report_payload(
        academic_session, term, level, arm, data.get("year"), data.get("admission_number") or data.get("admission"),
        include_cumulative=True, admission_numbers=data.get("admission_numbers") or data.get("admissions")
    )
    payload = apply_requested_next_term(payload, next_term)

    if not payload.get("reports"):
        payload["message"] = "No active student report sheets could be generated for this class selection."
        return jsonify(payload), 400

    if data.get("save_snapshot", True):
        snapshots = save_report_snapshots(payload["reports"]); snapshot_map = {normalize_admission_number(item.get("admission_number")): item.get("snapshot_id") for item in snapshots}
        for report in payload["reports"]: report["snapshot_id"] = snapshot_map.get(normalize_admission_number(report.get("admission_number")), "")
        payload["saved_snapshots"] = [{"snapshot_id": item["snapshot_id"], "admission_number": item["admission_number"], "full_name": item.get("full_name", ""), "generated_at": item.get("generated_at", ""), "transcript_archived": bool(item.get("transcript_archived"))} for item in snapshots]

    complete = sum(1 for report in payload.get("reports", []) if report.get("academic_complete")); partial = len(payload.get("reports", [])) - complete
    payload["message"] = f"{len(payload['reports'])} report sheet(s) generated successfully — {complete} complete, {partial} awaiting one or more academic sources."
    return jsonify(payload)


# ============================================================
# API — SAVED REPORTS
# ============================================================

@report_sheet_bp.route("/api/report-sheets/saved")
@report_staff_required
def api_saved_reports():
    denied = official_generation_denied()
    if denied: return denied
    academic_session = normalize_academic_session(request.args.get("session"))
    term = normalize_academic_term(request.args.get("term"))
    class_level, class_arm = request_class_values()
    level, arm = normalize_report_class(class_level, class_arm)

    rows = read_saved_report_snapshots()

    if academic_session: rows = [row for row in rows if normalize_academic_session(row.get("session")) == academic_session]
    if term: rows = [row for row in rows if normalize_academic_term(row.get("term")) == term]
    if level: rows = [row for row in rows if normalize_report_class(row.get("class_level"), row.get("class_arm"))[0] == level]
    if class_arm and arm: rows = [row for row in rows if normalize_report_class(row.get("class_level"), row.get("class_arm"))[1] == arm]

    return jsonify({"success": True, "reports": rows, "count": len(rows)})


@report_sheet_bp.route("/api/report-sheets/delete-saved", methods=["POST", "DELETE"])
@report_staff_required
def api_delete_saved_report():
    denied = official_generation_denied()
    if denied: return denied
    data = request.get_json(silent=True) or {}
    snapshot_ids = data.get("snapshot_ids") or ([data.get("snapshot_id")] if data.get("snapshot_id") else [])
    admissions = data.get("admission_numbers") or data.get("admissions") or []
    if isinstance(snapshot_ids, str): snapshot_ids = [item.strip() for item in snapshot_ids.replace(";", ",").split(",") if item.strip()]
    if isinstance(admissions, str): admissions = [item.strip() for item in admissions.replace(";", ",").split(",") if item.strip()]
    snapshot_ids = {clean(value) for value in snapshot_ids if clean(value)}; admissions = {normalize_admission_number(value) for value in admissions if normalize_admission_number(value)}
    delete_all = str(data.get("delete_all") or "").strip().lower() in {"1", "true", "yes", "on"}
    academic_session, term = normalize_academic_session(data.get("session")), normalize_academic_term(data.get("term")); class_level, class_arm = request_class_values(data); level, arm = normalize_report_class(class_level, class_arm)

    if not snapshot_ids and not admissions and not delete_all: return jsonify({"success": False, "message": "Provide a snapshot ID, selected report IDs, selected admission numbers, or delete_all=true."}), 400
    if (admissions or delete_all) and not (academic_session and term and level and arm): return jsonify({"success": False, "message": "Session, term, class level and class arm are required for selected/context report deletion."}), 400

    rows = read_saved_report_snapshots()[::-1]
    def same_context(row):
        row_level, row_arm = normalize_report_class(row.get("class_level"), row.get("class_arm"))
        return normalize_academic_session(row.get("session")) == academic_session and normalize_academic_term(row.get("term")) == term and row_level == level and row_arm == arm
    def should_delete(row):
        if snapshot_ids and clean(row.get("snapshot_id")) in snapshot_ids: return True
        if delete_all and same_context(row): return True
        if admissions and same_context(row) and normalize_admission_number(row.get("admission_number")) in admissions: return True
        return False

    deleted = [row for row in rows if should_delete(row)]; remaining = [row for row in rows if not should_delete(row)]
    if not deleted: return jsonify({"success": False, "message": "No matching saved report snapshots were found.", "deleted_count": 0}), 404

    ensure_report_dir()
    with REPORT_LOCK:
        with SNAPSHOT_FILE.open("w", encoding="utf-8") as file:
            for row in remaining: file.write(json.dumps(row, ensure_ascii=False) + "\n")

    for row in deleted:
        snapshot_id = clean(row.get("snapshot_id"))
        if snapshot_id: queue_emis_event_safely("report_sheets", "snapshot_delete", {"snapshot_id": snapshot_id}, entity_key=f"snapshot|{snapshot_id}")
    return jsonify({"success": True, "message": f"{len(deleted)} saved report snapshot(s) deleted successfully.", "deleted_count": len(deleted), "deleted_snapshot_ids": [row.get("snapshot_id") for row in deleted], "deleted_admission_numbers": [row.get("admission_number") for row in deleted]})


# ============================================================
# PERSISTENT REPORT DETAILS / DEFAULTS
# ============================================================

def report_context_key(academic_session, term, class_level, class_arm, admission_number=""):
    parts = [normalize_academic_session(academic_session), normalize_academic_term(term), clean_upper(class_level), clean_upper(class_arm), normalize_admission_number(admission_number)]
    return "|".join(parts)


# ============================================================
# FAST JSON STORE CACHE — signature-aware and safe for mutable callers
# ============================================================

_JSON_STORE_CACHE = {}

def _read_json_store(path):
    ensure_report_dir(); key = str(path.resolve())
    if not path.exists(): return {}
    with REPORT_LOCK:
        try:
            stat = path.stat(); signature = (stat.st_mtime_ns, stat.st_size); cached = _JSON_STORE_CACHE.get(key)
            if cached and cached.get("signature") == signature: return copy.deepcopy(cached.get("data") or {})
            data = json.loads(path.read_text(encoding="utf-8")); data = data if isinstance(data, dict) else {}; _JSON_STORE_CACHE[key] = {"signature": signature, "data": data}; return copy.deepcopy(data)
        except Exception: return {}

def _write_json_store(path, data):
    ensure_report_dir(); temp = path.with_suffix(path.suffix + ".tmp"); key = str(path.resolve())
    with REPORT_LOCK:
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"); temp.replace(path); _JSON_STORE_CACHE.pop(key, None)
    return path


def safe_rating(value, allow_blank=True):
    if value in (None, ""): return "" if allow_blank else 4
    try: return max(1, min(6, int(float(value))))
    except (TypeError, ValueError): return "" if allow_blank else 4


def normalize_trait_map(values, keys):
    values = values if isinstance(values, dict) else {}
    return {key: safe_rating(values.get(key), allow_blank=True) for key in keys}


def normalize_report_details(data, existing=None):
    data, existing = data if isinstance(data, dict) else {}, existing if isinstance(existing, dict) else {}
    affective_keys = ["punctuality", "attendance", "reliability", "neatness", "politeness", "honesty", "relationship", "self_control", "attentiveness", "perseverance"]
    psychomotor_keys = ["handwriting", "games", "sport", "drawing", "crafts", "musical_skills"]
    affective_source = data.get("affective") if isinstance(data.get("affective"), dict) else existing.get("affective", {})
    psychomotor_source = data.get("psychomotor") if isinstance(data.get("psychomotor"), dict) else existing.get("psychomotor", {})
    return {
        "form_teacher": clean(data.get("form_teacher", existing.get("form_teacher", ""))), "teacher_remark": clean(data.get("teacher_remark", existing.get("teacher_remark", ""))),
        "principal_remark": clean(data.get("principal_remark", existing.get("principal_remark", ""))), "next_term": clean(data.get("next_term", existing.get("next_term", ""))),
        "promotion_status": clean(data.get("promotion_status", existing.get("promotion_status", "PENDING"))).upper() or "PENDING", "promotion_note": clean(data.get("promotion_note", existing.get("promotion_note", ""))),
        "affective": normalize_trait_map(affective_source, affective_keys), "psychomotor": normalize_trait_map(psychomotor_source, psychomotor_keys),
        "updated_at": now_string(), "updated_by": clean(session.get("admin_username") or session.get("username") or session.get("user") or existing.get("updated_by") or "Staff"),
    }


def get_report_details(academic_session, term, class_level, class_arm, admission_number):
    key = report_context_key(academic_session, term, class_level, class_arm, admission_number)
    return _read_json_store(DETAILS_FILE).get(key, {})


def save_report_details(academic_session, term, class_level, class_arm, admission_number, data):
    store = _read_json_store(DETAILS_FILE); key = report_context_key(academic_session, term, class_level, class_arm, admission_number)
    store[key] = normalize_report_details(data, store.get(key, {})); _write_json_store(DETAILS_FILE, store)
    queue_emis_event_safely("report_sheets", "details_upsert", {"key": key, "item": store[key]}, entity_key=f"details|{key}")
    return store[key]


def get_report_defaults(academic_session, term, class_level, class_arm):
    key = report_context_key(academic_session, term, class_level, class_arm)
    return _read_json_store(DEFAULTS_FILE).get(key, {})


def save_report_defaults(academic_session, term, class_level, class_arm, data):
    store = _read_json_store(DEFAULTS_FILE); key = report_context_key(academic_session, term, class_level, class_arm)
    current = store.get(key, {}) if isinstance(store.get(key), dict) else {}; incoming_next_term = normalize_next_term_date(data.get("next_term", current.get("next_term", "")))
    item = {"form_teacher": clean(data.get("form_teacher", current.get("form_teacher", ""))), "next_term": incoming_next_term, "updated_at": now_string(), "updated_by": clean(session.get("admin_username") or session.get("username") or session.get("user") or current.get("updated_by") or "Staff")}
    store[key] = item; _write_json_store(DEFAULTS_FILE, store); queue_emis_event_safely("report_sheets", "defaults_upsert", {"key": key, "item": item}, entity_key=f"defaults|{key}")
    if incoming_next_term:
        details_store = _read_json_store(DETAILS_FILE); changed = []
        for detail_key, detail in details_store.items():
            if detail_key.startswith(key) and detail_key != key and isinstance(detail, dict) and clean(detail.get("next_term")) != incoming_next_term: detail["next_term"] = incoming_next_term; detail["updated_at"] = item["updated_at"]; detail["updated_by"] = item["updated_by"]; changed.append((detail_key, detail))
        if changed:
            _write_json_store(DETAILS_FILE, details_store)
            for detail_key, detail in changed: queue_emis_event_safely("report_sheets", "details_upsert", {"key": detail_key, "item": detail}, entity_key=f"details|{detail_key}")
    return item


def apply_saved_report_details(payload):
    if not isinstance(payload, dict): return payload
    session_value, term, level, arm = payload.get("session", ""), payload.get("term", ""), payload.get("class_level", ""), payload.get("class_arm", "")
    defaults, details_store = get_report_defaults(session_value, term, level, arm), _read_json_store(DETAILS_FILE); reports = payload.get("reports", []) if isinstance(payload.get("reports"), list) else []
    class_average = optional_float((payload.get("summary") or {}).get("class_average"))
    for report in reports:
        admission = report.get("admission_number"); details = details_store.get(report_context_key(session_value, term, level, arm, admission), {}); average = optional_float(report.get("average")); attendance = report.get("attendance") if isinstance(report.get("attendance"), dict) else {}
        report["form_teacher"] = clean(details.get("form_teacher") or defaults.get("form_teacher")); report["next_term"] = clean(defaults.get("next_term") or details.get("next_term"))
        report["teacher_remark"] = clean(details.get("teacher_remark") or report.get("teacher_remark") or (teacher_remark(average) if average is not None else "")); report["principal_remark"] = clean(details.get("principal_remark") or report.get("principal_remark") or (principal_remark(average) if average is not None else ""))
        report["promotion_status"] = clean(details.get("promotion_status") or report.get("promotion_status") or "PENDING").upper(); report["promotion_note"] = clean(details.get("promotion_note") or report.get("promotion_note"))
        report["affective"] = details.get("affective") if isinstance(details.get("affective"), dict) else {}; report["psychomotor"] = details.get("psychomotor") if isinstance(details.get("psychomotor"), dict) else {}
        subjects = report.get("subjects", []) if isinstance(report.get("subjects"), list) else []; scored = [row for row in subjects if row.get("total") is not None]; strongest = max(scored, key=lambda row: safe_float(row.get("total")), default=None); focus = min(scored, key=lambda row: safe_float(row.get("total")), default=None)
        report["performance_insights"] = {"strongest_subject": strongest.get("subject") if strongest else "", "strongest_score": pretty_optional(strongest.get("total")) if strongest else None, "focus_subject": focus.get("subject") if focus else "", "focus_score": pretty_optional(focus.get("total")) if focus else None, "class_average": pretty_optional(class_average), "average_difference": pretty_optional(average - class_average) if average is not None and class_average is not None else None, "subjects_assessed": len([row for row in subjects if row.get("has_ca") or row.get("has_exam")]), "subjects_complete": len(scored), "attendance_percentage": pretty_number(attendance.get("attendance_percentage", 0)) if attendance else None, "passes": sum(1 for row in scored if safe_float(row.get("total")) >= 40), "fails": sum(1 for row in scored if safe_float(row.get("total")) < 40)}
    return payload


_BASE_BUILD_TERM_REPORT_PAYLOAD = build_term_report_payload


def normalize_admission_selection(values):
    if values in (None, ""): return []
    if isinstance(values, str): values = [item.strip() for item in values.replace(";", ",").split(",") if item.strip()]
    if not isinstance(values, (list, tuple, set)): values = [values]
    output, seen = [], set()
    for value in values:
        admission = normalize_admission_number(value)
        if admission and admission not in seen: seen.add(admission); output.append(admission)
    return output


def build_term_report_payload(academic_session, term, class_level, class_arm, result_year="", admission_number="", include_cumulative=True, admission_numbers=None):
    # Always calculate the complete class first so selected-student reports keep true class positions, OUT OF, LOW, HIGH and CLASS AVE.
    payload = _BASE_BUILD_TERM_REPORT_PAYLOAD(academic_session, term, class_level, class_arm, result_year, "", include_cumulative)
    payload = apply_saved_report_details(payload)
    requested = normalize_admission_selection(admission_numbers)
    single = normalize_admission_number(admission_number)
    if single and single not in requested: requested.insert(0, single)
    if requested:
        wanted = set(requested)
        payload["reports"] = [report for report in payload.get("reports", []) if normalize_admission_number(report.get("admission_number")) in wanted]
        payload["students"] = [student for student in payload.get("students", []) if normalize_admission_number(student.get("admission_number")) in wanted]
        payload["blocked_students"] = [student for student in payload.get("blocked_students", []) if normalize_admission_number(student.get("admission_number")) in wanted]
        payload["readiness_warnings"] = [student for student in payload.get("readiness_warnings", []) if normalize_admission_number(student.get("admission_number")) in wanted]
        payload["summary"] = dict(payload.get("summary") or {}); payload["summary"]["generated"] = len(payload["reports"]); payload["summary"]["blocked"] = len(payload["blocked_students"]); payload["summary"]["selected_requested"] = len(requested); payload["success"] = bool(payload["reports"])
    return payload


# ============================================================
# API — REPORT DETAILS / CLASS DEFAULTS
# ============================================================

@report_sheet_bp.route("/api/report-sheets/details", methods=["GET", "POST"])
@report_staff_required
def api_report_details():
    denied = official_generation_denied()
    if denied: return denied
    source = request.get_json(silent=True) or {} if request.method == "POST" else request.args
    class_level, class_arm = request_class_values(source); level, arm, error = resolve_class(class_level, class_arm, require_arm=True)
    if error: return jsonify({"success": False, "message": error}), 400
    academic_session, term = resolve_context(source.get("session"), source.get("term")); admission = normalize_admission_number(source.get("admission_number") or source.get("admission"))
    if not academic_session or not term or not admission: return jsonify({"success": False, "message": "Session, term and admission number are required."}), 400
    student = get_student(admission, active_only=False)
    if not student: return jsonify({"success": False, "message": "Student was not found."}), 404
    if request.method == "GET": return jsonify({"success": True, "details": get_report_details(academic_session, term, level, arm, admission)})
    details = save_report_details(academic_session, term, level, arm, admission, source)
    return jsonify({"success": True, "message": "Report remarks and ratings saved successfully.", "details": details})


@report_sheet_bp.route("/api/report-sheets/defaults", methods=["GET", "POST"])
@report_staff_required
def api_report_defaults():
    source = request.get_json(silent=True) or {} if request.method == "POST" else request.args
    class_level, class_arm = request_class_values(source); level, arm, error = resolve_class(class_level, class_arm, require_arm=True)
    if error: return jsonify({"success": False, "message": error}), 400
    academic_session, term = resolve_context(source.get("session"), source.get("term"))
    if not academic_session or not term: return jsonify({"success": False, "message": "Session and term are required."}), 400
    if request.method == "GET": return jsonify({"success": True, "defaults": get_report_defaults(academic_session, term, level, arm)})
    denied = official_generation_denied()
    if denied: return denied
    next_term, next_term_error = next_term_required_response(source.get("next_term"))
    if next_term_error: return next_term_error
    defaults = save_report_defaults(academic_session, term, level, arm, {**source, "next_term": next_term})
    return jsonify({"success": True, "message": "Report defaults saved successfully.", "defaults": defaults})


# ============================================================
# REPORT EXPORT HELPERS
# ============================================================

def export_report_rows(payload):
    rows = []
    for report in payload.get("reports", []):
        for subject in report.get("subjects", []):
            rows.append({
                "Admission Number": report.get("admission_number"), "Student Name": report.get("full_name"), "Class": report.get("class_arm"), "Session": report.get("session"), "Term": report.get("term_label") or report.get("term"),
                "Subject": subject.get("subject"), "CA Total": subject.get("ca_total"), "Exam": subject.get("exam"), "Total": subject.get("total"), "Grade": subject.get("grade"), "Position": subject.get("position_text"), "Out Of": subject.get("out_of"),
                "Lowest": subject.get("lowest"), "Highest": subject.get("highest"), "Class Average": subject.get("class_average"), "Comment": subject.get("comment"), "Student Average": report.get("average"), "Final Grade": report.get("grade"), "Overall Position": report.get("position_text"),
            })
    return rows


def export_payload_from_request():
    class_level, class_arm = request_class_values(); level, arm, error = resolve_class(class_level, class_arm, require_arm=True)
    if error: return None, error
    academic_session, term = resolve_context(request.args.get("session"), request.args.get("term")); year = resolve_result_year(academic_session, request.args.get("year"), level, arm)
    if not academic_session or not term: return None, "Academic session and term are required."
    admissions = request.args.get("admission_numbers") or request.args.get("admissions") or ""
    return build_term_report_payload(academic_session, term, level, arm, year, include_cumulative=True, admission_numbers=admissions), ""


@report_sheet_bp.route("/api/report-sheets/export/csv")
@report_staff_required
def api_report_export_csv():
    denied = official_generation_denied()
    if denied: return denied
    payload, error = export_payload_from_request()
    if error: return jsonify({"success": False, "message": error}), 400
    rows = export_report_rows(payload); output = io.StringIO(newline="")
    headers = list(rows[0].keys()) if rows else ["Admission Number", "Student Name", "Class", "Session", "Term", "Subject", "CA Total", "Exam", "Total", "Grade", "Position", "Out Of", "Lowest", "Highest", "Class Average", "Comment", "Student Average", "Final Grade", "Overall Position"]
    writer = csv.DictWriter(output, fieldnames=headers); writer.writeheader(); writer.writerows(rows)
    filename = f"report_sheets_{clean(payload.get('class_arm')).replace('/', '-')}_{clean(payload.get('term')).lower()}.csv"
    return Response("\ufeff" + output.getvalue(), mimetype="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@report_sheet_bp.route("/api/report-sheets/export/excel")
@report_staff_required
def api_report_export_excel():
    denied = official_generation_denied()
    if denied: return denied
    payload, error = export_payload_from_request()
    if error: return jsonify({"success": False, "message": error}), 400
    rows = export_report_rows(payload); workbook = Workbook(); sheet = workbook.active; sheet.title = "Report Sheets"
    headers = list(rows[0].keys()) if rows else ["Admission Number", "Student Name", "Class", "Session", "Term", "Subject", "CA Total", "Exam", "Total", "Grade", "Position", "Out Of", "Lowest", "Highest", "Class Average", "Comment", "Student Average", "Final Grade", "Overall Position"]
    sheet.append(headers)
    for row in rows: sheet.append([row.get(header, "") for header in headers])
    for cell in sheet[1]: cell.font = cell.font.copy(bold=True)
    for column in sheet.columns:
        letter = column[0].column_letter; width = min(34, max(11, max(len(str(cell.value or "")) for cell in column) + 2)); sheet.column_dimensions[letter].width = width
    stream = io.BytesIO(); workbook.save(stream); stream.seek(0)
    filename = f"report_sheets_{clean(payload.get('class_arm')).replace('/', '-')}_{clean(payload.get('term')).lower()}.xlsx"
    return send_file(stream, as_attachment=True, download_name=filename, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ============================================================
# API — REPORT USAGE AUDIT
# ============================================================

@report_sheet_bp.route("/api/report-sheets/mark-used", methods=["POST"])
@report_staff_required
def api_report_mark_used():
    denied = official_generation_denied()
    if denied: return denied
    data = request.get_json(silent=True) or {}; class_level, class_arm = request_class_values(data); level, arm, error = resolve_class(class_level, class_arm, require_arm=True)
    if error: return jsonify({"success": False, "message": error}), 400
    academic_session, term = resolve_context(data.get("session"), data.get("term")); admissions = data.get("admission_numbers") or data.get("admissions") or []
    if isinstance(admissions, str): admissions = [admissions]
    admissions = [normalize_admission_number(value) for value in admissions if normalize_admission_number(value)]
    if not admissions: return jsonify({"success": False, "message": "Select at least one generated student report first."}), 400
    ensure_report_dir(); record = {"audit_id": uuid.uuid4().hex, "marked_at": now_string(), "marked_by": clean(session.get("admin_username") or session.get("username") or session.get("user") or "Staff"), "session": academic_session, "term": term, "class_level": level, "class_arm": arm, "admission_numbers": admissions}
    with REPORT_LOCK:
        with USAGE_FILE.open("a", encoding="utf-8") as file: file.write(json.dumps(record, ensure_ascii=False) + "\n")
    queue_emis_event_safely("report_sheets", "usage_append", {"record": record}, entity_key=f"usage|{record['audit_id']}")
    return jsonify({"success": True, "message": f"{len(admissions)} report result set(s) marked as used in the report audit.", "count": len(admissions)})


# ============================================================
# HYBRID / MANUAL REPORT SYSTEM — STORAGE + FILE NAMING
# ============================================================

MANUAL_FILE = REPORT_DIR / "manual_report_records.json"
REPORT_SUBJECT_SCOPE_FILE = REPORT_DIR / "report_subject_scopes.json"


def report_subject_scope_key(class_level, class_arm):
    level, arm = normalize_report_class(class_level, class_arm)
    return f"{level}|{arm}"


def get_report_subject_scope(class_level, class_arm):
    """Return the Report Sheets-only subject scope for a class/arm.

    This intentionally does not deactivate subjects in the global curriculum. Teachers can
    produce a focused report (for example four subjects) without deleting historical CA/Exam
    data or changing other academic modules. New subjects are added to the class registry, while
    inclusion/exclusion is kept here as a report-sheet preference.
    """
    level, arm = normalize_report_class(class_level, class_arm)
    available = []
    for subject in get_report_subjects_for_selection(level, arm):
        key = academic_subject_key(subject)
        if not key or clean_upper(key) in {"ISLAMIYYAH", "ISLAMIYAH"}: continue
        if not any(item["key"] == key for item in available): available.append({"key": key, "name": normalize_academic_subject(subject)})
    store = _read_json_store(REPORT_SUBJECT_SCOPE_FILE); saved = store.get(report_subject_scope_key(level, arm), {}) if isinstance(store, dict) else {}
    saved_keys = saved.get("subject_keys") if isinstance(saved, dict) and isinstance(saved.get("subject_keys"), list) else None
    available_keys = [item["key"] for item in available]
    selected = [key for key in (saved_keys if saved_keys is not None else available_keys) if key in available_keys]
    include_islamiyah = bool(saved.get("include_islamiyah", True)) if isinstance(saved, dict) else True
    return {"class_level": level, "class_arm": arm, "available_subjects": available, "selected_keys": selected, "selected_subjects": [item["name"] for item in available if item["key"] in selected], "include_islamiyah": include_islamiyah, "customized": saved_keys is not None, "updated_at": clean(saved.get("updated_at")) if isinstance(saved, dict) else "", "updated_by": clean(saved.get("updated_by")) if isinstance(saved, dict) else ""}


def save_report_subject_scope(class_level, class_arm, subject_keys, include_islamiyah=True):
    scope = get_report_subject_scope(class_level, class_arm); available = {item["key"]: item["name"] for item in scope["available_subjects"]}
    requested = []
    for value in subject_keys if isinstance(subject_keys, list) else []:
        key = academic_subject_key(value)
        if key in available and key not in requested: requested.append(key)
    if not requested and not include_islamiyah: raise ValueError("Select at least one report subject, or keep the synced Islamiyyah result enabled.")
    item = {"class_level": scope["class_level"], "class_arm": scope["class_arm"], "subject_keys": requested, "include_islamiyah": bool(include_islamiyah), "updated_at": now_string(), "updated_by": clean(session.get("admin_username") or session.get("username") or session.get("user") or "Staff")}
    store = _read_json_store(REPORT_SUBJECT_SCOPE_FILE); store[report_subject_scope_key(scope["class_level"], scope["class_arm"])] = item; _write_json_store(REPORT_SUBJECT_SCOPE_FILE, store)
    queue_emis_event_safely("report_sheets", "subject_scope_upsert", {"key": report_subject_scope_key(scope["class_level"], scope["class_arm"]), "item": item}, entity_key=f"report-subject-scope|{report_subject_scope_key(scope['class_level'], scope['class_arm'])}")
    return get_report_subject_scope(scope["class_level"], scope["class_arm"])


def apply_report_subject_scope(payload, class_level="", class_arm="", preloaded_scope=None):
    """Filter generated report rows to the class Report Sheets scope and recalculate totals/statistics."""
    if not isinstance(payload, dict): return payload
    level = payload.get("class_level") or class_level; arm = payload.get("class_arm") or class_arm; scope = preloaded_scope if isinstance(preloaded_scope, dict) else get_report_subject_scope(level, arm); allowed = set(scope.get("selected_keys") or []); include_islamiyah = bool(scope.get("include_islamiyah", True)); reports = payload.get("reports") if isinstance(payload.get("reports"), list) else []
    for report in reports:
        rows = []
        for row in report.get("subjects", []) if isinstance(report.get("subjects"), list) else []:
            key = academic_subject_key(row.get("subject_key") or row.get("subject")); is_islamiyah = clean_upper(key) in {"ISLAMIYYAH", "ISLAMIYAH"}
            if (is_islamiyah and include_islamiyah) or (not is_islamiyah and key in allowed): rows.append(row)
        report["subjects"] = rows; report["subject_count"] = len(rows); report["missing_ca_subjects"] = [key for key in (report.get("missing_ca_subjects") or []) if (clean_upper(key) in {"ISLAMIYYAH", "ISLAMIYAH"} and include_islamiyah) or academic_subject_key(key) in allowed]; report["missing_exam_subjects"] = [key for key in (report.get("missing_exam_subjects") or []) if (clean_upper(key) in {"ISLAMIYYAH", "ISLAMIYAH"} and include_islamiyah) or academic_subject_key(key) in allowed]; report["has_ca"] = any(bool(row.get("has_ca") or row.get("ca_complete")) for row in rows); report["has_exam"] = any(bool(row.get("has_exam") or row.get("exam_complete")) for row in rows); report["report_subject_scope"] = scope
    stats = finalize_report_statistics(reports); catalog = {academic_subject_key(row.get("subject_key") or row.get("subject")) for report in reports for row in report.get("subjects", []) if academic_subject_key(row.get("subject_key") or row.get("subject"))}; summary = dict(payload.get("summary") or {}); summary.update(stats); summary.update({"subjects": len(catalog), "generated": len(reports), "complete_reports": sum(1 for report in reports if report.get("academic_complete")), "partial_reports": sum(1 for report in reports if not report.get("academic_complete")), "report_subject_scope_count": len(scope.get("selected_keys") or []) + (1 if include_islamiyah else 0)}); payload["summary"] = summary; payload["subject_scope"] = scope
    for report in reports:
        average = optional_float(report.get("average")); report["teacher_remark"] = teacher_remark(average) if average is not None else ""; report["principal_remark"] = principal_remark(average) if average is not None else ""
    return payload


def safe_result_token(value):
    value = clean(value).replace("/", "-").replace("\\", "-")
    return "".join(ch for ch in value if ch.isalnum() or ch in {"-", "_"}).strip("_-")


def result_file_stem(report):
    report = report if isinstance(report, dict) else {}
    first_name = clean(report.get("first_name")) or (clean(report.get("full_name")).split()[0] if clean(report.get("full_name")) else "Student")
    level = clean_upper(report.get("class_level")) or normalize_academic_class(report.get("class_arm"), report.get("class_arm"))[0] or "CLASS"
    admission = clean(report.get("admission_number")) or "student"
    return f"{safe_result_token(first_name) or 'Student'}_{safe_result_token(level)}{safe_result_token(admission)}"


def save_report_snapshots(reports, generated_by=""):
    """Save snapshots immediately, batch-archive History, then queue cloud sync off the request path.

    The local report and Academic History remain durable before this function returns.  Only the
    retry/sync queue work is deferred, preventing class generation from waiting on dozens of small
    SQLite queue transactions.
    """
    ensure_report_dir(); saved = []
    with REPORT_LOCK:
        with SNAPSHOT_FILE.open("a", encoding="utf-8") as file:
            for report in reports:
                snapshot = {
                    "snapshot_id": uuid.uuid4().hex, "generated_at": now_string(),
                    "generated_by": clean(generated_by) or clean(session.get("admin_username") or session.get("username") or session.get("user") or "Staff"),
                    "session": report.get("session"), "term": report.get("term"), "class_level": report.get("class_level"), "class_arm": report.get("class_arm"),
                    "admission_number": report.get("admission_number"), "full_name": report.get("full_name"), "result_name": result_file_stem(report),
                    "source_mode": clean(report.get("source_mode") or "auto"), "report": report,
                }
                file.write(json.dumps(snapshot, ensure_ascii=False) + "\n"); saved.append(snapshot)
    archive_results = []
    try:
        from modules.academic_history import archive_report_snapshots
        archive_results = archive_report_snapshots(saved, queue_sync=False)
        archived_ids = {clean((item.get("record") or {}).get("snapshot_id")) for item in archive_results if isinstance(item, dict) and item.get("record")}
        for snapshot in saved: snapshot["transcript_archived"] = clean(snapshot.get("snapshot_id")) in archived_ids
    except Exception as error:
        print("[EMIS ACADEMIC HISTORY] Snapshot archive warning:", error)
        for snapshot in saved: snapshot["transcript_archived"] = False

    # Queue remote/retry sync after the HTTP response-critical disk work is complete.  This does not
    # postpone the local snapshot/history save; it only moves sync bookkeeping out of the UI wait.
    sync_snapshots = [dict(item) for item in saved]; sync_records = [dict(item.get("record") or {}) for item in archive_results if isinstance(item, dict) and item.get("record") and (item.get("created") or item.get("updated"))]
    def _queue_saved_report_sync():
        for snapshot in sync_snapshots: queue_emis_event_safely("report_sheets", "snapshot_upsert", {"snapshot": snapshot}, entity_key=f"snapshot|{clean(snapshot.get('snapshot_id'))}")
        for record in sync_records: queue_emis_event_safely("academic_history", "record_upsert", {"record": record}, entity_key=f"history|{clean(record.get('record_id'))}")
    try: Thread(target=_queue_saved_report_sync, name="emis-report-archive-sync", daemon=True).start()
    except Exception as error: print("[EMIS SYNC] Could not start report archive sync worker:", error)
    return saved


# ============================================================
# HYBRID / MANUAL REPORT SYSTEM — RECORD HELPERS
# ============================================================


def manual_score_fields(class_level):
    rule = get_assessment_rule(class_level) or {}
    if not assessment_entry_enabled(class_level): return {}
    fields = {}
    for item in rule.get("fields") or []:
        if not isinstance(item, dict): continue
        key = clean_upper(item.get("key")).lower(); maximum = optional_float(item.get("max"))
        if key and maximum is not None: fields[key] = maximum
    exam_max = optional_float(rule.get("exam_max"))
    if exam_max is not None: fields["exam"] = exam_max
    return fields


def manual_score_value(value, maximum, label):
    if value in (None, ""): return None
    try: number = float(str(value).replace(",", "").strip())
    except (TypeError, ValueError): raise ValueError(f"{label} must be a valid number.")
    if number < 0 or number > maximum: raise ValueError(f"{label} must be between 0 and {maximum}.")
    return int(number) if number.is_integer() else round(number, 2)


def normalize_manual_attendance(values):
    values = values if isinstance(values, dict) else {}; keys = ["days_open", "present", "absent", "late", "sick", "excused"]
    output = {}
    for key in keys:
        raw = values.get(key, 0)
        try: number = int(float(raw or 0))
        except (TypeError, ValueError): raise ValueError(f"Attendance {key.replace('_', ' ')} must be a whole number.")
        if number < 0: raise ValueError(f"Attendance {key.replace('_', ' ')} cannot be negative.")
        output[key] = number
    marked = output["present"] + output["absent"] + output["late"] + output["sick"] + output["excused"]
    if output["days_open"] and marked > output["days_open"]: raise ValueError("Attendance totals cannot be greater than Days School Open.")
    output["unmarked"] = max(0, output["days_open"] - marked); output["present_credit"] = output["present"] + output["late"] + output["excused"]; output["absent_total"] = output["absent"] + output["sick"]
    output["attendance_percentage"] = round((output["present_credit"] / output["days_open"]) * 100, 1) if output["days_open"] else 0
    return output


def normalize_manual_subject(entry, class_level, allowed_map):
    entry = entry if isinstance(entry, dict) else {}; raw_subject = entry.get("subject") or entry.get("subject_key"); key = academic_subject_key(raw_subject)
    if not key or key not in allowed_map or clean_upper(key) in {"ISLAMIYYAH", "ISLAMIYAH"}: return None
    fields = manual_score_fields(class_level); values = {field: manual_score_value(entry.get(field), maximum, field.upper()) for field, maximum in fields.items()}
    included = str(entry.get("included") or "").strip().lower() in {"1", "true", "yes", "on"} or any(value is not None for value in values.values())
    if not included: return None
    return {"subject": allowed_map.get(key) or normalize_academic_subject(raw_subject), "subject_key": key, "included": True, **values}


def manual_context_key(academic_session, term, class_level, class_arm, admission_number): return report_context_key(academic_session, term, class_level, class_arm, admission_number)


def get_manual_record(academic_session, term, class_level, class_arm, admission_number):
    return _read_json_store(MANUAL_FILE).get(manual_context_key(academic_session, term, class_level, class_arm, admission_number), {})


def save_manual_record(academic_session, term, class_level, class_arm, admission_number, data, student_record=None, queue_sync=True):
    key = manual_context_key(academic_session, term, class_level, class_arm, admission_number); source_student = student_record if isinstance(student_record, dict) else (get_student(admission_number, active_only=False) or {}); allowed = {key:value for key,value in expected_subject_map(source_student, class_level, class_arm).items() if clean_upper(key) not in {"ISLAMIYYAH","ISLAMIYAH"}}; is_teacher = report_role() == "teacher"
    if is_teacher:
        if not teacher_can_access_report_class(report_teacher_id(), academic_session, class_level, class_arm): raise ValueError("Access denied. This class is not assigned to your Teacher ID.")
        assigned=set(teacher_allowed_report_subjects(report_teacher_id(), academic_session, class_level, class_arm)); allowed={key:value for key,value in allowed.items() if key in assigned}
    entries=data.get("subjects") if isinstance(data.get("subjects"),list) else []; visible_keys={academic_subject_key(value) for value in (data.get("visible_subject_keys") or []) if academic_subject_key(value)}
    if is_teacher: visible_keys={key for key in visible_keys if key in allowed}
    with REPORT_LOCK:
        store=_read_json_store(MANUAL_FILE); current=store.get(key,{}) if isinstance(store.get(key),dict) else {}; subjects=dict(current.get("subjects",{})) if isinstance(current.get("subjects"),dict) else {}
        if "subjects" in data:
            if is_teacher:
                for entry in entries:
                    key_check=academic_subject_key((entry or {}).get("subject_key") or (entry or {}).get("subject")) if isinstance(entry,dict) else ""
                    if key_check and key_check not in allowed: raise ValueError(f"Access denied. {(entry or {}).get('subject') or key_check} is not assigned to your Teacher ID.")
                for visible_key in visible_keys: subjects.pop(visible_key,None)
            elif visible_keys:
                for visible_key in visible_keys: subjects.pop(visible_key,None)
            else: subjects={}
            for entry in entries:
                normalized=normalize_manual_subject(entry,class_level,allowed)
                if normalized: subjects[normalized["subject_key"]]=normalized
        attendance_supplied=isinstance(data.get("attendance"),dict); attendance=current.get("attendance",{}) if is_teacher else (normalize_manual_attendance(data.get("attendance")) if attendance_supplied else current.get("attendance",{})); status="FINAL" if clean_upper(data.get("status")) == "FINAL" else "DRAFT"
        if is_teacher:
            required=list(get_report_subject_scope(class_level,class_arm).get("selected_keys") or []); fields=manual_score_fields(class_level); status="FINAL" if required and all(isinstance(subjects.get(subject_key),dict) and all(subjects[subject_key].get(field) not in (None,"") for field in fields) for subject_key in required) else "DRAFT"
        item={"session":normalize_academic_session(academic_session),"term":normalize_academic_term(term),"class_level":class_level,"class_arm":class_arm,"admission_number":clean(admission_number),"subjects":subjects if "subjects" in data else current.get("subjects",{}),"attendance":attendance if isinstance(attendance,dict) else {},"attendance_user_set":bool(current.get("attendance_user_set",False)) if is_teacher else bool(data.get("attendance_user_set",current.get("attendance_user_set",False))),"attendance_override_enabled":bool(current.get("attendance_override_enabled",False)) if is_teacher else bool(data.get("attendance_override_enabled",current.get("attendance_override_enabled",False))),"prefer_manual_scores":bool(current.get("prefer_manual_scores",False)) if is_teacher else bool(data.get("prefer_manual_scores",current.get("prefer_manual_scores",False))),"suppress_automatic_scores":bool(current.get("suppress_automatic_scores",False)) if is_teacher else bool(data.get("suppress_automatic_scores",current.get("suppress_automatic_scores",False))),"status":status,"teacher_note":clean(current.get("teacher_note","")) if is_teacher else clean(data.get("teacher_note",current.get("teacher_note",""))),"excluded_from_class_report":bool(current.get("excluded_from_class_report",False)) if is_teacher else bool(data.get("excluded_from_class_report",current.get("excluded_from_class_report",False))),"exclusion_reason":clean(current.get("exclusion_reason","")) if is_teacher else clean(data.get("exclusion_reason",current.get("exclusion_reason",""))),"updated_at":now_string(),"updated_by":clean(session.get("admin_username") or session.get("username") or session.get("user") or current.get("updated_by") or "Staff")}; store[key]=item; _write_json_store(MANUAL_FILE,store)
    if queue_sync: queue_emis_event_safely("report_sheets","manual_upsert",{"key":key,"item":item},entity_key=f"manual|{key}")
    return item


def queue_manual_record_sync_background(key, item):
    """Queue cloud/retry bookkeeping outside the score-save request path.

    Manual score persistence is local and authoritative.  A busy sync SQLite file must never
    leave teachers watching a Save button spin for 15–60 seconds, so fast Manual saves return
    immediately after the durable JSON write and queue the sync event on a daemon thread.
    """
    def _queue():
        queue_emis_event_safely("report_sheets", "manual_upsert", {"key": key, "item": item}, entity_key=f"manual|{key}")
    try: Thread(target=_queue, name="emis-manual-score-sync", daemon=True).start()
    except Exception: _queue()


def bool_request_flag(value):
    return clean(value).lower() in {"1", "true", "yes", "on"}


def manual_record_summary(record):
    record = record if isinstance(record, dict) else {}; subjects = record.get("subjects") if isinstance(record.get("subjects"), dict) else {}
    return {"has_manual": bool(subjects or record.get("attendance")), "subject_count": len(subjects), "status": clean(record.get("status") or "DRAFT"), "attendance_override_enabled": bool(record.get("attendance_override_enabled")), "suppress_automatic_scores": bool(record.get("suppress_automatic_scores")), "excluded_from_class_report": bool(record.get("excluded_from_class_report")), "exclusion_reason": clean(record.get("exclusion_reason")), "updated_at": clean(record.get("updated_at")), "updated_by": clean(record.get("updated_by"))}


def manual_class_readiness(academic_session, term, class_level, class_arm):
    """Return the authoritative Manual Workstation class-completion state.

    Generation is class-based: every non-excluded pupil must have a FINAL saved record
    with every configured score component for every selected report subject that belongs
    to that pupil.  Excluded pupils remain visible in the roster but do not enter class
    statistics or report generation.
    """
    academic_session, term = normalize_academic_session(academic_session), normalize_academic_term(term); level, arm = normalize_report_class(class_level, class_arm)
    students = get_report_students_for_class(level, arm, active_only=True); store = _read_json_store(MANUAL_FILE); scope = get_report_subject_scope(level, arm); selected_keys = list(scope.get("selected_keys") or []); fields = manual_score_fields(level); rows = []
    # Manual Workstation now has one authoritative class curriculum.  Do not resolve the
    # subject registry again for every pupil; every included pupil must complete the same
    # selected class subjects.  This is both the intended workflow and substantially faster.
    for student in students:
        admission = normalize_admission_number(student.get("admission_number")); record = store.get(manual_context_key(academic_session, term, level, arm, admission), {}) if admission else {}; excluded = bool(record.get("excluded_from_class_report")); required_keys = selected_keys; saved_subjects = record.get("subjects") if isinstance(record.get("subjects"), dict) else {}; missing_subjects, missing_fields = [], []
        if not excluded:
            for subject_key in required_keys:
                entry = saved_subjects.get(subject_key) if isinstance(saved_subjects.get(subject_key), dict) else None
                if not entry:
                    missing_subjects.append(subject_key); continue
                for field in fields:
                    if entry.get(field) in (None, ""): missing_fields.append(f"{subject_key}:{field}")
        complete = bool(not excluded and required_keys and not missing_subjects and not missing_fields and clean_upper(record.get("status")) == "FINAL")
        rows.append({"admission_number": clean(student.get("admission_number")), "full_name": clean(student.get("full_name")), "excluded": excluded, "exclusion_reason": clean(record.get("exclusion_reason")), "complete": complete, "status": clean(record.get("status") or "NOT_STARTED"), "required_subjects": len(required_keys), "completed_subjects": max(0, len(required_keys) - len(missing_subjects) - len({item.split(':',1)[0] for item in missing_fields})), "missing_subjects": missing_subjects, "missing_fields": missing_fields})
    eligible = [row for row in rows if not row["excluded"]]; ready = [row for row in eligible if row["complete"]]; excluded = [row for row in rows if row["excluded"]]; pending = [row for row in eligible if not row["complete"]]; percent = round((len(ready) / len(eligible)) * 100, 1) if eligible else 0
    return {"students": rows, "total_students": len(rows), "eligible_students": len(eligible), "ready_students": len(ready), "remaining_students": len(pending), "excluded_students": len(excluded), "progress_percent": percent, "class_ready": bool(eligible) and not pending, "ready_admissions": [row["admission_number"] for row in ready], "eligible_admissions": [row["admission_number"] for row in eligible], "excluded_admissions": [row["admission_number"] for row in excluded], "pending": pending, "subject_scope": scope, "score_fields": fields}


# ============================================================
# HYBRID / MANUAL REPORT SYSTEM — REPORT CALCULATION
# ============================================================


def build_manual_subject_row(class_level, entry):
    entry = entry if isinstance(entry, dict) else {}; rule = get_assessment_rule(class_level) or {}; fields = manual_score_fields(class_level); scores = {field: optional_float(entry.get(field)) for field in fields}; component_keys = [clean_upper(item.get("key")).lower() for item in rule.get("fields") or [] if isinstance(item, dict) and clean_upper(item.get("key"))]; ca_values = [scores.get(field) for field in component_keys]; exam = scores.get("exam")
    has_ca = any(value is not None for value in ca_values); ca_complete = bool(component_keys) and all(value is not None for value in ca_values); has_exam = exam is not None; ca_total = round(sum(value or 0 for value in ca_values), 2) if has_ca else None; complete = ca_complete and has_exam; total = round((ca_total or 0) + exam, 2) if complete else None; grade, comment = grade_for_score(total, class_level) if total is not None else ("-", "Pending"); mode = clean_upper(rule.get("key"))
    definitions = [{"key": clean_upper(item.get("key")).lower(), "raw_key": clean_upper(item.get("key")), "label": clean(item.get("label") or item.get("key")), "max": optional_float(item.get("max")), "value": pretty_optional(scores.get(clean_upper(item.get("key")).lower()))} for item in rule.get("fields") or [] if isinstance(item, dict) and clean_upper(item.get("key"))]
    row = {"subject": normalize_academic_subject(entry.get("subject") or entry.get("subject_key")), "subject_key": academic_subject_key(entry.get("subject_key") or entry.get("subject")), "mode": mode, "assessment_mode": mode, "assessment_status": clean(rule.get("status")), "components": {key: pretty_optional(scores.get(key)) for key in component_keys}, "component_fields": definitions, "has_ca": has_ca, "has_exam": has_exam, "ca_complete": ca_complete, "exam_complete": has_exam, "complete": complete, "ca_total": pretty_optional(ca_total), "ca_max": pretty_optional(rule.get("ca_max")), "exam": pretty_optional(exam), "exam_max": pretty_optional(rule.get("exam_max")), "total": pretty_optional(total), "total_max": pretty_optional(rule.get("total_max") or 100), "grade": grade, "comment": comment, "position": 0, "position_text": "--", "out_of": 0, "lowest": None, "highest": None, "class_average": None}
    if mode == "JSS": row.update({"ca1": pretty_optional(scores.get("ca1")), "ca2": pretty_optional(scores.get("ca2")), "test1": pretty_optional(scores.get("test1")), "test2": pretty_optional(scores.get("test2"))})
    elif mode == "SS": row.update({"ass1": pretty_optional(scores.get("ass1")), "ass2": pretty_optional(scores.get("ass2")), "test": pretty_optional(scores.get("test"))})
    return row


def finalize_report_statistics(reports):
    reports = reports if isinstance(reports, list) else []; subject_scores = {}
    for report in reports:
        for row in report.get("subjects", []):
            if row.get("total") is not None: subject_scores.setdefault(row.get("subject_key"), []).append(safe_float(row.get("total")))
    for report in reports:
        for row in report.get("subjects", []):
            if row.get("total") is None: row.update({"position": 0, "position_text": "--", "out_of": 0, "lowest": None, "highest": None, "class_average": None}); continue
            scores = subject_scores.get(row.get("subject_key"), []); position = compute_position(row.get("total"), scores) if scores else 0
            row.update({"position": position, "position_text": ordinal(position) if position else "--", "out_of": len(scores), "lowest": pretty_number(min(scores)) if scores else None, "highest": pretty_number(max(scores)) if scores else None, "class_average": pretty_number(sum(scores) / len(scores)) if scores else None})
        complete_rows = [row for row in report.get("subjects", []) if row.get("complete") and row.get("total") is not None]; all_complete = bool(report.get("subjects")) and len(complete_rows) == len(report.get("subjects", [])); provisional_total = round(sum(safe_float(row.get("total")) for row in complete_rows), 2) if complete_rows else None; provisional_maximum = round(sum(safe_float(row.get("total_max"), 100) for row in complete_rows), 2) if complete_rows else None; provisional_average = round(provisional_total / provisional_maximum * 100, 2) if provisional_total is not None and provisional_maximum else None
        report["subjects_complete"] = len(complete_rows); report["academic_complete"] = all_complete; report["academic_partial"] = bool(report.get("subjects")) and not all_complete; report["provisional_total"] = pretty_optional(provisional_total); report["provisional_maximum"] = pretty_optional(provisional_maximum); report["provisional_average"] = pretty_optional(provisional_average); report["total_score"] = pretty_optional(provisional_total) if all_complete else None; report["maximum_score"] = pretty_optional(provisional_maximum) if all_complete else None; report["average"] = pretty_optional(provisional_average) if all_complete else None; report["grade"] = grade_for_score(provisional_average, report.get("class_level"))[0] if all_complete and provisional_average is not None else "-"
    averages = [safe_float(report.get("average")) for report in reports if report.get("average") is not None]
    for report in reports:
        if report.get("average") is None: report.update({"position": 0, "position_text": "--", "out_of": 0}); continue
        position = compute_position(report.get("average"), averages); report.update({"position": position, "position_text": ordinal(position), "out_of": len(averages)})
    return {"class_average": pretty_number(sum(averages) / len(averages)) if averages else None, "highest_average": pretty_number(max(averages)) if averages else None, "lowest_average": pretty_number(min(averages)) if averages else None}


def audit_manual_report_integrity(payload, expected_admissions):
    """Fail-safe verification for an official Manual/Hybrid class batch before snapshots or printing are allowed.

    Recomputes every report total/average, every overall rank, every subject rank/out-of/low/high/class-average and the class summary directly from the final
    printable rows. Any mismatch blocks generation instead of allowing an internally inconsistent report batch to reach parents.
    """
    reports = payload.get("reports") if isinstance(payload, dict) and isinstance(payload.get("reports"), list) else []; expected = [normalize_admission_number(value) for value in (expected_admissions or []) if normalize_admission_number(value)]; expected = list(dict.fromkeys(expected)); expected_set = set(expected); errors, warnings = [], []
    report_admissions = [normalize_admission_number(report.get("admission_number")) for report in reports]; duplicates = sorted({value for value in report_admissions if value and report_admissions.count(value) > 1}); missing = sorted(expected_set - set(report_admissions)); extras = sorted(set(report_admissions) - expected_set) if expected_set else []
    if duplicates: errors.append(f"Duplicate report rows found for: {', '.join(duplicates)}.")
    if missing: errors.append(f"Missing report rows for: {', '.join(missing)}.")
    if extras: errors.append(f"Unexpected report rows found for: {', '.join(extras)}.")
    if expected and len(reports) != len(expected): errors.append(f"Expected {len(expected)} class reports but generated {len(reports)}.")

    calculated = {}; subject_groups = {}
    for report in reports:
        admission = normalize_admission_number(report.get("admission_number")); rows = report.get("subjects") if isinstance(report.get("subjects"), list) else []; incomplete = [clean(row.get("subject") or row.get("subject_key")) for row in rows if row.get("total") is None or not row.get("complete")]
        if incomplete: errors.append(f"{admission or 'Unknown student'} has incomplete printable subject row(s): {', '.join(incomplete)}.")
        scored = [row for row in rows if row.get("total") is not None and row.get("complete")]; total = round(sum(safe_float(row.get("total")) for row in scored), 2) if scored else None; maximum = round(sum(safe_float(row.get("total_max"), 100) for row in scored), 2) if scored else None; average = round(total / maximum * 100, 2) if total is not None and maximum else None; calculated[admission] = {"total": total, "maximum": maximum, "average": average}
        if average is None: errors.append(f"{admission or 'Unknown student'} has no rankable final average.")
        if total is not None and (optional_float(report.get("total_score")) is None or abs(optional_float(report.get("total_score")) - total) > 0.011): errors.append(f"{admission} total mismatch: report={report.get('total_score')} recalculated={pretty_number(total)}.")
        if maximum is not None and (optional_float(report.get("maximum_score")) is None or abs(optional_float(report.get("maximum_score")) - maximum) > 0.011): errors.append(f"{admission} maximum-score mismatch: report={report.get('maximum_score')} recalculated={pretty_number(maximum)}.")
        if average is not None and (optional_float(report.get("average")) is None or abs(optional_float(report.get("average")) - average) > 0.011): errors.append(f"{admission} average mismatch: report={report.get('average')} recalculated={pretty_number(average)}.")
        expected_grade = grade_for_score(average, report.get("class_level"))[0] if average is not None else "-"
        if average is not None and clean_upper(report.get("grade")) != clean_upper(expected_grade): errors.append(f"{admission} grade mismatch: report={report.get('grade')} recalculated={expected_grade}.")
        for row in scored:
            key = academic_subject_key(row.get("subject_key") or row.get("subject")); subject_groups.setdefault(key, []).append((admission, row, safe_float(row.get("total"))))

    ranked = [(admission, item["average"]) for admission, item in calculated.items() if item.get("average") is not None]; rank_scores = [average for _, average in ranked]; expected_count = len(expected) if expected else len(reports)
    if len(rank_scores) != expected_count: errors.append(f"Ranking cohort mismatch: {len(rank_scores)} rankable report(s) for a {expected_count}-student class cohort.")
    for report in reports:
        admission = normalize_admission_number(report.get("admission_number")); average = calculated.get(admission, {}).get("average")
        if average is None: continue
        expected_position = compute_position(average, rank_scores); actual_position = int(safe_float(report.get("position"), 0)); actual_out_of = int(safe_float(report.get("out_of"), 0))
        if actual_position != expected_position: errors.append(f"{admission} overall position mismatch: report={actual_position or '--'} recalculated={ordinal(expected_position)}.")
        if actual_out_of != expected_count: errors.append(f"{admission} class-size mismatch: report OUT OF={actual_out_of} expected={expected_count}.")

    for subject_key, members in subject_groups.items():
        scores = [score for _, _, score in members]; low, high, average = min(scores), max(scores), sum(scores) / len(scores)
        for admission, row, score in members:
            expected_position = compute_position(score, scores); actual_position = int(safe_float(row.get("position"), 0)); actual_out_of = int(safe_float(row.get("out_of"), 0))
            if actual_position != expected_position: errors.append(f"{admission} {subject_key} position mismatch: report={actual_position or '--'} recalculated={ordinal(expected_position)}.")
            if actual_out_of != len(scores): errors.append(f"{admission} {subject_key} OUT OF mismatch: report={actual_out_of} recalculated={len(scores)}.")
            if optional_float(row.get("lowest")) is None or abs(optional_float(row.get("lowest")) - low) > 0.011: errors.append(f"{admission} {subject_key} lowest-score statistic mismatch.")
            if optional_float(row.get("highest")) is None or abs(optional_float(row.get("highest")) - high) > 0.011: errors.append(f"{admission} {subject_key} highest-score statistic mismatch.")
            if optional_float(row.get("class_average")) is None or abs(optional_float(row.get("class_average")) - round(average, 2)) > 0.011: errors.append(f"{admission} {subject_key} class-average statistic mismatch.")

    summary = payload.get("summary") if isinstance(payload, dict) and isinstance(payload.get("summary"), dict) else {}; class_average = round(sum(rank_scores) / len(rank_scores), 2) if rank_scores else None; class_high = max(rank_scores) if rank_scores else None; class_low = min(rank_scores) if rank_scores else None
    for label, actual, expected_value in [("class average", optional_float(summary.get("class_average")), class_average), ("highest average", optional_float(summary.get("highest_average")), class_high), ("lowest average", optional_float(summary.get("lowest_average")), class_low)]:
        if expected_value is not None and (actual is None or abs(actual - expected_value) > 0.011): errors.append(f"Summary {label} mismatch: report={actual} recalculated={pretty_number(expected_value)}.")
    subject_counts = sorted({len(report.get("subjects") or []) for report in reports})
    if len(subject_counts) > 1: warnings.append(f"Printable subject counts vary across pupils ({', '.join(map(str, subject_counts))}) because complete optional/synced subjects may exist for only part of the class. Overall ranks were still verified across all {expected_count} pupils.")
    verified = not errors
    for report in reports: report["integrity_verified"] = verified; report["integrity_cohort_size"] = expected_count; report["integrity_checked_at"] = now_string()
    return {"verified": verified, "cohort_size": expected_count, "reports_checked": len(reports), "ranked_students": len(rank_scores), "subjects_checked": len(subject_groups), "errors": errors, "warnings": warnings, "class_average_recalculated": pretty_optional(class_average), "highest_average_recalculated": pretty_optional(class_high), "lowest_average_recalculated": pretty_optional(class_low)}


def build_manual_report_payload(academic_session, term, class_level, class_arm, admission_numbers=None, preloaded_students=None, preloaded_store=None, preloaded_scope=None):
    academic_session, term = normalize_academic_session(academic_session), normalize_academic_term(term); level, arm = normalize_report_class(class_level, class_arm); students = list(preloaded_students) if isinstance(preloaded_students, (list, tuple)) else get_report_students_for_class(level, arm, active_only=True); requested = set(normalize_admission_selection(admission_numbers)); store = preloaded_store if isinstance(preloaded_store, dict) else _read_json_store(MANUAL_FILE); records_for_class = [store.get(manual_context_key(academic_session, term, level, arm, normalize_admission_number(student.get("admission_number"))), {}) for student in students]; needs_saved_attendance = any(isinstance(record, dict) and isinstance(record.get("subjects"), dict) and record.get("subjects") and not (isinstance(record.get("attendance"), dict) and record.get("attendance")) for record in records_for_class); saved_attendance = get_attendance_summary_map(academic_session, term, level, arm) if needs_saved_attendance else {}; reports, source_students, catalog = [], [], set(); scope = preloaded_scope if isinstance(preloaded_scope, dict) else get_report_subject_scope(level, arm); selected_subject_keys = list(scope.get("selected_keys") or [])
    for student in students:
        admission = normalize_admission_number(student.get("admission_number")); record = store.get(manual_context_key(academic_session, term, level, arm, admission), {}) if admission else {}; record_subjects = record.get("subjects") if isinstance(record.get("subjects"), dict) else {}; rows = []
        for subject_key in selected_subject_keys:
            entry = record_subjects.get(subject_key)
            if not isinstance(entry, dict): continue
            row = build_manual_subject_row(level, entry); rows.append(row); catalog.add(subject_key)
        manual_attendance = record.get("attendance") if isinstance(record.get("attendance"), dict) else {}; attendance = manual_attendance or saved_attendance.get(admission, {}); has_manual = bool(rows or manual_attendance); excluded = bool(record.get("excluded_from_class_report")); source_students.append({**student, "has_manual": has_manual, "manual_status": clean(record.get("status") or ""), "manual_subject_count": len(rows), "has_attendance": bool(attendance), "excluded_from_class_report": excluded, "exclusion_reason": clean(record.get("exclusion_reason"))})
        if excluded or not has_manual: continue
        reports.append({"admission_number": student.get("admission_number"), "full_name": student.get("full_name"), "last_name": student.get("last_name"), "first_name": student.get("first_name"), "other_names": student.get("other_names"), "sex": student.get("sex"), "class_level": level, "class_arm": arm, "session": academic_session, "term": term, "term_label": academic_term_label(term), "subjects": rows, "subject_count": len(rows), "has_ca": any(row.get("has_ca") for row in rows), "has_exam": any(row.get("has_exam") for row in rows), "has_attendance": bool(attendance), "attendance": attendance, "source_mode": "manual", "manual_status": clean(record.get("status") or "DRAFT"), "manual_updated_at": clean(record.get("updated_at")), "result_name": "", "teacher_remark": "", "principal_remark": "", "missing_ca_subjects": [row.get("subject_key") for row in rows if not row.get("has_ca")], "missing_exam_subjects": [row.get("subject_key") for row in rows if not row.get("has_exam")]})
    payload = {"success": bool(reports), "session": academic_session, "term": term, "term_label": academic_term_label(term), "class_level": level, "class_arm": arm, "students": source_students, "reports": reports, "blocked_students": [], "readiness_warnings": [], "source_status": {"students": bool(students), "manual": bool(reports), "attendance": bool(saved_attendance)}, "summary": {"students_in_class": len(students), "generated": len(reports), "manual_ready": len(reports), "subjects": len(catalog)}}; payload = apply_islamiyah_report_rows(payload); payload = apply_report_subject_scope(payload, level, arm, preloaded_scope=scope); reports = payload.get("reports", []); stats = finalize_report_statistics(reports); payload["summary"] = {**(payload.get("summary") or {}), **stats, "generated": len(reports)}
    payload = apply_saved_report_details(payload)
    for report in payload.get("reports", []): report["result_name"] = result_file_stem(report)
    if requested:
        payload["reports"] = [report for report in payload.get("reports", []) if normalize_admission_number(report.get("admission_number")) in requested]; payload["summary"]["generated"] = len(payload["reports"]); payload["success"] = bool(payload["reports"])
    return payload


def merge_hybrid_subject_row(class_level, auto_row=None, manual_row=None, prefer_manual=False):
    auto_row, manual_row = auto_row if isinstance(auto_row, dict) else {}, manual_row if isinstance(manual_row, dict) else {}; fields = list(manual_score_fields(class_level))
    values = {}
    for field in fields:
        first, second = (manual_row.get(field), auto_row.get(field)) if prefer_manual else (auto_row.get(field), manual_row.get(field)); values[field] = first if first not in (None, "") else second
    subject = manual_row.get("subject") or auto_row.get("subject") or manual_row.get("subject_key") or auto_row.get("subject_key"); entry = {"subject": subject, "subject_key": manual_row.get("subject_key") or auto_row.get("subject_key"), "included": True, **values}; row = build_manual_subject_row(class_level, entry); row["hybrid_manual_used"] = any(manual_row.get(field) not in (None, "") and (prefer_manual or auto_row.get(field) in (None, "")) for field in fields)
    return row


def build_hybrid_report_payload(academic_session, term, class_level, class_arm, result_year="", admission_numbers=None):
    auto = _AUTO_BUILD_TERM_REPORT_PAYLOAD(academic_session, term, class_level, class_arm, result_year, "", True, None); manual = build_manual_report_payload(academic_session, term, class_level, class_arm); manual_map = report_map(manual); store = _read_json_store(MANUAL_FILE); reports = auto.get("reports", []) if isinstance(auto.get("reports"), list) else []
    for report in reports:
        admission = normalize_admission_number(report.get("admission_number")); manual_report = manual_map.get(admission, {}); record = store.get(manual_context_key(auto.get("session"), auto.get("term"), auto.get("class_level"), auto.get("class_arm"), admission), {}) if admission else {}; prefer_manual = bool(record.get("prefer_manual_scores")); auto_rows = {row.get("subject_key"): row for row in report.get("subjects", []) if row.get("subject_key")}; manual_rows = {row.get("subject_key"): row for row in manual_report.get("subjects", []) if row.get("subject_key")}; order = list(auto_rows) + [key for key in manual_rows if key not in auto_rows]; merged, used = [], 0
        for key in order:
            row = merge_hybrid_subject_row(report.get("class_level"), auto_rows.get(key), manual_rows.get(key), prefer_manual); merged.append(row); used += 1 if row.get("hybrid_manual_used") else 0
        report["subjects"] = merged; report["subject_count"] = len(merged); report["source_mode"] = "hybrid"; report["manual_subjects_used"] = used; report["manual_status"] = clean(record.get("status") or "")
        manual_attendance = record.get("attendance") if isinstance(record.get("attendance"), dict) else {}
        if manual_attendance and (record.get("attendance_override_enabled") or not report.get("attendance")): report["attendance"] = manual_attendance; report["has_attendance"] = True; report["manual_attendance_used"] = True
    excluded = {normalize_admission_number(value.get("admission_number")) for value in store.values() if isinstance(value, dict) and normalize_academic_session(value.get("session")) == normalize_academic_session(academic_session) and normalize_academic_term(value.get("term")) == normalize_academic_term(term) and value.get("class_level") == auto.get("class_level") and value.get("class_arm") == auto.get("class_arm") and value.get("excluded_from_class_report")}
    reports = [report for report in reports if normalize_admission_number(report.get("admission_number")) not in excluded]; auto["reports"] = reports; auto["students"] = [student for student in (auto.get("students") or []) if normalize_admission_number(student.get("admission_number")) not in excluded]; auto = apply_islamiyah_report_rows(auto); auto = apply_report_subject_scope(auto, class_level, class_arm); reports = auto.get("reports", []); stats = finalize_report_statistics(reports); auto["summary"] = {**(auto.get("summary") or {}), **stats, "generated": len(reports), "excluded_students": len(excluded), "hybrid_manual_subjects_used": sum(int(report.get("manual_subjects_used") or 0) for report in reports)}; auto = apply_saved_report_details(auto)
    for report in auto.get("reports", []): report["result_name"] = result_file_stem(report)
    requested = set(normalize_admission_selection(admission_numbers))
    if requested:
        auto["reports"] = [report for report in auto.get("reports", []) if normalize_admission_number(report.get("admission_number")) in requested]; auto["students"] = [student for student in auto.get("students", []) if normalize_admission_number(student.get("admission_number")) in requested]; auto["summary"]["generated"] = len(auto["reports"]); auto["success"] = bool(auto["reports"])
    return auto


# ============================================================
# HYBRID / MANUAL REPORT SYSTEM — AUTO ATTENDANCE OVERRIDE
# ============================================================

_AUTO_BUILD_TERM_REPORT_PAYLOAD = build_term_report_payload


def apply_manual_attendance_overrides(payload):
    if not isinstance(payload, dict): return payload
    store = _read_json_store(MANUAL_FILE); session_value, term, level, arm = payload.get("session", ""), payload.get("term", ""), payload.get("class_level", ""), payload.get("class_arm", ""); override_count = 0
    for report in payload.get("reports", []):
        admission = normalize_admission_number(report.get("admission_number")); record = store.get(manual_context_key(session_value, term, level, arm, admission), {}) if admission else {}; attendance = record.get("attendance") if isinstance(record.get("attendance"), dict) else {}
        if record.get("attendance_override_enabled") and attendance: report["attendance"] = attendance; report["has_attendance"] = True; report["manual_attendance_used"] = True; override_count += 1
    source_map = {normalize_admission_number(report.get("admission_number")): report for report in payload.get("reports", [])}
    for student in payload.get("students", []):
        report = source_map.get(normalize_admission_number(student.get("admission_number")))
        if report and report.get("manual_attendance_used"): student["has_attendance"] = True; student["manual_attendance_used"] = True
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}; summary["manual_attendance_overrides"] = override_count; summary["missing_attendance"] = sum(1 for report in payload.get("reports", []) if not report.get("has_attendance")); summary["reports_with_attendance"] = sum(1 for report in payload.get("reports", []) if report.get("has_attendance")); payload["summary"] = summary
    for report in payload.get("reports", []): report["source_mode"] = clean(report.get("source_mode") or "auto"); report["result_name"] = result_file_stem(report)
    return payload


def apply_saved_manual_score_overrides(payload):
    """Merge saved Manual Studio scores into normal report generation.

    Saved manual values fill missing automated CA/CBT fields immediately, so closing
    the Studio and using the normal Generate button keeps the same student data.
    Automated values remain authoritative unless Prefer Manual is enabled.
    """
    if not isinstance(payload, dict): return payload
    session_value, term, level, arm = payload.get("session", ""), payload.get("term", ""), payload.get("class_level", ""), payload.get("class_arm", "")
    store = _read_json_store(MANUAL_FILE); manual_payload = build_manual_report_payload(session_value, term, level, arm); manual_map = report_map(manual_payload)
    reports = payload.get("reports") if isinstance(payload.get("reports"), list) else []; report_by_admission = {normalize_admission_number(report.get("admission_number")): report for report in reports if normalize_admission_number(report.get("admission_number"))}
    saved_records, used_fields = 0, 0

    for admission, manual_report in manual_map.items():
        record = store.get(manual_context_key(session_value, term, level, arm, admission), {}) if admission else {}
        status = clean_upper(record.get("status") or "DRAFT")
        if status not in {"DRAFT", "FINAL"}: continue
        saved_records += 1; target = report_by_admission.get(admission)
        if not target:
            target = dict(manual_report); target["source_mode"] = "manual-saved"; reports.append(target); report_by_admission[admission] = target
            used_fields += sum(1 for row in target.get("subjects", []) for field in manual_score_fields(level) if row.get(field) not in (None, ""))
            continue

        prefer_manual = bool(record.get("prefer_manual_scores")); auto_rows = {row.get("subject_key"): row for row in target.get("subjects", []) if row.get("subject_key")}; manual_rows = {row.get("subject_key"): row for row in manual_report.get("subjects", []) if row.get("subject_key")}; order = list(auto_rows) + [key for key in manual_rows if key not in auto_rows]; merged, used = [], 0
        for key in order:
            row = merge_hybrid_subject_row(level, auto_rows.get(key), manual_rows.get(key), prefer_manual); merged.append(row); used += sum(1 for field in manual_score_fields(level) if manual_rows.get(key, {}).get(field) not in (None, "") and (prefer_manual or auto_rows.get(key, {}).get(field) in (None, "")))
        target["subjects"] = merged; target["subject_count"] = len(merged); target["has_ca"] = any(row.get("has_ca") for row in merged); target["has_exam"] = any(row.get("has_exam") for row in merged); target["missing_ca_subjects"] = [row.get("subject_key") for row in merged if not row.get("has_ca")]; target["missing_exam_subjects"] = [row.get("subject_key") for row in merged if not row.get("has_exam")]; target["source_mode"] = "auto+manual-saved" if used else clean(target.get("source_mode") or "auto"); target["manual_status"] = status; target["manual_subjects_used"] = used; used_fields += used
        manual_attendance = record.get("attendance") if isinstance(record.get("attendance"), dict) else {}
        if manual_attendance and (record.get("attendance_override_enabled") or not target.get("attendance")): target["attendance"] = manual_attendance; target["has_attendance"] = True; target["manual_attendance_used"] = True

    stats = finalize_report_statistics(reports); summary = dict(payload.get("summary") or {}); summary.update(stats); summary["generated"] = len(reports); summary["saved_manual_records"] = saved_records; summary["saved_manual_score_fields_used"] = used_fields; summary["complete_reports"] = sum(1 for report in reports if report.get("academic_complete")); summary["partial_reports"] = sum(1 for report in reports if not report.get("academic_complete")); payload["summary"] = summary; payload["reports"] = reports; payload["success"] = bool(reports)
    student_map = {normalize_admission_number(student.get("admission_number")): student for student in payload.get("students", []) if normalize_admission_number(student.get("admission_number"))}
    for admission in manual_map:
        record = store.get(manual_context_key(session_value, term, level, arm, admission), {}) if admission else {}
        status = clean_upper(record.get("status") or "DRAFT")
        if status in {"DRAFT", "FINAL"} and admission in student_map: student_map[admission]["has_manual"] = True; student_map[admission]["manual_status"] = status
    for report in reports: report["result_name"] = result_file_stem(report)
    return payload


def apply_islamiyah_report_rows(payload):
    """Make Islamiyyah School the authoritative source without allowing unfinished Academy rows to corrupt official regular-school statistics.

    Only a COMPLETE Islamiyyah /100 result is inserted into the printable report. Linked pupils whose Islamiyyah score is pending/partial stay visible in the
    Islamiyyah Sync workspace, but no blank subject row is added to the official report and their regular-school average/position remains fully rankable.
    """
    if not isinstance(payload, dict): return payload
    session_value, term = normalize_academic_session(payload.get("session")), normalize_academic_term(payload.get("term")); reports = payload.get("reports") if isinstance(payload.get("reports"), list) else []; integrated = pending = complete_count = 0
    # Seed the Academy/regular identity bridge once per term payload, not once per pupil. This removes the largest repeated disk/database walk in cumulative class loads.
    try: seed_register_enrollments(session_value)
    except Exception: pass
    for report in reports:
        admission = normalize_admission_number(report.get("admission_number")); rows = list(report.get("subjects") or []); existing_index = next((index for index, row in enumerate(rows) if clean_upper(row.get("subject_key") or row.get("subject")) in {"ISLAMIYYAH", "ISLAMIYAH"}), None)
        # Never trust a legacy/manual Islamiyyah row. Remove it first, then attach only a complete authoritative Academy/regular-Islamiyyah result.
        rows = [row for row in rows if clean_upper(row.get("subject_key") or row.get("subject")) not in {"ISLAMIYYAH", "ISLAMIYAH"}]; report["subjects"] = rows; report["subject_count"] = len(rows); islamiyah_row = get_report_islamiyah_row(admission, session_value, term, ensure_seed=False)
        has_verified_score = bool(islamiyah_row and islamiyah_row.get("complete") and optional_float(islamiyah_row.get("total")) is not None)
        if not has_verified_score:
            if islamiyah_row is not None:
                pending += 1; report["has_islamiyah"] = False; report["islamiyah_complete"] = False; report["islamiyah_status"] = islamiyah_row.get("islamiyah_status") or "pending"; report["islamiyah_class"] = islamiyah_row.get("islamiyah_class"); report["islamiyah_class_label"] = islamiyah_row.get("islamiyah_class_label"); report["islamiyah_source"] = "ISLAMIYYAH_SCHOOL"
            report["missing_ca_subjects"] = [key for key in (report.get("missing_ca_subjects") or []) if clean_upper(key) not in {"ISLAMIYYAH", "ISLAMIYAH"}]; report["missing_exam_subjects"] = [key for key in (report.get("missing_exam_subjects") or []) if clean_upper(key) not in {"ISLAMIYYAH", "ISLAMIYAH"}]; continue
        if existing_index is None:
            irs_index = next((index for index, row in enumerate(rows) if clean_upper(row.get("subject_key")) == "IRS"), None); insert_at = (irs_index + 1) if irs_index is not None else min(4, len(rows))
        else: insert_at = min(existing_index, len(rows))
        rows.insert(insert_at, islamiyah_row); report["subjects"] = rows; report["subject_count"] = len(rows); report["has_islamiyah"] = True; report["islamiyah_source"] = "ISLAMIYYAH_SCHOOL"; report["islamiyah_class"] = islamiyah_row.get("islamiyah_class"); report["islamiyah_class_label"] = islamiyah_row.get("islamiyah_class_label"); report["islamiyah_complete"] = True; report["islamiyah_status"] = islamiyah_row.get("islamiyah_status") or "complete"; report["missing_ca_subjects"] = [key for key in (report.get("missing_ca_subjects") or []) if clean_upper(key) not in {"ISLAMIYYAH", "ISLAMIYAH"}]; report["missing_exam_subjects"] = [key for key in (report.get("missing_exam_subjects") or []) if clean_upper(key) not in {"ISLAMIYYAH", "ISLAMIYAH"}]; integrated += 1; complete_count += 1
    if not integrated and not pending: return payload
    stats = finalize_report_statistics(reports)
    for report in reports:
        average = optional_float(report.get("average")); report["teacher_remark"] = teacher_remark(average) if average is not None else ""; report["principal_remark"] = principal_remark(average) if average is not None else ""; report["result_name"] = result_file_stem(report)
    student_map = {normalize_admission_number(student.get("admission_number")): student for student in payload.get("students", []) if normalize_admission_number(student.get("admission_number"))}
    for report in reports:
        student = student_map.get(normalize_admission_number(report.get("admission_number")))
        if student: student.update({"has_islamiyah": bool(report.get("has_islamiyah")), "islamiyah_complete": bool(report.get("islamiyah_complete")), "islamiyah_class": report.get("islamiyah_class"), "islamiyah_class_label": report.get("islamiyah_class_label"), "islamiyah_status": report.get("islamiyah_status"), "islamiyah_source": report.get("islamiyah_source")})
    summary = dict(payload.get("summary") or {}); summary.update(stats); summary.update({"generated": len(reports), "complete_reports": sum(1 for report in reports if report.get("academic_complete")), "partial_reports": sum(1 for report in reports if not report.get("academic_complete")), "islamiyah_integrated": integrated, "islamiyah_complete": complete_count, "islamiyah_pending": pending, "islamiyah_authoritative_source": "ISLAMIYYAH_SCHOOL"}); payload["summary"] = summary
    source_status = dict(payload.get("source_status") or {}); source_status["islamiyah"] = bool(integrated or pending); source_status["islamiyah_complete"] = pending == 0; source_status["islamiyah_authoritative"] = True; payload["source_status"] = source_status
    return payload

def build_term_report_payload(academic_session, term, class_level, class_arm, result_year="", admission_number="", include_cumulative=True, admission_numbers=None):
    # Build the full class first so Manual Studio values still receive correct class
    # statistics/positions, then filter to the requested student(s).
    payload = _AUTO_BUILD_TERM_REPORT_PAYLOAD(academic_session, term, class_level, class_arm, result_year, "", include_cumulative, None)
    payload = apply_saved_manual_score_overrides(payload); payload = apply_manual_attendance_overrides(payload); payload = apply_islamiyah_report_rows(payload); payload = apply_report_subject_scope(payload, class_level, class_arm)
    if normalize_academic_term(term) == "THIRD" and include_cumulative and payload.get("reports"): attach_cumulative_results(payload, normalize_academic_session(academic_session), payload.get("class_level") or class_level, payload.get("class_arm") or class_arm, resolve_result_year(academic_session, result_year, payload.get("class_level") or class_level, payload.get("class_arm") or class_arm), mode="auto")
    requested = normalize_admission_selection(admission_numbers); single = normalize_admission_number(admission_number)
    if single and single not in requested: requested.insert(0, single)
    if requested:
        wanted = set(requested); payload["reports"] = [report for report in payload.get("reports", []) if normalize_admission_number(report.get("admission_number")) in wanted]; payload["students"] = [student for student in payload.get("students", []) if normalize_admission_number(student.get("admission_number")) in wanted]; payload["blocked_students"] = [student for student in payload.get("blocked_students", []) if normalize_admission_number(student.get("admission_number")) in wanted]; payload["readiness_warnings"] = [student for student in payload.get("readiness_warnings", []) if normalize_admission_number(student.get("admission_number")) in wanted]; payload["summary"] = dict(payload.get("summary") or {}); payload["summary"]["generated"] = len(payload["reports"]); payload["summary"]["blocked"] = len(payload.get("blocked_students", [])); payload["summary"]["selected_requested"] = len(requested); payload["success"] = bool(payload["reports"])
    return payload


# ============================================================
# THIRD TERM CUMULATIVE — LIVE REPORT-SHEET SYNC
# ============================================================

LIVE_CUMULATIVE_TERMS = ("FIRST", "SECOND", "THIRD")

def _live_cumulative_term_payload(academic_session, term, class_level, class_arm, mode="manual", result_year=""):
    mode = clean(mode or "manual").lower()
    if mode == "manual": return build_manual_report_payload(academic_session, term, class_level, class_arm)
    if mode == "hybrid": return build_hybrid_report_payload(academic_session, term, class_level, class_arm, result_year)
    return build_term_report_payload(academic_session, term, class_level, class_arm, result_year, include_cumulative=False)


def build_live_cumulative_payload(academic_session, class_level, class_arm, mode="manual", result_year="", next_term="", form_teacher="", include_term_reports=False, include_report_documents=True):
    """Compile the live Third-Term annual workspace and its two official report pages per pupil.

    Normal Third Term records remain untouched. The cumulative workspace creates a dedicated Third
    Term decision copy plus a separate true 3-term cumulative copy whose CA/Test/Exam columns are
    annualized from the saved First, Second and Third Term records.
    """
    academic_session = normalize_academic_session(academic_session); level, arm = normalize_report_class(class_level, class_arm); mode = clean(mode or "manual").lower(); mode = mode if mode in {"manual", "auto", "hybrid"} else "manual"; result_year = resolve_result_year(academic_session, result_year, level, arm); roster = get_report_students_for_class(level, arm, active_only=True)
    if mode == "manual":
        shared_store, shared_scope = _read_json_store(MANUAL_FILE), get_report_subject_scope(level, arm); term_payloads = {term: build_manual_report_payload(academic_session, term, level, arm, preloaded_students=roster, preloaded_store=shared_store, preloaded_scope=shared_scope) for term in LIVE_CUMULATIVE_TERMS}
    else: term_payloads = {term: _live_cumulative_term_payload(academic_session, term, level, arm, mode, result_year) for term in LIVE_CUMULATIVE_TERMS}
    term_maps = {term: report_map(payload) for term, payload in term_payloads.items()}; third_payload = term_payloads.get("THIRD") or {}
    if include_report_documents and third_payload.get("reports"): attach_cumulative_results(third_payload, academic_session, level, arm, result_year, mode=mode, first_payload=term_payloads.get("FIRST"), second_payload=term_payloads.get("SECOND"))
    if next_term: apply_requested_next_term(third_payload, next_term)
    if form_teacher:
        third_payload["form_teacher"] = clean(form_teacher)
        for report in third_payload.get("reports", []): report["form_teacher"] = clean(form_teacher)
    students = []
    for student in roster:
        admission = normalize_admission_number(student.get("admission_number")); terms, averages, score_pairs, missing = {}, [], [], []
        for term in LIVE_CUMULATIVE_TERMS:
            report = term_maps.get(term, {}).get(admission); average = optional_float((report or {}).get("average")); score = optional_float((report or {}).get("total_score")); maximum = optional_float((report or {}).get("maximum_score")); available = bool(report and report.get("academic_complete")) and average is not None
            if available: averages.append(average)
            else: missing.append(term)
            if available and score is not None and maximum: score_pairs.append((score, maximum))
            terms[term] = {"available": available, "average": pretty_optional(average), "score": pretty_optional(score), "maximum": pretty_optional(maximum), "grade": clean((report or {}).get("grade") or "-"), "position": int(safe_float((report or {}).get("position"), 0)), "position_text": clean((report or {}).get("position_text") or "--"), "out_of": int(safe_float((report or {}).get("out_of"), 0)), "academic_complete": bool((report or {}).get("academic_complete")), "source_mode": clean((report or {}).get("source_mode") or mode), "manual_status": clean((report or {}).get("manual_status"))}
        annual_average = round(sum(averages) / len(averages), 2) if averages else None; annual_score = round(sum(item[0] for item in score_pairs), 2) if score_pairs else None; annual_max = round(sum(item[1] for item in score_pairs), 2) if score_pairs else None; annual_score_percentage = round(annual_score / annual_max * 100, 2) if annual_score is not None and annual_max else None; grade, comment = grade_for_score(annual_average, level) if annual_average is not None else ("-", "Pending"); complete = len(averages) == 3; promotion_status, promotion_note = cumulative_promotion_decision(annual_average, complete, level)
        students.append({"profile": {"admission_number": clean(student.get("admission_number")), "full_name": clean(student.get("full_name")), "sex": clean(student.get("sex")), "class_level": level, "class_arm": arm, "class_display": arm or level}, "terms": terms, "annual_score": pretty_optional(annual_score), "annual_max": pretty_optional(annual_max), "annual_score_percentage": pretty_optional(annual_score_percentage), "annual_average": pretty_optional(annual_average), "annual_grade": grade, "annual_comment": comment, "terms_available": len(averages), "complete": complete, "cumulative_ready": complete, "missing_terms": missing, "generation_blockers": [f"{term.title()} Term result missing" for term in missing], "required_terms": list(LIVE_CUMULATIVE_TERMS), "annual_position": 0, "annual_position_text": "--", "annual_out_of": 0, "promotion_status": promotion_status, "promotion_note": promotion_note, "third_report_ready": bool((term_maps.get("THIRD", {}).get(admission) or {}).get("academic_complete"))})
    complete_students = [item for item in students if item.get("complete") and optional_float(item.get("annual_average")) is not None]; complete_scores = [optional_float(item.get("annual_average")) for item in complete_students]; provisional_scores = [optional_float(item.get("annual_average")) for item in students if optional_float(item.get("annual_average")) is not None]
    for item in students:
        average = optional_float(item.get("annual_average")); item["provisional_position"] = compute_position(average, provisional_scores) if average is not None and provisional_scores else 0; item["provisional_position_text"] = ordinal(item["provisional_position"]) if item["provisional_position"] else "--"
        if not item.get("complete") or average is None: continue
        position = compute_position(average, complete_scores); item["annual_position"], item["annual_position_text"], item["annual_out_of"] = position, ordinal(position), len(complete_students)
    term_counts = {term: sum(1 for item in students if bool((item.get("terms") or {}).get(term, {}).get("available"))) for term in LIVE_CUMULATIVE_TERMS}; roster_count = len(students); slots_complete = sum(term_counts.values()); data_coverage = round(slots_complete / (roster_count * 3) * 100, 2) if roster_count else 0; complete_count = len(complete_students); official_ready = bool(roster_count) and complete_count == roster_count and all(term_counts.get(term) == roster_count for term in LIVE_CUMULATIVE_TERMS); class_average = round(sum(complete_scores) / len(complete_scores), 2) if complete_scores else None; provisional_class_average = round(sum(provisional_scores) / len(provisional_scores), 2) if provisional_scores else None; reports = list(third_payload.get("reports") or []) if include_report_documents else []; student_map = {normalize_admission_number((item.get("profile") or {}).get("admission_number")): item for item in students}
    third_decision_reports, cumulative_reports = [], []
    if include_report_documents:
        for report in reports:
            admission = normalize_admission_number(report.get("admission_number")); item = student_map.get(admission) or {}; first_report, second_report = term_maps.get("FIRST", {}).get(admission), term_maps.get("SECOND", {}).get(admission)
            if not report.get("academic_complete") or not item.get("complete"): continue
            decision, note = clean(item.get("promotion_status") or "PENDING"), clean(item.get("promotion_note")); third_copy = copy.deepcopy(report); third_copy.update({"report_variant":"third_term_decision","is_cumulative_report":False,"show_promotion_decision":True,"promotion_status":decision,"promotion_note":note}); third_decision_reports.append(third_copy)
            annual_copy = build_true_cumulative_report(report, first_report, second_report, level, decision, note); annual_copy.update({"cumulative_position":item.get("annual_position"),"cumulative_position_text":item.get("annual_position_text"),"cumulative_out_of":item.get("annual_out_of")}); cumulative_reports.append(annual_copy)
        finalize_true_cumulative_subject_statistics(cumulative_reports)
    incomplete_terms = [f"{term.title()} Term {term_counts.get(term, 0)}/{roster_count}" for term in LIVE_CUMULATIVE_TERMS if term_counts.get(term, 0) < roster_count]; guard_message = "All active students have complete First, Second and Third Term records. Each pupil now has two official pages: Third Term + Promotion Decision and a separate 3-Term Cumulative Report." if official_ready else f"Official cumulative PDF is locked: {' • '.join(incomplete_terms) if incomplete_terms else '3-term coverage is incomplete'}. Each pupil must have complete First Term, Second Term and Third Term Report Sheet records before the two-page annual result becomes official. Current 3/3 readiness: {complete_count}/{roster_count}."
    generation_gate = {"required_terms": list(LIVE_CUMULATIVE_TERMS), "first_ready": bool(roster_count) and term_counts.get("FIRST") == roster_count, "second_ready": bool(roster_count) and term_counts.get("SECOND") == roster_count, "third_ready": bool(roster_count) and term_counts.get("THIRD") == roster_count, "official_ready": official_ready, "message": guard_message}
    payload = {"success": True, "session": academic_session, "term": "THIRD", "class_level": level, "class_arm": arm, "source_mode": mode, "count": roster_count, "students": students, "term_counts": term_counts, "complete_students": complete_count, "partial_students": max(0, roster_count - complete_count), "coverage_percentage": round(complete_count / roster_count * 100, 2) if roster_count else 0, "data_coverage_percentage": data_coverage, "class_average": pretty_optional(class_average), "provisional_class_average": pretty_optional(provisional_class_average), "official_ready": official_ready, "print_ready_count": complete_count if official_ready else 0, "official_page_count": complete_count * 2 if official_ready else 0, "report_documents_ready": bool(include_report_documents), "third_term_reports": reports, "third_term_decision_reports": third_decision_reports, "cumulative_reports": cumulative_reports, "official_third_term_reports": third_decision_reports if official_ready else [], "official_cumulative_reports": cumulative_reports if official_ready else [], "official_reports": cumulative_reports if official_ready else [], "next_term": next_term, "form_teacher": clean(form_teacher), "synced_at": now_string(), "generation_gate": generation_gate, "integrity_guard": {"ready": official_ready, "message": guard_message, "roster_count": roster_count, "term_counts": term_counts, "complete_students": complete_count, "data_slots_complete": slots_complete, "data_slots_total": roster_count * 3}, "calculation_method": "equal_term_component_and_percentage_average", "calculation_note": "Cumulative CA/Test/Exam cells are the mean of the same saved component across 1st + 2nd + 3rd Term. Each subject Annual Average is (1st total + 2nd total + 3rd total) ÷ 3. Overall Annual Avg. gives the three term percentages equal weight.", "source_summary": {term: (term_payloads.get(term, {}).get("summary") or {}) for term in LIVE_CUMULATIVE_TERMS}}
    if include_term_reports: payload["term_reports"] = {term: list((term_payloads.get(term) or {}).get("reports") or []) for term in LIVE_CUMULATIVE_TERMS}
    return payload


@report_sheet_bp.route("/api/report-sheets/cumulative/roster")
@report_staff_required
def api_report_cumulative_roster():
    denied = official_generation_denied()
    if denied: return denied
    class_level, class_arm = request_class_values(request.args); level, arm, error = resolve_class(class_level, class_arm, require_arm=True)
    if error: return jsonify({"success": False, "message": error, "students": []}), 400
    academic_session = normalize_academic_session(request.args.get("session")); next_term, next_term_error = next_term_required_response(request.args.get("next_term"))
    if not academic_session: return jsonify({"success": False, "message": "Select an academic session before loading Third Term cumulative students.", "students": []}), 400
    if next_term_error: return next_term_error
    students = get_report_students_for_class(level, arm, active_only=True)
    return jsonify({"success": True, "session": academic_session, "term": "THIRD", "class_level": level, "class_arm": arm, "next_term": next_term, "students": students, "count": len(students)})


@report_sheet_bp.route("/api/report-sheets/cumulative/live", methods=["POST"])
@report_staff_required
def api_report_cumulative_live():
    denied = official_generation_denied()
    if denied: return denied
    data = request.get_json(silent=True) or {}; class_level, class_arm = request_class_values(data); level, arm, error = resolve_class(class_level, class_arm, require_arm=True)
    if error: return jsonify({"success": False, "message": error}), 400
    academic_session = normalize_academic_session(data.get("session")); next_term, next_term_error = next_term_required_response(data.get("next_term")); mode = clean(data.get("mode") or "manual").lower()
    if not academic_session: return jsonify({"success": False, "message": "Select an academic session before loading Third Term cumulative results."}), 400
    if next_term_error: return next_term_error
    if mode not in {"manual", "auto", "hybrid"}: return jsonify({"success": False, "message": "Cumulative source mode must be manual, auto or hybrid."}), 400
    defaults = save_report_defaults(academic_session, "THIRD", level, arm, {"form_teacher": data.get("form_teacher"), "next_term": next_term}); payload = build_live_cumulative_payload(academic_session, level, arm, mode=mode, result_year=data.get("year"), next_term=next_term, form_teacher=defaults.get("form_teacher"), include_term_reports=False, include_report_documents=False); payload["defaults"] = defaults
    return jsonify(payload)


@report_sheet_bp.route("/api/report-sheets/cumulative/details", methods=["POST"])
@report_staff_required
def api_report_cumulative_details():
    denied = official_generation_denied()
    if denied: return denied
    data = request.get_json(silent=True) or {}; class_level, class_arm = request_class_values(data); level, arm, error = resolve_class(class_level, class_arm, require_arm=True)
    if error: return jsonify({"success": False, "message": error}), 400
    academic_session = normalize_academic_session(data.get("session")); next_term, next_term_error = next_term_required_response(data.get("next_term")); mode = clean(data.get("mode") or "manual").lower()
    if not academic_session: return jsonify({"success": False, "message": "Select an academic session before loading cumulative report details."}), 400
    if next_term_error: return next_term_error
    if mode not in {"manual", "auto", "hybrid"}: return jsonify({"success": False, "message": "Cumulative source mode must be manual, auto or hybrid."}), 400
    defaults = get_report_defaults(academic_session, "THIRD", level, arm); payload = build_live_cumulative_payload(academic_session, level, arm, mode=mode, result_year=data.get("year"), next_term=next_term, form_teacher=clean(data.get("form_teacher") or defaults.get("form_teacher")), include_term_reports=True, include_report_documents=True)
    archived = []
    if payload.get("official_ready"):
        archive_batch=[]
        for report in list(payload.get("third_term_decision_reports") or []):
            item=dict(report); item["report_variant"]="third_term_decision"; item["document_label"]="Third Term Final Result"; archive_batch.append(item)
        for report in list(payload.get("cumulative_reports") or []):
            item=dict(report); item["report_variant"]="cumulative"; item["is_cumulative_report"]=True; item["document_label"]="Annual Cumulative Report"; archive_batch.append(item)
        if archive_batch: archived=save_report_snapshots(archive_batch, generated_by=_admin_delete_actor())
    keys = ("term_reports", "third_term_reports", "third_term_decision_reports", "cumulative_reports", "official_third_term_reports", "official_cumulative_reports", "official_reports", "report_documents_ready", "print_ready_count", "official_page_count", "synced_at")
    return jsonify({"success": True, **{key: payload.get(key) for key in keys}, "history_archived":len(archived), "history_auto_saved":bool(archived)})


# ============================================================
# CENTRAL ADMIN — DESTRUCTIVE REPORT ARCHIVE CONTROL
# ============================================================

@report_sheet_bp.route("/api/report-sheets/admin-delete", methods=["POST"])
@report_staff_required
def api_report_admin_delete():
    denied=central_admin_required_response()
    if denied: return denied
    data=request.get_json(silent=True) or {}; action=clean(data.get("action")).lower(); confirmation=clean(data.get("confirmation"))
    if confirmation != "DELETE": return jsonify({"success":False,"message":"Type DELETE in capital letters to unlock this destructive action."}),400
    if action not in {"term_class","class_history","database"}: return jsonify({"success":False,"message":"Choose a valid Admin Delete action."}),400
    academic_session=normalize_academic_session(data.get("session")); term=normalize_academic_term(data.get("term")); level,arm=normalize_report_class(data.get("class_level"),data.get("class_arm"))
    if action == "database":
        expected_user,expected_password=os.getenv("ADMIN_USERNAME","").strip(),os.getenv("ADMIN_PASSWORD","").strip(); supplied_user,supplied_password=clean(data.get("admin_username")),str(data.get("admin_password") or "")
        if not expected_user or not expected_password: return jsonify({"success":False,"message":"ADMIN_USERNAME / ADMIN_PASSWORD are not configured in the server environment. Database deletion is locked."}),503
        if supplied_user != expected_user or supplied_password != expected_password: return jsonify({"success":False,"message":"Administrator credentials are incorrect. Nothing was deleted."}),403
        counts=delete_report_sheet_scope(delete_all=True); scope={"all_report_sheet_data":True}
    else:
        if not level or not arm: return jsonify({"success":False,"message":"Select the exact class and arm before deleting class Report Sheet data."}),400
        if action == "term_class":
            if not academic_session or not term: return jsonify({"success":False,"message":"Select session and term before deleting this class term."}),400
            counts=delete_report_sheet_scope(academic_session,term,level,arm,False); scope={"session":academic_session,"term":term,"class_level":level,"class_arm":arm}
        else:
            counts=delete_report_sheet_scope(class_level=level,class_arm=arm,delete_all=False); scope={"class_level":level,"class_arm":arm,"all_sessions_terms":True}
    audit=_write_admin_delete_audit(action,scope,counts); total=sum(value for value in counts.values() if isinstance(value,int)); queue_emis_event_safely("report_sheets","admin_delete",{"audit":audit},entity_key=f"admin_delete|{audit['audit_id']}")
    return jsonify({"success":True,"message":f"Admin Delete completed. {total} stored report/history item(s) were removed.","counts":counts,"scope":scope,"audit_id":audit.get("audit_id")})

# ============================================================
# THIRD TERM CUMULATIVE — VERIFICATION / TERM EXCEL EXPORTS
# ============================================================

_CUM_XLS = {"navy":"173F62","first":"EAF3FD","second":"EAF8F5","third":"FFF5E3","annual":"EAF8F0","line":"D8E5EF","text":"16344D","muted":"64798B","white":"FFFFFF","warn":"FFF4D8","green":"0F766E"}
_CUM_TERM_META = {"FIRST":("First Term","4F81BD","F5F9FE"),"SECOND":("Second Term","2E8B78","F4FBF9"),"THIRD":("Third Term","C88A2B","FFFAF1")}

def _cum_xls_score(term):
    term = term if isinstance(term, dict) else {}; score, maximum = optional_float(term.get("score")), optional_float(term.get("maximum")); return f"{pretty_number(score)} / {pretty_number(maximum)}" if score is not None and maximum is not None else ""

def _cum_xls_grade_style(cell, grade):
    fills = {"A":"E7F7EF","B":"EAF3FD","C":"EAF8F5","D":"FFF4D8","E":"FBEEDC","F":"FCE8E8"}; grade = clean_upper(grade); cell.font = Font(name="Aptos", size=10, bold=True, color="17324A"); cell.alignment = Alignment(horizontal="center", vertical="center"); cell.fill = PatternFill("solid", fgColor=fills.get(grade, "F5F8FA"))

def _cum_xls_finish_sheet(sheet, freeze="A2", filter_row=1, max_width=34):
    thin = Side(style="thin", color=_CUM_XLS["line"]); sheet.freeze_panes = freeze; sheet.sheet_view.showGridLines = False
    if sheet.max_row >= filter_row and sheet.max_column: sheet.auto_filter.ref = f"A{filter_row}:{get_column_letter(sheet.max_column)}{sheet.max_row}"
    for row in sheet.iter_rows():
        for cell in row: cell.border = Border(left=thin, right=thin, top=thin, bottom=thin); cell.alignment = Alignment(vertical="center", wrap_text=True)
    for column in range(1, sheet.max_column + 1):
        letter = get_column_letter(column); width = max(9, min(max_width, max(len(str(sheet.cell(row=row, column=column).value or "")) for row in range(1, sheet.max_row + 1)) + 2)); sheet.column_dimensions[letter].width = width

def _cum_xls_selected_students(payload, selected_admissions=None):
    selected = {normalize_admission_number(value) for value in (selected_admissions or []) if normalize_admission_number(value)}; students = [student for student in (payload.get("students") or []) if not selected or normalize_admission_number((student.get("profile") or {}).get("admission_number")) in selected]; return selected, students

def _cum_xls_term_reports(payload, term):
    reports = payload.get("term_reports") if isinstance(payload.get("term_reports"), dict) else {}; return list(reports.get(term) or [])

def _cum_xls_report_map(payload, term): return {normalize_admission_number(report.get("admission_number")): report for report in _cum_xls_term_reports(payload, term) if normalize_admission_number(report.get("admission_number"))}
def _cum_xls_subject_key(row): return clean_upper((row or {}).get("subject_key") or (row or {}).get("subject"))
def _cum_xls_subject_map(report): return {_cum_xls_subject_key(row): row for row in ((report or {}).get("subjects") or []) if _cum_xls_subject_key(row)}

def _cum_xls_title(sheet, title, subtitle, last_col, accent):
    last = get_column_letter(max(1,last_col)); sheet.merge_cells(f"A1:{last}1"); sheet["A1"] = title; sheet["A1"].font = Font(name="Aptos Display", size=14, bold=True, color=_CUM_XLS["white"]); sheet["A1"].fill = PatternFill("solid", fgColor=accent); sheet["A1"].alignment = Alignment(horizontal="left", vertical="center"); sheet.row_dimensions[1].height = 28
    sheet.merge_cells(f"A2:{last}2"); sheet["A2"] = subtitle; sheet["A2"].font = Font(name="Aptos", size=9, bold=True, color=_CUM_XLS["muted"]); sheet["A2"].fill = PatternFill("solid", fgColor="F7FAFC"); sheet["A2"].alignment = Alignment(vertical="center", wrap_text=True); sheet.row_dimensions[2].height = 28

def _cum_xls_header(sheet, row_number, headers, accent):
    sheet.append(headers) if sheet.max_row < row_number else None
    for cell in sheet[row_number]: cell.fill = PatternFill("solid", fgColor=accent); cell.font = Font(name="Aptos", size=9, bold=True, color=_CUM_XLS["white"]); cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    sheet.row_dimensions[row_number].height = 30

def _cum_add_term_class_sheet(workbook, payload, term, students):
    label, accent, soft = _CUM_TERM_META[term]; reports = _cum_xls_term_reports(payload, term); report_by_admission = _cum_xls_report_map(payload, term); subject_catalog = []
    for report in reports:
        for row in report.get("subjects") or []:
            key = _cum_xls_subject_key(row); name = clean(row.get("subject") or row.get("subject_key"));
            if key and all(item[0] != key for item in subject_catalog): subject_catalog.append((key,name))
    headers = ["S/N","Student","Admission","Sex"] + [name for _,name in subject_catalog] + ["Term Score","Maximum","Average %","Grade","Position","Status"]; sheet = workbook.create_sheet(f"{label} Class"); sheet.sheet_properties.tabColor = accent; _cum_xls_title(sheet, f"{label} Class Verification", f"{payload.get('class_arm') or payload.get('class_level')} • {payload.get('session')} • Saved {label} totals. Every subject value below comes directly from that term report record.", len(headers), accent); sheet.append([]); sheet.append(headers); _cum_xls_header(sheet,4,headers,accent)
    for index, student in enumerate(students,1):
        profile = student.get("profile") or {}; admission = normalize_admission_number(profile.get("admission_number")); report = report_by_admission.get(admission) or {}; subjects = _cum_xls_subject_map(report); total = optional_float(report.get("total_score")); maximum = optional_float(report.get("maximum_score")); maximum = maximum if maximum is not None else (len(report.get("subjects") or []) * 100 if report else None); average = optional_float(report.get("average")); grade = clean(report.get("grade") or "-"); position = f"{clean(report.get('position_text') or '--')} / {report.get('out_of') or '--'}" if report else "--"; values = [index,clean(profile.get("full_name")),clean(profile.get("admission_number")),clean(profile.get("sex"))] + [optional_float((subjects.get(key) or {}).get("total")) for key,_ in subject_catalog] + [total,maximum,average,grade,position,"Complete" if report.get("academic_complete") else "Pending"]
        sheet.append(values); row = sheet.max_row
        for column in range(5,5+len(subject_catalog)): sheet.cell(row,column).fill = PatternFill("solid",fgColor=soft); sheet.cell(row,column).alignment = Alignment(horizontal="center",vertical="center")
        avg_col = 7 + len(subject_catalog); grade_col = avg_col + 1; sheet.cell(row,avg_col).number_format = "0.00"; sheet.cell(row,avg_col).font = Font(name="Aptos",size=10,bold=True,color=_CUM_XLS["green"]); _cum_xls_grade_style(sheet.cell(row,grade_col),grade)
    _cum_xls_finish_sheet(sheet,freeze="E5",filter_row=4,max_width=28); sheet.column_dimensions["B"].width = 28; sheet.column_dimensions["C"].width = 15; return sheet

def _cum_add_term_entries_sheet(workbook, payload, term, students):
    label, accent, soft = _CUM_TERM_META[term]; wanted = {normalize_admission_number((student.get("profile") or {}).get("admission_number")) for student in students}; headers = ["S/N","Student","Admission","Subject","CA1","CA2","TEST1","TEST2","ASS1","ASS2","TEST","CA Total","Exam","Total","Grade","Subject Pos.","Out Of"]; sheet = workbook.create_sheet(f"{label} Entries"); sheet.sheet_properties.tabColor = accent; _cum_xls_title(sheet,f"{label} Assessment Entries",f"Full saved assessment breakdown for {payload.get('class_arm') or payload.get('class_level')} • use this sheet to verify exactly how each {label} subject total was formed.",len(headers),accent); sheet.append([]); sheet.append(headers); _cum_xls_header(sheet,4,headers,accent); row_no = 0
    for report in _cum_xls_term_reports(payload,term):
        admission = normalize_admission_number(report.get("admission_number"));
        if admission not in wanted: continue
        for subject in report.get("subjects") or []:
            row_no += 1; sheet.append([row_no,clean(report.get("full_name")),clean(report.get("admission_number")),clean(subject.get("subject")),subject.get("ca1"),subject.get("ca2"),subject.get("test1"),subject.get("test2"),subject.get("ass1"),subject.get("ass2"),subject.get("test"),subject.get("ca_total"),subject.get("exam"),subject.get("total"),clean(subject.get("grade")),clean(subject.get("position_text")),subject.get("out_of")]); row = sheet.max_row
            for col in range(5,15): sheet.cell(row,col).fill = PatternFill("solid",fgColor=soft)
            sheet.cell(row,14).font = Font(name="Aptos",size=9,bold=True,color=_CUM_XLS["green"]); _cum_xls_grade_style(sheet.cell(row,15),sheet.cell(row,15).value)
    _cum_xls_finish_sheet(sheet,freeze="E5",filter_row=4,max_width=28); sheet.column_dimensions["B"].width = 28; sheet.column_dimensions["D"].width = 24; return sheet

def _cum_add_annual_register_sheet(workbook, payload, students):
    register = workbook.create_sheet("Annual Register"); register.sheet_properties.tabColor = "17977A"; groups = [("A1:D1","STUDENT IDENTITY",_CUM_XLS["navy"]),("E1:G1","FIRST TERM",_CUM_XLS["first"]),("H1:J1","SECOND TERM",_CUM_XLS["second"]),("K1:M1","THIRD TERM",_CUM_XLS["third"]),("N1:T1","CUMULATIVE / ANNUAL",_CUM_XLS["annual"])]
    for span,label,color in groups:
        register.merge_cells(span); cell = register[span.split(":")[0]]; cell.value = label; cell.font = Font(name="Aptos Display", size=11, bold=True, color=_CUM_XLS["white"] if color == _CUM_XLS["navy"] else _CUM_XLS["text"]); cell.fill = PatternFill("solid", fgColor=color); cell.alignment = Alignment(horizontal="center", vertical="center")
    headers = ["S/N","Student","Admission","Sex","First Score","First Avg. %","First Grade","Second Score","Second Avg. %","Second Grade","Third Score","Third Avg. %","Third Grade","Combined Raw Score","Combined Raw %","Annual Avg. %","Annual Grade","Position","Progress","Status"]; register.append(headers)
    for cell in register[2]: cell.font = Font(name="Aptos", size=9, bold=True, color=_CUM_XLS["white"]); cell.fill = PatternFill("solid", fgColor=_CUM_XLS["navy"]); cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for index, student in enumerate(students,1):
        profile, terms = student.get("profile") or {}, student.get("terms") or {}; complete = bool(student.get("complete")); raw_score, raw_max, raw_pct, annual_avg = optional_float(student.get("annual_score")), optional_float(student.get("annual_max")), optional_float(student.get("annual_score_percentage")), optional_float(student.get("annual_average")); position = f"{student.get('annual_position_text') or '--'} / {student.get('annual_out_of') or '--'}" if complete and payload.get("official_ready") else "Pending"; status = "Official Ready" if complete and payload.get("official_ready") else "3/3 • Class Pending" if complete else "Incomplete"
        register.append([index,clean(profile.get("full_name")),clean(profile.get("admission_number")),clean(profile.get("sex")),_cum_xls_score(terms.get("FIRST")),optional_float((terms.get("FIRST") or {}).get("average")),clean((terms.get("FIRST") or {}).get("grade")),_cum_xls_score(terms.get("SECOND")),optional_float((terms.get("SECOND") or {}).get("average")),clean((terms.get("SECOND") or {}).get("grade")),_cum_xls_score(terms.get("THIRD")),optional_float((terms.get("THIRD") or {}).get("average")),clean((terms.get("THIRD") or {}).get("grade")),f"{pretty_number(raw_score)} / {pretty_number(raw_max)}" if raw_score is not None and raw_max is not None else "",raw_pct,annual_avg,clean(student.get("annual_grade")),position,f"{int(student.get('terms_available') or 0)}/3",status]); row = register.max_row
        for col in (6,9,12,15,16):
            if isinstance(register.cell(row=row,column=col).value,(int,float)): register.cell(row=row,column=col).number_format = "0.00"
        for cols,color in [((5,6),"F5F9FE"),((8,9),"F4FBF9"),((11,12),"FFFAF1"),((14,15,16,18,19),"F1FAF5")]:
            for col in cols: register.cell(row=row,column=col).fill = PatternFill("solid",fgColor=color)
        for col in (7,10,13,17): _cum_xls_grade_style(register.cell(row=row,column=col),register.cell(row=row,column=col).value)
        register.cell(row=row,column=16).font = Font(name="Aptos",size=10,bold=True,color="087052"); register.cell(row=row,column=20).fill = PatternFill("solid",fgColor="E7F7EF" if status == "Official Ready" else "FFF4D8")
    note_row = register.max_row + 2; register.merge_cells(start_row=note_row,start_column=1,end_row=note_row,end_column=20); register.cell(note_row,1).value = "VERIFICATION RULE: Annual Avg. = (First Term % + Second Term % + Third Term %) ÷ 3. Combined Raw % is shown separately because term subject totals can differ."; register.cell(note_row,1).font = Font(name="Aptos",size=9,bold=True,color="7A5B13"); register.cell(note_row,1).fill = PatternFill("solid",fgColor=_CUM_XLS["warn"]); register.cell(note_row,1).alignment = Alignment(wrap_text=True,vertical="center"); register.row_dimensions[note_row].height = 30; register.freeze_panes = "E3"; register.auto_filter.ref = f"A2:T{max(2,note_row-2)}"; register.sheet_view.showGridLines = False
    thin = Side(style="thin",color=_CUM_XLS["line"])
    for row in register.iter_rows(min_row=1,max_row=max(2,note_row-2),min_col=1,max_col=20):
        for cell in row: cell.border = Border(left=thin,right=thin,top=thin,bottom=thin); cell.alignment = Alignment(vertical="center",wrap_text=True,horizontal="center" if cell.column not in (2,3) else "left")
    for column in range(1,21): register.column_dimensions[get_column_letter(column)].width = {1:7,2:28,3:14,4:8,5:15,6:12,7:11,8:15,9:12,10:11,11:15,12:12,13:11,14:18,15:15,16:14,17:13,18:14,19:11,20:18}.get(column,12)
    register.row_dimensions[1].height = 25; register.row_dimensions[2].height = 30; return register

def _cum_add_subject_comparison_sheet(workbook, payload, students):
    sheet = workbook.create_sheet("3-Term Subject Compare"); sheet.sheet_properties.tabColor = "70AD47"; headers = ["S/N","Student","Admission","Subject","First Term","Second Term","Third Term","3-Term Total","Annual Subject Avg. %","Grade","Verification / Calculation Proof"]; _cum_xls_title(sheet,"First + Second + Third Term Subject Verification",f"{payload.get('class_arm') or payload.get('class_level')} • Each row exposes the saved term scores and the exact arithmetic used for the cumulative subject average.",len(headers),_CUM_XLS["green"]); sheet.append([]); sheet.append(headers); _cum_xls_header(sheet,4,headers,_CUM_XLS["green"]); maps = {term:_cum_xls_report_map(payload,term) for term in LIVE_CUMULATIVE_TERMS}; row_no = 0
    for student in students:
        profile = student.get("profile") or {}; admission = normalize_admission_number(profile.get("admission_number")); subject_maps = {term:_cum_xls_subject_map(maps[term].get(admission)) for term in LIVE_CUMULATIVE_TERMS}; ordered = []
        for term in LIVE_CUMULATIVE_TERMS:
            for key,row in subject_maps[term].items():
                if key and all(item[0] != key for item in ordered): ordered.append((key,clean(row.get("subject") or row.get("subject_key"))))
        for key,name in ordered:
            values = [optional_float((subject_maps[term].get(key) or {}).get("total")) for term in LIVE_CUMULATIVE_TERMS]; available = [value for value in values if value is not None]; total = round(sum(available),2) if available else None; average = round(total / len(available),2) if available else None; grade = grade_for_score(average,payload.get("class_level"))[0] if average is not None else "-"; proof = "Missing term score(s) — cumulative is not official for this subject."
            if len(available) == 3: proof = f"{pretty_number(values[0])} + {pretty_number(values[1])} + {pretty_number(values[2])} = {pretty_number(total)}; {pretty_number(total)} ÷ 3 = {pretty_number(average)}%"
            elif available: proof = f"Available scores: {' + '.join(pretty_number(value) for value in available)} = {pretty_number(total)}; provisional ÷ {len(available)} = {pretty_number(average)}%"
            row_no += 1; sheet.append([row_no,clean(profile.get("full_name")),clean(profile.get("admission_number")),name,values[0],values[1],values[2],total,average,grade,proof]); row = sheet.max_row
            for col,color in ((5,"F5F9FE"),(6,"F4FBF9"),(7,"FFFAF1"),(8,"F1FAF5"),(9,"EAF8F0")): sheet.cell(row,col).fill = PatternFill("solid",fgColor=color)
            sheet.cell(row,9).font = Font(name="Aptos",size=9,bold=True,color="087052"); _cum_xls_grade_style(sheet.cell(row,10),grade); sheet.cell(row,11).font = Font(name="Aptos",size=9,bold=True,color="355E55")
    _cum_xls_finish_sheet(sheet,freeze="E5",filter_row=4,max_width=52); sheet.column_dimensions["B"].width = 28; sheet.column_dimensions["D"].width = 24; sheet.column_dimensions["K"].width = 52; return sheet

def _cum_add_true_cumulative_detail_sheet(workbook, payload, students):
    reports = list(payload.get("cumulative_reports") or payload.get("official_cumulative_reports") or []); wanted = {normalize_admission_number((student.get("profile") or {}).get("admission_number")) for student in students}; score_fields = [key for key in manual_score_fields(payload.get("class_level")) if key != "exam"]; labels = {"ca1":"CA1 /10","ca2":"CA2 /10","test1":"T1 /20","test2":"T2 /20","ass1":"1st Ass.","ass2":"2nd Ass.","test":"Test"}; headers = ["S/N","Student","Admission","Subject"] + [labels.get(key,key.upper()) for key in score_fields] + ["Exam","Total /100","Annual Avg. %","Grade","Position","Out Of","Class Avg. %","1st Term","2nd Term","3rd Term","Terms","Calculation Proof"]; sheet = workbook.create_sheet("Cumulative Report Detail"); sheet.sheet_properties.tabColor = "17977A"; _cum_xls_title(sheet,"True 3-Term Cumulative Report Detail",f"{payload.get('class_arm') or payload.get('class_level')} • CA/Test/Exam cells below are component averages across the saved First + Second + Third Term records. This mirrors the official cumulative report sheet.",len(headers),_CUM_XLS["green"]); sheet.append([]); sheet.append(headers); _cum_xls_header(sheet,4,headers,_CUM_XLS["green"]); row_no = 0
    for report in reports:
        admission = normalize_admission_number(report.get("admission_number"));
        if admission not in wanted: continue
        for subject in report.get("subjects") or []:
            row_no += 1; components = subject.get("cumulative_components") if isinstance(subject.get("cumulative_components"),dict) else {}; values = [optional_float(components.get(key)) for key in score_fields]; sheet.append([row_no,clean(report.get("full_name")),clean(report.get("admission_number")),clean(subject.get("subject")),*values,optional_float(subject.get("cumulative_exam")),optional_float(subject.get("cumulative_total_100")),optional_float(subject.get("cumulative_average")),clean(subject.get("cumulative_grade")),clean(subject.get("cumulative_position_text")),subject.get("cumulative_out_of"),optional_float(subject.get("cumulative_class_average")),optional_float(subject.get("first_term_total")),optional_float(subject.get("second_term_total")),optional_float(subject.get("third_term_total")),f"{int(subject.get('terms_available') or 0)}/3",clean(subject.get("cumulative_proof"))]); row = sheet.max_row
            for col in range(5,5+len(score_fields)+2): sheet.cell(row,col).fill = PatternFill("solid",fgColor="F1FAF5")
            annual_col = 7 + len(score_fields); grade_col = annual_col + 1; sheet.cell(row,annual_col).font = Font(name="Aptos",size=9,bold=True,color="087052"); _cum_xls_grade_style(sheet.cell(row,grade_col),sheet.cell(row,grade_col).value)
    _cum_xls_finish_sheet(sheet,freeze="E5",filter_row=4,max_width=52); sheet.column_dimensions["B"].width = 28; sheet.column_dimensions["D"].width = 24; sheet.column_dimensions[get_column_letter(len(headers))].width = 52; return sheet


def _cum_add_guide_sheet(workbook, payload):
    sheet = workbook.create_sheet("Verification Guide"); sheet.sheet_properties.tabColor = "173F62"; rows = [["EMS CUMULATIVE VERIFICATION GUIDE"],["Purpose","This workbook is designed so a teacher can trace every cumulative figure back to the saved First, Second and Third Term report records."],["Student annual average","(First Term overall % + Second Term overall % + Third Term overall %) ÷ 3. Each term receives equal weight."],["Subject cumulative average","Example: Mathematics 50 + 80 + 70 = 200; 200 ÷ 3 = 66.67%. Cumulative CA/Test/Exam cells are also averaged component-by-component across the three saved terms; Cumulative Report Detail exposes every value."],["Combined raw score","Shown for reference only. It is not used for annual grading when the terms contain different subject totals."],["Verification workflow","1. Open First Term Class / Entries. 2. Check Second Term. 3. Check Third Term. 4. Open 3-Term Subject Compare. 5. Compare the arithmetic with Annual Register."],["Class",clean(payload.get("class_arm") or payload.get("class_level"))],["Session",clean(payload.get("session"))],["Source",clean_upper(payload.get("source_mode"))],["Generated",now_string()]]; sheet.append(rows[0]); sheet.merge_cells("A1:F1"); sheet["A1"].font = Font(name="Aptos Display",size=15,bold=True,color=_CUM_XLS["white"]); sheet["A1"].fill = PatternFill("solid",fgColor=_CUM_XLS["navy"]); sheet["A1"].alignment = Alignment(horizontal="left",vertical="center"); sheet.row_dimensions[1].height = 30
    for label,value in rows[1:]: sheet.append([label,value]); row = sheet.max_row; sheet.cell(row,1).font = Font(name="Aptos",size=10,bold=True,color=_CUM_XLS["text"]); sheet.cell(row,1).fill = PatternFill("solid",fgColor="EAF3FD"); sheet.merge_cells(start_row=row,start_column=2,end_row=row,end_column=6); sheet.cell(row,2).font = Font(name="Aptos",size=10,color="355268"); sheet.cell(row,2).alignment = Alignment(wrap_text=True,vertical="center"); sheet.row_dimensions[row].height = 34 if row <= 6 else 22
    sheet.column_dimensions["A"].width = 28
    for col in range(2,7): sheet.column_dimensions[get_column_letter(col)].width = 20
    sheet.sheet_view.showGridLines = False; return sheet

def build_live_cumulative_workbook(payload, selected_admissions=None, export_view="all"):
    selected, students = _cum_xls_selected_students(payload,selected_admissions); view = clean(export_view or "all").lower(); view = view if view in {"first","second","third","cumulative","compare","all"} else "all"; workbook = Workbook(); workbook.remove(workbook.active)
    if view in {"first","all","compare"}: _cum_add_term_class_sheet(workbook,payload,"FIRST",students)
    if view in {"first","all"}: _cum_add_term_entries_sheet(workbook,payload,"FIRST",students)
    if view in {"second","all","compare"}: _cum_add_term_class_sheet(workbook,payload,"SECOND",students)
    if view in {"second","all"}: _cum_add_term_entries_sheet(workbook,payload,"SECOND",students)
    if view in {"third","all","compare"}: _cum_add_term_class_sheet(workbook,payload,"THIRD",students)
    if view in {"third","all"}: _cum_add_term_entries_sheet(workbook,payload,"THIRD",students)
    if view in {"cumulative","compare","all"}: _cum_add_annual_register_sheet(workbook,payload,students); _cum_add_subject_comparison_sheet(workbook,payload,students); _cum_add_true_cumulative_detail_sheet(workbook,payload,students)
    _cum_add_guide_sheet(workbook,payload); workbook.active = 0; return workbook


@report_sheet_bp.route("/api/report-sheets/cumulative/export/excel")
@report_staff_required
def api_report_cumulative_export_excel():
    denied = official_generation_denied()
    if denied: return denied
    class_level, class_arm = request_class_values(request.args); level, arm, error = resolve_class(class_level, class_arm, require_arm=True)
    if error: return jsonify({"success": False, "message": error}), 400
    academic_session = normalize_academic_session(request.args.get("session")); next_term, next_term_error = next_term_required_response(request.args.get("next_term")); mode = clean(request.args.get("mode") or "manual").lower(); view = clean(request.args.get("view") or "all").lower()
    if not academic_session: return jsonify({"success": False, "message": "Select an academic session before exporting cumulative results."}), 400
    if next_term_error: return next_term_error
    if mode not in {"manual","auto","hybrid"}: return jsonify({"success": False, "message": "Cumulative source mode must be manual, auto or hybrid."}), 400
    if view not in {"first","second","third","cumulative","compare","all"}: return jsonify({"success": False, "message": "Excel view must be First, Second, Third, Cumulative, Compare or All."}), 400
    selected = normalize_admission_selection(request.args.get("admission_numbers") or request.args.get("admissions") or ""); payload = build_live_cumulative_payload(academic_session, level, arm, mode=mode, result_year=request.args.get("year"), next_term=next_term, form_teacher=request.args.get("form_teacher"), include_term_reports=True); workbook = build_live_cumulative_workbook(payload, selected, view); stream = io.BytesIO(); workbook.save(stream); stream.seek(0); scope = "Selected" if selected else "Class"; view_label = {"first":"First_Term","second":"Second_Term","third":"Third_Term","cumulative":"Cumulative","compare":"3_Term_Compare","all":"Full_Verification"}[view]; filename = f"{clean(arm or level).replace(' ','_')}_{academic_session.replace('/','-')}_{view_label}_{scope}.xlsx"
    return send_file(stream, as_attachment=True, download_name=filename, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ============================================================
# API — MANUAL REPORT STUDIO
# ============================================================

@report_sheet_bp.route("/api/report-sheets/manual/cache")
@report_staff_required
def api_report_manual_cache():
    """Tiny class cache used before the slower academic source scan finishes.

    This endpoint never opens CA/Exam workbooks and never rereads the student roster.  It only
    returns saved Manual Workstation drafts plus the class subject scope, so opening/switching
    pupils stays responsive even while Source Status is still resolving academic files.
    """
    class_level, class_arm = request_class_values(); level, arm, error = resolve_class(class_level, class_arm, require_arm=True)
    if error: return jsonify({"success": False, "message": error}), 400
    academic_session, term = resolve_context(request.args.get("session"), request.args.get("term")); denied = teacher_scope_denied(academic_session, level, arm)
    if denied: return denied
    store = _read_json_store(MANUAL_FILE); records = {}
    for value in store.values():
        if not isinstance(value, dict): continue
        if normalize_academic_session(value.get("session")) != academic_session or normalize_academic_term(value.get("term")) != term or value.get("class_level") != level or value.get("class_arm") != arm: continue
        admission = normalize_admission_number(value.get("admission_number"))
        if admission: records[admission] = teacher_visible_manual_record(value, academic_session, level, arm)
    scope = teacher_filtered_subject_scope(get_report_subject_scope(level, arm), academic_session, level, arm); readiness = role_manual_class_readiness(academic_session, term, level, arm)
    return jsonify({"success": True, "session": academic_session, "term": term, "class_level": level, "class_arm": arm, "records": records, "subject_scope": scope, "available_subjects": scope.get("available_subjects", []), "score_fields": manual_score_fields(level), "class_readiness": readiness})


@report_sheet_bp.route("/api/report-sheets/manual", methods=["GET", "POST", "DELETE"])
@report_staff_required
def api_report_manual():
    source = request.get_json(silent=True) or {} if request.method != "GET" else request.args; class_level, class_arm = request_class_values(source); level, arm, error = resolve_class(class_level, class_arm, require_arm=True)
    if error: return jsonify({"success": False, "message": error}), 400
    academic_session, term = resolve_context(source.get("session"), source.get("term")); admission = normalize_admission_number(source.get("admission_number") or source.get("admission")); fast_prefill = clean(source.get("fast_prefill") or source.get("fast")).lower() in {"1", "true", "yes", "on"}
    if not academic_session or not term: return jsonify({"success": False, "message": "Session and term are required."}), 400
    denied = teacher_scope_denied(academic_session, level, arm)
    if denied: return denied
    roster = get_report_students_for_class(level, arm, active_only=True); roster_map = {normalize_admission_number(student.get("admission_number")): student for student in roster}; store = _read_json_store(MANUAL_FILE)
    if request.method == "GET":
        record = store.get(manual_context_key(academic_session, term, level, arm, admission), {}) if admission else {}; record = teacher_visible_manual_record(record, academic_session, level, arm); summaries = {key: manual_record_summary(value) for key, value in store.items() if isinstance(value, dict) and normalize_academic_session(value.get("session")) == academic_session and normalize_academic_term(value.get("term")) == term and value.get("class_level") == level and value.get("class_arm") == arm}
        by_admission = {clean(value.get("admission_number")): manual_record_summary(teacher_visible_manual_record(value, academic_session, level, arm)) for value in store.values() if isinstance(value, dict) and normalize_academic_session(value.get("session")) == academic_session and normalize_academic_term(value.get("term")) == term and value.get("class_level") == level and value.get("class_arm") == arm}
        subject_scope = teacher_filtered_subject_scope(get_report_subject_scope(level, arm), academic_session, level, arm); manual_subjects = list(subject_scope.get("selected_subjects") or [])
        automatic_scores = {}
        # Fast path: Source Status already loaded every CA/Exam workbook for this class and
        # returned a compact browser bootstrap. Do not reopen all subject workbooks again.
        if admission and admission in roster_map and assessment_entry_enabled(level) and not fast_prefill:
            ca_records = get_ca_scores_map(academic_session, term, level, arm).get(admission, {})
            result_year = resolve_result_year(academic_session, source.get("year"), level, arm)
            exam_records, _ = load_exam_results_map(academic_session, term, level, arm, result_year)
            exam_records = exam_records.get(admission, {})
            allowed = expected_subject_map(roster_map.get(admission) or {}, level, arm); teacher_allowed = set(teacher_allowed_report_subjects(report_teacher_id(), academic_session, level, arm)) if report_role() == "teacher" else set()
            for subject_key, subject_name in allowed.items():
                if teacher_allowed and subject_key not in teacher_allowed: continue
                ca = ca_records.get(subject_key) if isinstance(ca_records, dict) else None; exam = exam_records.get(subject_key) if isinstance(exam_records, dict) else None
                values, _ = _assessment_component_values(ca or {}, level); item = {"subject": subject_name, "subject_key": subject_key, **values}
                exam_score = scale_exam_score(exam, level) if isinstance(exam, dict) and exam else None
                if exam_score is not None: item["exam"] = pretty_optional(exam_score)
                if any(value not in (None, "") for key, value in item.items() if key not in {"subject", "subject_key"}): automatic_scores[subject_key] = item
        return jsonify({"success": True, "session": academic_session, "term": term, "class_level": level, "class_arm": arm, "students": [] if fast_prefill else roster, "subjects": manual_subjects, "available_subjects": subject_scope.get("available_subjects", []), "subject_scope": subject_scope, "score_fields": manual_score_fields(level), "automatic_scores": automatic_scores, "automatic_scores_deferred": bool(fast_prefill), "assessment": get_assessment_rule(level), "grading": {"system": grading_system_for_class(level), "ready": grading_system_ready(grading_system_for_class(level))}, "entry_enabled": assessment_entry_enabled(level), "roster_source": report_roster_source(level), "record": record, "record_summaries": by_admission, "class_readiness": role_manual_class_readiness(academic_session, term, level, arm), "count": len(summaries)})
    if request.method == "POST" and not assessment_entry_enabled(level):
        rule = get_assessment_rule(level) or {}; return jsonify({"success": False, "status": "assessment_scheme_pending", "message": rule.get("message") or f"The assessment scheme for {class_label(level)} is not configured yet.", "assessment": rule}), 409
    if not admission or admission not in roster_map: return jsonify({"success": False, "message": "Select a valid active student from this class."}), 400
    key = manual_context_key(academic_session, term, level, arm, admission)
    if request.method == "DELETE":
        if report_role() == "teacher": return jsonify({"success": False, "message": "Teachers cannot delete a shared student record. Edit only your assigned subject scores."}), 403
        if key not in store: return jsonify({"success": False, "message": "No manual record exists for this student."}), 404
        del store[key]; _write_json_store(MANUAL_FILE, store); queue_emis_event_safely("report_sheets", "manual_delete", {"key": key}, entity_key=f"manual|{key}"); return jsonify({"success": True, "message": "Manual student record deleted successfully.", "admission_number": admission, "class_readiness": role_manual_class_readiness(academic_session, term, level, arm)})
    fast_save = bool_request_flag(source.get("fast_save"))
    try: record = save_manual_record(academic_session, term, level, arm, admission, source, student_record=roster_map.get(admission), queue_sync=not fast_save)
    except ValueError as error: return jsonify({"success": False, "message": str(error)}), 400
    if fast_save:
        queue_manual_record_sync_background(key, record)
        return jsonify({"success": True, "message": f"Manual report record saved for {roster_map[admission].get('full_name') or admission}.", "record": record, "summary": manual_record_summary(record), "readiness_deferred": True})
    return jsonify({"success": True, "message": f"Manual report record saved for {roster_map[admission].get('full_name') or admission}.", "record": record, "summary": manual_record_summary(record), "class_readiness": role_manual_class_readiness(academic_session, term, level, arm)})


@report_sheet_bp.route("/api/report-sheets/manual/clear-scores", methods=["POST"])
@report_staff_required
def api_report_manual_clear_scores():
    """Permanently reset Manual Workstation score boxes for one pupil or the loaded class.

    The original CA/Test and Exam source records are deliberately preserved.  A persistent
    suppression flag keeps those automatic values from refilling the Manual boxes after refresh,
    so the teacher can genuinely start the Manual entry again from empty score fields.
    """
    source = request.get_json(silent=True) or {}; class_level, class_arm = request_class_values(source); level, arm, error = resolve_class(class_level, class_arm, require_arm=True)
    if error: return jsonify({"success": False, "message": error}), 400
    academic_session, term = resolve_context(source.get("session"), source.get("term")); scope = clean(source.get("scope") or "student").lower(); roster = get_report_students_for_class(level, arm, active_only=True); roster_map = {normalize_admission_number(student.get("admission_number")): student for student in roster}
    if not academic_session or not term: return jsonify({"success": False, "message": "Session and term are required."}), 400
    denied = teacher_scope_denied(academic_session, level, arm)
    if denied: return denied
    if scope == "class": admissions = list(roster_map.keys())
    else:
        admission = normalize_admission_number(source.get("admission_number") or source.get("admission")); admissions = [admission] if admission and admission in roster_map else []
    if not admissions: return jsonify({"success": False, "message": "No valid student was selected for score clearing."}), 400
    store = _read_json_store(MANUAL_FILE); actor = clean(session.get("admin_username") or session.get("username") or session.get("user") or "Staff"); cleared = []; is_teacher = report_role() == "teacher"; teacher_keys = set(teacher_allowed_report_subjects(report_teacher_id(), academic_session, level, arm)) if is_teacher else set()
    if is_teacher and not teacher_keys: return jsonify({"success": False, "message": "No report subjects are assigned to this Teacher ID for the selected class."}), 403
    for admission in admissions:
        key = manual_context_key(academic_session, term, level, arm, admission); current = store.get(key, {}) if isinstance(store.get(key), dict) else {}
        if is_teacher:
            subjects = dict(current.get("subjects", {})) if isinstance(current.get("subjects"), dict) else {}; removed = False
            for subject_key in list(subjects.keys()):
                if academic_subject_key(subject_key) in teacher_keys: subjects.pop(subject_key, None); removed = True
            item = {**current, "session": normalize_academic_session(academic_session), "term": normalize_academic_term(term), "class_level": level, "class_arm": arm, "admission_number": clean((roster_map.get(admission) or {}).get("admission_number") or admission), "subjects": subjects, "status": "DRAFT", "updated_at": now_string(), "updated_by": actor}
            if removed or current: store[key] = item
        else:
            item = {
                "session": normalize_academic_session(academic_session), "term": normalize_academic_term(term), "class_level": level, "class_arm": arm, "admission_number": clean((roster_map.get(admission) or {}).get("admission_number") or admission),
                "subjects": {}, "attendance": current.get("attendance", {}) if isinstance(current.get("attendance"), dict) else {}, "attendance_user_set": bool(current.get("attendance_user_set", False)), "attendance_override_enabled": bool(current.get("attendance_override_enabled", False)),
                "prefer_manual_scores": bool(current.get("prefer_manual_scores", False)), "suppress_automatic_scores": True, "status": "DRAFT", "teacher_note": clean(current.get("teacher_note", "")),
                "excluded_from_class_report": bool(current.get("excluded_from_class_report", False)), "exclusion_reason": clean(current.get("exclusion_reason", "")), "updated_at": now_string(), "updated_by": actor,
            }; store[key] = item
        cleared.append(admission)
    _write_json_store(MANUAL_FILE, store)
    for admission in cleared:
        key = manual_context_key(academic_session, term, level, arm, admission); queue_emis_event_safely("report_sheets", "manual_upsert", {"key": key, "item": store.get(key, {})}, entity_key=f"manual|{key}")
    readiness = role_manual_class_readiness(academic_session, term, level, arm); label = f"{len(cleared)} student{'s' if len(cleared) != 1 else ''}" if scope == "class" else clean((roster_map.get(cleared[0]) or {}).get("full_name") or cleared[0]); message = f"Your assigned subject score entries were cleared for {label}. Other teachers' saved subjects were preserved." if is_teacher else f"Manual score entries cleared for {label}. Score boxes will stay empty until new Manual scores are entered and saved."
    return jsonify({"success": True, "message": message, "scope": scope, "cleared_count": len(cleared), "admission_numbers": cleared, "record": teacher_visible_manual_record(store.get(manual_context_key(academic_session, term, level, arm, cleared[0]), {}), academic_session, level, arm) if scope != "class" else {}, "class_readiness": readiness})


@report_sheet_bp.route("/api/report-sheets/manual/subjects", methods=["GET", "POST"])
@report_staff_required
def api_report_manual_subjects():
    source = request.get_json(silent=True) or {} if request.method == "POST" else request.args; class_level, class_arm = request_class_values(source); level, arm, error = resolve_class(class_level, class_arm, require_arm=True)
    if error: return jsonify({"success": False, "message": error}), 400
    academic_session, term = resolve_context(source.get("session"), source.get("term"))
    denied = teacher_scope_denied(academic_session, level, arm)
    if denied: return denied
    if request.method == "GET": return jsonify({"success": True, "subject_scope": teacher_filtered_subject_scope(get_report_subject_scope(level, arm), academic_session, level, arm)})
    if report_role() == "teacher": return jsonify({"success": False, "message": "Teachers cannot change the class subject scope. Your subjects are controlled by Academic Admin."}), 403
    action = clean(source.get("action") or "save").lower()
    if action == "add":
        name = clean(source.get("name"))
        if not name: return jsonify({"success": False, "message": "Enter the subject name first."}), 400
        try:
            row = add_registered_subject(level, name, source="report_sheets")
            try:
                sync_payload = build_subject_sync_payload((row or {}).get("subject_key") or academic_subject_key(name)); queue_emis_event_safely("subject_registry", "upsert_subject", sync_payload, entity_key=clean((sync_payload.get("subject") or {}).get("id") or academic_subject_key(name)))
            except Exception as sync_error: print("[REPORT SUBJECTS] Subject sync queue warning:", sync_error)
            current = get_report_subject_scope(level, arm)
            if current.get("customized"):
                keys = list(current.get("selected_keys") or []); new_key = academic_subject_key(name)
                if new_key and new_key not in keys: keys.append(new_key)
                current = save_report_subject_scope(level, arm, keys, current.get("include_islamiyah", True))
            else: current = get_report_subject_scope(level, arm)
            return jsonify({"success": True, "message": f"{normalize_academic_subject(name)} added to {class_label(level)} and included in Report Sheets.", "subject": row, "subject_scope": current, "class_readiness": role_manual_class_readiness(academic_session, term, level, arm)})
        except ValueError as error: return jsonify({"success": False, "message": str(error)}), 400
    if action == "reset":
        scope_key = report_subject_scope_key(level, arm); store = _read_json_store(REPORT_SUBJECT_SCOPE_FILE); store.pop(scope_key, None); _write_json_store(REPORT_SUBJECT_SCOPE_FILE, store); queue_emis_event_safely("report_sheets", "subject_scope_delete", {"key": scope_key}, entity_key=f"report-subject-scope|{scope_key}"); scope = get_report_subject_scope(level, arm); return jsonify({"success": True, "message": "Report subject selection reset to the full configured class curriculum.", "subject_scope": scope, "class_readiness": role_manual_class_readiness(academic_session, term, level, arm)})
    try: scope = save_report_subject_scope(level, arm, source.get("subject_keys") or [], bool(source.get("include_islamiyah", True)))
    except ValueError as error: return jsonify({"success": False, "message": str(error)}), 400
    return jsonify({"success": True, "message": f"Report subject selection saved — {len(scope.get('selected_keys') or [])} regular subject(s){' + Islamiyyah' if scope.get('include_islamiyah') else ''}.", "subject_scope": scope, "class_readiness": role_manual_class_readiness(academic_session, term, level, arm)})


@report_sheet_bp.route("/api/report-sheets/manual/generate", methods=["POST"])
@report_staff_required
def api_report_manual_generate():
    denied = official_generation_denied()
    if denied: return denied
    data = request.get_json(silent=True) or {}; class_level, class_arm = request_class_values(data); level, arm, error = resolve_class(class_level, class_arm, require_arm=True)
    if error: return jsonify({"success": False, "message": error}), 400
    academic_session, term = resolve_context(data.get("session"), data.get("term")); mode = clean(data.get("mode") or "manual").lower(); next_term, next_term_error = next_term_required_response(data.get("next_term"))
    if not academic_session or not term: return jsonify({"success": False, "message": "Academic session and term are required."}), 400
    if next_term_error: return next_term_error
    save_report_defaults(academic_session, term, level, arm, {**({"form_teacher": data.get("form_teacher")} if "form_teacher" in data else {}), "next_term": next_term})
    if not assessment_entry_enabled(level):
        rule = get_assessment_rule(level) or {}; return jsonify({"success": False, "status": "assessment_scheme_pending", "message": rule.get("message") or f"The assessment scheme for {class_label(level)} is not configured yet.", "assessment": rule}), 409
    if mode not in {"manual", "hybrid"}: return jsonify({"success": False, "message": "Manual generation mode must be manual or hybrid."}), 400

    readiness = role_manual_class_readiness(academic_session, term, level, arm)
    if not readiness.get("class_ready"):
        remaining = int(readiness.get("remaining_students") or 0); excluded = int(readiness.get("excluded_students") or 0)
        return jsonify({"success": False, "status": "manual_class_incomplete", "message": f"Class report generation is locked. Complete and save every included student's selected-subject scores first. {remaining} student(s) remain; {excluded} excluded.", "class_readiness": readiness}), 409

    # Manual generation is deliberately class-only.  This guarantees position, out-of, class
    # average, highest/lowest and subject statistics are calculated from the same completed cohort.
    eligible = readiness.get("eligible_admissions") or []
    if normalize_academic_term(term) == "THIRD":
        payload = build_manual_report_payload(academic_session, term, level, arm) if mode == "manual" else build_hybrid_report_payload(academic_session, term, level, arm, data.get("year")); payload = apply_report_subject_scope(payload, level, arm)
        if payload.get("reports"): attach_cumulative_results(payload, academic_session, level, arm, resolve_result_year(academic_session, data.get("year"), level, arm), mode=mode)
    else:
        payload = build_manual_report_payload(academic_session, term, level, arm) if mode == "manual" else build_hybrid_report_payload(academic_session, term, level, arm, data.get("year")); payload = apply_report_subject_scope(payload, level, arm)
    payload = apply_requested_next_term(payload, next_term)
    wanted = {normalize_admission_number(value) for value in eligible}; payload["reports"] = [report for report in (payload.get("reports") or []) if normalize_admission_number(report.get("admission_number")) in wanted]; payload["students"] = [student for student in (payload.get("students") or []) if normalize_admission_number(student.get("admission_number")) in wanted]; payload["summary"] = dict(payload.get("summary") or {}); payload["summary"].update({"generated": len(payload["reports"]), "manual_class_ready": True, "excluded_students": readiness.get("excluded_students", 0), "eligible_students": readiness.get("eligible_students", len(eligible))}); payload["success"] = bool(payload["reports"]); payload["class_readiness"] = readiness
    if not payload.get("reports"): return jsonify({**payload, "message": "No completed manual class reports are available for generation."}), 400
    integrity = audit_manual_report_integrity(payload, eligible); payload["integrity_audit"] = integrity
    if not integrity.get("verified"): return jsonify({**payload, "success": False, "status": "report_integrity_failed", "message": "Report generation was stopped by the EMIS integrity guard because one or more class totals/positions/statistics did not reconcile. Nothing was archived or approved for printing.", "integrity_audit": integrity}), 409

    # Official Manual / Hybrid generation is archived before success is returned.  The underlying
    # snapshot + Academic History batch write is local and fast; only remote sync bookkeeping is
    # deferred inside save_report_snapshots().  This guarantees that every generated official sheet
    # is immediately available in History, Broadsheets and transcript workflows.
    payload["saved_snapshots"] = []
    if data.get("save_snapshot", True):
        archive_actor = clean(session.get("admin_username") or session.get("username") or session.get("user") or "Staff"); snapshots = save_report_snapshots([dict(report) for report in payload["reports"]], generated_by=archive_actor); payload["saved_snapshots"] = [{"snapshot_id":item.get("snapshot_id"),"admission_number":item.get("admission_number"),"full_name":item.get("full_name"),"generated_at":item.get("generated_at"),"transcript_archived":bool(item.get("transcript_archived"))} for item in snapshots]; payload["history_auto_saved"] = True
    payload["message"] = f"{len(payload['reports'])} {mode} class report sheet(s) generated successfully."
    return jsonify(payload)


# ============================================================
# API — CLASS-WIDE REMARKS / TRAITS / ATTENDANCE
# ============================================================

@report_sheet_bp.route("/api/report-sheets/bulk-details", methods=["POST"])
@report_staff_required
def api_report_bulk_details():
    denied = official_generation_denied()
    if denied: return denied
    data = request.get_json(silent=True) or {}; class_level, class_arm = request_class_values(data); level, arm, error = resolve_class(class_level, class_arm, require_arm=True)
    if error: return jsonify({"success": False, "message": error}), 400
    academic_session, term = resolve_context(data.get("session"), data.get("term")); roster = get_report_students_for_class(level, arm, active_only=True); admissions = normalize_admission_selection(data.get("admission_numbers") or data.get("admissions")); scope = clean(data.get("scope") or "selected").lower()
    if scope == "all" or not admissions: admissions = [normalize_admission_number(student.get("admission_number")) for student in roster if normalize_admission_number(student.get("admission_number"))]
    wanted = set(admissions); selected = [student for student in roster if normalize_admission_number(student.get("admission_number")) in wanted]
    if not selected: return jsonify({"success": False, "message": "No students matched the bulk-apply selection."}), 400
    details_store = _read_json_store(DETAILS_FILE); manual_store = _read_json_store(MANUAL_FILE); attendance_payload = data.get("attendance") if isinstance(data.get("attendance"), dict) else None
    try: normalized_attendance = normalize_manual_attendance(attendance_payload) if attendance_payload is not None else None
    except ValueError as error: return jsonify({"success": False, "message": str(error)}), 400
    average_payload = build_hybrid_report_payload(academic_session, term, level, arm) if data.get("auto_teacher_remark") or data.get("auto_principal_remark") else None; average_map = {normalize_admission_number(report.get("admission_number")): optional_float(report.get("average")) for report in (average_payload or {}).get("reports", [])}
    for student in selected:
        admission = normalize_admission_number(student.get("admission_number")); key = report_context_key(academic_session, term, level, arm, admission); current = details_store.get(key, {}) if isinstance(details_store.get(key), dict) else {}; detail_data = {}
        for field in ["form_teacher", "teacher_remark", "principal_remark", "next_term", "promotion_status", "promotion_note"]:
            if field in data: detail_data[field] = data.get(field)
        if data.get("auto_teacher_remark"): detail_data["teacher_remark"] = teacher_remark(average_map.get(admission)) if average_map.get(admission) is not None else clean(data.get("teacher_remark"))
        if data.get("auto_principal_remark"): detail_data["principal_remark"] = principal_remark(average_map.get(admission)) if average_map.get(admission) is not None else clean(data.get("principal_remark"))
        if isinstance(data.get("affective"), dict): detail_data["affective"] = data.get("affective")
        if isinstance(data.get("psychomotor"), dict): detail_data["psychomotor"] = data.get("psychomotor")
        if detail_data: details_store[key] = normalize_report_details(detail_data, current)
        if normalized_attendance is not None:
            mkey = manual_context_key(academic_session, term, level, arm, admission); record = manual_store.get(mkey, {}) if isinstance(manual_store.get(mkey), dict) else {}; record.update({"session": academic_session, "term": term, "class_level": level, "class_arm": arm, "admission_number": clean(student.get("admission_number")), "attendance": normalized_attendance, "attendance_user_set": normalized_attendance is not None or bool(record.get("attendance_user_set", False)), "attendance_override_enabled": bool(data.get("attendance_override_enabled", True)), "status": clean(record.get("status") or "DRAFT"), "subjects": record.get("subjects", {}), "prefer_manual_scores": bool(record.get("prefer_manual_scores", False)), "updated_at": now_string(), "updated_by": clean(session.get("admin_username") or session.get("username") or session.get("user") or "Staff")}); manual_store[mkey] = record
    details_changed = any(key in data for key in ["form_teacher", "teacher_remark", "principal_remark", "next_term", "promotion_status", "promotion_note", "affective", "psychomotor", "auto_teacher_remark", "auto_principal_remark"])
    if details_changed: _write_json_store(DETAILS_FILE, details_store)
    if normalized_attendance is not None: _write_json_store(MANUAL_FILE, manual_store)
    for student in selected:
        admission = normalize_admission_number(student.get("admission_number")); dkey = report_context_key(academic_session, term, level, arm, admission)
        if details_changed and isinstance(details_store.get(dkey), dict): queue_emis_event_safely("report_sheets", "details_upsert", {"key": dkey, "item": details_store[dkey]}, entity_key=f"details|{dkey}")
        mkey = manual_context_key(academic_session, term, level, arm, admission)
        if normalized_attendance is not None and isinstance(manual_store.get(mkey), dict): queue_emis_event_safely("report_sheets", "manual_upsert", {"key": mkey, "item": manual_store[mkey]}, entity_key=f"manual|{mkey}")
    return jsonify({"success": True, "message": f"Class-wide report details applied to {len(selected)} student(s).", "count": len(selected), "admission_numbers": [student.get("admission_number") for student in selected], "attendance": normalized_attendance})


# ============================================================
# CLOUD SYNC EVENT APPLICATION
# ============================================================

def _rewrite_snapshot_rows(rows):
    ensure_report_dir()
    with REPORT_LOCK:
        with SNAPSHOT_FILE.open("w", encoding="utf-8") as file:
            for row in rows:
                if isinstance(row, dict): file.write(json.dumps(row, ensure_ascii=False) + "\n")


def _read_usage_rows():
    if not USAGE_FILE.exists(): return []
    rows = []
    with REPORT_LOCK:
        with USAGE_FILE.open("r", encoding="utf-8") as file:
            for line in file:
                try:
                    item = json.loads(line)
                    if isinstance(item, dict): rows.append(item)
                except Exception: continue
    return rows


def apply_report_sync_event(action, payload, event=None):
    action = clean(action).lower()
    if not isinstance(payload, dict): raise ValueError("Report Sheet sync payload must be an object.")

    if action in {"details_upsert", "defaults_upsert", "manual_upsert", "subject_scope_upsert"}:
        key, item = clean(payload.get("key")), payload.get("item")
        if not key or not isinstance(item, dict): raise ValueError(f"{action} requires a key and item.")
        target = DETAILS_FILE if action == "details_upsert" else DEFAULTS_FILE if action == "defaults_upsert" else REPORT_SUBJECT_SCOPE_FILE if action == "subject_scope_upsert" else MANUAL_FILE
        store = _read_json_store(target); store[key] = item; _write_json_store(target, store)
        return {"store": target.name, "key": key, "operation": "upsert"}

    if action in {"manual_delete", "subject_scope_delete"}:
        key = clean(payload.get("key"))
        if not key: raise ValueError(f"{action} requires a key.")
        target = REPORT_SUBJECT_SCOPE_FILE if action == "subject_scope_delete" else MANUAL_FILE; store = _read_json_store(target); existed = key in store; store.pop(key, None); _write_json_store(target, store)
        return {"store": target.name, "key": key, "deleted": existed}

    if action == "snapshot_upsert":
        snapshot = payload.get("snapshot")
        if not isinstance(snapshot, dict) or not clean(snapshot.get("snapshot_id")): raise ValueError("snapshot_upsert requires a valid snapshot.")
        snapshot_id = clean(snapshot.get("snapshot_id")); rows = read_saved_report_snapshots()[::-1]; replaced = False
        for index, row in enumerate(rows):
            if clean(row.get("snapshot_id")) == snapshot_id: rows[index] = snapshot; replaced = True; break
        if not replaced: rows.append(snapshot)
        _rewrite_snapshot_rows(rows)
        return {"snapshot_id": snapshot_id, "operation": "replace" if replaced else "append"}

    if action == "snapshot_delete":
        snapshot_id = clean(payload.get("snapshot_id"))
        if not snapshot_id: raise ValueError("snapshot_delete requires snapshot_id.")
        rows = read_saved_report_snapshots()[::-1]; remaining = [row for row in rows if clean(row.get("snapshot_id")) != snapshot_id]; deleted = len(rows) - len(remaining); _rewrite_snapshot_rows(remaining)
        return {"snapshot_id": snapshot_id, "deleted": deleted}

    if action == "usage_append":
        record = payload.get("record")
        if not isinstance(record, dict): raise ValueError("usage_append requires a record.")
        audit_id = clean(record.get("audit_id")) or clean((event or {}).get("event_id"))
        record = dict(record); record["audit_id"] = audit_id
        existing = _read_usage_rows()
        if any(clean(row.get("audit_id")) == audit_id for row in existing): return {"audit_id": audit_id, "duplicate": True}
        ensure_report_dir()
        with REPORT_LOCK:
            with USAGE_FILE.open("a", encoding="utf-8") as file: file.write(json.dumps(record, ensure_ascii=False) + "\n")
        return {"audit_id": audit_id, "appended": True}

    if action == "admin_delete":
        audit=payload.get("audit") if isinstance(payload.get("audit"),dict) else {}; scope=audit.get("scope") if isinstance(audit.get("scope"),dict) else {}; delete_action=clean(audit.get("action")).lower()
        if delete_action == "database" or scope.get("all_report_sheet_data"): return delete_report_sheet_scope(delete_all=True)
        if delete_action == "class_history": return delete_report_sheet_scope(class_level=scope.get("class_level"),class_arm=scope.get("class_arm"),delete_all=False)
        return delete_report_sheet_scope(scope.get("session"),scope.get("term"),scope.get("class_level"),scope.get("class_arm"),False)

    raise ValueError(f"Unsupported Report Sheet sync action: {action}")
