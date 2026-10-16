# MODULE: Tahfeez Database — independent Tahfeez roster with optional links to students2026.csv by Admission_number

import csv
import shutil
from pathlib import Path
from datetime import datetime
from threading import RLock

from modules.class_config import TAHFEEZ_CSV_FILE
from modules.islamiyah_database import REGISTER_LOCK, REGISTER_HEADERS, read_register, replace_tahfeez_rows
from modules.school_structure import TAHFEEZ_CLASS_LEVELS, class_label, normalize_school_class
from modules.student_database.student_database import find_student, read_master_students, normalize_admission, full_name as master_full_name
from modules.academy_identity import master_identity_indexes, resolve_master_identity

BASE_DIR = Path(__file__).resolve().parent.parent
TAHFEEZ_CSV = BASE_DIR / TAHFEEZ_CSV_FILE
BACKUP_DIR = TAHFEEZ_CSV.parent / "backups" / "tahfeez_database"
TAHFEEZ_LOCK = REGISTER_LOCK

TAHFEEZ_HEADERS = ["Admission_number", "Regular_Admission_number", "Last_name", "First_name", "Other_names", "Phone", "Sex", "Regular_Class", "Regular_Class_category", "Tahfeez_Class", "Tahfeez_Class_category"]


def clean(value): return str(value or "").strip()

def normalize_sex(value):
    raw = clean(value).upper()
    if raw in {"M", "MALE"}: return "Male"
    if raw in {"F", "FEMALE"}: return "Female"
    return clean(value)


def normalize_tahfeez_class(value):
    level = normalize_school_class(value)
    return level if level in TAHFEEZ_CLASS_LEVELS else ""


def ensure_tahfeez_storage():
    TAHFEEZ_CSV.parent.mkdir(parents=True, exist_ok=True); BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    if not TAHFEEZ_CSV.exists():
        with TAHFEEZ_CSV.open("w", newline="", encoding="utf-8-sig") as file: csv.DictWriter(file, fieldnames=REGISTER_HEADERS).writeheader()
    return TAHFEEZ_CSV


def backup_tahfeez_database(reason="update"):
    ensure_tahfeez_storage()
    if not TAHFEEZ_CSV.exists(): return ""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f"); safe = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in clean(reason) or "update")
    target = BACKUP_DIR / f"tahfeez2026_{safe}_{stamp}.csv"; shutil.copy2(TAHFEEZ_CSV, target); return str(target)


def _master_identity(admission_number):
    student = find_student(admission_number)
    if not student: return None
    return {
        "Admission_number": clean(student.get("Admission_number")), "Last_name": clean(student.get("Last_name")), "First_name": clean(student.get("First_name")), "Other_names": clean(student.get("Other_names")),
        "Phone": clean(student.get("Phone")), "Sex": normalize_sex(student.get("Sex")), "Regular_Class": clean(student.get("Class")), "Regular_Class_category": clean(student.get("Class_category")),
    }


def normalize_tahfeez_record(row, require_master=False):
    row = row or {}; admission = normalize_admission(row.get("Admission_number")); level = normalize_tahfeez_class(row.get("Tahfeez_Class_category") or row.get("Tahfeez_Class"))
    if not admission: raise ValueError("Tahfeez admission number is required.")
    if not level: raise ValueError(f"Invalid Tahfeez class for {admission}.")

    indexes = master_identity_indexes(); master = resolve_master_identity(row.get("Admission_number"), row.get("Last_name"), row.get("First_name"), row.get("Other_names"), linked_admission_number=row.get("Regular_Admission_number"), indexes=indexes)
    if require_master and not master: raise ValueError(f"Tahfeez student {admission} was not found in students2026.csv.")
    identity = {
        "Admission_number": clean(row.get("Admission_number")), "Regular_Admission_number": clean(master.get("admission_number")) if master else clean(row.get("Regular_Admission_number")),
        "Last_name": clean(row.get("Last_name")) or clean(master.get("last_name") if master else ""), "First_name": clean(row.get("First_name")) or clean(master.get("first_name") if master else ""), "Other_names": clean(row.get("Other_names")) or clean(master.get("other_names") if master else ""),
        "Phone": clean(row.get("Phone")) or clean(master.get("phone") if master else ""), "Sex": normalize_sex(row.get("Sex") or (master.get("sex") if master else "")),
        "Regular_Class": clean(master.get("class_arm") if master else row.get("Regular_Class")), "Regular_Class_category": clean(master.get("class_level") if master else row.get("Regular_Class_category")),
    }
    if not clean(identity.get("Last_name")): raise ValueError(f"Tahfeez student {admission} requires a name when no regular-school link exists.")
    return {**identity, "Tahfeez_Class": level, "Tahfeez_Class_category": level}


