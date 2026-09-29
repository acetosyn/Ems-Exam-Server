# MODULE: Teacher Assignment Routes — Phase 3 Admin assignment APIs + Teacher self-view

from flask import Blueprint, jsonify, request, session

from modules.admin_routes import admin_only, teacher_allowed
from modules.result_sync import queue_emis_event_safely
from modules.teacher_assignment_manager import build_teacher_assignment_sync_payload, get_teacher, get_teacher_assignment_config, get_teacher_assignments, get_teacher_assignment_stats, list_teachers_with_assignment_summary, normalize_assignment_session, replace_teacher_assignments, update_teacher_profile


teacher_assignment_bp = Blueprint("teacher_assignment_bp", __name__)


def _payload():
    value = request.get_json(silent=True)
    return value if isinstance(value, dict) else {}


def _queue_snapshot(teacher_id, academic_session):
    try:
        payload = build_teacher_assignment_sync_payload(teacher_id, academic_session); entity_key = f"{payload['teacher_id']}|{payload['academic_session']}"
        return queue_emis_event_safely("teacher_assignments", "replace_teacher_session", payload, entity_key=entity_key)
    except Exception as error:
        print("[TEACHER ASSIGNMENTS] Sync queue warning:", error)
        return {"queued": False, "status": "QUEUE_ERROR", "error": str(error)}


@teacher_assignment_bp.get("/api/teacher-assignments/config")
@teacher_allowed
def teacher_assignment_config():
    try:
        role = str(session.get("user_type") or "").lower().strip(); requested_session = request.args.get("academic_session", "")
        config = get_teacher_assignment_config(requested_session, include_teachers=role == "admin")
        if role == "teacher":
            teacher_id = str(session.get("teacher_id") or session.get("username") or "").strip(); config["teacher"] = get_teacher(teacher_id); config["assignments"] = get_teacher_assignments(teacher_id, config["academic_session"])
        return jsonify({"success": True, "role": role, **config})
    except ValueError as error: return jsonify({"success": False, "error": str(error)}), 400
    except Exception as error:
        print("[TEACHER ASSIGNMENTS] Config failed:", error); return jsonify({"success": False, "error": "Unable to load Teacher Assignment configuration."}), 500


@teacher_assignment_bp.get("/api/teacher-assignments/teachers")
@admin_only
def teacher_assignment_teachers():
    try:
        academic_session = normalize_assignment_session(request.args.get("academic_session", "")); teachers = list_teachers_with_assignment_summary(academic_session)
        return jsonify({"success": True, "academic_session": academic_session, "teachers": teachers, "stats": get_teacher_assignment_stats(academic_session)})
    except ValueError as error: return jsonify({"success": False, "error": str(error)}), 400


@teacher_assignment_bp.get("/api/teacher-assignments/teachers/<teacher_id>")
@admin_only
def teacher_assignment_teacher_detail(teacher_id):
    try:
        academic_session = normalize_assignment_session(request.args.get("academic_session", "")); teacher = get_teacher(teacher_id)
        if not teacher: return jsonify({"success": False, "error": "Teacher account not found."}), 404
        return jsonify({"success": True, "academic_session": academic_session, "teacher": teacher, "assignments": get_teacher_assignments(teacher_id, academic_session)})
    except ValueError as error: return jsonify({"success": False, "error": str(error)}), 400


@teacher_assignment_bp.patch("/api/teacher-assignments/teachers/<teacher_id>")
@admin_only
def teacher_assignment_teacher_profile(teacher_id):
    payload = _payload()
    try:
        teacher = update_teacher_profile(teacher_id, full_name=payload.get("full_name") if "full_name" in payload else None, status=payload.get("status") if "status" in payload else None)
        return jsonify({"success": True, "message": "Teacher profile updated successfully.", "teacher": teacher})
    except ValueError as error: return jsonify({"success": False, "error": str(error)}), 400
    except Exception as error:
        print("[TEACHER ASSIGNMENTS] Teacher update failed:", error); return jsonify({"success": False, "error": "Unable to update the teacher profile."}), 500


@teacher_assignment_bp.put("/api/teacher-assignments/teachers/<teacher_id>/assignments")
@admin_only
def teacher_assignment_replace(teacher_id):
    payload = _payload()
    try:
        academic_session = normalize_assignment_session(payload.get("academic_session")); assignments = replace_teacher_assignments(teacher_id, payload.get("assignments") or [], academic_session, changed_by=session.get("username") or "EMIS Admin")
        sync_info = _queue_snapshot(teacher_id, academic_session)
        return jsonify({"success": True, "message": "Teacher assignments saved successfully.", "academic_session": academic_session, "teacher": get_teacher(teacher_id), "assignments": assignments, "stats": get_teacher_assignment_stats(academic_session), "sync": sync_info})
    except ValueError as error: return jsonify({"success": False, "error": str(error)}), 400
    except Exception as error:
        print("[TEACHER ASSIGNMENTS] Save failed:", error); return jsonify({"success": False, "error": "Unable to save teacher assignments."}), 500


@teacher_assignment_bp.get("/api/teacher-assignments/mine")
@teacher_allowed
def teacher_assignment_mine():
    if str(session.get("user_type") or "").lower().strip() != "teacher": return jsonify({"success": False, "error": "Teacher account required."}), 403
    try:
        teacher_id = str(session.get("teacher_id") or session.get("username") or "").strip(); academic_session = normalize_assignment_session(request.args.get("academic_session", "")); assignments = get_teacher_assignments(teacher_id, academic_session)
        return jsonify({"success": True, "academic_session": academic_session, "teacher": get_teacher(teacher_id), "assignments": assignments, "assignment_count": len(assignments), "class_count": len({(row.get('class_level'), row.get('class_arm')) for row in assignments}), "subject_count": len({row.get('subject_key') for row in assignments})})
    except ValueError as error: return jsonify({"success": False, "error": str(error)}), 400
