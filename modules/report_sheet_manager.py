# MODULE: Report Sheet Manager — EMIS academic report aggregation, grading, statistics and cumulative results

import csv
import io
import json
import uuid
from pathlib import Path
from datetime import datetime
from threading import RLock
from functools import wraps

from flask import Blueprint, jsonify, request, session, Response, send_file

from modules.academic_records import clean, clean_upper, normalize_academic_session, normalize_academic_term, academic_term_label, get_current_academic_context, normalize_academic_class, validate_class_selection, get_students_for_class, get_student, get_subjects_for_selection, get_subjects_for_student, normalize_academic_subject, academic_subject_key
from modules.student_lookup import normalize_admission_number
from modules.attendance_manager import get_student_attendance_summary, get_attendance_summary_map
from modules.ca_test_manager import get_ca_scores_map, get_ca_available_contexts
from modules.api_routes import read_results_term_aware, normalize_result_record, enrich_records_with_essay, get_subject_folders
from openpyxl import Workbook


report_sheet_bp = Blueprint("report_sheet_bp", __name__)

BASE_DIR = Path(__file__).resolve().parent.parent
REPORT_DIR = BASE_DIR / "static" / "data" / "report_sheets"
SNAPSHOT_FILE = REPORT_DIR / "generated_reports.jsonl"
DETAILS_FILE = REPORT_DIR / "report_details.json"
DEFAULTS_FILE = REPORT_DIR / "report_defaults.json"
USAGE_FILE = REPORT_DIR / "report_usage.jsonl"
PORTAL_ACTIVE_YEARS_FILE = BASE_DIR / "static" / "portal" / "class_active_years.json"
REPORT_LOCK = RLock()

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
        if clean(session.get("user_type")).lower() not in {"admin", "teacher"}:
            return jsonify({"success": False, "message": "Unauthorized."}), 403
        return view(*args, **kwargs)
    return wrapped


def now_string(): return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


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
    context = get_current_academic_context(session_value, term_value)
    return normalize_academic_session(context.get("academic_session") or context.get("session")), normalize_academic_term(context.get("term"))


def resolve_class(class_level="", class_arm="", require_arm=True):
    level, arm = normalize_academic_class(class_level or class_arm, class_arm or class_level)
    result = validate_class_selection(level, class_arm or arm, require_arm=require_arm)

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

def grade_for_score(score):
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
    maximum = 40 if clean_upper(class_level).startswith("JSS") else 70
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
    level, arm = normalize_academic_class(class_level, class_arm)

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


def build_subject_row(class_level, subject_key, ca=None, exam_row=None, subject_name=""):
    """Build a subject row without converting missing/incomplete CA or CBT data into false zero scores."""
    ca, exam_row = ca if isinstance(ca, dict) else {}, exam_row if isinstance(exam_row, dict) else {}
    subject = normalize_academic_subject(ca.get("subject") or exam_row.get("Subject") or subject_name or subject_key)
    has_ca, has_exam = bool(ca), bool(exam_row); ca_complete = bool(ca.get("complete")) if has_ca else False
    ca_total = safe_float(ca.get("ca_total")) if has_ca else None; exam_score = scale_exam_score(exam_row, class_level) if has_exam else None; exam_complete = exam_score is not None
    complete = bool(ca_complete and exam_complete); total = round(ca_total + exam_score, 2) if complete else None
    grade, comment = grade_for_score(total) if total is not None else ("-", "Pending")
    row = {"subject": subject, "subject_key": subject_key, "mode": "JSS" if class_level.startswith("JSS") else "SS", "has_ca": has_ca, "has_exam": has_exam, "exam_complete": exam_complete, "ca_complete": ca_complete, "complete": complete, "ca_total": pretty_optional(ca_total), "exam": pretty_optional(exam_score), "total": pretty_optional(total), "grade": grade, "comment": comment, "position": 0, "position_text": "--", "out_of": 0, "lowest": None, "highest": None, "class_average": None}
    if class_level.startswith("JSS"): row.update({"ca1": ca.get("ca1") if has_ca else None, "ca2": ca.get("ca2") if has_ca else None, "test1": ca.get("test1") if has_ca else None, "test2": ca.get("test2") if has_ca else None})
    else: row.update({"ass1": ca.get("ass1") if has_ca else None, "ass2": ca.get("ass2") if has_ca else None, "test": ca.get("test") if has_ca else None})
    return row


