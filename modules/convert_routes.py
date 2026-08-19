# modules/convert_routes.py

from flask import Blueprint, request, jsonify, session
from functools import wraps

from convert import (
    save_uploaded_convert_file,
    extract_source_file,
    generate_exam_json_from_text,
    save_exam_json,
    detect_class_category,
    detect_subject,
)

from convert_ext import (
    build_clean_student_json,
    save_convert_draft,
    list_convert_drafts,
    get_convert_draft,
    delete_convert_draft,
    clear_convert_drafts,
)


convert_bp = Blueprint("convert_bp", __name__)


def teacher_allowed(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if session.get("user_type") not in ["admin", "teacher"]:
            return jsonify({"error": "Unauthorized access"}), 401
        return view_func(*args, **kwargs)
    return wrapper


def bool_form(value, default=False):
    if value is None:
        return default
    return str(value).lower() in ["1", "true", "yes", "on"]


def bool_json(value, default=False):
    if value is None:
        return default

    if isinstance(value, bool):
        return value

    return str(value).lower() in ["1", "true", "yes", "on"]


def safe_int(value, default=50):
    try:
        return int(value)
    except Exception:
        return default


@convert_bp.route("/convert/api/extract", methods=["POST"])
@teacher_allowed
def convert_extract():
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file uploaded"}), 400

        file = request.files.get("file")

        subject = request.form.get("subject", "").strip()
        class_category = request.form.get("class_category", "").strip()
        objective_only = bool_form(request.form.get("objective_only"), True)
        extract_diagrams = bool_form(request.form.get("extract_diagrams"), True)

        saved_path = save_uploaded_convert_file(file)

        result = extract_source_file(
            file_path=saved_path,
            subject=subject,
            class_category=class_category,
            objective_only=objective_only,
            extract_diagrams=extract_diagrams,
        )

        return jsonify({
            "success": True,
            "filename": result.get("filename"),
            "subject": result.get("subject"),
            "class_category": result.get("class_category"),
            "detected_year": result.get("detected_year"),
            "expected_questions": result.get("expected_questions"),
            "clean_text": result.get("clean_text"),
            "text_path": result.get("text_path"),
            "diagram_map": result.get("diagram_map", {}),
            "diagram_count": result.get("diagram_count", 0),
            "question_estimate": result.get("question_estimate", 0),
            "objective_warnings": result.get("objective_warnings", []),
            "multiple_objective_series": result.get("multiple_objective_series", False),
            "series_info": result.get("series_info", {}),
        })

    except Exception as e:
        print("CONVERT EXTRACT ERROR:", e)
        return jsonify({"error": str(e)}), 500


@convert_bp.route("/convert/api/generate-json", methods=["POST"])
@teacher_allowed
def convert_generate_json():
    try:
        payload = request.get_json(silent=True) or {}

        clean_text = str(payload.get("clean_text", "")).strip()

        if not clean_text:
            return jsonify({"error": "Clean text is required"}), 400

        subject_input = str(payload.get("subject", "")).strip()
        class_input = str(payload.get("class_category", "")).strip()

        subject = detect_subject("", clean_text, subject_input)
        class_category = detect_class_category("", clean_text, class_input)

        expected_questions = safe_int(payload.get("expected_questions"), 50)
        diagram_map = payload.get("diagram_map") or {}
        use_llm = bool_json(payload.get("use_llm"), True)

        result = generate_exam_json_from_text(
            clean_text=clean_text,
            subject=subject,
            class_category=class_category,
            expected_questions=expected_questions,
            diagram_map=diagram_map,
            use_llm=use_llm,
            solve_answers=True,
        )

        full_json = result.get("data") or {}

        student_json = build_clean_student_json(
            data=full_json,
            subject=subject,
            class_category=class_category,
        )

        draft = save_convert_draft(
            student_json=student_json,
            full_json=full_json,
            answer_report=result.get("answer_report", []),
            openai_usage=result.get("openai_usage", {}),
            needs_review=result.get("needs_review", 0),
            source_filename=str(payload.get("source_filename", "")).strip(),
            year=str(payload.get("year", "")).strip(),
            subject=subject,
            class_category=class_category,
        )

        return jsonify({
            "success": True,
            "json": student_json,
            "student_json": student_json,
            "full_json": full_json,
            "validation": result.get("validation"),
            "stats": result.get("stats"),
            "answer_report": result.get("answer_report", []),
            "openai_usage": result.get("openai_usage", {}),
            "needs_review": result.get("needs_review", 0),
            "draft": draft,
        })

    except Exception as e:
        print("CONVERT GENERATE ERROR:", e)
        return jsonify({"error": str(e)}), 500


@convert_bp.route("/convert/api/save-json", methods=["POST"])
@teacher_allowed
def convert_save_json():
    try:
        payload = request.get_json(silent=True) or {}

        data = payload.get("json") or payload.get("student_json") or payload.get("data")

        if not data:
            return jsonify({"error": "JSON data is required"}), 400

        year = str(
            payload.get("year")
            or payload.get("detected_year")
            or data.get("year")
            or ""
        ).strip()

        subject = str(
            payload.get("subject")
            or data.get("subject")
            or ""
        ).strip()

        class_category = str(
            payload.get("class_category")
            or data.get("class_category")
            or data.get("class")
            or ""
        ).strip()

        overwrite = bool_json(payload.get("overwrite"), True)
        review_report = payload.get("answer_report") or payload.get("review_report") or []

        result = save_exam_json(
            data=data,
            year=year,
            subject=subject,
            class_category=class_category,
            overwrite=overwrite,
            review_report=review_report,
        )

        return jsonify(result)

    except Exception as e:
        print("CONVERT SAVE ERROR:", e)
        return jsonify({"error": str(e)}), 500


# ============================================================
# CONVERT TEMP DRAFTS
# ============================================================

@convert_bp.route("/convert/api/drafts", methods=["GET"])
@teacher_allowed
def convert_list_drafts():
    try:
        return jsonify({
            "success": True,
            "drafts": list_convert_drafts(limit=30),
        })

    except Exception as e:
        print("CONVERT DRAFT LIST ERROR:", e)
        return jsonify({"error": str(e)}), 500


@convert_bp.route("/convert/api/drafts/<draft_id>", methods=["GET"])
@teacher_allowed
def convert_get_draft_route(draft_id):
    try:
        return jsonify({
            "success": True,
            "draft": get_convert_draft(draft_id),
        })

    except Exception as e:
        print("CONVERT DRAFT GET ERROR:", e)
        return jsonify({"error": str(e)}), 404


@convert_bp.route("/convert/api/drafts/<draft_id>", methods=["DELETE"])
@teacher_allowed
def convert_delete_draft_route(draft_id):
    try:
        return jsonify(delete_convert_draft(draft_id))

    except Exception as e:
        print("CONVERT DRAFT DELETE ERROR:", e)
        return jsonify({"error": str(e)}), 500


@convert_bp.route("/convert/api/drafts/clear", methods=["DELETE"])
@teacher_allowed
def convert_clear_drafts_route():
    try:
        return jsonify(clear_convert_drafts())

    except Exception as e:
        print("CONVERT DRAFT CLEAR ERROR:", e)
        return jsonify({"error": str(e)}), 500