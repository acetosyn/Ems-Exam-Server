# modules/student_lookup.py

import csv
import os
from modules.class_config import STUDENT_CSV_FILES, is_valid_class


def build_full_name(row):
    return " ".join([
        str(row.get("Last_name", "")).strip(),
        str(row.get("First_name", "")).strip(),
        str(row.get("Other_names", "")).strip(),
    ]).strip()


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
    admission_number = str(admission_number or "").strip().lower()

    if not admission_number:
        return None

    for fallback_class_category, csv_path in STUDENT_CSV_FILES.items():
        if not os.path.exists(csv_path):
            continue

        with open(csv_path, newline="", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)

            for row in reader:
                csv_admission = str(row.get("Admission_number", "")).strip().lower()

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

                    return {
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

    return None