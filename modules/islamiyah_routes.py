# MODULE: Islamiyah School Routes — staff UI APIs for roster placement, CA /30 + Exam /70 autosave, history and export

from functools import wraps
from io import BytesIO
from datetime import datetime

from flask import Blueprint, jsonify, request, session, send_file
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment

from modules.academic_records import clean, normalize_academic_session, normalize_academic_term, get_current_academic_context
from modules.school_structure import ISLAMIYAH_CLASS_LEVELS, ISLAMIYAH_ROSTER_CLASSES, islamiyah_base_level
from modules.result_sync import queue_emis_event_safely
from modules.islamiyah_manager import CA_MAX, EXAM_MAX, TOTAL_MAX, ISLAMIYAH_PROMOTION_PATH, assign_students, build_enrollment_sync_payload, build_score_scope_sync_payload, get_class_result_summary, get_enrollment, get_islamiyah_dashboard, get_islamiyah_roster_coverage, get_score_entry_roster, get_score_records, get_student_history, get_report_sync_roster, get_student_report_sync_sheet, get_report_islamiyah_row, get_regular_school_roster, get_regular_school_report_sheet, save_regular_school_islamiyah_score, regular_school_class_options, import_current_student_database, islamiyah_class_label, islamiyah_subject_rows, list_enrollments, next_islamiyah_class, normalize_islamiyah_class, normalize_islamiyah_session, promote_islamiyah_students, save_student_score, upsert_external_islamiyah_students, enroll_regular_students, add_islamiyah_student, update_islamiyah_student, remove_islamiyah_students, clear_islamiyah_score_records, clear_regular_school_score_records, get_academy_activity, log_academy_activity
from modules.tahfeez_database import get_tahfeez_management_roster, get_tahfeez_summary, set_tahfeez_placements, remove_tahfeez_placements, register_regular_students_to_tahfeez, add_tahfeez_student, update_tahfeez_student, tahfeez_database_health_check
from modules.school_structure import TAHFEEZ_CLASS_LEVELS, class_label
from modules.islamiyah_database import COMBINED_CSV, read_register
from modules.notifications import push_notification


islamiyah_bp = Blueprint("islamiyah_bp", __name__)


def _payload():
    value = request.get_json(silent=True); return value if isinstance(value, dict) else {}


def _role(): return clean(session.get("user_type")).lower()
def _teacher_id(): return clean(session.get("teacher_id") or session.get("username"))
def _staff_name(): return clean(session.get("admin_username") or session.get("username") or session.get("teacher_id") or "Staff")


def islamiyah_staff_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if _role() not in {"admin", "islamiyyah_teacher"}: return jsonify({"success": False, "message": "Unauthorized."}), 403
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
    # Central Admin and IMS staff both receive the complete Academy scope. IMS is restricted by PAGE access,
    # not by class/subject assignment. Normal EMT/ADM roles cannot enter this API at all.
    return {level: {row["key"] for row in islamiyah_subject_rows(level)} for level in ISLAMIYAH_CLASS_LEVELS}


