# MODULE: Islamiyah School Manager — independent Islamiyah roster placement, CA/Exam scoring, history and report integration
# STORAGE: static/data/islamiyah/*.csv — regular class and Islamiyah class remain independent classifications.

import csv
import shutil
import time
from pathlib import Path
from datetime import datetime
from threading import RLock

from modules.academic_records import clean, clean_upper, normalize_academic_session, normalize_academic_term, is_valid_academic_session, get_all_students, get_student
from modules.student_lookup import normalize_admission_number
from modules.academy_identity import master_identity_indexes, resolve_master_identity
from modules.islamiyah_database import read_register, sync_current_islamiyah_profiles
from modules.academic_records import get_current_academic_context
from modules.school_structure import ISLAMIYAH_ROSTER_CLASSES, ISLAMIYAH_BASE_LEVELS, islamiyah_base_level, ISLAMIYAH_CLASS_LEVELS, REGULAR_CLASS_LEVELS, CLASS_LABELS, ASSESSMENT_SCHEMES, is_islamiyah_class, normalize_school_class
from modules.subject_registry import get_class_subject_rows
from modules.class_config import CLASS_ARMS_BY_LEVEL, normalize_class_level, normalize_class_arm


BASE_DIR = Path(__file__).resolve().parent.parent
ISLAMIYAH_DIR = BASE_DIR / "static" / "data" / "islamiyah"
ENROLLMENT_FILE = ISLAMIYAH_DIR / "student_enrollments.csv"
SCORE_FILE = ISLAMIYAH_DIR / "score_records.csv"
REGULAR_SCORE_FILE = ISLAMIYAH_DIR / "regular_school_score_records.csv"
ACTIVITY_FILE = ISLAMIYAH_DIR / "academy_activity.csv"
BACKUP_DIR = ISLAMIYAH_DIR / "backups"
ISLAMIYAH_LOCK = RLock()
_ISLAMIYAH_SEED_RUNTIME = {}

ENROLLMENT_HEADERS = [
    "Session", "Admission_number", "Linked_admission_number", "Last_name", "First_name", "Other_names", "Full_name", "Sex", "Phone",
    "Regular_class", "Regular_class_level", "Islamiyah_class", "Source", "Source_note", "Active", "Imported_at", "Updated_at", "Updated_by",
]
SCORE_HEADERS = [
    "Session", "Term", "Islamiyah_class", "Subject", "Subject_key", "Admission_number", "Last_name", "First_name", "Other_names",
    "CA", "Exam", "Total", "Complete", "Saved_at", "Saved_by",
]
REGULAR_SCORE_HEADERS = [
    "Session", "Term", "Admission_number", "Class_level", "Class_arm", "Last_name", "First_name", "Other_names",
    "CA", "Exam", "Total", "Complete", "Exempt", "Saved_at", "Saved_by",
]
ACTIVITY_HEADERS = ["Timestamp", "Session", "Action", "School", "Admission_numbers", "Target_class", "Actor", "Note"]

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
    _ensure_csv(ENROLLMENT_FILE, ENROLLMENT_HEADERS); _ensure_csv(SCORE_FILE, SCORE_HEADERS); _ensure_csv(REGULAR_SCORE_FILE, REGULAR_SCORE_HEADERS); _ensure_csv(ACTIVITY_FILE, ACTIVITY_HEADERS); return {"enrollments": str(ENROLLMENT_FILE), "scores": str(SCORE_FILE), "regular_school_scores": str(REGULAR_SCORE_FILE), "activity": str(ACTIVITY_FILE)}


# ============================================================
# FAST CSV READ CACHE — file-signature aware, automatically invalidated after every write
# ============================================================

_ISLAMIYAH_READ_CACHE = {}

def _read_rows(path, headers):
    _ensure_csv(path, headers); key = str(path.resolve())
    with ISLAMIYAH_LOCK:
        try: stat = path.stat(); signature = (stat.st_mtime_ns, stat.st_size)
        except OSError: signature = (0, 0)
        cached = _ISLAMIYAH_READ_CACHE.get(key)
        if cached and cached.get("signature") == signature: return [dict(row) for row in cached.get("rows", ())]
        with path.open("r", newline="", encoding="utf-8-sig") as file: rows = list(csv.DictReader(file))
        _ISLAMIYAH_READ_CACHE[key] = {"signature": signature, "rows": tuple(dict(row) for row in rows)}; return [dict(row) for row in rows]

