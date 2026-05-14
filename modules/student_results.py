# modules/student_results.py

import sqlite3
from pathlib import Path
from datetime import datetime

from modules.excel_manager import append_result_to_excel


DB_PATH = Path("database.db")


# ============================================================
# INIT DATABASE
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

            submitted_at TEXT NOT NULL,
            status TEXT DEFAULT 'completed'
        )
    """)

    conn.commit()
    conn.close()


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

    "P.H.E": "P.H.E",
    "PHE": "P.H.E",

    "IRK": "IRK",
    "IRS": "IRS",

    "CCA": "CCA",
    "BST": "BST",
    "PVS": "PVS",
}


def normalize_subject(name: str) -> str:
    if not name:
        return "UNKNOWN"

    name = str(name).strip().upper()
    return SUBJECT_MAP.get(name, name)


# ============================================================
# SAFE INTEGER
# ============================================================
def safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


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

    subject = normalize_subject(data.get("subject"))
    year = str(data.get("year") or datetime.now().year)

    total = safe_int(data.get("total"))
    correct = safe_int(data.get("correct"))
    answered = safe_int(data.get("answered"))
    score = safe_int(data.get("score"))

    incorrect = max(total - correct, 0)
    skipped = max(total - answered, 0)

    flagged = safe_int(data.get("flagged"))
    tab_switches = safe_int(data.get("tabSwitches") or data.get("tab_switches"))
    time_taken = safe_int(data.get("time_taken") or data.get("timeTaken"))

    student_id = data.get("student_id") or data.get("admission_number")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO student_results (
            student_id, full_name, admission_number,
            class_name, class_category,
            subject, score, correct, incorrect,
            total, answered, skipped, flagged,
            tab_switches, time_taken,
            submitted_at, status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        student_id,
        data.get("full_name"),
        data.get("admission_number"),
        data.get("class_name"),
        data.get("class_category"),

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

        submitted_at,
        data.get("status", "completed")
    ))

    conn.commit()
    conn.close()

    excel_payload = {
        "full_name": data.get("full_name"),
        "admission_number": data.get("admission_number"),
        "class_name": data.get("class_name"),
        "class_category": data.get("class_category"),
        "subject": subject,
        "score": score,
        "correct": correct,
        "total": total,
        "time_taken": time_taken,
        "submitted_at": submitted_at,
        "year": year,
    }

    append_result_to_excel(excel_payload)

    return True


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
            subject, score, correct, incorrect,
            total, answered, skipped, flagged,
            tab_switches, time_taken,
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

    return {
        "student_id": row[0],
        "full_name": row[1],
        "admission_number": row[2],
        "class_name": row[3],
        "class_category": row[4],
        "subject": row[5],
        "score": row[6],
        "correct": row[7],
        "incorrect": row[8],
        "total": row[9],
        "answered": row[10],
        "skipped": row[11],
        "flagged": row[12],
        "tabSwitches": row[13],
        "time_taken": row[14],
        "submitted_at": row[15],
        "status": row[16],
    }


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
            subject, score, correct, incorrect,
            total, answered, skipped, flagged,
            tab_switches, time_taken,
            submitted_at, status
        FROM student_results
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))

    rows = cursor.fetchall()
    conn.close()

    results = []

    for r in rows:
        results.append({
            "student_id": r[0],
            "full_name": r[1],
            "admission_number": r[2],
            "class_name": r[3],
            "class_category": r[4],
            "subject": r[5],
            "score": r[6],
            "correct": r[7],
            "incorrect": r[8],
            "total": r[9],
            "answered": r[10],
            "skipped": r[11],
            "flagged": r[12],
            "tabSwitches": r[13],
            "time_taken": r[14],
            "submitted_at": r[15],
            "status": r[16],
        })

    return results