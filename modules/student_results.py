# modules/student_results.py

import sqlite3
from pathlib import Path
from datetime import datetime

from modules.excel_manager import append_result_to_excel, normalize_result_term, result_term_label
from modules.class_config import normalize_class_level, normalize_class_arm, get_ss_stream


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
    submitted_at, status, result_status, termination_reason
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

    if value in {"TIMEOUT", "TIMED_OUT", "TIMED OUT", "TIME UP", "TIME_UP"}:
        return "TIMEOUT"

    if value in {"TERMINATED", "SECURITY_VIOLATION", "SECURITY VIOLATION", "VIOLATION", "DISQUALIFIED"}:
        return "TERMINATED"

    if value in {"PENDING", "IN_PROGRESS", "STARTED"}:
        return value

    return "COMPLETED"


def is_jss_class(value):
    return str(normalize_class_level(value) or "").upper().startswith("JSS")


def is_ss_class(value):
    return str(normalize_class_level(value) or "").upper().startswith("SS")


# ============================================================
# SUBJECT NORMALIZATION
# ============================================================

SUBJECT_MAP = {
    "FINANCIAL ACCOUNTING": "FINANCIAL ACCOUNTING", "FINANCIAL ACCOUNT": "FINANCIAL ACCOUNTING",
    "ACCOUNTS": "FINANCIAL ACCOUNTING", "ACCOUNTING": "FINANCIAL ACCOUNTING",

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

    "SOC. & CIT. STD": "SOC. & CIT. STD",
    "SOC & CIT STD": "SOC. & CIT. STD",
    "SOCIAL AND CITIZENSHIP STUDIES": "SOC. & CIT. STD",

    "CIT & HER. STD": "CIT & HER. STD",
    "CIT & HER STD": "CIT & HER. STD",
    "CIT AND HER STD": "CIT & HER. STD",

    "HORT & CROP PRODUCTION": "HORT & CROP PRODUCTION",
    "HORT AND CROP PRODUCTION": "HORT & CROP PRODUCTION",

    "ARABIC": "ARABIC LANGUAGE", "ARABIC LANGUAGE": "ARABIC LANGUAGE",

    "YORUBA": "YORUBA LANGUAGE", "YORUBA LANGUAGE": "YORUBA LANGUAGE",

    "HAUSA": "HAUSA LANGUAGE", "HAUSA LANGUAGE": "HAUSA LANGUAGE",

    "TECHNICAL": "TECHNICAL DRAWING", "TECHNICAL DRAWING": "TECHNICAL DRAWING",

    "LITERATURE-IN-ENGLISH": "LITERATURE",
    "LITERATURE IN ENGLISH": "LITERATURE",
    "LITERATURE": "LITERATURE",

    "IRK": "IRK", "IRS": "IRS",
    "CCA": "CCA", "BST": "BST", "PVS": "PVS",

    "MARKETTING": "MARKETING", "MARKETING": "MARKETING",

    "ECONOMICS": "ECONOMICS",
    "GOVERNMENT": "GOVERNMENT",
    "COMMERCE": "COMMERCE",
    "GEOGRAPHY": "GEOGRAPHY",

    "BIOLOGY": "BIOLOGY",
    "CHEMISTRY": "CHEMISTRY",
    "PHYSICS": "PHYSICS",

    "POISE": "POISE",
    "ISLAMIYYAH": "ISLAMIYYAH",
    "ISLAMIYAH": "ISLAMIYYAH",

    "GARMENT MAKING": "GARMENT MAKING",
    "BUSINESS STUDIES": "BUSINESS STUDIES",

    "NATIONAL VALUE": "NATIONAL VALUE",
    "NATIONAL VALUES": "NATIONAL VALUE",

    "HISTORY": "HISTORY",

    "INTER SCIENCE": "INTER SCIENCE",
    "INTEGRATED SCIENCE": "INTER SCIENCE",
}


def normalize_subject(name):
    value = norm(name)
    return SUBJECT_MAP.get(value, value) if value else "UNKNOWN"


# ============================================================
# DATABASE
# ============================================================

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def column_exists(cursor, table_name, column_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    return column_name in [row[1] for row in cursor.fetchall()]


def add_column_if_missing(cursor, table_name, column_name, column_type):
    if not column_exists(cursor, table_name, column_name):
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")


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
            result_status TEXT,
            termination_reason TEXT
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
        ("termination_reason", "TEXT"),
    ]

    for column_name, column_type in migrations:
        add_column_if_missing(cursor, "student_results", column_name, column_type)

    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_results_admission ON student_results(admission_number)",
        "CREATE INDEX IF NOT EXISTS idx_results_student ON student_results(student_id)",
        "CREATE INDEX IF NOT EXISTS idx_results_class_level ON student_results(class_level)",
        "CREATE INDEX IF NOT EXISTS idx_results_class_arm ON student_results(class_arm)",
        "CREATE INDEX IF NOT EXISTS idx_results_subject ON student_results(subject)",
        "CREATE INDEX IF NOT EXISTS idx_results_year ON student_results(year)",
        "CREATE INDEX IF NOT EXISTS idx_results_term ON student_results(term)",
        "CREATE INDEX IF NOT EXISTS idx_results_session_term ON student_results(academic_session, term)",
    ]

    for statement in indexes:
        cursor.execute(statement)

    cursor.execute("""
        UPDATE student_results
        SET result_status = CASE WHEN score >= ? THEN 'PASS' ELSE 'FAIL' END
        WHERE result_status IS NULL OR TRIM(result_status) = ''
    """, (PASS_MARK,))

    conn.commit()
    conn.close()


