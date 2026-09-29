# MODULE: Islamiyah School Routes — staff UI APIs for roster placement, CA /30 + Exam /70 autosave, history and export

from functools import wraps
from io import BytesIO
from datetime import datetime

from flask import Blueprint, jsonify, request, session, send_file
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment

from modules.academic_records import clean, normalize_academic_session, normalize_academic_term, get_current_academic_context
from modules.school_structure import ISLAMIYAH_CLASS_LEVELS
from modules.teacher_assignment_manager import get_teacher_assignments
from modules.result_sync import queue_emis_event_safely
from modules.islamiyah_manager import CA_MAX, EXAM_MAX, TOTAL_MAX, assign_students, build_enrollment_sync_payload, build_score_scope_sync_payload, get_class_result_summary, get_enrollment, get_islamiyah_dashboard, get_score_entry_roster, get_score_records, get_student_history, import_current_student_database, islamiyah_class_label, islamiyah_subject_rows, list_enrollments, normalize_islamiyah_class, normalize_islamiyah_session, save_student_score


islamiyah_bp = Blueprint("islamiyah_bp", __name__)


def _payload():
    value = request.get_json(silent=True); return value if isinstance(value, dict) else {}


def _role(): return clean(session.get("user_type")).lower()
def _teacher_id(): return clean(session.get("teacher_id") or session.get("username"))
def _staff_name(): return clean(session.get("admin_username") or session.get("username") or session.get("teacher_id") or "Staff")


def islamiyah_staff_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if _role() not in {"admin", "teacher"}: return jsonify({"success": False, "message": "Unauthorized."}), 403
        return view(*args, **kwargs)
    return wrapped


def islamiyah_admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if _role() != "admin": return jsonify({"success": False, "message": "Admin privileges are required for Islamiyah roster placement."}), 403
        return view(*args, **kwargs)
    return wrapped


def _resolve_context(session_value="", term_value=""):
    context = get_current_academic_context(session_value, term_value); session_value = normalize_academic_session(context.get("academic_session") or context.get("session")); term = normalize_academic_term(context.get("term"))
    return session_value, term


def _teacher_access(academic_session):
    if _role() == "admin": return {level: {row["key"] for row in islamiyah_subject_rows(level)} for level in ISLAMIYAH_CLASS_LEVELS}
    assignments = get_teacher_assignments(_teacher_id(), academic_session); access = {}
    for row in assignments:
        level = clean(row.get("class_level")).upper()
        if level not in ISLAMIYAH_CLASS_LEVELS and clean(row.get("school_section")).upper() != "ISLAMIYAH": continue
        if level in ISLAMIYAH_CLASS_LEVELS: access.setdefault(level, set()).add(clean(row.get("subject_key")).upper())
    return access


def _ensure_access(academic_session, class_level="", subject=""):
    access = _teacher_access(academic_session)
    if _role() == "admin": return access, ""
    if not access: return access, "No Islamiyah teaching load is assigned to this Teacher for the selected academic session."
    if class_level:
        level = normalize_islamiyah_class(class_level)
        if level not in access: return access, f"You are not assigned to {islamiyah_class_label(level)}."
        if subject:
            wanted = clean(subject).upper(); rows = islamiyah_subject_rows(level); key = next((row["key"] for row in rows if wanted in {clean(row["key"]).upper(), clean(row["name"]).upper(), clean(row["id"]).upper()}), wanted)
            if key not in access.get(level, set()): return access, f"You are not assigned to {next((row['name'] for row in rows if row['key'] == key), subject)} in {islamiyah_class_label(level)}."
    return access, ""


def _queue_enrollment_snapshot(academic_session):
    try:
        payload = build_enrollment_sync_payload(academic_session); return queue_emis_event_safely("islamiyah", "replace_session_enrollments", payload, entity_key=f"enrollments|{payload['session']}")
    except Exception as error:
        print("[ISLAMIYAH] Enrollment sync warning:", error); return {"queued": False, "status": "QUEUE_ERROR", "error": str(error)}


