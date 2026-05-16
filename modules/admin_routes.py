# modules/admin_routes.py

from flask import Blueprint, request, session, redirect, url_for, jsonify, render_template, flash
from functools import wraps
from pathlib import Path
import csv

from engine import (
    generate_teacher_ids,
    get_all_teachers,
    validate_teacher_login,
    delete_teacher_from_db
)

from modules.promotion_manager import (
    get_class_summary,
    read_students,
    read_logs,
    promote_or_move_students,
    import_csv_to_class,
    CLASSES,
    DESTINATIONS,
)

import user_exam


admin_bp = Blueprint("admin_bp", __name__)

BASE_DIR = Path(__file__).resolve().parent.parent
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)


# ==========================================================
# DECORATORS
# ==========================================================
def admin_only(view_func):
    """Restrict access to admin users only."""
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if session.get("user_type") != "admin":
            flash("Access Restricted — Admin privileges required.", "error")
            return redirect(url_for("admin_bp.admin_login"))
        return view_func(*args, **kwargs)
    return wrapper


def teacher_allowed(view_func):
    """Allow both admin and teacher; block unauthenticated."""
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if session.get("user_type") not in ["admin", "teacher"]:
            return redirect(url_for("admin_bp.admin_login"))
        return view_func(*args, **kwargs)
    return wrapper


# ==========================================================
# UNIFIED ADMIN / TEACHER LOGIN
# ==========================================================
@admin_bp.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    from app import ADMIN_USERNAME, ADMIN_PASSWORD

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session.clear()
            session["user_type"] = "admin"
            session["username"] = username
            return redirect(url_for("admin_bp.admin_dashboard"))

        if validate_teacher_login(username, password):
            session.clear()
            session["user_type"] = "teacher"
            session["teacher_id"] = username
            return redirect(url_for("admin_bp.admin_teachers"))

        return render_template(
            "admin_login.html",
            error="Invalid Username or Password"
        )

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

    except Exception as e:
        print("Error generating IDs:", e)
        return jsonify({"error": str(e)}), 500


@admin_bp.route("/delete_teacher_id/<int:teacher_id>", methods=["DELETE"])
@admin_only
def delete_teacher_id(teacher_id):
    try:
        success = delete_teacher_from_db(teacher_id)
        return jsonify({"success": success})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


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
def admin_activities():
    return render_template("promotion.html", user_type="admin")


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
        with open(latest, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row in reader:
                creds.append({
                    "username": row.get("username", "").strip(),
                    "password": row.get("password", "").strip()
                })

    except Exception as e:
        print(f"Error reading credentials file: {e}")

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
    except Exception as e:
        print(f"DB fetch failed: {e}")

    if not results:
        files = sorted(LOGS_DIR.glob("exam_results_*.csv"), reverse=True)

        for file in files:
            try:
                with open(file, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)

                    for row in reader:
                        cleaned = {
                            k.strip(): (v or "").strip()
                            for k, v in row.items()
                        }
                        results.append(cleaned)

            except Exception as e:
                print(f"Error reading {file.name}: {e}")

    results.sort(key=lambda r: r.get("submitted_at", ""), reverse=True)

    return jsonify({"results": results})


# ==========================================================
# YEAR / CLASS / SUBJECT RESULTS PAGE
# ==========================================================
@admin_bp.route("/admin/results")
@teacher_allowed
def admin_results():
    return render_template(
        "admin_results.html",
        user_type=session.get("user_type")
    )



# =======================================================
# PROMOTION MANAGER
# =======================================================
@admin_bp.route("/admin/promotion")
def admin_promotion():
    return render_template(
        "promotion.html",
        classes=CLASSES,
        destinations=DESTINATIONS,
    )


@admin_bp.route("/api/promotion/summary")
def api_promotion_summary():
    return jsonify({
        "success": True,
        "summary": get_class_summary(),
    })


@admin_bp.route("/api/promotion/students")
def api_promotion_students():
    class_category = request.args.get("class", "JSS1")
    rows = read_students(class_category)

    return jsonify({
        "success": True,
        "class": class_category,
        "students": rows,
        "count": len(rows),
    })


@admin_bp.route("/api/promotion/logs")
def api_promotion_logs():
    return jsonify({
        "success": True,
        "logs": read_logs(),
    })


@admin_bp.route("/api/promotion/promote", methods=["POST"])
def api_promote_students():
    data = request.get_json(silent=True) or {}

    success, message, payload = promote_or_move_students(
        from_class=data.get("from_class"),
        to_class=data.get("to_class"),
        admissions=data.get("admissions") or [],
        mode=data.get("mode", "selected"),
        destination_arm=data.get("destination_arm", ""),
        note=data.get("note", ""),
    )

    return jsonify({
        "success": success,
        "message": message,
        "data": payload,
    }), 200 if success else 400


@admin_bp.route("/api/promotion/import", methods=["POST"])
def api_import_students():
    success, message, payload = import_csv_to_class(
        target_class=request.form.get("target_class"),
        uploaded_file=request.files.get("csv_file"),
        mode=request.form.get("mode", "append"),
    )

    return jsonify({
        "success": success,
        "message": message,
        "data": payload,
    }), 200 if success else 400


# ==========================================================
# LOGOUT
# ==========================================================
@admin_bp.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_bp.admin_login"))