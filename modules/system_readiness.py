# MODULE: EMIS System Readiness — final Phase 10 cross-module health/readiness aggregator
# PURPOSE: Give Admin one compact, non-destructive view of database health, roster coverage,
#          assessment readiness, permanent-record storage and Local -> Deployed sync state.

import os
from pathlib import Path

from modules.academic_settings import get_academic_settings
from modules.assessment_rules import get_all_assessment_rules
from modules.class_config import STUDENT_DATABASE_CLASSES, TAHFEEZ_CLASSES
from modules.islamiyah_manager import get_islamiyah_roster_coverage
from modules.result_sync import SUPPORTED_EVENT_MODULES, sync_status_summary
from modules.school_structure import class_label
from modules.student_database.student_database import database_health_check, get_database_summary
from modules.subject_registry import get_registry_stats
from modules.tahfeez_database import tahfeez_database_health_check
from modules.teacher_assignment_manager import get_teacher_assignment_stats

BASE_DIR = Path(__file__).resolve().parent.parent
HISTORY_FILE = BASE_DIR / "static" / "data" / "academic_history" / "academic_records.jsonl"
HISTORY_REVISION_FILE = BASE_DIR / "static" / "data" / "academic_history" / "record_revisions.jsonl"
REPORT_SNAPSHOT_FILE = BASE_DIR / "static" / "data" / "report_sheets" / "generated_reports.jsonl"


def clean(value): return str(value or "").strip()


def _line_count(path):
    try:
        if not Path(path).exists(): return 0
        with Path(path).open("r", encoding="utf-8") as handle: return sum(1 for line in handle if line.strip())
    except Exception: return 0


def _safe(label, callback, default=None):
    try: return {"ok": True, "data": callback(), "error": ""}
    except Exception as error: return {"ok": False, "data": default, "error": f"{label}: {error}"}


def _assessment_summary():
    rules = get_all_assessment_rules(); ready, pending = [], []
    for key, rule in rules.items():
        item = {
            "key": key, "label": clean(rule.get("label")) or key,
            "status": clean(rule.get("status")), "entry_enabled": bool(rule.get("entry_enabled")),
            "ca_max": rule.get("ca_max"), "exam_max": rule.get("exam_max"), "total_max": rule.get("total_max"),
            "message": clean(rule.get("message")),
        }
        if key == "ISLAMIYAH" or item["entry_enabled"]: ready.append(item)
        else: pending.append(item)
    return {
        "rules": rules, "ready": ready, "pending": pending,
        "ready_count": len(ready), "pending_count": len(pending),
        "pending_keys": [row["key"] for row in pending],
        "fully_configured": not pending,
    }


def _history_summary():
    history_dir = HISTORY_FILE.parent; report_dir = REPORT_SNAPSHOT_FILE.parent
    history_dir.mkdir(parents=True, exist_ok=True); report_dir.mkdir(parents=True, exist_ok=True)
    return {
        "history_records": _line_count(HISTORY_FILE), "history_revisions": _line_count(HISTORY_REVISION_FILE),
        "report_snapshots": _line_count(REPORT_SNAPSHOT_FILE), "history_file_exists": HISTORY_FILE.exists(),
        "history_directory_writable": os.access(history_dir, os.W_OK), "report_directory_writable": os.access(report_dir, os.W_OK),
    }


