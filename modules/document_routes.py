# ============================================================
# modules/document_routes.py
# EMIS CBT — DOCUMENT / CONVERSION ROUTES
#
# RESPONSIBILITIES:
#   - Render Admin / Teacher Past Question Upload page
#   - Accept DOCX conversion requests
#   - Save converted JSON into the canonical year structure
#
# IMPORTANT:
#   - JSON library listing / preview / delete belongs to uploads.py
#   - Portal publishing / active year / active term belongs to push.py
#
# CANONICAL STRUCTURE:
#
# JSS:
# static/subjects/<YEAR>/subjects-json/JSS1/FIRST/file.json
# static/subjects/<YEAR>/subjects-json/JSS1/SECOND/file.json
# static/subjects/<YEAR>/subjects-json/JSS1/THIRD/file.json
#
# SS:
# static/subjects/<YEAR>/subjects-json/SS1/file.json
# static/subjects/<YEAR>/subjects-json/SS2/file.json
# static/subjects/<YEAR>/subjects-json/SS3/file.json
# ============================================================

import json
import os
import re

from pathlib import Path

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename

from convert import convert_exam_file, normalize_subject_display, safe_slug

from modules.class_config import SUPPORTED_CLASSES, CLASS_ARMS, normalize_class_level, normalize_class_arm, get_ss_stream


document_bp = Blueprint("document_bp", __name__)


# ============================================================
# PATH CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_ROOT = BASE_DIR / "static"
SUBJECTS_ROOT = STATIC_ROOT / "subjects"

TERM_AWARE_CLASSES = {"JSS1", "JSS2", "JSS3"}
VALID_TERMS = {"FIRST", "SECOND", "THIRD"}


# ============================================================
# BASIC HELPERS
# ============================================================

def can_manage_uploads():
    return session.get("user_type") in {"admin", "teacher"}


def normalize_class(value):
    return normalize_class_level(value)


def is_term_aware_class(value):
    return str(normalize_class_level(value) or "").upper().strip() in TERM_AWARE_CLASSES


def normalize_term(value):
    if value is None:
        return None

    raw = str(value).strip().upper()

    if not raw:
        return None

    aliases = {
        "1": "FIRST", "01": "FIRST", "1ST": "FIRST", "FIRST": "FIRST", "FIRST TERM": "FIRST", "1ST TERM": "FIRST", "TERM 1": "FIRST", "TERM1": "FIRST",
        "2": "SECOND", "02": "SECOND", "2ND": "SECOND", "SECOND": "SECOND", "SECOND TERM": "SECOND", "2ND TERM": "SECOND", "TERM 2": "SECOND", "TERM2": "SECOND",
        "3": "THIRD", "03": "THIRD", "3RD": "THIRD", "THIRD": "THIRD", "THIRD TERM": "THIRD", "3RD TERM": "THIRD", "TERM 3": "THIRD", "TERM3": "THIRD",
    }

    return aliases.get(raw)


def term_label(term):
    term = normalize_term(term)
    return {"FIRST": "1st Term", "SECOND": "2nd Term", "THIRD": "3rd Term"}.get(term, "—")


def valid_year(year):
    return bool(str(year or "").strip().isdigit())


def safe_year(year):
    year = str(year or "").strip()
    return year if valid_year(year) else None


# ============================================================
# TERM DETECTION HELPERS
# ============================================================

def detect_term_from_text(value):
    text = str(value or "").upper()

    patterns = [
        ("FIRST", [r"\bFIRST\s+TERM\b", r"\b1ST\s+TERM\b", r"\bTERM\s*1\b", r"(?:^|[\s_-])FIRST(?:$|[\s_.-])", r"(?:^|[\s_-])1ST(?:$|[\s_.-])"]),
        ("SECOND", [r"\bSECOND\s+TERM\b", r"\b2ND\s+TERM\b", r"\bTERM\s*2\b", r"(?:^|[\s_-])SECOND(?:$|[\s_.-])", r"(?:^|[\s_-])2ND(?:$|[\s_.-])"]),
        ("THIRD", [r"\bTHIRD\s+TERM\b", r"\b3RD\s+TERM\b", r"\bTERM\s*3\b", r"(?:^|[\s_-])THIRD(?:$|[\s_.-])", r"(?:^|[\s_-])3RD(?:$|[\s_.-])"]),
    ]

    for term, regexes in patterns:
        for pattern in regexes:
            if re.search(pattern, text, re.IGNORECASE):
                return term

    return None


