# MODULE: Promotion Manager — Flask routes and orchestration for student promotion, repetition, graduation and database administration

import csv
import io
from pathlib import Path
from datetime import datetime

from flask import Blueprint, request, jsonify, session, send_file
from openpyxl import Workbook

from modules.class_config import (
    SUPPORTED_CLASSES, CLASS_ARMS_BY_LEVEL, normalize_class_level, get_ss_stream,
    get_class_arm_stream_label,
)

from modules.student_database.student_database import (
    STUDENT_HEADERS, get_students_by_class, add_student, edit_student,
    delete_students, move_students, create_database_backup, get_database_summary,
    normalize_admission, normalize_student_level, normalize_student_arm,
    validate_student_class,
)

from modules.student_database.admission_manager import (
    reserve_admission_number, restore_reserved_admission_number,
    get_admission_number_summary,
)

from modules.student_database.graduation_manager import (
    graduate_students, read_graduates, search_graduates, get_graduation_summary,
    clear_graduate_archive,
)

from modules.student_database.promotion_safeguards import (
    DEMOTION_PATH, build_guard, recommended_promotion_sequence, recommended_first_action,
)
from modules.student_database.student_import_manager import (
    analyze_student_upload, commit_student_import, canonical_csv_template, SUPPORTED_EXTENSIONS,
)


promotion_bp = Blueprint("promotion_bp", __name__)

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_DIR = BASE_DIR / "static" / "data" / "database"
LOG_FILE = DATABASE_DIR / "promotion_logs.csv"

CLASSES = list(SUPPORTED_CLASSES)

PROMOTION_PATH = {
    "JSS1": "JSS2",
    "JSS2": "JSS3",
    "JSS3": "SS1",
    "SS1": "SS2",
    "SS2": "SS3",
    "SS3": "GRADUATED",
}

LOG_HEADERS = ["Timestamp", "Action", "From", "To", "Count", "Admissions", "Admin", "Note"]


# ============================================================
# BASIC HELPERS
# ============================================================

def clean(value):
    return str(value or "").strip()


def get_admin_name():
    return session.get("admin_username") or session.get("username") or session.get("user") or "Admin"


def normalize_requested_class(value):
    level = normalize_class_level(clean(value))
    return level if level in CLASSES else ""


def normalize_admissions(values):
    result = []

    for value in values or []:
        admission = normalize_admission(value)
        if admission and admission not in result:
            result.append(admission)

    return result


def resolve_request_mode(data, allow_all=True):
    """Protect selected-student actions from accidentally becoming whole-class actions."""
    mode = clean((data or {}).get("mode") or "selected").lower()
    if mode not in {"selected", "all"}:
        raise ValueError("Invalid promotion scope. Use selected or all.")
    if mode == "all":
        if not allow_all:
            raise ValueError("Whole-class mode is not allowed for this action.")
        confirmed = (data or {}).get("confirm_entire_class")
        confirmed = confirmed is True or str(confirmed or "").strip().lower() in {"1", "true", "yes"}
        if not confirmed:
            raise ValueError("Whole-class action was not explicitly confirmed. Re-open Promote Entire Class and confirm the full-class scope.")
    return mode


# ============================================================
# ACTIVITY LOG
# ============================================================

def log_action(action, from_class="", to_class="", admissions=None, note=""):
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)

    admissions = normalize_admissions(admissions or [])
    file_exists = LOG_FILE.exists()

    with LOG_FILE.open("a", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=LOG_HEADERS)

        if not file_exists:
            writer.writeheader()

        writer.writerow({
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Action": clean(action),
            "From": clean(from_class),
            "To": clean(to_class),
            "Count": len(admissions),
            "Admissions": ";".join(admissions),
            "Admin": get_admin_name(),
            "Note": clean(note),
        })


def read_logs(limit=30):
    if not LOG_FILE.exists():
        return []

    with LOG_FILE.open("r", newline="", encoding="utf-8-sig") as file:
        rows = list(csv.DictReader(file))

    return rows[-max(1, int(limit)):][::-1]


# ============================================================
# FRONTEND STUDENT FORMAT
# ============================================================

def frontend_student(student):
    class_level = normalize_student_level(student.get("Class_category") or student.get("Class"))
    class_arm = normalize_student_arm(student.get("Class"), class_level)

    row = dict(student)
    row["Class_category"] = class_level
    row["Class"] = class_arm
    row["Class_level"] = class_level
    row["Class_arm"] = class_arm
    row["Stream"] = get_ss_stream(class_arm)
    row["Stream_label"] = get_class_arm_stream_label(class_arm)
    row["Status"] = "ACTIVE"

    return row