def _queue_score_scope(academic_session, term, islamiyah_class, subject):
    try:
        payload = build_score_scope_sync_payload(academic_session, term, islamiyah_class, subject); entity_key = "|".join(["scores", payload["session"], payload["term"], payload["islamiyah_class"], payload["subject_key"]])
        return queue_emis_event_safely("islamiyah", "replace_score_scope", payload, entity_key=entity_key)
    except Exception as error:
        print("[ISLAMIYAH] Score sync warning:", error); return {"queued": False, "status": "QUEUE_ERROR", "error": str(error)}


@islamiyah_bp.get("/api/islamiyah/config")
@islamiyah_staff_required
def api_islamiyah_config():
    try:
        academic_session, term = _resolve_context(request.args.get("session"), request.args.get("term")); session_value = normalize_islamiyah_session(academic_session); access, access_error = _ensure_access(session_value)
        classes = []
        for level in ISLAMIYAH_CLASS_LEVELS:
            subjects = islamiyah_subject_rows(level); allowed_keys = access.get(level, set()) if _role() == "teacher" else {row["key"] for row in subjects}; visible = [row for row in subjects if row["key"] in allowed_keys]
            if _role() == "teacher" and level not in access: continue
            classes.append({"key": level, "label": islamiyah_class_label(level), "subjects": visible, "subject_count": len(visible)})
        dashboard = get_islamiyah_dashboard(session_value, term); roster_imported = dashboard.get("roster_count", 0) > 0
        return jsonify({"success": True, "role": _role(), "academic_session": session_value, "term": term, "classes": classes, "assessment": {"ca_max": CA_MAX, "exam_max": EXAM_MAX, "total_max": TOTAL_MAX}, "dashboard": dashboard, "roster_imported": roster_imported, "can_manage_roster": _role() == "admin", "teacher_has_access": bool(access), "access_message": access_error})
    except ValueError as error: return jsonify({"success": False, "message": str(error)}), 400
    except Exception as error:
        print("[ISLAMIYAH] Config failed:", error); return jsonify({"success": False, "message": "Unable to load Islamiyah School configuration."}), 500


@islamiyah_bp.get("/api/islamiyah/dashboard")
@islamiyah_staff_required
def api_islamiyah_dashboard():
    try:
        academic_session, term = _resolve_context(request.args.get("session"), request.args.get("term")); session_value = normalize_islamiyah_session(academic_session); access, error = _ensure_access(session_value)
        if _role() == "teacher" and error and not access: return jsonify({"success": True, "dashboard": get_islamiyah_dashboard(session_value, term), "allowed_classes": [], "message": error})
        dashboard = get_islamiyah_dashboard(session_value, term)
        if _role() == "teacher": dashboard["classes"] = [row for row in dashboard.get("classes", []) if row.get("key") in access]; dashboard["class_counts"] = {key: value for key, value in dashboard.get("class_counts", {}).items() if key in access}
        return jsonify({"success": True, "dashboard": dashboard, "allowed_classes": list(access)})
    except ValueError as error: return jsonify({"success": False, "message": str(error)}), 400


@islamiyah_bp.get("/api/islamiyah/roster")
@islamiyah_staff_required
def api_islamiyah_roster():
    try:
        academic_session, _ = _resolve_context(request.args.get("session"), request.args.get("term")); session_value = normalize_islamiyah_session(academic_session); requested_class = clean(request.args.get("islamiyah_class")); access, error = _ensure_access(session_value, requested_class) if requested_class else _ensure_access(session_value)
        if error and _role() == "teacher" and (requested_class or not access): return jsonify({"success": False, "message": error, "students": []}), 403
        students = list_enrollments(session_value, requested_class, request.args.get("regular_class", ""), active_only=True, search=request.args.get("search", ""))
        if _role() == "teacher" and not requested_class: students = [student for student in students if student.get("islamiyah_class") in access]
        return jsonify({"success": True, "session": session_value, "students": students, "count": len(students), "assigned": sum(1 for row in students if row.get("islamiyah_class")), "unassigned": sum(1 for row in students if not row.get("islamiyah_class")), "can_manage_roster": _role() == "admin"})
    except ValueError as error: return jsonify({"success": False, "message": str(error), "students": []}), 400