def detect_term_from_data(data):
    if not isinstance(data, dict):
        return None

    for value in [data.get("term"), data.get("exam_term"), data.get("academic_term"), data.get("term_name")]:
        normalized = normalize_term(value)

        if normalized:
            return normalized

    combined = " ".join(str(value) for value in [
        data.get("exam_title"),
        data.get("title"),
        data.get("description"),
        data.get("instructions"),
        data.get("school"),
    ] if value)

    return detect_term_from_text(combined)


# ============================================================
# CLASS META
# ============================================================

def get_class_meta(raw_class):
    class_level = normalize_class_level(raw_class)
    class_arm = normalize_class_arm(raw_class, class_level)

    if not class_arm:
        class_arm = class_level

    return {
        "class_level": class_level,
        "class_category": class_level,
        "class_arm": class_arm,
        "stream": get_ss_stream(class_arm),
    }


# ============================================================
# PATH HELPERS
# ============================================================

def get_year_root(year):
    return SUBJECTS_ROOT / str(year)


def get_year_docx_folder(year):
    return get_year_root(year) / "subjects-docx"


def get_year_json_folder(year):
    return get_year_root(year) / "subjects-json"


def get_class_json_folder(year, class_level):
    return get_year_json_folder(year) / class_level


def get_json_save_folder(year, class_level, term=None):
    class_level = normalize_class_level(class_level)

    if not class_level:
        return None

    folder = get_class_json_folder(year, class_level)

    if is_term_aware_class(class_level):
        term = normalize_term(term)

        if not term:
            return None

        folder = folder / term

    return folder


# ============================================================
# CONVERSION WRAPPER
# ============================================================

def convert_exam(docx_path):
    result = convert_exam_file(str(docx_path))

    if not isinstance(result, dict):
        raise ValueError("Converter returned an invalid response.")

    return result.get("subject"), result.get("class_category"), result.get("json") or {}


# ============================================================
# CANONICAL JSON SAVE
# ============================================================

def save_output(subject, class_level, data, year, term=None):
    if not isinstance(data, dict):
        data = {}

    year = safe_year(year)

    if not year:
        raise ValueError("A valid examination year is required.")

    subject = normalize_subject_display(subject or data.get("subject") or "General")
    class_level = normalize_class_level(class_level or data.get("class_category") or data.get("class_level") or "")

    if class_level not in SUPPORTED_CLASSES:
        raise ValueError(f"Unsupported class: {class_level or 'Unknown'}")

    if is_term_aware_class(class_level):
        term = normalize_term(term)

        if not term:
            raise ValueError(f"{class_level} requires FIRST, SECOND or THIRD term.")
    else:
        term = None

    folder = get_json_save_folder(year, class_level, term)

    if folder is None:
        raise ValueError("Unable to determine JSON destination folder.")

    folder.mkdir(parents=True, exist_ok=True)

    filename = f"{safe_slug(subject)}_{class_level.lower()}.json"
    path = folder / filename

    final_data = dict(data)

    final_data["subject"] = subject
    final_data["class_category"] = class_level
    final_data["class_level"] = class_level

    if "groups" not in final_data:
        final_data["groups"] = data.get("groups", [])

    if "questions" not in final_data:
        final_data["questions"] = data.get("questions", [])

    if is_term_aware_class(class_level):
        final_data["term"] = term
        final_data["term_label"] = term_label(term)
    else:
        final_data.pop("term", None)
        final_data.pop("term_label", None)
        final_data.pop("exam_term", None)
        final_data.pop("academic_term", None)

    with path.open("w", encoding="utf-8") as file:
        json.dump(final_data, file, indent=4, ensure_ascii=False)

    return path


# ============================================================
# UPLOADS PAGE — ADMIN + TEACHER
# ============================================================

@document_bp.route("/admin/uploads")
def uploads_page():
    if not can_manage_uploads():
        return redirect(url_for("admin_bp.admin_login"))

    return render_template("uploads.html", user_type=session.get("user_type"), classes=SUPPORTED_CLASSES, class_arms=CLASS_ARMS)


