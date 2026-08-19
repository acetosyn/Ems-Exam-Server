# modules/promotion_manager.py

import csv
import io
import shutil
from pathlib import Path
from datetime import datetime

from flask import (
    Blueprint,
    render_template,
    request,
    jsonify,
    session,
    send_file,
)

from modules.class_config import (
    SUPPORTED_CLASSES,
    CLASS_ARMS,
    STUDENT_CSV_FILE,
    normalize_class_level,
    normalize_class_arm,
    get_ss_stream,
)


# =========================================================
# BLUEPRINT
# =========================================================

promotion_bp = Blueprint(
    "promotion_bp",
    __name__,
)


# =========================================================
# PATHS
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DATABASE_DIR = (
    BASE_DIR
    / "static"
    / "data"
    / "database"
)

MASTER_CSV = (
    BASE_DIR
    / STUDENT_CSV_FILE
)

BACKUP_DIR = (
    DATABASE_DIR
    / "backups"
)

LOG_FILE = (
    DATABASE_DIR
    / "promotion_logs.csv"
)


# =========================================================
# CLASS CONFIGURATION
# =========================================================

CLASSES = SUPPORTED_CLASSES

DESTINATIONS = [
    "JSS1",
    "JSS2",
    "JSS3",
    "SS1",
    "SS2",
    "SS3",
    "GRADUATED",
    "LEFT",
]


NEXT_CLASS = {
    "JSS1": "JSS2",
    "JSS2": "JSS3",
    "JSS3": "SS1",
    "SS1": "SS2",
    "SS2": "SS3",
    "SS3": "GRADUATED",
}


# =========================================================
# MASTER DATABASE HEADERS
#
# students2026.csv originally has the first 8 columns.
#
# Status is added automatically when promotion_manager
# next writes the database.
# Existing rows without Status become ACTIVE.
# =========================================================

HEADERS = [
    "Admission_number",
    "Last_name",
    "First_name",
    "Other_names",
    "Phone",
    "Sex",
    "Class",
    "Class_category",
    "Status",
]


# =========================================================
# LOG HEADERS
# =========================================================

LOG_HEADERS = [
    "Timestamp",
    "Action",
    "From",
    "To",
    "Count",
    "Admissions",
    "Admin",
    "Note",
]


# =========================================================
# BASIC HELPERS
# =========================================================

def ensure_dirs():
    DATABASE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    BACKUP_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


def clean(value):
    return str(
        value or ""
    ).strip()


def norm(value):
    return clean(
        value
    ).upper()


def normalize_sex(value):
    value = norm(value)

    if value in {
        "M",
        "MALE",
    }:
        return "M"

    if value in {
        "F",
        "FEMALE",
    }:
        return "F"

    return value


# =========================================================
# CLASS NORMALIZATION
# =========================================================

def normalize_csv_level(
    value,
    fallback="",
):
    value = norm(value)

    if value in {
        "GRADUATED",
        "LEFT",
    }:
        return value

    level = (
        normalize_class_level(value)
        or normalize_class_level(fallback)
    )

    return level or value


def normalize_csv_class(
    value,
    fallback_level="",
):
    value = norm(value)

    fallback_level = normalize_csv_level(
        fallback_level
    )

    if value in {
        "GRADUATED",
        "LEFT",
    }:
        return value

    arm = normalize_class_arm(
        value,
        fallback_level,
    )

    if arm:
        return arm

    level = normalize_class_level(
        value
    )

    if level:
        return level

    return value


# =========================================================
# ADMISSION HELPERS
# =========================================================

def admission_key(row):
    return clean(
        row.get("Admission_number")
    ).lower()


def admission_value(value):
    return clean(
        value
    ).lower()


def admission_sort_key(row):
    """
    Keep std001, std002, ... in numerical order.

    Unknown formats are placed after normal std numbers.
    """

    value = admission_key(row)

    if value.startswith("std"):
        number = value[3:]

        if number.isdigit():
            return (
                0,
                int(number),
            )

    return (
        1,
        value,
    )


# =========================================================
# NORMALIZE DATABASE ROW
# =========================================================

def normalize_row(
    row,
    fallback_class="",
):
    fallback_level = normalize_csv_level(
        fallback_class
    )

    normalized = {}

    for header in HEADERS:
        normalized[header] = clean(
            row.get(header)
        )

    # -----------------------------------------------------
    # Admission number
    # -----------------------------------------------------

    normalized["Admission_number"] = clean(
        normalized.get(
            "Admission_number"
        )
    ).lower()

    # -----------------------------------------------------
    # Sex
    # -----------------------------------------------------

    normalized["Sex"] = normalize_sex(
        normalized.get("Sex")
    )

    # -----------------------------------------------------
    # Class level
    # -----------------------------------------------------

    class_level = normalize_csv_level(
        normalized.get("Class_category")
        or normalized.get("Class")
        or fallback_level
    )

    # -----------------------------------------------------
    # Class arm
    # -----------------------------------------------------

    class_arm = normalize_csv_class(
        normalized.get("Class")
        or normalized.get("Class_category")
        or class_level,
        class_level,
    )

    # -----------------------------------------------------
    # Graduated / Left
    # -----------------------------------------------------

    if class_level in {
        "GRADUATED",
        "LEFT",
    }:
        class_arm = class_level

    normalized["Class_category"] = (
        class_level
    )

    normalized["Class"] = (
        class_arm
        or class_level
    )

    # -----------------------------------------------------
    # Status
    # -----------------------------------------------------

    status = norm(
        normalized.get("Status")
    )

    if class_level == "GRADUATED":
        status = "GRADUATED"

    elif class_level == "LEFT":
        status = "LEFT"

    elif not status:
        status = "ACTIVE"

    normalized["Status"] = status

    return normalized


