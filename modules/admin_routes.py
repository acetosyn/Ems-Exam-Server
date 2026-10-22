# MODULE: Admin Routes — Admin/teacher authentication, dashboards and protected administrative pages

import os
import csv
import time
from functools import wraps
from pathlib import Path

from flask import Blueprint, request, session, redirect, url_for, jsonify, render_template, flash

from modules.teacher_assignment_manager import delete_teacher_assignments, replace_teacher_assignments, validate_teacher_assignment_payload, teacher_report_scope
from modules.staff_identity_manager import delete_staff_account, generate_staff_ids, get_staff_account, list_staff_accounts, list_staff_identity_audit, set_staff_status, staff_identity_stats, validate_staff_login
from modules.school_structure import class_label, hybrid_class_label, basic_class_reference
from modules.class_config import SUPPORTED_CLASSES, STUDENT_DATABASE_CLASSES, TAHFEEZ_CLASSES, ISLAMIYAH_CLASSES, CLASS_ARMS_BY_LEVEL
from modules.system_readiness import build_system_readiness

import user_exam


admin_bp = Blueprint("admin_bp", __name__)

BASE_DIR = Path(__file__).resolve().parent.parent
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

CLASSES = list(SUPPORTED_CLASSES)
CLASS_ARMS = CLASS_ARMS_BY_LEVEL
OPERATIONAL_CLASSES = list(STUDENT_DATABASE_CLASSES) + list(TAHFEEZ_CLASSES) + list(ISLAMIYAH_CLASSES)
OPERATIONAL_CLASS_ARMS = {**CLASS_ARMS_BY_LEVEL, **{level: [level] for level in (list(TAHFEEZ_CLASSES) + list(ISLAMIYAH_CLASSES))}}
OPERATIONAL_CLASS_LABELS = {level: class_label(level) for level in OPERATIONAL_CLASSES}


def report_page_access_scope():
    """Resolve the class/arm menu that the current Report Sheets user is allowed to open.

    Normal EMT teachers receive only the classes/arms saved against their Staff ID. Teacher
    Admin keeps every regular-school class; central Admin keeps the complete operational list.
    The API repeats the same policy, so this server-rendered filter is a first-line UX guard, not
    the security boundary.
    """
    role = str(session.get("user_type") or "").strip().lower(); classes = list(OPERATIONAL_CLASSES); arms = {key:list(value or []) for key,value in OPERATIONAL_CLASS_ARMS.items()}
    if role == "teacher":
        teacher_id = str(session.get("teacher_id") or session.get("username") or "").strip(); scope = teacher_report_scope(teacher_id, "")
        allowed_levels = set(scope.get("class_levels") or []); classes = [level for level in classes if level in allowed_levels]
        arms = {level:[arm for arm in arms.get(level, []) if not scope.get("class_arms", {}).get(level) or arm in set(scope.get("class_arms", {}).get(level) or [])] for level in classes}
        return classes, arms, scope
    if role == "teacher_admin":
        classes = [level for level in classes if not (level in TAHFEEZ_CLASSES or level in ISLAMIYAH_CLASSES)]; arms = {level:arms.get(level, []) for level in classes}
        return classes, arms, {"class_levels":classes,"class_arms":arms,"subjects":{},"assignments":[],"full_regular_school_access":True}
    return classes, arms, {"class_levels":classes,"class_arms":arms,"subjects":{},"assignments":[],"central_admin":True}


# ==========================================================
# ADMIN / TEACHER SESSION
# ==========================================================

STAFF_SESSION_TIMEOUT_SECONDS = 2 * 60 * 60
STAFF_SESSION_ACTIVITY_KEY = "_staff_last_activity"


def start_staff_session(user_type, username, teacher_id=None):
    session.clear()
    session.permanent = True

    role = str(user_type or "").strip().lower()

    session["user_type"] = role
    session["username"] = str(username or "").strip()

    session["staff_role"] = role
    if role == "admin": session["admin_username"] = username
    if role in {"teacher", "teacher_admin", "islamiyyah_teacher"} and teacher_id: session["teacher_id"] = teacher_id

    session[STAFF_SESSION_ACTIVITY_KEY] = time.time()
    session.modified = True


