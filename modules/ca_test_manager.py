# MODULE: CA/Test Manager — EMIS continuous assessment entry, storage, history and report-source engine

import csv
import shutil
from pathlib import Path
from datetime import datetime
from threading import RLock
from functools import wraps

from flask import Blueprint, jsonify, request, session

from modules.academic_records import clean, clean_upper, safe_bool, normalize_academic_session, normalize_academic_term, academic_term_label, get_current_academic_context, normalize_academic_class, validate_class_selection, get_students_for_class, get_subjects_for_selection, normalize_academic_subject, academic_subject_key, subject_is_valid_for_class
from modules.student_lookup import normalize_admission_number
from modules.result_sync import queue_emis_event_safely


ca_test_bp = Blueprint("ca_test_bp", __name__)

BASE_DIR = Path(__file__).resolve().parent.parent
CA_DIR = BASE_DIR / "static" / "data" / "ca_tests"
CA_FILE = CA_DIR / "ca_test_records.csv"
BACKUP_DIR = CA_DIR / "backups"

CA_HEADERS = [
    "Session", "Term", "Class", "Class_category", "Subject", "Subject_key", "Admission_number",
    "Last_name", "First_name", "Other_names", "CA1", "CA2", "TEST1", "TEST2",
    "ASS1", "ASS2", "TEST", "CA_Total", "CA_Complete", "Saved_at", "Saved_by",
]

JSS_FIELDS = {"CA1": 10, "CA2": 10, "TEST1": 20, "TEST2": 20}
SS_FIELDS = {"ASS1": 5, "ASS2": 5, "TEST": 20}

CA_LOCK = RLock()


# ============================================================
# ACCESS / BASIC HELPERS
# ============================================================

def ca_staff_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if clean(session.get("user_type")).lower() not in {"admin", "teacher"}:
            return jsonify({"success": False, "message": "Unauthorized."}), 403
        return view(*args, **kwargs)
    return wrapped


def now_string(): return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def get_staff_name(): return clean(session.get("admin_username") or session.get("username") or session.get("user") or "Staff")

def assessment_mode(class_level): return "JSS" if clean_upper(class_level).startswith("JSS") else "SS"

def assessment_fields(class_level): return dict(JSS_FIELDS if assessment_mode(class_level) == "JSS" else SS_FIELDS)


def score_number(value):
    if value in (None, ""): return None
    try:
        number = float(str(value).replace(",", "").strip())
        return int(number) if number.is_integer() else round(number, 2)
    except (TypeError, ValueError): return None


def validate_score(value, maximum, label):
    number = score_number(value)
    if number is None: return None
    if number < 0 or number > maximum: raise ValueError(f"{label} must be between 0 and {maximum}.")
    return number


def score_storage(value): return "" if value is None else value


def safe_subject_display(subject): return normalize_academic_subject(subject)


# ============================================================
# FILE HELPERS
# ============================================================

def ensure_ca_file():
    CA_DIR.mkdir(parents=True, exist_ok=True)

    if not CA_FILE.exists():
        with CA_FILE.open("w", newline="", encoding="utf-8-sig") as file:
            csv.DictWriter(file, fieldnames=CA_HEADERS).writeheader()

    return CA_FILE


def read_ca_rows():
    ensure_ca_file()

    with CA_LOCK:
        with CA_FILE.open("r", newline="", encoding="utf-8-sig") as file:
            return list(csv.DictReader(file))