# ============================================================
# API — DOCX UPLOAD + CONVERSION
#
# This endpoint ONLY handles conversion.
#
# JSON LIBRARY ROUTES ARE NOT DEFINED HERE.
#
# Expected optional form fields:
#
# file=<DOCX>
# year=2017
# class=JSS1
# term=FIRST
#
# For SS:
# year=2025
# class=SS1
#
# ============================================================

@document_bp.route("/api/upload", methods=["POST"])
def api_upload():
    if not can_manage_uploads():
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file uploaded"}), 400

    uploaded_file = request.files["file"]

    if not uploaded_file or not uploaded_file.filename:
        return jsonify({"success": False, "error": "Invalid file name"}), 400

    filename = secure_filename(uploaded_file.filename)

    if not filename.lower().endswith(".docx"):
        return jsonify({"success": False, "error": "Only DOCX files are supported"}), 400

    year = safe_year(request.form.get("year"))

    if not year:
        return jsonify({"success": False, "error": "A valid examination year is required"}), 400

    requested_class = normalize_class_level(request.form.get("class") or request.form.get("class_level") or request.form.get("class_category"))
    requested_term = normalize_term(request.form.get("term") or request.form.get("exam_term") or request.form.get("academic_term"))

    docx_folder = get_year_docx_folder(year)
    docx_folder.mkdir(parents=True, exist_ok=True)

    docx_path = docx_folder / filename
    uploaded_file.save(str(docx_path))

    try:
        subject, detected_class, data = convert_exam(docx_path)

        if not isinstance(data, dict):
            data = {}

        detected_class = normalize_class_level(detected_class or data.get("class_category") or data.get("class_level"))
        class_level = requested_class or detected_class

        if class_level not in SUPPORTED_CLASSES:
            return jsonify({
                "success": False,
                "error": "Invalid or unsupported class detected from document",
                "detected_class": detected_class,
            }), 400

        class_meta = get_class_meta(class_level)

        # Explicit UI-selected term is authoritative.
        term = requested_term

        if is_term_aware_class(class_level) and not term:
            term = detect_term_from_data(data) or detect_term_from_text(filename)

        if is_term_aware_class(class_level) and not term:
            return jsonify({
                "success": False,
                "error": f"{class_level} requires a term. Select 1st, 2nd or 3rd Term.",
                "class_category": class_level,
                "class_level": class_level,
                "term_required": True,
            }), 400

        if not is_term_aware_class(class_level):
            term = None

        json_path = save_output(subject, class_level, data, year, term)

        return jsonify({
            "success": True,
            "message": "File converted successfully",
            "year": int(year),
            "json_file": json_path.name,
            "json_filename": json_path.name,
            "json_path": str(json_path),
            "class_category": class_level,
            "class_level": class_level,
            "class_arm": class_meta["class_arm"],
            "stream": class_meta["stream"],
            "term": term,
            "term_label": term_label(term) if term else "—",
            "subject": subject,
            "questions": len(data.get("questions", [])) if isinstance(data.get("questions", []), list) else 0,
        })

    except Exception as exc:
        print(f"DOCUMENT CONVERSION ERROR [{docx_path}]: {exc}")

        return jsonify({
            "success": False,
            "error": str(exc),
        }), 500


# ============================================================
# IMPORTANT — JSON LIBRARY ROUTES REMOVED FROM THIS FILE
# ============================================================
#
# DO NOT ADD THESE ROUTES BACK HERE:
#
#   GET    /api/uploads
#   GET    /api/uploads/<year>
#   GET    /api/uploads/<class>/<filename>
#   DELETE /api/uploads/<class>/<filename>
#
# uploads.py is now the SINGLE source of truth for the JSON
# question library.
#
# When uploads_bp is registered using:
#
#   app.register_blueprint(uploads_bp, url_prefix="/api")
#
# uploads.py owns:
#
#   GET    /api/uploads/<year>
#   GET    /api/uploads/<year>/<filename>
#   DELETE /api/uploads/<year>/delete/<filename>
#
# This prevents the old non-term-aware document_routes.py
# implementation from intercepting /api/uploads/2017.
#
# ============================================================