def _ensure_access(academic_session, class_level="", subject=""):
    access = _teacher_access(academic_session)
    if _role() == "admin": return access, ""
    if not access: return access, "Academy access is unavailable for this account."
    if class_level:
        level = normalize_islamiyah_class(class_level)
        if level not in access: return access, f"Academy access does not include {islamiyah_class_label(level)}."
        if subject:
            wanted = clean(subject).upper(); rows = islamiyah_subject_rows(level); key = next((row["key"] for row in rows if wanted in {clean(row["key"]).upper(), clean(row["name"]).upper(), clean(row["id"]).upper()}), wanted)
            if key not in access.get(level, set()): return access, f"Academy access does not include {next((row['name'] for row in rows if row['key'] == key), subject)} in {islamiyah_class_label(level)}."
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
        dashboard = get_islamiyah_dashboard(session_value, term); dashboard_counts = dashboard.get("class_counts", {}); classes = []
        for level in ISLAMIYAH_ROSTER_CLASSES + [key for key in ISLAMIYAH_CLASS_LEVELS if key not in ISLAMIYAH_ROSTER_CLASSES and dashboard_counts.get(key)]:
            subjects = islamiyah_subject_rows(level); allowed_keys = access.get(level, set()) if _role() == "islamiyyah_teacher" else {row["key"] for row in subjects}; visible = [row for row in subjects if row["key"] in allowed_keys]
            classes.append({"key": level, "label": islamiyah_class_label(level), "subjects": visible, "subject_count": len(visible), "roster_manage": True})
        roster_imported = dashboard.get("roster_count", 0) > 0; tahfeez_summary = get_tahfeez_summary()
        return jsonify({"success": True, "role": _role(), "academic_session": session_value, "term": term, "classes": classes, "assessment": {"ca_max": CA_MAX, "exam_max": EXAM_MAX, "total_max": TOTAL_MAX}, "dashboard": dashboard, "tahfeez": {"summary": tahfeez_summary, "health": {"healthy": True, "count": tahfeez_summary.get("total", 0)}, "classes": [{"key": level, "label": class_label(level)} for level in TAHFEEZ_CLASS_LEVELS]}, "promotion": {"islamiyah_path": [{"key": level, "label": islamiyah_class_label(level), "next": next_islamiyah_class(level)} for level in ISLAMIYAH_ROSTER_CLASSES], "tahfeez_path": [{"key": level, "label": class_label(level), "next": TAHFEEZ_CLASS_LEVELS[index + 1] if index + 1 < len(TAHFEEZ_CLASS_LEVELS) else ""} for index, level in enumerate(TAHFEEZ_CLASS_LEVELS)]}, "regular_school": {"classes": regular_school_class_options(), "total": sum(item.get("count", 0) for item in regular_school_class_options()), "source": "students2026.csv"}, "combined_database": {"source": "tahfeez2026.csv", "tahfeez_students": tahfeez_summary.get("total", 0), "islamiyah_students": dashboard.get("assigned_count", 0)}, "roster_imported": roster_imported, "can_manage_roster": _role() in {"admin", "islamiyyah_teacher"}, "teacher_has_access": bool(access), "access_message": access_error})
    except ValueError as error: return jsonify({"success": False, "message": str(error)}), 400
    except Exception as error:
        print("[ISLAMIYAH] Config failed:", error); return jsonify({"success": False, "message": "Unable to load Islamiyah School configuration."}), 500


@islamiyah_bp.get("/api/islamiyah/dashboard")
@islamiyah_staff_required
def api_islamiyah_dashboard():
    try:
        academic_session, term = _resolve_context(request.args.get("session"), request.args.get("term")); session_value = normalize_islamiyah_session(academic_session); access, error = _ensure_access(session_value)
        if _role() == "islamiyyah_teacher" and error and not access: return jsonify({"success": True, "dashboard": get_islamiyah_dashboard(session_value, term), "allowed_classes": [], "message": error})
        dashboard = get_islamiyah_dashboard(session_value, term)
        if _role() == "islamiyyah_teacher": dashboard["classes"] = [row for row in dashboard.get("classes", []) if row.get("key") in access]; dashboard["class_counts"] = {key: value for key, value in dashboard.get("class_counts", {}).items() if key in access}
        return jsonify({"success": True, "dashboard": dashboard, "allowed_classes": list(access)})
    except ValueError as error: return jsonify({"success": False, "message": str(error)}), 400


@islamiyah_bp.get("/api/islamiyah/roster")
@islamiyah_staff_required
def api_islamiyah_roster():
    try:
        academic_session, _ = _resolve_context(request.args.get("session"), request.args.get("term")); session_value = normalize_islamiyah_session(academic_session); requested_class = clean(request.args.get("islamiyah_class")); access, _ = _ensure_access(session_value)
        # Roster management is an Academy operation, not a subject-score permission. IMS staff may view/manage the Academy roster while score entry remains limited by teaching assignment.
        students = list_enrollments(session_value, requested_class, request.args.get("regular_class", ""), active_only=True, search=request.args.get("search", "")); classes = []
        for level in ISLAMIYAH_ROSTER_CLASSES:
            subjects = islamiyah_subject_rows(level); allowed_keys = access.get(level, set()) if _role() == "islamiyyah_teacher" else {row["key"] for row in subjects}; visible = [row for row in subjects if row["key"] in allowed_keys] if allowed_keys else subjects
            classes.append({"key": level, "label": islamiyah_class_label(level), "subjects": visible, "subject_count": len(subjects), "score_subject_count": len(visible)})
        return jsonify({"success": True, "session": session_value, "students": students, "classes": classes, "count": len(students), "assigned": sum(1 for row in students if row.get("islamiyah_class")), "unassigned": sum(1 for row in students if not row.get("islamiyah_class")), "roster_coverage": get_islamiyah_roster_coverage(session_value), "can_manage_roster": _role() in {"admin", "islamiyyah_teacher"}})
    except ValueError as error: return jsonify({"success": False, "message": str(error), "students": []}), 400