def refresh_staff_session():
    role = str(session.get("user_type") or "").strip().lower()

    if role not in {"admin", "teacher", "teacher_admin", "islamiyyah_teacher"}:
        return False

    # Staff-account status is revalidated on every protected request so disabling/deleting an EMT/IMS ID revokes the active session immediately.
    if role in {"teacher", "teacher_admin", "islamiyyah_teacher"}:
        staff_id = str(session.get("teacher_id") or session.get("username") or "").strip(); account = get_staff_account(staff_id)
        if not account or account.get("status") != "active" or account.get("staff_role") != role:
            session.clear(); return False

    now = time.time()
    last_activity = session.get(STAFF_SESSION_ACTIVITY_KEY)

    if last_activity is not None:
        try:
            elapsed = now - float(last_activity)

            if elapsed > STAFF_SESSION_TIMEOUT_SECONDS:
                print(f"[STAFF SESSION] {role} session expired after {round(elapsed / 3600, 2)} hour(s) inactivity.")
                session.clear()
                return False

        except (TypeError, ValueError):
            pass

    session.permanent = True
    session[STAFF_SESSION_ACTIVITY_KEY] = now
    session.modified = True

    return True


# ==========================================================
# DECORATORS
# ==========================================================

def admin_only(view_func):
    """Restrict access to Admin users only."""

    @wraps(view_func)
    def wrapper(*args, **kwargs):
        role = str(session.get("user_type") or "").strip().lower()

        if role != "admin":
            if str(request.path or "").startswith("/api/"): return jsonify({"success": False, "error": "Administrator privileges are required."}), 403
            flash("Access Restricted — Administrator privileges are required.", "error")
            return redirect(url_for("admin_bp.admin_dashboard") if role in {"teacher", "teacher_admin", "islamiyyah_teacher"} else url_for("admin_bp.admin_login"))

        if not refresh_staff_session():
            flash("Your Admin session expired after 2 hours of inactivity. Please log in again.", "warning")
            return redirect(url_for("admin_bp.admin_login"))

        return view_func(*args, **kwargs)

    return wrapper


def staff_allowed(view_func):
    """Allow every authenticated EMIS staff role: Admin, Teacher Admin, normal Teacher and Islamiyyah Teacher."""

    @wraps(view_func)
    def wrapper(*args, **kwargs):
        role = str(session.get("user_type") or "").strip().lower()
        if role not in {"admin", "teacher", "teacher_admin", "islamiyyah_teacher"}: return redirect(url_for("admin_bp.admin_login"))
        if not refresh_staff_session():
            flash("Your session expired after 2 hours of inactivity. Please log in again.", "warning"); return redirect(url_for("admin_bp.admin_login"))
        return view_func(*args, **kwargs)
    return wrapper


def teacher_allowed(view_func):
    """Allow central Admin + Teacher Admin + normal Teacher. Islamiyyah Teacher accounts are intentionally excluded."""

    @wraps(view_func)
    def wrapper(*args, **kwargs):
        role = str(session.get("user_type") or "").strip().lower()
        if role not in {"admin", "teacher", "teacher_admin"}:
            flash("Access Restricted — this module is not available to your staff role.", "error"); return redirect(url_for("admin_bp.admin_dashboard") if role in {"teacher","teacher_admin","islamiyyah_teacher"} else url_for("admin_bp.admin_login"))
        if not refresh_staff_session():
            flash("Your session expired after 2 hours of inactivity. Please log in again.", "warning"); return redirect(url_for("admin_bp.admin_login"))
        return view_func(*args, **kwargs)
    return wrapper


def islamiyyah_allowed(view_func):
    """Allow only Admin + Islamiyyah Teacher accounts."""

    @wraps(view_func)
    def wrapper(*args, **kwargs):
        role = str(session.get("user_type") or "").strip().lower()
        if role not in {"admin", "islamiyyah_teacher"}:
            flash("Access Restricted — Tahfeez & Islamiyyah is reserved for Admin and Islamiyyah staff.", "error"); return redirect(url_for("admin_bp.admin_dashboard") if role in {"teacher", "teacher_admin"} else url_for("admin_bp.admin_login"))
        if not refresh_staff_session():
            flash("Your session expired after 2 hours of inactivity. Please log in again.", "warning"); return redirect(url_for("admin_bp.admin_login"))
        return view_func(*args, **kwargs)
    return wrapper