# =========================================================
# READ FULL MASTER DATABASE
# =========================================================

def read_all_students():
    ensure_dirs()

    if not MASTER_CSV.exists():
        return []

    rows = []

    with open(
        MASTER_CSV,
        newline="",
        encoding="utf-8-sig",
    ) as file:

        reader = csv.DictReader(
            file
        )

        for row in reader:
            normalized = normalize_row(
                row
            )

            if not normalized.get(
                "Admission_number"
            ):
                continue

            rows.append(
                normalized
            )

    return rows


# =========================================================
# WRITE FULL MASTER DATABASE
#
# IMPORTANT:
# Every modification writes the WHOLE database.
#
# We never overwrite students2026.csv using only one class.
# =========================================================

def write_all_students(rows):
    ensure_dirs()

    normalized_rows = []

    for row in rows:
        normalized = normalize_row(
            row
        )

        if not normalized.get(
            "Admission_number"
        ):
            continue

        normalized_rows.append(
            normalized
        )

    # -----------------------------------------------------
    # Verify admission numbers remain globally unique.
    # -----------------------------------------------------

    seen = set()

    duplicates = []

    for row in normalized_rows:
        key = admission_key(
            row
        )

        if key in seen:
            duplicates.append(
                row.get(
                    "Admission_number"
                )
            )
        else:
            seen.add(
                key
            )

    if duplicates:
        duplicate_text = ", ".join(
            sorted(set(duplicates))
        )

        raise ValueError(
            "Duplicate admission number(s) detected: "
            f"{duplicate_text}"
        )

    # -----------------------------------------------------
    # Keep master CSV consistently sorted by admission no.
    # -----------------------------------------------------

    normalized_rows.sort(
        key=admission_sort_key
    )

    # -----------------------------------------------------
    # Atomic-ish write:
    # Write temporary file first, then replace master.
    # -----------------------------------------------------

    temp_path = MASTER_CSV.with_name(
        f"{MASTER_CSV.stem}.tmp.csv"
    )

    with open(
        temp_path,
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=HEADERS,
            extrasaction="ignore",
        )

        writer.writeheader()

        writer.writerows(
            normalized_rows
        )

    temp_path.replace(
        MASTER_CSV
    )

    return True


# =========================================================
# READ STUDENTS FOR ONE CLASS
#
# This now filters the SINGLE students2026.csv database.
# =========================================================

def read_students(
    class_category,
):
    requested = norm(
        class_category
    )

    if requested in {
        "GRADUATED",
        "LEFT",
    }:
        level = requested
        requested_arm = requested

    else:
        level = normalize_csv_level(
            requested
        )

        requested_arm = normalize_csv_class(
            requested,
            level,
        )

    all_rows = read_all_students()

    rows = []

    for row in all_rows:
        row_level = normalize_csv_level(
            row.get(
                "Class_category"
            )
        )

        row_arm = normalize_csv_class(
            row.get("Class"),
            row_level,
        )

        # -------------------------------------------------
        # Broad level query:
        # read_students("SS1")
        # -------------------------------------------------

        if requested_arm == level:
            if row_level == level:
                rows.append(
                    row
                )

            continue

        # -------------------------------------------------
        # Exact arm query:
        # read_students("SS1_GOLD")
        # read_students("SS1_B/C")
        # -------------------------------------------------

        if (
            row_level == level
            and row_arm == requested_arm
        ):
            rows.append(
                row
            )

    return rows


# =========================================================
# COMPATIBILITY WRITE FUNCTION
#
# Some older internal code may call:
#
#     write_students("JSS1", rows)
#
# This implementation safely replaces ONLY that class
# inside the full master CSV.
# =========================================================

def write_students(
    class_category,
    rows,
):
    target_level = normalize_csv_level(
        class_category
    )

    if target_level not in DESTINATIONS:
        raise ValueError(
            "Invalid class category."
        )

    all_rows = read_all_students()

    remaining = []

    for row in all_rows:

        row_level = normalize_csv_level(
            row.get(
                "Class_category"
            )
        )

        if row_level != target_level:
            remaining.append(
                row
            )

    incoming = []

    for row in rows:
        normalized = normalize_row(
            row,
            target_level,
        )

        normalized[
            "Class_category"
        ] = target_level

        incoming.append(
            normalized
        )

    write_all_students(
        remaining
        + incoming
    )


# =========================================================
# BACKUP MASTER DATABASE
# =========================================================