# ============================================================
# CLASS / SCORE META
# ============================================================

def resolve_class_meta(data):
    raw_arm = (
        data.get("class_arm")
        or data.get("class")
        or data.get("class_name")
        or data.get("class_category")
        or data.get("class_level")
    )

    raw_level = data.get("class_level") or data.get("class_category") or raw_arm

    class_level = normalize_class_level(raw_level)
    class_arm = normalize_class_arm(raw_arm, class_level)

    if not class_level:
        class_level = normalize_class_level(class_arm)

    if not class_arm:
        class_arm = class_level

    stream = norm(data.get("stream") or data.get("ss_stream") or get_ss_stream(class_arm) or "")

    if str(class_level or "").startswith("JSS"):
        stream = "GENERAL"

    return class_level, class_arm, stream


def calculate_score_percentage(data, correct, total):
    for key in ("score_percentage", "percentage", "Score (%)"):
        if data.get(key) not in (None, ""):
            return max(0, min(100, safe_int(data.get(key))))

    if total > 0 and ("correct" in data or "score" in data):
        raw_correct = correct if "correct" in data else safe_int(data.get("score"))
        return max(0, min(100, round((raw_correct / total) * 100)))

    return max(0, min(100, safe_int(data.get("score"))))


# ============================================================
# DUPLICATE CHECK
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
# SAVE RESULT
# ============================================================

def save_result(data):
    init_db()
    now = datetime.now()

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

    subject = normalize_subject(data.get("subject"))
    year = clean(data.get("year") or now.year)
    academic_session = clean(data.get("academic_session") or data.get("session"))

    class_level, class_arm, stream = resolve_class_meta(data)

    if not class_level:
        raise ValueError("Student class level is required.")

    raw_term = clean(data.get("term"))
    term = normalize_result_term(raw_term)

    # JSS = strict term.
    # SS = hybrid term: FIRST/SECOND/THIRD when selected, blank for General.
    if is_jss_class(class_level) and not term:
        raise ValueError(f"Term is required for JSS result: {class_level} / {subject}")

    if raw_term and not term:
        raise ValueError(f"Invalid result term: {raw_term}")

    data["term"] = term
    data["term_label"] = result_term_label(term) if term else ""
    data["class_level"] = class_level
    data["class_category"] = class_level
    data["class_arm"] = class_arm
    data["class"] = class_arm

    total = max(safe_int(data.get("total")), 0)
    correct = max(safe_int(data.get("correct", data.get("score"))), 0)
    answered = max(safe_int(data.get("answered")), 0)

    if total > 0:
        correct = min(correct, total)
        answered = min(answered, total)

    score = calculate_score_percentage(data, correct, total)

    incorrect_default = max(answered - correct, 0)
    skipped_default = max(total - answered, 0)

    incorrect = max(safe_int(data.get("incorrect"), incorrect_default), 0)
    skipped = max(safe_int(data.get("skipped"), skipped_default), 0)

    flagged = max(safe_int(data.get("flagged")), 0)
    tab_switches = max(safe_int(data.get("tabSwitches") or data.get("tab_switches")), 0)
    time_taken = max(safe_int(data.get("time_taken") or data.get("timeTaken")), 0)

    submission_status = normalize_submission_status(
        data.get("submission_status")
        or data.get("status")
        or "COMPLETED"
    )

    result_status = normalize_result_status(score)

    termination_reason = clean(
        data.get("termination_reason")
        or data.get("security_reason")
        or data.get("violation_reason")
    )

    submitted_at = clean(
        data.get("submitted_at")
        or data.get("submittedAt")
        or now.strftime("%Y-%m-%d %H:%M:%S")
    )

    date_written = clean(data.get("date_written") or now.strftime("%Y-%m-%d"))
    day_written = clean(data.get("day_written") or now.strftime("%A"))
    time_written = clean(data.get("time_written") or now.strftime("%I:%M %p"))

    if result_exists(
        admission_number=admission_number,
        subject=subject,
        year=year,
        academic_session=academic_session,
        term=term,
    ):
        return False

    conn = get_connection()
    cursor = conn.cursor()

    inserted_id = None

    try:
        cursor.execute("""
            INSERT INTO student_results (
                student_id, full_name, admission_number, sex,
                class_name, class_category, class_arm, class_level, stream,
                subject, score, correct, incorrect, total, answered, skipped, flagged, tab_switches, time_taken,
                academic_session, term, year,
                date_written, day_written, time_written,
                submitted_at, status, result_status, termination_reason
            )
            VALUES (
                ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?
            )
        """, (
            student_id, full_name, admission_number, sex,

            class_arm, class_level, class_arm, class_level, stream,

            subject, score, correct, incorrect, total, answered, skipped, flagged, tab_switches, time_taken,

            academic_session, term, year,

            date_written, day_written, time_written,

            submitted_at, submission_status, result_status, termination_reason,
        ))

        inserted_id = cursor.lastrowid

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

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
        "score_percentage": score,

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
        "termination_reason": termination_reason,

        "submitted_at": submitted_at,

        "academic_session": academic_session,
        "term": term,
        "year": year,

        "date_written": date_written,
        "day_written": day_written,
        "time_written": time_written,
    }

    try:
        append_result_to_excel(excel_payload)

    except Exception:
        # If Excel fails, remove the newly inserted SQLite row.
        # This keeps both result stores synchronized and allows retry.
        if inserted_id:
            cleanup = get_connection()

            try:
                cleanup.execute(
                    "DELETE FROM student_results WHERE id = ?",
                    (inserted_id,),
                )

                cleanup.commit()

            finally:
                cleanup.close()

        raise

    return True