# ============================================================
# SELECT STUDENTS
# ============================================================

def get_selected_students(class_category, admissions=None, mode="selected"):
    class_category = normalize_requested_class(class_category)

    if not class_category:
        raise ValueError("Invalid class category.")

    students = get_students_by_class(class_category)

    if clean(mode).lower() == "all":
        if not students:
            raise ValueError(f"No students found in {class_category}.")
        return students

    admission_set = set(normalize_admissions(admissions))

    if not admission_set:
        raise ValueError("No students selected.")

    selected = [
        student for student in students
        if normalize_admission(student.get("Admission_number")) in admission_set
    ]

    found = {
        normalize_admission(student.get("Admission_number"))
        for student in selected
    }

    missing = sorted(admission_set - found)

    if missing:
        raise ValueError(f"Student(s) not found in {class_category}: {', '.join(missing)}.")

    return selected


# ============================================================
# NEW STUDENT CLASS ARM ASSIGNMENT
# ============================================================

def _balanced_arm(class_category, stream=""):
    available_arms = list(CLASS_ARMS_BY_LEVEL.get(class_category, []))
    stream = clean(stream).upper()
    if stream == "SCIENCE": available_arms = [arm for arm in available_arms if get_ss_stream(arm) == "SCIENCE"]
    elif stream in {"ART_COMMERCIAL", "ART", "COMMERCIAL"}: available_arms = [arm for arm in available_arms if get_ss_stream(arm) == "ART_COMMERCIAL"]
    if not available_arms: raise ValueError(f"No compatible class arms are configured for {class_category}.")
    counts = {arm: 0 for arm in available_arms}
    for student in get_students_by_class(class_category):
        arm = normalize_student_arm(student.get("Class"), class_category)
        if arm in counts: counts[arm] += 1
    return min(available_arms, key=lambda arm: (counts.get(arm, 0), available_arms.index(arm)))


def resolve_student_arm(class_category, requested_arm=""):
    class_category = normalize_requested_class(class_category)
    if not class_category: raise ValueError("Invalid class category.")
    available_arms = list(CLASS_ARMS_BY_LEVEL.get(class_category, []))
    if not available_arms: raise ValueError(f"No class arms are configured for {class_category}.")

    requested_arm = clean(requested_arm)
    requested_key = requested_arm.upper().replace(" ", "_")
    auto_stream = ""
    if requested_key in {"AUTO", "AUTOMATIC", "BALANCED", "AUTOMATIC_ASSIGNMENT"}: requested_arm = ""
    elif requested_key in {"AUTO_SCIENCE", "SCIENCE_AUTO"}: requested_arm = ""; auto_stream = "SCIENCE"
    elif requested_key in {"AUTO_ART_COMMERCIAL", "AUTO_ARTS_COMMERCIAL", "ART_COMMERCIAL_AUTO"}: requested_arm = ""; auto_stream = "ART_COMMERCIAL"

    if requested_arm:
        class_arm = normalize_student_arm(requested_arm, class_category)
        if not class_arm:
            available = ", ".join(available_arms)
            raise ValueError(f"Invalid class arm for {class_category}. Choose one of: {available}.")
        validate_student_class(class_category, class_arm)
        return class_arm, "manual"

    class_arm = _balanced_arm(class_category, auto_stream)
    validate_student_class(class_category, class_arm)
    return class_arm, "automatic-balanced"


# ============================================================
# PROMOTION DESTINATION HELPERS
# ============================================================

def class_suffix(class_arm, class_level):
    class_arm = normalize_student_arm(class_arm, class_level)

    if not class_arm or not class_arm.startswith(class_level):
        return ""

    return class_arm[len(class_level):]