def backup_master_file(
    reason="backup",
):
    ensure_dirs()

    if not MASTER_CSV.exists():
        return None

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S_%f"
    )

    safe_reason = (
        clean(reason)
        .replace(" ", "_")
        .replace("/", "-")
        .replace("\\", "-")
    )

    if not safe_reason:
        safe_reason = "backup"

    backup_name = (
        f"students2026_"
        f"{safe_reason}_"
        f"{timestamp}.csv"
    )

    backup_path = (
        BACKUP_DIR
        / backup_name
    )

    shutil.copy2(
        MASTER_CSV,
        backup_path,
    )

    return backup_path.name


# =========================================================
# BACKWARD COMPATIBILITY
#
# Existing routes/template logic may still call
# backup_class_file().
#
# It now backs up the MASTER database.
# =========================================================

def backup_class_file(
    class_category="",
):
    reason = (
        normalize_csv_level(
            class_category
        )
        or "master"
    )

    return backup_master_file(
        reason
    )


# =========================================================
# ADMIN NAME
# =========================================================

def get_admin_name():
    return (
        session.get(
            "admin_username"
        )
        or session.get(
            "username"
        )
        or session.get(
            "user"
        )
        or "Admin"
    )


# =========================================================
# LOG ACTION
# =========================================================

def log_action(
    action,
    from_class,
    to_class,
    count,
    admissions,
    note="",
):
    ensure_dirs()

    exists = LOG_FILE.exists()

    with open(
        LOG_FILE,
        "a",
        newline="",
        encoding="utf-8-sig",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=LOG_HEADERS,
        )

        if not exists:
            writer.writeheader()

        writer.writerow({
            "Timestamp":
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),

            "Action":
                action,

            "From":
                from_class,

            "To":
                to_class,

            "Count":
                count,

            "Admissions":
                ";".join(
                    clean(adm)
                    for adm in admissions
                    if clean(adm)
                ),

            "Admin":
                get_admin_name(),

            "Note":
                note,
        })


# =========================================================
# GET CLASS ARM SUFFIX
#
# Examples:
#
# JSS1A -> A
# SS1_GOLD -> _GOLD
# SS1_B/C -> _B/C
# =========================================================

def class_arm_suffix(
    old_class,
    old_category,
):
    old_category = normalize_csv_level(
        old_category
    )

    old_class = normalize_csv_class(
        old_class,
        old_category,
    )

    if (
        not old_class
        or not old_category
    ):
        return ""

    if old_class == old_category:
        return ""

    if old_class.startswith(
        old_category
    ):
        return old_class.replace(
            old_category,
            "",
            1,
        )

    return ""


# =========================================================
# VALIDATE DESTINATION ARM
# =========================================================

def validate_destination_arm(
    destination_category,
    destination_arm,
):
    destination_category = normalize_csv_level(
        destination_category
    )

    if destination_category in {
        "GRADUATED",
        "LEFT",
    }:
        return destination_category

    if destination_category not in CLASSES:
        return ""

    if not destination_arm:
        return ""

    normalized_arm = normalize_csv_class(
        destination_arm,
        destination_category,
    )

    # User may send only:
    #
    # GOLD
    # SILVER
    # DIAMOND
    # B/C
    # A
    # B
    # C
    #
    # Try prefixing destination class.
    if normalized_arm == destination_category:

        prefixed = normalize_csv_class(
            f"{destination_category}"
            f"{destination_arm}",
            destination_category,
        )

        normalized_arm = prefixed

    valid_arms = CLASS_ARMS.get(
        destination_category,
        [],
    )

    if normalized_arm in valid_arms:
        return normalized_arm

    return ""


# =========================================================
# BUILD DESTINATION CLASS
#
# Safe rules:
#
# JSS1A -> JSS2A
# JSS2C -> JSS3C
#
# JSS3 -> SS1 requires explicit senior destination arm.
#
# SS1_GOLD -> SS2_GOLD
# SS1_B/C  -> SS2_B/C
#
# SS2_DIAMOND -> SS3 cannot auto-map because current SS3
# has no Diamond. Admin must choose a valid SS3 arm.
# =========================================================

def build_destination_class(
    old_class,
    old_category,
    destination_category,
    destination_arm="",
):
    old_category = normalize_csv_level(
        old_category
    )

    old_class = normalize_csv_class(
        old_class,
        old_category,
    )

    destination_category = normalize_csv_level(
        destination_category
    )

    # -----------------------------------------------------
    # Graduated / Left
    # -----------------------------------------------------

    if destination_category in {
        "GRADUATED",
        "LEFT",
    }:
        return destination_category

    if destination_category not in CLASSES:
        return ""

    # -----------------------------------------------------
    # Explicit destination arm always takes priority.
    # -----------------------------------------------------

    if clean(destination_arm):

        explicit_arm = validate_destination_arm(
            destination_category,
            destination_arm,
        )

        return explicit_arm

    destination_arms = CLASS_ARMS.get(
        destination_category,
        [],
    )

    # -----------------------------------------------------
    # If destination has no configured arms.
    # -----------------------------------------------------

    if not destination_arms:
        return destination_category

    # -----------------------------------------------------
    # JSS -> JSS
    #
    # Preserve A / B / C when valid.
    # -----------------------------------------------------

    if (
        old_category.startswith("JSS")
        and destination_category.startswith("JSS")
    ):

        suffix = class_arm_suffix(
            old_class,
            old_category,
        )

        if suffix in {
            "A",
            "B",
            "C",
        }:

            candidate = (
                f"{destination_category}"
                f"{suffix}"
            )

            candidate = normalize_csv_class(
                candidate,
                destination_category,
            )

            if candidate in destination_arms:
                return candidate

        return ""

    # -----------------------------------------------------
    # JSS -> SS
    #
    # A/B/C cannot safely determine Gold/Silver/Diamond/B/C.
    # Require explicit destination arm.
    # -----------------------------------------------------

    if (
        old_category.startswith("JSS")
        and destination_category.startswith("SS")
    ):
        return ""

    # -----------------------------------------------------
    # SS -> SS
    #
    # Preserve Gold / Silver / Diamond / B/C when the
    # destination supports the same arm.
    # -----------------------------------------------------

    if (
        old_category.startswith("SS")
        and destination_category.startswith("SS")
    ):

        suffix = class_arm_suffix(
            old_class,
            old_category,
        )

        if suffix:

            candidate = normalize_csv_class(
                f"{destination_category}"
                f"{suffix}",
                destination_category,
            )

            if candidate in destination_arms:
                return candidate

        return ""

    # -----------------------------------------------------
    # Other unusual moves require explicit arm.
    # -----------------------------------------------------

    return ""