def expected_subject_map(student, class_level, class_arm):
    subjects = get_subjects_for_student(student) or get_subjects_for_selection(class_level, class_arm)
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
    level, arm = normalize_academic_class(class_level, class_arm); result_year = resolve_result_year(academic_session, result_year, level, arm)
    students = get_students_for_class(level, arm, active_only=True)
    if admission_number:
        wanted = normalize_admission_number(admission_number); students = [student for student in students if normalize_admission_number(student.get("admission_number")) == wanted]

    ca_map = get_ca_scores_map(academic_session, term, level, arm); attendance_map = get_attendance_summary_map(academic_session, term, level, arm); exam_map, exam_subject_names = load_exam_results_map(academic_session, term, level, arm, result_year)
    ca_contexts = [] if ca_map else get_ca_available_contexts(level, arm)
    reports, blocked, source_students, readiness_warnings, subject_scores, subject_catalog = [], [], [], [], {}, set()

    for student in students:
        admission = normalize_admission_number(student.get("admission_number")); student_ca = ca_map.get(admission, {}); student_exam = exam_map.get(admission, {}); attendance = attendance_map.get(admission, {})
        source = build_student_source_status(student, student_ca, student_exam, attendance); source_students.append(source)
        expected = expected_subject_map(student, level, arm); subject_keys, excluded_subjects = resolve_report_subject_keys(expected, student_ca, student_exam); subject_rows = []

        for subject_key in subject_keys:
            row = build_subject_row(level, subject_key, student_ca.get(subject_key), student_exam.get(subject_key), expected.get(subject_key) or exam_subject_names.get(subject_key) or subject_key)
            subject_rows.append(row); subject_catalog.add(subject_key)
            if row.get("total") is not None: subject_scores.setdefault(subject_key, []).append(safe_float(row.get("total")))

        complete_rows = [row for row in subject_rows if row.get("complete") and row.get("total") is not None]
        all_subjects_complete = bool(subject_rows) and len(complete_rows) == len(subject_rows)
        provisional_total = round(sum(safe_float(row.get("total")) for row in complete_rows), 2) if complete_rows else None
        provisional_average = round(provisional_total / len(complete_rows), 2) if complete_rows else None
        total_score = provisional_total if all_subjects_complete else None; average = provisional_average if all_subjects_complete else None
        final_grade = grade_for_score(average)[0] if average is not None else "-"
        if not source.get("has_ca") or not source.get("has_exam") or not all_subjects_complete:
            missing = []
            if not source.get("has_ca"): missing.append("CA/Test")
            if not source.get("has_exam"): missing.append("Exam")
            if not source.get("has_attendance"): missing.append("Attendance")
            if source.get("has_ca") and not source.get("has_complete_ca"): missing.append("Complete CA")
            readiness_warnings.append({"admission_number": student.get("admission_number"), "full_name": student.get("full_name"), "missing": missing, "status": source.get("status"), "status_label": source.get("status_label")})

        reports.append({"admission_number": student.get("admission_number"), "full_name": student.get("full_name"), "last_name": student.get("last_name"), "first_name": student.get("first_name"), "other_names": student.get("other_names"), "sex": student.get("sex"), "class_level": level, "class_arm": arm, "session": academic_session, "term": term, "term_label": academic_term_label(term), "result_year": result_year, "subjects": subject_rows, "subject_count": len(subject_rows), "subjects_complete": len(complete_rows), "academic_complete": all_subjects_complete, "academic_partial": bool(student_ca or student_exam) and not all_subjects_complete, "has_ca": bool(student_ca), "has_exam": bool(student_exam), "has_attendance": bool(attendance), "total_score": pretty_optional(total_score), "average": pretty_optional(average), "provisional_total": pretty_optional(provisional_total), "provisional_average": pretty_optional(provisional_average), "grade": final_grade, "position": 0, "position_text": "--", "out_of": 0, "attendance": attendance, "teacher_remark": teacher_remark(average) if average is not None else "", "principal_remark": principal_remark(average) if average is not None else "", "missing_ca_subjects": source["missing_ca_subjects"], "missing_exam_subjects": source["missing_exam_subjects"], "excluded_subjects": excluded_subjects, "source_status": source.get("status"), "source_status_label": source.get("status_label")})

    # Subject statistics use only complete CA + Exam totals; missing data stays blank instead of becoming zero.
    for report in reports:
        for row in report.get("subjects", []):
            if row.get("total") is None: continue
            scores = subject_scores.get(row.get("subject_key"), [])
            if not scores: continue
            position = compute_position(row.get("total"), scores); row.update({"position": position, "position_text": ordinal(position), "out_of": len(scores), "lowest": pretty_number(min(scores)), "highest": pretty_number(max(scores)), "class_average": pretty_number(sum(scores) / len(scores))})

    # Overall class positions are assigned only when a full final average exists.
    averages = [safe_float(report.get("average")) for report in reports if report.get("average") is not None]
    for report in reports:
        if report.get("average") is None: continue
        position = compute_position(report.get("average"), averages); report["position"] = position; report["position_text"] = ordinal(position); report["out_of"] = len(averages)

    summary = {"students_in_class": len(students), "generated": len(reports), "blocked": len(blocked), "complete_reports": sum(1 for report in reports if report.get("academic_complete")), "partial_reports": sum(1 for report in reports if not report.get("academic_complete")), "reports_with_ca": sum(1 for report in reports if report.get("has_ca")), "reports_with_exam": sum(1 for report in reports if report.get("has_exam")), "reports_with_attendance": sum(1 for report in reports if report.get("has_attendance")), "subjects": len(subject_catalog), "class_average": pretty_number(sum(averages) / len(averages)) if averages else None, "highest_average": pretty_number(max(averages)) if averages else None, "lowest_average": pretty_number(min(averages)) if averages else None, "missing_ca": sum(1 for item in source_students if not item.get("has_ca")), "missing_exam": sum(1 for item in source_students if not item.get("has_exam")), "missing_attendance": sum(1 for item in source_students if not item.get("has_attendance"))}
    payload = {"success": bool(reports), "session": academic_session, "term": term, "term_label": academic_term_label(term), "result_year": result_year, "class_level": level, "class_arm": arm, "students": source_students, "reports": reports, "blocked_students": blocked, "readiness_warnings": readiness_warnings, "summary": summary, "source_status": {"students": bool(students), "ca_test": bool(ca_map), "exam_results": bool(exam_map), "attendance": bool(attendance_map), "ca_context_mismatch": bool(not ca_map and ca_contexts)}, "ca_available_contexts": ca_contexts}
    if term == "THIRD" and include_cumulative and reports: attach_cumulative_results(payload, academic_session, level, arm, result_year)
    return payload


# ============================================================
# THIRD TERM CUMULATIVE ENGINE — PARTIAL DATA SAFE
# ============================================================

def report_map(payload): return {normalize_admission_number(report.get("admission_number")): report for report in (payload or {}).get("reports", []) if normalize_admission_number(report.get("admission_number"))}


def subject_total_map(report):
    return {row.get("subject_key"): safe_float(row.get("total")) for row in (report or {}).get("subjects", []) if row.get("subject_key") and row.get("total") is not None}


def combine_attendance_summaries(*items):
    output = {"days_open": 0, "present": 0, "absent": 0, "late": 0, "sick": 0, "excused": 0, "unmarked": 0, "present_credit": 0, "absent_total": 0, "attendance_percentage": 0}
    for item in items:
        if not isinstance(item, dict): continue
        for key in ["days_open", "present", "absent", "late", "sick", "excused", "unmarked", "present_credit", "absent_total"]: output[key] += int(safe_float(item.get(key)))
    output["attendance_percentage"] = round((output["present_credit"] / output["days_open"]) * 100, 1) if output["days_open"] else 0
    return output


