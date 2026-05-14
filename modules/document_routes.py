# modules/document_routes.py

from flask import Blueprint, jsonify, request, session, redirect, url_for, render_template
import os
import json
from werkzeug.utils import secure_filename

from convert import convert_exam, save_output
from modules.class_config import SUPPORTED_CLASSES


document_bp = Blueprint("document_bp", __name__)


BASE_DOCX = "static/subjects/subjects-docx"
BASE_JSON = "static/subjects/subjects-json"


# =========================================================
# Helper — Access check
# =========================================================
def can_manage_uploads():
    return session.get("user_type") in ["admin", "teacher"]


# =========================================================
# Helper — Normalize class
# =========================================================
def normalize_class(cls):
    cls = str(cls or "").upper().strip()
    return cls if cls in SUPPORTED_CLASSES else ""


# =========================================================
# UPLOADS PAGE Admin + Teacher
# =========================================================
@document_bp.route("/admin/uploads")
def uploads_page():
    if not can_manage_uploads():
        return redirect(url_for("admin_bp.admin_login"))

    return render_template(
        "uploads.html",
        user_type=session.get("user_type")
    )


# =========================================================
# API — UPLOAD + CONVERT DOCX TO JSON
# =========================================================
@document_bp.route("/api/upload", methods=["POST"])
def api_upload():
    if not can_manage_uploads():
        return jsonify({"error": "Unauthorized"}), 403

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"error": "Invalid file name"}), 400

    filename = secure_filename(file.filename)

    os.makedirs(BASE_DOCX, exist_ok=True)

    docx_path = os.path.join(BASE_DOCX, filename)
    file.save(docx_path)

    try:
        subject, class_cat, data = convert_exam(docx_path)

        class_cat = normalize_class(class_cat)

        if not class_cat:
            return jsonify({
                "error": "Invalid or unsupported class detected from document"
            }), 400

        json_path = save_output(subject, class_cat, data)

        return jsonify({
            "success": True,
            "message": "File converted successfully",
            "json_file": os.path.basename(json_path),
            "class_category": class_cat,
            "subject": subject
        })

    except Exception as e:
        print("❌ Conversion Error:", e)
        return jsonify({"error": str(e)}), 500


# =========================================================
# API — LIST ALL CONVERTED JSON
# static/subjects/subjects-json/<CLASS>/
# =========================================================
@document_bp.route("/api/uploads", methods=["GET"])
def api_list_uploads():
    if not can_manage_uploads():
        return jsonify({"error": "Unauthorized"}), 403

    all_files = {}

    for cls in SUPPORTED_CLASSES:
        folder = os.path.join(BASE_JSON, cls)

        if not os.path.exists(folder):
            all_files[cls] = []
            continue

        all_files[cls] = sorted([
            f for f in os.listdir(folder)
            if f.lower().endswith(".json")
        ])

    return jsonify({"uploads": all_files})


# =========================================================
# API — VIEW A JSON FILE
# =========================================================
@document_bp.route("/api/uploads/<cls>/<filename>", methods=["GET"])
def api_view_upload(cls, filename):
    if not can_manage_uploads():
        return jsonify({"error": "Unauthorized"}), 403

    cls = normalize_class(cls)

    if not cls:
        return jsonify({"error": "Invalid class"}), 400

    filename = secure_filename(filename)
    path = os.path.join(BASE_JSON, cls, filename)

    if not os.path.exists(path):
        return jsonify({"error": "File not found"}), 404

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    return jsonify({
        "class_category": cls,
        "filename": filename,
        "content": content
    })


# =========================================================
# API — DELETE A JSON FILE
# =========================================================
@document_bp.route("/api/uploads/<cls>/<filename>", methods=["DELETE"])
def api_delete_upload(cls, filename):
    if not can_manage_uploads():
        return jsonify({"error": "Unauthorized"}), 403

    cls = normalize_class(cls)

    if not cls:
        return jsonify({"error": "Invalid class"}), 400

    filename = secure_filename(filename)
    path = os.path.join(BASE_JSON, cls, filename)

    if not os.path.exists(path):
        return jsonify({"error": "File not found"}), 404

    os.remove(path)

    return jsonify({
        "success": True,
        "message": f"{filename} deleted successfully",
        "class_category": cls
    })


# =========================================================
# API — LIST JSON FILES BY YEAR
# /api/uploads/<year>
#
# Expected:
# static/subjects/<year>/subjects-json/<CLASS>/<file>.json
# =========================================================
@document_bp.route("/api/uploads/<int:year>", methods=["GET"])
def api_list_by_year(year):
    if not can_manage_uploads():
        return jsonify({"error": "Unauthorized"}), 403

    year_folder = os.path.join(
        "static",
        "subjects",
        str(year),
        "subjects-json"
    )

    results = []

    if not os.path.exists(year_folder):
        return jsonify({"uploads": []})

    for cls in SUPPORTED_CLASSES:
        cls_path = os.path.join(year_folder, cls)

        if not os.path.exists(cls_path):
            continue

        for fname in sorted(os.listdir(cls_path)):
            if not fname.lower().endswith(".json"):
                continue

            fpath = os.path.join(cls_path, fname)
            size_kb = round(os.path.getsize(fpath) / 1024, 1)

            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    j = json.load(f)

                subject = j.get("subject", "Unknown")
                questions = len(j.get("questions", []))
                version = j.get("version", None)

            except Exception:
                subject = "Unknown"
                questions = 0
                version = None

            results.append({
                "year": year,
                "filename": fname,
                "subject": subject,
                "class_category": cls,
                "questions": questions,
                "version": version,
                "size_kb": size_kb,
                "status": "OK",
            })

    return jsonify({"uploads": results})