# =========================================================
# DESTINATION REQUIREMENT MESSAGE
# =========================================================

def destination_arm_required_message(
    from_class,
    to_class,
):
    available = CLASS_ARMS.get(
        to_class,
        [],
    )

    options = ", ".join(
        available
    )

    if (
        from_class == "JSS3"
        and to_class == "SS1"
    ):
        return (
            "SS1 destination arm is required when promoting "
            "students from JSS3. Choose one of: "
            f"{options}."
        )

    if (
        from_class == "SS2"
        and to_class == "SS3"
    ):
        return (
            "A valid SS3 destination arm is required for any "
            "student whose current SS2 arm cannot be carried "
            "forward. Current SS3 arms are: "
            f"{options}."
        )

    return (
        f"A valid destination arm is required for {to_class}. "
        f"Choose one of: {options}."
    )


# =========================================================
# CLASS SUMMARY
# =========================================================

def get_class_summary():
    summary = {}

    all_rows = read_all_students()

    for cls in CLASSES:

        rows = [
            row
            for row in all_rows
            if normalize_csv_level(
                row.get(
                    "Class_category"
                )
            ) == cls
        ]

        active = [
            row
            for row in rows
            if norm(
                row.get(
                    "Status"
                )
            ) == "ACTIVE"
        ]

        arms_count = {}

        for row in active:

            arm = normalize_csv_class(
                row.get("Class"),
                cls,
            )

            if arm:
                arms_count[arm] = (
                    arms_count.get(
                        arm,
                        0,
                    )
                    + 1
                )

        summary[cls] = {
            "total":
                len(rows),

            "active":
                len(active),

            "next":
                NEXT_CLASS.get(
                    cls,
                    "",
                ),

            "arms":
                arms_count,

            "available_arms":
                CLASS_ARMS.get(
                    cls,
                    [],
                ),
        }

    graduated = [
        row
        for row in all_rows
        if normalize_csv_level(
            row.get(
                "Class_category"
            )
        ) == "GRADUATED"
    ]

    left = [
        row
        for row in all_rows
        if normalize_csv_level(
            row.get(
                "Class_category"
            )
        ) == "LEFT"
    ]

    summary["GRADUATED"] = {
        "total":
            len(graduated),

        "active":
            0,

        "next":
            "",

        "arms":
            {},

        "available_arms":
            [],
    }

    summary["LEFT"] = {
        "total":
            len(left),

        "active":
            0,

        "next":
            "",

        "arms":
            {},

        "available_arms":
            [],
    }

    return summary


# =========================================================
# PROMOTE / MOVE STUDENTS
# =========================================================