@islamiyah_bp.post("/api/islamiyah/roster/import")
@islamiyah_admin_required
def api_islamiyah_roster_import():
    data = _payload()
    try:
        academic_session, _ = _resolve_context(data.get("session"), data.get("term")); result = import_current_student_database(academic_session, _staff_name()); result["sync"] = _queue_enrollment_snapshot(result["session"])
        return jsonify({"success": True, "message": f"Regular-school identity links refreshed — {result['linked']} Academy student(s) currently have verified std... admissions. Independent Academy records were preserved.", **result})
    except ValueError as error: return jsonify({"success": False, "message": str(error)}), 400
    except Exception as error:
        print("[ISLAMIYAH] Roster import failed:", error); return jsonify({"success": False, "message": "Unable to synchronize the school database into Islamiyah School."}), 500


@islamiyah_bp.put("/api/islamiyah/roster/assign")
@islamiyah_staff_required
def api_islamiyah_roster_assign():
    data = _payload()
    try:
        admissions = data.get("admission_numbers") or data.get("students") or []; result = assign_students(data.get("session"), admissions, data.get("islamiyah_class", ""), _staff_name()); result["sync"] = _queue_enrollment_snapshot(result["session"]); log_academy_activity("MOVE" if result.get("islamiyah_class") else "UNASSIGN", "ISLAMIYYAH", result["session"], admissions, result.get("islamiyah_class", ""), _staff_name(), "Academy roster placement updated")
        message = f"{result['updated']} student(s) assigned to {result['islamiyah_class_label']}." if result.get("islamiyah_class") else f"{result['updated']} student(s) returned to Unassigned."
        return jsonify({"success": True, "message": message, **result})
    except ValueError as error: return jsonify({"success": False, "message": str(error)}), 400
    except Exception as error:
        print("[ISLAMIYAH] Placement failed:", error); return jsonify({"success": False, "message": "Unable to update Islamiyah class placement."}), 500


@islamiyah_bp.get("/api/islamiyah/tahfeez/roster")
@islamiyah_staff_required
def api_islamiyah_tahfeez_roster():
    try:
        academic_session, _ = _resolve_context(request.args.get("session"), request.args.get("term")); session_value = normalize_islamiyah_session(academic_session); students = get_tahfeez_management_roster(); enrollments = {clean(row.get("academy_admission_number") or row.get("admission_number")).lower(): row for row in list_enrollments(session_value, active_only=True)}
        for student in students:
            enrollment = enrollments.get(clean(student.get("admission_number")).lower()); transitioned = enrollment if enrollment and clean(enrollment.get("source")).upper() == "TAHFEEZ" else None
            student["transitioned_to_islamiyah"] = transitioned.get("islamiyah_class") if transitioned else ""; student["transitioned_to_islamiyah_label"] = transitioned.get("islamiyah_class_label") if transitioned else ""
        summary = get_tahfeez_summary(); return jsonify({"success": True, "session": session_value, "students": students, "summary": summary, "health": {"healthy": True, "count": len(students)}, "classes": [{"key": level, "label": class_label(level)} for level in TAHFEEZ_CLASS_LEVELS], "count": len(students)})
    except ValueError as error: return jsonify({"success": False, "message": str(error), "students": []}), 400
    except Exception as error:
        print("[ISLAMIYAH] Tahfeez roster failed:", error); return jsonify({"success": False, "message": "Unable to load the Tahfeez roster."}), 500


@islamiyah_bp.put("/api/islamiyah/tahfeez/assign")
@islamiyah_staff_required
def api_islamiyah_tahfeez_assign():
    data = _payload(); admissions = data.get("admission_numbers") or data.get("admissions") or []; target = clean(data.get("tahfeez_class"))
    try:
        if not target: raise ValueError("Choose a Tahfeez class.")
        academic_session, _ = _resolve_context(data.get("session"), data.get("term")); result = set_tahfeez_placements(admissions, target, reason="islamiyah_page_tahfeez_assignment"); log_academy_activity("MOVE", "TAHFEEZ", academic_session, admissions, target, _staff_name(), "Tahfeez roster placement updated")
        return jsonify({"success": True, "message": f"{len(result.get('updated') or [])} student(s) moved to {class_label(result.get('tahfeez_class'))}.", "result": result, "summary": get_tahfeez_summary()})
    except ValueError as error: return jsonify({"success": False, "message": str(error)}), 400
    except Exception as error:
        print("[ISLAMIYAH] Tahfeez assignment failed:", error); return jsonify({"success": False, "message": "Unable to update Tahfeez placement."}), 500


