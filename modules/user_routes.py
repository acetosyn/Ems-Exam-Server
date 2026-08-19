# modules/user_routes.py

from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, session, request

from modules.student_lookup import authenticate_student, normalize_login_text
from modules.api_routes import push_admin_notification


user_bp = Blueprint("user_bp", __name__)


# =========================================================
# LOGIN SECURITY CONFIG
# =========================================================

MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_MINUTES = 5

GENERIC_LOGIN_ERROR = "Invalid login details. Please check your admission number and first or last name."


# =========================================================
# LOGIN ATTEMPT KEYS
# =========================================================

def get_login_identifier(admission_number):
    admission = normalize_login_text(admission_number)
    return f"student_login_attempts_{admission}" if admission else "student_login_attempts_unknown"


def get_lockout_key(admission_number):
    admission = normalize_login_text(admission_number)
    return f"student_login_locked_until_{admission}" if admission else "student_login_locked_until_unknown"


# =========================================================
# LOCKOUT CHECK
# =========================================================

def is_login_locked(admission_number):
    key = get_lockout_key(admission_number)
    locked_until_raw = session.get(key)

    if not locked_until_raw:
        return False, None

    try:
        locked_until = datetime.fromisoformat(locked_until_raw)
    except Exception:
        session.pop(key, None)
        return False, None

    if datetime.now() >= locked_until:
        session.pop(key, None)
        session.pop(get_login_identifier(admission_number), None)
        return False, None

    return True, locked_until


# =========================================================
# FAILED LOGIN TRACKING
# =========================================================

def register_failed_login(admission_number):
    attempt_key = get_login_identifier(admission_number)
    lockout_key = get_lockout_key(admission_number)

    try:
        attempts = int(session.get(attempt_key, 0)) + 1
    except (TypeError, ValueError):
        attempts = 1

    session[attempt_key] = attempts

    if attempts < MAX_LOGIN_ATTEMPTS:
        return False, None

    locked_until = datetime.now() + timedelta(minutes=LOCKOUT_MINUTES)

    session[lockout_key] = locked_until.isoformat()
    session[attempt_key] = 0

    return True, locked_until


def clear_failed_login(admission_number):
    session.pop(get_login_identifier(admission_number), None)
    session.pop(get_lockout_key(admission_number), None)


# =========================================================
# LOGIN ERROR
# =========================================================

def render_login_error(admission_number="", login_name="", error=GENERIC_LOGIN_ERROR):
    return render_template("student_login.html", error=error, admission_number=admission_number, login_name=login_name, first_name=login_name)


# =========================================================
# BUILD SAFE STUDENT SESSION
# =========================================================

def build_session_student(student):
    admission = student.get("admission_number")
    class_arm = student.get("class_arm") or student.get("class") or ""
    class_level = student.get("class_level") or student.get("class_category") or ""
    stream = student.get("stream") or student.get("ss_stream") or ""

    return {
        "id": student.get("id") or admission,
        "admission_number": admission,

        "last_name": student.get("last_name", ""),
        "first_name": student.get("first_name", ""),
        "other_names": student.get("other_names", ""),
        "full_name": student.get("full_name", ""),

        "phone": student.get("phone", ""),
        "sex": student.get("sex", ""),

        "class": class_arm,
        "class_arm": class_arm,
        "class_category": class_level,
        "class_level": class_level,

        "stream": stream,
        "ss_stream": stream,

        "status": student.get("status", "ACTIVE"),
        "is_active": student.get("is_active", True),

        "login_name_tokens": student.get("login_name_tokens", []),
    }


# =========================================================
# REAL-TIME LOGIN NOTIFICATION
# =========================================================

def notify_student_login(student):
    """
    Pushes a live event to the Admin Results notification stream.

    Notification failure must NEVER prevent a student from logging in.
    """

    try:
        student_name = student.get("full_name") or f'{student.get("first_name", "")} {student.get("last_name", "")}'.strip() or "Student"
        admission_number = student.get("admission_number") or student.get("id") or ""
        class_arm = student.get("class_arm") or student.get("class") or ""
        class_level = student.get("class_level") or student.get("class_category") or ""
        stream = student.get("stream") or student.get("ss_stream") or ""

        push_admin_notification(
            "login",
            f"{student_name} logged into the CBT portal.",
            {
                "student_name": student_name,
                "admission_number": admission_number,
                "class": class_arm,
                "class_arm": class_arm,
                "class_category": class_level,
                "class_level": class_level,
                "stream": stream,
            }
        )

    except Exception as error:
        print("STUDENT LOGIN NOTIFICATION ERROR:", error)


# =========================================================
# STUDENT LOGIN
# =========================================================

