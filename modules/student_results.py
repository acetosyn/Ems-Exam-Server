# modules/student_results.py

import sqlite3
from pathlib import Path
from datetime import datetime

from modules.excel_manager import append_result_to_excel
from modules.class_config import normalize_class_level, normalize_class_arm, get_ss_stream


# ============================================================
# PATHS / CONSTANTS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "database.db"

PASS_MARK = 50
VALID_TERMS = ("FIRST", "SECOND", "THIRD")

RESULT_COLUMNS = """
    student_id, full_name, admission_number, sex,
    class_name, class_category, class_arm, class_level, stream,
    subject, score, correct, incorrect, total, answered, skipped, flagged, tab_switches, time_taken,
    academic_session, term, year,
    date_written, day_written, time_written,
    submitted_at, status, result_status
"""


# ============================================================
# BASIC HELPERS
# ============================================================

def clean(value):
    return str(value or "").strip()


def norm(value):
    return clean(value).upper()


def safe_int(value, default=0):
    try:
        return int(float(str(value or "").replace("%", "").strip()))
    except (TypeError, ValueError):
        return default


def normalize_sex(value):
    value = norm(value)

    if value in {"M", "MALE"}:
        return "M"

    if value in {"F", "FEMALE"}:
        return "F"

    return ""


def normalize_result_status(score):
    return "PASS" if safe_int(score) >= PASS_MARK else "FAIL"


def normalize_submission_status(value):
    value = norm(value)

    if value in {"COMPLETED", "SUBMITTED", "DONE"}:
        return "COMPLETED"

    if value in {"PENDING", "IN_PROGRESS", "STARTED"}:
        return value

    return "COMPLETED"


# ============================================================
# TERM HELPERS
# ============================================================

def normalize_result_term(value):
    raw = norm(value).replace("_", " ").replace("-", " ")
    raw = " ".join(raw.split())

    aliases = {
        "FIRST": "FIRST", "FIRST TERM": "FIRST", "TERM 1": "FIRST", "TERM ONE": "FIRST", "1": "FIRST", "1ST": "FIRST", "1ST TERM": "FIRST",
        "SECOND": "SECOND", "SECOND TERM": "SECOND", "TERM 2": "SECOND", "TERM TWO": "SECOND", "2": "SECOND", "2ND": "SECOND", "2ND TERM": "SECOND",
        "THIRD": "THIRD", "THIRD TERM": "THIRD", "TERM 3": "THIRD", "TERM THREE": "THIRD", "3": "THIRD", "3RD": "THIRD", "3RD TERM": "THIRD",
    }

    return aliases.get(raw, "")


def term_label(value):
    term = normalize_result_term(value)
    return {"FIRST": "FIRST TERM", "SECOND": "SECOND TERM", "THIRD": "THIRD TERM"}.get(term, "")


def is_jss_class(value):
    return str(normalize_class_level(value) or "").upper().startswith("JSS")


# ============================================================
# SUBJECT NORMALIZATION
# ============================================================

