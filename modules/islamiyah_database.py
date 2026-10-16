# MODULE: Combined Tahfeez and Islamiyyah student register; session scores remain in their existing files.
import csv
import shutil
from datetime import datetime
from pathlib import Path
from threading import RLock
from modules.school_structure import islamiyah_base_level

BASE_DIR = Path(__file__).resolve().parent.parent
COMBINED_CSV = BASE_DIR / "static/data/database/tahfeez2026.csv"
REGISTER_LOCK = RLock()
REGISTER_HEADERS = ["Admission_number", "Regular_Admission_number", "Last_name", "First_name", "Other_names", "Phone", "Sex", "Regular_Class", "Regular_Class_category", "Tahfeez_Class", "Tahfeez_Class_category", "Islamiyah_Class", "Islamiyah_Class_category", "Islamiyah_Source", "Source_note"]

# Shared storage and scoped writes prevent one school's update from removing the other school's rows.
def read_register():
    with REGISTER_LOCK:
        if not COMBINED_CSV.exists(): return []
        with COMBINED_CSV.open("r", encoding="utf-8-sig", newline="") as file: return list(csv.DictReader(file))

def write_register(rows, reason="register_update"):
    with REGISTER_LOCK:
        rows = list(rows); seen = set()
        for row in rows:
            admission = str(row.get("Admission_number") or "").strip().lower()
            if not admission or admission in seen: raise ValueError("Combined register requires unique, nonblank admission numbers.")
            seen.add(admission)
        COMBINED_CSV.parent.mkdir(parents=True, exist_ok=True); backup = ""
        if COMBINED_CSV.exists():
            folder = COMBINED_CSV.parent / "backups/combined_islamiyah_database"; folder.mkdir(parents=True, exist_ok=True)
            safe = "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in reason)
            target = folder / f"register_{safe}_{datetime.now():%Y%m%d_%H%M%S_%f}.csv"; shutil.copy2(COMBINED_CSV, target); backup = str(target)
        temp = COMBINED_CSV.with_suffix(".tmp")
        with temp.open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=REGISTER_HEADERS, extrasaction="ignore"); writer.writeheader(); writer.writerows(rows)
        temp.replace(COMBINED_CSV); return backup

def replace_tahfeez_rows(rows, reason="tahfeez_update"):
    with REGISTER_LOCK:
        incoming = {str(row["Admission_number"]).strip().lower(): dict(row) for row in rows}; output = []
        for old in read_register():
            admission = str(old.get("Admission_number") or "").strip().lower()
            if admission in incoming: output.append({**old, **incoming.pop(admission)})
            elif old.get("Tahfeez_Class") or old.get("Tahfeez_Class_category"):
                if old.get("Islamiyah_Source") or old.get("Islamiyah_Class"):
                    output.append({**old, "Tahfeez_Class": "", "Tahfeez_Class_category": ""})
            else: output.append(old)
        output.extend(incoming.values()); return write_register(output, reason)

def sync_current_islamiyah_profiles(enrollments, academic_session):
    """Persist only the configured current session; editing history cannot change today's register."""
    with REGISTER_LOCK:
        rows = read_register(); by_id = {str(row["Admission_number"]).strip().lower(): row for row in rows}; changed = False
        for enrollment in enrollments:
            if enrollment.get("Session") != academic_session: continue
            admission = str(enrollment.get("Admission_number") or "").strip().lower(); previous = by_id.get(admission, {})
            if not previous and not enrollment.get("Islamiyah_class"): continue
            record = {**previous, **{field: enrollment.get(field, "") for field in ["Admission_number", "Last_name", "First_name", "Other_names", "Phone", "Sex"]}, "Regular_Admission_number": enrollment.get("Linked_admission_number", "") or (enrollment.get("Admission_number", "") if str(enrollment.get("Admission_number", "")).lower().startswith("std") else ""), "Regular_Class": enrollment.get("Regular_class", ""), "Regular_Class_category": enrollment.get("Regular_class_level", ""), "Islamiyah_Class": enrollment.get("Islamiyah_class", "") if enrollment.get("Active", "YES") == "YES" else "", "Islamiyah_Class_category": islamiyah_base_level(enrollment.get("Islamiyah_class", "")) if enrollment.get("Active", "YES") == "YES" else "", "Islamiyah_Source": enrollment.get("Source") or "ISLAMIYYAH_DATABASE"}
            if record != previous: by_id[admission] = record; changed = True
        if changed: write_register(list(by_id.values()), "islamiyah_placement")