def attach_cumulative_results(third_payload, academic_session, class_level, class_arm, result_year):
    first = build_term_report_payload(academic_session, "FIRST", class_level, class_arm, result_year, include_cumulative=False); second = build_term_report_payload(academic_session, "SECOND", class_level, class_arm, result_year, include_cumulative=False)
    first_map, second_map = report_map(first), report_map(second)
    for report in third_payload.get("reports", []):
        admission = normalize_admission_number(report.get("admission_number")); first_report, second_report = first_map.get(admission), second_map.get(admission); first_subjects, second_subjects = subject_total_map(first_report), subject_total_map(second_report)
        for row in report.get("subjects", []):
            key = row.get("subject_key"); first_total, second_total = first_subjects.get(key), second_subjects.get(key); third_total = optional_float(row.get("total")); available = [value for value in [first_total, second_total, third_total] if value is not None]
            cumulative_average = round(sum(available) / len(available), 2) if available else None; cumulative_grade, cumulative_comment = grade_for_score(cumulative_average) if cumulative_average is not None else ("-", "Pending")
            row.update({"first_term_total": pretty_optional(first_total), "second_term_total": pretty_optional(second_total), "third_term_total": pretty_optional(third_total), "cumulative_total": pretty_optional(sum(available) if available else None), "cumulative_average": pretty_optional(cumulative_average), "cumulative_grade": cumulative_grade, "cumulative_comment": cumulative_comment, "terms_available": len(available)})
        term_averages = [optional_float((first_report or {}).get("average")), optional_float((second_report or {}).get("average")), optional_float(report.get("average"))]; valid_averages = [value for value in term_averages if value is not None]
        cumulative_average = round(sum(valid_averages) / len(valid_averages), 2) if valid_averages else None; cumulative_grade = grade_for_score(cumulative_average)[0] if cumulative_average is not None else "-"
        report["first_term_average"], report["second_term_average"], report["third_term_average"] = pretty_optional(term_averages[0]), pretty_optional(term_averages[1]), pretty_optional(term_averages[2]); report["cumulative_average"], report["cumulative_grade"] = pretty_optional(cumulative_average), cumulative_grade
        report["cumulative_attendance"] = combine_attendance_summaries((first_report or {}).get("attendance"), (second_report or {}).get("attendance"), report.get("attendance"))
    cumulative_averages = [safe_float(report.get("cumulative_average")) for report in third_payload.get("reports", []) if report.get("cumulative_average") is not None]
    for report in third_payload.get("reports", []):
        if report.get("cumulative_average") is None: report["cumulative_position"], report["cumulative_position_text"], report["cumulative_out_of"] = 0, "--", 0; continue
        position = compute_position(report.get("cumulative_average"), cumulative_averages); report["cumulative_position"], report["cumulative_position_text"], report["cumulative_out_of"] = position, ordinal(position), len(cumulative_averages)
    third_payload["cumulative"], third_payload["cumulative_terms"] = True, ["FIRST", "SECOND", "THIRD"]


# ============================================================
# SAVED REPORT SNAPSHOTS
# ============================================================

def ensure_report_dir():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    return REPORT_DIR