SUBJECT_MAP = {
    "FINANCIAL ACCOUNTING": "FINANCIAL ACCOUNTING", "FINANCIAL ACCOUNT": "FINANCIAL ACCOUNTING", "ACCOUNTS": "FINANCIAL ACCOUNTING", "ACCOUNTING": "FINANCIAL ACCOUNTING",

    "ENGLISH LANGUAGE": "ENGLISH LANGUAGE", "ENGLISH": "ENGLISH LANGUAGE",

    "MATHEMATICS": "MATHEMATICS", "MATHS": "MATHEMATICS",

    "FURTHER MATHEMATICS": "FURTHER MATHEMATICS", "FURTHER MATHS": "FURTHER MATHEMATICS",

    "CIVIC EDUCATION": "CIVIC EDUCATION", "CIVIC": "CIVIC EDUCATION",

    "AGRICULTURAL SCIENCE": "AGRICULTURAL SCIENCE", "AGRICULTURE": "AGRICULTURAL SCIENCE",

    "DIGITAL TECH.": "DIGITAL TECH.", "DIGITAL TECH": "DIGITAL TECH.", "DIGITAL TECHNOLOGY": "DIGITAL TECH.",

    "COMPUTER SCIENCE": "COMPUTER SCIENCE", "COMPUTER STUDIES": "COMPUTER SCIENCE", "COMPUTER": "COMPUTER SCIENCE",

    "P.H.E": "P.H.E", "P.H.E.": "P.H.E", "PHE": "P.H.E", "PHYSICAL HEALTH EDUCATION": "P.H.E",

    "HERITAGE & CITIZENSHIP STUDIES": "HERITAGE & CITIZENSHIP STUDIES",
    "HERITAGE AND CITIZENSHIP STUDIES": "HERITAGE & CITIZENSHIP STUDIES",
    "HCS": "HERITAGE & CITIZENSHIP STUDIES",

    "SOC. & CIT. STD": "SOC. & CIT. STD", "SOC & CIT STD": "SOC. & CIT. STD", "SOCIAL AND CITIZENSHIP STUDIES": "SOC. & CIT. STD",

    "CIT & HER. STD": "CIT & HER. STD", "CIT & HER STD": "CIT & HER. STD", "CIT AND HER STD": "CIT & HER. STD",

    "HORT & CROP PRODUCTION": "HORT & CROP PRODUCTION", "HORT AND CROP PRODUCTION": "HORT & CROP PRODUCTION",

    "ARABIC": "ARABIC LANGUAGE", "ARABIC LANGUAGE": "ARABIC LANGUAGE",

    "YORUBA": "YORUBA LANGUAGE", "YORUBA LANGUAGE": "YORUBA LANGUAGE",

    "HAUSA": "HAUSA LANGUAGE", "HAUSA LANGUAGE": "HAUSA LANGUAGE",

    "TECHNICAL": "TECHNICAL DRAWING", "TECHNICAL DRAWING": "TECHNICAL DRAWING",

    "LITERATURE-IN-ENGLISH": "LITERATURE", "LITERATURE IN ENGLISH": "LITERATURE", "LITERATURE": "LITERATURE",

    "IRK": "IRK", "IRS": "IRS",

    "CCA": "CCA", "BST": "BST", "PVS": "PVS",

    "MARKETTING": "MARKETING", "MARKETING": "MARKETING",

    "ECONOMICS": "ECONOMICS", "GOVERNMENT": "GOVERNMENT", "COMMERCE": "COMMERCE", "GEOGRAPHY": "GEOGRAPHY",
    "BIOLOGY": "BIOLOGY", "CHEMISTRY": "CHEMISTRY", "PHYSICS": "PHYSICS",

    "POISE": "POISE", "ISLAMIYYAH": "ISLAMIYYAH", "ISLAMIYAH": "ISLAMIYYAH",

    "GARMENT MAKING": "GARMENT MAKING", "BUSINESS STUDIES": "BUSINESS STUDIES",

    "NATIONAL VALUE": "NATIONAL VALUE", "NATIONAL VALUES": "NATIONAL VALUE",

    "HISTORY": "HISTORY",

    "INTER SCIENCE": "INTER SCIENCE", "INTEGRATED SCIENCE": "INTER SCIENCE",
}


def normalize_subject(name):
    value = norm(name)

    if not value:
        return "UNKNOWN"

    return SUBJECT_MAP.get(value, value)


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ============================================================
# DATABASE COLUMN HELPERS
# ============================================================

