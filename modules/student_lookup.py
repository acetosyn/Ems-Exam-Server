# modules/student_lookup.py

import csv
import re
import unicodedata
from pathlib import Path

from modules.class_config import (
    STUDENT_CSV_FILE,
    normalize_class_level,
    normalize_class_arm,
    get_ss_stream,
    is_valid_class,
    is_valid_class_arm,
)


# =========================================================
# PATHS
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent

STUDENT_DATABASE = (
    BASE_DIR
    / STUDENT_CSV_FILE
)


# =========================================================
# LOGIN TEXT NORMALIZATION
# =========================================================

def normalize_login_text(value):
    """
    Normalize values used during student login.

    Examples:

        Abdul-Mumin
            -> abdulmumin

        ABDUL MUMIN
            -> abdulmumin

        Abdul.Mumin
            -> abdulmumin

        O'Connor
            -> oconnor

        std-512
            -> std512

        STD 512
            -> std512
    """

    value = str(
        value or ""
    ).strip()

    if not value:
        return ""

    value = unicodedata.normalize(
        "NFKD",
        value,
    )

    value = (
        value
        .encode(
            "ascii",
            "ignore",
        )
        .decode(
            "ascii"
        )
    )

    value = value.lower()

    value = re.sub(
        r"[^a-z0-9]",
        "",
        value,
    )

    return value


# =========================================================
# GENERIC TEXT CLEANER
# =========================================================

def clean_text(value):
    return str(
        value or ""
    ).strip()


# =========================================================
# SEX NORMALIZATION
# =========================================================

def normalize_sex(value):
    value = clean_text(
        value
    ).upper()

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
# STATUS NORMALIZATION
# =========================================================

def normalize_status(value):
    """
    Existing students2026.csv may not yet contain Status.

    Missing Status means ACTIVE.

    Possible values:
        ACTIVE
        GRADUATED
        LEFT
    """

    value = clean_text(
        value
    ).upper()

    if not value:
        return "ACTIVE"

    return value


# =========================================================
# BUILD FULL NAME
# =========================================================

def build_full_name(row):
    """
    Standard name order:

        Last_name First_name Other_names
    """

    parts = [
        clean_text(
            row.get("Last_name")
        ),
        clean_text(
            row.get("First_name")
        ),
        clean_text(
            row.get("Other_names")
        ),
    ]

    return " ".join(
        part
        for part in parts
        if part
    ).strip()


# =========================================================
# LOGIN NAME TOKENS
#
# IMPORTANT:
# The student may login using ONLY:
#
#   - First_name
#   OR
#   - Last_name
#
# Other_names is intentionally NOT accepted as a login name.
# =========================================================

def build_login_name_tokens(student):
    """
    Build valid student-login names.

    Accepted:
        First name
        Last name / surname

    Not accepted:
        Other names
        Full name
        Random individual middle-name components

    All comparisons are case-insensitive and punctuation-insensitive.
    """

    tokens = set()

    possible_values = [
        student.get(
            "first_name"
        ),
        student.get(
            "last_name"
        ),
    ]

    for value in possible_values:

        normalized = normalize_login_text(
            value
        )

        if normalized:
            tokens.add(
                normalized
            )

    return tokens


# =========================================================
# STUDENT NAME MATCHING
# =========================================================

def student_name_matches(
    student,
    entered_name,
):
    """
    Verify the name entered during login.

    Login succeeds if entered_name matches either:

        student.first_name
        OR
        student.last_name

    Matching ignores:
        capitalization
        spaces
        hyphens
        apostrophes
        dots
        other punctuation
    """

    entered = normalize_login_text(
        entered_name
    )

    if not entered:
        return False

    allowed_tokens = build_login_name_tokens(
        student
    )

    return entered in allowed_tokens


# =========================================================
# ADMISSION NUMBER NORMALIZATION
# =========================================================

def normalize_admission_number(value):
    """
    Normalize admission numbers for comparison.

    Examples:

        std001
        STD001
        std-001
        std 001

    all become:

        std001
    """

    return normalize_login_text(
        value
    )


