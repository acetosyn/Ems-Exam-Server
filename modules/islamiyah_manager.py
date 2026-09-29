# MODULE: Islamiyah School Manager — independent Islamiyah roster placement, CA/Exam scoring, history and report integration
# STORAGE: static/data/islamiyah/*.csv — regular class and Islamiyah class remain independent classifications.

import csv
import shutil
from pathlib import Path
from datetime import datetime
from threading import RLock

from modules.academic_records import clean, clean_upper, normalize_academic_session, normalize_academic_term, is_valid_academic_session, get_all_students
from modules.student_lookup import normalize_admission_number
from modules.school_structure import ISLAMIYAH_CLASS_LEVELS, CLASS_LABELS, ASSESSMENT_SCHEMES, is_islamiyah_class, normalize_school_class
from modules.subject_registry import get_class_subject_rows


BASE_DIR = Path(__file__).resolve().parent.parent
ISLAMIYAH_DIR = BASE_DIR / "static" / "data" / "islamiyah"
ENROLLMENT_FILE = ISLAMIYAH_DIR / "student_enrollments.csv"
SCORE_FILE = ISLAMIYAH_DIR / "score_records.csv"
BACKUP_DIR = ISLAMIYAH_DIR / "backups"
ISLAMIYAH_LOCK = RLock()

ENROLLMENT_HEADERS = [
    "Session", "Admission_number", "Last_name", "First_name", "Other_names", "Full_name", "Sex", "Phone",
    "Regular_class", "Regular_class_level", "Islamiyah_class", "Active", "Imported_at", "Updated_at", "Updated_by",
]
SCORE_HEADERS = [
    "Session", "Term", "Islamiyah_class", "Subject", "Subject_key", "Admission_number", "Last_name", "First_name", "Other_names",
    "CA", "Exam", "Total", "Complete", "Saved_at", "Saved_by",
]

CA_MAX = int(ASSESSMENT_SCHEMES["ISLAMIYAH"]["ca_max"])
EXAM_MAX = int(ASSESSMENT_SCHEMES["ISLAMIYAH"]["exam_max"])
TOTAL_MAX = int(ASSESSMENT_SCHEMES["ISLAMIYAH"]["total_max"])


def now_string(): return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
def score_number(value):
    if value in (None, ""): return None
    try:
        number = float(str(value).replace(",", "").strip()); return int(number) if number.is_integer() else round(number, 2)
    except (TypeError, ValueError): return None


def _validate_score(value, maximum, label):
    if value in (None, ""): return None
    number = score_number(value)
    if number is None or number < 0 or number > maximum: raise ValueError(f"{label} must be between 0 and {maximum}.")
    return number


def _storage(value): return "" if value is None else value

def normalize_islamiyah_session(value):
    session_value = normalize_academic_session(value)
    if not is_valid_academic_session(session_value): raise ValueError("A valid academic session such as 2026/2027 is required.")
    return session_value


def normalize_islamiyah_class(value, allow_blank=False):
    raw = clean(value)
    if not raw and allow_blank: return ""
    level = normalize_school_class(raw)
    if level not in ISLAMIYAH_CLASS_LEVELS: raise ValueError(f"Invalid Islamiyah class: {raw or 'blank'}")
    return level


def islamiyah_class_label(value):
    level = normalize_school_class(value); return CLASS_LABELS.get(level, level or clean(value))


def islamiyah_subject_rows(class_level):
    level = normalize_islamiyah_class(class_level)
    rows = get_class_subject_rows(level, active_only=True)
    return [{"id": clean(row.get("id")), "key": clean_upper(row.get("key")), "name": clean(row.get("name") or row.get("catalog_name") or row.get("key")), "order": int(row.get("order") or 0)} for row in rows]


def islamiyah_subjects(class_level): return [row["name"] for row in islamiyah_subject_rows(class_level)]