def resolve_destination_arm(student, destination_level, explicit_arm=""):
    source_level = normalize_student_level(student.get("Class_category") or student.get("Class"))
    source_arm = normalize_student_arm(student.get("Class"), source_level)

    # --------------------------------------------------------
    # EXPLICIT DESTINATION ARM
    # --------------------------------------------------------
    if explicit_arm:
        destination_arm = normalize_student_arm(explicit_arm, destination_level)

        if not destination_arm:
            available = ", ".join(CLASS_ARMS_BY_LEVEL.get(destination_level, []))
            raise ValueError(
                f"Invalid destination arm for {destination_level}. Choose one of: {available}."
            )

        validate_student_class(destination_level, destination_arm)
        return destination_arm

    # --------------------------------------------------------
    # JSS ↔ JSS
    # Preserve A / B / C for both promotion and demotion.
    # --------------------------------------------------------
    if source_level.startswith("JSS") and destination_level.startswith("JSS"):
        suffix = class_suffix(source_arm, source_level)
        destination_arm = normalize_student_arm(f"{destination_level}{suffix}", destination_level)
        if destination_arm: return destination_arm

    # --------------------------------------------------------
    # JSS3 → SS1
    # MUST CHOOSE SS STREAM / ARM
    # --------------------------------------------------------
    if source_level == "JSS3" and destination_level == "SS1":
        available = ", ".join(CLASS_ARMS_BY_LEVEL.get("SS1", []))
        raise ValueError(
            "SS1 destination arm is required when promoting "
            f"JSS3 students. Choose one of: {available}."
        )

    # --------------------------------------------------------
    # SS1 → SS2 / SS2 → SS3
    # PRESERVE COMPATIBLE ARM
    # --------------------------------------------------------
    if source_level.startswith("SS") and destination_level.startswith("SS"):
        suffix = class_suffix(source_arm, source_level)
        destination_arm = normalize_student_arm(
            f"{destination_level}{suffix}", destination_level
        )

        if destination_arm:
            return destination_arm

        available = ", ".join(CLASS_ARMS_BY_LEVEL.get(destination_level, []))
        raise ValueError(
            f"{source_arm} cannot be mapped automatically to "
            f"{destination_level}. Choose one of: {available}."
        )

    available = ", ".join(CLASS_ARMS_BY_LEVEL.get(destination_level, []))
    raise ValueError(f"Destination class arm is required. Choose one of: {available}.")


def build_destination_map(students, destination_level, destination_arm="", destination_classes=None):
    destination_classes = destination_classes or {}

    normalized_map = {
        normalize_admission(admission): clean(class_arm)
        for admission, class_arm in destination_classes.items()
    }

    result = {}

    for student in students:
        admission = normalize_admission(student.get("Admission_number"))
        student_explicit_arm = normalized_map.get(admission) or clean(destination_arm)

        result[admission] = resolve_destination_arm(
            student, destination_level, student_explicit_arm
        )

    return result


# ============================================================
# EXPORT HELPERS
# ============================================================

def export_students_csv(rows, filename):
    text_buffer = io.StringIO()

    writer = csv.DictWriter(
        text_buffer, fieldnames=STUDENT_HEADERS, extrasaction="ignore"
    )

    writer.writeheader()
    writer.writerows(rows)

    binary_buffer = io.BytesIO(text_buffer.getvalue().encode("utf-8-sig"))
    binary_buffer.seek(0)

    return send_file(
        binary_buffer,
        as_attachment=True,
        download_name=filename,
        mimetype="text/csv",
    )


