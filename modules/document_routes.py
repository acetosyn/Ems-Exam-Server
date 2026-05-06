# modules/document_routes.py
from flask import Blueprint, jsonify, request, session, redirect, url_for, render_template
import os
from werkzeug.utils import secure_filename

# NEW: Import your convert logic
from convert import convert_exam, save_output
import json

# NEW: Correct base paths
BASE_DOCX = "static/subjects/subjects-docx"
BASE_JSON = "static/subjects/subjects-json"

document_bp = Blueprint("document_bp", __name__)


# =========================================================
# UPLOADS PAGE (Admin + Teacher)
# =========================================================
@document_bp.route("/admin/uploads")
def uploads_page():
    user_type = session.get("user_type")
    if user_type not in ["admin", "teacher"]:
        return redirect(url_for("admin_bp.admin_login"))
    return render_template("uploads.html", user_type=user_type)


# =========================================================
# API — UPLOAD + CONVERT DOCX → JSON
# =========================================================
@document_bp.route("/api/upload", methods=["POST"])
def api_upload():
    user_type = session.get("user_type")
    if user_type not in ["admin", "teacher"]:
        return jsonify({"error": "Unauthorized"}), 403

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Invalid file name"}), 400

    filename = secure_filename(file.filename)

    # Save DOCX into static/subjects/subjects-docx/
    os.makedirs(BASE_DOCX, exist_ok=True)
    docx_path = os.path.join(BASE_DOCX, filename)
    file.save(docx_path)

    try:
        # Run conversion
        subject, class_cat, data = convert_exam(docx_path)

        # Save JSON output properly
        json_path = save_output(subject, class_cat, data)

        return jsonify({
            "success": True,
            "message": "File converted successfully",
            "json_file": os.path.basename(json_path)
        })

    except Exception as e:
        print("❌ Conversion Error:", e)
        return jsonify({"error": str(e)}), 500


# =========================================================
# API — LIST ALL CONVERTED JSON
# =========================================================
@document_bp.route("/api/uploads", methods=["GET"])
def api_list_uploads():
    user_type = session.get("user_type")
    if user_type not in ["admin", "teacher"]:
        return jsonify({"error": "Unauthorized"}), 403

    all_files = {}

    # Scan SS1, SS2, SS3 folders
    for cls in ["SS1", "SS2", "SS3"]:
        folder = os.path.join(BASE_JSON, cls)
        if not os.path.exists(folder):
            continue

        items = [
            f for f in os.listdir(folder)
            if f.endswith(".json")
        ]

        all_files[cls] = items

    return jsonify({"uploads": all_files})


# =========================================================
# API — VIEW A JSON FILE
# =========================================================
@document_bp.route("/api/uploads/<cls>/<filename>", methods=["GET"])
def api_view_upload(cls, filename):
    user_type = session.get("user_type")
    if user_type not in ["admin", "teacher"]:
        return jsonify({"error": "Unauthorized"}), 403

    path = os.path.join(BASE_JSON, cls.upper(), filename)

    if not os.path.exists(path):
        return jsonify({"error": "File not found"}), 404

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    return jsonify({"content": content})


# =========================================================
# API — DELETE A JSON FILE
# =========================================================
@document_bp.route("/api/uploads/<cls>/<filename>", methods=["DELETE"])
def api_delete_upload(cls, filename):
    user_type = session.get("user_type")
    if user_type not in ["admin", "teacher"]:
        return jsonify({"error": "Unauthorized"}), 403

    path = os.path.join(BASE_JSON, cls.upper(), filename)

    if not os.path.exists(path):
        return jsonify({"error": "File not found"}), 404

    os.remove(path)

    return jsonify({
        "success": True,
        "message": f"{filename} deleted successfully"
    })



# =========================================================
# API — LIST JSON FILES BY YEAR
# /api/uploads/<year>
# =========================================================
@document_bp.route("/api/uploads/<int:year>", methods=["GET"])
def api_list_by_year(year):
    user_type = session.get("user_type")
    if user_type not in ["admin", "teacher"]:
        return jsonify({"error": "Unauthorized"}), 403

    year_folder = os.path.join("static/subjects", str(year), "subjects-json")
    results = []

    # If year folder missing → no subjects
    if not os.path.exists(year_folder):
        return jsonify({"uploads": []})

    # Scan SS1 SS2 SS3
    for cls in ["SS1", "SS2", "SS3"]:
        cls_path = os.path.join(year_folder, cls)
        if not os.path.exists(cls_path):
            continue

        for fname in os.listdir(cls_path):
            if not fname.endswith(".json"):
                continue

            fpath = os.path.join(cls_path, fname)
            size_kb = round(os.path.getsize(fpath) / 1024, 1)

            # Load minimal JSON to extract meta
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    j = json.load(f)

                subject = j.get("subject", "Unknown")
                questions = len(j.get("questions", []))
                version = j.get("version", None)
            except:
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