@islamiyah_bp.post("/api/islamiyah/tahfeez/promote")
@islamiyah_staff_required
def api_islamiyah_tahfeez_promote():
    data = _payload(); admissions = [clean(value) for value in (data.get("admission_numbers") or data.get("admissions") or []) if clean(value)]
    try:
        source = clean(data.get("source_class")).upper()
        if source not in TAHFEEZ_CLASS_LEVELS: raise ValueError("Choose a valid Tahfeez source class.")
        roster = get_tahfeez_management_roster(); selected = [row for row in roster if clean(row.get("admission_number")).lower() in {value.lower() for value in admissions} and row.get("tahfeez_class") == source]
        if not selected: raise ValueError(f"Select at least one student currently in {class_label(source)}.")
        if len(selected) != len({value.lower() for value in admissions}): raise ValueError("One or more selected students are no longer in the chosen Tahfeez class. Refresh and try again.")
        index = TAHFEEZ_CLASS_LEVELS.index(source)
        if index + 1 < len(TAHFEEZ_CLASS_LEVELS):
            academic_session, _ = _resolve_context(data.get("session"), data.get("term")); target = TAHFEEZ_CLASS_LEVELS[index + 1]; result = set_tahfeez_placements(admissions, target, reason=f"promotion_{source}_to_{target}"); log_academy_activity("PROMOTE", "TAHFEEZ", academic_session, admissions, target, _staff_name(), f"From {class_label(source)} to {class_label(target)}")
            return jsonify({"success": True, "message": f"{len(selected)} student(s) promoted from {class_label(source)} to {class_label(target)}.", "source_class": source, "destination_class": target, "destination_label": class_label(target), "result": result, "summary": get_tahfeez_summary()})
        academic_session, _ = _resolve_context(data.get("session"), data.get("term")); target = normalize_islamiyah_class(data.get("destination_class")); transition = upsert_external_islamiyah_students(academic_session, selected, target, _staff_name(), source="TAHFEEZ"); transition["sync"] = _queue_enrollment_snapshot(transition["session"]); log_academy_activity("PROMOTE", "TAHFEEZ", academic_session, admissions, target, _staff_name(), f"Tahfeez 5 transition to {transition['islamiyah_class_label']}")
        return jsonify({"success": True, "message": f"{len(selected)} Tahfeez 5 student(s) transitioned to {transition['islamiyah_class_label']}. Their Tahfeez 5 record is preserved as the completion-stage register.", "source_class": source, "destination_class": target, "destination_label": transition["islamiyah_class_label"], "transition": transition})
    except ValueError as error: return jsonify({"success": False, "message": str(error)}), 400
    except Exception as error:
        print("[ISLAMIYAH] Tahfeez promotion failed:", error); return jsonify({"success": False, "message": "Unable to complete Tahfeez promotion."}), 500


@islamiyah_bp.post("/api/islamiyah/promote")
@islamiyah_staff_required
def api_islamiyah_promote():
    data = _payload()
    try:
        academic_session, _ = _resolve_context(data.get("session"), data.get("term")); session_value = normalize_islamiyah_session(academic_session); source = normalize_islamiyah_class(data.get("source_class")); result = promote_islamiyah_students(session_value, data.get("admission_numbers") or data.get("admissions") or [], source, data.get("destination_class", ""), _staff_name()); result["sync"] = _queue_enrollment_snapshot(result["session"]); log_academy_activity("PROMOTE", "ISLAMIYAH", session_value, data.get("admission_numbers") or data.get("admissions") or [], result.get("destination_class"), _staff_name(), f"From {result.get('source_class_label')} to {result.get('destination_class_label')}")
        return jsonify({"success": True, "message": f"{result['promoted']} student(s) promoted from {result['source_class_label']} to {result['destination_class_label']}.", **result})
    except ValueError as error: return jsonify({"success": False, "message": str(error)}), 400
    except Exception as error:
        print("[ISLAMIYAH] Islamiyah promotion failed:", error); return jsonify({"success": False, "message": "Unable to complete Islamiyah promotion."}), 500