def promote_or_move_students(
    from_class,
    to_class,
    admissions,
    mode="selected",
    destination_arm="",
    note="",
):
    from_class = normalize_csv_level(
        from_class
    )

    to_class = normalize_csv_level(
        to_class
    )

    mode = clean(
        mode
    ).lower()

    destination_arm = clean(
        destination_arm
    )

    # -----------------------------------------------------
    # Validate classes.
    # -----------------------------------------------------

    if from_class not in CLASSES:
        return (
            False,
            "Invalid source class.",
            None,
        )

    if to_class not in DESTINATIONS:
        return (
            False,
            "Invalid destination class.",
            None,
        )

    # -----------------------------------------------------
    # Read full database.
    # -----------------------------------------------------

    all_rows = read_all_students()

    source_rows = [
        row
        for row in all_rows
        if (
            normalize_csv_level(
                row.get(
                    "Class_category"
                )
            )
            == from_class
            and norm(
                row.get(
                    "Status"
                )
            )
            == "ACTIVE"
        )
    ]

    if not source_rows:
        return (
            False,
            f"No active students found in {from_class}.",
            None,
        )

    # -----------------------------------------------------
    # Determine selected admissions.
    # -----------------------------------------------------

    if mode == "all":

        selected_admissions = {
            admission_key(row)
            for row in source_rows
            if admission_key(row)
        }

    else:

        selected_admissions = {
            admission_value(adm)
            for adm in admissions
            if clean(adm)
        }

    if not selected_admissions:
        return (
            False,
            "No students selected.",
            None,
        )

    selected_rows = [
        row
        for row in source_rows
        if admission_key(row)
        in selected_admissions
    ]

    if not selected_rows:
        return (
            False,
            "Selected students were not found.",
            None,
        )

    # -----------------------------------------------------
    # Build destination class for EVERY selected student
    # before modifying the database.
    #
    # If even one cannot be mapped safely, stop everything.
    # -----------------------------------------------------

    destination_map = {}

    for row in selected_rows:

        old_category = (
            row.get(
                "Class_category"
            )
            or from_class
        )

        old_class = (
            row.get("Class")
            or old_category
        )

        new_class = build_destination_class(
            old_class=old_class,
            old_category=old_category,
            destination_category=to_class,
            destination_arm=destination_arm,
        )

        if not new_class:

            return (
                False,
                destination_arm_required_message(
                    from_class,
                    to_class,
                ),
                {
                    "admission_number":
                        row.get(
                            "Admission_number"
                        ),

                    "current_class":
                        normalize_csv_class(
                            old_class,
                            old_category,
                        ),

                    "available_arms":
                        CLASS_ARMS.get(
                            to_class,
                            [],
                        ),
                },
            )

        destination_map[
            admission_key(row)
        ] = new_class

    # -----------------------------------------------------
    # Backup BEFORE modifying.
    # -----------------------------------------------------

    backup = backup_master_file(
        f"{from_class}_to_{to_class}"
    )

    moved_admissions = []

    # -----------------------------------------------------
    # Modify rows in place inside master database.
    # -----------------------------------------------------

    for row in all_rows:

        key = admission_key(
            row
        )

        if key not in selected_admissions:
            continue

        if normalize_csv_level(
            row.get(
                "Class_category"
            )
        ) != from_class:
            continue

        new_class = destination_map.get(
            key
        )

        if not new_class:
            continue

        row["Class_category"] = (
            to_class
        )

        row["Class"] = (
            new_class
        )

        if to_class == "GRADUATED":
            row["Status"] = "GRADUATED"

        elif to_class == "LEFT":
            row["Status"] = "LEFT"

        else:
            row["Status"] = "ACTIVE"

        moved_admissions.append(
            row.get(
                "Admission_number"
            )
        )

    if not moved_admissions:
        return (
            False,
            "No student was moved.",
            None,
        )

    # -----------------------------------------------------
    # Save master database.
    # -----------------------------------------------------

    try:
        write_all_students(
            all_rows
        )

    except Exception as error:

        return (
            False,
            f"Database update failed: {error}",
            None,
        )

    # -----------------------------------------------------
    # Determine action type.
    # -----------------------------------------------------

    action = (
        "PROMOTE"
        if to_class
        == NEXT_CLASS.get(
            from_class
        )
        else "MOVE"
    )

    if to_class == "GRADUATED":
        action = "GRADUATE"

    elif to_class == "LEFT":
        action = "MARK_LEFT"

    # -----------------------------------------------------
    # Log action.
    # -----------------------------------------------------

    log_action(
        action=action,
        from_class=from_class,
        to_class=to_class,
        count=len(
            moved_admissions
        ),
        admissions=moved_admissions,
        note=note,
    )

    return (
        True,
        (
            f"{len(moved_admissions)} student(s) "
            f"moved from {from_class} to {to_class}."
        ),
        {
            "count":
                len(
                    moved_admissions
                ),

            "admissions":
                moved_admissions,

            "backup":
                backup,
        },
    )


# =========================================================
# IMPORT CSV INTO CLASS
#
# append:
#   Add students that do not already exist globally.
#
# replace:
#   Replace ONLY students belonging to target_class,
#   while preserving all other classes in students2026.csv.
# =========================================================

