# modules/promotion_manager.py

import csv
import shutil
from pathlib import Path
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, session, send_file

from modules.class_config import (
    SUPPORTED_CLASSES,
    CLASS_ARMS,
    normalize_class_level,
    normalize_class_arm,
    get_ss_stream,
)

promotion_bp = Blueprint("promotion_bp", __name__)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "static" / "data"
BACKUP_DIR = DATA_DIR / "backups"
LOG_FILE = DATA_DIR / "promotion_logs.csv"

CLASSES = SUPPORTED_CLASSES
DESTINATIONS = ["JSS1", "JSS2", "JSS3", "SS1", "SS2", "SS3", "GRADUATED", "LEFT"]

NEXT_CLASS = {
    "JSS1": "JSS2",
    "JSS2": "JSS3",
    "JSS3": "SS1",
    "SS1": "SS2",
    "SS2": "SS3",
    "SS3": "GRADUATED",
}

HEADERS = [
    "Admission_number",
    "Last_name",
    "First_name",
    "Other_names",
    "Phone",
    "Class",
    "Class_category",
    "Status",
]


def ensure_dirs():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def clean(value):
    return str(value or "").strip()


def norm(value):
    return clean(value).upper()


def normalize_csv_class(value, fallback_level=""):
    value = norm(value)
    fallback_level = normalize_class_level(fallback_level)

    if value in ["GRADUATED", "LEFT"]:
        return value

    return normalize_class_arm(value, fallback_level) or normalize_class_level(value) or value


def normalize_csv_level(value, fallback=""):
    value = norm(value)

    if value in ["GRADUATED", "LEFT"]:
        return value

    return normalize_class_level(value) or normalize_class_level(fallback) or value


def file_for_class(class_category):
    class_category = normalize_csv_level(class_category)

    if class_category == "GRADUATED":
        return DATA_DIR / "GRADUATED_Students.csv"

    if class_category == "LEFT":
        return DATA_DIR / "LEFT_Students.csv"

    return DATA_DIR / f"{class_category}_Students.csv"


def get_admin_name():
    return (
        session.get("admin_username")
        or session.get("username")
        or session.get("user")
        or "Admin"
    )


def admission_key(row):
    return clean(row.get("Admission_number")).lower()


def normalize_row(row, fallback_class=""):
    fallback_level = normalize_csv_level(fallback_class)

    normalized = {}

    for header in HEADERS:
        normalized[header] = clean(row.get(header))

    class_level = normalize_csv_level(
        normalized.get("Class_category")
        or normalized.get("Class")
        or fallback_level
    )

    class_arm = normalize_csv_class(
        normalized.get("Class")
        or normalized.get("Class_category")
        or class_level,
        class_level
    )

    if class_level in ["GRADUATED", "LEFT"]:
        class_arm = class_level

    normalized["Class_category"] = class_level
    normalized["Class"] = class_arm or class_level

    if not normalized["Status"]:
        normalized["Status"] = "ACTIVE"

    return normalized


def read_students(class_category):
    path = file_for_class(class_category)

    if not path.exists():
        return []

    rows = []

    with open(path, newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)

        for row in reader:
            rows.append(normalize_row(row, normalize_csv_level(class_category)))

    return rows