def column_exists(cursor, table_name, column_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    return column_name in [row[1] for row in cursor.fetchall()]


def add_column_if_missing(cursor, table_name, column_name, column_type):
    if not column_exists(cursor, table_name, column_name):
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")


# ============================================================
# DATABASE INITIALIZATION / MIGRATION
# ============================================================

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS student_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            student_id TEXT NOT NULL,
            full_name TEXT NOT NULL,
            admission_number TEXT NOT NULL,
            sex TEXT,

            class_name TEXT,
            class_category TEXT,
            class_arm TEXT,
            class_level TEXT,
            stream TEXT,

            subject TEXT NOT NULL,

            score INTEGER NOT NULL DEFAULT 0,
            correct INTEGER DEFAULT 0,
            incorrect INTEGER DEFAULT 0,
            total INTEGER DEFAULT 0,
            answered INTEGER DEFAULT 0,
            skipped INTEGER DEFAULT 0,
            flagged INTEGER DEFAULT 0,
            tab_switches INTEGER DEFAULT 0,
            time_taken INTEGER DEFAULT 0,

            academic_session TEXT,
            term TEXT,
            year TEXT,

            date_written TEXT,
            day_written TEXT,
            time_written TEXT,

            submitted_at TEXT NOT NULL,

            status TEXT DEFAULT 'COMPLETED',
            result_status TEXT
        )
    """)

    migrations = [
        ("sex", "TEXT"),

        ("class_arm", "TEXT"),
        ("class_level", "TEXT"),
        ("stream", "TEXT"),

        ("academic_session", "TEXT"),
        ("term", "TEXT"),
        ("year", "TEXT"),

        ("date_written", "TEXT"),
        ("day_written", "TEXT"),
        ("time_written", "TEXT"),

        ("result_status", "TEXT"),
    ]

    for column_name, column_type in migrations:
        add_column_if_missing(cursor, "student_results", column_name, column_type)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_results_admission ON student_results(admission_number)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_results_student ON student_results(student_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_results_class_level ON student_results(class_level)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_results_class_arm ON student_results(class_arm)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_results_subject ON student_results(subject)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_results_year ON student_results(year)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_results_session_term ON student_results(academic_session, term)")

    cursor.execute("""
        UPDATE student_results
        SET result_status = CASE WHEN score >= ? THEN 'PASS' ELSE 'FAIL' END
        WHERE result_status IS NULL OR TRIM(result_status) = ''
    """, (PASS_MARK,))

    conn.commit()
    conn.close()


# ============================================================
# CLASS META
# ============================================================

def resolve_class_meta(data):
    raw_class_arm = data.get("class_arm") or data.get("class") or data.get("class_name") or data.get("class_category") or data.get("class_level")
    raw_class_level = data.get("class_level") or data.get("class_category") or raw_class_arm

    class_level = normalize_class_level(raw_class_level)
    class_arm = normalize_class_arm(raw_class_arm, class_level)

    if not class_level:
        class_level = normalize_class_level(class_arm)

    if not class_arm:
        class_arm = class_level

    stream = norm(data.get("stream") or data.get("ss_stream") or get_ss_stream(class_arm) or "")

    if str(class_level or "").startswith("JSS"):
        stream = "GENERAL"

    return class_level, class_arm, stream


# ============================================================
# CHECK EXISTING RESULT
# ============================================================

def result_exists(admission_number, subject, year, academic_session="", term=""):
    init_db()

    admission_number = clean(admission_number)
    subject = normalize_subject(subject)
    year = clean(year)
    academic_session = clean(academic_session)
    term = normalize_result_term(term)

    if not admission_number or not subject:
        return False

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id FROM student_results
        WHERE LOWER(TRIM(admission_number)) = LOWER(TRIM(?))
          AND UPPER(TRIM(subject)) = UPPER(TRIM(?))
          AND TRIM(COALESCE(year, '')) = TRIM(?)
          AND TRIM(COALESCE(academic_session, '')) = TRIM(?)
          AND UPPER(TRIM(COALESCE(term, ''))) = UPPER(TRIM(?))
        LIMIT 1
    """, (admission_number, subject, year, academic_session, term))

    exists = cursor.fetchone() is not None

    conn.close()

    return exists


# ============================================================
# SAVE RESULT — SQLITE + TERM-AWARE EXCEL
# ============================================================