def import_csv_to_class(
    target_class,
    uploaded_file,
    mode="append",
):
    target_class = normalize_csv_level(
        target_class
    )

    mode = clean(
        mode
    ).lower()

    if target_class not in CLASSES:
        return (
            False,
            "Invalid target class.",
            None,
        )

    if mode not in {
        "append",
        "replace",
    }:
        return (
            False,
            "Import mode must be append or replace.",
            None,
        )

    if not uploaded_file:
        return (
            False,
            "No CSV file uploaded.",
            None,
        )

    ensure_dirs()

    # -----------------------------------------------------
    # Decode uploaded CSV.
    # -----------------------------------------------------

    try:

        uploaded_file.stream.seek(
            0
        )

        decoded = (
            uploaded_file
            .stream
            .read()
            .decode(
                "utf-8-sig"
            )
            .splitlines()
        )

    except UnicodeDecodeError:

        uploaded_file.stream.seek(
            0
        )

        decoded = (
            uploaded_file
            .stream
            .read()
            .decode(
                "latin-1"
            )
            .splitlines()
        )

    reader = csv.DictReader(
        decoded
    )

    if not reader.fieldnames:
        return (
            False,
            "Uploaded file has no valid CSV header.",
            None,
        )

    required = [
        "Admission_number",
        "Last_name",
        "First_name",
        "Class",
        "Class_category",
    ]

    missing = [
        field
        for field in required
        if field not in reader.fieldnames
    ]

    if missing:
        return (
            False,
            (
                "Missing required columns: "
                + ", ".join(missing)
            ),
            None,
        )

    imported_rows = []

    uploaded_keys = set()

    duplicate_uploads = []

    # -----------------------------------------------------
    # Normalize uploaded rows.
    # -----------------------------------------------------

    for row in reader:

        clean_row = normalize_row(
            row,
            target_class,
        )

        admission = admission_key(
            clean_row
        )

        if not admission:
            continue

        if admission in uploaded_keys:
            duplicate_uploads.append(
                clean_row.get(
                    "Admission_number"
                )
            )

            continue

        uploaded_keys.add(
            admission
        )

        clean_row[
            "Class_category"
        ] = target_class

        class_arm = normalize_csv_class(
            clean_row.get("Class"),
            target_class,
        )

        if (
            class_arm
            not in CLASS_ARMS.get(
                target_class,
                []
            )
            and class_arm
            != target_class
        ):
            return (
                False,
                (
                    f"Invalid class arm "
                    f"'{clean_row.get('Class')}' "
                    f"for {target_class}."
                ),
                None,
            )

        clean_row["Class"] = (
            class_arm
        )

        clean_row["Status"] = (
            "ACTIVE"
        )

        imported_rows.append(
            clean_row
        )

    if duplicate_uploads:
        return (
            False,
            (
                "Duplicate admission numbers exist "
                "inside the uploaded file: "
                + ", ".join(
                    sorted(
                        set(
                            duplicate_uploads
                        )
                    )
                )
            ),
            None,
        )

    if not imported_rows:
        return (
            False,
            "No valid student rows found in uploaded CSV.",
            None,
        )

    # -----------------------------------------------------
    # Read master database.
    # -----------------------------------------------------

    all_rows = read_all_students()

    existing_by_admission = {
        admission_key(row):
            row
        for row in all_rows
    }

    # -----------------------------------------------------
    # APPEND
    # -----------------------------------------------------

    if mode == "append":

        conflicts = [
            row.get(
                "Admission_number"
            )
            for row in imported_rows
            if admission_key(row)
            in existing_by_admission
        ]

        if conflicts:
            return (
                False,
                (
                    "These admission numbers already exist "
                    "in students2026.csv: "
                    + ", ".join(
                        conflicts
                    )
                ),
                None,
            )

        final_rows = (
            all_rows
            + imported_rows
        )

        added_rows = (
            imported_rows
        )

    # -----------------------------------------------------
    # REPLACE TARGET CLASS ONLY
    # -----------------------------------------------------

    else:

        other_class_rows = [
            row
            for row in all_rows
            if normalize_csv_level(
                row.get(
                    "Class_category"
                )
            )
            != target_class
        ]

        other_class_keys = {
            admission_key(row)
            for row
            in other_class_rows
        }

        conflicts = [
            row.get(
                "Admission_number"
            )
            for row
            in imported_rows
            if admission_key(row)
            in other_class_keys
        ]

        if conflicts:
            return (
                False,
                (
                    "Cannot replace class because these "
                    "admission numbers belong to students "
                    "in another class: "
                    + ", ".join(
                        conflicts
                    )
                ),
                None,
            )

        final_rows = (
            other_class_rows
            + imported_rows
        )

        added_rows = (
            imported_rows
        )

    # -----------------------------------------------------
    # Backup & save.
    # -----------------------------------------------------

    backup = backup_master_file(
        f"import_{target_class}"
    )

    try:

        write_all_students(
            final_rows
        )

    except Exception as error:

        return (
            False,
            f"Database update failed: {error}",
            None,
        )

    admissions = [
        row.get(
            "Admission_number"
        )
        for row in added_rows
    ]

    log_action(
        action="IMPORT_CSV",
        from_class="CSV_UPLOAD",
        to_class=target_class,
        count=len(
            added_rows
        ),
        admissions=admissions,
        note=(
            f"Import mode: {mode}"
        ),
    )

    return (
        True,
        (
            f"{len(added_rows)} student(s) "
            f"imported into {target_class}."
        ),
        {
            "count":
                len(
                    added_rows
                ),

            "backup":
                backup,
        },
    )


# =========================================================
# READ LOGS
# =========================================================

def read_logs(
    limit=30,
):
    if not LOG_FILE.exists():
        return []

    with open(
        LOG_FILE,
        newline="",
        encoding="utf-8-sig",
    ) as file:

        rows = list(
            csv.DictReader(
                file
            )
        )

    return rows[
        -limit:
    ][::-1]


# =========================================================
# PROMOTION PAGE
# =========================================================

@promotion_bp.route(
    "/admin/promotion"
)
def promotion_page():

    return render_template(
        "promotion.html",
        classes=CLASSES,
        destinations=DESTINATIONS,
        class_arms=CLASS_ARMS,
    )


# =========================================================
# SUMMARY API
# =========================================================

@promotion_bp.route(
    "/api/promotion/summary"
)
def api_promotion_summary():

    return jsonify({
        "success":
            True,

        "summary":
            get_class_summary(),
    })


# =========================================================
# STUDENTS API
# =========================================================

