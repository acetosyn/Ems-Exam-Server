# modules/student_lookup.py

import csv
import os
import re
import unicodedata

from modules.class_config import STUDENT_CSV_FILES, is_valid_class


def normalize_login_text(value):
    """
    Login-safe normalizer.

    Examples:
        Abdul-Mumin  -> abdulmumin
        ABDUL MUMIN  -> abdulmumin
        Abdul.Mumin  -> abdulmumin
        O'Connor     -> oconnor
    """
    value = str(value or "").strip()

    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode("ascii")

    value = value.lower()
    value = re.sub(r"[^a-z0-9]", "", value)

    return value


def build_full_name(row):
    return " ".join([
        str(row.get("Last_name", "")).strip(),
        str(row.get("First_name", "")).strip(),
        str(row.get("Other_names", "")).strip(),
    ]).strip()


def build_login_name_tokens(student):
    """
    Builds all acceptable name tokens for login.

    A student can login with:
      - first name
      - last name / surname
      - other name
      - any individual part of the full name

    All tokens are normalized, so Abdul-Mumin and abdulmumin match.
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


def normalize_class_category(value, fallback):
    """
    Converts/validates broad class category.

    Examples:
        JSS1A      -> JSS1
        JSS2B      -> JSS2
        SS1_GOLD   -> SS1
        SS2_B      -> SS2
        SS3_SILVER -> SS3
    """

    value = str(value or "").upper().strip()
    fallback = str(fallback or "").upper().strip()

    if is_valid_class(value):
        return value

    for cls in ["JSS1", "JSS2", "JSS3", "SS1", "SS2", "SS3"]:
        if value.startswith(cls):
            return cls

    if is_valid_class(fallback):
        return fallback

    return ""


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

                if csv_admission == admission_number:
                    class_name = str(row.get("Class", "")).upper().strip()

                    class_category = normalize_class_category(
                        row.get("Class_category"),
                        fallback_class_category
                    )

                    if not class_category:
                        class_category = normalize_class_category(
                            class_name,
                            fallback_class_category
                        )

                    full_name = build_full_name(row)

                    student = {
                        "id": row.get("Admission_number"),
                        "admission_number": row.get("Admission_number"),
                        "last_name": row.get("Last_name"),
                        "first_name": row.get("First_name"),
                        "other_names": row.get("Other_names"),
                        "full_name": full_name,
                        "phone": row.get("Phone"),

                        # Exact class arm e.g JSS1A, SS1_GOLD
                        "class": class_name,

                        # Broad portal/exam class e.g JSS1, SS1
                        "class_category": class_category,
                    }

                    student["login_name_tokens"] = sorted(build_login_name_tokens(student))

                    return student

    return None