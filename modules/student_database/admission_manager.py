# MODULE: Admission Manager — Generates, reserves and recycles student admission numbers

import json
from pathlib import Path
from datetime import datetime

from modules.student_database.student_database import read_master_students, normalize_admission


BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATABASE_DIR = BASE_DIR / "static" / "data" / "database"
ADMISSION_DIR = DATABASE_DIR / "admission_numbers"
AVAILABLE_NUMBERS_FILE = ADMISSION_DIR / "available_numbers.json"


# ============================================================
# DIRECTORY
# ============================================================

def ensure_admission_directory():
    ADMISSION_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# ADMISSION NUMBER HELPERS
# ============================================================

def admission_number_value(admission_number):
    admission = normalize_admission(admission_number)

    if admission.startswith("std") and admission[3:].isdigit():
        return int(admission[3:])

    return None


def format_admission_number(number):
    number = int(number)

    if number < 1:
        raise ValueError("Admission number must be greater than zero.")

    return f"std{number:03d}"


def is_valid_admission_number(admission_number):
    return admission_number_value(admission_number) is not None


# ============================================================
# ACTIVE ADMISSION NUMBERS
# ============================================================

def get_active_admission_numbers():
    return {
        normalize_admission(student.get("Admission_number"))
        for student in read_master_students()
        if normalize_admission(student.get("Admission_number"))
    }


def admission_number_is_active(admission_number):
    admission = normalize_admission(admission_number)

    if not admission:
        return False

    return admission in get_active_admission_numbers()


# ============================================================
# AVAILABLE / RECYCLED NUMBER FILE
# ============================================================

def load_available_numbers():
    ensure_admission_directory()

    if not AVAILABLE_NUMBERS_FILE.exists():
        return []

    try:
        with AVAILABLE_NUMBERS_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)

    except (json.JSONDecodeError, OSError):
        return []

    if isinstance(data, dict):
        numbers = data.get("available", [])

    elif isinstance(data, list):
        numbers = data

    else:
        numbers = []

    if not isinstance(numbers, list):
        numbers = []

    active_numbers = get_active_admission_numbers()
    cleaned = []

    for value in numbers:
        admission = normalize_admission(value)

        if not admission:
            continue

        if not is_valid_admission_number(admission):
            continue

        if admission in active_numbers:
            continue

        if admission in cleaned:
            continue

        cleaned.append(admission)

    cleaned.sort(key=lambda value: admission_number_value(value) or 999999999)

    return cleaned


def save_available_numbers(numbers):
    ensure_admission_directory()

    active_numbers = get_active_admission_numbers()
    cleaned = []

    for value in numbers or []:
        admission = normalize_admission(value)

        if not admission:
            continue

        if not is_valid_admission_number(admission):
            continue

        if admission in active_numbers:
            continue

        if admission in cleaned:
            continue

        cleaned.append(admission)

    cleaned.sort(key=lambda value: admission_number_value(value) or 999999999)

    payload = {
        "available": cleaned,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }

    temp_path = AVAILABLE_NUMBERS_FILE.with_name(f"{AVAILABLE_NUMBERS_FILE.stem}.tmp.json")

    with temp_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)

    temp_path.replace(AVAILABLE_NUMBERS_FILE)

    return cleaned


def admission_number_is_available(admission_number):
    admission = normalize_admission(admission_number)

    if not admission:
        return False

    return admission in load_available_numbers()


# ============================================================
# CLEAN AVAILABLE NUMBER POOL
# ============================================================

def clean_available_number_pool():
    available = load_available_numbers()
    cleaned = save_available_numbers(available)

    return {
        "success": True,
        "available_count": len(cleaned),
        "available_numbers": cleaned,
    }


# ============================================================
# HIGHEST ADMISSION NUMBERS
# ============================================================

def get_highest_active_admission_number():
    highest = 0

    for admission in get_active_admission_numbers():
        number = admission_number_value(admission)

        if number is not None and number > highest:
            highest = number

    return highest


def get_highest_available_admission_number():
    highest = 0

    for admission in load_available_numbers():
        number = admission_number_value(admission)

        if number is not None and number > highest:
            highest = number

    return highest


def get_highest_known_admission_number():
    return max(
        get_highest_active_admission_number(),
        get_highest_available_admission_number(),
    )


# ============================================================
# GENERATE NEW ADMISSION NUMBER
#
# Used ONLY when there is no recycled admission number to use,
# or when recycled-number preference has explicitly been
# disabled.
#
# The generated number must not exist in:
#
#   • students2026.csv
#   • available_numbers.json
# ============================================================

def generate_new_admission_number():
    active_numbers = get_active_admission_numbers()
    available_numbers = set(load_available_numbers())

    number = get_highest_known_admission_number() + 1

    while True:
        admission = format_admission_number(number)

        if admission not in active_numbers and admission not in available_numbers:
            return admission

        number += 1


# ============================================================
# PEEK NEXT ADMISSION NUMBER
#
# Does NOT reserve or remove any number.
#
# This is useful for summaries or previews only.
# ============================================================