# =========================================================
# CLASS CATEGORY NORMALIZATION
# =========================================================

def normalize_class_category(
    value,
    fallback="",
):
    """
    Convert any class/arm value to broad class level.

    Examples:

        JSS1A
            -> JSS1

        JSS2C
            -> JSS2

        SS1_GOLD
            -> SS1

        SS1_B/C
            -> SS1

        SS2B
            -> SS2

        SS2B&C
            -> SS2
    """

    class_level = (
        normalize_class_level(
            value
        )
        or
        normalize_class_level(
            fallback
        )
    )

    if (
        class_level
        and is_valid_class(
            class_level
        )
    ):
        return class_level

    return ""


# =========================================================
# EXACT STUDENT CLASS ARM
# =========================================================

def normalize_student_class_arm(
    class_value,
    class_category_value="",
):
    """
    Return the student's exact normalized class arm.

    Examples:

        JSS1A
            -> JSS1A

        JSS2C
            -> JSS2C

        SS1_GOLD
            -> SS1_GOLD

        SS1B
            -> SS1_B/C

        SS1_B&C
            -> SS1_B/C

        SS2BC
            -> SS2_B/C

        SS3_B/C
            -> SS3_B/C
    """

    broad_level = (
        normalize_class_level(
            class_value
        )
        or
        normalize_class_level(
            class_category_value
        )
    )

    if not broad_level:
        return ""

    exact_arm = normalize_class_arm(
        class_value,
        broad_level,
    )

    if (
        exact_arm
        and is_valid_class_arm(
            exact_arm
        )
    ):
        return exact_arm

    exact_arm = normalize_class_arm(
        class_category_value,
        broad_level,
    )

    if (
        exact_arm
        and is_valid_class_arm(
            exact_arm
        )
    ):
        return exact_arm

    return broad_level


# =========================================================
# NORMALIZE STUDENT CSV ROW
# =========================================================

def normalize_student_row(row):
    """
    Convert a students2026.csv row into the standard
    student object used by the rest of the application.
    """

    raw_class = clean_text(
        row.get("Class")
    )

    raw_class_category = clean_text(
        row.get("Class_category")
    )

    class_category = normalize_class_category(
        raw_class_category
        or raw_class
    )

    class_arm = normalize_student_class_arm(
        raw_class,
        raw_class_category,
    )

    if (
        not class_category
        and class_arm
    ):
        class_category = normalize_class_level(
            class_arm
        )

    if not class_arm:
        class_arm = class_category

    full_name = build_full_name(
        row
    )

    stream = get_ss_stream(
        class_arm
    )

    status = normalize_status(
        row.get("Status")
    )

    student = {
        # -------------------------------------------------
        # Identity
        # -------------------------------------------------

        "id":
            clean_text(
                row.get(
                    "Admission_number"
                )
            ),

        "admission_number":
            clean_text(
                row.get(
                    "Admission_number"
                )
            ),

        # -------------------------------------------------
        # Name
        # -------------------------------------------------

        "last_name":
            clean_text(
                row.get(
                    "Last_name"
                )
            ),

        "first_name":
            clean_text(
                row.get(
                    "First_name"
                )
            ),

        "other_names":
            clean_text(
                row.get(
                    "Other_names"
                )
            ),

        "full_name":
            full_name,

        # -------------------------------------------------
        # Contact
        # -------------------------------------------------

        "phone":
            clean_text(
                row.get(
                    "Phone"
                )
            ),

        # -------------------------------------------------
        # Sex
        # -------------------------------------------------

        "sex":
            normalize_sex(
                row.get(
                    "Sex"
                )
            ),

        # -------------------------------------------------
        # Exact class arm
        #
        # Examples:
        # JSS1A
        # JSS2B
        # SS1_GOLD
        # SS1_B/C
        # -------------------------------------------------

        "class":
            class_arm,

        "class_arm":
            class_arm,

        # -------------------------------------------------
        # Broad class level
        #
        # Examples:
        # JSS1
        # JSS2
        # SS1
        # SS2
        # -------------------------------------------------

        "class_category":
            class_category,

        "class_level":
            class_category,

        # -------------------------------------------------
        # Senior-school stream
        #
        # SCIENCE
        # ART_COMMERCIAL
        # GENERAL
        # ""
        # -------------------------------------------------

        "stream":
            stream,

        "ss_stream":
            stream,

        # -------------------------------------------------
        # Student lifecycle
        # -------------------------------------------------

        "status":
            status,

        "is_active":
            status == "ACTIVE",

        # -------------------------------------------------
        # Raw database values
        # Useful for admin/debugging.
        # -------------------------------------------------

        "raw_class":
            raw_class,

        "raw_class_category":
            raw_class_category,
    }

    student[
        "login_name_tokens"
    ] = sorted(
        build_login_name_tokens(
            student
        )
    )

    return student


