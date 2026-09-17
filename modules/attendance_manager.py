# MODULE: Attendance Manager — EMIS daily attendance, history and term-summary engine

import csv
import shutil
from pathlib import Path
from datetime import datetime
from threading import RLock
from functools import wraps

from flask import Blueprint, jsonify, request, session

from modules.academic_records import clean, clean_upper, safe_bool, normalize_academic_session, normalize_academic_term, academic_term_label, get_current_academic_context, normalize_academic_class, validate_class_selection, get_students_for_class, get_student, student_display_name
from modules.student_lookup import normalize_admission_number
from modules.result_sync import queue_emis_event_safely

attendance_bp = Blueprint("attendance_bp", __name__)

BASE_DIR = Path(__file__).resolve().parent.parent
ATTENDANCE_DIR = BASE_DIR / "static" / "data" / "attendance"
BACKUP_DIR = ATTENDANCE_DIR / "backups"

VALID_STATUSES = {"PRESENT", "ABSENT", "LATE", "SICK", "EXCUSED", "UNMARKED"}
ATTENDANCE_CREDIT_STATUSES = {"PRESENT", "LATE", "EXCUSED"}
ATTENDANCE_HEADERS = ["Date", "Session", "Term", "Class", "Class_category", "Admission_number", "Last_name", "First_name", "Other_names", "Status", "Reason", "Note", "Saved_at", "Record_type"]

ATTENDANCE_LOCK = RLock()


# ============================================================
# ACCESS / BASIC HELPERS
# ============================================================

def attendance_staff_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if clean(session.get("user_type")).lower() not in {"admin", "teacher"}: return jsonify({"success": False, "message": "Unauthorized."}), 403
        return view(*args, **kwargs)
    return wrapped