def peek_next_admission_number(prefer_recycled=True):
    available = load_available_numbers()

    if prefer_recycled and available:
        return available[0]

    return generate_new_admission_number()


# ============================================================
# RESERVE ADMISSION NUMBER
#
# DEFAULT RULE:
#
#   1. Use the lowest released graduate admission number.
#   2. If none exists, generate the next new stdNNN.
#
# Recycled numbers are immediately removed from the available
# pool while the student-save transaction is running.
#
# If student creation fails, promotion_manager.py calls
# restore_reserved_admission_number().
# ============================================================

def reserve_admission_number(prefer_recycled=True):
    available = load_available_numbers()

    # --------------------------------------------------------
    # RECYCLED GRADUATE NUMBER
    # --------------------------------------------------------
    if prefer_recycled and available:
        admission = normalize_admission(available.pop(0))

        if not admission:
            raise RuntimeError("Invalid recycled admission number.")

        if not is_valid_admission_number(admission):
            raise RuntimeError(f"Invalid recycled admission number: {admission}.")

        if admission_number_is_active(admission):
            raise RuntimeError(f"Admission number {admission} is already assigned to an active student.")

        save_available_numbers(available)

        return {
            "success": True,
            "admission_number": admission,
            "source": "recycled",
        }

    # --------------------------------------------------------
    # NEW ADMISSION NUMBER
    # --------------------------------------------------------
    admission = generate_new_admission_number()

    if not admission:
        raise RuntimeError("Unable to generate a new admission number.")

    if not is_valid_admission_number(admission):
        raise RuntimeError(f"Generated admission number is invalid: {admission}.")

    if admission_number_is_active(admission):
        raise RuntimeError(f"Admission number {admission} is already assigned to an active student.")

    if admission_number_is_available(admission):
        raise RuntimeError(f"Admission number {admission} is currently reserved in the recycled admission-number pool.")

    return {
        "success": True,
        "admission_number": admission,
        "source": "new",
    }


# ============================================================
# RELEASE ADMISSION NUMBER
#
# Used ONLY after successful SS3 graduation.
#
# Deleted, expelled or withdrawn students do NOT automatically
# release their admission numbers.
# ============================================================

def release_admission_number(admission_number):
    admission = normalize_admission(admission_number)

    if not admission:
        raise ValueError("Admission number is required.")

    if not is_valid_admission_number(admission):
        raise ValueError(f"Invalid admission number: {admission_number}.")

    if admission_number_is_active(admission):
        raise ValueError(f"Admission number {admission} still belongs to an active student and cannot be released.")

    available = load_available_numbers()

    if admission not in available:
        available.append(admission)

    available = save_available_numbers(available)

    return {
        "success": True,
        "admission_number": admission,
        "available_count": len(available),
        "available_numbers": available,
    }


# ============================================================
# REMOVE NUMBER FROM AVAILABLE POOL
# ============================================================

def remove_available_admission_number(admission_number):
    admission = normalize_admission(admission_number)

    if not admission:
        raise ValueError("Admission number is required.")

    if not is_valid_admission_number(admission):
        raise ValueError(f"Invalid admission number: {admission_number}.")

    available = load_available_numbers()

    if admission not in available:
        return False

    available.remove(admission)
    save_available_numbers(available)

    return True


# ============================================================
# RESTORE FAILED RECYCLED RESERVATION
#
# If a recycled admission number was removed from the pool but
# add_student() later fails, the number must be returned to the
# available pool.
#
# Freshly generated numbers do not need restoration because
# they were never removed from a persistent pool.
# ============================================================

def restore_reserved_admission_number(admission_number, source):
    admission = normalize_admission(admission_number)
    source = str(source or "").strip().lower()

    if not admission:
        return False

    if source != "recycled":
        return False

    if not is_valid_admission_number(admission):
        return False

    if admission_number_is_active(admission):
        return False

    available = load_available_numbers()

    if admission not in available:
        available.append(admission)

    save_available_numbers(available)

    return True


# ============================================================
# ASSIGN ADMISSION NUMBER
#
# Convenience helper.
#
# Does not write the student to students2026.csv.
# It only reserves an admission number and optionally returns a
# student dictionary containing that number.
# ============================================================

def assign_admission_number(student=None, prefer_recycled=True):
    reservation = reserve_admission_number(prefer_recycled=prefer_recycled)

    result = {
        "Admission_number": reservation["admission_number"],
        "source": reservation["source"],
    }

    if student is not None:
        student_record = dict(student)
        student_record["Admission_number"] = reservation["admission_number"]
        result["student"] = student_record

    return result


# ============================================================
# ADMISSION NUMBER SUMMARY
# ============================================================

def get_admission_number_summary():
    active = get_active_admission_numbers()
    available = load_available_numbers()

    next_admission = available[0] if available else generate_new_admission_number()
    next_source = "recycled" if available else "new"

    return {
        "active_count": len(active),
        "available_count": len(available),
        "next_admission_number": next_admission,
        "next_admission_source": next_source,
        "highest_active_number": get_highest_active_admission_number(),
        "highest_available_number": get_highest_available_admission_number(),
        "highest_known_number": get_highest_known_admission_number(),
        "available_numbers": available,
    }