def read_tahfeez_rows(raw=False):
    ensure_tahfeez_storage()
    with TAHFEEZ_LOCK:
        rows = [row for row in read_register() if clean(row.get("Tahfeez_Class") or row.get("Tahfeez_Class_category"))]
    if raw: return rows
    output = []
    for row in rows:
        if not normalize_admission(row.get("Admission_number")): continue
        try: output.append(normalize_tahfeez_record(row, require_master=False))
        except ValueError: output.append({header: clean(row.get(header)) for header in TAHFEEZ_HEADERS})
    return output


def validate_tahfeez_rows(rows, require_master=False):
    normalized, seen = [], set()
    for row in rows or []:
        record = normalize_tahfeez_record(row, require_master=require_master); admission = normalize_admission(record.get("Admission_number"))
        if admission in seen: raise ValueError(f"Duplicate Tahfeez placement for {admission}.")
        seen.add(admission); normalized.append(record)
    normalized.sort(key=lambda row: (TAHFEEZ_CLASS_LEVELS.index(row["Tahfeez_Class_category"]), normalize_admission(row["Admission_number"])))
    return normalized


def write_tahfeez_rows(rows, reason="tahfeez_update", require_master=False, queue_sync=True):
    normalized = validate_tahfeez_rows(rows, require_master=require_master); ensure_tahfeez_storage(); backup = ""
    with TAHFEEZ_LOCK:
        backup = replace_tahfeez_rows(normalized, reason=reason)
    result = {"success": True, "count": len(normalized), "backup": backup}
    if queue_sync: result["sync"] = queue_tahfeez_snapshot_safely()
    return result


def placement_to_student(record):
    if not isinstance(record, dict): return {}
    admission = clean(record.get("Admission_number")); indexes = master_identity_indexes(); master = resolve_master_identity(admission, record.get("Last_name"), record.get("First_name"), record.get("Other_names"), linked_admission_number=record.get("Regular_Admission_number"), indexes=indexes) or {}; level = normalize_tahfeez_class(record.get("Tahfeez_Class_category") or record.get("Tahfeez_Class")); regular_admission = clean(master.get("admission_number") or record.get("Regular_Admission_number"))
    return {
        "admission_number": admission, "academy_admission_number": admission, "regular_admission_number": regular_admission, "id": admission, "last_name": clean(record.get("Last_name") or master.get("last_name")), "first_name": clean(record.get("First_name") or master.get("first_name")),
        "other_names": clean(record.get("Other_names") or master.get("other_names")), "full_name": " ".join(part for part in [clean(record.get("Last_name") or master.get("last_name")), clean(record.get("First_name") or master.get("first_name")), clean(record.get("Other_names") or master.get("other_names"))] if part),
        "phone": clean(record.get("Phone") or master.get("phone")), "sex": normalize_sex(record.get("Sex") or master.get("sex")),
        "regular_class": clean(master.get("class_arm") or record.get("Regular_Class")), "regular_class_category": clean(master.get("class_level") or record.get("Regular_Class_category")),
        "tahfeez_class": level, "tahfeez_class_category": level, "class": level, "class_arm": level, "class_level": level, "class_category": level,
        "tahfeez_class_label": class_label(level), "roster_source": "tahfeez2026.csv", "is_linked_to_master": bool(regular_admission), "is_active": bool(level and (clean(record.get("Last_name")) or master)),
    }


def get_all_tahfeez_students(active_only=True):
    rows = [placement_to_student(row) for row in read_tahfeez_rows()]; rows = [row for row in rows if row.get("admission_number") and (row.get("is_active") or not active_only)]
    rows.sort(key=lambda row: (TAHFEEZ_CLASS_LEVELS.index(row.get("tahfeez_class")) if row.get("tahfeez_class") in TAHFEEZ_CLASS_LEVELS else 99, clean(row.get("last_name")).lower(), clean(row.get("first_name")).lower(), normalize_admission(row.get("admission_number"))))
    return rows


def get_tahfeez_students_by_class(tahfeez_class, active_only=True):
    level = normalize_tahfeez_class(tahfeez_class)
    if not level: return []
    return [student for student in get_all_tahfeez_students(active_only=active_only) if student.get("tahfeez_class") == level]


def find_tahfeez_placement(admission_number, active_only=True):
    admission = normalize_admission(admission_number)
    if not admission: return None
    matches = [student for student in get_all_tahfeez_students(active_only=active_only) if normalize_admission(student.get("admission_number")) == admission]
    return matches[0] if len(matches) == 1 else None