def save_result(data):
    init_db()

    now = datetime.now()

    # --------------------------------------------------------
    # STUDENT
    # --------------------------------------------------------

    admission_number = clean(data.get("admission_number") or data.get("student_id"))
    student_id = clean(data.get("student_id") or admission_number)
    full_name = clean(data.get("full_name") or data.get("student_name"))
    sex = normalize_sex(data.get("sex") or data.get("gender"))

    if not admission_number:
        raise ValueError("Admission number is required.")

    if not student_id:
        student_id = admission_number

    if not full_name:
        raise ValueError("Student full name is required.")

    # --------------------------------------------------------
    # EXAM
    # --------------------------------------------------------

    subject = normalize_subject(data.get("subject"))
    year = clean(data.get("year") or now.year)
    academic_session = clean(data.get("academic_session") or data.get("session"))

    # --------------------------------------------------------
    # CLASS
    # --------------------------------------------------------

    class_level, class_arm, stream = resolve_class_meta(data)

    if not class_level:
        raise ValueError("Student class level is required.")

    # --------------------------------------------------------
    # TERM
    #
    # JSS = canonical FIRST/SECOND/THIRD
    # SS = no term
    # --------------------------------------------------------

    if is_jss_class(class_level):
        term = normalize_result_term(data.get("term"))

        if not term:
            raise ValueError(f"Term is required for JSS result: {class_level} / {subject}")
    else:
        term = ""

    # Keep normalized values in the original payload.
    data["term"] = term
    data["class_level"] = class_level
    data["class_category"] = class_level
    data["class_arm"] = class_arm
    data["class"] = class_arm

    # --------------------------------------------------------
    # RESULT NUMBERS
    # --------------------------------------------------------

    total = max(safe_int(data.get("total")), 0)
    correct = max(safe_int(data.get("correct")), 0)
    answered = max(safe_int(data.get("answered")), 0)
    score = max(safe_int(data.get("score", data.get("score_percentage", data.get("percentage", 0)))), 0)

    if total > 0:
        correct = min(correct, total)
        answered = min(answered, total)

    incorrect_default = max(answered - correct, 0)
    incorrect = max(safe_int(data.get("incorrect"), incorrect_default), 0)

    skipped_default = max(total - answered, 0)
    skipped = max(safe_int(data.get("skipped"), skipped_default), 0)

    flagged = max(safe_int(data.get("flagged")), 0)
    tab_switches = max(safe_int(data.get("tabSwitches") or data.get("tab_switches")), 0)
    time_taken = max(safe_int(data.get("time_taken") or data.get("timeTaken")), 0)

    # --------------------------------------------------------
    # STATUS
    # --------------------------------------------------------

    submission_status = normalize_submission_status(data.get("submission_status") or data.get("status") or "COMPLETED")
    result_status = normalize_result_status(score)

    # --------------------------------------------------------
    # DATE
    # --------------------------------------------------------

    submitted_at = clean(data.get("submitted_at") or data.get("submittedAt") or now.strftime("%Y-%m-%d %H:%M:%S"))
    date_written = clean(data.get("date_written") or now.strftime("%Y-%m-%d"))
    day_written = clean(data.get("day_written") or now.strftime("%A"))
    time_written = clean(data.get("time_written") or now.strftime("%I:%M %p"))

    # --------------------------------------------------------
    # DUPLICATE PROTECTION
    # --------------------------------------------------------

    if result_exists(
        admission_number=admission_number,
        subject=subject,
        year=year,
        academic_session=academic_session,
        term=term,
    ):
        return False

    # --------------------------------------------------------
    # SQLITE
    # --------------------------------------------------------

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO student_results (
                student_id, full_name, admission_number, sex,
                class_name, class_category, class_arm, class_level, stream,
                subject, score, correct, incorrect, total, answered, skipped, flagged, tab_switches, time_taken,
                academic_session, term, year,
                date_written, day_written, time_written,
                submitted_at, status, result_status
            )
            VALUES (
                ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?
            )
        """, (
            student_id, full_name, admission_number, sex,

            class_arm, class_level, class_arm, class_level, stream,

            subject, score, correct, incorrect, total, answered, skipped, flagged, tab_switches, time_taken,

            academic_session, term, year,

            date_written, day_written, time_written,

            submitted_at, submission_status, result_status,
        ))

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    # --------------------------------------------------------
    # TERM-AWARE EXCEL
    # --------------------------------------------------------

    excel_payload = {
        "student_id": student_id,
        "full_name": full_name,
        "admission_number": admission_number,
        "sex": sex,

        "class_name": class_arm,
        "class": class_arm,
        "class_arm": class_arm,
        "class_category": class_level,
        "class_level": class_level,

        "stream": stream,
        "ss_stream": stream,

        "subject": subject,

        "score": score,
        "correct": correct,
        "incorrect": incorrect,
        "total": total,
        "answered": answered,
        "skipped": skipped,
        "flagged": flagged,
        "tab_switches": tab_switches,
        "time_taken": time_taken,

        "status": result_status,
        "result_status": result_status,
        "submission_status": submission_status,

        "submitted_at": submitted_at,

        "academic_session": academic_session,
        "term": term,
        "year": year,

        "date_written": date_written,
        "day_written": day_written,
        "time_written": time_written,
    }

    append_result_to_excel(excel_payload)

    return True


# ============================================================
# SQLITE ROW -> RESULT DICT
# ============================================================

def row_to_result(row):
    if row is None:
        return None

    data = dict(row)

    score = safe_int(data.get("score"))

    result_status = norm(data.get("result_status"))

    if result_status not in {"PASS", "FAIL"}:
        result_status = normalize_result_status(score)

    submission_status = norm(data.get("status")) or "COMPLETED"

    class_level = clean(data.get("class_level") or data.get("class_category"))
    class_arm = clean(data.get("class_arm") or data.get("class_name"))

    stored_term = normalize_result_term(data.get("term")) if is_jss_class(class_level) else ""

    return {
        "student_id": clean(data.get("student_id")),
        "id": clean(data.get("student_id") or data.get("admission_number")),

        "full_name": clean(data.get("full_name")),
        "admission_number": clean(data.get("admission_number")),

        "sex": normalize_sex(data.get("sex")),
        "gender": normalize_sex(data.get("sex")),

        "class_name": class_arm,
        "class": class_arm,

        "class_category": class_level,
        "class_level": class_level,
        "class_arm": class_arm,

        "stream": clean(data.get("stream")),
        "ss_stream": clean(data.get("stream")),

        "subject": clean(data.get("subject")),

        "score": score,
        "correct": safe_int(data.get("correct")),
        "incorrect": safe_int(data.get("incorrect")),
        "total": safe_int(data.get("total")),
        "answered": safe_int(data.get("answered")),
        "skipped": safe_int(data.get("skipped")),
        "flagged": safe_int(data.get("flagged")),

        "tabSwitches": safe_int(data.get("tab_switches")),
        "tab_switches": safe_int(data.get("tab_switches")),

        "time_taken": safe_int(data.get("time_taken")),

        "academic_session": clean(data.get("academic_session")),
        "term": stored_term,
        "term_label": term_label(stored_term) if stored_term else "",
        "year": clean(data.get("year")),

        "date_written": clean(data.get("date_written")),
        "day_written": clean(data.get("day_written")),
        "time_written": clean(data.get("time_written")),
        "submitted_at": clean(data.get("submitted_at")),

        "status": result_status,
        "result_status": result_status,
        "submission_status": submission_status,
    }


# ============================================================
# GET LATEST RESULT
# ============================================================

def get_latest_result(student_id):
    init_db()

    identifier = clean(student_id)

    if not identifier:
        return None

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(f"""
        SELECT {RESULT_COLUMNS}
        FROM student_results
        WHERE LOWER(TRIM(student_id)) = LOWER(TRIM(?))
           OR LOWER(TRIM(admission_number)) = LOWER(TRIM(?))
        ORDER BY id DESC
        LIMIT 1
    """, (identifier, identifier))

    row = cursor.fetchone()
    conn.close()

    return row_to_result(row)


# ============================================================
# GET ALL RESULTS
# ============================================================

def get_all_results(limit=500):
    init_db()

    limit = max(1, safe_int(limit, 500))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(f"SELECT {RESULT_COLUMNS} FROM student_results ORDER BY id DESC LIMIT ?", (limit,))

    rows = cursor.fetchall()
    conn.close()

    return [row_to_result(row) for row in rows]


# ============================================================
# GET RESULTS FOR ONE STUDENT
# ============================================================

def get_student_results(student_id, limit=200):
    init_db()

    identifier = clean(student_id)

    if not identifier:
        return []

    limit = max(1, safe_int(limit, 200))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(f"""
        SELECT {RESULT_COLUMNS}
        FROM student_results
        WHERE LOWER(TRIM(student_id)) = LOWER(TRIM(?))
           OR LOWER(TRIM(admission_number)) = LOWER(TRIM(?))
        ORDER BY id DESC
        LIMIT ?
    """, (identifier, identifier, limit))

    rows = cursor.fetchall()
    conn.close()

    return [row_to_result(row) for row in rows]


# ============================================================
# GET RESULTS BY CLASS
# ============================================================

def get_results_by_class(class_value, limit=1000):
    init_db()

    class_level = normalize_class_level(class_value)
    class_arm = normalize_class_arm(class_value, class_level)
    limit = max(1, safe_int(limit, 1000))

    conn = get_connection()
    cursor = conn.cursor()

    if class_arm and class_arm != class_level:
        cursor.execute(
            f"SELECT {RESULT_COLUMNS} FROM student_results WHERE UPPER(TRIM(class_arm)) = UPPER(TRIM(?)) ORDER BY id DESC LIMIT ?",
            (class_arm, limit),
        )
    else:
        cursor.execute(
            f"SELECT {RESULT_COLUMNS} FROM student_results WHERE UPPER(TRIM(class_level)) = UPPER(TRIM(?)) ORDER BY id DESC LIMIT ?",
            (class_level, limit),
        )

    rows = cursor.fetchall()
    conn.close()

    return [row_to_result(row) for row in rows]


# ============================================================
# ADMIN RESULT FILTERS
# ============================================================

def get_filtered_results(
    year="",
    academic_session="",
    term="",
    class_level="",
    class_arm="",
    sex="",
    stream="",
    subject="",
    status="",
    search="",
    limit=2000,
):
    init_db()

    clauses = []
    params = []

    year = clean(year)
    academic_session = clean(academic_session)

    class_level = normalize_class_level(class_level) if class_level else ""
    class_arm = normalize_class_arm(class_arm, class_level) if class_arm else ""

    sex = normalize_sex(sex)
    stream = norm(stream)
    subject = normalize_subject(subject) if subject else ""
    status = norm(status)
    search = clean(search)

    term = normalize_result_term(term) if term and term.lower() != "all" else ""

    if year:
        clauses.append("TRIM(COALESCE(year, '')) = ?")
        params.append(year)

    if academic_session:
        clauses.append("TRIM(COALESCE(academic_session, '')) = ?")
        params.append(academic_session)

    if term:
        clauses.append("UPPER(TRIM(COALESCE(term, ''))) = ?")
        params.append(term)

    if class_level:
        clauses.append("UPPER(TRIM(COALESCE(class_level, ''))) = ?")
        params.append(class_level.upper())

    if class_arm and class_arm != class_level:
        clauses.append("UPPER(TRIM(COALESCE(class_arm, ''))) = ?")
        params.append(class_arm.upper())

    if sex:
        clauses.append("UPPER(TRIM(COALESCE(sex, ''))) = ?")
        params.append(sex)

    if stream:
        clauses.append("UPPER(TRIM(COALESCE(stream, ''))) = ?")
        params.append(stream)

    if subject:
        clauses.append("UPPER(TRIM(COALESCE(subject, ''))) = ?")
        params.append(subject.upper())

    if status in {"PASS", "FAIL"}:
        clauses.append("UPPER(TRIM(COALESCE(result_status, ''))) = ?")
        params.append(status)

    if search:
        clauses.append("""
            (
                LOWER(full_name) LIKE LOWER(?)
                OR LOWER(admission_number) LIKE LOWER(?)
                OR LOWER(student_id) LIKE LOWER(?)
                OR LOWER(subject) LIKE LOWER(?)
                OR LOWER(class_arm) LIKE LOWER(?)
            )
        """)

        pattern = f"%{search}%"
        params.extend([pattern, pattern, pattern, pattern, pattern])

    where_clause = "WHERE " + " AND ".join(clauses) if clauses else ""

    limit = max(1, safe_int(limit, 2000))
    params.append(limit)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(f"""
        SELECT {RESULT_COLUMNS}
        FROM student_results
        {where_clause}
        ORDER BY id DESC
        LIMIT ?
    """, params)

    rows = cursor.fetchall()
    conn.close()

    return [row_to_result(row) for row in rows]


# ============================================================
# RESULT SUMMARY FOR ADMIN DASHBOARD
# ============================================================

def get_result_summary(results=None):
    if results is None:
        results = get_all_results(limit=10000)

    total = len(results)
    passed = sum(1 for result in results if result.get("result_status") == "PASS")
    failed = sum(1 for result in results if result.get("result_status") == "FAIL")

    average = round(sum(safe_int(result.get("score")) for result in results) / total, 2) if total else 0
    pass_rate = round((passed / total) * 100, 2) if total else 0

    return {
        "total": total,
        "submitted": total,
        "passed": passed,
        "failed": failed,
        "average_score": average,
        "pass_rate": pass_rate,
    }