@promotion_bp.route(
    "/api/promotion/students"
)
def api_promotion_students():

    class_category = request.args.get(
        "class",
        "JSS1",
    )

    rows = read_students(
        class_category
    )

    for row in rows:

        class_level = normalize_csv_level(
            row.get(
                "Class_category"
            )
        )

        class_arm = normalize_csv_class(
            row.get("Class"),
            class_level,
        )

        row[
            "Class_category"
        ] = class_level

        row[
            "Class"
        ] = class_arm

        # Compatibility fields used by frontend code.
        row[
            "Class_level"
        ] = class_level

        row[
            "Class_arm"
        ] = class_arm

        row[
            "Stream"
        ] = get_ss_stream(
            class_arm
        )

    return jsonify({
        "success":
            True,

        "class":
            normalize_csv_level(
                class_category
            ),

        "students":
            rows,

        "count":
            len(rows),
    })


# =========================================================
# LOGS API
# =========================================================

@promotion_bp.route(
    "/api/promotion/logs"
)
def api_promotion_logs():

    return jsonify({
        "success":
            True,

        "logs":
            read_logs(),
    })


# =========================================================
# PROMOTION API
# =========================================================

@promotion_bp.route(
    "/api/promotion/promote",
    methods=["POST"],
)
def api_promote_students():

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )

    from_class = data.get(
        "from_class"
    )

    to_class = data.get(
        "to_class"
    )

    admissions = (
        data.get(
            "admissions"
        )
        or []
    )

    mode = data.get(
        "mode",
        "selected",
    )

    destination_arm = data.get(
        "destination_arm",
        "",
    )

    note = data.get(
        "note",
        "",
    )

    (
        success,
        message,
        payload,
    ) = promote_or_move_students(
        from_class=from_class,
        to_class=to_class,
        admissions=admissions,
        mode=mode,
        destination_arm=destination_arm,
        note=note,
    )

    status = (
        200
        if success
        else 400
    )

    return jsonify({
        "success":
            success,

        "message":
            message,

        "data":
            payload,
    }), status


# =========================================================
# IMPORT API
# =========================================================

@promotion_bp.route(
    "/api/promotion/import",
    methods=["POST"],
)
def api_import_students():

    target_class = request.form.get(
        "target_class"
    )

    mode = request.form.get(
        "mode",
        "append",
    )

    uploaded_file = request.files.get(
        "csv_file"
    )

    (
        success,
        message,
        payload,
    ) = import_csv_to_class(
        target_class,
        uploaded_file,
        mode,
    )

    status = (
        200
        if success
        else 400
    )

    return jsonify({
        "success":
            success,

        "message":
            message,

        "data":
            payload,
    }), status


# =========================================================
# BACKUP API
#
# Since there is one student database, this backs up
# students2026.csv regardless of selected class.
# =========================================================

@promotion_bp.route(
    "/api/promotion/backup",
    methods=["POST"],
)
def api_backup_class():

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )

    class_category = normalize_csv_level(
        data.get(
            "class_category"
        )
        or "MASTER"
    )

    backup = backup_master_file(
        class_category
    )

    if not backup:

        return jsonify({
            "success":
                False,

            "message":
                "students2026.csv was not found.",
        }), 404

    log_action(
        action="BACKUP",
        from_class=class_category,
        to_class=class_category,
        count=0,
        admissions=[],
        note=(
            f"Master database backup created: "
            f"{backup}"
        ),
    )

    return jsonify({
        "success":
            True,

        "message":
            "Master student database backup created.",

        "backup":
            backup,
    })


# =========================================================
# EXPORT CLASS API
#
# Creates a class-specific CSV in memory without creating
# separate permanent class files.
# =========================================================

@promotion_bp.route(
    "/api/promotion/export"
)
def api_export_class():

    class_category = normalize_csv_level(
        request.args.get(
            "class"
        )
        or "JSS1"
    )

    if (
        class_category
        not in DESTINATIONS
    ):

        return jsonify({
            "success":
                False,

            "message":
                "Invalid class category.",
        }), 400

    rows = read_students(
        class_category
    )

    if not rows:

        return jsonify({
            "success":
                False,

            "message":
                (
                    f"No students found in "
                    f"{class_category}."
                ),
        }), 404

    text_buffer = io.StringIO()

    writer = csv.DictWriter(
        text_buffer,
        fieldnames=HEADERS,
        extrasaction="ignore",
    )

    writer.writeheader()

    writer.writerows(
        rows
    )

    binary_buffer = io.BytesIO(
        text_buffer
        .getvalue()
        .encode(
            "utf-8-sig"
        )
    )

    binary_buffer.seek(
        0
    )

    return send_file(
        binary_buffer,
        as_attachment=True,
        download_name=(
            f"{class_category}_Students.csv"
        ),
        mimetype="text/csv",
    )


# =========================================================
# DELETE STUDENTS API
#
# Permanently removes selected rows from students2026.csv.
#
# A full master backup is created first.
# =========================================================