def _write_rows(path, headers, rows):
    _ensure_csv(path, headers); temp = path.with_suffix(path.suffix + ".tmp"); key = str(path.resolve())
    with ISLAMIYAH_LOCK:
        with temp.open("w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(file, fieldnames=headers, extrasaction="ignore"); writer.writeheader(); writer.writerows(rows)
        temp.replace(path); _ISLAMIYAH_READ_CACHE.pop(key, None)
    return path


def read_enrollments(): return _read_rows(ENROLLMENT_FILE, ENROLLMENT_HEADERS)
def write_enrollments(rows):
    rows = list(rows); current_session = get_current_academic_context().get("academic_session", "")
    result = _write_rows(ENROLLMENT_FILE, ENROLLMENT_HEADERS, rows); _ISLAMIYAH_SEED_RUNTIME.clear()
    sync_current_islamiyah_profiles(rows, current_session); return result

# Seed known class placements from the combined register, preserving every existing session placement.
def seed_register_enrollments(academic_session):
    session_value = normalize_islamiyah_session(academic_session); now_tick = time.monotonic(); cached = _ISLAMIYAH_SEED_RUNTIME.get(session_value)
    if cached and now_tick - cached < 30: return read_enrollments()
    indexes = master_identity_indexes()
    with ISLAMIYAH_LOCK:
        rows = read_enrollments(); by_key = {_enrollment_key(row.get("Session"), row.get("Admission_number")): dict(row) for row in rows}; changed = False; now = now_string()
        for profile in read_register():
            if not profile.get("Islamiyah_Source") and not profile.get("Islamiyah_Class"): continue
            admission = clean(profile.get("Admission_number")); key = _enrollment_key(session_value, admission); previous = by_key.get(key, {})
            master = resolve_master_identity(admission, profile.get("Last_name"), profile.get("First_name"), profile.get("Other_names"), linked_admission_number=profile.get("Regular_Admission_number") or previous.get("Linked_admission_number"), indexes=indexes)
            linked = clean(master.get("admission_number")) if master else clean(profile.get("Regular_Admission_number") or previous.get("Linked_admission_number")); regular_class = clean(master.get("class_arm")) if master else clean(profile.get("Regular_Class") or previous.get("Regular_class")); regular_level = clean_upper(master.get("class_level")) if master else clean_upper(profile.get("Regular_Class_category") or previous.get("Regular_class_level"))
            record = {**previous, "Session": session_value, "Admission_number": admission, "Linked_admission_number": linked, "Last_name": clean(profile.get("Last_name") or previous.get("Last_name")), "First_name": clean(profile.get("First_name") or previous.get("First_name")), "Other_names": clean(profile.get("Other_names") or previous.get("Other_names")), "Full_name": " ".join(filter(None, [profile.get("Last_name"), profile.get("First_name"), profile.get("Other_names")])) or clean(previous.get("Full_name")), "Sex": clean(profile.get("Sex") or previous.get("Sex")), "Phone": clean(profile.get("Phone") or previous.get("Phone")), "Regular_class": regular_class, "Regular_class_level": regular_level, "Islamiyah_class": clean_upper(profile.get("Islamiyah_Class") or previous.get("Islamiyah_class")), "Source": clean_upper(profile.get("Islamiyah_Source") or previous.get("Source") or "ISLAMIYYAH_DATABASE"), "Source_note": clean(profile.get("Source_note") or previous.get("Source_note")), "Active": clean_upper(previous.get("Active") or "YES"), "Imported_at": clean(previous.get("Imported_at")) or now, "Updated_at": clean(previous.get("Updated_at")) or now, "Updated_by": clean(previous.get("Updated_by")) or "Combined student register"}
            if record != previous: by_key[key] = record; changed = True
        output = list(by_key.values())
        if changed: _write_rows(ENROLLMENT_FILE, ENROLLMENT_HEADERS, output); sync_current_islamiyah_profiles(output, session_value)
        _ISLAMIYAH_SEED_RUNTIME[session_value] = time.monotonic()
    return output

def read_scores(): return _read_rows(SCORE_FILE, SCORE_HEADERS)
def write_scores(rows): return _write_rows(SCORE_FILE, SCORE_HEADERS, rows)
def read_regular_school_scores(): return _read_rows(REGULAR_SCORE_FILE, REGULAR_SCORE_HEADERS)
def write_regular_school_scores(rows): return _write_rows(REGULAR_SCORE_FILE, REGULAR_SCORE_HEADERS, rows)


# ============================================================
# ACADEMY DATABASE MANAGEMENT — roster CRUD + immutable regular-school bridge
# ============================================================
def _next_academy_admission(prefix="isl"):
    prefix = clean(prefix).lower() or "isl"; used = set()
    for row in read_enrollments():
        admission = normalize_admission_number(row.get("Admission_number"))
        if admission.startswith(prefix): used.add(admission)
    for row in read_register():
        admission = normalize_admission_number(row.get("Admission_number"))
        if admission.startswith(prefix): used.add(admission)
    highest = 0
    for admission in used:
        suffix = admission[len(prefix):]
        if suffix.isdigit(): highest = max(highest, int(suffix))
    return f"{prefix}{highest + 1:03d}"


def log_academy_activity(action, school, academic_session="", admission_numbers=None, target_class="", actor="", note=""):
    ensure_islamiyah_storage(); admissions = [clean(value) for value in (admission_numbers or []) if clean(value)]; row = {"Timestamp": now_string(), "Session": normalize_academic_session(academic_session) if academic_session else "", "Action": clean_upper(action), "School": clean_upper(school), "Admission_numbers": ", ".join(admissions), "Target_class": clean(target_class), "Actor": clean(actor) or "EMIS Staff", "Note": clean(note)}
    with ISLAMIYAH_LOCK:
        rows = _read_rows(ACTIVITY_FILE, ACTIVITY_HEADERS); rows.append(row); _write_rows(ACTIVITY_FILE, ACTIVITY_HEADERS, rows[-1500:])
    return row


def get_academy_activity(limit=80, school=""):
    wanted = clean_upper(school); rows = _read_rows(ACTIVITY_FILE, ACTIVITY_HEADERS)
    if wanted: rows = [row for row in rows if clean_upper(row.get("School")) == wanted]
    rows.reverse(); return rows[:max(1, min(int(limit or 80), 250))]


def enroll_regular_students(academic_session, admission_numbers, islamiyah_class, updated_by=""):
    """Create/update linked Academy rows without modifying students2026.csv."""
    session_value = normalize_islamiyah_session(academic_session); target = normalize_islamiyah_class(islamiyah_class); admissions = []
    for value in admission_numbers or []:
        admission = normalize_admission_number(value)
        if admission and admission not in admissions: admissions.append(admission)
    if not admissions: raise ValueError("Select at least one regular-school student.")
    master = {normalize_admission_number(row.get("admission_number")): row for row in get_all_students(active_only=True)}; missing = [value for value in admissions if value not in master]
    if missing: raise ValueError(f"{len(missing)} selected student(s) were not found in the active regular-school database.")
    with ISLAMIYAH_LOCK:
        rows = read_enrollments(); now = now_string(); linked_map = {}
        for index, row in enumerate(rows):
            if normalize_academic_session(row.get("Session")) != session_value or clean_upper(row.get("Active") or "YES") != "YES": continue
            linked = normalize_admission_number(row.get("Linked_admission_number"))
            if linked: linked_map.setdefault(linked, []).append(index)
        created, updated, academy_ids = 0, 0, []
        for regular in admissions:
            student = master[regular]; indexes = linked_map.get(regular, [])
            if len(indexes) > 1: raise ValueError(f"{clean(student.get('admission_number'))} has multiple active Islamiyyah links. Resolve the duplicate before registering it again.")
            payload = {"Linked_admission_number": clean(student.get("admission_number")), "Last_name": clean(student.get("last_name")), "First_name": clean(student.get("first_name")), "Other_names": clean(student.get("other_names")), "Full_name": clean(student.get("full_name")) or _student_name(student), "Sex": clean(student.get("sex")), "Phone": clean(student.get("phone")), "Regular_class": clean(student.get("class_arm") or student.get("class")), "Regular_class_level": clean_upper(student.get("class_level") or student.get("class_category")), "Islamiyah_class": target, "Source": "REGULAR_DATABASE", "Source_note": "Linked from immutable regular-school master", "Active": "YES", "Updated_at": now, "Updated_by": clean(updated_by) or "EMIS Staff"}
            if indexes:
                idx = indexes[0]; rows[idx].update(payload); academy_ids.append(clean(rows[idx].get("Admission_number"))); updated += 1
            else:
                academy_id = _next_academy_admission("isl"); existing_ids = {normalize_admission_number(row.get("Admission_number")) for row in rows}
                while normalize_admission_number(academy_id) in existing_ids: academy_id = f"isl{int(academy_id[3:]) + 1:03d}"
                rows.append({"Session": session_value, "Admission_number": academy_id, **payload, "Imported_at": now}); academy_ids.append(academy_id); created += 1
        if rows: backup_islamiyah_file(ENROLLMENT_FILE, "regular_to_islamiyah")
        write_enrollments(rows)
    log_academy_activity("REGISTER_FROM_BASIC", "ISLAMIYAH", session_value, academy_ids, target, updated_by, f"{created} created, {updated} updated; regular master unchanged")
    return {"session": session_value, "islamiyah_class": target, "islamiyah_class_label": islamiyah_class_label(target), "created": created, "updated": updated, "academy_admission_numbers": academy_ids}


def add_islamiyah_student(academic_session, payload, updated_by=""):
    session_value = normalize_islamiyah_session(academic_session); target = normalize_islamiyah_class(payload.get("islamiyah_class")); admission = normalize_admission_number(payload.get("admission_number")) or _next_academy_admission("isl"); now = now_string(); linked = normalize_admission_number(payload.get("regular_admission_number"))
    if linked: return enroll_regular_students(session_value, [linked], target, updated_by)
    last_name, first_name, other_names = clean(payload.get("last_name")), clean(payload.get("first_name")), clean(payload.get("other_names"))
    if not last_name or not first_name: raise ValueError("Last name and first name are required for an independent Islamiyyah student.")
    with ISLAMIYAH_LOCK:
        rows = read_enrollments(); key = _enrollment_key(session_value, admission)
        if any(_enrollment_key(row.get("Session"), row.get("Admission_number")) == key and clean_upper(row.get("Active") or "YES") == "YES" for row in rows): raise ValueError(f"Academy admission {admission} already exists in this session.")
        row = {"Session": session_value, "Admission_number": admission, "Linked_admission_number": "", "Last_name": last_name, "First_name": first_name, "Other_names": other_names, "Full_name": " ".join(part for part in [last_name, first_name, other_names] if part), "Sex": clean(payload.get("sex")), "Phone": clean(payload.get("phone")), "Regular_class": "", "Regular_class_level": "", "Islamiyah_class": target, "Source": "ISLAMIYYAH_DATABASE", "Source_note": "Independent Academy student", "Active": "YES", "Imported_at": now, "Updated_at": now, "Updated_by": clean(updated_by) or "EMIS Staff"}; rows.append(row); backup_islamiyah_file(ENROLLMENT_FILE, "add_islamiyah_student"); write_enrollments(rows)
    log_academy_activity("ADD", "ISLAMIYAH", session_value, [admission], target, updated_by, "Independent Academy student")
    return enrollment_to_record(row)


def update_islamiyah_student(academic_session, admission_number, payload, updated_by=""):
    session_value = normalize_islamiyah_session(academic_session); admission = normalize_admission_number(admission_number); target = normalize_islamiyah_class(payload.get("islamiyah_class"), allow_blank=True); now = now_string()
    with ISLAMIYAH_LOCK:
        rows = read_enrollments(); matched = None
        for row in rows:
            if normalize_academic_session(row.get("Session")) != session_value or normalize_admission_number(row.get("Admission_number")) != admission or clean_upper(row.get("Active") or "YES") != "YES": continue
            matched = row; linked = normalize_admission_number(row.get("Linked_admission_number"))
            # Academy profile fields are editable; the regular-school master is never written here.
            for field, key in [("Last_name","last_name"),("First_name","first_name"),("Other_names","other_names"),("Phone","phone"),("Sex","sex")]:
                if key in payload: row[field] = clean(payload.get(key))
            row["Full_name"] = " ".join(part for part in [clean(row.get("Last_name")), clean(row.get("First_name")), clean(row.get("Other_names"))] if part); row["Islamiyah_class"] = target or clean_upper(row.get("Islamiyah_class")); row["Updated_at"], row["Updated_by"] = now, clean(updated_by) or "EMIS Staff"; row["Source_note"] = clean(row.get("Source_note")) or ("Linked Academy profile; regular master remains read-only" if linked else "Independent Academy student"); break
        if not matched: raise ValueError("Active Islamiyyah student record was not found.")
        backup_islamiyah_file(ENROLLMENT_FILE, "edit_islamiyah_student"); write_enrollments(rows)
    log_academy_activity("EDIT", "ISLAMIYAH", session_value, [clean(matched.get("Admission_number"))], matched.get("Islamiyah_class"), updated_by, "Academy profile only; regular master unchanged")
    return enrollment_to_record(matched)


def remove_islamiyah_students(academic_session, admission_numbers, updated_by=""):
    """Soft-remove from the current Academy roster; score/history records remain archived."""
    session_value = normalize_islamiyah_session(academic_session); wanted = {normalize_admission_number(value) for value in (admission_numbers or []) if normalize_admission_number(value)}
    if not wanted: raise ValueError("Select at least one Islamiyyah student to remove.")
    with ISLAMIYAH_LOCK:
        rows = read_enrollments(); removed = []; now = now_string()
        for row in rows:
            if normalize_academic_session(row.get("Session")) == session_value and normalize_admission_number(row.get("Admission_number")) in wanted and clean_upper(row.get("Active") or "YES") == "YES": row["Active"], row["Updated_at"], row["Updated_by"] = "NO", now, clean(updated_by) or "EMIS Staff"; removed.append(clean(row.get("Admission_number")))
        if not removed: raise ValueError("No active Islamiyyah records matched the selected students.")
        backup_islamiyah_file(ENROLLMENT_FILE, "remove_islamiyah_students"); write_enrollments(rows)
    log_academy_activity("REMOVE", "ISLAMIYAH", session_value, removed, "", updated_by, "Roster deactivated; score history preserved; regular master unchanged")
    return {"session": session_value, "removed": removed, "count": len(removed)}


def clear_islamiyah_score_records(academic_session, term, admission_numbers, subject="", updated_by=""):
    session_value = normalize_islamiyah_session(academic_session); term_value = normalize_academic_term(term); wanted = {normalize_admission_number(value) for value in (admission_numbers or []) if normalize_admission_number(value)}; subject_key = clean_upper(subject)
    if not term_value: raise ValueError("A valid academic term is required.")
    if not wanted: raise ValueError("Select at least one score record to clear.")
    with ISLAMIYAH_LOCK:
        rows = read_scores(); removed = [] ; kept = []
        for row in rows:
            admission = normalize_admission_number(row.get("Admission_number")); match = normalize_academic_session(row.get("Session")) == session_value and normalize_academic_term(row.get("Term")) == term_value and admission in wanted and (not subject_key or subject_key in {clean_upper(row.get("Subject_key")), clean_upper(row.get("Subject"))})
            if match: removed.append(admission); continue
            kept.append(row)
        if removed: backup_islamiyah_file(SCORE_FILE, "bulk_score_clear"); write_scores(kept)
    unique = sorted(set(removed)); log_academy_activity("CLEAR_SCORE", "ISLAMIYAH", session_value, unique, subject_key, updated_by, f"{len(removed)} subject score row(s) cleared for {term_value}")
    return {"session": session_value, "term": term_value, "cleared": len(removed), "students": unique}


def clear_regular_school_score_records(academic_session, term, admission_numbers, updated_by=""):
    """Delete only Islamiyyah score rows; students2026.csv remains immutable."""
    session_value = normalize_islamiyah_session(academic_session); term_value = normalize_academic_term(term); wanted = {normalize_admission_number(value) for value in (admission_numbers or []) if normalize_admission_number(value)}
    if not term_value: raise ValueError("A valid academic term is required.")
    if not wanted: raise ValueError("Select at least one regular-school Islamiyyah score record to clear.")
    with ISLAMIYAH_LOCK:
        rows = read_regular_school_scores(); kept, removed = [], []
        for row in rows:
            admission = normalize_admission_number(row.get("Admission_number")); match = normalize_academic_session(row.get("Session")) == session_value and normalize_academic_term(row.get("Term")) == term_value and admission in wanted
            if match: removed.append(admission); continue
            kept.append(row)
        if removed: backup_islamiyah_file(REGULAR_SCORE_FILE, "regular_bulk_score_clear"); write_regular_school_scores(kept)
    unique = sorted(set(removed)); log_academy_activity("CLEAR_SCORE", "REGULAR_ISLAMIYYAH", session_value, unique, "", updated_by, f"{len(removed)} direct Islamiyyah score row(s) cleared; master student records untouched")
    return {"session": session_value, "term": term_value, "cleared": len(removed), "students": unique}


def regular_school_class_options():
    students = get_all_students(active_only=True); counts = {}; display_labels = {"PRIMARY1": "Basic 1 / Primary 1", "PRIMARY2": "Basic 2 / Primary 2", "PRIMARY3": "Basic 3 / Primary 3", "PRIMARY4": "Basic 4 / Primary 4", "PRIMARY5": "Basic 5 / Primary 5", "PRIMARY6": "Basic 6 / Primary 6", "JSS1": "Basic 7 / JSS1", "JSS2": "Basic 8 / JSS2", "JSS3": "Basic 9 / JSS3", "SS1": "Basic 10 / SS1", "SS2": "Basic 11 / SS2", "SS3": "Basic 12 / SS3"}
    for student in students:
        level = clean_upper(student.get("class_level")); arm = clean_upper(student.get("class_arm"))
        if level and arm: counts[arm] = counts.get(arm, 0) + 1
    return [{"key": level, "label": display_labels.get(level, CLASS_LABELS.get(level, level)), "arms": [{"key": arm, "label": arm, "count": counts.get(arm, 0)} for arm in CLASS_ARMS_BY_LEVEL.get(level, [])], "count": sum(counts.get(arm, 0) for arm in CLASS_ARMS_BY_LEVEL.get(level, []))} for level in REGULAR_CLASS_LEVELS]


def _regular_score_key(session_value, term, admission): return "|".join([normalize_academic_session(session_value), normalize_academic_term(term), normalize_admission_number(admission)])


def regular_score_to_record(row):
    ca, exam = score_number(row.get("CA")), score_number(row.get("Exam")); exempt = clean_upper(row.get("Exempt")) == "YES"; complete = exempt or clean_upper(row.get("Complete")) == "YES" or (ca is not None and exam is not None); total = score_number(row.get("Total"))
    if complete and not exempt and total is None and ca is not None and exam is not None: total = round(ca + exam, 2)
    return {"session": normalize_academic_session(row.get("Session")), "term": normalize_academic_term(row.get("Term")), "admission_number": clean(row.get("Admission_number")), "regular_admission_number": clean(row.get("Admission_number")), "academy_admission_number": "", "class_level": clean_upper(row.get("Class_level")), "class_arm": clean_upper(row.get("Class_arm")), "regular_class": clean_upper(row.get("Class_arm")), "last_name": clean(row.get("Last_name")), "first_name": clean(row.get("First_name")), "other_names": clean(row.get("Other_names")), "full_name": " ".join(value for value in [clean(row.get("Last_name")), clean(row.get("First_name")), clean(row.get("Other_names"))] if value), "ca": None if exempt else ca, "exam": None if exempt else exam, "total": None if exempt else (total if complete else None), "provisional_total": None if exempt else (round((ca or 0) + (exam or 0), 2) if ca is not None or exam is not None else None), "complete": complete, "exempt": exempt, "saved_at": clean(row.get("Saved_at")), "saved_by": clean(row.get("Saved_by")), "source": "REGULAR_SCHOOL_DATABASE"}


def get_regular_school_score(academic_session, term, admission_number):
    key = _regular_score_key(academic_session, term, admission_number)
    for row in read_regular_school_scores():
        if _regular_score_key(row.get("Session"), row.get("Term"), row.get("Admission_number")) == key: return regular_score_to_record(row)
    return None


def save_regular_school_islamiyah_score(academic_session, term, admission_number, ca=None, exam=None, saved_by="", exempt=False):
    session_value = normalize_islamiyah_session(academic_session); term_value = normalize_academic_term(term)
    if not term_value: raise ValueError("A valid FIRST, SECOND or THIRD term is required.")
    admission = normalize_admission_number(admission_number); student = get_student(admission, active_only=True); exempt_value = exempt is True or clean_upper(exempt) in {"YES", "TRUE", "1", "ON"}
    if not student: raise ValueError("Student was not found in the active regular-school database.")
    ca_value, exam_value = (None, None) if exempt_value else (_validate_score(ca, CA_MAX, "CA"), _validate_score(exam, EXAM_MAX, "Exam")); target_key = _regular_score_key(session_value, term_value, admission)
    with ISLAMIYAH_LOCK:
        rows = read_regular_school_scores(); remaining = [row for row in rows if _regular_score_key(row.get("Session"), row.get("Term"), row.get("Admission_number")) != target_key]
        if not exempt_value and ca_value is None and exam_value is None:
            if len(remaining) != len(rows): backup_islamiyah_file(REGULAR_SCORE_FILE, "regular_score_clear"); write_regular_school_scores(remaining)
            return {"deleted": True, "admission_number": clean(student.get("admission_number")), "regular_admission_number": clean(student.get("admission_number")), "ca": None, "exam": None, "total": None, "complete": False, "exempt": False, "source": "REGULAR_SCHOOL_DATABASE"}
        complete = exempt_value or (ca_value is not None and exam_value is not None); total = round(ca_value + exam_value, 2) if complete and not exempt_value else ""; now = now_string()
        new_row = {"Session": session_value, "Term": term_value, "Admission_number": clean(student.get("admission_number")), "Class_level": clean_upper(student.get("class_level")), "Class_arm": clean_upper(student.get("class_arm")), "Last_name": clean(student.get("last_name")), "First_name": clean(student.get("first_name")), "Other_names": clean(student.get("other_names")), "CA": _storage(ca_value), "Exam": _storage(exam_value), "Total": total, "Complete": "YES" if complete else "NO", "Exempt": "YES" if exempt_value else "NO", "Saved_at": now, "Saved_by": clean(saved_by) or "Staff"}
        if rows: backup_islamiyah_file(REGULAR_SCORE_FILE, "regular_score_save")
        write_regular_school_scores(remaining + [new_row])
    return regular_score_to_record(new_row)


def get_regular_school_roster(academic_session="", term="", class_level="", class_arm="", search="", include_scores=True):
    session_value = normalize_academic_session(academic_session) if academic_session else ""; term_value = normalize_academic_term(term) if term else ""; level = normalize_class_level(class_level) if class_level else ""; arm = normalize_class_arm(class_arm, level) if class_arm else ""; token = clean(search).lower(); scores = {}
    if include_scores and session_value and term_value:
        scores = {normalize_admission_number(row.get("admission_number")): row for row in (regular_score_to_record(item) for item in read_regular_school_scores()) if row.get("session") == session_value and row.get("term") == term_value}
    students = []
    for student in get_all_students(active_only=True):
        if level and clean_upper(student.get("class_level")) != level: continue
        if arm and clean_upper(student.get("class_arm")) != arm: continue
        haystack = " ".join([clean(student.get("admission_number")), clean(student.get("full_name")), clean(student.get("class_level")), clean(student.get("class_arm")), clean(student.get("phone"))]).lower()
        if token and token not in haystack: continue
        admission = normalize_admission_number(student.get("admission_number")); score = scores.get(admission)
        students.append({**student, "regular_admission_number": clean(student.get("admission_number")), "academy_admission_number": "", "regular_class": clean(student.get("class_arm")), "score_source": "regular_school", "scores": score, "ca_average": score.get("ca") if score else None, "exam_average": score.get("exam") if score else None, "total": score.get("total") if score else None, "complete": bool(score and score.get("complete")), "exempt": bool(score and score.get("exempt")), "status": "exempt" if score and score.get("exempt") else "complete" if score and score.get("complete") else "partial" if score and (score.get("ca") is not None or score.get("exam") is not None) else "pending", "subject_count": 1, "subjects_complete": 1 if score and score.get("complete") else 0, "islamiyah_class": "REGULAR_SCHOOL", "islamiyah_class_label": "Regular School Islamiyyah", "pending_subjects": [] if score and score.get("complete") else ["Islamiyyah"]})
    return {"session": session_value, "term": term_value, "class_level": level, "class_arm": arm, "students": students, "count": len(students), "complete_students": sum(1 for row in students if row.get("complete")), "partial_students": sum(1 for row in students if row.get("status") == "partial"), "pending_students": sum(1 for row in students if row.get("status") == "pending"), "linked_students": len(students), "classes": regular_school_class_options(), "source": "REGULAR_SCHOOL_DATABASE"}


def get_regular_school_report_sheet(admission_number, academic_session, term):
    student = get_student(admission_number, active_only=True)
    if not student: raise ValueError("Student was not found in the active regular-school database.")
    score = get_regular_school_score(academic_session, term, admission_number) or {}; exempt = bool(score.get("exempt")); component = {"subject": "Islamiyyah", "subject_key": "ISLAMIYYAH", "ca": score.get("ca"), "exam": score.get("exam"), "total": score.get("total"), "complete": bool(score.get("complete")), "exempt": exempt, "saved_at": score.get("saved_at", ""), "saved_by": score.get("saved_by", "")}
    row = {**student, "regular_admission_number": clean(student.get("admission_number")), "academy_admission_number": "", "regular_class": clean(student.get("class_arm")), "islamiyah_class": "REGULAR_SCHOOL", "islamiyah_class_label": "Regular School Islamiyyah", "score_source": "regular_school", "subject_count": 1, "subjects_complete": 1 if component["complete"] else 0, "ca_complete": exempt or component.get("ca") is not None, "exam_complete": exempt or component.get("exam") is not None, "complete": component["complete"], "exempt": exempt, "ca_average": component.get("ca"), "exam_average": component.get("exam"), "total": component.get("total"), "status": "exempt" if exempt else "complete" if component["complete"] else "partial" if component.get("ca") is not None or component.get("exam") is not None else "pending", "pending_subjects": [] if component["complete"] else ["Islamiyyah"], "components": [component]}
    return {"session": normalize_academic_session(academic_session), "term": normalize_academic_term(term), "student": row, "subjects": [component], "ca_max": CA_MAX, "exam_max": EXAM_MAX, "total_max": TOTAL_MAX, "source": "REGULAR_SCHOOL_DATABASE"}


def get_regular_school_islamiyah_row(admission_number, academic_session, term):
    score = get_regular_school_score(academic_session, term, admission_number)
    if not score: return None
    ca, exam, total, complete, exempt = score.get("ca"), score.get("exam"), score.get("total"), bool(score.get("complete")), bool(score.get("exempt")); student = get_student(admission_number, active_only=False) or {}; grade = "N/A" if exempt else "-"; comment = "Does not take Islamiyyah" if exempt else "Pending Islamiyyah scores"
    if total is not None and not exempt:
        if total >= 80: grade, comment = "A", "Excellent"
        elif total >= 70: grade, comment = "B", "Very Good"
        elif total >= 60: grade, comment = "C", "Good"
        elif total >= 45: grade, comment = "D", "Pass"
        elif total >= 40: grade, comment = "E", "Pass"
        else: grade, comment = "F", "Fail"
    return {"subject": "Islamiyyah", "subject_key": "ISLAMIYYAH", "mode": "ISLAMIYYAH", "assessment_mode": "ISLAMIYYAH", "source": "ISLAMIYYAH_SCHOOL_REGULAR_DATABASE", "academy_admission_number": "", "regular_admission_number": clean(student.get("admission_number") or admission_number), "ca_max": CA_MAX, "exam_max": EXAM_MAX, "total_max": TOTAL_MAX, "islamiyah_class": "REGULAR_SCHOOL", "islamiyah_class_label": "Regular School Islamiyyah", "position": 0, "position_text": "--", "out_of": 0, "lowest": None, "highest": None, "class_average": None, "has_ca": ca is not None, "has_exam": exam is not None, "ca_complete": exempt or ca is not None, "exam_complete": exempt or exam is not None, "complete": complete, "exempt": exempt, "ca": ca, "ca_total": ca, "exam": exam, "total": total, "provisional_total": score.get("provisional_total"), "grade": grade, "comment": comment, "islamiyah_status": "exempt" if exempt else "complete" if complete else "partial", "islamiyah_subject_count": 1, "islamiyah_subjects_complete": 1 if complete else 0, "islamiyah_components": [{"subject": "Islamiyyah", "subject_key": "ISLAMIYYAH", "ca": ca, "exam": exam, "total": total, "complete": complete, "exempt": exempt, "saved_at": score.get("saved_at", "")}], "score_source": "regular_school"}


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
    academy_admission = clean(row.get("Admission_number")); linked = clean(row.get("Linked_admission_number")); regular_admission = linked or (academy_admission if normalize_admission_number(academy_admission).startswith("std") else "")
    return {
        "session": normalize_academic_session(row.get("Session")), "admission_number": academy_admission, "academy_admission_number": academy_admission, "linked_admission_number": linked, "regular_admission_number": regular_admission, "last_name": clean(row.get("Last_name")), "first_name": clean(row.get("First_name")),
        "other_names": clean(row.get("Other_names")), "full_name": clean(row.get("Full_name")) or " ".join(value for value in [clean(row.get("Last_name")), clean(row.get("First_name")), clean(row.get("Other_names"))] if value),
        "sex": clean(row.get("Sex")), "phone": clean(row.get("Phone")), "regular_class": clean(row.get("Regular_class")), "regular_class_level": clean_upper(row.get("Regular_class_level")),
        "islamiyah_class": clean_upper(row.get("Islamiyah_class")), "islamiyah_class_label": islamiyah_class_label(row.get("Islamiyah_class")) if clean(row.get("Islamiyah_class")) else "Unassigned",
        "source_note": clean(row.get("Source_note")), "source": clean_upper(row.get("Source")) or "REGULAR_DATABASE", "active": clean_upper(row.get("Active") or "YES") == "YES", "imported_at": clean(row.get("Imported_at")), "updated_at": clean(row.get("Updated_at")), "updated_by": clean(row.get("Updated_by")), "linked_to_regular_school": bool(regular_admission),
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


def get_enrollment(admission_number, academic_session, active_only=False, ensure_seed=True):
    session_value, admission = normalize_academic_session(academic_session), normalize_admission_number(admission_number)
    if not session_value or not admission: return None
    if ensure_seed and session_value == get_current_academic_context().get("academic_session"): seed_register_enrollments(session_value)
    matches = []
    for row in read_enrollments():
        if normalize_academic_session(row.get("Session")) != session_value: continue
        academy = normalize_admission_number(row.get("Admission_number")); linked = normalize_admission_number(row.get("Linked_admission_number")); record = enrollment_to_record(row)
        if admission not in {academy, linked}: continue
        if active_only and not record.get("active"): continue
        matches.append(record)
    if not matches: return None
    exact = [row for row in matches if normalize_admission_number(row.get("admission_number")) == admission]
    if exact: matches = exact
    elif admission.startswith("std") and len(matches) > 1: return None  # Never guess between duplicate Academy rows linked to one regular admission.
    matches.sort(key=lambda row: (bool(row.get("active")), bool(row.get("islamiyah_class"))), reverse=True); return matches[0]

def list_enrollments(academic_session, islamiyah_class="", regular_class="", active_only=True, search=""):
    session_value = normalize_academic_session(academic_session); level = normalize_islamiyah_class(islamiyah_class, allow_blank=True); regular = clean_upper(regular_class); token = clean(search).lower(); rows = []
    if session_value == get_current_academic_context().get("academic_session"): seed_register_enrollments(session_value)
    for row in read_enrollments():
        record = enrollment_to_record(row)
        if record.get("session") != session_value: continue
        if active_only and not record.get("active"): continue
        if level and record.get("islamiyah_class") != level: continue
        if regular and regular not in {clean_upper(record.get("regular_class")), clean_upper(record.get("regular_class_level"))}: continue
        haystack = " ".join([record.get("admission_number", ""), record.get("regular_admission_number", ""), record.get("full_name", ""), record.get("regular_class", ""), record.get("islamiyah_class_label", "")]).lower()
        if token and token not in haystack: continue
        rows.append(record)
    rows.sort(key=lambda item: (item.get("islamiyah_class") or "ZZZ", item.get("regular_class") or "", item.get("last_name", "").lower(), item.get("first_name", "").lower(), item.get("admission_number", "").lower()))
    return rows

def get_islamiyah_roster_coverage(academic_session):
    """Compare regular-school students with one-to-one Academy links; ambiguous duplicate links are never treated as verified."""
    session_value = normalize_islamiyah_session(academic_session); master = get_all_students(active_only=True); imported = list_enrollments(session_value, active_only=True); master_map = {normalize_admission_number(row.get("admission_number")): row for row in master if normalize_admission_number(row.get("admission_number"))}; candidates = {}; standalone = []
    for row in imported:
        regular = normalize_admission_number(row.get("regular_admission_number"))
        if regular and regular in master_map: candidates.setdefault(regular, []).append(row)
        else: standalone.append(row)
    duplicate_links = {regular: rows for regular, rows in candidates.items() if len(rows) > 1}; linked_imported_map = {regular: rows[0] for regular, rows in candidates.items() if len(rows) == 1}; ambiguous_rows = [row for rows in duplicate_links.values() for row in rows]; standalone.extend(ambiguous_rows)
    missing = sorted(admission for admission in master_map if admission not in linked_imported_map); stale = []
    for admission, target in linked_imported_map.items():
        source = master_map[admission]; expected_class = clean(source.get("class_arm") or source.get("class")); expected_level = clean_upper(source.get("class_level") or source.get("class_category"))
        if clean(target.get("regular_class")) != expected_class or clean_upper(target.get("regular_class_level")) != expected_level: stale.append({"admission_number": clean(source.get("admission_number")), "stored_class": clean(target.get("regular_class")), "current_class": expected_class})
    by_regular_class = {}
    for row in master:
        level = clean_upper(row.get("class_level") or row.get("class_category")) or "UNKNOWN"; item = by_regular_class.setdefault(level, {"master": 0, "synced": 0, "missing": 0}); item["master"] += 1; admission = normalize_admission_number(row.get("admission_number")); item["synced" if admission in linked_imported_map else "missing"] += 1
    return {"session": session_value, "master_students": len(master_map), "synced_students": len(linked_imported_map), "linked_students": len(linked_imported_map), "standalone_students": len(standalone), "ambiguous_link_rows": len(ambiguous_rows), "duplicate_regular_links": len(duplicate_links), "duplicate_link_admissions": sorted(duplicate_links)[:100], "total_islamiyah_roster": len(imported), "missing_students": len(missing), "stale_regular_class_records": len(stale), "sync_required": bool(missing or stale or duplicate_links), "missing_admissions": missing[:100], "stale_students": stale[:100], "by_regular_class": by_regular_class, "source": "students2026.csv + Academy identity link", "message": f"{len(linked_imported_map)} Islamiyyah record(s) have safe one-to-one regular-school links; {len(ambiguous_rows)} row(s) have ambiguous duplicate links and {len(standalone)-len(ambiguous_rows)} remain independent Academy records."}

def import_current_student_database(academic_session, updated_by=""):
    """Refresh verified std... links and regular-class profiles without importing unrelated regular pupils into the independent Academy roster."""
    session_value = normalize_islamiyah_session(academic_session); students = get_all_students(active_only=True); now = now_string(); master_map = {normalize_admission_number(student.get("admission_number")): student for student in students if normalize_admission_number(student.get("admission_number"))}
    with ISLAMIYAH_LOCK:
        existing = seed_register_enrollments(session_value); rows = [dict(row) for row in existing]; linked = 0; refreshed = 0
        for row in rows:
            if normalize_academic_session(row.get("Session")) != session_value: continue
            regular = normalize_admission_number(row.get("Linked_admission_number")); academy = normalize_admission_number(row.get("Admission_number"))
            if not regular and academy in master_map: regular = academy; row["Linked_admission_number"] = clean(master_map[academy].get("admission_number"))
            student = master_map.get(regular)
            if not student: continue
            linked += 1; row.update({"Linked_admission_number": clean(student.get("admission_number")), "Regular_class": clean(student.get("class_arm") or student.get("class")), "Regular_class_level": clean_upper(student.get("class_level") or student.get("class_category")), "Phone": clean(row.get("Phone")) or clean(student.get("phone")), "Sex": clean(row.get("Sex")) or clean(student.get("sex")), "Updated_at": now, "Updated_by": clean(updated_by) or "EMIS Admin"}); refreshed += 1
        if existing: backup_islamiyah_file(ENROLLMENT_FILE, "roster_link_sync")
        rows.sort(key=lambda row: (normalize_academic_session(row.get("Session")), clean_upper(row.get("Islamiyah_class")) or "ZZZ", clean_upper(row.get("Regular_class")), clean(row.get("Last_name")).lower(), clean(row.get("Admission_number")).lower())); write_enrollments(rows)
    imported = [enrollment_to_record(row) for row in rows if normalize_academic_session(row.get("Session")) == session_value and clean_upper(row.get("Active") or "YES") == "YES"]; assigned = sum(1 for row in imported if row.get("islamiyah_class"))
    return {"session": session_value, "students": imported, "count": len(imported), "assigned": assigned, "unassigned": len(imported)-assigned, "linked": linked, "refreshed": refreshed, "updated_at": now}

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



ISLAMIYAH_PROMOTION_PATH = ["ISLAMIYAH_STARTER", "ISLAMIYAH_PREP1", "ISLAMIYAH1", "ISLAMIYAH2", "ISLAMIYAH3", "ISLAMIYAH4", "ISLAMIYAH5", "ISLAMIYAH6", "ISLAMIYAH7"]


def next_islamiyah_class(class_level):
    level = normalize_islamiyah_class(class_level); base = islamiyah_base_level(level)
    if base != level:
        target = f"ISLAMIYAH{int(base.removeprefix('ISLAMIYAH')) + 1}{level[-1]}"
        if target in ISLAMIYAH_ROSTER_CLASSES: return target
        return "ISLAMIYAH7" if base == "ISLAMIYAH6" else ""
    try: index = ISLAMIYAH_PROMOTION_PATH.index(level)
    except ValueError: return ""
    return ISLAMIYAH_PROMOTION_PATH[index + 1] if index + 1 < len(ISLAMIYAH_PROMOTION_PATH) else ""


def upsert_external_islamiyah_students(academic_session, students, islamiyah_class, updated_by="", source="TAHFEEZ"):
    """Create/update independent Islamiyah roster rows from a non-regular-school source.

    This is intentionally separate from students2026.csv import so real standalone Tahfeez pupils
    can move into Islamiyah after Tahfeez 5 without inventing a regular-school class link.
    """
    session_value = normalize_islamiyah_session(academic_session); target = normalize_islamiyah_class(islamiyah_class); now = now_string(); incoming = []
    for student in students or []:
        admission = normalize_admission_number(student.get("admission_number") or student.get("Admission_number"))
        if not admission: continue
        incoming.append({
            "Session": session_value, "Admission_number": clean(student.get("admission_number") or student.get("Admission_number")), "Linked_admission_number": clean(student.get("regular_admission_number") or student.get("Regular_Admission_number")),
            "Last_name": clean(student.get("last_name") or student.get("Last_name")), "First_name": clean(student.get("first_name") or student.get("First_name")),
            "Other_names": clean(student.get("other_names") or student.get("Other_names")), "Full_name": clean(student.get("full_name")) or " ".join(part for part in [clean(student.get("last_name") or student.get("Last_name")), clean(student.get("first_name") or student.get("First_name")), clean(student.get("other_names") or student.get("Other_names"))] if part),
            "Sex": clean(student.get("sex") or student.get("Sex")), "Phone": clean(student.get("phone") or student.get("Phone")),
            "Regular_class": clean(student.get("regular_class") or student.get("Regular_Class")), "Regular_class_level": clean_upper(student.get("regular_class_category") or student.get("Regular_Class_category")),
            "Islamiyah_class": target, "Source": clean_upper(source) or "TAHFEEZ", "Active": "YES", "Imported_at": now, "Updated_at": now, "Updated_by": clean(updated_by) or "EMIS Staff",
        })
    if not incoming: raise ValueError("No valid students were supplied for Islamiyah transition.")
    with ISLAMIYAH_LOCK:
        rows = read_enrollments(); row_map = {_enrollment_key(row.get("Session"), row.get("Admission_number")): dict(row) for row in rows}
        for row in incoming:
            key = _enrollment_key(session_value, row.get("Admission_number")); previous = row_map.get(key, {})
            row["Imported_at"] = clean(previous.get("Imported_at")) or row["Imported_at"]
            if clean_upper(previous.get("Source")) == "REGULAR_DATABASE": row["Source"] = "REGULAR_DATABASE"
            row_map[key] = {**previous, **row}
        if rows: backup_islamiyah_file(ENROLLMENT_FILE, "tahfeez_transition")
        output = sorted(row_map.values(), key=lambda row: (normalize_academic_session(row.get("Session")), clean_upper(row.get("Islamiyah_class")) or "ZZZ", clean(row.get("Last_name")).lower(), clean(row.get("Admission_number")).lower())); write_enrollments(output)
    return {"session": session_value, "islamiyah_class": target, "islamiyah_class_label": islamiyah_class_label(target), "updated": len(incoming), "admission_numbers": [clean(row.get("Admission_number")) for row in incoming]}


def promote_islamiyah_students(academic_session, admission_numbers, source_class, destination_class="", updated_by=""):
    session_value = normalize_islamiyah_session(academic_session); source = normalize_islamiyah_class(source_class); destination = normalize_islamiyah_class(destination_class, allow_blank=True) or next_islamiyah_class(source)
    if not destination: raise ValueError(f"{islamiyah_class_label(source)} has no automatic destination configured. Choose the destination class manually.")
    if destination == source: raise ValueError("Destination Islamiyah class must be different from the source class.")
    admissions = {normalize_admission_number(value) for value in (admission_numbers or []) if normalize_admission_number(value)}
    if not admissions: raise ValueError("Select at least one student to promote.")
    eligible = {normalize_admission_number(row.get("admission_number")) for row in list_enrollments(session_value, source, active_only=True)}
    invalid = sorted(admissions - eligible)
    if invalid: raise ValueError(f"{len(invalid)} selected student(s) are not currently in {islamiyah_class_label(source)}.")
    result = assign_students(session_value, list(admissions), destination, updated_by)
    result.update({"source_class": source, "source_class_label": islamiyah_class_label(source), "destination_class": destination, "destination_class_label": islamiyah_class_label(destination), "promoted": len(admissions)})
    return result

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
    ca_value, exam_value = _validate_score(ca, CA_MAX, "CA"), _validate_score(exam, EXAM_MAX, "Exam"); academy_admission = normalize_admission_number(enrollment.get("admission_number")); target_key = "|".join([session_value, term_value, academy_admission, level, clean_upper(subject_row["key"])])
    with ISLAMIYAH_LOCK:
        rows = read_scores(); remaining = [row for row in rows if _score_key(row) != target_key]
        if ca_value is None and exam_value is None:
            if len(remaining) != len(rows): backup_islamiyah_file(SCORE_FILE, "score_clear"); write_scores(remaining)
            return {"deleted": True, "admission_number": enrollment.get("admission_number"), "regular_admission_number": enrollment.get("regular_admission_number"), "subject_key": subject_row["key"], "ca": None, "exam": None, "total": None, "complete": False}
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
    requested = normalize_admission_number(admission_number); session_filter = normalize_academic_session(academic_session) if academic_session else ""; academy_admission = requested
    if session_filter:
        enrollment = get_enrollment(requested, session_filter, active_only=False); academy_admission = normalize_admission_number(enrollment.get("admission_number")) if enrollment else requested; records = get_score_records(session_filter, admission_number=academy_admission)
    else:
        linked_ids = {normalize_admission_number(row.get("Admission_number")) for row in read_enrollments() if requested in {normalize_admission_number(row.get("Admission_number")), normalize_admission_number(row.get("Linked_admission_number"))}}
        linked_ids.add(requested); records = [record for record in map(score_to_record, read_scores()) if normalize_admission_number(record.get("admission_number")) in linked_ids]
    records.sort(key=lambda item: (item.get("session", ""), {"FIRST": 1, "SECOND": 2, "THIRD": 3}.get(item.get("term"), 9), item.get("islamiyah_class", ""), item.get("subject", ""))); grouped = {}
    for record in records:
        key = f"{record.get('session')}|{record.get('term')}|{record.get('islamiyah_class')}"; item = grouped.setdefault(key, {"session": record.get("session"), "term": record.get("term"), "islamiyah_class": record.get("islamiyah_class"), "islamiyah_class_label": record.get("islamiyah_class_label"), "subjects": [], "complete_subjects": 0, "average": None}); item["subjects"].append(record); item["complete_subjects"] += 1 if record.get("complete") else 0
    for item in grouped.values():
        totals = [float(row["total"]) for row in item["subjects"] if row.get("complete") and row.get("total") is not None]; item["average"] = round(sum(totals) / len(totals), 2) if totals and len(totals) == len(item["subjects"]) else None
    return list(grouped.values())

def get_report_islamiyah_row(admission_number, academic_session, term, ensure_seed=True):
    """Return one aggregated Islamiyyah /100 row for a regular-school report, or None before the session roster is activated.

    Each Islamiyah subject uses CA /30 + Exam /70. The regular report's single Islamiyyah row is the equal-weight average
    across all active subjects for the student's assigned Islamiyah class. Missing component subjects remain pending; they are never zero-filled.
    """
    session_value, term_value = normalize_academic_session(academic_session), normalize_academic_term(term); direct_regular = get_regular_school_islamiyah_row(admission_number, session_value, term_value)
    if direct_regular is not None: return direct_regular
    enrollment = get_enrollment(admission_number, session_value, active_only=False, ensure_seed=ensure_seed)
    if not enrollment: return None
    base = {"subject": "Islamiyyah", "subject_key": "ISLAMIYYAH", "mode": "ISLAMIYAH", "assessment_mode": "ISLAMIYAH", "source": "ISLAMIYYAH_SCHOOL", "academy_admission_number": enrollment.get("admission_number"), "regular_admission_number": enrollment.get("regular_admission_number"), "ca_max": CA_MAX, "exam_max": EXAM_MAX, "total_max": TOTAL_MAX, "islamiyah_class": enrollment.get("islamiyah_class"), "islamiyah_class_label": enrollment.get("islamiyah_class_label"), "position": 0, "position_text": "--", "out_of": 0, "lowest": None, "highest": None, "class_average": None}
    if not enrollment.get("active"): return {**base, "has_ca": False, "has_exam": False, "ca_complete": False, "exam_complete": False, "complete": False, "ca_total": None, "exam": None, "total": None, "grade": "-", "comment": "Islamiyah roster inactive", "islamiyah_status": "inactive", "islamiyah_subject_count": 0, "islamiyah_subjects_complete": 0, "islamiyah_components": []}
    level = clean_upper(enrollment.get("islamiyah_class"))
    if not level: return {**base, "has_ca": False, "has_exam": False, "ca_complete": False, "exam_complete": False, "complete": False, "ca_total": None, "exam": None, "total": None, "grade": "-", "comment": "Islamiyah class assignment pending", "islamiyah_status": "class_pending", "islamiyah_subject_count": 0, "islamiyah_subjects_complete": 0, "islamiyah_components": []}
    subjects = islamiyah_subject_rows(level); academy_admission = enrollment.get("admission_number"); saved = get_score_map(session_value, term_value, academy_admission).get(normalize_admission_number(academy_admission), {}); components = []
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
    completed = sum(1 for row in scores if row.get("complete")); coverage = get_islamiyah_roster_coverage(session_value); return {"session": session_value, "term": term_value, "roster_count": len(enrollments), "assigned_count": len(assigned), "unassigned_count": len(enrollments) - len(assigned), "score_records": len(scores), "complete_score_records": completed, "incomplete_score_records": len(scores) - completed, "linked_to_regular_count": coverage.get("linked_students", 0), "ambiguous_link_rows": coverage.get("ambiguous_link_rows", 0), "class_counts": class_counts, "roster_coverage": coverage, "classes": [{"key": level, "label": islamiyah_class_label(level), "students": class_counts.get(level, 0), "subjects": islamiyah_subject_rows(level)} for level in ISLAMIYAH_CLASS_LEVELS]}


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


# ============================================================
# REPORT-SHEET SYNC WORKSPACE — CLASS / STUDENT COMPLETION
# ============================================================
def get_report_sync_roster(academic_session, term, islamiyah_class="", regular_class="", search=""):
    session_value = normalize_islamiyah_session(academic_session); term_value = normalize_academic_term(term)
    if not term_value: raise ValueError("A valid FIRST, SECOND or THIRD term is required.")
    level = normalize_islamiyah_class(islamiyah_class, allow_blank=True); enrollments = list_enrollments(session_value, level, regular_class, active_only=True, search=search); score_map = get_score_map(session_value, term_value); students = []
    for enrollment in enrollments:
        academy = normalize_admission_number(enrollment.get("admission_number")); student_level = clean_upper(enrollment.get("islamiyah_class")); subjects = islamiyah_subject_rows(student_level) if student_level else []; saved = score_map.get(academy, {}); components = []
        for subject in subjects:
            record = saved.get(clean_upper(subject.get("key"))) or {}; components.append({"subject": subject.get("name"), "subject_key": subject.get("key"), "ca": record.get("ca"), "exam": record.get("exam"), "total": record.get("total"), "complete": bool(record.get("complete")), "saved_at": record.get("saved_at", ""), "saved_by": record.get("saved_by", "")})
        complete_rows = [row for row in components if row.get("complete") and row.get("total") is not None]; ca_values = [float(row["ca"]) for row in components if row.get("ca") is not None]; exam_values = [float(row["exam"]) for row in components if row.get("exam") is not None]; all_complete = bool(components) and len(complete_rows) == len(components); ca_complete = bool(components) and len(ca_values) == len(components); exam_complete = bool(components) and len(exam_values) == len(components); ca_average = round(sum(ca_values) / len(ca_values), 2) if ca_values else None; exam_average = round(sum(exam_values) / len(exam_values), 2) if exam_values else None; total = round(ca_average + exam_average, 2) if all_complete and ca_average is not None and exam_average is not None else None
        students.append({**enrollment, "term": term_value, "subject_count": len(components), "subjects_complete": len(complete_rows), "ca_complete": ca_complete, "exam_complete": exam_complete, "complete": all_complete, "ca_average": ca_average, "exam_average": exam_average, "total": total, "status": "complete" if all_complete else "partial" if (ca_values or exam_values) else "pending", "pending_subjects": [row.get("subject") for row in components if not row.get("complete")], "components": components})
    return {"session": session_value, "term": term_value, "islamiyah_class": level, "islamiyah_class_label": islamiyah_class_label(level) if level else "All Islamiyyah Classes", "students": students, "count": len(students), "complete_students": sum(1 for row in students if row.get("complete")), "partial_students": sum(1 for row in students if row.get("status") == "partial"), "pending_students": sum(1 for row in students if row.get("status") == "pending"), "linked_students": sum(1 for row in students if normalize_admission_number(row.get("regular_admission_number")).startswith("std"))}


def get_student_report_sync_sheet(academic_session, term, admission_number):
    session_value = normalize_islamiyah_session(academic_session); term_value = normalize_academic_term(term); enrollment = get_enrollment(admission_number, session_value, active_only=True)
    if not enrollment: raise ValueError("Student was not found in the active Islamiyyah roster.")
    level = normalize_islamiyah_class(enrollment.get("islamiyah_class"), allow_blank=True)
    if not level: raise ValueError("Assign the student to an Islamiyyah class before entering scores.")
    roster = get_report_sync_roster(session_value, term_value, level); academy = normalize_admission_number(enrollment.get("admission_number")); student = next((row for row in roster.get("students", []) if normalize_admission_number(row.get("admission_number")) == academy), None)
    if not student: raise ValueError("Student score sheet could not be prepared.")
    return {"session": session_value, "term": term_value, "student": student, "subjects": student.get("components", []), "ca_max": CA_MAX, "exam_max": EXAM_MAX, "total_max": TOTAL_MAX}