def write_students(class_category, rows):
    ensure_dirs()
    path = file_for_class(class_category)

    with open(path, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(rows)


def backup_class_file(class_category):
    ensure_dirs()
    path = file_for_class(class_category)

    if not path.exists():
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"{path.stem}_{timestamp}.csv"
    shutil.copy2(path, backup_path)

    return backup_path.name


def log_action(action, from_class, to_class, count, admissions, note=""):
    ensure_dirs()

    exists = LOG_FILE.exists()

    with open(LOG_FILE, "a", newline="", encoding="utf-8-sig") as file:
        headers = [
            "Timestamp",
            "Action",
            "From",
            "To",
            "Count",
            "Admissions",
            "Admin",
            "Note",
        ]

        writer = csv.DictWriter(file, fieldnames=headers)

        if not exists:
            writer.writeheader()

        writer.writerow({
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Action": action,
            "From": from_class,
            "To": to_class,
            "Count": count,
            "Admissions": ";".join(admissions),
            "Admin": get_admin_name(),
            "Note": note,
        })


def class_arm_suffix(old_class, old_category):
    old_class = normalize_csv_class(old_class, old_category)
    old_category = normalize_csv_level(old_category)

    if not old_class or not old_category:
        return ""

    if old_class == old_category:
        return ""

    if old_class.startswith(old_category):
        return old_class.replace(old_category, "", 1)

    return ""


def build_destination_class(old_class, old_category, destination_category, destination_arm=""):
    old_class = normalize_csv_class(old_class, old_category)
    old_category = normalize_csv_level(old_category)
    destination_category = normalize_csv_level(destination_category)
    destination_arm = norm(destination_arm)

    if destination_category in ["GRADUATED", "LEFT"]:
        return destination_category

    if destination_arm:
        normalized_arm = normalize_csv_class(destination_arm, destination_category)

        if normalized_arm.startswith(destination_category):
            return normalized_arm

        return normalize_csv_class(f"{destination_category}{destination_arm}", destination_category)

    suffix = class_arm_suffix(old_class, old_category)

    if suffix:
        return normalize_csv_class(f"{destination_category}{suffix}", destination_category)

    return destination_category


def get_class_summary():
    summary = {}

    for cls in CLASSES:
        rows = read_students(cls)
        active = [row for row in rows if norm(row.get("Status")) == "ACTIVE"]

        arms_count = {}

        for row in active:
            arm = normalize_csv_class(row.get("Class"), cls)
            if arm:
                arms_count[arm] = arms_count.get(arm, 0) + 1

        summary[cls] = {
            "total": len(rows),
            "active": len(active),
            "next": NEXT_CLASS.get(cls, ""),
            "arms": arms_count,
            "available_arms": CLASS_ARMS.get(cls, []),
        }

    summary["GRADUATED"] = {
        "total": len(read_students("GRADUATED")),
        "active": 0,
        "next": "",
        "arms": {},
        "available_arms": [],
    }

    summary["LEFT"] = {
        "total": len(read_students("LEFT")),
        "active": 0,
        "next": "",
        "arms": {},
        "available_arms": [],
    }

    return summary


def promote_or_move_students(from_class, to_class, admissions, mode="selected", destination_arm="", note=""):
    from_class = normalize_csv_level(from_class)
    to_class = normalize_csv_level(to_class)
    mode = clean(mode).lower()
    destination_arm = norm(destination_arm)

    if from_class not in CLASSES:
        return False, "Invalid source class.", None

    if to_class not in DESTINATIONS:
        return False, "Invalid destination class.", None

    source_rows = read_students(from_class)

    if not source_rows:
        return False, f"No students found in {from_class}.", None

    if mode == "all":
        selected_admissions = {
            admission_key(row)
            for row in source_rows
            if admission_key(row)
        }
    else:
        selected_admissions = {
            clean(adm).lower()
            for adm in admissions
            if clean(adm)
        }

    if not selected_admissions:
        return False, "No students selected.", None

    selected_rows = []
    remaining_rows = []

    for row in source_rows:
        if admission_key(row) in selected_admissions:
            selected_rows.append(row)
        else:
            remaining_rows.append(row)

    if not selected_rows:
        return False, "Selected students were not found.", None

    backup_from = backup_class_file(from_class)
    backup_to = backup_class_file(to_class)

    destination_rows = read_students(to_class)
    existing_destination = {admission_key(row) for row in destination_rows}

    moved_admissions = []

    for row in selected_rows:
        adm = admission_key(row)

        if adm in existing_destination:
            continue

        old_category = row.get("Class_category") or from_class
        old_class = row.get("Class") or from_class

        new_class = build_destination_class(
            old_class=old_class,
            old_category=old_category,
            destination_category=to_class,
            destination_arm=destination_arm,
        )

        row["Class_category"] = to_class
        row["Class"] = new_class

        if to_class == "GRADUATED":
            row["Status"] = "GRADUATED"
        elif to_class == "LEFT":
            row["Status"] = "LEFT"
        else:
            row["Status"] = "ACTIVE"

        destination_rows.append(row)
        moved_admissions.append(row.get("Admission_number"))

    if not moved_admissions:
        return False, "No student was moved. They may already exist in the destination file.", None

    write_students(from_class, remaining_rows)
    write_students(to_class, destination_rows)

    action = "PROMOTE" if to_class == NEXT_CLASS.get(from_class) else "MOVE"
    if to_class == "GRADUATED":
        action = "GRADUATE"
    if to_class == "LEFT":
        action = "MARK_LEFT"

    log_action(action, from_class, to_class, len(moved_admissions), moved_admissions, note)

    return True, f"{len(moved_admissions)} student(s) moved from {from_class} to {to_class}.", {
        "count": len(moved_admissions),
        "admissions": moved_admissions,
        "backup_from": backup_from,
        "backup_to": backup_to,
    }


def import_csv_to_class(target_class, uploaded_file, mode="append"):
    target_class = normalize_csv_level(target_class)
    mode = clean(mode).lower()

    if target_class not in CLASSES:
        return False, "Invalid target class.", None

    if not uploaded_file:
        return False, "No CSV file uploaded.", None

    ensure_dirs()

    try:
        decoded = uploaded_file.stream.read().decode("utf-8-sig").splitlines()
    except UnicodeDecodeError:
        uploaded_file.stream.seek(0)
        decoded = uploaded_file.stream.read().decode("latin-1").splitlines()

    reader = csv.DictReader(decoded)

    if not reader.fieldnames:
        return False, "Uploaded file has no valid CSV header.", None

    required = ["Admission_number", "Last_name", "First_name", "Class", "Class_category"]
    missing = [field for field in required if field not in reader.fieldnames]

    if missing:
        return False, f"Missing required columns: {', '.join(missing)}", None

    imported_rows = []

    for row in reader:
        clean_row = normalize_row(row, target_class)

        clean_row["Class_category"] = target_class
        clean_row["Class"] = normalize_csv_class(
            clean_row.get("Class") or target_class,
            target_class
        )

        if normalize_class_level(clean_row["Class"]) != target_class:
            clean_row["Class"] = target_class

        clean_row["Status"] = clean_row.get("Status") or "ACTIVE"

        if clean_row["Admission_number"]:
            imported_rows.append(clean_row)

    if not imported_rows:
        return False, "No valid student rows found in uploaded CSV.", None

    backup = backup_class_file(target_class)

    if mode == "replace":
        final_rows = imported_rows
    else:
        existing_rows = read_students(target_class)
        existing_keys = {admission_key(row) for row in existing_rows}

        added = []

        for row in imported_rows:
            if admission_key(row) not in existing_keys:
                existing_rows.append(row)
                existing_keys.add(admission_key(row))
                added.append(row)

        final_rows = existing_rows
        imported_rows = added

    write_students(target_class, final_rows)

    admissions = [row.get("Admission_number") for row in imported_rows]

    log_action(
        action="IMPORT_CSV",
        from_class="CSV_UPLOAD",
        to_class=target_class,
        count=len(imported_rows),
        admissions=admissions,
        note=f"Import mode: {mode}",
    )

    return True, f"{len(imported_rows)} student(s) imported into {target_class}.", {
        "count": len(imported_rows),
        "backup": backup,
    }


def read_logs(limit=30):
    if not LOG_FILE.exists():
        return []

    with open(LOG_FILE, newline="", encoding="utf-8-sig") as file:
        rows = list(csv.DictReader(file))

    return rows[-limit:][::-1]


@promotion_bp.route("/admin/promotion")
def promotion_page():
    return render_template(
        "promotion.html",
        classes=CLASSES,
        destinations=DESTINATIONS,
        class_arms=CLASS_ARMS,
    )


@promotion_bp.route("/api/promotion/summary")
def api_promotion_summary():
    return jsonify({
        "success": True,
        "summary": get_class_summary(),
    })


@promotion_bp.route("/api/promotion/students")
def api_promotion_students():
    class_category = request.args.get("class", "JSS1")
    rows = read_students(class_category)

    for row in rows:
        class_level = normalize_csv_level(row.get("Class_category"))
        class_arm = normalize_csv_class(row.get("Class"), class_level)

        row["Class_category"] = class_level
        row["Class"] = class_arm
        row["Class_level"] = class_level
        row["Class_arm"] = class_arm
        row["Stream"] = get_ss_stream(class_arm)

    return jsonify({
        "success": True,
        "class": normalize_csv_level(class_category),
        "students": rows,
        "count": len(rows),
    })


@promotion_bp.route("/api/promotion/logs")
def api_promotion_logs():
    return jsonify({
        "success": True,
        "logs": read_logs(),
    })


@promotion_bp.route("/api/promotion/promote", methods=["POST"])
def api_promote_students():
    data = request.get_json(silent=True) or {}

    from_class = data.get("from_class")
    to_class = data.get("to_class")
    admissions = data.get("admissions") or []
    mode = data.get("mode", "selected")
    destination_arm = data.get("destination_arm", "")
    note = data.get("note", "")

    success, message, payload = promote_or_move_students(
        from_class=from_class,
        to_class=to_class,
        admissions=admissions,
        mode=mode,
        destination_arm=destination_arm,
        note=note,
    )

    status = 200 if success else 400

    return jsonify({
        "success": success,
        "message": message,
        "data": payload,
    }), status


@promotion_bp.route("/api/promotion/import", methods=["POST"])
def api_import_students():
    target_class = request.form.get("target_class")
    mode = request.form.get("mode", "append")
    uploaded_file = request.files.get("csv_file")

    success, message, payload = import_csv_to_class(target_class, uploaded_file, mode)

    status = 200 if success else 400

    return jsonify({
        "success": success,
        "message": message,
        "data": payload,
    }), status


@promotion_bp.route("/api/promotion/backup", methods=["POST"])
def api_backup_class():
    data = request.get_json(silent=True) or {}
    class_category = normalize_csv_level(data.get("class_category") or "JSS1")

    backup = backup_class_file(class_category)

    if not backup:
        return jsonify({
            "success": False,
            "message": f"No CSV file found for {class_category}.",
        }), 404

    log_action(
        action="BACKUP",
        from_class=class_category,
        to_class=class_category,
        count=0,
        admissions=[],
        note=f"Backup created: {backup}",
    )

    return jsonify({
        "success": True,
        "message": f"Backup created for {class_category}.",
        "backup": backup,
    })


@promotion_bp.route("/api/promotion/export")
def api_export_class():
    class_category = normalize_csv_level(request.args.get("class") or "JSS1")
    path = file_for_class(class_category)

    if not path.exists():
        return jsonify({
            "success": False,
            "message": f"No CSV file found for {class_category}.",
        }), 404

    return send_file(
        path,
        as_attachment=True,
        download_name=path.name,
        mimetype="text/csv",
    )


@promotion_bp.route("/api/promotion/delete", methods=["POST"])
def api_delete_students():
    data = request.get_json(silent=True) or {}

    class_category = normalize_csv_level(data.get("class_category") or "JSS1")
    admissions = {
        clean(adm).lower()
        for adm in data.get("admissions", [])
        if clean(adm)
    }

    if not admissions:
        return jsonify({
            "success": False,
            "message": "No students selected.",
        }), 400

    rows = read_students(class_category)

    if not rows:
        return jsonify({
            "success": False,
            "message": f"No students found in {class_category}.",
        }), 404

    backup = backup_class_file(class_category)

    kept = []
    deleted = []

    for row in rows:
        if admission_key(row) in admissions:
            deleted.append(row)
        else:
            kept.append(row)

    if not deleted:
        return jsonify({
            "success": False,
            "message": "Selected students were not found.",
        }), 404

    write_students(class_category, kept)

    deleted_admissions = [row.get("Admission_number") for row in deleted]

    log_action(
        action="DELETE",
        from_class=class_category,
        to_class="REMOVED",
        count=len(deleted),
        admissions=deleted_admissions,
        note=f"Backup: {backup}",
    )

    return jsonify({
        "success": True,
        "message": f"{len(deleted)} student(s) deleted from {class_category}.",
        "backup": backup,
    })


@promotion_bp.route("/api/promotion/student/save", methods=["POST"])
def api_save_student():
    data = request.get_json(silent=True) or {}

    student = data.get("student") or {}
    original_admission = clean(data.get("original_admission")).lower()

    class_category = normalize_csv_level(student.get("Class_category") or "JSS1")

    if class_category not in CLASSES:
        return jsonify({
            "success": False,
            "message": "Invalid class category.",
        }), 400

    new_admission = clean(student.get("Admission_number"))

    if not new_admission:
        return jsonify({
            "success": False,
            "message": "Admission number is required.",
        }), 400

    clean_student = normalize_row(student, class_category)
    clean_student["Class_category"] = class_category
    clean_student["Class"] = normalize_csv_class(
        clean_student.get("Class") or class_category,
        class_category
    )

    if normalize_class_level(clean_student["Class"]) != class_category:
        clean_student["Class"] = class_category

    backup = backup_class_file(class_category)

    rows = read_students(class_category)
    existing_index = None

    for index, row in enumerate(rows):
        row_adm = admission_key(row)

        if original_admission and row_adm == original_admission:
            existing_index = index
            break

        if not original_admission and row_adm == new_admission.lower():
            return jsonify({
                "success": False,
                "message": "A student with this admission number already exists.",
            }), 400

    if existing_index is None:
        rows.append(clean_student)
        action = "ADD_STUDENT"
        message = f"Student {new_admission} added to {class_category}."
    else:
        rows[existing_index] = clean_student
        action = "EDIT_STUDENT"
        message = f"Student {new_admission} updated."

    write_students(class_category, rows)

    log_action(
        action=action,
        from_class=class_category,
        to_class=class_category,
        count=1,
        admissions=[new_admission],
        note=f"Backup: {backup}",
    )

    return jsonify({
        "success": True,
        "message": message,
        "student": clean_student,
        "backup": backup,
    })