@islamiyah_bp.get("/api/islamiyah/tahfeez/export")
@islamiyah_staff_required
def api_islamiyah_tahfeez_export():
    try:
        rows = get_tahfeez_management_roster(); workbook = Workbook(); sheet = workbook.active; sheet.title = "Tahfeez Register"; headers = ["S/N", "Regular Admission", "Tahfeez ID", "Student Name", "Phone", "Sex", "Regular Class", "Tahfeez Class"]
        sheet.append(headers)
        for cell in sheet[1]: cell.font = Font(bold=True); cell.alignment = Alignment(horizontal="center", vertical="center")
        for index, row in enumerate(rows, 1): sheet.append([index, row.get("regular_admission_number") or "—", row.get("academy_admission_number") or row.get("admission_number"), row.get("full_name"), row.get("phone"), row.get("sex"), row.get("regular_class") or row.get("regular_class_category"), row.get("tahfeez_class_label")])
        for column, width in {"A":7,"B":18,"C":16,"D":34,"E":18,"F":11,"G":22,"H":18}.items(): sheet.column_dimensions[column].width = width
        sheet.freeze_panes = "A2"; stream = BytesIO(); workbook.save(stream); workbook.close(); stream.seek(0)
        return send_file(stream, as_attachment=True, download_name=f"Tahfeez_Register_{datetime.now().strftime('%Y%m%d')}.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except Exception as error:
        print("[ISLAMIYAH] Tahfeez export failed:", error); return jsonify({"success": False, "message": "Unable to export the Tahfeez register."}), 500


@islamiyah_bp.get("/api/islamiyah/regular-school/roster")
@islamiyah_staff_required
def api_islamiyah_regular_school_roster():
    try:
        academic_session, term = _resolve_context(request.args.get("session"), request.args.get("term")); payload = get_regular_school_roster(academic_session, term, request.args.get("class_level", ""), request.args.get("class_arm", ""), request.args.get("search", ""), include_scores=True)
        return jsonify({"success": True, **payload})
    except ValueError as error: return jsonify({"success": False, "message": str(error), "students": []}), 400


@islamiyah_bp.get("/api/islamiyah/regular-school/student/<admission_number>")
@islamiyah_staff_required
def api_islamiyah_regular_school_student(admission_number):
    try:
        academic_session, term = _resolve_context(request.args.get("session"), request.args.get("term")); return jsonify({"success": True, **get_regular_school_report_sheet(admission_number, academic_session, term)})
    except ValueError as error: return jsonify({"success": False, "message": str(error)}), 400


@islamiyah_bp.patch("/api/islamiyah/regular-school/scores/autosave")
@islamiyah_staff_required
def api_islamiyah_regular_school_score_autosave():
    data = _payload()
    try:
        session_value = normalize_islamiyah_session(data.get("session")); term = normalize_academic_term(data.get("term")); record = save_regular_school_islamiyah_score(session_value, term, data.get("admission_number"), data.get("ca"), data.get("exam"), _staff_name(), data.get("exempt", False)); student_sheet = get_regular_school_report_sheet(data.get("admission_number"), session_value, term); student = student_sheet.get("student") or {}
        notification = push_notification("islamiyah_score_saved", f"Islamiyyah score updated: {student.get('full_name') or data.get('admission_number')} — {student.get('regular_class') or 'Regular School'}", payload={"session": session_value, "term": term, "source": "regular_school", "academy_admission_number": "", "regular_admission_number": student.get("regular_admission_number"), "full_name": student.get("full_name"), "regular_class": student.get("regular_class"), "subject": "Islamiyyah", "subject_key": "ISLAMIYYAH", "score_complete": bool(record.get("complete")), "report_complete": bool(student.get("complete")), "report_status": student.get("status", "pending")})
        return jsonify({"success": True, "message": "Saved", "record": record, "notification": notification, "report_sync": student})
    except ValueError as error: return jsonify({"success": False, "message": str(error)}), 400
    except Exception as error:
        print("[ISLAMIYYAH] Regular-school autosave failed:", error); return jsonify({"success": False, "message": "Unable to autosave the regular-school Islamiyyah score."}), 500


@islamiyah_bp.get("/api/islamiyah/report-sync")
@islamiyah_staff_required
def api_islamiyah_report_sync():
    try:
        academic_session, term = _resolve_context(request.args.get("session"), request.args.get("term")); session_value = normalize_islamiyah_session(academic_session); level = normalize_islamiyah_class(request.args.get("islamiyah_class"), allow_blank=True); access, error = _ensure_access(session_value, level) if level else _ensure_access(session_value)
        if error and _role() == "islamiyyah_teacher" and level: return jsonify({"success": False, "message": error, "students": []}), 403
        payload = get_report_sync_roster(session_value, term, level, request.args.get("regular_class", ""), request.args.get("search", ""))
        if _role() == "islamiyyah_teacher" and not level: payload["students"] = [row for row in payload.get("students", []) if row.get("islamiyah_class") in access]; payload["count"] = len(payload["students"]); payload["complete_students"] = sum(1 for row in payload["students"] if row.get("complete")); payload["partial_students"] = sum(1 for row in payload["students"] if row.get("status") == "partial"); payload["pending_students"] = sum(1 for row in payload["students"] if row.get("status") == "pending")
        return jsonify({"success": True, **payload})
    except ValueError as error: return jsonify({"success": False, "message": str(error), "students": []}), 400


@islamiyah_bp.get("/api/islamiyah/report-sync/student/<admission_number>")
@islamiyah_staff_required
def api_islamiyah_report_sync_student(admission_number):
    try:
        academic_session, term = _resolve_context(request.args.get("session"), request.args.get("term")); session_value = normalize_islamiyah_session(academic_session); enrollment = get_enrollment(admission_number, session_value, active_only=True)
        if not enrollment: return jsonify({"success": False, "message": "Student was not found in the active Islamiyyah roster."}), 404
        level = normalize_islamiyah_class(enrollment.get("islamiyah_class")); _, error = _ensure_access(session_value, level)
        if error: return jsonify({"success": False, "message": error}), 403
        return jsonify({"success": True, **get_student_report_sync_sheet(session_value, term, admission_number)})
    except ValueError as error: return jsonify({"success": False, "message": str(error)}), 400


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
        record = save_student_score(session_value, term, data.get("admission_number"), subject, data.get("ca"), data.get("exam"), _staff_name()); sync_info = _queue_score_scope(session_value, term, level, subject); enrollment = get_enrollment(data.get("admission_number"), session_value, active_only=True); regular = clean((enrollment or {}).get("regular_admission_number")); report_status = get_report_islamiyah_row(regular, session_value, term) if regular else None
        notification = push_notification("islamiyah_score_saved", f"Islamiyyah score updated: {(enrollment or {}).get('full_name') or data.get('admission_number')} — {islamiyah_class_label(level)} / {record.get('subject') or subject}", payload={"session": session_value, "term": term, "islamiyah_class": level, "islamiyah_class_label": islamiyah_class_label(level), "academy_admission_number": clean((enrollment or {}).get("admission_number")), "regular_admission_number": regular, "full_name": clean((enrollment or {}).get("full_name")), "regular_class": clean((enrollment or {}).get("regular_class")), "subject": record.get("subject"), "subject_key": record.get("subject_key"), "score_complete": bool(record.get("complete")), "report_complete": bool((report_status or {}).get("complete")), "report_status": (report_status or {}).get("islamiyah_status", "unlinked")})
        return jsonify({"success": True, "message": "Saved", "record": record, "sync": sync_info, "notification": notification, "report_sync": report_status})
    except ValueError as error: return jsonify({"success": False, "message": str(error)}), 400
    except Exception as error:
        print("[ISLAMIYAH] Autosave failed:", error); return jsonify({"success": False, "message": "Unable to autosave Islamiyah score."}), 500



@islamiyah_bp.post("/api/islamiyah/roster/register-regular")
@islamiyah_staff_required
def api_islamiyah_register_regular_students():
    data = _payload()
    try:
        academic_session, _ = _resolve_context(data.get("session"), data.get("term")); session_value = normalize_islamiyah_session(academic_session); school = clean(data.get("school")).lower(); admissions = data.get("admission_numbers") or data.get("students") or []; target = clean(data.get("class_level") or data.get("target_class"))
        if school == "tahfeez":
            result = register_regular_students_to_tahfeez(admissions, target, _staff_name()); log_academy_activity("REGISTER_FROM_BASIC", "TAHFEEZ", session_value, result.get("admission_numbers") or [], result.get("tahfeez_class"), _staff_name(), f"{result.get('created',0)} created, {result.get('updated',0)} updated; regular master unchanged")
            return jsonify({"success": True, "message": f"{len(result.get('admission_numbers') or [])} student(s) registered in {class_label(result.get('tahfeez_class'))}. The Basic School database was not changed.", "result": result})
        result = enroll_regular_students(session_value, admissions, target, _staff_name()); result["sync"] = _queue_enrollment_snapshot(session_value)
        return jsonify({"success": True, "message": f"{len(result.get('academy_admission_numbers') or [])} student(s) registered in {result.get('islamiyah_class_label')}. The Basic School database was not changed.", "result": result})
    except ValueError as error: return jsonify({"success": False, "message": str(error)}), 400
    except Exception as error:
        print("[ISLAMIYAH] Register from basic failed:", error); return jsonify({"success": False, "message": "Unable to register the selected Basic School students in the Academy."}), 500


@islamiyah_bp.post("/api/islamiyah/roster/student")
@islamiyah_staff_required
def api_islamiyah_add_academy_student():
    data = _payload()
    try:
        academic_session, _ = _resolve_context(data.get("session"), data.get("term")); session_value = normalize_islamiyah_session(academic_session); school = clean(data.get("school")).lower()
        if school == "tahfeez":
            result = add_tahfeez_student(data, _staff_name()); student = result.get("student") or {}; log_academy_activity("ADD", "TAHFEEZ", session_value, [student.get("admission_number")], student.get("tahfeez_class"), _staff_name(), "Independent Academy student")
            return jsonify({"success": True, "message": "Tahfeez student added.", "student": student})
        student = add_islamiyah_student(session_value, data, _staff_name()); _queue_enrollment_snapshot(session_value); return jsonify({"success": True, "message": "Islamiyyah student added.", "student": student})
    except ValueError as error: return jsonify({"success": False, "message": str(error)}), 400
    except Exception as error:
        print("[ISLAMIYAH] Add Academy student failed:", error); return jsonify({"success": False, "message": "Unable to add the Academy student."}), 500


@islamiyah_bp.put("/api/islamiyah/roster/student/<admission_number>")
@islamiyah_staff_required
def api_islamiyah_edit_academy_student(admission_number):
    data = _payload()
    try:
        academic_session, _ = _resolve_context(data.get("session"), data.get("term")); session_value = normalize_islamiyah_session(academic_session); school = clean(data.get("school")).lower()
        if school == "tahfeez":
            result = update_tahfeez_student(admission_number, data, _staff_name()); student = result.get("student") or {}; log_academy_activity("EDIT", "TAHFEEZ", session_value, [admission_number], student.get("tahfeez_class"), _staff_name(), "Tahfeez profile only; regular master unchanged")
            return jsonify({"success": True, "message": "Tahfeez student updated.", "student": student})
        student = update_islamiyah_student(session_value, admission_number, data, _staff_name()); _queue_enrollment_snapshot(session_value); return jsonify({"success": True, "message": "Islamiyyah student updated.", "student": student})
    except ValueError as error: return jsonify({"success": False, "message": str(error)}), 400
    except Exception as error:
        print("[ISLAMIYAH] Edit Academy student failed:", error); return jsonify({"success": False, "message": "Unable to edit the Academy student."}), 500


@islamiyah_bp.delete("/api/islamiyah/roster/students")
@islamiyah_staff_required
def api_islamiyah_remove_academy_students():
    data = _payload()
    try:
        academic_session, _ = _resolve_context(data.get("session"), data.get("term")); session_value = normalize_islamiyah_session(academic_session); school = clean(data.get("school")).lower(); admissions = data.get("admission_numbers") or data.get("students") or []
        if school == "tahfeez":
            result = remove_tahfeez_placements(admissions, reason="academy_teacher_remove"); log_academy_activity("REMOVE", "TAHFEEZ", session_value, result.get("removed") or [], "", _staff_name(), "Tahfeez placement removed; Basic School master unchanged")
            return jsonify({"success": True, "message": f"{result.get('count',0)} Tahfeez record(s) removed. Basic School records were not changed.", "result": result})
        result = remove_islamiyah_students(session_value, admissions, _staff_name()); result["sync"] = _queue_enrollment_snapshot(session_value); return jsonify({"success": True, "message": f"{result.get('count',0)} Islamiyyah record(s) removed from the active Academy roster. Score history was preserved and Basic School records were not changed.", "result": result})
    except ValueError as error: return jsonify({"success": False, "message": str(error)}), 400
    except Exception as error:
        print("[ISLAMIYAH] Remove Academy students failed:", error); return jsonify({"success": False, "message": "Unable to remove the selected Academy student records."}), 500


@islamiyah_bp.delete("/api/islamiyah/scores/records")
@islamiyah_staff_required
def api_islamiyah_clear_score_records():
    data = _payload()
    try:
        session_value = normalize_islamiyah_session(data.get("session")); term = normalize_academic_term(data.get("term")); admissions = data.get("admission_numbers") or []; subject = clean(data.get("subject_key") or data.get("subject"))
        if _role() == "islamiyyah_teacher" and subject:
            for admission in admissions:
                enrollment = get_enrollment(admission, session_value, active_only=True)
                if enrollment:
                    _, error = _ensure_access(session_value, enrollment.get("islamiyah_class"), subject)
                    if error: return jsonify({"success": False, "message": error}), 403
        result = clear_islamiyah_score_records(session_value, term, admissions, subject, _staff_name()); return jsonify({"success": True, "message": f"{result.get('cleared',0)} Islamiyyah score record(s) cleared.", "result": result})
    except ValueError as error: return jsonify({"success": False, "message": str(error)}), 400


@islamiyah_bp.delete("/api/islamiyah/regular-school/scores/records")
@islamiyah_staff_required
def api_islamiyah_clear_regular_score_records():
    data = _payload()
    try:
        result = clear_regular_school_score_records(data.get("session"), data.get("term"), data.get("admission_numbers") or [], _staff_name()); return jsonify({"success": True, "message": f"{result.get('cleared',0)} direct Islamiyyah score record(s) cleared. No Basic School student record was modified.", "result": result})
    except ValueError as error: return jsonify({"success": False, "message": str(error)}), 400


@islamiyah_bp.get("/api/islamiyah/activity")
@islamiyah_staff_required
def api_islamiyah_activity():
    try: return jsonify({"success": True, "records": get_academy_activity(request.args.get("limit", 80), request.args.get("school", ""))})
    except Exception as error: return jsonify({"success": False, "message": "Unable to load Academy activity."}), 500


@islamiyah_bp.get("/api/islamiyah/results")
@islamiyah_staff_required
def api_islamiyah_results():
    try:
        academic_session, term = _resolve_context(request.args.get("session"), request.args.get("term")); session_value = normalize_islamiyah_session(academic_session); level = normalize_islamiyah_class(request.args.get("islamiyah_class")); _, error = _ensure_access(session_value, level)
        if error: return jsonify({"success": False, "message": error, "students": []}), 403
        payload = get_class_result_summary(session_value, term, level)
        if _role() == "islamiyyah_teacher":
            allowed_subjects = _teacher_access(session_value).get(level, set()); payload["subjects"] = [row for row in payload.get("subjects", []) if row.get("key") in allowed_subjects]
            for student in payload.get("students", []): student["subjects"] = [row for row in student.get("subjects", []) if row.get("subject_key") in allowed_subjects]
        return jsonify({"success": True, **payload})
    except ValueError as error: return jsonify({"success": False, "message": str(error), "students": []}), 400


@islamiyah_bp.get("/api/islamiyah/history/<admission_number>")
@islamiyah_staff_required
def api_islamiyah_history(admission_number):
    try:
        academic_session = normalize_academic_session(request.args.get("session")); check_session = academic_session or _resolve_context("", "")[0]; access, error = _ensure_access(normalize_islamiyah_session(check_session)); enrollment = get_enrollment(admission_number, check_session, active_only=False)
        if _role() == "islamiyyah_teacher" and (not enrollment or enrollment.get("islamiyah_class") not in access): return jsonify({"success": False, "message": error or "This student's Islamiyyah record is unavailable."}), 403
        history = get_student_history(admission_number, academic_session); return jsonify({"success": True, "admission_number": admission_number, "history": history, "count": len(history)})
    except ValueError as error: return jsonify({"success": False, "message": str(error)}), 400


@islamiyah_bp.get("/api/islamiyah/export")
@islamiyah_staff_required
def api_islamiyah_export():
    try:
        academic_session, term = _resolve_context(request.args.get("session"), request.args.get("term")); session_value = normalize_islamiyah_session(academic_session); level = normalize_islamiyah_class(request.args.get("islamiyah_class")); subject = clean(request.args.get("subject")); _, error = _ensure_access(session_value, level, subject)
        if error: return jsonify({"success": False, "message": error}), 403
        payload = get_score_entry_roster(session_value, term, level, subject); workbook = Workbook(); sheet = workbook.active; sheet.title = "Islamiyah Scores"
        headers = ["S/N", "Regular Admission", "Academy ID", "Student Name", "Regular Class", "Islamiyah Class", f"CA /{CA_MAX}", f"Exam /{EXAM_MAX}", f"Total /{TOTAL_MAX}", "Status", "Saved At", "Saved By"]
        sheet.append(headers)
        for cell in sheet[1]: cell.font = Font(bold=True); cell.alignment = Alignment(horizontal="center", vertical="center")
        for index, student in enumerate(payload.get("students", []), 1):
            score = student.get("scores") or {}; sheet.append([index, student.get("regular_admission_number") or "—", student.get("academy_admission_number") or student.get("admission_number"), student.get("full_name"), student.get("regular_class"), student.get("islamiyah_class_label"), score.get("ca"), score.get("exam"), score.get("total"), "Complete" if score.get("complete") else "Pending", score.get("saved_at", ""), score.get("saved_by", "")])
        widths = [7, 18, 16, 32, 16, 20, 12, 12, 13, 14, 21, 18]
        for index, width in enumerate(widths, 1): sheet.column_dimensions[chr(64 + index)].width = width
        sheet.freeze_panes = "A2"; stream = BytesIO(); workbook.save(stream); stream.seek(0); safe_subject = "_".join(payload.get("subject", "subject").lower().split()); filename = f"islamiyah_{payload.get('islamiyah_class','').lower()}_{safe_subject}_{term.lower()}_{datetime.now().strftime('%Y%m%d')}.xlsx"
        return send_file(stream, as_attachment=True, download_name=filename, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except ValueError as error: return jsonify({"success": False, "message": str(error)}), 400


# Complete current register export includes both Tahfeez and Islamiyyah; restricted to the database administrator.
@islamiyah_bp.get("/api/islamiyah/database/export")
@islamiyah_admin_required
def api_combined_islamiyah_database_export():
    if not COMBINED_CSV.exists(): return jsonify({"success": False, "message": "The student register is unavailable."}), 404
    return send_file(COMBINED_CSV, as_attachment=True, download_name="Tahfeez_Islamiyyah_2026.csv", mimetype="text/csv")