# ============================================================
# ROW CONVERSION
# ============================================================

def row_to_result(row):
    if row is None:
        return None

    data = dict(row)

    score = safe_int(data.get("score"))

    result_status = norm(data.get("result_status"))

    if result_status not in {"PASS", "FAIL"}:
        result_status = normalize_result_status(score)

    submission_status = normalize_submission_status(data.get("status"))

    class_level = clean(data.get("class_level") or data.get("class_category"))
    class_arm = clean(data.get("class_arm") or data.get("class_name"))

    # IMPORTANT: preserve SS term too.
    stored_term = normalize_result_term(data.get("term"))

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
        "term_label": result_term_label(stored_term) if stored_term else "",

        "year": clean(data.get("year")),

        "date_written": clean(data.get("date_written")),
        "day_written": clean(data.get("day_written")),
        "time_written": clean(data.get("time_written")),

        "submitted_at": clean(data.get("submitted_at")),

        "status": result_status,
        "result_status": result_status,

        "submission_status": submission_status,
        "termination_reason": clean(data.get("termination_reason")),
    }


# ============================================================
# RESULT QUERIES
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


def get_all_results(limit=500):
    init_db()

    limit = max(1, safe_int(limit, 500))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        f"SELECT {RESULT_COLUMNS} FROM student_results ORDER BY id DESC LIMIT ?",
        (limit,),
    )

    rows = cursor.fetchall()

    conn.close()

    return [row_to_result(row) for row in rows]


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

def get_filtered_results(year="", academic_session="", term="", class_level="", class_arm="", sex="", stream="", subject="", status="", search="", limit=2000):
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

    term = normalize_result_term(term) if term and str(term).lower() != "all" else ""

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

    elif status in {"COMPLETED", "TIMEOUT", "TERMINATED", "PENDING", "IN_PROGRESS", "STARTED"}:
        clauses.append("UPPER(TRIM(COALESCE(status, ''))) = ?")
        params.append(status)

    if search:
        clauses.append("""
            (
                LOWER(COALESCE(full_name, '')) LIKE LOWER(?)
                OR LOWER(COALESCE(admission_number, '')) LIKE LOWER(?)
                OR LOWER(COALESCE(student_id, '')) LIKE LOWER(?)
                OR LOWER(COALESCE(subject, '')) LIKE LOWER(?)
                OR LOWER(COALESCE(class_arm, '')) LIKE LOWER(?)
                OR LOWER(COALESCE(termination_reason, '')) LIKE LOWER(?)
            )
        """)

        pattern = f"%{search}%"

        params.extend([
            pattern,
            pattern,
            pattern,
            pattern,
            pattern,
            pattern,
        ])

    where_clause = "WHERE " + " AND ".join(clauses) if clauses else ""

    limit = max(1, safe_int(limit, 2000))
    params.append(limit)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        f"""
        SELECT {RESULT_COLUMNS}
        FROM student_results
        {where_clause}
        ORDER BY id DESC
        LIMIT ?
        """,
        params,
    )

    rows = cursor.fetchall()

    conn.close()

    return [row_to_result(row) for row in rows]


# ============================================================
# RESULT SUMMARY
# ============================================================

def get_result_summary(results=None):
    results = results if results is not None else get_all_results(limit=10000)

    total = len(results)
    passed = sum(1 for result in results if result.get("result_status") == "PASS")
    failed = sum(1 for result in results if result.get("result_status") == "FAIL")

    average = round(
        sum(safe_int(result.get("score")) for result in results) / total,
        2,
    ) if total else 0

    pass_rate = round(
        (passed / total) * 100,
        2,
    ) if total else 0

    return {
        "total": total,
        "submitted": total,
        "passed": passed,
        "failed": failed,
        "average_score": average,
        "pass_rate": pass_rate,
    }