def save_report_snapshots(reports):
    ensure_report_dir()
    saved = []

    with REPORT_LOCK:
        with SNAPSHOT_FILE.open("a", encoding="utf-8") as file:
            for report in reports:
                snapshot = {
                    "snapshot_id": uuid.uuid4().hex, "generated_at": now_string(),
                    "generated_by": clean(session.get("admin_username") or session.get("username") or session.get("user") or "Staff"),
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
    academic_session, term = resolve_context(request.args.get("session"), request.args.get("term"))
    class_level, class_arm = request_class_values()
    level, arm = normalize_academic_class(class_level, class_arm)

    return jsonify({
        "success": True, "session": academic_session, "term": term, "term_label": academic_term_label(term),
        "class_level": level, "class_arm": arm,
        "subjects": get_subjects_for_selection(level, arm) if level else [],
        "result_year": resolve_result_year(academic_session, request.args.get("year"), level, arm),
    })


@report_sheet_bp.route("/api/report-sheets/students")
@report_staff_required
def api_report_students():
    class_level, class_arm = request_class_values()
    level, arm, error = resolve_class(class_level, class_arm, require_arm=True)

    if error: return jsonify({"success": False, "message": error, "students": []}), 400

    students = get_students_for_class(level, arm, active_only=True)
    return jsonify({"success": True, "class_level": level, "class_arm": arm, "students": students, "count": len(students)})


@report_sheet_bp.route("/api/report-sheets/source-status")
@report_staff_required
def api_report_source_status():
    class_level, class_arm = request_class_values()
    level, arm, error = resolve_class(class_level, class_arm, require_arm=True)

    if error: return jsonify({"success": False, "message": error}), 400

    academic_session, term = resolve_context(request.args.get("session"), request.args.get("term"))
    year = resolve_result_year(academic_session, request.args.get("year"), level, arm)

    payload = build_term_report_payload(academic_session, term, level, arm, year, include_cumulative=False)

    return jsonify({"success": True, "result_year": payload.get("result_year") or year, "session": academic_session, "term": term, "class_level": level, "class_arm": arm, "students": payload.get("students", []), "source_status": payload.get("source_status", {}), "summary": payload.get("summary", {}), "blocked_students": payload.get("blocked_students", []), "readiness_warnings": payload.get("readiness_warnings", []), "ca_available_contexts": payload.get("ca_available_contexts", [])})


# ============================================================
# API — PREVIEW / GENERATE
# ============================================================

@report_sheet_bp.route("/api/report-sheets/preview", methods=["POST"])
@report_staff_required
def api_report_preview():
    data = request.get_json(silent=True) or {}
    class_level, class_arm = request_class_values(data)
    level, arm, error = resolve_class(class_level, class_arm, require_arm=True)

    if error: return jsonify({"success": False, "message": error}), 400

    academic_session, term = resolve_context(data.get("session"), data.get("term"))

    if not academic_session or not term:
        return jsonify({"success": False, "message": "Academic session and term are required."}), 400

    payload = build_term_report_payload(
        academic_session, term, level, arm, data.get("year"), data.get("admission_number") or data.get("admission"),
        include_cumulative=True, admission_numbers=data.get("admission_numbers") or data.get("admissions")
    )

    return jsonify(payload)


@report_sheet_bp.route("/api/report-sheets/generate", methods=["POST"])
@report_staff_required
def api_report_generate():
    data = request.get_json(silent=True) or {}
    class_level, class_arm = request_class_values(data)
    level, arm, error = resolve_class(class_level, class_arm, require_arm=True)

    if error: return jsonify({"success": False, "message": error}), 400

    academic_session, term = resolve_context(data.get("session"), data.get("term"))

    if not academic_session or not term:
        return jsonify({"success": False, "message": "Academic session and term are required."}), 400

    payload = build_term_report_payload(
        academic_session, term, level, arm, data.get("year"), data.get("admission_number") or data.get("admission"),
        include_cumulative=True, admission_numbers=data.get("admission_numbers") or data.get("admissions")
    )

    if not payload.get("reports"):
        payload["message"] = "No active student report sheets could be generated for this class selection."
        return jsonify(payload), 400

    if data.get("save_snapshot", True):
        snapshots = save_report_snapshots(payload["reports"]); snapshot_map = {normalize_admission_number(item.get("admission_number")): item.get("snapshot_id") for item in snapshots}
        for report in payload["reports"]: report["snapshot_id"] = snapshot_map.get(normalize_admission_number(report.get("admission_number")), "")
        payload["saved_snapshots"] = [{"snapshot_id": item["snapshot_id"], "admission_number": item["admission_number"], "full_name": item.get("full_name", ""), "generated_at": item.get("generated_at", "")} for item in snapshots]

    complete = sum(1 for report in payload.get("reports", []) if report.get("academic_complete")); partial = len(payload.get("reports", [])) - complete
    payload["message"] = f"{len(payload['reports'])} report sheet(s) generated successfully — {complete} complete, {partial} awaiting one or more academic sources."
    return jsonify(payload)


# ============================================================
# API — SAVED REPORTS
# ============================================================

@report_sheet_bp.route("/api/report-sheets/saved")
@report_staff_required
def api_saved_reports():
    academic_session = normalize_academic_session(request.args.get("session"))
    term = normalize_academic_term(request.args.get("term"))
    class_level, class_arm = request_class_values()
    level, arm = normalize_academic_class(class_level, class_arm)

    rows = read_saved_report_snapshots()

    if academic_session: rows = [row for row in rows if normalize_academic_session(row.get("session")) == academic_session]
    if term: rows = [row for row in rows if normalize_academic_term(row.get("term")) == term]
    if level: rows = [row for row in rows if normalize_academic_class(row.get("class_level"), row.get("class_arm"))[0] == level]
    if class_arm and arm: rows = [row for row in rows if normalize_academic_class(row.get("class_level"), row.get("class_arm"))[1] == arm]

    return jsonify({"success": True, "reports": rows, "count": len(rows)})


@report_sheet_bp.route("/api/report-sheets/delete-saved", methods=["POST", "DELETE"])
@report_staff_required
def api_delete_saved_report():
    data = request.get_json(silent=True) or {}
    snapshot_ids = data.get("snapshot_ids") or ([data.get("snapshot_id")] if data.get("snapshot_id") else [])
    admissions = data.get("admission_numbers") or data.get("admissions") or []
    if isinstance(snapshot_ids, str): snapshot_ids = [item.strip() for item in snapshot_ids.replace(";", ",").split(",") if item.strip()]
    if isinstance(admissions, str): admissions = [item.strip() for item in admissions.replace(";", ",").split(",") if item.strip()]
    snapshot_ids = {clean(value) for value in snapshot_ids if clean(value)}; admissions = {normalize_admission_number(value) for value in admissions if normalize_admission_number(value)}
    delete_all = str(data.get("delete_all") or "").strip().lower() in {"1", "true", "yes", "on"}
    academic_session, term = normalize_academic_session(data.get("session")), normalize_academic_term(data.get("term")); class_level, class_arm = request_class_values(data); level, arm = normalize_academic_class(class_level, class_arm)

    if not snapshot_ids and not admissions and not delete_all: return jsonify({"success": False, "message": "Provide a snapshot ID, selected report IDs, selected admission numbers, or delete_all=true."}), 400
    if (admissions or delete_all) and not (academic_session and term and level and arm): return jsonify({"success": False, "message": "Session, term, class level and class arm are required for selected/context report deletion."}), 400

    rows = read_saved_report_snapshots()[::-1]
    def same_context(row):
        row_level, row_arm = normalize_academic_class(row.get("class_level"), row.get("class_arm"))
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

    return jsonify({"success": True, "message": f"{len(deleted)} saved report snapshot(s) deleted successfully.", "deleted_count": len(deleted), "deleted_snapshot_ids": [row.get("snapshot_id") for row in deleted], "deleted_admission_numbers": [row.get("admission_number") for row in deleted]})


# ============================================================
# PERSISTENT REPORT DETAILS / DEFAULTS
# ============================================================

def report_context_key(academic_session, term, class_level, class_arm, admission_number=""):
    parts = [normalize_academic_session(academic_session), normalize_academic_term(term), clean_upper(class_level), clean_upper(class_arm), normalize_admission_number(admission_number)]
    return "|".join(parts)


def _read_json_store(path):
    ensure_report_dir()
    if not path.exists(): return {}
    with REPORT_LOCK:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception: return {}


def _write_json_store(path, data):
    ensure_report_dir(); temp = path.with_suffix(path.suffix + ".tmp")
    with REPORT_LOCK:
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"); temp.replace(path)
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
        "affective": normalize_trait_map(affective_source, affective_keys), "psychomotor": normalize_trait_map(psychomotor_source, psychomotor_keys),
        "updated_at": now_string(), "updated_by": clean(session.get("admin_username") or session.get("username") or session.get("user") or existing.get("updated_by") or "Staff"),
    }


def get_report_details(academic_session, term, class_level, class_arm, admission_number):
    key = report_context_key(academic_session, term, class_level, class_arm, admission_number)
    return _read_json_store(DETAILS_FILE).get(key, {})


def save_report_details(academic_session, term, class_level, class_arm, admission_number, data):
    store = _read_json_store(DETAILS_FILE); key = report_context_key(academic_session, term, class_level, class_arm, admission_number)
    store[key] = normalize_report_details(data, store.get(key, {})); _write_json_store(DETAILS_FILE, store); return store[key]


def get_report_defaults(academic_session, term, class_level, class_arm):
    key = report_context_key(academic_session, term, class_level, class_arm)
    return _read_json_store(DEFAULTS_FILE).get(key, {})


def save_report_defaults(academic_session, term, class_level, class_arm, data):
    store = _read_json_store(DEFAULTS_FILE); key = report_context_key(academic_session, term, class_level, class_arm)
    current = store.get(key, {}) if isinstance(store.get(key), dict) else {}
    item = {"form_teacher": clean(data.get("form_teacher", current.get("form_teacher", ""))), "next_term": clean(data.get("next_term", current.get("next_term", ""))), "updated_at": now_string(), "updated_by": clean(session.get("admin_username") or session.get("username") or session.get("user") or current.get("updated_by") or "Staff")}
    store[key] = item; _write_json_store(DEFAULTS_FILE, store); return item