# ==========================================================
# UNIFIED ADMIN / TEACHER LOGIN
# ==========================================================

@admin_bp.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        admin_username = os.getenv("ADMIN_USERNAME", "").strip()
        admin_password = os.getenv("ADMIN_PASSWORD", "").strip()

        if admin_username and admin_password and username == admin_username and password == admin_password:
            start_staff_session("admin", username)
            return redirect(url_for("admin_bp.admin_dashboard"))

        staff_account = validate_staff_login(username, password)
        if staff_account:
            role = staff_account.get("staff_role") or "teacher"; staff_id = staff_account.get("staff_id") or username
            start_staff_session(role, staff_id, teacher_id=staff_id)
            return redirect(url_for("admin_bp.admin_dashboard"))

        return render_template("admin_login.html", error="Invalid Username or Password")

    return render_template("admin_login.html")


# ==========================================================
# TEACHER ID GENERATION
# ==========================================================

@admin_bp.route("/generate_teacher_ids", methods=["GET", "POST"])
@admin_only
def generate_teacher_ids_api():
    """Legacy EMT endpoint kept read-compatible; credential creation must use the assignment-aware ID API."""
    try:
        if request.method == "POST": return jsonify({"error": "Use Academic Admin → IDs & Access to generate Teacher IDs with class and subject assignments."}), 409
        return jsonify({"teachers": list_staff_accounts("teacher", include_password=True)})
    except ValueError as error: return jsonify({"error": str(error)}), 400
    except Exception as error:
        print("Error loading Teacher IDs:", error); return jsonify({"error": str(error)}), 500


@admin_bp.route("/api/staff-ids", methods=["GET", "POST"])
@admin_only
def staff_ids_api():
    try:
        if request.method == "POST":
            payload = request.get_json(silent=True) or request.form; role = payload.get("staff_role") or payload.get("role") or "teacher"; assignments = payload.get("assignments") or []; academic_session = payload.get("academic_session") or ""; actor=session.get("username") or "EMIS Admin"; generated=[]
            if role == "teacher": validate_teacher_assignment_payload(assignments, academic_session, role, require_assignment=True)
            try:
                generated = generate_staff_ids(role, payload.get("count", 1), created_by=actor)
                if role == "teacher":
                    for account in generated: replace_teacher_assignments(account.get("staff_id"), assignments, academic_session, changed_by=actor)
                elif role == "islamiyyah_teacher":
                    # IMS is a page-scoped Academy role, not a class/subject-scoped Report Sheets role.
                    # Clear any legacy assignment rows if a deleted IMS number has been recycled.
                    for account in generated: delete_teacher_assignments(account.get("staff_id"))
            except Exception:
                for account in generated:
                    try: delete_staff_account(account.get("id"), changed_by=actor)
                    except Exception: pass
                raise
            return jsonify({"success": True, "message": f"{len(generated)} staff credential(s) generated" + (" and teaching access saved." if role == "teacher" else "."), "generated": generated, "accounts": list_staff_accounts(include_password=True), "stats": staff_identity_stats()})
        return jsonify({"success": True, "accounts": list_staff_accounts(request.args.get("role", ""), include_password=True), "stats": staff_identity_stats(), "audit": list_staff_identity_audit(60)})
    except ValueError as error: return jsonify({"success": False, "error": str(error)}), 400
    except Exception as error:
        print("[STAFF IDS] Request failed:", error); return jsonify({"success": False, "error": "Unable to load staff credentials."}), 500


@admin_bp.route("/api/staff-ids/<int:row_id>", methods=["PATCH", "DELETE"])
@admin_only
def staff_id_record_api(row_id):
    try:
        if request.method == "DELETE":
            deleted = delete_staff_account(row_id, changed_by=session.get("username") or "EMIS Admin")
            if not deleted: return jsonify({"success": False, "error": "Staff credential was not found. Refresh the register and try again."}), 404
            return jsonify({"success": True, "accounts": list_staff_accounts(include_password=True), "stats": staff_identity_stats(), "audit": list_staff_identity_audit(60)})
        payload = request.get_json(silent=True) or {}; account = set_staff_status(row_id, payload.get("status"), changed_by=session.get("username") or "EMIS Admin"); return jsonify({"success": True, "account": account, "accounts": list_staff_accounts(include_password=True), "stats": staff_identity_stats(), "audit": list_staff_identity_audit(60)})
    except ValueError as error: return jsonify({"success": False, "error": str(error)}), 400
    except Exception as error: return jsonify({"success": False, "error": str(error)}), 500


