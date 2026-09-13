# MODULE: Admin Routes — Admin/teacher authentication, dashboards and protected administrative pages

import os
import csv
import time
from functools import wraps
from pathlib import Path

from flask import Blueprint, request, session, redirect, url_for, jsonify, render_template, flash

from engine import generate_teacher_ids, get_all_teachers, validate_teacher_login, delete_teacher_from_db
from modules.class_config import SUPPORTED_CLASSES, CLASS_ARMS_BY_LEVEL

import user_exam


admin_bp = Blueprint("admin_bp", __name__)

BASE_DIR = Path(__file__).resolve().parent.parent
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

CLASSES = list(SUPPORTED_CLASSES)
CLASS_ARMS = CLASS_ARMS_BY_LEVEL


# ==========================================================
# ADMIN / TEACHER SESSION
#
# Staff sessions remain active while being used.
# They expire only after 2 hours without staff activity.
# ==========================================================

STAFF_SESSION_TIMEOUT_SECONDS = 2 * 60 * 60
STAFF_SESSION_ACTIVITY_KEY = "_staff_last_activity"


def start_staff_session(user_type, username, teacher_id=None):
    session.clear()
    session.permanent = True

    role = str(user_type or "").strip().lower()

    session["user_type"] = role
    session["username"] = str(username or "").strip()

    if role == "admin":
        session["admin_username"] = username

    if role == "teacher" and teacher_id:
        session["teacher_id"] = teacher_id

    session[STAFF_SESSION_ACTIVITY_KEY] = time.time()
    session.modified = True


def refresh_staff_session():
    role = str(session.get("user_type") or "").strip().lower()

    if role not in {"admin", "teacher"}:
        return False

    now = time.time()
    last_activity = session.get(STAFF_SESSION_ACTIVITY_KEY)

    if last_activity is not None:
        try:
            elapsed = now - float(last_activity)

            if elapsed > STAFF_SESSION_TIMEOUT_SECONDS:
                print(
                    f"[STAFF SESSION] {role} session expired after "
                    f"{round(elapsed / 3600, 2)} hour(s) inactivity."
                )
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
            flash("Access Restricted — Admin privileges required.", "error")
            return redirect(url_for("admin_bp.admin_login"))

        if not refresh_staff_session():
            flash("Your Admin session expired after 2 hours of inactivity. Please log in again.", "warning")
            return redirect(url_for("admin_bp.admin_login"))

        return view_func(*args, **kwargs)

    return wrapper


def teacher_allowed(view_func):
    """Allow Admin and Teacher users while maintaining the 20-minute staff session."""

    @wraps(view_func)
    def wrapper(*args, **kwargs):
        role = str(session.get("user_type") or "").strip().lower()

        if role not in {"admin", "teacher"}:
            return redirect(url_for("admin_bp.admin_login"))

        if not refresh_staff_session():
            flash("Your session expired after 2 hours of inactivity. Please log in again.", "warning")
            return redirect(url_for("admin_bp.admin_login"))

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

        if validate_teacher_login(username, password):
            start_staff_session("teacher", username, teacher_id=username)
            return redirect(url_for("admin_bp.admin_teachers"))

        return render_template("admin_login.html", error="Invalid Username or Password")

    return render_template("admin_login.html")


# ==========================================================
# TEACHER ID GENERATION
# ==========================================================

@admin_bp.route("/generate_teacher_ids", methods=["GET", "POST"])
@admin_only
def generate_teacher_ids_api():
    try:
        if request.method == "POST":
            num = int(request.form.get("count", 1))

            if num < 1 or num > 100:
                return jsonify({"error": "Invalid count"}), 400

            generated = generate_teacher_ids(count=num)
            all_teachers = get_all_teachers()

            return jsonify({
                "message": f"{len(generated)} Teacher IDs generated successfully.",
                "generated": generated,
                "teachers": all_teachers
            })

        return jsonify({"teachers": get_all_teachers()})

    except Exception as error:
        print("Error generating IDs:", error)
        return jsonify({"error": str(error)}), 500


@admin_bp.route("/delete_teacher_id/<int:teacher_id>", methods=["DELETE"])
@admin_only
def delete_teacher_id(teacher_id):
    try:
        success = delete_teacher_from_db(teacher_id)
        return jsonify({"success": success})

    except Exception as error:
        return jsonify({"success": False, "error": str(error)}), 500


# ==========================================================
# DASHBOARD & SUB-PAGES
# ==========================================================

@admin_bp.route("/admin")
@admin_bp.route("/admin/dashboard")
@admin_only
def admin_dashboard():
    return render_template("dashboard.html", user_type="admin")


@admin_bp.route("/admin/teachers")
@teacher_allowed
def admin_teachers():
    return render_template("teachers.html", user_type=session.get("user_type"))


@admin_bp.route("/admin/convert")
@teacher_allowed
def admin_convert():
    return render_template("convert.html", user_type=session.get("user_type"), classes=CLASSES, class_arms=CLASS_ARMS)


@admin_bp.route("/admin/students")
@teacher_allowed
def admin_students():
    return render_template("students.html", user_type=session.get("user_type"))


@admin_bp.route("/admin/past_questions")
@teacher_allowed
def admin_past_questions():
    return render_template("past_questions.html", user_type=session.get("user_type"))


@admin_bp.route("/admin/mock_exam")
@teacher_allowed
def admin_mock_exam():
    return render_template("mock_exam.html", user_type=session.get("user_type"))


# ==========================================================
# ADMIN-ONLY SECTIONS
# ==========================================================

@admin_bp.route("/admin/ids")
@admin_only
def admin_ids():
    return render_template("ids.html", user_type="admin")


@admin_bp.route("/admin/third_party")
@admin_only
def admin_third_party():
    return render_template("third_party.html", user_type="admin")


@admin_bp.route("/admin/promotion")
@admin_only
def admin_promotion():
    return render_template("promotion.html", user_type="admin", classes=CLASSES, class_arms=CLASS_ARMS)


@admin_bp.route("/admin/settings")
@admin_only
def admin_settings():
    return render_template("settings.html", user_type="admin")


@admin_bp.route("/admin/support")
@admin_only
def admin_support():
    return render_template("support.html", user_type="admin")


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