def export_students_excel(rows, filename, title="Students"):
    workbook = Workbook()
    worksheet = workbook.active

    worksheet.title = title[:31]
    worksheet.append(STUDENT_HEADERS)

    for student in rows:
        worksheet.append([student.get(header, "") for header in STUDENT_HEADERS])

    worksheet.freeze_panes = "A2"
    worksheet.auto_filter.ref = f"A1:H{max(1, len(rows) + 1)}"

    widths = {
        "A": 18,
        "B": 22,
        "C": 22,
        "D": 24,
        "E": 18,
        "F": 12,
        "G": 18,
        "H": 18,
    }

    for column, width in widths.items():
        worksheet.column_dimensions[column].width = width

    binary_buffer = io.BytesIO()

    workbook.save(binary_buffer)
    workbook.close()
    binary_buffer.seek(0)

    return send_file(
        binary_buffer,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# ============================================================
# SUMMARY
# ============================================================

@promotion_bp.route("/api/promotion/summary")
def api_promotion_summary():
    try:
        summary = get_database_summary()
        graduation_summary = get_graduation_summary()
        admission_summary = get_admission_number_summary()

        for level in CLASSES:
            summary[level]["next"] = PROMOTION_PATH.get(level, "")

        return jsonify({
            "success": True,
            "summary": summary,
            "graduation": graduation_summary,
            "admission_numbers": admission_summary,
            "promotion_roadmap": recommended_promotion_sequence(summary),
            "recommended_first_action": recommended_first_action(summary),
        })

    except Exception as error:
        return jsonify({"success": False, "message": str(error)}), 500


# ============================================================
# STUDENT LIST
# ============================================================

@promotion_bp.route("/api/promotion/students")
def api_promotion_students():
    try:
        class_category = normalize_requested_class(request.args.get("class", "JSS1"))
        class_arm = clean(request.args.get("arm"))

        if not class_category:
            return jsonify({"success": False, "message": "Invalid class category."}), 400

        if class_arm:
            normalized_arm = normalize_student_arm(class_arm, class_category)

            if not normalized_arm:
                return jsonify({
                    "success": False,
                    "message": f"Invalid class arm for {class_category}.",
                }), 400

            class_arm = normalized_arm

        students = [
            frontend_student(student)
            for student in get_students_by_class(class_category, class_arm)
        ]

        return jsonify({
            "success": True,
            "class": class_category,
            "arm": class_arm,
            "students": students,
            "count": len(students),
            "available_arms": CLASS_ARMS_BY_LEVEL.get(class_category, []),
            "next_class": PROMOTION_PATH.get(class_category, ""),
        })

    except Exception as error:
        return jsonify({"success": False, "message": str(error)}), 500


# ============================================================
# ACTIVITY LOGS
# ============================================================

@promotion_bp.route("/api/promotion/logs")
def api_promotion_logs():
    try:
        limit = request.args.get("limit", 30, type=int)
        return jsonify({"success": True, "logs": read_logs(limit)})

    except Exception as error:
        return jsonify({"success": False, "message": str(error)}), 500


# ============================================================
# ADD / EDIT STUDENT
# ============================================================

@promotion_bp.route("/api/promotion/student/save", methods=["POST"])
def api_save_student():
    data = request.get_json(silent=True) or {}
    student = dict(data.get("student") or {})
    original_admission = normalize_admission(data.get("original_admission"))

    try:
        # ----------------------------------------------------
        # CLASS LEVEL
        # ----------------------------------------------------
        class_category = normalize_requested_class(
            student.get("Class_category") or student.get("Class")
        )

        if not class_category:
            return jsonify({"success": False, "message": "Invalid class category."}), 400

        # ----------------------------------------------------
        # CLASS ARM
        #
        # Blank = automatic random assignment.
        # Selected arm = validate and preserve.
        # ----------------------------------------------------
        class_arm, arm_source = resolve_student_arm(class_category, student.get("Class"))

        student["Class_category"] = class_category
        student["Class"] = class_arm

        # ----------------------------------------------------
        # EDIT EXISTING STUDENT
        # ----------------------------------------------------
        if original_admission:
            student["Admission_number"] = original_admission

            result = edit_student(original_admission, student)
            saved_student = result["student"]

            log_action(
                "EDIT_STUDENT",
                class_category,
                class_category,
                [original_admission],
                (
                    f"Student record updated. Class arm: {class_arm}. "
                    f"Arm source: {arm_source}. Backup: {result['backup']}"
                ),
            )

            return jsonify({
                "success": True,
                "message": f"Student {original_admission} updated successfully.",
                "student": frontend_student(saved_student),
                "class_arm": class_arm,
                "arm_source": arm_source,
                "backup": result["backup"],
            })

        # ----------------------------------------------------
        # ADD NEW STUDENT
        #
        # ALWAYS prefer a released graduate admission number.
        #
        # admission_manager.py is responsible for generating a
        # fresh stdNNN when no recycled number is available.
        # ----------------------------------------------------
        reservation = reserve_admission_number(prefer_recycled=True)
        admission = normalize_admission(reservation["admission_number"])

        if not admission:
            raise ValueError("EMIS could not reserve an admission number.")

        student["Admission_number"] = admission

        # ----------------------------------------------------
        # SAVE STUDENT
        #
        # add_student() updates students2026.csv and then
        # synchronizes all six class XLSX databases through
        # commit_master_transaction().
        # ----------------------------------------------------
        try:
            result = add_student(student)

        except Exception:
            restore_reserved_admission_number(admission, reservation["source"])
            raise

        saved_student = result["student"]

        log_action(
            "ADD_STUDENT",
            "",
            class_category,
            [admission],
            (
                f"Admission source: {reservation['source']}. "
                f"Class arm: {class_arm}. Arm source: {arm_source}. "
                f"Backup: {result['backup']}"
            ),
        )

        return jsonify({
            "success": True,
            "message": f"Student added successfully with admission number {admission}.",
            "student": frontend_student(saved_student),
            "admission_number": admission,
            "admission_source": reservation["source"],
            "class_arm": class_arm,
            "arm_source": arm_source,
            "backup": result["backup"],
        })

    except ValueError as error:
        return jsonify({"success": False, "message": str(error)}), 400

    except Exception as error:
        return jsonify({"success": False, "message": f"Student save failed: {error}"}), 500


# ============================================================
# DELETE STUDENTS
# ============================================================

@promotion_bp.route("/api/promotion/delete", methods=["POST"])
def api_delete_students():
    data = request.get_json(silent=True) or {}

    try:
        class_category = normalize_requested_class(
            data.get("class_category") or data.get("class")
        )

        if not class_category:
            return jsonify({"success": False, "message": "Invalid class category."}), 400

        students = get_selected_students(
            class_category,
            data.get("admissions"),
            data.get("mode", "selected"),
        )

        admissions = [
            normalize_admission(student.get("Admission_number"))
            for student in students
        ]

        result = delete_students(class_category, admissions)

        log_action(
            "DELETE_STUDENT",
            class_category,
            "REMOVED",
            result["deleted_admissions"],
            (
                "Student left/was removed from active database. "
                "Admission numbers were NOT released. "
                f"Backup: {result['backup']}"
            ),
        )

        return jsonify({
            "success": True,
            "message": f"{result['count']} student(s) deleted from {class_category}.",
            "count": result["count"],
            "deleted": result["deleted"],
            "backup": result["backup"],
        })

    except ValueError as error:
        return jsonify({"success": False, "message": str(error)}), 400

    except Exception as error:
        return jsonify({"success": False, "message": f"Delete failed: {error}"}), 500


# ============================================================
# PROMOTE STUDENTS
# ============================================================

@promotion_bp.route("/api/promotion/promote", methods=["POST"])
def api_promote_students():
    data = request.get_json(silent=True) or {}

    try:
        source_class = normalize_requested_class(
            data.get("class_category") or data.get("from_class")
        )

        if not source_class:
            return jsonify({"success": False, "message": "Invalid source class."}), 400

        destination_class = PROMOTION_PATH.get(source_class)

        if not destination_class:
            return jsonify({
                "success": False,
                "message": "This class does not have a valid promotion destination.",
            }), 400

        if destination_class == "GRADUATED":
            return jsonify({
                "success": False,
                "message": "SS3 students must use the Graduation action instead of Promotion.",
            }), 400

        requested_destination = normalize_requested_class(data.get("to_class"))

        if data.get("to_class") and requested_destination != destination_class:
            return jsonify({
                "success": False,
                "message": (
                    f"{source_class} students can only be promoted to {destination_class}."
                ),
            }), 400

        mode = resolve_request_mode(data, allow_all=True)
        students = get_selected_students(
            source_class,
            data.get("admissions"),
            mode,
        )

        admissions = [
            normalize_admission(student.get("Admission_number"))
            for student in students
        ]

        destination_map = build_destination_map(
            students=students,
            destination_level=destination_class,
            destination_arm=data.get("destination_arm", ""),
            destination_classes=data.get("destination_classes") or {},
        )

        result = move_students(
            source_class=source_class,
            destination_class=destination_class,
            admissions=admissions,
            destination_classes=destination_map,
            reason="promotion",
        )

        placement_counts = {}
        for item in result["moved"]:
            key = f"{item.get('From', '')} → {item.get('To', '')}"
            placement_counts[key] = placement_counts.get(key, 0) + 1
        placement_text = "; ".join(f"{key}: {count}" for key, count in sorted(placement_counts.items()))
        log_action(
            "PROMOTE", source_class, destination_class, result["admissions"],
            f"Promotion completed. Scope: {mode}. Placements: {placement_text}. Backup: {result['backup']}",
        )

        return jsonify({
            "success": True,
            "message": (
                f"{result['count']} student(s) promoted from "
                f"{source_class} to {destination_class}."
            ),
            "count": result["count"],
            "source_class": source_class,
            "destination_class": destination_class,
            "moved": result["moved"],
            "placements": placement_counts,
            "scope": mode,
            "backup": result["backup"],
        })

    except ValueError as error:
        return jsonify({"success": False, "message": str(error)}), 400

    except Exception as error:
        return jsonify({"success": False, "message": f"Promotion failed: {error}"}), 500


# ============================================================
# REPEAT STUDENTS
# ============================================================

@promotion_bp.route("/api/promotion/repeat", methods=["POST"])
def api_repeat_students():
    data = request.get_json(silent=True) or {}

    try:
        class_category = normalize_requested_class(
            data.get("class_category") or data.get("class")
        )

        if not class_category:
            return jsonify({"success": False, "message": "Invalid class category."}), 400

        students = get_selected_students(
            class_category,
            data.get("admissions"),
            data.get("mode", "selected"),
        )

        admissions = [
            normalize_admission(student.get("Admission_number"))
            for student in students
        ]

        log_action(
            "REPEAT",
            class_category,
            class_category,
            admissions,
            clean(data.get("note")) or "Student(s) retained in the same class.",
        )

        return jsonify({
            "success": True,
            "message": (
                f"{len(students)} student(s) marked to repeat {class_category}. "
                "They remain in the same class."
            ),
            "count": len(students),
            "class_category": class_category,
            "students": [frontend_student(student) for student in students],
        })

    except ValueError as error:
        return jsonify({"success": False, "message": str(error)}), 400

    except Exception as error:
        return jsonify({
            "success": False,
            "message": f"Repeat action failed: {error}",
        }), 500


# ============================================================
# GRADUATE SS3 STUDENTS
# ============================================================

@promotion_bp.route("/api/promotion/graduate", methods=["POST"])
def api_graduate_students():
    data = request.get_json(silent=True) or {}

    try:
        source_class = normalize_requested_class(
            data.get("class_category") or data.get("class") or "SS3"
        )

        if source_class != "SS3":
            return jsonify({
                "success": False,
                "message": "Only SS3 students can be graduated.",
            }), 400

        mode = resolve_request_mode(data, allow_all=True)
        students = get_selected_students(
            "SS3",
            data.get("admissions"),
            mode,
        )

        admissions = [
            normalize_admission(student.get("Admission_number"))
            for student in students
        ]

        result = graduate_students(
            admissions=admissions,
            graduation_date=data.get("graduation_date"),
            academic_session=data.get("academic_session", ""),
        )

        released_text = ", ".join(result["released_admission_numbers"])

        log_action(
            "GRADUATE",
            "SS3",
            "GRADUATED",
            admissions,
            f"Graduated and archived. Admission numbers released: {released_text}",
        )

        return jsonify({
            "success": True,
            "message": f"{result['count']} SS3 student(s) graduated successfully.",
            "count": result["count"],
            "graduated": result["graduated"],
            "graduation_date": result["graduation_date"],
            "graduation_year": result["graduation_year"],
            "academic_session": result["academic_session"],
            "released_admission_numbers": result["released_admission_numbers"],
            "archive_file": result["archive_file"],
            "database_backup": result["database_backup"],
        })

    except ValueError as error:
        return jsonify({"success": False, "message": str(error)}), 400

    except Exception as error:
        return jsonify({"success": False, "message": f"Graduation failed: {error}"}), 500


# ============================================================
# GRADUATE ARCHIVE
# ============================================================

@promotion_bp.route("/api/promotion/graduates")
def api_promotion_graduates():
    try:
        search = clean(request.args.get("search"))
        year = clean(request.args.get("year"))

        if year and not year.isdigit():
            return jsonify({
                "success": False,
                "message": "Invalid graduation year.",
            }), 400

        if search or year:
            graduates = search_graduates(
                search=search,
                year=int(year) if year else None,
            )
        else:
            graduates = read_graduates()

        return jsonify({
            "success": True,
            "graduates": graduates,
            "count": len(graduates),
            "summary": get_graduation_summary(),
        })

    except Exception as error:
        return jsonify({"success": False, "message": str(error)}), 500


# ============================================================
# CLEAR GRADUATE ARCHIVE
#
# Removes archive history only. It does NOT restore students to
# SS3 and does NOT change/re-release admission numbers.
# ============================================================

@promotion_bp.route("/api/promotion/graduates/clear", methods=["POST"])
def api_clear_promotion_graduates():
    data = request.get_json(silent=True) or {}

    try:
        confirmation = clean(data.get("confirmation")).upper()

        if confirmation != "DELETE":
            return jsonify({
                "success": False,
                "message": "Type DELETE exactly to confirm clearing the graduate archive.",
            }), 400

        scope = clean(data.get("scope") or "all").lower()
        year = clean(data.get("year"))

        if scope not in {"all", "year"}:
            return jsonify({
                "success": False,
                "message": "Invalid graduate archive clear scope.",
            }), 400

        if scope == "year":
            if not year or not year.isdigit():
                return jsonify({
                    "success": False,
                    "message": "Choose a valid graduation year before clearing that year.",
                }), 400
            clear_year = int(year)
        else:
            clear_year = None

        result = clear_graduate_archive(
            year=clear_year,
            requested_by=get_admin_name(),
        )

        scope_text = str(clear_year) if clear_year else "ALL YEARS"
        log_action(
            "CLEAR_GRADUATE_ARCHIVE",
            "GRADUATE ARCHIVE",
            scope_text,
            result.get("admissions") or [],
            (
                f"Cleared {result['count']} archived graduate record(s). "
                f"Safety backup: {result['backup_directory']}. "
                "Active students and admission-number status were not changed."
            ),
        )

        return jsonify({
            "success": True,
            "message": (
                f"{result['count']} archived graduate record(s) cleared successfully "
                f"from {scope_text}. A safety backup was created first."
            ),
            "count": result["count"],
            "scope": result["scope"],
            "year": result["year"],
            "backup_directory": result["backup_directory"],
            "graduation_log_preserved": result["graduation_log_preserved"],
            "active_student_database_changed": result["active_student_database_changed"],
            "admission_number_pool_changed": result["admission_number_pool_changed"],
            "summary": get_graduation_summary(),
        })

    except ValueError as error:
        return jsonify({"success": False, "message": str(error)}), 400

    except Exception as error:
        return jsonify({
            "success": False,
            "message": f"Graduate archive clear failed: {error}",
        }), 500


# ============================================================
# SMART PROMOTION GUARD / ROADMAP
# ============================================================

@promotion_bp.route("/api/promotion/guard", methods=["POST"])
def api_promotion_guard():
    data = request.get_json(silent=True) or {}
    try:
        action = clean(data.get("action") or "promote").lower()
        source_class = normalize_requested_class(data.get("class_category") or data.get("class") or data.get("from_class"))
        if not source_class: return jsonify({"success": False, "message": "Invalid source class."}), 400
        admissions = normalize_admissions(data.get("admissions") or [])
        mode = clean(data.get("mode") or "selected").lower()
        selected_count = None
        if mode != "all" and admissions:
            selected_count = len(get_selected_students(source_class, admissions, "selected"))
        result = build_guard(
            action=action, source_class=source_class, selected_admissions=admissions, selected_count=selected_count,
            mode=mode, destination_classes=data.get("destination_classes") or {}, use_ai=bool(data.get("use_ai")),
        )
        return jsonify({"success": True, **result})
    except ValueError as error: return jsonify({"success": False, "message": str(error)}), 400
    except Exception as error: return jsonify({"success": False, "message": f"Promotion guard failed: {error}"}), 500


# ============================================================
# DEMOTE SELECTED STUDENTS
# ============================================================

@promotion_bp.route("/api/promotion/demote", methods=["POST"])
def api_demote_students():
    data = request.get_json(silent=True) or {}
    try:
        source_class = normalize_requested_class(data.get("class_category") or data.get("from_class"))
        if not source_class: return jsonify({"success": False, "message": "Invalid source class."}), 400
        destination_class = DEMOTION_PATH.get(source_class)
        if not destination_class: return jsonify({"success": False, "message": f"{source_class} does not have a lower class in the EMIS progression path."}), 400
        if clean(data.get("mode")).lower() == "all": return jsonify({"success": False, "message": "Whole-class demotion is intentionally disabled. Select the individual students to demote."}), 400
        students = get_selected_students(source_class, data.get("admissions"), "selected")
        admissions = [normalize_admission(student.get("Admission_number")) for student in students]
        destination_map = build_destination_map(students=students, destination_level=destination_class, destination_arm=data.get("destination_arm", ""), destination_classes=data.get("destination_classes") or {})
        result = move_students(source_class=source_class, destination_class=destination_class, admissions=admissions, destination_classes=destination_map, reason="demotion")
        log_action("DEMOTE", source_class, destination_class, result["admissions"], f"Selected-student demotion completed. Backup: {result['backup']}")
        return jsonify({"success": True, "message": f"{result['count']} student(s) demoted from {source_class} to {destination_class}.", "count":result["count"], "source_class":source_class, "destination_class":destination_class, "moved":result["moved"], "backup":result["backup"]})
    except ValueError as error: return jsonify({"success": False, "message": str(error)}), 400
    except Exception as error: return jsonify({"success": False, "message": f"Demotion failed: {error}"}), 500


# ============================================================
# SMART STUDENT IMPORT
# ============================================================

@promotion_bp.route("/api/promotion/import/analyze", methods=["POST"])
def api_analyze_student_import():
    try:
        upload = request.files.get("file")
        if not upload or not clean(upload.filename): return jsonify({"success": False, "message": "Choose a student file to analyze."}), 400
        payload = upload.read(12 * 1024 * 1024 + 1)
        if len(payload) > 12 * 1024 * 1024: return jsonify({"success": False, "message": "Student import file is larger than 12 MB."}), 400
        result = analyze_student_upload(payload, upload.filename, default_class_category=request.form.get("default_class_category", ""), default_class_arm=request.form.get("default_class_arm", ""), use_ai=clean(request.form.get("use_ai", "1")).lower() not in {"0","false","no","off"})
        return jsonify({"success": True, **result})
    except ValueError as error: return jsonify({"success": False, "message": str(error)}), 400
    except Exception as error: return jsonify({"success": False, "message": f"Student import analysis failed: {error}"}), 500


@promotion_bp.route("/api/promotion/import/commit", methods=["POST"])
def api_commit_student_import():
    data = request.get_json(silent=True) or {}
    try:
        result = commit_student_import(data.get("rows") or [], mode=data.get("mode") or "add")
        admissions = [normalize_admission(row.get("Admission_number")) for row in result.get("added", []) + result.get("updated", []) if normalize_admission(row.get("Admission_number"))]
        log_action("IMPORT_STUDENTS", "UPLOAD", "ACTIVE_DATABASE", admissions, f"Smart student import: {result['added_count']} added, {result['updated_count']} updated. Backup: {result['backup']}")
        return jsonify({**result, "message": f"Student import completed: {result['added_count']} added and {result['updated_count']} updated."})
    except ValueError as error: return jsonify({"success": False, "message": str(error)}), 400
    except Exception as error: return jsonify({"success": False, "message": f"Student import failed: {error}"}), 500


@promotion_bp.route("/api/promotion/import/template")
def api_student_import_template():
    content = canonical_csv_template().encode("utf-8-sig")
    return send_file(io.BytesIO(content), as_attachment=True, download_name="EMIS_student_import_template.csv", mimetype="text/csv; charset=utf-8")


# ============================================================
# MANUAL BACKUP
# ============================================================

@promotion_bp.route("/api/promotion/backup", methods=["POST"])
def api_backup_database():
    try:
        data = request.get_json(silent=True) or {}
        reason = clean(data.get("reason")) or "manual_backup"

        snapshot = create_database_backup(reason)

        log_action(
            "BACKUP",
            "MASTER",
            "MASTER",
            [],
            f"Manual student database backup created: {snapshot.name}",
        )

        return jsonify({
            "success": True,
            "message": "Student database backup created successfully.",
            "backup": snapshot.name,
        })

    except Exception as error:
        return jsonify({"success": False, "message": f"Backup failed: {error}"}), 500


# ============================================================
# EXPORT CLASS
# ============================================================

@promotion_bp.route("/api/promotion/export")
def api_export_class():
    try:
        class_category = normalize_requested_class(request.args.get("class", "JSS1"))
        class_arm = clean(request.args.get("arm"))
        export_format = clean(request.args.get("format", "xlsx")).lower()

        if not class_category:
            return jsonify({"success": False, "message": "Invalid class category."}), 400

        if class_arm:
            class_arm = normalize_student_arm(class_arm, class_category)

            if not class_arm:
                return jsonify({
                    "success": False,
                    "message": f"Invalid class arm for {class_category}.",
                }), 400

        students = get_students_by_class(class_category, class_arm)

        if not students:
            return jsonify({
                "success": False,
                "message": f"No students found in {class_arm or class_category}.",
            }), 404

        label = class_arm or class_category
        safe_label = label.replace("/", "-")

        if export_format == "csv":
            return export_students_csv(students, f"{safe_label}_Students.csv")

        return export_students_excel(
            students,
            f"{safe_label}_Students.xlsx",
            f"{label} Students",
        )

    except Exception as error:
        return jsonify({"success": False, "message": f"Export failed: {error}"}), 500