def set_tahfeez_placement(admission_number, tahfeez_class, reason="placement_update"):
    admission = normalize_admission(admission_number); level = normalize_tahfeez_class(tahfeez_class)
    if not admission: raise ValueError("Admission number is required.")
    if not level: raise ValueError("A valid Tahfeez class is required.")
    rows = read_tahfeez_rows(raw=True); updated = False
    existing = next((row for row in rows if normalize_admission(row.get("Admission_number")) == admission), None)
    if not existing and not _master_identity(admission): raise ValueError(f"Student {admission} was not found in the Tahfeez roster or students2026.csv.")
    for row in rows:
        if normalize_admission(row.get("Admission_number")) == admission: row["Tahfeez_Class"] = level; row["Tahfeez_Class_category"] = level; updated = True; break
    if not updated: rows.append({"Admission_number": admission, "Tahfeez_Class": level, "Tahfeez_Class_category": level})
    result = write_tahfeez_rows(rows, reason=reason); result["student"] = find_tahfeez_placement(admission, active_only=False); return result


def remove_tahfeez_placement(admission_number, reason="placement_remove"):
    admission = normalize_admission(admission_number)
    if not admission: raise ValueError("Admission number is required.")
    rows = read_tahfeez_rows(raw=True); kept = [row for row in rows if normalize_admission(row.get("Admission_number")) != admission]
    if len(kept) == len(rows): raise ValueError("Tahfeez placement was not found.")
    return write_tahfeez_rows(kept, reason=reason)



def get_tahfeez_management_roster():
    """Return the actual Tahfeez roster; standalone real records are not hidden by the regular master."""
    roster = []
    for student in get_all_tahfeez_students(active_only=False):
        row = dict(student)
        row["has_tahfeez"] = bool(row.get("tahfeez_class"))
        roster.append(row)
    roster.sort(key=lambda row: (TAHFEEZ_CLASS_LEVELS.index(row.get("tahfeez_class")) if row.get("tahfeez_class") in TAHFEEZ_CLASS_LEVELS else 99, clean(row.get("last_name")).lower(), clean(row.get("first_name")).lower(), normalize_admission(row.get("admission_number"))))
    return roster


def set_tahfeez_placements(admission_numbers, tahfeez_class, reason="bulk_placement_update"):
    level = normalize_tahfeez_class(tahfeez_class); admissions = []
    for value in admission_numbers or []:
        admission = normalize_admission(value)
        if admission and admission not in admissions: admissions.append(admission)
    if not admissions: raise ValueError("Select at least one student for Tahfeez placement.")
    if not level: raise ValueError("A valid Tahfeez class is required.")
    rows = read_tahfeez_rows(raw=True); row_map = {normalize_admission(row.get("Admission_number")): dict(row) for row in rows if normalize_admission(row.get("Admission_number"))}
    missing = [admission for admission in admissions if admission not in row_map and not _master_identity(admission)]
    if missing: raise ValueError(f"Student(s) not found in the Tahfeez roster or students2026.csv: {', '.join(missing)}")
    for admission in admissions:
        row = row_map.get(admission) or {"Admission_number": admission}; row["Tahfeez_Class"] = level; row["Tahfeez_Class_category"] = level; row_map[admission] = row
    result = write_tahfeez_rows(list(row_map.values()), reason=reason); result.update({"updated": admissions, "tahfeez_class": level, "students": [find_tahfeez_placement(admission, active_only=False) for admission in admissions]}); return result


def remove_tahfeez_placements(admission_numbers, reason="bulk_placement_remove", ignore_missing=True):
    admissions = []
    for value in admission_numbers or []:
        admission = normalize_admission(value)
        if admission and admission not in admissions: admissions.append(admission)
    if not admissions: raise ValueError("Select at least one student to remove from Tahfeez.")
    wanted = set(admissions); rows = read_tahfeez_rows(raw=True); removed = [normalize_admission(row.get("Admission_number")) for row in rows if normalize_admission(row.get("Admission_number")) in wanted]
    if not removed and not ignore_missing: raise ValueError("No selected Tahfeez placement was found.")
    kept = [row for row in rows if normalize_admission(row.get("Admission_number")) not in wanted]
    if len(kept) == len(rows): return {"success": True, "count": 0, "removed": [], "backup": ""}
    result = write_tahfeez_rows(kept, reason=reason); result.update({"count": len(removed), "removed": removed}); return result



def _next_tahfeez_admission():
    used = {normalize_admission(row.get("Admission_number")) for row in read_register()}; highest = 0
    for admission in used:
        if admission.startswith("thf") and admission[3:].isdigit(): highest = max(highest, int(admission[3:]))
    candidate = f"thf{highest + 1:03d}"
    while normalize_admission(candidate) in used: candidate = f"thf{int(candidate[3:]) + 1:03d}"
    return candidate