def apply_saved_report_details(payload):
    if not isinstance(payload, dict): return payload
    session_value, term, level, arm = payload.get("session", ""), payload.get("term", ""), payload.get("class_level", ""), payload.get("class_arm", "")
    defaults, details_store = get_report_defaults(session_value, term, level, arm), _read_json_store(DETAILS_FILE); reports = payload.get("reports", []) if isinstance(payload.get("reports"), list) else []
    class_average = optional_float((payload.get("summary") or {}).get("class_average"))
    for report in reports:
        admission = report.get("admission_number"); details = details_store.get(report_context_key(session_value, term, level, arm, admission), {}); average = optional_float(report.get("average")); attendance = report.get("attendance") if isinstance(report.get("attendance"), dict) else {}
        report["form_teacher"] = clean(details.get("form_teacher") or defaults.get("form_teacher")); report["next_term"] = clean(details.get("next_term") or defaults.get("next_term"))
        report["teacher_remark"] = clean(details.get("teacher_remark") or report.get("teacher_remark") or (teacher_remark(average) if average is not None else "")); report["principal_remark"] = clean(details.get("principal_remark") or report.get("principal_remark") or (principal_remark(average) if average is not None else ""))
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
    defaults = save_report_defaults(academic_session, term, level, arm, source)
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
    data = request.get_json(silent=True) or {}; class_level, class_arm = request_class_values(data); level, arm, error = resolve_class(class_level, class_arm, require_arm=True)
    if error: return jsonify({"success": False, "message": error}), 400
    academic_session, term = resolve_context(data.get("session"), data.get("term")); admissions = data.get("admission_numbers") or data.get("admissions") or []
    if isinstance(admissions, str): admissions = [admissions]
    admissions = [normalize_admission_number(value) for value in admissions if normalize_admission_number(value)]
    if not admissions: return jsonify({"success": False, "message": "Select at least one generated student report first."}), 400
    ensure_report_dir(); record = {"marked_at": now_string(), "marked_by": clean(session.get("admin_username") or session.get("username") or session.get("user") or "Staff"), "session": academic_session, "term": term, "class_level": level, "class_arm": arm, "admission_numbers": admissions}
    with REPORT_LOCK:
        with USAGE_FILE.open("a", encoding="utf-8") as file: file.write(json.dumps(record, ensure_ascii=False) + "\n")
    return jsonify({"success": True, "message": f"{len(admissions)} report result set(s) marked as used in the report audit.", "count": len(admissions)})


# ============================================================
# HYBRID / MANUAL REPORT SYSTEM — STORAGE + FILE NAMING
# ============================================================

MANUAL_FILE = REPORT_DIR / "manual_report_records.json"


def safe_result_token(value):
    value = clean(value).replace("/", "-").replace("\\", "-")
    return "".join(ch for ch in value if ch.isalnum() or ch in {"-", "_"}).strip("_-")


def result_file_stem(report):
    report = report if isinstance(report, dict) else {}
    first_name = clean(report.get("first_name")) or (clean(report.get("full_name")).split()[0] if clean(report.get("full_name")) else "Student")
    level = clean_upper(report.get("class_level")) or normalize_academic_class(report.get("class_arm"), report.get("class_arm"))[0] or "CLASS"
    admission = clean(report.get("admission_number")) or "student"
    return f"{safe_result_token(first_name) or 'Student'}_{safe_result_token(level)}{safe_result_token(admission)}"


def save_report_snapshots(reports):
    """Save report snapshots with a stable human-readable result name for PDF/file workflows."""
    ensure_report_dir(); saved = []
    with REPORT_LOCK:
        with SNAPSHOT_FILE.open("a", encoding="utf-8") as file:
            for report in reports:
                snapshot = {
                    "snapshot_id": uuid.uuid4().hex, "generated_at": now_string(),
                    "generated_by": clean(session.get("admin_username") or session.get("username") or session.get("user") or "Staff"),
                    "session": report.get("session"), "term": report.get("term"), "class_level": report.get("class_level"), "class_arm": report.get("class_arm"),
                    "admission_number": report.get("admission_number"), "full_name": report.get("full_name"), "result_name": result_file_stem(report),
                    "source_mode": clean(report.get("source_mode") or "auto"), "report": report,
                }
                file.write(json.dumps(snapshot, ensure_ascii=False) + "\n"); saved.append(snapshot)
    return saved


# ============================================================
# HYBRID / MANUAL REPORT SYSTEM — RECORD HELPERS
# ============================================================


def manual_score_fields(class_level):
    return {"ca1": 10, "ca2": 10, "test1": 20, "test2": 20, "exam": 40} if clean_upper(class_level).startswith("JSS") else {"ass1": 5, "ass2": 5, "test": 20, "exam": 70}


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
    if not key or key not in allowed_map: return None
    fields = manual_score_fields(class_level); values = {field: manual_score_value(entry.get(field), maximum, field.upper()) for field, maximum in fields.items()}
    included = str(entry.get("included") or "").strip().lower() in {"1", "true", "yes", "on"} or any(value is not None for value in values.values())
    if not included: return None
    return {"subject": allowed_map.get(key) or normalize_academic_subject(raw_subject), "subject_key": key, "included": True, **values}


def manual_context_key(academic_session, term, class_level, class_arm, admission_number): return report_context_key(academic_session, term, class_level, class_arm, admission_number)


def get_manual_record(academic_session, term, class_level, class_arm, admission_number):
    return _read_json_store(MANUAL_FILE).get(manual_context_key(academic_session, term, class_level, class_arm, admission_number), {})


def save_manual_record(academic_session, term, class_level, class_arm, admission_number, data):
    store = _read_json_store(MANUAL_FILE); key = manual_context_key(academic_session, term, class_level, class_arm, admission_number); current = store.get(key, {}) if isinstance(store.get(key), dict) else {}
    allowed = expected_subject_map(get_student(admission_number, active_only=False) or {}, class_level, class_arm); entries = data.get("subjects") if isinstance(data.get("subjects"), list) else []
    subjects = {}
    for entry in entries:
        normalized = normalize_manual_subject(entry, class_level, allowed)
        if normalized: subjects[normalized["subject_key"]] = normalized
    attendance_supplied = isinstance(data.get("attendance"), dict); attendance = normalize_manual_attendance(data.get("attendance")) if attendance_supplied else current.get("attendance", {})
    item = {
        "session": normalize_academic_session(academic_session), "term": normalize_academic_term(term), "class_level": class_level, "class_arm": class_arm, "admission_number": clean(admission_number),
        "subjects": subjects if "subjects" in data else current.get("subjects", {}), "attendance": attendance if isinstance(attendance, dict) else {},
        "attendance_override_enabled": bool(data.get("attendance_override_enabled", current.get("attendance_override_enabled", False))),
        "prefer_manual_scores": bool(data.get("prefer_manual_scores", current.get("prefer_manual_scores", False))),
        "status": "FINAL" if clean_upper(data.get("status")) == "FINAL" else "DRAFT", "teacher_note": clean(data.get("teacher_note", current.get("teacher_note", ""))),
        "updated_at": now_string(), "updated_by": clean(session.get("admin_username") or session.get("username") or session.get("user") or current.get("updated_by") or "Staff"),
    }
    store[key] = item; _write_json_store(MANUAL_FILE, store); return item


