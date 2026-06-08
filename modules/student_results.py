# modules/student_results.py

import sqlite3
from pathlib import Path
from datetime import datetime

from modules.excel_manager import append_result_to_excel
from modules.class_config import normalize_class_level, normalize_class_arm, get_ss_stream


DB_PATH = Path("database.db")


# ============================================================
# SAFE INTEGER
# ============================================================
def safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


# ============================================================
# SUBJECT NORMALIZATION
# ============================================================
SUBJECT_MAP = {
    "FINANCIAL ACCOUNTING": "FINANCIAL ACCOUNTING",
    "FINANCIAL ACCOUNT": "FINANCIAL ACCOUNTING",
    "ACCOUNTS": "FINANCIAL ACCOUNTING",
    "ACCOUNTING": "FINANCIAL ACCOUNTING",

    "ENGLISH LANGUAGE": "ENGLISH LANGUAGE",
    "ENGLISH": "ENGLISH LANGUAGE",

    "MATHEMATICS": "MATHEMATICS",
    "MATHS": "MATHEMATICS",

    "FURTHER MATHEMATICS": "FURTHER MATHEMATICS",
    "FURTHER MATHS": "FURTHER MATHEMATICS",

    "CIVIC EDUCATION": "CIVIC EDUCATION",
    "CIVIC": "CIVIC EDUCATION",

    "AGRICULTURAL SCIENCE": "AGRICULTURAL SCIENCE",
    "AGRICULTURE": "AGRICULTURAL SCIENCE",

    "DIGITAL TECH.": "DIGITAL TECH.",
    "DIGITAL TECH": "DIGITAL TECH.",
    "DIGITAL TECHNOLOGY": "DIGITAL TECH.",

    "COMPUTER SCIENCE": "COMPUTER SCIENCE",
    "COMPUTER STUDIES": "COMPUTER SCIENCE",
    "COMPUTER": "COMPUTER SCIENCE",

    "P.H.E": "P.H.E",
    "PHE": "P.H.E",

    "HERITAGE & CITIZENSHIP STUDIES": "HERITAGE & CITIZENSHIP STUDIES",
    "HCS": "HERITAGE & CITIZENSHIP STUDIES",

    "SOC. & CIT. STD": "SOC. & CIT. STD",
    "SOC & CIT STD": "SOC. & CIT. STD",

    "CIT & HER. STD": "CIT & HER. STD",
    "CIT AND HER STD": "CIT & HER. STD",

    "HORT & CROP PRODUCTION": "HORT & CROP PRODUCTION",
    "HORT AND CROP PRODUCTION": "HORT & CROP PRODUCTION",

    "ARABIC": "ARABIC LANGUAGE",
    "ARABIC LANGUAGE": "ARABIC LANGUAGE",

    "YORUBA": "YORUBA LANGUAGE",
    "YORUBA LANGUAGE": "YORUBA LANGUAGE",

    "HAUSA": "HAUSA LANGUAGE",
    "HAUSA LANGUAGE": "HAUSA LANGUAGE",

    "IRK": "IRK",
    "IRS": "IRS",
    "CCA": "CCA",
    "BST": "BST",
    "PVS": "PVS",

    "MARKETTING": "MARKETING",
    "MARKETING": "MARKETING",
}


def normalize_subject(name: str) -> str:
    if not name:
        return "UNKNOWN"

    name = str(name).strip().upper()
    return SUBJECT_MAP.get(name, name)