@admin_bp.route("/delete_teacher_id/<int:teacher_id>", methods=["DELETE"])
@admin_only
def delete_teacher_id(teacher_id):
    try: return jsonify({"success": delete_staff_account(teacher_id, changed_by=session.get("username") or "EMIS Admin")})
    except Exception as error: return jsonify({"success": False, "error": str(error)}), 500


# ==========================================================
# DASHBOARD & EXISTING STAFF PAGES
# ==========================================================

@admin_bp.route("/admin")
@admin_bp.route("/admin/dashboard")
@staff_allowed
def admin_dashboard():
    return render_template("dashboard.html", user_type=session.get("user_type"))


@admin_bp.route("/admin/teachers")
@admin_only
def admin_teachers():
    user_type = session.get("user_type")
    legacy_tool = request.args.get("open", "").strip().lower()
    if user_type == "admin" and legacy_tool in {"uploads", "convert"}: return render_template("teachers.html", user_type="admin")
    if user_type == "admin":
        initial_view = request.args.get("view", "teachers").strip().lower()
        if initial_view not in {"teachers", "subjects", "ids"}: initial_view = "teachers"
        return render_template("academic_admin.html", user_type="admin", initial_view=initial_view)
    return render_template("teachers.html", user_type=user_type)


@admin_bp.route("/admin/convert")
@teacher_allowed
def admin_convert():
    return render_template("convert.html", user_type=session.get("user_type"), classes=CLASSES, class_arms=CLASS_ARMS)


@admin_bp.route("/admin/students")
@teacher_allowed
def admin_students():
    return render_template("students.html", user_type=session.get("user_type"))


# ==========================================================
# STAFF MANAGEMENT MODULES
# ==========================================================

@admin_bp.route("/admin/attendance")
@teacher_allowed
def admin_attendance():
    return render_template("attendance.html", user_type=session.get("user_type"), classes=OPERATIONAL_CLASSES, class_arms=OPERATIONAL_CLASS_ARMS, class_labels=OPERATIONAL_CLASS_LABELS)


@admin_bp.route("/admin/ca-tests")
@teacher_allowed
def admin_ca_tests():
    return render_template("ca_test.html", user_type=session.get("user_type"), classes=OPERATIONAL_CLASSES, class_arms=OPERATIONAL_CLASS_ARMS, class_labels=OPERATIONAL_CLASS_LABELS)


@admin_bp.route("/admin/islamiyah")
@islamiyyah_allowed
def admin_islamiyah():
    return render_template("islamiyah.html", user_type=session.get("user_type"))


 # Report Sheets are available to Admin, Teacher Admin and normal Teacher accounts. Islamiyyah staff are excluded by role policy.
@admin_bp.route("/admin/report-sheets")
@teacher_allowed
def admin_report_sheets():
    classes, class_arms, report_access_scope = report_page_access_scope()
    return render_template("report_sheets.html", user_type=session.get("user_type"), classes=classes, class_arms=class_arms, class_labels=OPERATIONAL_CLASS_LABELS, report_access_scope=report_access_scope)


@admin_bp.route("/admin/academic-history")
@admin_only
def admin_academic_history():
    return render_template("academic_history.html", user_type="admin")


@admin_bp.route("/admin/cumulative-results")
@admin_only
def admin_cumulative_results():
    # The standalone cumulative page has been retired. Annual / three-term compilation now lives inside Report Sheets.
    return redirect(url_for("admin_bp.admin_report_sheets", view="cumulative", _anchor="reportCumulativeHub"))


@admin_bp.route("/admin/broadsheets")
@admin_only
def admin_broadsheets():
    # Retired standalone page: class matrices now live inside Academic History.
    args = request.args.to_dict(flat=True); args["view"] = "broadsheets"
    return redirect(url_for("admin_bp.admin_academic_history", **args))