def build_system_readiness():
    settings_result = _safe("Academic Settings", get_academic_settings, {})
    settings = settings_result.get("data") or {}; academic_session = clean(settings.get("current_session") or settings.get("academic_session") or settings.get("session"))

    student_result = _safe("Student database", database_health_check, {})
    student_summary_result = _safe("Student database summary", get_database_summary, {})
    tahfeez_result = _safe("Tahfeez database", tahfeez_database_health_check, {})
    islamiyah_result = _safe("Islamiyah roster", lambda: get_islamiyah_roster_coverage(academic_session), {}) if academic_session else {"ok": False, "data": {}, "error": "Academic session is not configured."}
    assessment_result = _safe("Assessment rules", _assessment_summary, {})
    subject_result = _safe("Subject Registry", get_registry_stats, {})
    teacher_result = _safe("Teacher assignments", lambda: get_teacher_assignment_stats(academic_session), {})
    history_result = _safe("Academic History", _history_summary, {})
    sync_result = _safe("Sync engine", sync_status_summary, {})

    student_health = student_result.get("data") or {}; student_summary = student_summary_result.get("data") or {}
    tahfeez_health = tahfeez_result.get("data") or {}; islamiyah = islamiyah_result.get("data") or {}
    assessments = assessment_result.get("data") or {}; subjects = subject_result.get("data") or {}; teachers = teacher_result.get("data") or {}
    history = history_result.get("data") or {}; sync = sync_result.get("data") or {}

    class_counts = [{"key": level, "label": class_label(level), "total": int((student_summary.get(level) or {}).get("total") or 0)} for level in STUDENT_DATABASE_CLASSES]
    tahfeez_counts = [{"key": level, "label": class_label(level), "total": int((((tahfeez_health.get("summary") or {}).get("classes") or {}).get(level) or {}).get("total") or 0)} for level in TAHFEEZ_CLASSES]

    blockers, warnings = [], []
    if not student_result.get("ok") or not student_health.get("healthy"): blockers.append("Regular student database needs attention.")
    if not tahfeez_result.get("ok") or not tahfeez_health.get("healthy"): blockers.append("Tahfeez placement database needs attention.")
    if not history_result.get("ok") or not history.get("history_directory_writable") or not history.get("report_directory_writable"): blockers.append("Academic record storage is not writable.")
    if islamiyah_result.get("ok") and islamiyah.get("sync_required"): warnings.append("Islamiyah roster is not fully synchronized with the current student database.")
    if not islamiyah_result.get("ok"): warnings.append(islamiyah_result.get("error") or "Islamiyah roster coverage could not be checked.")
    if int(assessments.get("pending_count") or 0): warnings.append("Starter/Nursery, Primary and/or Tahfeez assessment rules are still intentionally protected pending school-approved scoring rules.")
    if int(sync.get("failed") or 0): warnings.append(f"Sync queue has {int(sync.get('failed') or 0)} failed item(s).")
    if sync.get("sender_enabled") and not sync.get("sender_configured"): warnings.append("Local sync sender is enabled but not fully configured.")
    if sync.get("receiver_enabled") and not sync.get("receiver_configured"): warnings.append("Deployed sync receiver is enabled but not fully configured.")

    component_errors = [result.get("error") for result in [settings_result, student_result, student_summary_result, tahfeez_result, assessment_result, subject_result, teacher_result, history_result, sync_result] if not result.get("ok") and result.get("error")]
    warnings.extend(error for error in component_errors if error not in warnings)

    if blockers: status, label = "attention", "Attention Required"
    elif warnings: status, label = "ready_with_pending", "Core Ready • Protected Items Remain"
    else: status, label = "ready", "System Ready"

    return {
        "success": not blockers, "status": status, "status_label": label, "blockers": blockers, "warnings": warnings,
        "academic": {"session": academic_session, "term": clean(settings.get("current_term") or settings.get("term")), "year": clean(settings.get("current_year") or settings.get("year"))},
        "student_database": {**student_health, "configured_classes": len(STUDENT_DATABASE_CLASSES), "class_counts": class_counts},
        "tahfeez_database": {**tahfeez_health, "configured_classes": len(TAHFEEZ_CLASSES), "class_counts": tahfeez_counts},
        "islamiyah": islamiyah,
        "assessments": assessments,
        "subjects": subjects,
        "teachers": teachers,
        "history": history,
        "sync": {**sync, "supported_event_modules": sorted(SUPPORTED_EVENT_MODULES), "tahfeez_sync_supported": "tahfeez" in SUPPORTED_EVENT_MODULES},
        "architecture": {
            "regular_student_source": "static/data/database/students2026.csv",
            "tahfeez_source": "static/data/database/tahfeez2026.csv",
            "historical_source": "static/data/academic_history/academic_records.jsonl",
            "lower_school_scoring_protected": bool(assessments.get("pending_count")),
        },
    }
