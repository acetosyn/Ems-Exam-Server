# modules/supabase_results.py

import os
from datetime import datetime
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    raise RuntimeError(
        "Supabase credentials are missing. "
        "Check SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in your .env"
    )

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


# ============================================================
# SAFE CONVERSIONS
# ============================================================
def safe_float(value, default=0):
    try:
        return float(value)
    except Exception:
        return default


def safe_int(value, default=0):
    try:
        return int(float(value))
    except Exception:
        return default


def safe_text(value, default=""):
    if value is None:
        return default
    return str(value).strip()


def safe_upper(value, default=""):
    return safe_text(value, default).upper().strip()


# ============================================================
# SCORE CALCULATION
# ============================================================
def calculate_exam_score_70(result: dict):
    """
    Report sheet EXAM column is over 70.

    CBT sends:
      correct = number of correct answers
      total   = total questions

    Example:
      correct 40 / total 50 = 80%
      80% of 70 = 56/70
    """
    correct = safe_float(result.get("correct"), 0)
    total = safe_float(result.get("total"), 0)

    if total > 0:
        raw_percent = round((correct / total) * 100, 2)
        exam_score_70 = round((correct / total) * 70, 2)
        return exam_score_70, raw_percent

    score_percent = safe_float(
        result.get("score_percent")
        or result.get("raw_score_percent")
        or result.get("score")
        or 0,
        0
    )

    exam_score_70 = round((score_percent / 100) * 70, 2)
    return exam_score_70, score_percent


# ============================================================
# SAVE CBT EXAM RESULT TO SUPABASE
# ============================================================
def save_exam_result_to_supabase(result: dict):
    """
    Saves CBT result into Supabase exam_results table.

    Important naming:
      session      = school academic session, e.g. 2025/2026
      term         = school term, e.g. SECOND TERM
      exam_year    = question/past-question year pushed to student portal, e.g. 2017

    Staff Management Software will fetch exam_score /70 and combine it
    with CA/Test scores for final report generation.
    """

    now = datetime.now()

    exam_score_70, raw_percent = calculate_exam_score_70(result)

    submitted_at = (
        result.get("submitted_at")
        or result.get("submittedAt")
        or now.isoformat()
    )

    date_written = (
        result.get("date_written")
        or now.date().isoformat()
    )

    day_written = (
        result.get("day_written")
        or now.strftime("%A")
    )

    time_written = (
        result.get("time_written")
        or now.strftime("%I:%M %p")
    )

    student_id = safe_text(
        result.get("student_id")
        or result.get("id")
        or result.get("admission_number")
    )

    payload = {
        "student_id": student_id,

        "admission_number": safe_text(result.get("admission_number")),
        "student_name": safe_text(
            result.get("full_name")
            or result.get("student_name")
            or result.get("name")
        ),

        "class_name": safe_upper(result.get("class_name")),
        "class_category": safe_upper(result.get("class_category")),

        "subject": safe_upper(result.get("subject")),

        "session": safe_text(
            result.get("academic_session")
            or result.get("session")
        ),

        "term": safe_upper(result.get("term")),

        # This is the question/past-question year, not school session.
        "exam_year": safe_text(
            result.get("exam_year")
            or result.get("question_year")
            or result.get("year")
        ),

        "exam_name": safe_text(
            result.get("exam_name")
            or result.get("exam_type")
            or "CBT EXAM"
        ).upper(),

        "exam_score": exam_score_70,
        "raw_score_percent": raw_percent,

        "correct_answers": safe_int(result.get("correct")),
        "total_questions": safe_int(result.get("total")),

        "time_taken": safe_text(
            result.get("time_taken")
            or result.get("timeTaken")
        ),

        "attempt_no": safe_int(
            result.get("attempt_no")
            or result.get("attempt")
            or 1,
            1
        ),

        "status": safe_upper(
            result.get("status")
            or "COMPLETED"
        ),

        "date_written": date_written,
        "day_written": safe_text(day_written),
        "time_written": safe_text(time_written),
        "submitted_at": submitted_at,
        "updated_at": now.isoformat(),
    }

    if not payload["admission_number"]:
        raise ValueError("Missing admission_number")

    if not payload["subject"]:
        raise ValueError("Missing subject")

    if not payload["session"]:
        raise ValueError("Missing academic session")

    if not payload["term"]:
        raise ValueError("Missing term")

    return (
        supabase.table("exam_results")
        .upsert(
            payload,
            on_conflict=(
                "admission_number,"
                "class_name,"
                "class_category,"
                "subject,"
                "session,"
                "term,"
                "exam_year,"
                "exam_name,"
                "attempt_no"
            )
        )
        .execute()
    )


# ============================================================
# ACADEMIC SETTINGS
# ============================================================
def get_academic_settings():
    response = (
        supabase.table("academic_settings")
        .select("*")
        .limit(1)
        .execute()
    )

    if response.data:
        return response.data[0]

    return {
        "current_session": "2025/2026",
        "current_term": "SECOND TERM"
    }


def update_academic_settings(session_value, term_value):
    current = get_academic_settings()

    payload = {
        "current_session": safe_text(session_value),
        "current_term": safe_upper(term_value),
        "updated_at": datetime.now().isoformat(),
    }

    if not current.get("id"):
        return (
            supabase.table("academic_settings")
            .insert(payload)
            .execute()
        )

    return (
        supabase.table("academic_settings")
        .update(payload)
        .eq("id", current["id"])
        .execute()
    )