# ==========================================================
# LEGACY ROUTE COMPATIBILITY
# ==========================================================

@admin_bp.route("/admin/past_questions")
@teacher_allowed
def admin_past_questions():
    return redirect(url_for("admin_bp.admin_attendance"))


@admin_bp.route("/admin/mock_exam")
@teacher_allowed
def admin_mock_exam():
    return redirect(url_for("admin_bp.admin_ca_tests"))


@admin_bp.route("/admin/third_party")
@admin_only
def admin_third_party():
    return redirect(url_for("admin_bp.admin_report_sheets"))


# ==========================================================
# ADMIN-ONLY SECTIONS
# ==========================================================

@admin_bp.route("/admin/ids")
@admin_only
def admin_ids():
    return redirect(url_for("admin_bp.admin_teachers", view="ids"))


@admin_bp.route("/admin/promotion")
@staff_allowed
def admin_promotion():
    return render_template("promotion.html", user_type=session.get("user_type"), classes=list(STUDENT_DATABASE_CLASSES), class_arms=CLASS_ARMS, class_labels={level: hybrid_class_label(level) for level in STUDENT_DATABASE_CLASSES}, basic_class_map=basic_class_reference())


@admin_bp.route("/admin/subjects")
@admin_only
def admin_subjects():
    return redirect(url_for("admin_bp.admin_teachers", view="subjects"))


@admin_bp.route("/admin/settings")
@teacher_allowed
def admin_settings():
    role = str(session.get("user_type") or "").strip().lower()
    if role == "teacher":
        flash("Access Restricted — the active academic period is controlled by Admin / Teacher Admin and is applied automatically to Teacher workspaces.", "warning")
        return redirect(url_for("admin_bp.admin_dashboard"))
    return render_template("settings.html", user_type=role)


@admin_bp.route("/api/system-readiness")
@staff_allowed
def api_system_readiness():
    return jsonify(build_system_readiness())


@admin_bp.route("/admin/support")
@staff_allowed
def admin_support():
    return render_template("support.html", user_type=session.get("user_type"))


@admin_bp.route("/admin/dash_results")
@admin_only
def admin_dash_results():
    return render_template("dash_results.html", user_type="admin")


# ==========================================================
# VIEW CREDENTIALS
# ==========================================================

@admin_bp.route("/view_credentials")
@admin_only
def view_credentials():
    files = sorted(LOGS_DIR.glob("credentials_*.csv"), reverse=True)

    if not files:
        return jsonify({"credentials": []})

    latest = files[0]
    creds = []

    try:
        with open(latest, "r", encoding="utf-8") as file:
            reader = csv.DictReader(file)

            for row in reader:
                creds.append({
                    "username": row.get("username", "").strip(),
                    "password": row.get("password", "").strip()
                })

    except Exception as error:
        print(f"Error reading credentials file: {error}")

    return jsonify({"credentials": creds})


# ==========================================================
# VIEW OLD MOCK EXAM RESULTS
# ==========================================================

@admin_bp.route("/view_results")
@admin_only
def view_results():
    results = []

    try:
        results = user_exam.get_exam_results() or []

    except Exception as error:
        print(f"DB fetch failed: {error}")

    if not results:
        files = sorted(LOGS_DIR.glob("exam_results_*.csv"), reverse=True)

        for file in files:
            try:
                with open(file, "r", encoding="utf-8") as result_file:
                    reader = csv.DictReader(result_file)

                    for row in reader:
                        cleaned = {key.strip(): (value or "").strip() for key, value in row.items()}
                        results.append(cleaned)

            except Exception as error:
                print(f"Error reading {file.name}: {error}")

    results.sort(key=lambda row: row.get("submitted_at", ""), reverse=True)

    return jsonify({"results": results})


# ==========================================================
# YEAR / CLASS / SUBJECT RESULTS PAGE
# ==========================================================

@admin_bp.route("/admin/results")
@teacher_allowed
def admin_results():
    return render_template("admin_results.html", user_type=session.get("user_type"))


# ==========================================================
# LOGOUT
# ==========================================================

@admin_bp.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_bp.admin_login"))
