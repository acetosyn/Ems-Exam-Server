# MODULE: Subject Manager — Admin-only APIs for the Phase 2 dynamic subject catalogue and class assignments

from flask import Blueprint, jsonify, request

from modules.admin_routes import admin_only
from modules.subject_registry import build_subject_sync_payload, create_subject, get_registry_stats, get_subject_manager_config, list_subjects, save_subject_configuration, set_subject_assignments, set_subject_status, update_subject
from modules.result_sync import queue_emis_event_safely


subject_manager_bp = Blueprint("subject_manager_bp", __name__)


def _json_payload():
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else {}


def _subject_with_assignments(subject_id):
    token = str(subject_id or "").upper().strip()
    return next((row for row in list_subjects() if str(row.get("id") or "").upper() == token), None)


def _queue_subject_sync(subject_id):
    try:
        payload = build_subject_sync_payload(subject_id); stable_id = str(payload.get("subject", {}).get("id") or subject_id).strip()
        return queue_emis_event_safely("subject_registry", "upsert_subject", payload, entity_key=stable_id)
    except Exception as error:
        print("[SUBJECT MANAGER] Subject sync queue warning:", error)
        return {"queued": False, "status": "QUEUE_ERROR", "error": str(error)}


@subject_manager_bp.get("/api/subject-manager/config")
@admin_only
def subject_manager_config():
    config = get_subject_manager_config(); config["subjects"] = list_subjects()
    return jsonify({"success": True, **config})


@subject_manager_bp.get("/api/subject-manager/subjects")
@admin_only
def subject_manager_subjects():
    section = request.args.get("section", ""); class_level = request.args.get("class_level", ""); status = str(request.args.get("status", "all") or "all").lower().strip()
    active = True if status == "active" else False if status == "inactive" else None
    subjects = list_subjects(section=section, class_level=class_level, active=active)
    return jsonify({"success": True, "subjects": subjects, "count": len(subjects), "stats": get_registry_stats()})


@subject_manager_bp.post("/api/subject-manager/subjects")
@admin_only
def subject_manager_create():
    payload = _json_payload()
    try:
        subject = create_subject(payload.get("name"), assignments=payload.get("assignments") or [], source="admin")
        if "active" in payload and not bool(payload.get("active")): subject = update_subject(subject.get("id"), active=False)
        sync_info = _queue_subject_sync(subject.get("id"))
        return jsonify({"success": True, "message": "Subject created successfully.", "subject": _subject_with_assignments(subject.get("id")), "stats": get_registry_stats(), "sync": sync_info}), 201
    except ValueError as error:
        return jsonify({"success": False, "error": str(error)}), 400
    except Exception as error:
        print("[SUBJECT MANAGER] Create failed:", error)
        return jsonify({"success": False, "error": "Unable to create the subject."}), 500


@subject_manager_bp.put("/api/subject-manager/subjects/<subject_id>")
@admin_only
def subject_manager_update(subject_id):
    payload = _json_payload()
    try:
        subject = save_subject_configuration(subject_id, name=payload.get("name") if "name" in payload else None, active=payload.get("active") if "active" in payload else None, assignments=payload.get("assignments") if "assignments" in payload else None)
        sync_info = _queue_subject_sync(subject.get("id"))
        return jsonify({"success": True, "message": "Subject updated successfully.", "subject": _subject_with_assignments(subject.get("id")), "stats": get_registry_stats(), "sync": sync_info})
    except ValueError as error:
        return jsonify({"success": False, "error": str(error)}), 400
    except Exception as error:
        print("[SUBJECT MANAGER] Update failed:", error)
        return jsonify({"success": False, "error": "Unable to update the subject."}), 500


@subject_manager_bp.put("/api/subject-manager/subjects/<subject_id>/assignments")
@admin_only
def subject_manager_assignments(subject_id):
    payload = _json_payload()
    try:
        set_subject_assignments(subject_id, payload.get("assignments") or [])
        sync_info = _queue_subject_sync(subject_id)
        return jsonify({"success": True, "message": "Class assignments updated successfully.", "subject": _subject_with_assignments(subject_id), "stats": get_registry_stats(), "sync": sync_info})
    except ValueError as error:
        return jsonify({"success": False, "error": str(error)}), 400
    except Exception as error:
        print("[SUBJECT MANAGER] Assignment update failed:", error)
        return jsonify({"success": False, "error": "Unable to update subject assignments."}), 500


@subject_manager_bp.patch("/api/subject-manager/subjects/<subject_id>/status")
@admin_only
def subject_manager_status(subject_id):
    payload = _json_payload()
    if "active" not in payload: return jsonify({"success": False, "error": "The active status is required."}), 400
    try:
        subject = set_subject_status(subject_id, active=bool(payload.get("active")))
        sync_info = _queue_subject_sync(subject.get("id"))
        return jsonify({"success": True, "message": "Subject status updated successfully.", "subject": _subject_with_assignments(subject.get("id")), "stats": get_registry_stats(), "sync": sync_info})
    except ValueError as error:
        return jsonify({"success": False, "error": str(error)}), 400
    except Exception as error:
        print("[SUBJECT MANAGER] Status update failed:", error)
        return jsonify({"success": False, "error": "Unable to update the subject status."}), 500