@user_bp.route("/student_login", methods=["GET", "POST"])
def student_login():

    # -----------------------------------------------------
    # GET
    # -----------------------------------------------------

    if request.method == "GET":
        if session.get("user_type") == "student" and session.get("student"):
            return redirect(url_for("student_portal_bp.student_portal"))

        return render_template("student_login.html")


    # -----------------------------------------------------
    # POST — LOGIN INPUT
    # -----------------------------------------------------

    admission_number = request.form.get("admission_number", "").strip()
    login_name = (request.form.get("login_name", "") or request.form.get("first_name", "")).strip()


    # -----------------------------------------------------
    # LOCKOUT CHECK
    # -----------------------------------------------------

    locked, locked_until = is_login_locked(admission_number)

    if locked:
        remaining_seconds = max(1, int((locked_until - datetime.now()).total_seconds()))
        remaining_minutes = max(1, (remaining_seconds + 59) // 60)

        return render_login_error(
            admission_number=admission_number,
            login_name=login_name,
            error=f"Too many failed attempts. Please wait about {remaining_minutes} minute(s) before trying again."
        )


    # -----------------------------------------------------
    # REQUIRED FIELDS
    # -----------------------------------------------------

    if not admission_number or not login_name:
        locked_now, _ = register_failed_login(admission_number)

        if locked_now:
            return render_login_error(
                admission_number=admission_number,
                login_name=login_name,
                error=f"Too many failed attempts. Please wait {LOCKOUT_MINUTES} minute(s) before trying again."
            )

        return render_login_error(admission_number=admission_number, login_name=login_name)


    # -----------------------------------------------------
    # AUTHENTICATE STUDENT
    # -----------------------------------------------------

    student = authenticate_student(admission_number, login_name)

    if not student:
        locked_now, _ = register_failed_login(admission_number)

        if locked_now:
            return render_login_error(
                admission_number=admission_number,
                login_name=login_name,
                error=f"Too many failed attempts. Please wait {LOCKOUT_MINUTES} minute(s) before trying again."
            )

        return render_login_error(admission_number=admission_number, login_name=login_name)


    # =====================================================
    # SUCCESSFUL LOGIN
    # =====================================================

    clear_failed_login(admission_number)

    # Clear previous admin/teacher/student session only after
    # authentication has succeeded.
    session.clear()

    student_session = build_session_student(student)


    # =====================================================
    # MAIN STUDENT SESSION
    # =====================================================

    session["user_type"] = "student"
    session["student"] = student_session

    session["student_id"] = student_session.get("id")
    session["admission_number"] = student_session.get("admission_number")


    # =====================================================
    # STUDENT NAME
    # =====================================================

    session["student_name"] = student_session.get("full_name", "")
    session["first_name"] = student_session.get("first_name", "")
    session["last_name"] = student_session.get("last_name", "")


    # =====================================================
    # SEX / GENDER
    # =====================================================

    session["sex"] = student_session.get("sex") or ""
    session["gender"] = student_session.get("sex") or ""


    # =====================================================
    # CLASS
    # =====================================================

    session["class"] = student_session.get("class") or student_session.get("class_arm")
    session["class_arm"] = student_session.get("class_arm") or student_session.get("class")

    session["class_category"] = student_session.get("class_category") or student_session.get("class_level")
    session["class_level"] = student_session.get("class_level") or student_session.get("class_category")


    # =====================================================
    # SS STREAM
    # =====================================================

    session["stream"] = student_session.get("stream") or student_session.get("ss_stream") or ""
    session["ss_stream"] = student_session.get("ss_stream") or student_session.get("stream") or ""


    # =====================================================
    # STUDENT STATUS
    # =====================================================

    session["student_status"] = student_session.get("status", "ACTIVE")


    # =====================================================
    # INITIAL EXAM STATE
    # =====================================================

    session["exam_started"] = False
    session["exam_submitted"] = False

    session.pop("selected_subject", None)
    session.pop("selected_year", None)
    session.pop("selected_class_level", None)
    session.pop("selected_class_arm", None)


    # =====================================================
    # LOGIN AUDIT
    # =====================================================

    session["student_login_name_used"] = login_name
    session["student_login_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


    # =====================================================
    # REAL-TIME ADMIN NOTIFICATION
    #
    # IMPORTANT:
    # This occurs only AFTER successful authentication.
    # Failed login attempts do NOT produce admin activity cards.
    # =====================================================

    notify_student_login(student_session)


    # =====================================================
    # ENTER STUDENT PORTAL
    # =====================================================

    return redirect(url_for("student_portal_bp.student_portal"))


# =========================================================
# LOGOUT
# =========================================================

@user_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("user_bp.student_login"))