def now_string(): return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def normalize_date(value):
    raw = clean(value)
    if not raw: return ""
    try: return datetime.strptime(raw, "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError: return ""


def date_metadata(value):
    date_value = normalize_date(value)
    if not date_value: return {"date": "", "day": "", "month": "", "week": 0}
    parsed = datetime.strptime(date_value, "%Y-%m-%d")
    return {"date": date_value, "day": parsed.strftime("%A"), "month": parsed.strftime("%B"), "week": int(parsed.strftime("%V"))}


def safe_filename(value):
    value = clean_upper(value).replace("/", "-").replace("\\", "-").replace(" ", "_")
    return "".join(ch for ch in value if ch.isalnum() or ch in {"_", "-"}) or "UNKNOWN"


def full_name_from_row(row):
    return " ".join(part for part in [clean(row.get("Last_name")), clean(row.get("First_name")), clean(row.get("Other_names"))] if part).strip()


def attendance_file_path(class_arm):
    ATTENDANCE_DIR.mkdir(parents=True, exist_ok=True)
    return ATTENDANCE_DIR / f"attendance_{safe_filename(class_arm)}.csv"


def iter_attendance_files():
    if not ATTENDANCE_DIR.exists(): return []
    return sorted(path for path in ATTENDANCE_DIR.glob("attendance_*.csv") if path.is_file())


def backup_attendance_file(class_arm, reason="update"):
    path = attendance_file_path(class_arm)
    if not path.exists(): return ""

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup = BACKUP_DIR / f"{path.stem}_{safe_filename(reason)}_{stamp}.csv"
    shutil.copy2(path, backup)
    return str(backup)


def read_attendance_path(path):
    path = Path(path)
    if not path.exists(): return []

    with ATTENDANCE_LOCK:
        with path.open("r", newline="", encoding="utf-8-sig") as file: return list(csv.DictReader(file))


def read_attendance_rows(class_arm): return read_attendance_path(attendance_file_path(class_arm))


def read_all_attendance_rows():
    rows = []
    for path in iter_attendance_files(): rows.extend(read_attendance_path(path))
    return rows


def write_attendance_rows(class_arm, rows):
    path = attendance_file_path(class_arm)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(".tmp")

    with ATTENDANCE_LOCK:
        with temp_path.open("w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(file, fieldnames=ATTENDANCE_HEADERS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)

        temp_path.replace(path)

    return path


# ============================================================
# REQUEST / RECORD NORMALIZATION
# ============================================================

def resolve_academic_context(session_value="", term_value=""):
    context = get_current_academic_context(session_value, term_value)
    return normalize_academic_session(context.get("academic_session") or context.get("session")), normalize_academic_term(context.get("term"))


def resolve_optional_context(session_value="", term_value=""):
    academic_session = normalize_academic_session(session_value) if clean(session_value) else ""
    term = normalize_academic_term(term_value) if clean(term_value) else ""
    return academic_session, term


def resolve_class_selection(class_level="", class_arm="", require_arm=True):
    level, arm = normalize_academic_class(class_level or class_arm, class_arm or class_level)
    validation = validate_class_selection(level, class_arm or arm, require_arm=require_arm)

    if not validation.get("valid"): return "", "", validation.get("message") or "Invalid class selection."
    return validation["class_level"], validation["class_arm"], ""


def request_class_values(source=None):
    source = source or request.args
    class_level = source.get("class_level") or source.get("class_category") or source.get("level") or source.get("class") or ""
    class_arm = source.get("class_arm") or source.get("arm") or source.get("class_name") or source.get("class") or ""
    return class_level, class_arm


def record_matches(row, academic_session="", term="", class_level="", class_arm="", date_value=""):
    if academic_session and normalize_academic_session(row.get("Session")) != academic_session: return False
    if term and normalize_academic_term(row.get("Term")) != term: return False
    if class_level and normalize_academic_class(row.get("Class_category") or row.get("Class"), row.get("Class"))[0] != class_level: return False
    if class_arm and normalize_academic_class(row.get("Class_category") or row.get("Class"), row.get("Class"))[1] != class_arm: return False
    if date_value and normalize_date(row.get("Date")) != date_value: return False
    return True


def filtered_attendance_rows(class_arm, academic_session="", term="", class_level="", date_value=""):
    return [row for row in read_attendance_rows(class_arm) if record_matches(row, academic_session, term, class_level, class_arm, date_value)]


def normalize_status(value):
    status = clean_upper(value)
    return status if status in VALID_STATUSES else "UNMARKED"


def row_status(row):
    if clean_upper(row.get("Record_type")) == "HOLIDAY" or clean_upper(row.get("Status")) == "HOLIDAY": return "HOLIDAY"
    return normalize_status(row.get("Status"))


def history_record(row):
    meta = date_metadata(row.get("Date"))
    level, arm = normalize_academic_class(row.get("Class_category") or row.get("Class"), row.get("Class"))
    status = row_status(row)

    return {
        **meta, "session": normalize_academic_session(row.get("Session")), "term": normalize_academic_term(row.get("Term")),
        "term_label": academic_term_label(row.get("Term")), "class": arm, "class_arm": arm, "class_category": level, "class_level": level,
        "admission_number": clean(row.get("Admission_number")), "last_name": clean(row.get("Last_name")), "first_name": clean(row.get("First_name")),
        "other_names": clean(row.get("Other_names")), "full_name": full_name_from_row(row), "status": status,
        "reason": clean(row.get("Reason")), "note": clean(row.get("Note")), "saved_at": clean(row.get("Saved_at")),
        "record_type": "HOLIDAY" if status == "HOLIDAY" else "DAILY",
    }


def build_daily_row(student, date_value, academic_session, term, class_level, class_arm, status="UNMARKED", reason="", note="", saved_at=""):
    return {
        "Date": date_value, "Session": academic_session, "Term": term, "Class": class_arm, "Class_category": class_level,
        "Admission_number": clean(student.get("admission_number") or student.get("id")), "Last_name": clean(student.get("last_name")),
        "First_name": clean(student.get("first_name")), "Other_names": clean(student.get("other_names")), "Status": normalize_status(status),
        "Reason": clean(reason), "Note": clean(note), "Saved_at": saved_at or now_string(), "Record_type": "DAILY",
    }


def build_holiday_row(date_value, academic_session, term, class_level, class_arm, reason="", note="", saved_at=""):
    return {
        "Date": date_value, "Session": academic_session, "Term": term, "Class": class_arm, "Class_category": class_level,
        "Admission_number": "", "Last_name": "", "First_name": "", "Other_names": "", "Status": "HOLIDAY",
        "Reason": clean(reason) or "HOLIDAY", "Note": clean(note), "Saved_at": saved_at or now_string(), "Record_type": "HOLIDAY",
    }


# ============================================================
# ATTENDANCE SUMMARY ENGINE
# ============================================================

def get_term_rows(academic_session, term, class_level, class_arm):
    academic_session, term = normalize_academic_session(academic_session), normalize_academic_term(term)
    level, arm = normalize_academic_class(class_level, class_arm)

    if not academic_session or not term or not level or not arm: return []
    return filtered_attendance_rows(arm, academic_session, term, level)


def get_open_and_holiday_dates(rows):
    open_dates = {normalize_date(row.get("Date")) for row in rows if row_status(row) != "HOLIDAY" and normalize_date(row.get("Date"))}
    holiday_dates = {normalize_date(row.get("Date")) for row in rows if row_status(row) == "HOLIDAY" and normalize_date(row.get("Date"))}
    open_dates -= holiday_dates
    return sorted(open_dates), sorted(holiday_dates)


def blank_student_summary(admission_number="", full_name="", days_open=0):
    return {
        "admission_number": clean(admission_number), "full_name": clean(full_name), "days_open": int(days_open), "days_school_open": int(days_open),
        "present": 0, "days_present": 0, "absent": 0, "days_absent": 0, "late": 0, "days_late": 0,
        "sick": 0, "days_sick": 0, "excused": 0, "days_excused": 0, "unmarked": 0,
        "present_credit": 0, "attendance_score": 0, "absent_total": 0, "attendance_percentage": 0.0,
    }


def finalize_student_summary(summary):
    summary["present_credit"] = summary["present"] + summary["late"] + summary["excused"]
    summary["attendance_score"] = summary["present_credit"]
    summary["absent_total"] = summary["absent"] + summary["sick"] + summary["unmarked"]
    summary["attendance_percentage"] = round((summary["present_credit"] / summary["days_open"]) * 100, 1) if summary["days_open"] else 0.0

    summary.update({
        "days_school_open": summary["days_open"], "days_present": summary["present_credit"], "days_absent": summary["absent_total"],
        "days_late": summary["late"], "days_sick": summary["sick"], "days_excused": summary["excused"],
    })

    return summary


def summarize_student_rows(rows, admission_number, days_open=None, full_name=""):
    admission_key = normalize_admission_number(admission_number)
    open_dates, _ = get_open_and_holiday_dates(rows)

    if days_open is None: days_open = len(open_dates)

    summary, student_rows = blank_student_summary(admission_number, full_name, days_open), {}

    for row in rows:
        if row_status(row) == "HOLIDAY" or normalize_admission_number(row.get("Admission_number")) != admission_key: continue
        date_value = normalize_date(row.get("Date"))
        if date_value: student_rows[date_value] = row

    for date_value in open_dates:
        row = student_rows.get(date_value)

        if not row:
            summary["unmarked"] += 1
            continue

        status = normalize_status(row.get("Status"))

        if status == "PRESENT": summary["present"] += 1
        elif status == "ABSENT": summary["absent"] += 1
        elif status == "LATE": summary["late"] += 1
        elif status == "SICK": summary["sick"] += 1
        elif status == "EXCUSED": summary["excused"] += 1
        else: summary["unmarked"] += 1

    return finalize_student_summary(summary)


def summarize_student_history_rows(rows, admission_number="", full_name=""):
    daily_map = {}

    for row in rows:
        if row_status(row) == "HOLIDAY": continue
        date_value = normalize_date(row.get("Date"))
        if date_value: daily_map[date_value] = row

    summary = blank_student_summary(admission_number, full_name, len(daily_map))

    for row in daily_map.values():
        status = normalize_status(row.get("Status"))

        if status == "PRESENT": summary["present"] += 1
        elif status == "ABSENT": summary["absent"] += 1
        elif status == "LATE": summary["late"] += 1
        elif status == "SICK": summary["sick"] += 1
        elif status == "EXCUSED": summary["excused"] += 1
        else: summary["unmarked"] += 1

    return finalize_student_summary(summary)


def get_student_attendance_summary(admission_number, academic_session, term, class_level="", class_arm=""):
    student = get_student(admission_number, active_only=False)

    level, arm = normalize_academic_class(
        class_level or (student or {}).get("class_level") or (student or {}).get("class_category"),
        class_arm or (student or {}).get("class_arm") or (student or {}).get("class"),
    )

    if not level or not arm: return blank_student_summary(admission_number, student_display_name(student or {}), 0)

    rows = get_term_rows(academic_session, term, level, arm)
    open_dates, holiday_dates = get_open_and_holiday_dates(rows)
    summary = summarize_student_rows(rows, admission_number, len(open_dates), student_display_name(student or {}))

    summary.update({
        "session": normalize_academic_session(academic_session), "term": normalize_academic_term(term), "term_label": academic_term_label(term),
        "class_level": level, "class_arm": arm, "holiday_days": len(holiday_dates),
    })

    return summary


def get_class_attendance_summary(academic_session, term, class_level, class_arm):
    level, arm = normalize_academic_class(class_level, class_arm)
    rows = get_term_rows(academic_session, term, level, arm)
    open_dates, holiday_dates = get_open_and_holiday_dates(rows)

    roster = get_students_for_class(level, arm, active_only=True)
    known = {normalize_admission_number(student.get("admission_number")): student for student in roster}

    for row in rows:
        admission = normalize_admission_number(row.get("Admission_number"))
        if not admission or admission in known: continue
        known[admission] = {"admission_number": row.get("Admission_number"), "full_name": full_name_from_row(row)}

    students = []

    for admission, student in sorted(known.items(), key=lambda item: clean(item[1].get("full_name")).lower()):
        students.append(summarize_student_rows(rows, admission, len(open_dates), student.get("full_name") or student_display_name(student)))

    class_percentage = round(sum(item["attendance_percentage"] for item in students) / len(students), 1) if students else 0.0

    return {
        "session": normalize_academic_session(academic_session), "term": normalize_academic_term(term), "term_label": academic_term_label(term),
        "class_level": level, "class_arm": arm, "days_open": len(open_dates), "days_school_open": len(open_dates),
        "holiday_days": len(holiday_dates), "open_dates": open_dates, "holiday_dates": holiday_dates,
        "students_count": len(students), "class_attendance_percentage": class_percentage, "students": students,
    }


def get_attendance_summary_map(academic_session, term, class_level, class_arm):
    summary = get_class_attendance_summary(academic_session, term, class_level, class_arm)
    return {normalize_admission_number(item.get("admission_number")): item for item in summary.get("students", [])}


# ============================================================
# HISTORY ENGINE
# ============================================================

def history_scope_rows(class_level, class_arm, academic_session="", term="", start_date="", end_date=""):
    level, arm = normalize_academic_class(class_level, class_arm)
    start_date, end_date = normalize_date(start_date), normalize_date(end_date)
    rows = []

    for row in read_attendance_rows(arm):
        if not record_matches(row, academic_session, term, level, arm): continue

        date_value = normalize_date(row.get("Date"))

        if start_date and (not date_value or date_value < start_date): continue
        if end_date and (not date_value or date_value > end_date): continue

        rows.append(row)

    return rows


def history_search_match(row, search_text):
    search_text = clean(search_text).lower()
    if not search_text: return True

    haystack = " ".join([
        clean(row.get("Date")), clean(row.get("Session")), clean(row.get("Term")), clean(row.get("Class")),
        clean(row.get("Admission_number")), full_name_from_row(row), row_status(row), clean(row.get("Reason")), clean(row.get("Note"))
    ]).lower()

    return search_text in haystack


def filter_history_records(rows, status="", search_text=""):
    status = clean_upper(status)
    output = []

    for row in rows:
        if status and row_status(row) != status: continue
        if search_text and not history_search_match(row, search_text): continue
        output.append(row)

    return output


def history_summary(rows):
    open_dates, holiday_dates = get_open_and_holiday_dates(rows)
    counts = {"present": 0, "absent": 0, "late": 0, "sick": 0, "excused": 0, "unmarked": 0}

    for row in rows:
        key = row_status(row).lower()
        if key in counts: counts[key] += 1

    return {
        "total_records": len(rows), "days_open": len(open_dates), "days_school_open": len(open_dates),
        "present": counts["present"], "absent": counts["absent"], "late": counts["late"],
        "sick": counts["sick"], "excused": counts["excused"], "unmarked": counts["unmarked"], "holiday": len(holiday_dates),
    }


def build_daily_breakdown(rows):
    grouped = {}

    for row in rows:
        date_value = normalize_date(row.get("Date"))
        if not date_value: continue

        item = grouped.setdefault(date_value, {
            **date_metadata(date_value), "records": 0, "present": 0, "absent": 0, "late": 0,
            "sick": 0, "excused": 0, "unmarked": 0, "holiday": 0, "record_type": "DAILY",
        })

        status = row_status(row)

        if status == "HOLIDAY":
            item["holiday"] = 1
            item["record_type"] = "HOLIDAY"
            continue

        item["records"] += 1
        key = status.lower()

        if key in item: item[key] += 1

    return sorted(grouped.values(), key=lambda item: item["date"], reverse=True)


def build_saved_date_history_from_rows(rows):
    grouped = {}

    for row in rows:
        date_value = normalize_date(row.get("Date"))
        if not date_value: continue

        item = grouped.setdefault(date_value, {
            **date_metadata(date_value), "record_type": "DAILY", "saved_at": "", "reason": "", "note": "",
            "total": 0, "records": 0, "present": 0, "absent": 0, "late": 0, "sick": 0,
            "excused": 0, "unmarked": 0, "holiday": 0,
        })

        item["saved_at"] = clean(row.get("Saved_at")) or item["saved_at"]
        status = row_status(row)

        if status == "HOLIDAY":
            item["record_type"] = "HOLIDAY"
            item["holiday"] = 1
            item["reason"] = clean(row.get("Reason"))
            item["note"] = clean(row.get("Note"))
            continue

        item["total"] += 1
        item["records"] += 1
        key = status.lower()

        if key in item: item[key] += 1

    return sorted(grouped.values(), key=lambda item: item["date"], reverse=True)


def build_saved_date_history(academic_session, term, class_level, class_arm):
    return build_saved_date_history_from_rows(get_term_rows(academic_session, term, class_level, class_arm))


def build_student_breakdown(rows, search_text=""):
    open_dates, _ = get_open_and_holiday_dates(rows)
    known = {}

    for row in rows:
        if row_status(row) == "HOLIDAY": continue

        admission = normalize_admission_number(row.get("Admission_number"))
        if not admission: continue

        item = known.setdefault(admission, {
            "admission_number": clean(row.get("Admission_number")), "full_name": full_name_from_row(row),
            "class_arm": clean(row.get("Class")), "class_level": clean(row.get("Class_category")),
        })

        if not item.get("full_name"): item["full_name"] = full_name_from_row(row)

    results = []
    search = clean(search_text).lower()

    for admission, identity in known.items():
        if search and search not in clean(identity.get("admission_number")).lower() and search not in clean(identity.get("full_name")).lower(): continue

        summary = summarize_student_rows(rows, admission, len(open_dates), identity.get("full_name"))
        summary.update({"class": identity.get("class_arm"), "class_arm": identity.get("class_arm"), "class_level": identity.get("class_level")})
        results.append(summary)

    return sorted(results, key=lambda item: (clean(item.get("full_name")).lower(), clean(item.get("admission_number")).lower()))


def build_history_payload(class_level, class_arm, academic_session="", term="", start_date="", end_date="", status="", search_text=""):
    scope_rows = history_scope_rows(class_level, class_arm, academic_session, term, start_date, end_date)
    visible_rows = filter_history_records(scope_rows, status, search_text)

    records = sorted([history_record(row) for row in visible_rows], key=lambda row: (row["date"], row["saved_at"]), reverse=True)
    daily = build_daily_breakdown(visible_rows)
    students = build_student_breakdown(scope_rows, search_text)
    dates = build_saved_date_history_from_rows(scope_rows)

    return {
        "records": records, "daily_breakdown": daily, "student_breakdown": students, "saved_dates": dates,
        "summary": history_summary(scope_rows), "total_records": len(records), "scope_total_records": len(scope_rows),
    }


def get_register_for_date(academic_session, term, class_level, class_arm, date_value):
    level, arm = normalize_academic_class(class_level, class_arm)
    date_value = normalize_date(date_value)

    rows = filtered_attendance_rows(arm, normalize_academic_session(academic_session), normalize_academic_term(term), level, date_value)
    holiday = next((row for row in rows if row_status(row) == "HOLIDAY"), None)

    if holiday:
        return {
            "saved": True, "holiday": True, "date": date_value, "reason": clean(holiday.get("Reason")),
            "note": clean(holiday.get("Note")), "saved_at": clean(holiday.get("Saved_at")),
            "students": [], "existing_count": 1,
        }

    saved_map = {
        normalize_admission_number(row.get("Admission_number")): row
        for row in rows if row_status(row) != "HOLIDAY" and normalize_admission_number(row.get("Admission_number"))
    }

    roster, students = get_students_for_class(level, arm, active_only=True), []

    for student in roster:
        admission = normalize_admission_number(student.get("admission_number"))
        saved = saved_map.get(admission)

        students.append({
            **student, "status": normalize_status(saved.get("Status")) if saved else "UNMARKED",
            "attendance_status": normalize_status(saved.get("Status")) if saved else "UNMARKED",
            "reason": clean(saved.get("Reason")) if saved else "", "note": clean(saved.get("Note")) if saved else "",
            "saved_at": clean(saved.get("Saved_at")) if saved else "",
        })

    return {
        "saved": bool(rows), "holiday": False, "date": date_value,
        "students": students, "count": len(students), "existing_count": len(rows),
    }




# ============================================================
# SYNC HELPERS
# ============================================================

def attendance_sync_entity_key(academic_session, term, class_arm, date_value):
    return "|".join([clean(academic_session), clean_upper(term), clean_upper(class_arm), clean(date_value)])


def queue_attendance_scope_sync(academic_session, term, class_level, class_arm, date_value, rows):
    payload = {
        "session": normalize_academic_session(academic_session), "term": normalize_academic_term(term),
        "class_level": clean_upper(class_level), "class_arm": clean_upper(class_arm),
        "date": normalize_date(date_value), "rows": [dict(row) for row in (rows or [])],
    }
    return queue_emis_event_safely(
        "attendance", "replace_scope", payload,
        entity_key=attendance_sync_entity_key(payload["session"], payload["term"], payload["class_arm"], payload["date"]),
    )


def apply_attendance_sync_event(action, payload, event=None):
    if clean(action).lower() != "replace_scope": raise ValueError(f"Unsupported attendance sync action: {action}")
    if not isinstance(payload, dict): raise ValueError("Attendance sync payload must be an object.")

    academic_session = normalize_academic_session(payload.get("session") or payload.get("academic_session"))
    term = normalize_academic_term(payload.get("term"))
    level, arm, error = resolve_class_selection(payload.get("class_level") or payload.get("class_category"), payload.get("class_arm") or payload.get("class"), require_arm=True)
    date_value = normalize_date(payload.get("date"))
    rows = payload.get("rows") or []

    if error: raise ValueError(error)
    if not academic_session or not term or not date_value: raise ValueError("Attendance sync requires session, term and date.")
    if not isinstance(rows, list): raise ValueError("Attendance synchronized rows must be a list.")

    normalized_rows = []
    for row in rows:
        if not isinstance(row, dict): continue
        item = {header: row.get(header, "") for header in ATTENDANCE_HEADERS}
        item["Session"], item["Term"], item["Class"], item["Class_category"], item["Date"] = academic_session, term, arm, level, date_value
        normalized_rows.append(item)

    with ATTENDANCE_LOCK:
        existing = read_attendance_rows(arm)
        if existing: backup_attendance_file(arm, "cloud_sync")
        remaining = [row for row in existing if not record_matches(row, academic_session, term, level, arm, date_value)]
        write_attendance_rows(arm, remaining + normalized_rows)

    return {"class_arm": arm, "date": date_value, "saved_count": len(normalized_rows), "deleted": not bool(normalized_rows)}


# ============================================================
# API — STUDENTS / REGISTER
# ============================================================

@attendance_bp.route("/api/attendance/students")
@attendance_staff_required
def api_attendance_students():
    class_level, class_arm = request_class_values()
    level, arm, error = resolve_class_selection(class_level, class_arm, require_arm=True)

    if error: return jsonify({"success": False, "message": error, "students": []}), 400

    academic_session, term = resolve_academic_context(request.args.get("session"), request.args.get("term"))
    students = get_students_for_class(level, arm, active_only=True)

    return jsonify({
        "success": True, "session": academic_session, "term": term, "term_label": academic_term_label(term),
        "class_level": level, "class_arm": arm, "students": students, "count": len(students),
    })


@attendance_bp.route("/api/attendance/records")
@attendance_staff_required
def api_attendance_records():
    class_level, class_arm = request_class_values()
    level, arm, error = resolve_class_selection(class_level, class_arm, require_arm=True)

    if error: return jsonify({"success": False, "message": error}), 400

    academic_session, term = resolve_academic_context(request.args.get("session"), request.args.get("term"))
    date_value = normalize_date(request.args.get("date") or datetime.now().strftime("%Y-%m-%d"))

    if not academic_session or not term: return jsonify({"success": False, "message": "Academic session and term are required."}), 400
    if not date_value: return jsonify({"success": False, "message": "A valid date is required."}), 400

    register = get_register_for_date(academic_session, term, level, arm, date_value)

    return jsonify({
        "success": True, "session": academic_session, "term": term,
        "class_level": level, "class_arm": arm, **register,
    })


# ============================================================
# API — SAVE DAILY ATTENDANCE
# ============================================================

@attendance_bp.route("/api/attendance/save", methods=["POST"])
@attendance_staff_required
def api_attendance_save():
    data = request.get_json(silent=True) or {}

    class_level, class_arm = request_class_values(data)
    level, arm, error = resolve_class_selection(class_level, class_arm, require_arm=True)

    if error: return jsonify({"success": False, "message": error}), 400

    academic_session, term = resolve_academic_context(data.get("session"), data.get("term"))
    date_value = normalize_date(data.get("date") or datetime.now().strftime("%Y-%m-%d"))
    overwrite, records = safe_bool(data.get("overwrite")), data.get("students") or data.get("records") or []

    if not academic_session or not term: return jsonify({"success": False, "message": "Academic session and term are required."}), 400
    if not date_value: return jsonify({"success": False, "message": "A valid attendance date is required."}), 400
    if not isinstance(records, list): return jsonify({"success": False, "message": "Attendance records must be a list."}), 400

    roster = get_students_for_class(level, arm, active_only=True)

    if not roster: return jsonify({"success": False, "message": f"No active students found in {arm}."}), 404

    roster_map = {normalize_admission_number(student.get("admission_number")): student for student in roster}
    submitted = {}

    for item in records:
        if not isinstance(item, dict): continue

        admission = normalize_admission_number(item.get("admission_number") or item.get("Admission_number") or item.get("id"))
        if not admission: continue

        if admission not in roster_map:
            return jsonify({"success": False, "message": f"Student {item.get('admission_number') or admission} is not an active member of {arm}."}), 400

        status = clean_upper(item.get("status") or item.get("Status") or "UNMARKED")

        if status not in VALID_STATUSES:
            return jsonify({"success": False, "message": f"Invalid attendance status '{status}' for {roster_map[admission].get('full_name') or admission}."}), 400

        submitted[admission] = {
            "status": status, "reason": clean(item.get("reason") or item.get("Reason")),
            "note": clean(item.get("note") or item.get("Note")),
        }

    saved_at, new_rows = now_string(), []

    for student in roster:
        admission = normalize_admission_number(student.get("admission_number"))
        value = submitted.get(admission, {"status": "UNMARKED", "reason": "", "note": ""})
        new_rows.append(build_daily_row(student, date_value, academic_session, term, level, arm, value["status"], value["reason"], value["note"], saved_at))

    with ATTENDANCE_LOCK:
        existing = read_attendance_rows(arm)
        matching = [row for row in existing if record_matches(row, academic_session, term, level, arm, date_value)]

        if matching and not overwrite:
            return jsonify({
                "success": False, "status": "exists", "message": f"Attendance for {arm} on {date_value} already exists.",
                "requires_overwrite": True, "existing_count": len(matching),
            }), 409

        backup = backup_attendance_file(arm, "overwrite" if matching else "save") if existing else ""
        remaining = [row for row in existing if not record_matches(row, academic_session, term, level, arm, date_value)]

        write_attendance_rows(arm, remaining + new_rows)

    counts = {status: 0 for status in VALID_STATUSES}

    for row in new_rows: counts[normalize_status(row.get("Status"))] += 1

    sync_info = queue_attendance_scope_sync(academic_session, term, level, arm, date_value, new_rows)

    return jsonify({
        "success": True, "message": "Attendance saved successfully.", "session": academic_session, "term": term,
        "class_level": level, "class_arm": arm, "date": date_value, "saved_count": len(new_rows),
        "overwrite": bool(matching), "counts": counts, "saved_at": saved_at, "backup": backup, "sync": sync_info,
    })


# ============================================================
# API — HOLIDAY
# ============================================================

@attendance_bp.route("/api/attendance/holiday", methods=["POST"])
@attendance_staff_required
def api_attendance_holiday():
    data = request.get_json(silent=True) or {}

    class_level, class_arm = request_class_values(data)
    level, arm, error = resolve_class_selection(class_level, class_arm, require_arm=True)

    if error: return jsonify({"success": False, "message": error}), 400

    academic_session, term = resolve_academic_context(data.get("session"), data.get("term"))
    date_value = normalize_date(data.get("date") or datetime.now().strftime("%Y-%m-%d"))
    overwrite, reason, note = safe_bool(data.get("overwrite")), clean(data.get("reason") or "HOLIDAY"), clean(data.get("note"))

    if not academic_session or not term: return jsonify({"success": False, "message": "Academic session and term are required."}), 400
    if not date_value: return jsonify({"success": False, "message": "A valid holiday date is required."}), 400

    holiday_row = build_holiday_row(date_value, academic_session, term, level, arm, reason, note)

    with ATTENDANCE_LOCK:
        existing = read_attendance_rows(arm)
        matching = [row for row in existing if record_matches(row, academic_session, term, level, arm, date_value)]

        if matching and not overwrite:
            return jsonify({
                "success": False, "status": "exists", "message": f"A record already exists for {arm} on {date_value}.",
                "requires_overwrite": True, "existing_count": len(matching),
            }), 409

        backup = backup_attendance_file(arm, "holiday") if existing else ""
        remaining = [row for row in existing if not record_matches(row, academic_session, term, level, arm, date_value)]

        write_attendance_rows(arm, remaining + [holiday_row])

    sync_info = queue_attendance_scope_sync(academic_session, term, level, arm, date_value, [holiday_row])

    return jsonify({
        "success": True, "message": "Holiday saved successfully.", "session": academic_session, "term": term,
        "class_level": level, "class_arm": arm, "date": date_value, "reason": reason, "note": note,
        "overwrite": bool(matching), "saved_at": holiday_row["Saved_at"], "backup": backup, "sync": sync_info,
    })


# ============================================================
# API — HISTORY / SAVED DATES
# ============================================================

@attendance_bp.route("/api/attendance/history")
@attendance_staff_required
def api_attendance_history():
    class_level, class_arm = request_class_values()
    level, arm, error = resolve_class_selection(class_level, class_arm, require_arm=True)

    if error: return jsonify({"success": False, "message": error, "records": []}), 400

    academic_session, term = resolve_optional_context(request.args.get("session"), request.args.get("term"))
    start_date, end_date = normalize_date(request.args.get("start_date")), normalize_date(request.args.get("end_date"))
    status, search_text = clean_upper(request.args.get("status")), clean(request.args.get("search"))

    if request.args.get("start_date") and not start_date: return jsonify({"success": False, "message": "Invalid start date.", "records": []}), 400
    if request.args.get("end_date") and not end_date: return jsonify({"success": False, "message": "Invalid end date.", "records": []}), 400
    if start_date and end_date and start_date > end_date: return jsonify({"success": False, "message": "Start date cannot be after end date.", "records": []}), 400
    if status and status not in VALID_STATUSES | {"HOLIDAY"}: return jsonify({"success": False, "message": "Invalid attendance status.", "records": []}), 400

    payload = build_history_payload(level, arm, academic_session, term, start_date, end_date, status, search_text)

    return jsonify({
        "success": True, "session": academic_session, "term": term, "term_label": academic_term_label(term) if term else "",
        "class_level": level, "class_arm": arm, **payload,
        "daily": payload["daily_breakdown"], "students": payload["student_breakdown"], "dates": payload["saved_dates"],
        "count": payload["total_records"],
    })


@attendance_bp.route("/api/attendance/dates")
@attendance_staff_required
def api_attendance_dates():
    class_level, class_arm = request_class_values()
    level, arm, error = resolve_class_selection(class_level, class_arm, require_arm=True)

    if error: return jsonify({"success": False, "message": error, "dates": []}), 400

    academic_session, term = resolve_optional_context(request.args.get("session"), request.args.get("term"))
    start_date, end_date = normalize_date(request.args.get("start_date")), normalize_date(request.args.get("end_date"))
    rows = history_scope_rows(level, arm, academic_session, term, start_date, end_date)
    dates = build_saved_date_history_from_rows(rows)

    return jsonify({
        "success": True, "class_level": level, "class_arm": arm,
        "session": academic_session, "term": term, "dates": dates, "count": len(dates),
    })


# ============================================================
# API — CLASS / STUDENT SUMMARY
# ============================================================

@attendance_bp.route("/api/attendance/summary")
@attendance_staff_required
def api_attendance_summary():
    class_level, class_arm = request_class_values()
    level, arm, error = resolve_class_selection(class_level, class_arm, require_arm=True)

    if error: return jsonify({"success": False, "message": error}), 400

    academic_session, term = resolve_academic_context(request.args.get("session"), request.args.get("term"))

    if not academic_session or not term: return jsonify({"success": False, "message": "Academic session and term are required."}), 400

    summary = get_class_attendance_summary(academic_session, term, level, arm)
    return jsonify({"success": True, "summary": summary, **summary})


@attendance_bp.route("/api/attendance/student-summary")
@attendance_staff_required
def api_attendance_student_summary():
    admission = request.args.get("admission_number") or request.args.get("admission") or request.args.get("student_id")

    if not normalize_admission_number(admission): return jsonify({"success": False, "message": "Admission number is required."}), 400

    class_level, class_arm = request_class_values()
    student = get_student(admission, active_only=False)

    if not class_level and student: class_level = student.get("class_level")
    if not class_arm and student: class_arm = student.get("class_arm")

    level, arm, error = resolve_class_selection(class_level, class_arm, require_arm=True)

    if error: return jsonify({"success": False, "message": error}), 400

    academic_session, term = resolve_academic_context(request.args.get("session"), request.args.get("term"))

    if not academic_session or not term: return jsonify({"success": False, "message": "Academic session and term are required."}), 400

    summary = get_student_attendance_summary(admission, academic_session, term, level, arm)
    return jsonify({"success": True, "summary": summary, **summary})


@attendance_bp.route("/api/attendance/student-history")
@attendance_staff_required
def api_attendance_student_history():
    admission = request.args.get("admission_number") or request.args.get("admission") or request.args.get("student_id")
    admission_key = normalize_admission_number(admission)

    if not admission_key: return jsonify({"success": False, "message": "Admission number is required.", "records": []}), 400

    academic_session, term = resolve_optional_context(request.args.get("session"), request.args.get("term"))
    start_date, end_date = normalize_date(request.args.get("start_date")), normalize_date(request.args.get("end_date"))
    status = clean_upper(request.args.get("status"))

    if request.args.get("start_date") and not start_date: return jsonify({"success": False, "message": "Invalid start date.", "records": []}), 400
    if request.args.get("end_date") and not end_date: return jsonify({"success": False, "message": "Invalid end date.", "records": []}), 400
    if start_date and end_date and start_date > end_date: return jsonify({"success": False, "message": "Start date cannot be after end date.", "records": []}), 400
    if status and status not in VALID_STATUSES: return jsonify({"success": False, "message": "Invalid attendance status.", "records": []}), 400

    rows = []

    for row in read_all_attendance_rows():
        if row_status(row) == "HOLIDAY": continue
        if normalize_admission_number(row.get("Admission_number")) != admission_key: continue
        if academic_session and normalize_academic_session(row.get("Session")) != academic_session: continue
        if term and normalize_academic_term(row.get("Term")) != term: continue

        date_value = normalize_date(row.get("Date"))

        if start_date and (not date_value or date_value < start_date): continue
        if end_date and (not date_value or date_value > end_date): continue
        if status and normalize_status(row.get("Status")) != status: continue

        rows.append(row)

    records = sorted([history_record(row) for row in rows], key=lambda row: (row["date"], row["saved_at"]), reverse=True)
    student = get_student(admission, active_only=False)
    full_name = student_display_name(student or {}) or (records[0]["full_name"] if records else "")
    summary = summarize_student_history_rows(rows, clean(admission), full_name)

    if records: summary.update({"class_arm": records[0].get("class_arm", ""), "class_level": records[0].get("class_level", "")})

    return jsonify({
        "success": True, "admission_number": clean(admission), "student": student or {},
        "session": academic_session, "term": term, "records": records, "history": records,
        "summary": summary, "total_records": len(records),
    })


# ============================================================
# API — DELETE SAVED DATE
# ============================================================

@attendance_bp.route("/api/attendance/delete", methods=["POST", "DELETE"])
@attendance_staff_required
def api_attendance_delete():
    data = request.get_json(silent=True) or {}

    class_level, class_arm = request_class_values(data)
    level, arm, error = resolve_class_selection(class_level, class_arm, require_arm=True)

    if error: return jsonify({"success": False, "message": error}), 400

    academic_session, term = resolve_academic_context(data.get("session"), data.get("term"))
    date_value = normalize_date(data.get("date"))

    if not academic_session or not term: return jsonify({"success": False, "message": "Academic session and term are required."}), 400
    if not date_value: return jsonify({"success": False, "message": "A valid saved attendance date is required."}), 400

    with ATTENDANCE_LOCK:
        existing = read_attendance_rows(arm)
        remaining = [row for row in existing if not record_matches(row, academic_session, term, level, arm, date_value)]
        deleted_count = len(existing) - len(remaining)

        if not deleted_count:
            return jsonify({
                "success": False, "status": "not_found",
                "message": "No saved attendance record was found for that date.", "deleted_count": 0,
            }), 404

        backup = backup_attendance_file(arm, "delete")
        write_attendance_rows(arm, remaining)

    sync_info = queue_attendance_scope_sync(academic_session, term, level, arm, date_value, [])

    return jsonify({
        "success": True, "message": "Saved attendance deleted successfully.",
        "session": academic_session, "term": term, "class_level": level,
        "class_arm": arm, "date": date_value, "deleted_count": deleted_count, "backup": backup, "sync": sync_info,
    })


# ============================================================
# API — MODULE CONFIG
# ============================================================

@attendance_bp.route("/api/attendance/config")
@attendance_staff_required
def api_attendance_config():
    context = get_current_academic_context()

    return jsonify({
        "success": True, "academic": context, "statuses": sorted(VALID_STATUSES),
        "attendance_credit_statuses": sorted(ATTENDANCE_CREDIT_STATUSES), "record_types": ["DAILY", "HOLIDAY"],
    })