@islamiyah_bp.post("/api/islamiyah/roster/import")
@islamiyah_admin_required
def api_islamiyah_roster_import():
    data = _payload()
    try:
        academic_session, _ = _resolve_context(data.get("session"), data.get("term")); result = import_current_student_database(academic_session, _staff_name()); result["sync"] = _queue_enrollment_snapshot(result["session"])
        return jsonify({"success": True, "message": f"Current school database synchronized into Islamiyah School — {result['count']} active student(s), {result['assigned']} assigned, {result['unassigned']} awaiting Islamiyah placement.", **result})
    except ValueError as error: return jsonify({"success": False, "message": str(error)}), 400
    except Exception as error:
        print("[ISLAMIYAH] Roster import failed:", error); return jsonify({"success": False, "message": "Unable to synchronize the school database into Islamiyah School."}), 500


@islamiyah_bp.put("/api/islamiyah/roster/assign")
@islamiyah_admin_required
def api_islamiyah_roster_assign():
    data = _payload()
    try:
        result = assign_students(data.get("session"), data.get("admission_numbers") or data.get("students") or [], data.get("islamiyah_class", ""), _staff_name()); result["sync"] = _queue_enrollment_snapshot(result["session"])
        message = f"{result['updated']} student(s) assigned to {result['islamiyah_class_label']}." if result.get("islamiyah_class") else f"{result['updated']} student(s) returned to Unassigned."
        return jsonify({"success": True, "message": message, **result})
    except ValueError as error: return jsonify({"success": False, "message": str(error)}), 400
    except Exception as error:
        print("[ISLAMIYAH] Placement failed:", error); return jsonify({"success": False, "message": "Unable to update Islamiyah class placement."}), 500


@islamiyah_bp.get("/api/islamiyah/scores")
@islamiyah_staff_required
def api_islamiyah_scores():
    try:
        academic_session, term = _resolve_context(request.args.get("session"), request.args.get("term")); session_value = normalize_islamiyah_session(academic_session); level = normalize_islamiyah_class(request.args.get("islamiyah_class")); subject = clean(request.args.get("subject")); _, error = _ensure_access(session_value, level, subject)
        if error: return jsonify({"success": False, "message": error, "students": []}), 403
        payload = get_score_entry_roster(session_value, term, level, subject); return jsonify({"success": True, **payload})
    except ValueError as error: return jsonify({"success": False, "message": str(error), "students": []}), 400


@islamiyah_bp.patch("/api/islamiyah/scores/autosave")
@islamiyah_staff_required
def api_islamiyah_score_autosave():
    data = _payload()
    try:
        session_value = normalize_islamiyah_session(data.get("session")); term = normalize_academic_term(data.get("term")); enrollment = get_enrollment(data.get("admission_number"), session_value, active_only=True)
        if not enrollment: raise ValueError("Student is not in the active Islamiyah roster for this session.")
        level = normalize_islamiyah_class(enrollment.get("islamiyah_class")); subject = clean(data.get("subject_key") or data.get("subject")); _, error = _ensure_access(session_value, level, subject)
        if error: return jsonify({"success": False, "message": error}), 403
        record = save_student_score(session_value, term, data.get("admission_number"), subject, data.get("ca"), data.get("exam"), _staff_name()); sync_info = _queue_score_scope(session_value, term, level, subject)
        return jsonify({"success": True, "message": "Saved", "record": record, "sync": sync_info})
    except ValueError as error: return jsonify({"success": False, "message": str(error)}), 400
    except Exception as error:
        print("[ISLAMIYAH] Autosave failed:", error); return jsonify({"success": False, "message": "Unable to autosave Islamiyah score."}), 500