@promotion_bp.route(
    "/api/promotion/delete",
    methods=["POST"],
)
def api_delete_students():

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )

    class_category = normalize_csv_level(
        data.get(
            "class_category"
        )
        or "JSS1"
    )

    admissions = {
        admission_value(adm)
        for adm
        in data.get(
            "admissions",
            [],
        )
        if clean(adm)
    }

    if not admissions:

        return jsonify({
            "success":
                False,

            "message":
                "No students selected.",
        }), 400

    all_rows = read_all_students()

    deleted = []

    kept = []

    for row in all_rows:

        row_class = normalize_csv_level(
            row.get(
                "Class_category"
            )
        )

        if (
            row_class
            == class_category
            and admission_key(row)
            in admissions
        ):

            deleted.append(
                row
            )

        else:

            kept.append(
                row
            )

    if not deleted:

        return jsonify({
            "success":
                False,

            "message":
                "Selected students were not found.",
        }), 404

    backup = backup_master_file(
        f"delete_{class_category}"
    )

    try:

        write_all_students(
            kept
        )

    except Exception as error:

        return jsonify({
            "success":
                False,

            "message":
                (
                    f"Database update failed: "
                    f"{error}"
                ),
        }), 500

    deleted_admissions = [
        row.get(
            "Admission_number"
        )
        for row in deleted
    ]

    log_action(
        action="DELETE",
        from_class=class_category,
        to_class="REMOVED",
        count=len(
            deleted
        ),
        admissions=deleted_admissions,
        note=(
            f"Backup: {backup}"
        ),
    )

    return jsonify({
        "success":
            True,

        "message":
            (
                f"{len(deleted)} student(s) "
                f"deleted from {class_category}."
            ),

        "backup":
            backup,
    })


# =========================================================
# SAVE / EDIT STUDENT API
#
# Admission numbers are globally unique across the entire
# students2026.csv database.
# =========================================================

@promotion_bp.route(
    "/api/promotion/student/save",
    methods=["POST"],
)
def api_save_student():

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )

    student = (
        data.get(
            "student"
        )
        or {}
    )

    original_admission = admission_value(
        data.get(
            "original_admission"
        )
    )

    class_category = normalize_csv_level(
        student.get(
            "Class_category"
        )
        or "JSS1"
    )

    if class_category not in CLASSES:

        return jsonify({
            "success":
                False,

            "message":
                "Invalid class category.",
        }), 400

    new_admission = admission_value(
        student.get(
            "Admission_number"
        )
    )

    if not new_admission:

        return jsonify({
            "success":
                False,

            "message":
                "Admission number is required.",
        }), 400

    clean_student = normalize_row(
        student,
        class_category,
    )

    clean_student[
        "Admission_number"
    ] = new_admission

    clean_student[
        "Class_category"
    ] = class_category

    class_arm = normalize_csv_class(
        clean_student.get(
            "Class"
        )
        or class_category,
        class_category,
    )

    valid_arms = CLASS_ARMS.get(
        class_category,
        [],
    )

    # -----------------------------------------------------
    # Require a valid arm where the level has arms.
    # -----------------------------------------------------

    if valid_arms:

        if (
            class_arm
            not in valid_arms
        ):

            return jsonify({
                "success":
                    False,

                "message":
                    (
                        f"Invalid class arm for "
                        f"{class_category}. "
                        f"Choose one of: "
                        f"{', '.join(valid_arms)}."
                    ),
            }), 400

    else:

        class_arm = class_category

    clean_student[
        "Class"
    ] = class_arm

    clean_student[
        "Status"
    ] = (
        clean_student.get(
            "Status"
        )
        or "ACTIVE"
    )

    # -----------------------------------------------------
    # Read FULL database.
    # -----------------------------------------------------

    all_rows = read_all_students()

    existing_index = None

    # -----------------------------------------------------
    # Global admission uniqueness check.
    # -----------------------------------------------------

    for index, row in enumerate(
        all_rows
    ):

        row_admission = admission_key(
            row
        )

        # Editing original row.
        if (
            original_admission
            and row_admission
            == original_admission
        ):
            existing_index = index
            continue

        # Any OTHER row using new admission is forbidden.
        if row_admission == new_admission:

            return jsonify({
                "success":
                    False,

                "message":
                    (
                        "A student with this admission "
                        "number already exists."
                    ),
            }), 400

    # -----------------------------------------------------
    # Backup before save.
    # -----------------------------------------------------

    backup = backup_master_file(
        f"save_{class_category}"
    )

    # -----------------------------------------------------
    # Add or edit.
    # -----------------------------------------------------

    if existing_index is None:

        all_rows.append(
            clean_student
        )

        action = (
            "ADD_STUDENT"
        )

        message = (
            f"Student {new_admission} "
            f"added to {class_category}."
        )

    else:

        all_rows[
            existing_index
        ] = clean_student

        action = (
            "EDIT_STUDENT"
        )

        message = (
            f"Student {new_admission} "
            f"updated."
        )

    # -----------------------------------------------------
    # Save master.
    # -----------------------------------------------------

    try:

        write_all_students(
            all_rows
        )

    except Exception as error:

        return jsonify({
            "success":
                False,

            "message":
                (
                    f"Database update failed: "
                    f"{error}"
                ),
        }), 500

    log_action(
        action=action,
        from_class=class_category,
        to_class=class_category,
        count=1,
        admissions=[
            new_admission
        ],
        note=(
            f"Backup: {backup}"
        ),
    )

    return jsonify({
        "success":
            True,

        "message":
            message,

        "student":
            clean_student,

        "backup":
            backup,
    })