# ============================================================
# DATABASE COLUMN HELPERS
# ============================================================
def column_exists(cursor, table_name, column_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns


def add_column_if_missing(cursor, table_name, column_name, column_type):
    if not column_exists(cursor, table_name, column_name):
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")


# ============================================================
# INIT DATABASE + AUTO-MIGRATION
# ============================================================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS student_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            student_id TEXT NOT NULL,
            full_name TEXT NOT NULL,
            admission_number TEXT NOT NULL,

            class_name TEXT,
            class_category TEXT,

            class_arm TEXT,
            class_level TEXT,
            stream TEXT,

            subject TEXT NOT NULL,
            score INTEGER NOT NULL,
            correct INTEGER,
            incorrect INTEGER,
            total INTEGER,
            answered INTEGER,
            skipped INTEGER,
            flagged INTEGER,
            tab_switches INTEGER,
            time_taken INTEGER,

            academic_session TEXT,
            term TEXT,
            year TEXT,

            date_written TEXT,
            day_written TEXT,
            time_written TEXT,

            submitted_at TEXT NOT NULL,
            status TEXT DEFAULT 'completed'
        )
    """)

    # Existing database migration support
    add_column_if_missing(cursor, "student_results", "class_arm", "TEXT")
    add_column_if_missing(cursor, "student_results", "class_level", "TEXT")
    add_column_if_missing(cursor, "student_results", "stream", "TEXT")

    add_column_if_missing(cursor, "student_results", "academic_session", "TEXT")
    add_column_if_missing(cursor, "student_results", "term", "TEXT")
    add_column_if_missing(cursor, "student_results", "year", "TEXT")

    add_column_if_missing(cursor, "student_results", "date_written", "TEXT")
    add_column_if_missing(cursor, "student_results", "day_written", "TEXT")
    add_column_if_missing(cursor, "student_results", "time_written", "TEXT")

    conn.commit()
    conn.close()


# ============================================================
# CLASS META NORMALIZATION
# ============================================================
def resolve_class_meta(data):
    raw_class_arm = (
        data.get("class_arm")
        or data.get("class")
        or data.get("class_name")
        or data.get("class_category")
    )

    raw_class_level = (
        data.get("class_level")
        or data.get("class_category")
        or raw_class_arm
    )

    class_level = normalize_class_level(raw_class_level)
    class_arm = normalize_class_arm(raw_class_arm, class_level)

    if not class_level:
        class_level = normalize_class_level(class_arm)

    if not class_arm:
        class_arm = class_level

    stream = (
        data.get("stream")
        or data.get("ss_stream")
        or get_ss_stream(class_arm)
        or ""
    )

    return class_level, class_arm, stream


# ============================================================
# SAVE RESULT — SQLITE + EXCEL
# ============================================================
def save_result(data: dict):
    init_db()

    submitted_at = (
        data.get("submittedAt")
        or data.get("submitted_at")
        or datetime.now().isoformat()
    )

    now = datetime.now()

    subject = normalize_subject(data.get("subject"))
    year = str(data.get("year") or now.year)

    total = safe_int(data.get("total"))
    correct = safe_int(data.get("correct"))
    answered = safe_int(data.get("answered"))
    score = safe_int(data.get("score"))

    incorrect = safe_int(data.get("incorrect"), max(total - correct, 0))
    skipped = safe_int(data.get("skipped"), max(total - answered, 0))

    flagged = safe_int(data.get("flagged"))
    tab_switches = safe_int(data.get("tabSwitches") or data.get("tab_switches"))
    time_taken = safe_int(data.get("time_taken") or data.get("timeTaken"))

    student_id = data.get("student_id") or data.get("admission_number")

    class_level, class_arm, stream = resolve_class_meta(data)

    academic_session = data.get("academic_session") or data.get("session") or ""
    term = data.get("term") or ""

    date_written = data.get("date_written") or now.strftime("%Y-%m-%d")
    day_written = data.get("day_written") or now.strftime("%A")
    time_written = data.get("time_written") or now.strftime("%I:%M %p")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO student_results (
            student_id, full_name, admission_number,

            class_name, class_category,
            class_arm, class_level, stream,

            subject, score, correct, incorrect,
            total, answered, skipped, flagged,
            tab_switches, time_taken,

            academic_session, term, year,
            date_written, day_written, time_written,

            submitted_at, status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        student_id,
        data.get("full_name"),
        data.get("admission_number"),

        class_arm,
        class_level,
        class_arm,
        class_level,
        stream,

        subject,
        score,
        correct,
        incorrect,
        total,
        answered,
        skipped,
        flagged,
        tab_switches,
        time_taken,

        academic_session,
        term,
        year,
        date_written,
        day_written,
        time_written,

        submitted_at,
        data.get("status", "completed")
    ))

    conn.commit()
    conn.close()

    excel_payload = {
        "full_name": data.get("full_name"),
        "admission_number": data.get("admission_number"),

        # Keep both for older and newer Excel manager logic
        "class_name": class_arm,
        "class": class_arm,
        "class_arm": class_arm,
        "class_category": class_level,
        "class_level": class_level,
        "stream": stream,

        "subject": subject,
        "score": score,
        "correct": correct,
        "total": total,
        "time_taken": time_taken,
        "submitted_at": submitted_at,
        "year": year,

        "academic_session": academic_session,
        "term": term,
        "date_written": date_written,
        "day_written": day_written,
        "time_written": time_written,
    }

    append_result_to_excel(excel_payload)

    return True


# ============================================================
# ROW TO DICT
# ============================================================
def row_to_result(row):
    return {
        "student_id": row[0],
        "full_name": row[1],
        "admission_number": row[2],

        "class_name": row[3],
        "class_category": row[4],
        "class_arm": row[5],
        "class_level": row[6],
        "stream": row[7],

        "subject": row[8],
        "score": row[9],
        "correct": row[10],
        "incorrect": row[11],
        "total": row[12],
        "answered": row[13],
        "skipped": row[14],
        "flagged": row[15],
        "tabSwitches": row[16],
        "time_taken": row[17],

        "academic_session": row[18],
        "term": row[19],
        "year": row[20],
        "date_written": row[21],
        "day_written": row[22],
        "time_written": row[23],

        "submitted_at": row[24],
        "status": row[25],
    }


# ============================================================
# GET LATEST RESULT FOR STUDENT
# ============================================================
def get_latest_result(student_id):
    init_db()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            student_id, full_name, admission_number,

            class_name, class_category,
            class_arm, class_level, stream,

            subject, score, correct, incorrect,
            total, answered, skipped, flagged,
            tab_switches, time_taken,

            academic_session, term, year,
            date_written, day_written, time_written,

            submitted_at, status
        FROM student_results
        WHERE student_id = ?
        ORDER BY id DESC
        LIMIT 1
    """, (student_id,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return row_to_result(row)


# ============================================================
# GET ALL RESULTS
# ============================================================
def get_all_results(limit=200):
    init_db()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            student_id, full_name, admission_number,

            class_name, class_category,
            class_arm, class_level, stream,

            subject, score, correct, incorrect,
            total, answered, skipped, flagged,
            tab_switches, time_taken,

            academic_session, term, year,
            date_written, day_written, time_written,

            submitted_at, status
        FROM student_results
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))

    rows = cursor.fetchall()
    conn.close()

    return [row_to_result(row) for row in rows]