def manual_record_summary(record):
    record = record if isinstance(record, dict) else {}; subjects = record.get("subjects") if isinstance(record.get("subjects"), dict) else {}
    return {"has_manual": bool(subjects or record.get("attendance")), "subject_count": len(subjects), "status": clean(record.get("status") or "DRAFT"), "attendance_override_enabled": bool(record.get("attendance_override_enabled")), "updated_at": clean(record.get("updated_at")), "updated_by": clean(record.get("updated_by"))}


# ============================================================
# HYBRID / MANUAL REPORT SYSTEM — REPORT CALCULATION
# ============================================================


def build_manual_subject_row(class_level, entry):
    entry = entry if isinstance(entry, dict) else {}; fields = manual_score_fields(class_level); scores = {field: optional_float(entry.get(field)) for field in fields}; is_jss = clean_upper(class_level).startswith("JSS")
    ca_fields = ["ca1", "ca2", "test1", "test2"] if is_jss else ["ass1", "ass2", "test"]; ca_values = [scores.get(field) for field in ca_fields]; exam = scores.get("exam")
    has_ca = any(value is not None for value in ca_values); ca_complete = all(value is not None for value in ca_values); has_exam = exam is not None; ca_total = round(sum(value or 0 for value in ca_values), 2) if has_ca else None
    complete = ca_complete and has_exam; total = round((ca_total or 0) + exam, 2) if complete else None; grade, comment = grade_for_score(total) if total is not None else ("-", "Pending")
    row = {"subject": normalize_academic_subject(entry.get("subject") or entry.get("subject_key")), "subject_key": academic_subject_key(entry.get("subject_key") or entry.get("subject")), "mode": "JSS" if is_jss else "SS", "has_ca": has_ca, "has_exam": has_exam, "ca_complete": ca_complete, "complete": complete, "ca_total": pretty_optional(ca_total), "exam": pretty_optional(exam), "total": pretty_optional(total), "grade": grade, "comment": comment, "position": 0, "position_text": "--", "out_of": 0, "lowest": None, "highest": None, "class_average": None}
    if is_jss: row.update({"ca1": pretty_optional(scores.get("ca1")), "ca2": pretty_optional(scores.get("ca2")), "test1": pretty_optional(scores.get("test1")), "test2": pretty_optional(scores.get("test2"))})
    else: row.update({"ass1": pretty_optional(scores.get("ass1")), "ass2": pretty_optional(scores.get("ass2")), "test": pretty_optional(scores.get("test"))})
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
        complete_rows = [row for row in report.get("subjects", []) if row.get("complete") and row.get("total") is not None]; all_complete = bool(report.get("subjects")) and len(complete_rows) == len(report.get("subjects", [])); provisional_total = round(sum(safe_float(row.get("total")) for row in complete_rows), 2) if complete_rows else None; provisional_average = round(provisional_total / len(complete_rows), 2) if complete_rows else None
        report["subjects_complete"] = len(complete_rows); report["academic_complete"] = all_complete; report["academic_partial"] = bool(report.get("subjects")) and not all_complete; report["provisional_total"] = pretty_optional(provisional_total); report["provisional_average"] = pretty_optional(provisional_average); report["total_score"] = pretty_optional(provisional_total) if all_complete else None; report["average"] = pretty_optional(provisional_average) if all_complete else None; report["grade"] = grade_for_score(provisional_average)[0] if all_complete and provisional_average is not None else "-"
    averages = [safe_float(report.get("average")) for report in reports if report.get("average") is not None]
    for report in reports:
        if report.get("average") is None: report.update({"position": 0, "position_text": "--", "out_of": 0}); continue
        position = compute_position(report.get("average"), averages); report.update({"position": position, "position_text": ordinal(position), "out_of": len(averages)})
    return {"class_average": pretty_number(sum(averages) / len(averages)) if averages else None, "highest_average": pretty_number(max(averages)) if averages else None, "lowest_average": pretty_number(min(averages)) if averages else None}


def build_manual_report_payload(academic_session, term, class_level, class_arm, admission_numbers=None):
    academic_session, term = normalize_academic_session(academic_session), normalize_academic_term(term); level, arm = normalize_academic_class(class_level, class_arm); students = get_students_for_class(level, arm, active_only=True); requested = set(normalize_admission_selection(admission_numbers)); store = _read_json_store(MANUAL_FILE); saved_attendance = get_attendance_summary_map(academic_session, term, level, arm); reports, source_students, catalog = [], [], set()
    for student in students:
        admission = normalize_admission_number(student.get("admission_number")); record = store.get(manual_context_key(academic_session, term, level, arm, admission), {}) if admission else {}; record_subjects = record.get("subjects") if isinstance(record.get("subjects"), dict) else {}; allowed = expected_subject_map(student, level, arm); rows = []
        for subject_key in allowed:
            entry = record_subjects.get(subject_key)
            if not isinstance(entry, dict): continue
            row = build_manual_subject_row(level, entry); rows.append(row); catalog.add(subject_key)
        manual_attendance = record.get("attendance") if isinstance(record.get("attendance"), dict) else {}; attendance = manual_attendance or saved_attendance.get(admission, {}); has_manual = bool(rows or manual_attendance); source_students.append({**student, "has_manual": has_manual, "manual_status": clean(record.get("status") or ""), "manual_subject_count": len(rows), "has_attendance": bool(attendance)})
        if not has_manual: continue
        reports.append({"admission_number": student.get("admission_number"), "full_name": student.get("full_name"), "last_name": student.get("last_name"), "first_name": student.get("first_name"), "other_names": student.get("other_names"), "sex": student.get("sex"), "class_level": level, "class_arm": arm, "session": academic_session, "term": term, "term_label": academic_term_label(term), "subjects": rows, "subject_count": len(rows), "has_ca": any(row.get("has_ca") for row in rows), "has_exam": any(row.get("has_exam") for row in rows), "has_attendance": bool(attendance), "attendance": attendance, "source_mode": "manual", "manual_status": clean(record.get("status") or "DRAFT"), "manual_updated_at": clean(record.get("updated_at")), "result_name": "", "teacher_remark": "", "principal_remark": "", "missing_ca_subjects": [row.get("subject_key") for row in rows if not row.get("has_ca")], "missing_exam_subjects": [row.get("subject_key") for row in rows if not row.get("has_exam")]})
    stats = finalize_report_statistics(reports); payload = {"success": bool(reports), "session": academic_session, "term": term, "term_label": academic_term_label(term), "class_level": level, "class_arm": arm, "students": source_students, "reports": reports, "blocked_students": [], "readiness_warnings": [], "source_status": {"students": bool(students), "manual": bool(reports), "attendance": bool(saved_attendance)}, "summary": {"students_in_class": len(students), "generated": len(reports), "manual_ready": len(reports), "subjects": len(catalog), **stats}}
    payload = apply_saved_report_details(payload)
    for report in payload.get("reports", []): report["result_name"] = result_file_stem(report)
    if requested:
        payload["reports"] = [report for report in payload.get("reports", []) if normalize_admission_number(report.get("admission_number")) in requested]; payload["summary"]["generated"] = len(payload["reports"]); payload["success"] = bool(payload["reports"])
    return payload


