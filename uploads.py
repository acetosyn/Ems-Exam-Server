# uploads.py — YEAR-AWARE JSON BROWSER (2025)
import os
import json
from flask import Blueprint, jsonify, request
from werkzeug.utils import secure_filename

uploads_bp = Blueprint("uploads_bp", __name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Static structure:
# static/subjects/subjects-json/<YEAR>/<CLASS>/<FILES>
SUBJECTS_ROOT = os.path.join(BASE_DIR, "static", "subjects", "subjects-json")
os.makedirs(SUBJECTS_ROOT, exist_ok=True)

ALLOWED_EXTENSIONS = {"json", "docx"}  # docx optional (future)


# ======================================================
# HELPERS
# ======================================================
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def safe_filename(filename):
    return secure_filename(filename)


def detect_class_from_filename(filename):
    low = filename.lower()
    if "ss1" in low: return "SS1"
    if "ss2" in low: return "SS2"
    if "ss3" in low: return "SS3"
    return None


def get_year_path(year):
    """Return folder path for a given academic year."""
    return os.path.join(SUBJECTS_ROOT, str(year))


def get_json_path(year, class_cat, filename):
    return os.path.join(get_year_path(year), class_cat, filename)


# ======================================================
# OPTIONAL DOCX/JSON UPLOAD HANDLING (you said you may not use it)
# Still included for future safety.
# ======================================================
@uploads_bp.route("/upload", methods=["POST"])
def upload_handler():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    files = request.files.getlist("file")
    if not files:
        return jsonify({"error": "No selected files"}), 400

    # Admin must specify the year they want to upload into
    year = request.form.get("year")
    if not year:
        return jsonify({"error": "Missing year"}), 400

    year_folder = get_year_path(year)
    os.makedirs(year_folder, exist_ok=True)

    results = []

    for file in files:
        fname = safe_filename(file.filename)
        ext = fname.split(".")[-1].lower()

        if not allowed_file(fname):
            continue

        class_cat = detect_class_from_filename(fname) or "UNSORTED"
        class_folder = os.path.join(year_folder, class_cat)
        os.makedirs(class_folder, exist_ok=True)

        save_path = os.path.join(class_folder, fname)
        file.save(save_path)

        results.append({
            "filename": fname,
            "year": year,
            "class_category": class_cat,
            "status": "saved",
        })

    return jsonify({"success": True, "uploads": results})


# ======================================================
# API: LIST JSON FILES FOR A GIVEN YEAR
# ======================================================
@uploads_bp.route("/uploads/<year>", methods=["GET"])
def list_year_files(year):
    year_folder = get_year_path(year)
    if not os.path.isdir(year_folder):
        return jsonify({"uploads": []})  # empty

    results = []

    for class_cat in ["SS1", "SS2", "SS3"]:
        class_folder = os.path.join(year_folder, class_cat)
        if not os.path.isdir(class_folder):
            continue

        for filename in sorted(os.listdir(class_folder)):
            if not filename.endswith(".json"):
                continue

            full_path = os.path.join(class_folder, filename)
            size_kb = round(os.path.getsize(full_path) / 1024, 1)

            # Read minimal metadata
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    subject = data.get("subject", filename)
                    qcount = len(data.get("questions", []))
            except:
                subject = filename
                qcount = 0

            results.append({
                "year": int(year),
                "filename": filename,
                "subject": subject,
                "class_category": class_cat,
                "questions": qcount,
                "size": size_kb,
                "status": "OK",
            })

    return jsonify({"uploads": results})


# ======================================================
# API: PREVIEW JSON FILE
# ======================================================
@uploads_bp.route("/uploads/<year>/<filename>", methods=["GET"])
def preview_json(year, filename):
    class_cat = detect_class_from_filename(filename)
    if not class_cat:
        return jsonify({"error": "Cannot detect class from filename"}), 400

    json_path = get_json_path(year, class_cat, filename)

    if not os.path.exists(json_path):
        return jsonify({"error": "Not found"}), 404

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            return jsonify(json.load(f))
    except:
        return jsonify({"error": "Failed to read JSON"}), 500


# ======================================================
# API: DELETE FILE
# ======================================================
@uploads_bp.route("/uploads/<year>/delete/<filename>", methods=["DELETE"])
def delete_json(year, filename):
    class_cat = detect_class_from_filename(filename)
    if not class_cat:
        return jsonify({"error": "Cannot detect class"}), 400

    json_path = get_json_path(year, class_cat, filename)

    if not os.path.exists(json_path):
        return jsonify({"error": "File not found"}), 404

    try:
        os.remove(json_path)
        return jsonify({"success": True, "deleted": filename})
    except:
        return jsonify({"error": "Failed to delete"}), 500