def write_ca_rows(rows):
    ensure_ca_file()
    temp = CA_FILE.with_suffix(".tmp")

    with CA_LOCK:
        with temp.open("w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(file, fieldnames=CA_HEADERS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)

        temp.replace(CA_FILE)

    return CA_FILE


def backup_ca_file(reason="update"):
    ensure_ca_file()

    if not CA_FILE.exists(): return ""

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    path = BACKUP_DIR / f"ca_test_records_{clean_upper(reason).replace(' ', '_')}_{stamp}.csv"
    shutil.copy2(CA_FILE, path)
    return str(path)


# ============================================================
# REQUEST / NORMALIZATION HELPERS
# ============================================================

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


def normalize_row_subject(row):
    return academic_subject_key(row.get("Subject_key") or row.get("Subject"))


def ca_row_matches(row, academic_session="", term="", class_level="", class_arm="", subject=""):
    row_level, row_arm = normalize_academic_class(row.get("Class_category") or row.get("Class"), row.get("Class"))

    if academic_session and normalize_academic_session(row.get("Session")) != academic_session: return False
    if term and normalize_academic_term(row.get("Term")) != term: return False
    if class_level and row_level != class_level: return False
    if class_arm and row_arm != class_arm: return False
    if subject and normalize_row_subject(row) != academic_subject_key(subject): return False

    return True


# ============================================================
# RECORD BUILDING
# ============================================================

def build_ca_record(student, scores, academic_session, term, class_level, class_arm, subject, saved_at="", saved_by=""):
    mode = assessment_mode(class_level)
    fields = assessment_fields(class_level)
    values = {}

    for field, maximum in fields.items():
        values[field] = validate_score(scores.get(field.lower(), scores.get(field)), maximum, field)

    complete = all(values.get(field) is not None for field in fields)
    ca_total = round(sum(value or 0 for value in values.values()), 2)

    return {
        "Session": academic_session, "Term": term, "Class": class_arm, "Class_category": class_level,
        "Subject": safe_subject_display(subject), "Subject_key": academic_subject_key(subject),
        "Admission_number": clean(student.get("admission_number") or student.get("id")),
        "Last_name": clean(student.get("last_name")), "First_name": clean(student.get("first_name")), "Other_names": clean(student.get("other_names")),
        "CA1": score_storage(values.get("CA1")), "CA2": score_storage(values.get("CA2")),
        "TEST1": score_storage(values.get("TEST1")), "TEST2": score_storage(values.get("TEST2")),
        "ASS1": score_storage(values.get("ASS1")), "ASS2": score_storage(values.get("ASS2")),
        "TEST": score_storage(values.get("TEST")), "CA_Total": ca_total, "CA_Complete": "YES" if complete else "NO",
        "Saved_at": saved_at or now_string(), "Saved_by": saved_by or get_staff_name(),
    }


def ca_row_to_record(row):
    class_level = normalize_academic_class(row.get("Class_category") or row.get("Class"), row.get("Class"))[0]
    mode = assessment_mode(class_level)
    record = {"admission_number": clean(row.get("Admission_number")), "subject": safe_subject_display(row.get("Subject")), "subject_key": academic_subject_key(row.get("Subject_key") or row.get("Subject")), "mode": mode, "ca_total": score_number(row.get("CA_Total")) or 0, "complete": clean_upper(row.get("CA_Complete")) == "YES", "saved_at": clean(row.get("Saved_at")), "saved_by": clean(row.get("Saved_by"))}
    if mode == "JSS": record.update({"ca1": score_number(row.get("CA1")), "ca2": score_number(row.get("CA2")), "test1": score_number(row.get("TEST1")), "test2": score_number(row.get("TEST2"))})
    else: record.update({"ass1": score_number(row.get("ASS1")), "ass2": score_number(row.get("ASS2")), "test": score_number(row.get("TEST"))})
    return record


def ca_record_has_any_score(record):
    """True only when at least one real CA/Test component has been entered. Explicit zero is a valid score."""
    if not isinstance(record, dict): return False
    fields = ["ca1", "ca2", "test1", "test2"] if clean_upper(record.get("mode")) == "JSS" else ["ass1", "ass2", "test"]
    return any(record.get(field) is not None for field in fields)


def submitted_item_has_any_score(item, class_level):
    """Ignore untouched blank students when the frontend submits the whole loaded class."""
    if not isinstance(item, dict): return False
    return any(item.get(field.lower(), item.get(field)) not in (None, "") for field in assessment_fields(class_level))


# ============================================================
# PUBLIC CA DATA HELPERS
# ============================================================

def get_ca_records(academic_session, term, class_level, class_arm, subject=""):
    academic_session = normalize_academic_session(academic_session)
    term = normalize_academic_term(term)
    level, arm = normalize_academic_class(class_level, class_arm)

    if not academic_session or not term or not level or not arm: return []

    return [
        row for row in read_ca_rows()
        if ca_row_matches(row, academic_session, term, level, arm, subject)
    ]


def get_ca_scores_map(academic_session, term, class_level, class_arm):
    """Return only students/subjects that contain at least one entered CA/Test score for the exact academic context."""
    rows = get_ca_records(academic_session, term, class_level, class_arm); output = {}
    for row in rows:
        admission, subject_key, record = normalize_admission_number(row.get("Admission_number")), normalize_row_subject(row), ca_row_to_record(row)
        if not admission or not subject_key or not ca_record_has_any_score(record): continue
        output.setdefault(admission, {})[subject_key] = record
    return output


def get_ca_available_contexts(class_level="", class_arm=""):
    """Diagnostic helper used by Report Sheets when no CA exists for the selected session/term."""
    level, arm = normalize_academic_class(class_level, class_arm); grouped = {}
    for row in read_ca_rows():
        row_level, row_arm = normalize_academic_class(row.get("Class_category") or row.get("Class"), row.get("Class"))
        if level and row_level != level: continue
        if class_arm and arm and row_arm != arm: continue
        record = ca_row_to_record(row)
        if not ca_record_has_any_score(record): continue
        key = (normalize_academic_session(row.get("Session")), normalize_academic_term(row.get("Term")), row_level, row_arm)
        item = grouped.setdefault(key, {"session": key[0], "term": key[1], "class_level": row_level, "class_arm": row_arm, "subjects": set(), "students": set(), "records": 0})
        item["records"] += 1; item["subjects"].add(record.get("subject") or normalize_row_subject(row)); item["students"].add(normalize_admission_number(row.get("Admission_number")))
    output = []
    for item in grouped.values(): output.append({**item, "subjects": sorted(value for value in item["subjects"] if value), "student_count": len([value for value in item["students"] if value]), "students": None})
    return sorted(output, key=lambda item: (item.get("session", ""), item.get("term", ""), item.get("class_arm", "")), reverse=True)


def get_student_ca_scores(admission_number, academic_session, term, class_level, class_arm):
    admission = normalize_admission_number(admission_number)
    return get_ca_scores_map(academic_session, term, class_level, class_arm).get(admission, {})


def get_ca_subjects_saved(academic_session, term, class_level, class_arm):
    rows = get_ca_records(academic_session, term, class_level, class_arm)
    subjects = {}

    for row in rows:
        key = normalize_row_subject(row)
        if key and key not in subjects: subjects[key] = safe_subject_display(row.get("Subject"))

    return sorted(subjects.values(), key=str.lower)


# ============================================================
# API — CONFIG / STUDENTS
# ============================================================



# ============================================================
# SYNC HELPERS
# ============================================================

def ca_sync_entity_key(academic_session, term, class_arm, subject):
    return "|".join([clean(academic_session), clean_upper(term), clean_upper(class_arm), academic_subject_key(subject)])


def queue_ca_scope_sync(academic_session, term, class_level, class_arm, subject, rows):
    payload = {
        "session": normalize_academic_session(academic_session), "term": normalize_academic_term(term),
        "class_level": clean_upper(class_level), "class_arm": clean_upper(class_arm),
        "subject": safe_subject_display(subject), "rows": [dict(row) for row in (rows or [])],
    }
    return queue_emis_event_safely(
        "ca_tests", "replace_scope", payload,
        entity_key=ca_sync_entity_key(payload["session"], payload["term"], payload["class_arm"], payload["subject"]),
    )


def apply_ca_sync_event(action, payload, event=None):
    if clean(action).lower() != "replace_scope": raise ValueError(f"Unsupported CA/Test sync action: {action}")
    if not isinstance(payload, dict): raise ValueError("CA/Test sync payload must be an object.")

    academic_session, term = resolve_context(payload.get("session") or payload.get("academic_session"), payload.get("term"))
    level, arm, error = resolve_class(payload.get("class_level") or payload.get("class_category"), payload.get("class_arm") or payload.get("class"), require_arm=True)
    subject = safe_subject_display(payload.get("subject"))
    rows = payload.get("rows") or []

    if error: raise ValueError(error)
    if not academic_session or not term or not subject: raise ValueError("CA/Test sync requires session, term and subject.")
    if not isinstance(rows, list): raise ValueError("CA/Test synchronized rows must be a list.")

    normalized_rows = []
    for row in rows:
        if not isinstance(row, dict): continue
        item = {header: row.get(header, "") for header in CA_HEADERS}
        item["Session"], item["Term"], item["Class"], item["Class_category"] = academic_session, term, arm, level
        item["Subject"], item["Subject_key"] = subject, academic_subject_key(subject)
        normalized_rows.append(item)

    with CA_LOCK:
        existing = read_ca_rows()
        if existing: backup_ca_file("cloud_sync")
        remaining = [row for row in existing if not ca_row_matches(row, academic_session, term, level, arm, subject)]
        write_ca_rows(remaining + normalized_rows)

    return {"class_arm": arm, "subject": subject, "saved_count": len(normalized_rows), "deleted": not bool(normalized_rows)}


@ca_test_bp.route("/api/ca-tests/config")
@ca_staff_required
def api_ca_config():
    class_level, class_arm = request_class_values()
    level, arm, error = resolve_class(class_level, class_arm, require_arm=bool(class_arm))

    if error and class_level:
        return jsonify({"success": False, "message": error}), 400

    academic_session, term = resolve_context(request.args.get("session"), request.args.get("term"))
    subjects = get_subjects_for_selection(level, arm) if level else []

    return jsonify({
        "success": True, "session": academic_session, "term": term, "term_label": academic_term_label(term),
        "class_level": level, "class_arm": arm, "mode": assessment_mode(level) if level else "",
        "fields": assessment_fields(level) if level else {}, "subjects": subjects,
    })


@ca_test_bp.route("/api/ca-tests/students")
@ca_staff_required
def api_ca_students():
    class_level, class_arm = request_class_values()
    level, arm, error = resolve_class(class_level, class_arm, require_arm=True)

    if error: return jsonify({"success": False, "message": error, "students": []}), 400

    academic_session, term = resolve_context(request.args.get("session"), request.args.get("term"))
    subject = clean(request.args.get("subject"))

    if not academic_session or not term:
        return jsonify({"success": False, "message": "Academic session and term are required.", "students": []}), 400

    if subject and not subject_is_valid_for_class(subject, level, arm):
        return jsonify({"success": False, "message": f"{subject} is not configured for {arm}.", "students": []}), 400

    roster = get_students_for_class(level, arm, active_only=True)
    existing = {}

    if subject:
        for row in get_ca_records(academic_session, term, level, arm, subject):
            existing[normalize_admission_number(row.get("Admission_number"))] = ca_row_to_record(row)

    students = []

    for student in roster:
        admission = normalize_admission_number(student.get("admission_number"))
        students.append({**student, "scores": existing.get(admission), "has_saved_scores": admission in existing})

    return jsonify({
        "success": True, "session": academic_session, "term": term, "term_label": academic_term_label(term),
        "class_level": level, "class_arm": arm, "subject": safe_subject_display(subject) if subject else "",
        "mode": assessment_mode(level), "fields": assessment_fields(level), "students": students, "count": len(students),
    })


# ============================================================
# API — LOAD SAVED SUBJECT
# ============================================================

@ca_test_bp.route("/api/ca-tests/records")
@ca_staff_required
def api_ca_records():
    class_level, class_arm = request_class_values()
    level, arm, error = resolve_class(class_level, class_arm, require_arm=True)

    if error: return jsonify({"success": False, "message": error, "records": []}), 400

    academic_session, term = resolve_context(request.args.get("session"), request.args.get("term"))
    subject = clean(request.args.get("subject"))

    if not academic_session or not term or not subject:
        return jsonify({"success": False, "message": "Session, term and subject are required.", "records": []}), 400

    rows = get_ca_records(academic_session, term, level, arm, subject)
    records = [ca_row_to_record(row) for row in rows]

    return jsonify({
        "success": True, "session": academic_session, "term": term, "class_level": level,
        "class_arm": arm, "subject": safe_subject_display(subject), "mode": assessment_mode(level),
        "fields": assessment_fields(level), "records": records, "count": len(records),
    })


# ============================================================
# API — SAVE CA/TEST
# ============================================================

@ca_test_bp.route("/api/ca-tests/save", methods=["POST"])
@ca_staff_required
def api_ca_save():
    data = request.get_json(silent=True) or {}
    class_level, class_arm = request_class_values(data)
    level, arm, error = resolve_class(class_level, class_arm, require_arm=True)

    if error: return jsonify({"success": False, "message": error}), 400

    academic_session, term = resolve_context(data.get("session"), data.get("term"))
    subject = clean(data.get("subject"))
    overwrite = safe_bool(data.get("overwrite"))
    records = data.get("students") or data.get("records") or []

    if not academic_session or not term:
        return jsonify({"success": False, "message": "Academic session and term are required."}), 400

    if not subject:
        return jsonify({"success": False, "message": "Subject is required."}), 400

    if not subject_is_valid_for_class(subject, level, arm):
        return jsonify({"success": False, "message": f"{subject} is not configured for {arm}."}), 400

    if not isinstance(records, list) or not records:
        return jsonify({"success": False, "message": "No CA/Test records were supplied."}), 400

    roster = get_students_for_class(level, arm, active_only=True)

    if not roster:
        return jsonify({"success": False, "message": f"No active students found in {arm}."}), 404

    roster_map = {normalize_admission_number(student.get("admission_number")): student for student in roster}
    submitted, skipped_blank = {}, 0

    try:
        for item in records:
            if not isinstance(item, dict): continue
            admission = normalize_admission_number(item.get("admission_number") or item.get("Admission_number") or item.get("id"))
            if not admission: continue
            if admission not in roster_map: return jsonify({"success": False, "message": f"Student {item.get('admission_number') or admission} is not an active member of {arm}."}), 400
            if not submitted_item_has_any_score(item, level): skipped_blank += 1; continue
            submitted[admission] = build_ca_record(roster_map[admission], item, academic_session, term, level, arm, subject, saved_at=now_string(), saved_by=get_staff_name())
    except ValueError as error: return jsonify({"success": False, "message": str(error)}), 400

    if not submitted: return jsonify({"success": False, "message": "No CA/Test scores were entered. Enter at least one score before saving."}), 400

    with CA_LOCK:
        existing = read_ca_rows()
        matching = [row for row in existing if ca_row_matches(row, academic_session, term, level, arm, subject)]

        if matching and not overwrite:
            return jsonify({
                "success": False, "status": "exists",
                "message": f"{safe_subject_display(subject)} CA/Test records already exist for {arm}.",
                "requires_overwrite": True, "existing_count": len(matching),
            }), 409

        backup = backup_ca_file("overwrite" if matching else "save") if existing else ""
        remaining = [row for row in existing if not ca_row_matches(row, academic_session, term, level, arm, subject)]
        write_ca_rows(remaining + list(submitted.values()))

    sync_info = queue_ca_scope_sync(academic_session, term, level, arm, subject, list(submitted.values()))
    complete = sum(1 for row in submitted.values() if clean_upper(row.get("CA_Complete")) == "YES")

    return jsonify({
        "success": True, "message": "CA/Test scores saved successfully.",
        "session": academic_session, "term": term, "class_level": level, "class_arm": arm,
        "subject": safe_subject_display(subject), "mode": assessment_mode(level),
        "saved_count": len(submitted), "complete_count": complete, "incomplete_count": len(submitted) - complete,
        "skipped_blank_count": skipped_blank, "overwrite": bool(matching), "backup": backup, "sync": sync_info,
    })


# ============================================================
# API — HISTORY
# ============================================================

@ca_test_bp.route("/api/ca-tests/history")
@ca_staff_required
def api_ca_history():
    class_level, class_arm = request_class_values()
    level, arm, error = resolve_class(class_level, class_arm, require_arm=True)

    if error: return jsonify({"success": False, "message": error, "records": []}), 400

    academic_session, term = resolve_context(request.args.get("session"), request.args.get("term"))

    if not academic_session or not term:
        return jsonify({"success": False, "message": "Academic session and term are required.", "records": []}), 400

    rows = get_ca_records(academic_session, term, level, arm)
    grouped = {}

    for row in rows:
        key = normalize_row_subject(row)
        if not key: continue

        item = grouped.setdefault(key, {
            "subject": safe_subject_display(row.get("Subject")), "subject_key": key,
            "students": 0, "complete": 0, "incomplete": 0, "saved_at": "", "saved_by": "",
        })

        item["students"] += 1
        item["saved_at"] = clean(row.get("Saved_at")) or item["saved_at"]
        item["saved_by"] = clean(row.get("Saved_by")) or item["saved_by"]

        if clean_upper(row.get("CA_Complete")) == "YES": item["complete"] += 1
        else: item["incomplete"] += 1

    history = sorted(grouped.values(), key=lambda item: item["subject"].lower())

    return jsonify({
        "success": True, "session": academic_session, "term": term, "class_level": level,
        "class_arm": arm, "records": history, "subjects": history, "count": len(history),
    })


# ============================================================
# API — DELETE SUBJECT RECORDS
# ============================================================

@ca_test_bp.route("/api/ca-tests/delete", methods=["POST", "DELETE"])
@ca_staff_required
def api_ca_delete():
    data = request.get_json(silent=True) or {}
    class_level, class_arm = request_class_values(data)
    level, arm, error = resolve_class(class_level, class_arm, require_arm=True)

    if error: return jsonify({"success": False, "message": error}), 400

    academic_session, term = resolve_context(data.get("session"), data.get("term"))
    subject = clean(data.get("subject"))

    if not academic_session or not term or not subject:
        return jsonify({"success": False, "message": "Session, term and subject are required."}), 400

    with CA_LOCK:
        existing = read_ca_rows()
        remaining = [row for row in existing if not ca_row_matches(row, academic_session, term, level, arm, subject)]
        deleted_count = len(existing) - len(remaining)

        if not deleted_count:
            return jsonify({"success": False, "status": "not_found", "message": "No matching CA/Test records were found.", "deleted_count": 0}), 404

        backup = backup_ca_file("delete")
        write_ca_rows(remaining)

    sync_info = queue_ca_scope_sync(academic_session, term, level, arm, subject, [])

    return jsonify({
        "success": True, "message": "CA/Test records deleted successfully.",
        "session": academic_session, "term": term, "class_level": level, "class_arm": arm,
        "subject": safe_subject_display(subject), "deleted_count": deleted_count, "backup": backup, "sync": sync_info,
    })