def merge_hybrid_subject_row(class_level, auto_row=None, manual_row=None, prefer_manual=False):
    auto_row, manual_row = auto_row if isinstance(auto_row, dict) else {}, manual_row if isinstance(manual_row, dict) else {}; is_jss = clean_upper(class_level).startswith("JSS"); fields = ["ca1", "ca2", "test1", "test2", "exam"] if is_jss else ["ass1", "ass2", "test", "exam"]
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
    stats = finalize_report_statistics(reports); auto["summary"] = {**(auto.get("summary") or {}), **stats, "generated": len(reports), "hybrid_manual_subjects_used": sum(int(report.get("manual_subjects_used") or 0) for report in reports)}; auto = apply_saved_report_details(auto)
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


def build_term_report_payload(academic_session, term, class_level, class_arm, result_year="", admission_number="", include_cumulative=True, admission_numbers=None):
    # Build the full class first so Manual Studio values still receive correct class
    # statistics/positions, then filter to the requested student(s).
    payload = _AUTO_BUILD_TERM_REPORT_PAYLOAD(academic_session, term, class_level, class_arm, result_year, "", include_cumulative, None)
    payload = apply_saved_manual_score_overrides(payload); payload = apply_manual_attendance_overrides(payload)
    if normalize_academic_term(term) == "THIRD" and include_cumulative and payload.get("reports"): attach_cumulative_results(payload, normalize_academic_session(academic_session), payload.get("class_level") or class_level, payload.get("class_arm") or class_arm, resolve_result_year(academic_session, result_year, payload.get("class_level") or class_level, payload.get("class_arm") or class_arm))
    requested = normalize_admission_selection(admission_numbers); single = normalize_admission_number(admission_number)
    if single and single not in requested: requested.insert(0, single)
    if requested:
        wanted = set(requested); payload["reports"] = [report for report in payload.get("reports", []) if normalize_admission_number(report.get("admission_number")) in wanted]; payload["students"] = [student for student in payload.get("students", []) if normalize_admission_number(student.get("admission_number")) in wanted]; payload["blocked_students"] = [student for student in payload.get("blocked_students", []) if normalize_admission_number(student.get("admission_number")) in wanted]; payload["readiness_warnings"] = [student for student in payload.get("readiness_warnings", []) if normalize_admission_number(student.get("admission_number")) in wanted]; payload["summary"] = dict(payload.get("summary") or {}); payload["summary"]["generated"] = len(payload["reports"]); payload["summary"]["blocked"] = len(payload.get("blocked_students", [])); payload["summary"]["selected_requested"] = len(requested); payload["success"] = bool(payload["reports"])
    return payload


# ============================================================
# API — MANUAL REPORT STUDIO
# ============================================================

@report_sheet_bp.route("/api/report-sheets/manual", methods=["GET", "POST", "DELETE"])
@report_staff_required
def api_report_manual():
    source = request.get_json(silent=True) or {} if request.method != "GET" else request.args; class_level, class_arm = request_class_values(source); level, arm, error = resolve_class(class_level, class_arm, require_arm=True)
    if error: return jsonify({"success": False, "message": error}), 400
    academic_session, term = resolve_context(source.get("session"), source.get("term")); admission = normalize_admission_number(source.get("admission_number") or source.get("admission"))
    if not academic_session or not term: return jsonify({"success": False, "message": "Session and term are required."}), 400
    roster = get_students_for_class(level, arm, active_only=True); roster_map = {normalize_admission_number(student.get("admission_number")): student for student in roster}; store = _read_json_store(MANUAL_FILE)
    if request.method == "GET":
        record = store.get(manual_context_key(academic_session, term, level, arm, admission), {}) if admission else {}; summaries = {key: manual_record_summary(value) for key, value in store.items() if isinstance(value, dict) and normalize_academic_session(value.get("session")) == academic_session and normalize_academic_term(value.get("term")) == term and value.get("class_level") == level and value.get("class_arm") == arm}
        by_admission = {clean(value.get("admission_number")): manual_record_summary(value) for value in store.values() if isinstance(value, dict) and normalize_academic_session(value.get("session")) == academic_session and normalize_academic_term(value.get("term")) == term and value.get("class_level") == level and value.get("class_arm") == arm}
        return jsonify({"success": True, "session": academic_session, "term": term, "class_level": level, "class_arm": arm, "students": roster, "subjects": get_subjects_for_selection(level, arm), "score_fields": manual_score_fields(level), "record": record, "record_summaries": by_admission, "count": len(summaries)})
    if not admission or admission not in roster_map: return jsonify({"success": False, "message": "Select a valid active student from this class."}), 400
    key = manual_context_key(academic_session, term, level, arm, admission)
    if request.method == "DELETE":
        if key not in store: return jsonify({"success": False, "message": "No manual record exists for this student."}), 404
        del store[key]; _write_json_store(MANUAL_FILE, store); return jsonify({"success": True, "message": "Manual student record deleted successfully.", "admission_number": admission})
    try: record = save_manual_record(academic_session, term, level, arm, admission, source)
    except ValueError as error: return jsonify({"success": False, "message": str(error)}), 400
    return jsonify({"success": True, "message": f"Manual report draft saved for {roster_map[admission].get('full_name') or admission}.", "record": record, "summary": manual_record_summary(record)})


