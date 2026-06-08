# modules/user_routes.py

from datetime import datetime, timedelta

from flask import Blueprint, render_template, redirect, url_for, session, request

from modules.student_lookup import (
    find_student_by_admission,
    student_name_matches,
    normalize_login_text,
)


user_bp = Blueprint("user_bp", __name__)


MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_MINUTES = 5

GENERIC_LOGIN_ERROR = (
    "Invalid login details. Please check your admission number and first or last name."
)


def get_login_identifier(admission_number):
    """
    Session-safe key for tracking failed attempts.
    """
    admission = normalize_login_text(admission_number)

    if admission:
        return f"student_login_attempts_{admission}"

    return "student_login_attempts_unknown"


def get_lockout_key(admission_number):
    admission = normalize_login_text(admission_number)

    if admission:
        return f"student_login_locked_until_{admission}"

    return "student_login_locked_until_unknown"


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


def register_failed_login(admission_number):
    attempt_key = get_login_identifier(admission_number)
    lockout_key = get_lockout_key(admission_number)

    attempts = int(session.get(attempt_key, 0)) + 1
    session[attempt_key] = attempts

    if attempts >= MAX_LOGIN_ATTEMPTS:
        locked_until = datetime.now() + timedelta(minutes=LOCKOUT_MINUTES)
        session[lockout_key] = locked_until.isoformat()
        session[attempt_key] = 0

        return True, locked_until

    return False, None


def clear_failed_login(admission_number):
    session.pop(get_login_identifier(admission_number), None)
    session.pop(get_lockout_key(admission_number), None)


def render_login_error(admission_number="", login_name="", error=GENERIC_LOGIN_ERROR):
    return render_template(
        "student_login.html",
        error=error,
        admission_number=admission_number,
        login_name=login_name,
        first_name=login_name,  # backward compatibility with old template value
    )


# =======================================================
# STUDENT LOGIN
# =======================================================
@user_bp.route("/student_login", methods=["GET", "POST"])
def student_login():
    if request.method == "POST":
        admission_number = request.form.get("admission_number", "").strip()

        # New field name is login_name, but keep first_name fallback
        # so old template/browser cache still works.
        login_name = (
            request.form.get("login_name", "")
            or request.form.get("first_name", "")
        ).strip()

        locked, locked_until = is_login_locked(admission_number)

        if locked:
            remaining_seconds = max(
                1,
                int((locked_until - datetime.now()).total_seconds())
            )
            remaining_minutes = max(1, remaining_seconds // 60)

            return render_login_error(
                admission_number=admission_number,
                login_name=login_name,
                error=(
                    f"Too many failed attempts. Please wait about "
                    f"{remaining_minutes} minute(s) before trying again."
                )
            )

        if not admission_number or not login_name:
            register_failed_login(admission_number)

            return render_login_error(
                admission_number=admission_number,
                login_name=login_name
            )

        student = find_student_by_admission(admission_number)

        if not student or not student_name_matches(student, login_name):
            locked_now, locked_until = register_failed_login(admission_number)

            if locked_now:
                return render_login_error(
                    admission_number=admission_number,
                    login_name=login_name,
                    error=(
                        f"Too many failed attempts. Please wait "
                        f"{LOCKOUT_MINUTES} minute(s) before trying again."
                    )
                )

            return render_login_error(
                admission_number=admission_number,
                login_name=login_name
            )

        clear_failed_login(admission_number)

        session.clear()

        session["user_type"] = "student"
        session["student"] = student

        # ==================================================
        # CLASS INFORMATION
        # ==================================================

        # Exact class arm
        # Examples:
        #   JSS1A
        #   JSS2C
        #   SS1_GOLD
        #   SS2_SILVER
        #   SS3_DIAMOND
        #   SS1B
        session["class"] = (
            student.get("class")
            or student.get("class_arm")
        )

        session["class_arm"] = (
            student.get("class_arm")
            or student.get("class")
        )

        # Broad class level
        # Examples:
        #   JSS1
        #   JSS2
        #   SS1
        #   SS2
        session["class_category"] = (
            student.get("class_category")
            or student.get("class_level")
        )

        session["class_level"] = (
            student.get("class_level")
            or student.get("class_category")
        )

        # SS stream awareness
        # SCIENCE / ART_COMMERCIAL / GENERAL
        session["stream"] = (
            student.get("stream")
            or student.get("ss_stream")
            or ""
        )

        session["ss_stream"] = (
            student.get("ss_stream")
            or student.get("stream")
            or ""
        )

        # ==================================================
        # EXAM STATE
        # ==================================================
        session["exam_started"] = False
        session["exam_submitted"] = False

        # ==================================================
        # AUDIT INFORMATION
        # ==================================================
        session["student_login_name_used"] = login_name
        session["student_login_time"] = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        return redirect(
            url_for("student_portal_bp.student_portal")
        )

    return render_template("student_login.html")


# =======================================================
# LOGOUT
# =======================================================
@user_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("user_bp.student_login"))