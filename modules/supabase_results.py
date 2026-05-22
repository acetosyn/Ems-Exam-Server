# modules/supabase_results.py

import os
from datetime import datetime
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


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
        result.get("score_percent") or result.get("score") or 0,
        0
    )

    exam_score_70 = round((score_percent / 100) * 70, 2)
    return exam_score_70, score_percent


def save_exam_result_to_supabase(result: dict):
    now = datetime.now()

    exam_score_70, raw_percent = calculate_exam_score_70(result)

    payload = {
        "admission_number": str(result.get("admission_number", "")).strip(),
        "student_name": str(result.get("full_name", "")).strip(),

        "class_name": str(result.get("class_name", "")).upper().strip(),
        "class_category": str(result.get("class_category", "")).upper().strip(),

        "subject": str(result.get("subject", "")).upper().strip(),

        "session": str(result.get("academic_session", "")).strip(),
        "term": str(result.get("term", "")).upper().strip(),

        "academic_year": str(result.get("year", "")).strip(),

        "exam_score": exam_score_70,
        "raw_score_percent": raw_percent,
        "correct_answers": safe_int(result.get("correct")),
        "total_questions": safe_int(result.get("total")),
        "time_taken": str(result.get("time_taken") or result.get("timeTaken") or ""),

        "date_written": now.date().isoformat(),
        "day_written": now.strftime("%A"),
        "time_written": now.strftime("%I:%M %p"),
        "submitted_at": now.isoformat(),
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
            on_conflict="admission_number,class_name,class_category,subject,session,term"
        )
        .execute()
    )


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
        "current_session": str(session_value).strip(),
        "current_term": str(term_value).upper().strip(),
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