def _subject_for_class(class_level, subject_value):
    wanted = clean_upper(subject_value)
    for row in islamiyah_subject_rows(class_level):
        if wanted in {clean_upper(row.get("id")), clean_upper(row.get("key")), clean_upper(row.get("name"))}: return row
    return None


def _ensure_csv(path, headers):
    ISLAMIYAH_DIR.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with path.open("w", newline="", encoding="utf-8-sig") as file: csv.DictWriter(file, fieldnames=headers).writeheader()
    return path


def ensure_islamiyah_storage():
    _ensure_csv(ENROLLMENT_FILE, ENROLLMENT_HEADERS); _ensure_csv(SCORE_FILE, SCORE_HEADERS); return {"enrollments": str(ENROLLMENT_FILE), "scores": str(SCORE_FILE)}


def _read_rows(path, headers):
    _ensure_csv(path, headers)
    with ISLAMIYAH_LOCK:
        with path.open("r", newline="", encoding="utf-8-sig") as file: return list(csv.DictReader(file))


def _write_rows(path, headers, rows):
    _ensure_csv(path, headers); temp = path.with_suffix(path.suffix + ".tmp")
    with ISLAMIYAH_LOCK:
        with temp.open("w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(file, fieldnames=headers, extrasaction="ignore"); writer.writeheader(); writer.writerows(rows)
        temp.replace(path)
    return path


def read_enrollments(): return _read_rows(ENROLLMENT_FILE, ENROLLMENT_HEADERS)
def write_enrollments(rows): return _write_rows(ENROLLMENT_FILE, ENROLLMENT_HEADERS, rows)
def read_scores(): return _read_rows(SCORE_FILE, SCORE_HEADERS)
def write_scores(rows): return _write_rows(SCORE_FILE, SCORE_HEADERS, rows)


def backup_islamiyah_file(path, reason="update"):
    ensure_islamiyah_storage(); BACKUP_DIR.mkdir(parents=True, exist_ok=True); stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    target = BACKUP_DIR / f"{path.stem}_{clean_upper(reason).replace(' ', '_')}_{stamp}{path.suffix}"
    if path.exists(): shutil.copy2(path, target)
    return str(target)


def _enrollment_key(session_value, admission): return f"{normalize_academic_session(session_value)}|{normalize_admission_number(admission)}"
def _score_key(row): return "|".join([normalize_academic_session(row.get("Session")), normalize_academic_term(row.get("Term")), normalize_admission_number(row.get("Admission_number")), clean_upper(row.get("Islamiyah_class")), clean_upper(row.get("Subject_key"))])


def _student_name(student):
    return clean(student.get("full_name")) or " ".join(value for value in [clean(student.get("last_name")), clean(student.get("first_name")), clean(student.get("other_names"))] if value)


def enrollment_to_record(row):
    return {
        "session": normalize_academic_session(row.get("Session")), "admission_number": clean(row.get("Admission_number")), "last_name": clean(row.get("Last_name")), "first_name": clean(row.get("First_name")),
        "other_names": clean(row.get("Other_names")), "full_name": clean(row.get("Full_name")) or " ".join(value for value in [clean(row.get("Last_name")), clean(row.get("First_name")), clean(row.get("Other_names"))] if value),
        "sex": clean(row.get("Sex")), "phone": clean(row.get("Phone")), "regular_class": clean(row.get("Regular_class")), "regular_class_level": clean_upper(row.get("Regular_class_level")),
        "islamiyah_class": clean_upper(row.get("Islamiyah_class")), "islamiyah_class_label": islamiyah_class_label(row.get("Islamiyah_class")) if clean(row.get("Islamiyah_class")) else "Unassigned",
        "active": clean_upper(row.get("Active") or "YES") == "YES", "imported_at": clean(row.get("Imported_at")), "updated_at": clean(row.get("Updated_at")), "updated_by": clean(row.get("Updated_by")),
    }


def score_to_record(row):
    ca, exam = score_number(row.get("CA")), score_number(row.get("Exam")); complete = clean_upper(row.get("Complete")) == "YES" or (ca is not None and exam is not None); total = score_number(row.get("Total"))
    if complete and total is None: total = round(ca + exam, 2)
    return {
        "session": normalize_academic_session(row.get("Session")), "term": normalize_academic_term(row.get("Term")), "islamiyah_class": clean_upper(row.get("Islamiyah_class")), "islamiyah_class_label": islamiyah_class_label(row.get("Islamiyah_class")),
        "subject": clean(row.get("Subject")), "subject_key": clean_upper(row.get("Subject_key")), "admission_number": clean(row.get("Admission_number")), "last_name": clean(row.get("Last_name")), "first_name": clean(row.get("First_name")), "other_names": clean(row.get("Other_names")),
        "ca": ca, "exam": exam, "total": total if complete else None, "provisional_total": round((ca or 0) + (exam or 0), 2) if ca is not None or exam is not None else None, "complete": complete,
        "saved_at": clean(row.get("Saved_at")), "saved_by": clean(row.get("Saved_by")),
    }


def get_enrollment(admission_number, academic_session, active_only=False):
    session_value, admission = normalize_academic_session(academic_session), normalize_admission_number(admission_number)
    if not session_value or not admission: return None
    for row in reversed(read_enrollments()):
        if normalize_academic_session(row.get("Session")) == session_value and normalize_admission_number(row.get("Admission_number")) == admission:
            record = enrollment_to_record(row)
            if active_only and not record.get("active"): return None
            return record
    return None


def list_enrollments(academic_session, islamiyah_class="", regular_class="", active_only=True, search=""):
    session_value = normalize_academic_session(academic_session); level = normalize_islamiyah_class(islamiyah_class, allow_blank=True); regular = clean_upper(regular_class); token = clean(search).lower(); rows = []
    for row in read_enrollments():
        record = enrollment_to_record(row)
        if record.get("session") != session_value: continue
        if active_only and not record.get("active"): continue
        if level and record.get("islamiyah_class") != level: continue
        if regular and regular not in {clean_upper(record.get("regular_class")), clean_upper(record.get("regular_class_level"))}: continue
        if token and token not in " ".join([record.get("admission_number", ""), record.get("full_name", ""), record.get("regular_class", ""), record.get("islamiyah_class_label", "")]).lower(): continue
        rows.append(record)
    rows.sort(key=lambda item: (item.get("islamiyah_class") or "ZZZ", item.get("regular_class") or "", item.get("last_name", "").lower(), item.get("first_name", "").lower(), item.get("admission_number", "").lower()))
    return rows


def import_current_student_database(academic_session, updated_by=""):
    """Import/synchronize the active EMIS master roster for one session while preserving existing Islamiyah placements."""
    session_value = normalize_islamiyah_session(academic_session); students = get_all_students(active_only=True); now = now_string(); current_admissions = set()
    with ISLAMIYAH_LOCK:
        existing = read_enrollments(); by_key = {_enrollment_key(row.get("Session"), row.get("Admission_number")): dict(row) for row in existing}
        for student in students:
            admission = normalize_admission_number(student.get("admission_number"))
            if not admission: continue
            current_admissions.add(admission); key = _enrollment_key(session_value, admission); previous = by_key.get(key, {})
            by_key[key] = {"Session": session_value, "Admission_number": clean(student.get("admission_number")), "Last_name": clean(student.get("last_name")), "First_name": clean(student.get("first_name")), "Other_names": clean(student.get("other_names")), "Full_name": _student_name(student), "Sex": clean(student.get("sex")), "Phone": clean(student.get("phone")), "Regular_class": clean(student.get("class_arm") or student.get("class")), "Regular_class_level": clean_upper(student.get("class_level") or student.get("class_category")), "Islamiyah_class": clean_upper(previous.get("Islamiyah_class")), "Active": "YES", "Imported_at": clean(previous.get("Imported_at")) or now, "Updated_at": now, "Updated_by": clean(updated_by) or "EMIS Admin"}
        for key, row in list(by_key.items()):
            if normalize_academic_session(row.get("Session")) == session_value and normalize_admission_number(row.get("Admission_number")) not in current_admissions: row["Active"], row["Updated_at"], row["Updated_by"] = "NO", now, clean(updated_by) or "EMIS Admin"
        if existing: backup_islamiyah_file(ENROLLMENT_FILE, "roster_import")
        rows = sorted(by_key.values(), key=lambda row: (normalize_academic_session(row.get("Session")), clean_upper(row.get("Islamiyah_class")) or "ZZZ", clean_upper(row.get("Regular_class")), clean(row.get("Last_name")).lower(), clean(row.get("Admission_number")).lower())); write_enrollments(rows)
    imported = [enrollment_to_record(row) for row in rows if normalize_academic_session(row.get("Session")) == session_value and clean_upper(row.get("Active")) == "YES"]; assigned = sum(1 for row in imported if row.get("islamiyah_class"))
    return {"session": session_value, "students": imported, "count": len(imported), "assigned": assigned, "unassigned": len(imported) - assigned, "updated_at": now}


def assign_students(academic_session, admission_numbers, islamiyah_class="", updated_by=""):
    session_value = normalize_islamiyah_session(academic_session); target = normalize_islamiyah_class(islamiyah_class, allow_blank=True); admissions = {normalize_admission_number(value) for value in (admission_numbers or []) if normalize_admission_number(value)}
    if not admissions: raise ValueError("Select at least one student.")
    with ISLAMIYAH_LOCK:
        rows = read_enrollments(); matched = set(); now = now_string()
        for row in rows:
            admission = normalize_admission_number(row.get("Admission_number"))
            if normalize_academic_session(row.get("Session")) == session_value and admission in admissions and clean_upper(row.get("Active") or "YES") == "YES": row["Islamiyah_class"], row["Updated_at"], row["Updated_by"] = target, now, clean(updated_by) or "EMIS Admin"; matched.add(admission)
        missing = sorted(admissions - matched)
        if missing: raise ValueError(f"{len(missing)} selected student(s) are not in the imported Islamiyah roster for {session_value}. Import/sync the current school database first.")
        backup_islamiyah_file(ENROLLMENT_FILE, "placement"); write_enrollments(rows)
    return {"session": session_value, "islamiyah_class": target, "islamiyah_class_label": islamiyah_class_label(target) if target else "Unassigned", "updated": len(matched), "students": list_enrollments(session_value)}


def get_score_records(academic_session, term="", islamiyah_class="", subject="", admission_number=""):
    session_value = normalize_academic_session(academic_session); term_value = normalize_academic_term(term) if term else ""; level = normalize_islamiyah_class(islamiyah_class, allow_blank=True); admission = normalize_admission_number(admission_number); wanted_subject = clean_upper(subject)
    rows = []
    for row in read_scores():
        record = score_to_record(row)
        if session_value and record.get("session") != session_value: continue
        if term_value and record.get("term") != term_value: continue
        if level and record.get("islamiyah_class") != level: continue
        if admission and normalize_admission_number(record.get("admission_number")) != admission: continue
        if wanted_subject and wanted_subject not in {clean_upper(record.get("subject_key")), clean_upper(record.get("subject"))}: continue
        rows.append(record)
    return rows


def get_score_map(academic_session, term, admission_number=""):
    output = {}
    for record in get_score_records(academic_session, term, admission_number=admission_number):
        admission = normalize_admission_number(record.get("admission_number")); key = clean_upper(record.get("subject_key"));
        if admission and key: output.setdefault(admission, {})[key] = record
    return output


def _student_from_enrollment(enrollment):
    return {"admission_number": enrollment.get("admission_number"), "last_name": enrollment.get("last_name"), "first_name": enrollment.get("first_name"), "other_names": enrollment.get("other_names")}


def save_student_score(academic_session, term, admission_number, subject, ca=None, exam=None, saved_by=""):
    session_value = normalize_islamiyah_session(academic_session); term_value = normalize_academic_term(term)
    if not term_value: raise ValueError("A valid FIRST, SECOND or THIRD term is required.")
    admission = normalize_admission_number(admission_number); enrollment = get_enrollment(admission, session_value, active_only=True)
    if not enrollment: raise ValueError("Student is not in the active Islamiyah roster for this session.")
    level = normalize_islamiyah_class(enrollment.get("islamiyah_class"), allow_blank=True)
    if not level: raise ValueError("Assign the student to an Islamiyah class before entering scores.")
    subject_row = _subject_for_class(level, subject)
    if not subject_row: raise ValueError(f"{clean(subject)} is not an active subject for {islamiyah_class_label(level)}.")
    ca_value, exam_value = _validate_score(ca, CA_MAX, "CA"), _validate_score(exam, EXAM_MAX, "Exam"); target_key = "|".join([session_value, term_value, admission, level, clean_upper(subject_row["key"])])
    with ISLAMIYAH_LOCK:
        rows = read_scores(); remaining = [row for row in rows if _score_key(row) != target_key]
        if ca_value is None and exam_value is None:
            if len(remaining) != len(rows): backup_islamiyah_file(SCORE_FILE, "score_clear"); write_scores(remaining)
            return {"deleted": True, "admission_number": admission, "subject_key": subject_row["key"], "ca": None, "exam": None, "total": None, "complete": False}
        complete = ca_value is not None and exam_value is not None; total = round(ca_value + exam_value, 2) if complete else ""; now = now_string(); student = _student_from_enrollment(enrollment)
        new_row = {"Session": session_value, "Term": term_value, "Islamiyah_class": level, "Subject": subject_row["name"], "Subject_key": subject_row["key"], "Admission_number": enrollment.get("admission_number"), "Last_name": student.get("last_name"), "First_name": student.get("first_name"), "Other_names": student.get("other_names"), "CA": _storage(ca_value), "Exam": _storage(exam_value), "Total": total, "Complete": "YES" if complete else "NO", "Saved_at": now, "Saved_by": clean(saved_by) or "Staff"}
        if rows: backup_islamiyah_file(SCORE_FILE, "score_save")
        write_scores(remaining + [new_row])
    return score_to_record(new_row)


def get_score_entry_roster(academic_session, term, islamiyah_class, subject):
    session_value = normalize_islamiyah_session(academic_session); term_value = normalize_academic_term(term)
    if not term_value: raise ValueError("A valid academic term is required.")
    level = normalize_islamiyah_class(islamiyah_class); subject_row = _subject_for_class(level, subject)
    if not subject_row: raise ValueError(f"The selected subject is not active for {islamiyah_class_label(level)}.")
    enrollments = list_enrollments(session_value, level, active_only=True); existing = {normalize_admission_number(item.get("admission_number")): item for item in get_score_records(session_value, term_value, level, subject_row["key"])}; students = []
    for enrollment in enrollments:
        admission = normalize_admission_number(enrollment.get("admission_number")); students.append({**enrollment, "scores": existing.get(admission), "has_saved_scores": admission in existing})
    return {"session": session_value, "term": term_value, "islamiyah_class": level, "islamiyah_class_label": islamiyah_class_label(level), "subject": subject_row["name"], "subject_key": subject_row["key"], "students": students, "count": len(students), "ca_max": CA_MAX, "exam_max": EXAM_MAX, "total_max": TOTAL_MAX}


def get_student_history(admission_number, academic_session=""):
    admission = normalize_admission_number(admission_number); session_filter = normalize_academic_session(academic_session) if academic_session else ""; records = get_score_records(session_filter, admission_number=admission) if session_filter else [record for record in map(score_to_record, read_scores()) if normalize_admission_number(record.get("admission_number")) == admission]
    records.sort(key=lambda item: (item.get("session", ""), {"FIRST": 1, "SECOND": 2, "THIRD": 3}.get(item.get("term"), 9), item.get("islamiyah_class", ""), item.get("subject", "")))
    grouped = {}
    for record in records:
        key = f"{record.get('session')}|{record.get('term')}|{record.get('islamiyah_class')}"; item = grouped.setdefault(key, {"session": record.get("session"), "term": record.get("term"), "islamiyah_class": record.get("islamiyah_class"), "islamiyah_class_label": record.get("islamiyah_class_label"), "subjects": [], "complete_subjects": 0, "average": None})
        item["subjects"].append(record); item["complete_subjects"] += 1 if record.get("complete") else 0
    for item in grouped.values():
        totals = [float(row["total"]) for row in item["subjects"] if row.get("complete") and row.get("total") is not None]; item["average"] = round(sum(totals) / len(totals), 2) if totals and len(totals) == len(item["subjects"]) else None
    return list(grouped.values())


def get_report_islamiyah_row(admission_number, academic_session, term):
    """Return one aggregated Islamiyyah /100 row for a regular-school report, or None before the session roster is activated.

    Each Islamiyah subject uses CA /30 + Exam /70. The regular report's single Islamiyyah row is the equal-weight average
    across all active subjects for the student's assigned Islamiyah class. Missing component subjects remain pending; they are never zero-filled.
    """
    session_value, term_value = normalize_academic_session(academic_session), normalize_academic_term(term); enrollment = get_enrollment(admission_number, session_value, active_only=False)
    if not enrollment: return None
    base = {"subject": "Islamiyyah", "subject_key": "ISLAMIYYAH", "mode": "ISLAMIYAH", "assessment_mode": "ISLAMIYAH", "ca_max": CA_MAX, "exam_max": EXAM_MAX, "total_max": TOTAL_MAX, "islamiyah_class": enrollment.get("islamiyah_class"), "islamiyah_class_label": enrollment.get("islamiyah_class_label"), "position": 0, "position_text": "--", "out_of": 0, "lowest": None, "highest": None, "class_average": None}
    if not enrollment.get("active"): return {**base, "has_ca": False, "has_exam": False, "ca_complete": False, "exam_complete": False, "complete": False, "ca_total": None, "exam": None, "total": None, "grade": "-", "comment": "Islamiyah roster inactive", "islamiyah_status": "inactive", "islamiyah_subject_count": 0, "islamiyah_subjects_complete": 0, "islamiyah_components": []}
    level = clean_upper(enrollment.get("islamiyah_class"))
    if not level: return {**base, "has_ca": False, "has_exam": False, "ca_complete": False, "exam_complete": False, "complete": False, "ca_total": None, "exam": None, "total": None, "grade": "-", "comment": "Islamiyah class assignment pending", "islamiyah_status": "class_pending", "islamiyah_subject_count": 0, "islamiyah_subjects_complete": 0, "islamiyah_components": []}
    subjects = islamiyah_subject_rows(level); saved = get_score_map(session_value, term_value, admission_number).get(normalize_admission_number(admission_number), {}); components = []
    for subject in subjects:
        record = saved.get(clean_upper(subject["key"])) or {}; components.append({"subject": subject["name"], "subject_key": subject["key"], "ca": record.get("ca"), "exam": record.get("exam"), "total": record.get("total"), "complete": bool(record.get("complete")), "saved_at": record.get("saved_at", "")})
    ca_values = [float(item["ca"]) for item in components if item.get("ca") is not None]; exam_values = [float(item["exam"]) for item in components if item.get("exam") is not None]; complete_rows = [item for item in components if item.get("complete") and item.get("total") is not None]
    all_complete = bool(components) and len(complete_rows) == len(components); ca_complete = bool(components) and len(ca_values) == len(components); exam_complete = bool(components) and len(exam_values) == len(components)
    ca_average = round(sum(ca_values) / len(ca_values), 2) if ca_values else None; exam_average = round(sum(exam_values) / len(exam_values), 2) if exam_values else None; total = round(ca_average + exam_average, 2) if all_complete and ca_average is not None and exam_average is not None else None
    if total is None: grade, comment = "-", "Pending Islamiyah scores"
    elif total >= 80: grade, comment = "A", "Excellent"
    elif total >= 70: grade, comment = "B", "Very Good"
    elif total >= 60: grade, comment = "C", "Good"
    elif total >= 45: grade, comment = "D", "Pass"
    elif total >= 40: grade, comment = "E", "Pass"
    else: grade, comment = "F", "Fail"
    return {**base, "islamiyah_class": level, "islamiyah_class_label": islamiyah_class_label(level), "has_ca": bool(ca_values), "has_exam": bool(exam_values), "ca_complete": ca_complete, "exam_complete": exam_complete, "complete": all_complete, "ca": ca_average, "ca_total": ca_average, "exam": exam_average, "total": total, "provisional_total": round((ca_average or 0) + (exam_average or 0), 2) if ca_average is not None or exam_average is not None else None, "grade": grade, "comment": comment, "islamiyah_status": "complete" if all_complete else "partial" if (ca_values or exam_values) else "pending", "islamiyah_subject_count": len(components), "islamiyah_subjects_complete": len(complete_rows), "islamiyah_components": components}


def get_class_result_summary(academic_session, term, islamiyah_class):
    session_value = normalize_islamiyah_session(academic_session); term_value = normalize_academic_term(term); level = normalize_islamiyah_class(islamiyah_class)
    if not term_value: raise ValueError("A valid academic term is required.")
    subjects = islamiyah_subject_rows(level); score_map = get_score_map(session_value, term_value); students = []
    for enrollment in list_enrollments(session_value, level, active_only=True):
        admission = normalize_admission_number(enrollment.get("admission_number")); saved = score_map.get(admission, {}); rows = []
        for subject in subjects:
            record = saved.get(clean_upper(subject["key"])) or {}; rows.append({"subject": subject["name"], "subject_key": subject["key"], "ca": record.get("ca"), "exam": record.get("exam"), "total": record.get("total"), "complete": bool(record.get("complete"))})
        complete = [row for row in rows if row.get("complete") and row.get("total") is not None]; totals = [float(row["total"]) for row in complete]; all_complete = bool(rows) and len(complete) == len(rows); provisional = round(sum(totals) / len(totals), 2) if totals else None; average = provisional if all_complete else None
        students.append({**enrollment, "subjects": rows, "subject_count": len(rows), "subjects_complete": len(complete), "complete": all_complete, "average": average, "provisional_average": provisional, "status": "Complete" if all_complete else "In Progress" if complete else "Not Started"})
    complete_averages = [float(row["average"]) for row in students if row.get("average") is not None]; return {"session": session_value, "term": term_value, "islamiyah_class": level, "islamiyah_class_label": islamiyah_class_label(level), "subjects": subjects, "students": students, "count": len(students), "complete_students": sum(1 for row in students if row.get("complete")), "class_average": round(sum(complete_averages) / len(complete_averages), 2) if complete_averages else None}


def get_islamiyah_dashboard(academic_session, term=""):
    session_value = normalize_academic_session(academic_session); term_value = normalize_academic_term(term) if term else ""; enrollments = list_enrollments(session_value, active_only=True); assigned = [row for row in enrollments if row.get("islamiyah_class")]; scores = get_score_records(session_value, term_value) if term_value else get_score_records(session_value); class_counts = {level: 0 for level in ISLAMIYAH_CLASS_LEVELS}
    for row in assigned: class_counts[row.get("islamiyah_class")] = class_counts.get(row.get("islamiyah_class"), 0) + 1
    completed = sum(1 for row in scores if row.get("complete")); return {"session": session_value, "term": term_value, "roster_count": len(enrollments), "assigned_count": len(assigned), "unassigned_count": len(enrollments) - len(assigned), "score_records": len(scores), "complete_score_records": completed, "incomplete_score_records": len(scores) - completed, "class_counts": class_counts, "classes": [{"key": level, "label": islamiyah_class_label(level), "students": class_counts.get(level, 0), "subjects": islamiyah_subject_rows(level)} for level in ISLAMIYAH_CLASS_LEVELS]}


def build_enrollment_sync_payload(academic_session):
    session_value = normalize_islamiyah_session(academic_session); rows = [row for row in read_enrollments() if normalize_academic_session(row.get("Session")) == session_value]
    return {"session": session_value, "rows": rows, "updated_at": now_string()}


def build_score_scope_sync_payload(academic_session, term, islamiyah_class, subject):
    session_value = normalize_islamiyah_session(academic_session); term_value = normalize_academic_term(term); level = normalize_islamiyah_class(islamiyah_class); subject_row = _subject_for_class(level, subject)
    if not term_value or not subject_row: raise ValueError("Valid term, Islamiyah class and subject are required for score synchronization.")
    raw_rows = []
    for row in read_scores():
        if normalize_academic_session(row.get("Session")) == session_value and normalize_academic_term(row.get("Term")) == term_value and clean_upper(row.get("Islamiyah_class")) == level and clean_upper(row.get("Subject_key")) == clean_upper(subject_row["key"]): raw_rows.append(dict(row))
    return {"session": session_value, "term": term_value, "islamiyah_class": level, "subject": subject_row["name"], "subject_key": subject_row["key"], "rows": raw_rows, "updated_at": now_string()}


def apply_islamiyah_sync_event(action, payload, event=None):
    if not isinstance(payload, dict): raise ValueError("Islamiyah sync payload must be an object.")
    action = clean(action).lower()
    if action == "replace_session_enrollments":
        session_value = normalize_islamiyah_session(payload.get("session") or payload.get("academic_session")); incoming = payload.get("rows") or []
        if not isinstance(incoming, list): raise ValueError("Islamiyah enrollment rows must be a list.")
        normalized = []
        for row in incoming:
            if not isinstance(row, dict): continue
            item = {header: row.get(header, "") for header in ENROLLMENT_HEADERS}; item["Session"] = session_value
            if item.get("Islamiyah_class"): item["Islamiyah_class"] = normalize_islamiyah_class(item.get("Islamiyah_class"))
            normalized.append(item)
        with ISLAMIYAH_LOCK:
            existing = read_enrollments(); remaining = [row for row in existing if normalize_academic_session(row.get("Session")) != session_value]
            if existing: backup_islamiyah_file(ENROLLMENT_FILE, "cloud_sync")
            write_enrollments(remaining + normalized)
        return {"session": session_value, "saved_count": len(normalized)}
    if action == "replace_score_scope":
        session_value = normalize_islamiyah_session(payload.get("session") or payload.get("academic_session")); term_value = normalize_academic_term(payload.get("term")); level = normalize_islamiyah_class(payload.get("islamiyah_class")); subject_row = _subject_for_class(level, payload.get("subject_key") or payload.get("subject")); incoming = payload.get("rows") or []
        if not term_value or not subject_row or not isinstance(incoming, list): raise ValueError("Islamiyah score sync requires term, class, subject and row list.")
        normalized = []
        for row in incoming:
            if not isinstance(row, dict): continue
            item = {header: row.get(header, "") for header in SCORE_HEADERS}; item.update({"Session": session_value, "Term": term_value, "Islamiyah_class": level, "Subject": subject_row["name"], "Subject_key": subject_row["key"]}); normalized.append(item)
        with ISLAMIYAH_LOCK:
            existing = read_scores(); remaining = [row for row in existing if not (normalize_academic_session(row.get("Session")) == session_value and normalize_academic_term(row.get("Term")) == term_value and clean_upper(row.get("Islamiyah_class")) == level and clean_upper(row.get("Subject_key")) == clean_upper(subject_row["key"]))]
            if existing: backup_islamiyah_file(SCORE_FILE, "cloud_sync")
            write_scores(remaining + normalized)
        return {"session": session_value, "term": term_value, "islamiyah_class": level, "subject_key": subject_row["key"], "saved_count": len(normalized)}
    raise ValueError(f"Unsupported Islamiyah sync action: {action}")