# =========================================================
# READ STUDENT DATABASE
# =========================================================

def read_student_database():
    """
    Read every student from:

        static/data/database/students2026.csv

    Returns normalized student dictionaries.

    This is now the SINGLE source of truth.
    """

    if not STUDENT_DATABASE.exists():
        return []

    students = []

    with open(
        STUDENT_DATABASE,
        newline="",
        encoding="utf-8-sig",
    ) as file:

        reader = csv.DictReader(
            file
        )

        for row in reader:

            admission = normalize_admission_number(
                row.get(
                    "Admission_number"
                )
            )

            if not admission:
                continue

            student = normalize_student_row(
                row
            )

            students.append(
                student
            )

    return students


# =========================================================
# FIND STUDENT BY UNIQUE ADMISSION NUMBER
# =========================================================

def find_student_by_admission(
    admission_number,
):
    """
    Find a student using their unique std admission number.

    Examples accepted:

        std001
        STD001
        std-001
        std 001

    students2026.csv is the ONLY database searched.

    Admission numbers are expected to be globally unique.

    If no student matches:
        returns None

    If a duplicate admission number somehow exists:
        returns None rather than authenticating the wrong student.
    """

    admission_number = normalize_admission_number(
        admission_number
    )

    if not admission_number:
        return None

    if not STUDENT_DATABASE.exists():
        return None

    matches = []

    with open(
        STUDENT_DATABASE,
        newline="",
        encoding="utf-8-sig",
    ) as file:

        reader = csv.DictReader(
            file
        )

        for row in reader:

            csv_admission = normalize_admission_number(
                row.get(
                    "Admission_number"
                )
            )

            if (
                csv_admission
                != admission_number
            ):
                continue

            matches.append(
                normalize_student_row(
                    row
                )
            )

    # -----------------------------------------------------
    # No match
    # -----------------------------------------------------

    if not matches:
        return None

    # -----------------------------------------------------
    # Admission numbers MUST be unique.
    #
    # If database corruption somehow creates duplicates,
    # fail safely instead of logging in the wrong student.
    # -----------------------------------------------------

    if len(matches) > 1:
        return None

    return matches[0]


# =========================================================
# FIND ACTIVE STUDENT BY ADMISSION NUMBER
# =========================================================

def find_active_student_by_admission(
    admission_number,
):
    """
    Same as find_student_by_admission(), but prevents
    GRADUATED / LEFT students from logging into the
    active student portal.
    """

    student = find_student_by_admission(
        admission_number
    )

    if not student:
        return None

    if not student.get(
        "is_active",
        True,
    ):
        return None

    return student


# =========================================================
# AUTHENTICATE STUDENT
#
# This is the recommended login helper.
#
# Student provides:
#
#   1. Unique admission number
#   2. Either First_name OR Last_name
#
# =========================================================

def authenticate_student(
    admission_number,
    entered_name,
):
    """
    Authenticate an ACTIVE student.

    Login requires:

        Admission_number
            AND

        First_name
            OR

        Last_name

    Example:

        Admission:
            std234

        Student:
            Last_name = ADEYEMI
            First_name = FUAD

        Both of these are valid:

            std234 + FUAD

            std234 + ADEYEMI

    Other_names alone will NOT authenticate.
    """

    student = find_active_student_by_admission(
        admission_number
    )

    if not student:
        return None

    if not student_name_matches(
        student,
        entered_name,
    ):
        return None

    return student