def register_regular_students_to_tahfeez(admission_numbers, tahfeez_class, updated_by=""):
    """Link regular-school pupils into Tahfeez without changing students2026.csv."""
    level = normalize_tahfeez_class(tahfeez_class); admissions = []
    for value in admission_numbers or []:
        admission = normalize_admission(value)
        if admission and admission not in admissions: admissions.append(admission)
    if not admissions: raise ValueError("Select at least one regular-school student.")
    if not level: raise ValueError("Choose a valid Tahfeez class.")
    master_rows = read_master_students(); master = {normalize_admission(row.get("Admission_number")): row for row in master_rows}; missing = [value for value in admissions if value not in master]
    if missing: raise ValueError(f"{len(missing)} selected student(s) were not found in the active regular-school database.")
    rows = read_tahfeez_rows(raw=True); by_regular = {}
    for index,row in enumerate(rows):
        regular = normalize_admission(row.get("Regular_Admission_number"))
        if regular: by_regular.setdefault(regular, []).append(index)
    created, updated, ids = 0, 0, []
    for regular in admissions:
        student = master[regular]; matches = by_regular.get(regular, [])
        if len(matches) > 1: raise ValueError(f"{regular} has multiple Tahfeez links. Resolve the duplicate before registering it again.")
        values = {"Regular_Admission_number": clean(student.get("Admission_number")), "Last_name": clean(student.get("Last_name")), "First_name": clean(student.get("First_name")), "Other_names": clean(student.get("Other_names")), "Phone": clean(student.get("Phone")), "Sex": normalize_sex(student.get("Sex")), "Regular_Class": clean(student.get("Class")), "Regular_Class_category": clean(student.get("Class_category")), "Tahfeez_Class": level, "Tahfeez_Class_category": level}
        if matches:
            rows[matches[0]].update(values); ids.append(clean(rows[matches[0]].get("Admission_number"))); updated += 1
        else:
            academy_id = _next_tahfeez_admission(); used = {normalize_admission(row.get("Admission_number")) for row in rows}
            while normalize_admission(academy_id) in used: academy_id = f"thf{int(academy_id[3:]) + 1:03d}"
            rows.append({"Admission_number": academy_id, **values}); ids.append(academy_id); created += 1
    result = write_tahfeez_rows(rows, reason="register_regular_students"); result.update({"created": created, "updated": updated, "admission_numbers": ids, "tahfeez_class": level, "tahfeez_class_label": class_label(level)})
    return result


def add_tahfeez_student(payload, updated_by=""):
    level = normalize_tahfeez_class(payload.get("tahfeez_class")); linked = normalize_admission(payload.get("regular_admission_number"))
    if linked: return register_regular_students_to_tahfeez([linked], level, updated_by)
    last_name, first_name, other_names = clean(payload.get("last_name")), clean(payload.get("first_name")), clean(payload.get("other_names"))
    if not last_name or not first_name: raise ValueError("Last name and first name are required for an independent Tahfeez student.")
    admission = normalize_admission(payload.get("admission_number")) or _next_tahfeez_admission(); rows = read_tahfeez_rows(raw=True)
    if any(normalize_admission(row.get("Admission_number")) == admission for row in rows): raise ValueError(f"Tahfeez admission {admission} already exists.")
    rows.append({"Admission_number": admission, "Regular_Admission_number": "", "Last_name": last_name, "First_name": first_name, "Other_names": other_names, "Phone": clean(payload.get("phone")), "Sex": normalize_sex(payload.get("sex")), "Regular_Class": "", "Regular_Class_category": "", "Tahfeez_Class": level, "Tahfeez_Class_category": level}); result = write_tahfeez_rows(rows, reason="add_tahfeez_student"); result["student"] = find_tahfeez_placement(admission, active_only=False); return result


def update_tahfeez_student(admission_number, payload, updated_by=""):
    admission = normalize_admission(admission_number); rows = read_tahfeez_rows(raw=True); matched = None
    for row in rows:
        if normalize_admission(row.get("Admission_number")) != admission: continue
        matched = row
        for field,key in [("Last_name","last_name"),("First_name","first_name"),("Other_names","other_names"),("Phone","phone"),("Sex","sex")]:
            if key in payload: row[field] = normalize_sex(payload.get(key)) if field == "Sex" else clean(payload.get(key))
        if payload.get("tahfeez_class"): row["Tahfeez_Class"] = row["Tahfeez_Class_category"] = normalize_tahfeez_class(payload.get("tahfeez_class"))
        break
    if not matched: raise ValueError("Tahfeez student record was not found.")
    result = write_tahfeez_rows(rows, reason="edit_tahfeez_student"); result["student"] = find_tahfeez_placement(admission, active_only=False); return result

