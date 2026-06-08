# modules/student_lookup.py

import csv
import os
import re
import unicodedata

from modules.class_config import (
    STUDENT_CSV_FILES,
    normalize_class_level,
    normalize_class_arm,
    get_ss_stream,
    is_valid_class,
)


def normalize_login_text(value):
    """
    Login-safe normalizer.

    Examples:
        Abdul-Mumin  -> abdulmumin
        ABDUL MUMIN  -> abdulmumin
        Abdul.Mumin  -> abdulmumin
        O'Connor     -> oconnor
        std-512      -> std512
    """
    value = str(value or "").strip()

    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode("ascii")

    value = value.lower()
    value = re.sub(r"[^a-z0-9]", "", value)

    return value


def clean_text(value):
    return str(value or "").strip()


def build_full_name(row):
    return " ".join([
        clean_text(row.get("Last_name")),
        clean_text(row.get("First_name")),
        clean_text(row.get("Other_names")),
    ]).strip()


def build_login_name_tokens(student):
    """
    Builds all acceptable name tokens for login.

    A student can login with:
      - first name
      - last name / surname
      - other name
      - any individual part of the full name

    All tokens are normalized.
    """
    tokens = set()

    possible_values = [
        student.get("first_name"),
        student.get("last_name"),
        student.get("other_names"),
        student.get("full_name"),
    ]

    for value in possible_values:
        raw = str(value or "").strip()

        if not raw:
            continue

        normalized_whole = normalize_login_text(raw)
        if normalized_whole:
            tokens.add(normalized_whole)

        for part in re.split(r"[\s,\-/_.']+", raw):
            normalized_part = normalize_login_text(part)
            if normalized_part:
                tokens.add(normalized_part)

    return tokens


def student_name_matches(student, entered_name):
    entered = normalize_login_text(entered_name)

    if not entered:
        return False

    allowed_tokens = build_login_name_tokens(student)

    return entered in allowed_tokens


def normalize_csv_class_value(value):
    """
    Cleans class values coming from CSV.

    Examples:
        SS 1 GOLD  -> SS1_GOLD
        SS1 GOLD   -> SS1_GOLD
        SS 2B      -> SS2B
        JSS 1A     -> JSS1A
    """
    value = str(value or "").upper().strip()

    if not value:
        return ""

    value = value.replace("-", "_")
    value = re.sub(r"\s+", " ", value)

    # SS science arms
    value = re.sub(r"^(SS[123])\s+(GOLD|SILVER|DIAMOND)$", r"\1_\2", value)
    value = re.sub(r"^(SS)\s+([123])\s+(GOLD|SILVER|DIAMOND)$", r"\1\2_\3", value)

    # SS B arms
    value = re.sub(r"^(SS)\s+([123])\s*B$", r"\1\2B", value)
    value = re.sub(r"^(SS[123])\s*B$", r"\1B", value)

    # JSS arms
    value = re.sub(r"^(JSS)\s+([123])\s*([ABC])$", r"\1\2\3", value)
    value = re.sub(r"^(JSS[123])\s*([ABC])$", r"\1\2", value)

    return value.replace(" ", "")


def normalize_class_category(value, fallback):
    """
    Converts/validates broad class category.

    Examples:
        JSS1A      -> JSS1
        JSS2B      -> JSS2
        SS1_GOLD   -> SS1
        SS2B       -> SS2
        SS3_SILVER -> SS3
    """
    value = normalize_csv_class_value(value)
    fallback = normalize_csv_class_value(fallback)

    class_level = normalize_class_level(value)

    if class_level:
        return class_level

    fallback_level = normalize_class_level(fallback)

    if fallback_level:
        return fallback_level

    if is_valid_class(value):
        return value

    return ""


def normalize_student_class_arm(class_value, class_category_value, fallback_class_category):
    """
    Returns exact class arm/category for the student.

    Priority:
      1. Class column
      2. Class_category column
      3. CSV file fallback level

    Examples:
        Class = JSS1A       -> JSS1A
        Class = SS1_GOLD    -> SS1_GOLD
        Class = SS 2B       -> SS2B
        Class_category = SS3 -> SS3
    """
    class_value = normalize_csv_class_value(class_value)
    class_category_value = normalize_csv_class_value(class_category_value)
    fallback_class_category = normalize_csv_class_value(fallback_class_category)

    broad_level = (
        normalize_class_level(class_value)
        or normalize_class_level(class_category_value)
        or normalize_class_level(fallback_class_category)
    )

    exact_arm = normalize_class_arm(class_value, broad_level)

    if exact_arm and exact_arm != broad_level:
        return exact_arm

    exact_arm = normalize_class_arm(class_category_value, broad_level)

    if exact_arm:
        return exact_arm

    exact_arm = normalize_class_arm(fallback_class_category, broad_level)

    if exact_arm:
        return exact_arm

    return broad_level or ""


def find_student_by_admission(admission_number):
    admission_number = normalize_login_text(admission_number)

    if not admission_number:
        return None

    for fallback_class_category, csv_path in STUDENT_CSV_FILES.items():
        if not os.path.exists(csv_path):
            continue

        with open(csv_path, newline="", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)

            for row in reader:
                csv_admission = normalize_login_text(row.get("Admission_number", ""))

                if csv_admission != admission_number:
                    continue

                raw_class = clean_text(row.get("Class"))
                raw_class_category = clean_text(row.get("Class_category"))

                class_category = normalize_class_category(
                    raw_class_category or raw_class,
                    fallback_class_category
                )

                class_arm = normalize_student_class_arm(
                    raw_class,
                    raw_class_category,
                    fallback_class_category
                )

                if not class_category:
                    class_category = normalize_class_level(class_arm)

                if not class_arm:
                    class_arm = class_category

                full_name = build_full_name(row)
                stream = get_ss_stream(class_arm)

                student = {
                    "id": clean_text(row.get("Admission_number")),
                    "admission_number": clean_text(row.get("Admission_number")),
                    "last_name": clean_text(row.get("Last_name")),
                    "first_name": clean_text(row.get("First_name")),
                    "other_names": clean_text(row.get("Other_names")),
                    "full_name": full_name,
                    "phone": clean_text(row.get("Phone")),

                    # Exact class arm e.g. JSS1A, SS1_GOLD, SS2B
                    "class": class_arm,
                    "class_arm": class_arm,

                    # Broad portal/exam class e.g. JSS1, SS1
                    "class_category": class_category,
                    "class_level": class_category,

                    # SS stream awareness
                    # SCIENCE / ART_COMMERCIAL / GENERAL / ""
                    "stream": stream,
                    "ss_stream": stream,

                    # Raw CSV values for debugging/admin use
                    "raw_class": raw_class,
                    "raw_class_category": raw_class_category,
                }

                student["login_name_tokens"] = sorted(build_login_name_tokens(student))

                return student

    return None