@report_sheet_bp.route("/api/report-sheets/manual/generate", methods=["POST"])
@report_staff_required
def api_report_manual_generate():
    data = request.get_json(silent=True) or {}; class_level, class_arm = request_class_values(data); level, arm, error = resolve_class(class_level, class_arm, require_arm=True)
    if error: return jsonify({"success": False, "message": error}), 400
    academic_session, term = resolve_context(data.get("session"), data.get("term")); mode = clean(data.get("mode") or "manual").lower(); admissions = data.get("admission_numbers") or data.get("admissions") or ([data.get("admission_number")] if data.get("admission_number") else [])
    if mode not in {"manual", "hybrid"}: return jsonify({"success": False, "message": "Manual generation mode must be manual or hybrid."}), 400
    payload = build_manual_report_payload(academic_session, term, level, arm, admissions) if mode == "manual" else build_hybrid_report_payload(academic_session, term, level, arm, data.get("year"), admissions)
    if not payload.get("reports"): return jsonify({**payload, "message": "No manual report data is available for the requested student selection."}), 400
    if data.get("save_snapshot", True):
        snapshots = save_report_snapshots(payload["reports"]); snap_map = {normalize_admission_number(item.get("admission_number")): item for item in snapshots}
        for report in payload["reports"]:
            snap = snap_map.get(normalize_admission_number(report.get("admission_number")), {}); report["snapshot_id"] = snap.get("snapshot_id", ""); report["result_name"] = snap.get("result_name") or result_file_stem(report)
        payload["saved_snapshots"] = [{"snapshot_id": item.get("snapshot_id"), "admission_number": item.get("admission_number"), "full_name": item.get("full_name"), "result_name": item.get("result_name"), "generated_at": item.get("generated_at")} for item in snapshots]
    payload["message"] = f"{len(payload['reports'])} {mode} report sheet(s) generated successfully."
    return jsonify(payload)


# ============================================================
# API — CLASS-WIDE REMARKS / TRAITS / ATTENDANCE
# ============================================================

@report_sheet_bp.route("/api/report-sheets/bulk-details", methods=["POST"])
@report_staff_required
def api_report_bulk_details():
    data = request.get_json(silent=True) or {}; class_level, class_arm = request_class_values(data); level, arm, error = resolve_class(class_level, class_arm, require_arm=True)
    if error: return jsonify({"success": False, "message": error}), 400
    academic_session, term = resolve_context(data.get("session"), data.get("term")); roster = get_students_for_class(level, arm, active_only=True); admissions = normalize_admission_selection(data.get("admission_numbers") or data.get("admissions")); scope = clean(data.get("scope") or "selected").lower()
    if scope == "all" or not admissions: admissions = [normalize_admission_number(student.get("admission_number")) for student in roster if normalize_admission_number(student.get("admission_number"))]
    wanted = set(admissions); selected = [student for student in roster if normalize_admission_number(student.get("admission_number")) in wanted]
    if not selected: return jsonify({"success": False, "message": "No students matched the bulk-apply selection."}), 400
    details_store = _read_json_store(DETAILS_FILE); manual_store = _read_json_store(MANUAL_FILE); attendance_payload = data.get("attendance") if isinstance(data.get("attendance"), dict) else None
    try: normalized_attendance = normalize_manual_attendance(attendance_payload) if attendance_payload is not None else None
    except ValueError as error: return jsonify({"success": False, "message": str(error)}), 400
    average_payload = build_hybrid_report_payload(academic_session, term, level, arm) if data.get("auto_teacher_remark") or data.get("auto_principal_remark") else None; average_map = {normalize_admission_number(report.get("admission_number")): optional_float(report.get("average")) for report in (average_payload or {}).get("reports", [])}
    for student in selected:
        admission = normalize_admission_number(student.get("admission_number")); key = report_context_key(academic_session, term, level, arm, admission); current = details_store.get(key, {}) if isinstance(details_store.get(key), dict) else {}; detail_data = {}
        for field in ["form_teacher", "teacher_remark", "principal_remark", "next_term"]:
            if field in data: detail_data[field] = data.get(field)
        if data.get("auto_teacher_remark"): detail_data["teacher_remark"] = teacher_remark(average_map.get(admission)) if average_map.get(admission) is not None else clean(data.get("teacher_remark"))
        if data.get("auto_principal_remark"): detail_data["principal_remark"] = principal_remark(average_map.get(admission)) if average_map.get(admission) is not None else clean(data.get("principal_remark"))
        if isinstance(data.get("affective"), dict): detail_data["affective"] = data.get("affective")
        if isinstance(data.get("psychomotor"), dict): detail_data["psychomotor"] = data.get("psychomotor")
        if detail_data: details_store[key] = normalize_report_details(detail_data, current)
        if normalized_attendance is not None:
            mkey = manual_context_key(academic_session, term, level, arm, admission); record = manual_store.get(mkey, {}) if isinstance(manual_store.get(mkey), dict) else {}; record.update({"session": academic_session, "term": term, "class_level": level, "class_arm": arm, "admission_number": clean(student.get("admission_number")), "attendance": normalized_attendance, "attendance_override_enabled": bool(data.get("attendance_override_enabled", True)), "status": clean(record.get("status") or "DRAFT"), "subjects": record.get("subjects", {}), "prefer_manual_scores": bool(record.get("prefer_manual_scores", False)), "updated_at": now_string(), "updated_by": clean(session.get("admin_username") or session.get("username") or session.get("user") or "Staff")}); manual_store[mkey] = record
    if any(key in data for key in ["form_teacher", "teacher_remark", "principal_remark", "next_term", "affective", "psychomotor", "auto_teacher_remark", "auto_principal_remark"]): _write_json_store(DETAILS_FILE, details_store)
    if normalized_attendance is not None: _write_json_store(MANUAL_FILE, manual_store)
    return jsonify({"success": True, "message": f"Class-wide report details applied to {len(selected)} student(s).", "count": len(selected), "admission_numbers": [student.get("admission_number") for student in selected], "attendance": normalized_attendance})