def sync_tahfeez_identities(reason="identity_sync"):
    rows = read_tahfeez_rows(raw=True)
    if not rows: return {"success": True, "count": 0, "standalone_preserved": 0, "backup": ""}
    refreshed, standalone = [], 0
    for row in rows:
        master = _master_identity(row.get("Admission_number"))
        if master:
            refreshed.append({**row, **master})
        else:
            refreshed.append(row); standalone += 1
    result = write_tahfeez_rows(refreshed, reason=reason, require_master=False)
    result["standalone_preserved"] = standalone
    return result

def get_tahfeez_summary():
    students = get_all_tahfeez_students(active_only=False)
    active = [row for row in students if row.get("is_active")]
    linked = [row for row in active if row.get("is_linked_to_master")]
    standalone = [row for row in active if not row.get("is_linked_to_master")]
    return {
        "total": len(students), "active_links": len(active), "linked_to_master": len(linked), "standalone_records": len(standalone), "missing_master_links": 0,
        "classes": {level: {"label": class_label(level), "total": sum(1 for row in active if row.get("tahfeez_class") == level)} for level in TAHFEEZ_CLASS_LEVELS},
    }


def tahfeez_database_health_check():
    ensure_tahfeez_storage(); raw_rows = read_tahfeez_rows(raw=True); seen, duplicates, invalid, stale_identity = set(), [], [], []
    for index, row in enumerate(raw_rows, start=2):
        admission = normalize_admission(row.get("Admission_number"))
        if admission in seen: duplicates.append(admission)
        elif admission: seen.add(admission)
        try: normalized = normalize_tahfeez_record(row, require_master=False)
        except Exception as error:
            invalid.append({"line": index, "admission_number": admission, "error": str(error)}); continue
        master = _master_identity(admission)
        if master:
            for field in ["Last_name", "First_name", "Other_names", "Phone", "Sex", "Regular_Class", "Regular_Class_category"]:
                if clean(row.get(field)) != clean(normalized.get(field)):
                    stale_identity.append({"admission_number": admission, "field": field, "stored": clean(row.get(field)), "master": clean(normalized.get(field))})
    return {
        "healthy": not duplicates and not invalid, "file_exists": TAHFEEZ_CSV.exists(), "path": str(TAHFEEZ_CSV), "total": len(raw_rows), "duplicate_admissions": sorted(set(duplicates)),
        "invalid_records": invalid, "missing_master_links": [], "stale_identity_fields": stale_identity, "summary": get_tahfeez_summary(),
    }


# ============================================================
# LOCAL -> DEPLOYED TAHFEEZ PLACEMENT SYNC
#
# Tahfeez is a parallel classification, so every successful local
# placement mutation queues one complete placement snapshot. A single
# stable entity key plus the sync engine's revision protection means the
# newest successful snapshot wins and stale retries cannot overwrite it.
# ============================================================

def build_tahfeez_sync_payload():
    rows = validate_tahfeez_rows(read_tahfeez_rows(raw=True), require_master=False)
    return {
        "rows": rows,
        "count": len(rows),
        "source": "tahfeez2026.csv",
        "updated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }


def queue_tahfeez_snapshot_safely():
    try:
        from modules.result_sync import queue_emis_event_safely
        return queue_emis_event_safely("tahfeez", "replace_all", build_tahfeez_sync_payload(), entity_key="tahfeez:placements")
    except Exception as error:
        print("[TAHFEEZ SYNC] Could not queue placement snapshot:", error)
        return {"queued": False, "status": "QUEUE_ERROR", "error": str(error)}


def apply_tahfeez_sync_event(action, payload, event=None):
    if clean(action).lower() not in {"replace_all", "replace_snapshot"}:
        raise ValueError(f"Unsupported Tahfeez sync action: {action}")
    if not isinstance(payload, dict):
        raise ValueError("Tahfeez sync payload must be an object.")
    rows = payload.get("rows") or []
    if not isinstance(rows, list):
        raise ValueError("Tahfeez synchronized rows must be a list.")
    result = write_tahfeez_rows(rows, reason="sync_replace_all", require_master=False, queue_sync=False)
    return {
        "count": int(result.get("count") or 0),
        "source": clean(payload.get("source")) or "tahfeez2026.csv",
        "updated_at": clean(payload.get("updated_at")),
        "remote_server": clean((event or {}).get("server_id")),
    }
