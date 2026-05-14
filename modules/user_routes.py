# modules/user_routes.py

from flask import Blueprint, render_template, redirect, url_for, session, request

from modules.student_lookup import find_student_by_admission


user_bp = Blueprint("user_bp", __name__)


# =======================================================
# STUDENT LOGIN
# =======================================================
@user_bp.route("/student_login", methods=["GET", "POST"])
def student_login():
    if request.method == "POST":
        admission_number = request.form.get("admission_number", "").strip()
        first_name = request.form.get("first_name", "").strip()

        student = find_student_by_admission(admission_number)

        if student:
            saved_first_name = str(student.get("first_name", "")).strip().lower()
            entered_first_name = str(first_name).strip().lower()

            if saved_first_name != entered_first_name:
                return render_template(
                    "student_login.html",
                    error="Invalid admission number or first name",
                    admission_number=admission_number,
                    first_name=first_name
                )

            session.clear()
            session["user_type"] = "student"
            session["student"] = student

            session["class"] = student.get("class")                    # e.g JSS1A / SS1_GOLD
            session["class_category"] = student.get("class_category")  # e.g JSS1 / SS1

            session["exam_started"] = False
            session["exam_submitted"] = False

            return redirect(url_for("student_portal_bp.student_portal"))

        return render_template(
            "student_login.html",
            error="Invalid admission number or first name",
            admission_number=admission_number,
            first_name=first_name
        )

    return render_template("student_login.html")


# =======================================================
# LOGOUT
# =======================================================
@user_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("user_bp.student_login"))