# =========================================================
# CHECK ADMISSION NUMBER UNIQUENESS
# =========================================================

def admission_number_is_unique(
    admission_number,
):
    """
    Returns True only when exactly one student owns
    the supplied admission number.

    Useful for diagnostics/admin validation.
    """

    target = normalize_admission_number(
        admission_number
    )

    if not target:
        return False

    if not STUDENT_DATABASE.exists():
        return False

    count = 0

    with open(
        STUDENT_DATABASE,
        newline="",
        encoding="utf-8-sig",
    ) as file:

        reader = csv.DictReader(
            file
        )

        for row in reader:

            current = normalize_admission_number(
                row.get(
                    "Admission_number"
                )
            )

            if current == target:

                count += 1

                if count > 1:
                    return False

    return count == 1


# =========================================================
# DATABASE VALIDATION
# =========================================================

def validate_student_database():
    """
    Validate students2026.csv.

    Useful for admin diagnostics or startup checks.

    Returns:

        {
            "valid": True/False,
            "total": ...,
            "duplicate_admissions": [...],
            "missing_admissions": ...,
            "invalid_classes": [...],
            "invalid_sex": [...],
        }
    """

    result = {
        "valid":
            True,

        "total":
            0,

        "duplicate_admissions":
            [],

        "missing_admissions":
            0,

        "invalid_classes":
            [],

        "invalid_sex":
            [],
    }

    if not STUDENT_DATABASE.exists():

        result["valid"] = False

        result["error"] = (
            f"Student database not found: "
            f"{STUDENT_DATABASE}"
        )

        return result

    admission_counts = {}

    with open(
        STUDENT_DATABASE,
        newline="",
        encoding="utf-8-sig",
    ) as file:

        reader = csv.DictReader(
            file
        )

        for row in reader:

            admission = normalize_admission_number(
                row.get(
                    "Admission_number"
                )
            )

            if not admission:

                result[
                    "missing_admissions"
                ] += 1

                continue

            result[
                "total"
            ] += 1

            admission_counts[
                admission
            ] = (
                admission_counts.get(
                    admission,
                    0,
                )
                + 1
            )

            class_category = normalize_class_category(
                row.get(
                    "Class_category"
                )
                or row.get(
                    "Class"
                )
            )

            class_arm = normalize_student_class_arm(
                row.get(
                    "Class"
                ),
                row.get(
                    "Class_category"
                ),
            )

            if (
                not class_category
                or not is_valid_class(
                    class_category
                )
                or not class_arm
                or not is_valid_class_arm(
                    class_arm
                )
            ):

                result[
                    "invalid_classes"
                ].append({
                    "admission_number":
                        clean_text(
                            row.get(
                                "Admission_number"
                            )
                        ),

                    "class":
                        clean_text(
                            row.get(
                                "Class"
                            )
                        ),

                    "class_category":
                        clean_text(
                            row.get(
                                "Class_category"
                            )
                        ),
                })

            sex = normalize_sex(
                row.get(
                    "Sex"
                )
            )

            if sex not in {
                "",
                "M",
                "F",
            }:

                result[
                    "invalid_sex"
                ].append({
                    "admission_number":
                        clean_text(
                            row.get(
                                "Admission_number"
                            )
                        ),

                    "sex":
                        clean_text(
                            row.get(
                                "Sex"
                            )
                        ),
                })

    result[
        "duplicate_admissions"
    ] = sorted([
        admission
        for admission, count
        in admission_counts.items()
        if count > 1
    ])

    if (
        result[
            "duplicate_admissions"
        ]
        or result[
            "missing_admissions"
        ]
        or result[
            "invalid_classes"
        ]
        or result[
            "invalid_sex"
        ]
    ):

        result[
            "valid"
        ] = False

    return result