@islamiyah_bp.get("/api/islamiyah/results")
@islamiyah_staff_required
def api_islamiyah_results():
    try:
        academic_session, term = _resolve_context(request.args.get("session"), request.args.get("term")); session_value = normalize_islamiyah_session(academic_session); level = normalize_islamiyah_class(request.args.get("islamiyah_class")); _, error = _ensure_access(session_value, level)
        if error: return jsonify({"success": False, "message": error, "students": []}), 403
        payload = get_class_result_summary(session_value, term, level)
        if _role() == "teacher":
            allowed_subjects = _teacher_access(session_value).get(level, set()); payload["subjects"] = [row for row in payload.get("subjects", []) if row.get("key") in allowed_subjects]
            for student in payload.get("students", []): student["subjects"] = [row for row in student.get("subjects", []) if row.get("subject_key") in allowed_subjects]
        return jsonify({"success": True, **payload})
    except ValueError as error: return jsonify({"success": False, "message": str(error), "students": []}), 400


@islamiyah_bp.get("/api/islamiyah/history/<admission_number>")
@islamiyah_staff_required
def api_islamiyah_history(admission_number):
    try:
        academic_session = normalize_academic_session(request.args.get("session")); check_session = academic_session or _resolve_context("", "")[0]; access, error = _ensure_access(normalize_islamiyah_session(check_session)); enrollment = get_enrollment(admission_number, check_session, active_only=False)
        if _role() == "teacher" and (not enrollment or enrollment.get("islamiyah_class") not in access): return jsonify({"success": False, "message": error or "This student's Islamiyah record is outside your assigned teaching load."}), 403
        history = get_student_history(admission_number, academic_session); return jsonify({"success": True, "admission_number": admission_number, "history": history, "count": len(history)})
    except ValueError as error: return jsonify({"success": False, "message": str(error)}), 400


@islamiyah_bp.get("/api/islamiyah/export")
@islamiyah_staff_required
def api_islamiyah_export():
    try:
        academic_session, term = _resolve_context(request.args.get("session"), request.args.get("term")); session_value = normalize_islamiyah_session(academic_session); level = normalize_islamiyah_class(request.args.get("islamiyah_class")); subject = clean(request.args.get("subject")); _, error = _ensure_access(session_value, level, subject)
        if error: return jsonify({"success": False, "message": error}), 403
        payload = get_score_entry_roster(session_value, term, level, subject); workbook = Workbook(); sheet = workbook.active; sheet.title = "Islamiyah Scores"
        headers = ["S/N", "Admission No.", "Student Name", "Regular Class", "Islamiyah Class", f"CA /{CA_MAX}", f"Exam /{EXAM_MAX}", f"Total /{TOTAL_MAX}", "Status", "Saved At", "Saved By"]
        sheet.append(headers)
        for cell in sheet[1]: cell.font = Font(bold=True); cell.alignment = Alignment(horizontal="center", vertical="center")
        for index, student in enumerate(payload.get("students", []), 1):
            score = student.get("scores") or {}; sheet.append([index, student.get("admission_number"), student.get("full_name"), student.get("regular_class"), student.get("islamiyah_class_label"), score.get("ca"), score.get("exam"), score.get("total"), "Complete" if score.get("complete") else "Pending", score.get("saved_at", ""), score.get("saved_by", "")])
        widths = [7, 16, 32, 16, 20, 12, 12, 13, 14, 21, 18]
        for index, width in enumerate(widths, 1): sheet.column_dimensions[chr(64 + index)].width = width
        sheet.freeze_panes = "A2"; stream = BytesIO(); workbook.save(stream); stream.seek(0); safe_subject = "_".join(payload.get("subject", "subject").lower().split()); filename = f"islamiyah_{payload.get('islamiyah_class','').lower()}_{safe_subject}_{term.lower()}_{datetime.now().strftime('%Y%m%d')}.xlsx"
        return send_file(stream, as_attachment=True, download_name=filename, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except ValueError as error: return jsonify({"success": False, "message": str(error)}), 400
