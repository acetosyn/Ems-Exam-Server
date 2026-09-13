# uploads.py — EMIS CBT YEAR / CLASS / TERM-AWARE JSON LIBRARY

import os
import json
import re

from flask import Blueprint, jsonify, request
from werkzeug.utils import secure_filename


uploads_bp = Blueprint("uploads_bp", __name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# ============================================================
# DIRECTORY STRUCTURE
#
# JSS — STRICT TERM SYSTEM:
# static/subjects/<YEAR>/subjects-json/JSS1/FIRST/file.json
# static/subjects/<YEAR>/subjects-json/JSS1/SECOND/file.json
# static/subjects/<YEAR>/subjects-json/JSS1/THIRD/file.json
#
# SS — HYBRID TERM SYSTEM:
# static/subjects/<YEAR>/subjects-json/SS1/file.json
# static/subjects/<YEAR>/subjects-json/SS1/FIRST/file.json
# static/subjects/<YEAR>/subjects-json/SS1/SECOND/file.json
# static/subjects/<YEAR>/subjects-json/SS1/THIRD/file.json
#
# SS root JSONs remain supported as general / legacy exams.
# ============================================================

SUBJECTS_ROOT = os.path.join(BASE_DIR, "static", "subjects")

ALLOWED_EXTENSIONS = {"json", "docx"}

SUPPORTED_CLASSES = ["JSS1", "JSS2", "JSS3", "SS1", "SS2", "SS3"]

# JSS = compulsory term system.
TERM_AWARE_CLASSES = {"JSS1", "JSS2", "JSS3"}

# SS = optional / hybrid term system.
OPTIONAL_TERM_CLASSES = {"SS1", "SS2", "SS3"}

VALID_TERMS = {"FIRST", "SECOND", "THIRD"}
TERM_ORDER = {"FIRST": 1, "SECOND": 2, "THIRD": 3, None: 4}

IGNORED_JSON_FILES = {"pushed_subjects.json"}


# ============================================================
# BASIC HELPERS
# ============================================================

def allowed_file(filename):
    return "." in str(filename or "") and str(filename).rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def safe_filename(filename):
    return secure_filename(str(filename or ""))


def normalize_class(value):
    return str(value or "").upper().strip().replace(" ", "")


def is_term_aware_class(class_cat):
    """JSS classes: FIRST / SECOND / THIRD is compulsory."""
    return normalize_class(class_cat) in TERM_AWARE_CLASSES


def is_optional_term_class(class_cat):
    """SS classes: FIRST / SECOND / THIRD is optional; root/general JSON remains valid."""
    return normalize_class(class_cat) in OPTIONAL_TERM_CLASSES


def supports_term_folders(class_cat):
    return is_term_aware_class(class_cat) or is_optional_term_class(class_cat)


def is_valid_class(class_cat):
    return normalize_class(class_cat) in SUPPORTED_CLASSES


def is_ignored_json(filename):
    return str(filename or "").lower().strip() in IGNORED_JSON_FILES


def valid_year(year):
    return bool(str(year or "").strip().isdigit())


def get_file_size_kb(path):
    try: return round(os.path.getsize(path) / 1024, 1)
    except OSError: return 0


# ============================================================
# CLASS DETECTION
# ============================================================

def detect_class_from_filename(filename):
    low = str(filename or "").lower()

    # JSS must be checked before SS because "jss1" also contains "ss1".
    patterns = [
        ("JSS1", r"(?<![a-z0-9])jss[\s_-]*1(?![0-9])"),
        ("JSS2", r"(?<![a-z0-9])jss[\s_-]*2(?![0-9])"),
        ("JSS3", r"(?<![a-z0-9])jss[\s_-]*3(?![0-9])"),
        ("SS1", r"(?<![a-z0-9])ss[\s_-]*1(?![0-9])"),
        ("SS2", r"(?<![a-z0-9])ss[\s_-]*2(?![0-9])"),
        ("SS3", r"(?<![a-z0-9])ss[\s_-]*3(?![0-9])"),
    ]

    for class_cat, pattern in patterns:
        if re.search(pattern, low, re.IGNORECASE): return class_cat

    return None


def detect_class_from_json(data):
    if not isinstance(data, dict): return None

    raw = normalize_class(data.get("class_category") or data.get("class_level") or data.get("class") or "")

    # Supports broad class and class-arm metadata:
    # JSS1A -> JSS1
    # JSS2B -> JSS2
    # SS1_GOLD -> SS1
    for class_cat in SUPPORTED_CLASSES:
        if raw.startswith(class_cat): return class_cat

    return None


# ============================================================
# TERM NORMALIZATION
# ============================================================

def normalize_term(value):
    if value is None: return None

    value = str(value).strip().upper()
    if not value: return None

    aliases = {
        "1": "FIRST", "01": "FIRST", "1ST": "FIRST", "FIRST": "FIRST",
        "FIRST TERM": "FIRST", "1ST TERM": "FIRST", "TERM 1": "FIRST", "TERM1": "FIRST",

        "2": "SECOND", "02": "SECOND", "2ND": "SECOND", "SECOND": "SECOND",
        "SECOND TERM": "SECOND", "2ND TERM": "SECOND", "TERM 2": "SECOND", "TERM2": "SECOND",

        "3": "THIRD", "03": "THIRD", "3RD": "THIRD", "THIRD": "THIRD",
        "THIRD TERM": "THIRD", "3RD TERM": "THIRD", "TERM 3": "THIRD", "TERM3": "THIRD",
    }

    return aliases.get(value)


def term_label(term):
    labels = {"FIRST": "1st Term", "SECOND": "2nd Term", "THIRD": "3rd Term"}
    return labels.get(normalize_term(term), "—")


# ============================================================
# TERM DETECTION FROM TEXT
# ============================================================

def detect_term_from_text(text):
    text = str(text or "").upper()

    patterns = [
        ("FIRST", [
            r"\bFIRST\s+TERM\b", r"\b1ST\s+TERM\b", r"\bTERM\s*1\b",
            r"(?:^|[\s_-])FIRST(?:$|[\s_.-])", r"(?:^|[\s_-])1ST(?:$|[\s_.-])",
        ]),
        ("SECOND", [
            r"\bSECOND\s+TERM\b", r"\b2ND\s+TERM\b", r"\bTERM\s*2\b",
            r"(?:^|[\s_-])SECOND(?:$|[\s_.-])", r"(?:^|[\s_-])2ND(?:$|[\s_.-])",
        ]),
        ("THIRD", [
            r"\bTHIRD\s+TERM\b", r"\b3RD\s+TERM\b", r"\bTERM\s*3\b",
            r"(?:^|[\s_-])THIRD(?:$|[\s_.-])", r"(?:^|[\s_-])3RD(?:$|[\s_.-])",
        ]),
    ]

    for term, term_patterns in patterns:
        for pattern in term_patterns:
            if re.search(pattern, text, re.IGNORECASE): return term

    return None


# ============================================================
# TERM DETECTION FROM JSON
# ============================================================

def detect_term_from_json(data):
    if not isinstance(data, dict): return None

    direct_fields = [data.get("term"), data.get("exam_term"), data.get("academic_term"), data.get("term_name")]

    for value in direct_fields:
        normalized = normalize_term(value)
        if normalized: return normalized

    searchable_fields = [
        data.get("exam_title"), data.get("title"), data.get("instructions"),
        data.get("school"), data.get("description"),
    ]

    combined = " ".join(str(value) for value in searchable_fields if value)
    return detect_term_from_text(combined)


def detect_term(filename=None, data=None):
    detected = detect_term_from_json(data)
    return detected if detected else detect_term_from_text(filename)


# ============================================================
# PATH HELPERS
# ============================================================

def get_year_path(year):
    return os.path.join(SUBJECTS_ROOT, str(year), "subjects-json")


def get_class_path(year, class_cat):
    return os.path.join(get_year_path(year), normalize_class(class_cat))


def get_term_path(year, class_cat, term):
    normalized_term = normalize_term(term)
    if not normalized_term: return None

    return os.path.join(get_class_path(year, class_cat), normalized_term)


def get_json_path(year, class_cat, filename, term=None):
    class_cat, filename, normalized_term = normalize_class(class_cat), safe_filename(filename), normalize_term(term)

    if class_cat not in SUPPORTED_CLASSES or not filename: return None

    class_folder = get_class_path(year, class_cat)

    # JSS = term compulsory.
    if is_term_aware_class(class_cat):
        if not normalized_term: return None
        return os.path.join(class_folder, normalized_term, filename)

    # SS = term optional. Supplied term points to FIRST / SECOND / THIRD.
    if is_optional_term_class(class_cat) and normalized_term:
        return os.path.join(class_folder, normalized_term, filename)

    # SS with no term = root/general JSON.
    return os.path.join(class_folder, filename)


# ============================================================
# JSON READER
# ============================================================

def read_json_file(path):
    try:
        with open(path, "r", encoding="utf-8-sig") as file: data = json.load(file)

        if isinstance(data, dict): return data, None
        return {}, "JSON root must be an object"

    except Exception as exc:
        return {}, str(exc)


# ============================================================
# JSON METADATA
# ============================================================

def read_json_metadata(path, filename, class_cat, fallback_term=None, force_folder_term=False):
    data, error = read_json_file(path)

    if error: print(f"JSON metadata error [{path}]: {error}")
    if not isinstance(data, dict): data = {}

    subject = str(data.get("subject") or filename).strip()

    questions = data.get("questions", [])
    objective_count = len(questions) if isinstance(questions, list) else 0

    essay = data.get("essay")
    essay_questions = essay.get("questions", []) if isinstance(essay, dict) else []
    essay_count = len(essay_questions) if isinstance(essay_questions, list) else 0
    has_essay = isinstance(essay, dict) and essay_count > 0

    detected_class = detect_class_from_json(data) or normalize_class(class_cat)
    folder_term = normalize_term(fallback_term)

    # Physical FIRST / SECOND / THIRD folder is authoritative for both JSS and SS.
    detected_term = folder_term if force_folder_term and folder_term else detect_term(filename, data) or folder_term

    return {
        "data": data, "subject": subject,

        "questions": objective_count, "objective_count": objective_count, "objective_questions": objective_count,

        "essay_questions": essay_count, "essay_count": essay_count,
        "theory_questions": essay_count, "theory_count": essay_count,

        "has_essay": has_essay, "hasEssay": has_essay,
        "essay_present": has_essay, "theory_present": has_essay,

        "essay_title": str(essay.get("title") or "").strip() if isinstance(essay, dict) else "",
        "essay_instruction": str(essay.get("instruction") or "").strip() if isinstance(essay, dict) else "",

        "class_category": detected_class, "term": detected_term,
        "valid": error is None, "error": error,
    }


# ============================================================
# LIBRARY ITEM BUILDER
# ============================================================

def build_library_item(year, filename, full_path, class_cat, term=None, legacy=False):
    class_cat, folder_term = normalize_class(class_cat), normalize_term(term)

    # FIRST / SECOND / THIRD folder itself is authoritative.
    force_folder_term = supports_term_folders(class_cat) and bool(folder_term)

    meta = read_json_metadata(
        full_path, filename, class_cat,
        fallback_term=folder_term,
        force_folder_term=force_folder_term,
    )

    # JSS = strict term system.
    if is_term_aware_class(class_cat):
        resolved_term = folder_term if force_folder_term else normalize_term(meta.get("term"))
        status = "OK" if resolved_term else "TERM_REQUIRED"

    # SS = hybrid system. Root file is general; folder file receives folder term.
    elif is_optional_term_class(class_cat):
        resolved_term, status = (folder_term if force_folder_term else None), "OK"

    else:
        resolved_term, status = None, "OK"

    if not meta.get("valid"): status = "INVALID_JSON"

    objective_count = int(meta.get("objective_count", meta.get("questions", 0)) or 0)
    essay_count = int(meta.get("essay_count", meta.get("essay_questions", 0)) or 0)
    has_essay = bool(meta.get("has_essay", False))

    return {
        "year": int(year), "filename": filename, "subject": meta.get("subject") or filename,
        "class_category": class_cat, "class_level": class_cat,
        "term": resolved_term, "term_label": term_label(resolved_term),

        "questions": objective_count, "objective_count": objective_count, "objective_questions": objective_count,

        "essay_questions": essay_count, "essay_count": essay_count,
        "theory_questions": essay_count, "theory_count": essay_count,

        "has_essay": has_essay, "hasEssay": has_essay,
        "essay_present": has_essay, "theory_present": has_essay,

        "essay_title": meta.get("essay_title", ""), "essay_instruction": meta.get("essay_instruction", ""),

        "size": get_file_size_kb(full_path), "status": status, "legacy": bool(legacy),
    }


# ============================================================
# LIBRARY FOLDER SCANNER
# ============================================================

def scan_library_folder(year, class_cat, folder, term=None, legacy=False):
    if not os.path.isdir(folder): return []

    try:
        entries = sorted(os.scandir(folder), key=lambda entry: entry.name.lower())
    except OSError as exc:
        print(f"[ERROR] Unable to scan {folder}: {exc}")
        return []

    items = []

    for entry in entries:
        if not entry.is_file(): continue

        filename = entry.name

        if not filename.lower().endswith(".json") or is_ignored_json(filename): continue

        location = f"{class_cat}/{term}/{filename}" if term else f"{class_cat}/{filename}"
        print(f"        [FOUND] {location}")

        items.append(build_library_item(
            year=year, filename=filename, full_path=entry.path,
            class_cat=class_cat, term=term, legacy=legacy,
        ))

    return items


# ============================================================
# OPTIONAL UPLOAD API
# ============================================================

@uploads_bp.route("/upload", methods=["POST"])
def upload_handler():
    if "file" not in request.files: return jsonify({"success": False, "error": "No file part"}), 400

    files = request.files.getlist("file")
    if not files: return jsonify({"success": False, "error": "No selected files"}), 400

    year = str(request.form.get("year", "")).strip()
    if not valid_year(year): return jsonify({"success": False, "error": "Missing or invalid year"}), 400

    requested_class = normalize_class(request.form.get("class") or request.form.get("class_category") or request.form.get("class_level"))

    raw_requested_term = str(request.form.get("term") or "").strip()
    requested_term = normalize_term(raw_requested_term)

    if raw_requested_term and not requested_term:
        return jsonify({"success": False, "error": "Invalid term. Use FIRST, SECOND or THIRD"}), 400

    results, failed = [], []

    for file in files:
        original_name, fname = file.filename or "", safe_filename(file.filename or "")

        if not fname or not allowed_file(fname):
            failed.append({"filename": original_name, "reason": "Unsupported file"})
            continue

        filename_class = detect_class_from_filename(fname)
        class_cat = requested_class if requested_class in SUPPORTED_CLASSES else filename_class

        # ========================================================
        # JSON UPLOAD
        # ========================================================

        if fname.lower().endswith(".json"):
            try:
                data = json.load(file.stream)
                file.stream.seek(0)
            except Exception as exc:
                failed.append({"filename": fname, "reason": f"Invalid JSON: {exc}"})
                continue

            if not isinstance(data, dict):
                failed.append({"filename": fname, "reason": "JSON root must be an object"})
                continue

            detected_class = detect_class_from_json(data) or class_cat or filename_class
            if detected_class: class_cat = normalize_class(detected_class)

            if class_cat not in SUPPORTED_CLASSES:
                failed.append({"filename": fname, "reason": "Class could not be detected"})
                continue

            data["class_category"], data["class_level"] = class_cat, class_cat

            # ----------------------------------------------------
            # JSS — STRICT TERM
            # ----------------------------------------------------

            if is_term_aware_class(class_cat):
                term = requested_term or detect_term(fname, data)

                if not term:
                    failed.append({
                        "filename": fname, "class_category": class_cat,
                        "reason": "JSS JSON requires FIRST, SECOND or THIRD term",
                    })
                    continue

                data["term"], data["term_label"] = term, term_label(term)
                save_folder = get_term_path(year, class_cat, term)

                if not save_folder:
                    failed.append({"filename": fname, "class_category": class_cat, "reason": "Invalid JSS term"})
                    continue

            # ----------------------------------------------------
            # SS — HYBRID / OPTIONAL TERM
            # ----------------------------------------------------

            else:
                # Selected UI term has priority. If no term was explicitly selected,
                # term may still be detected from JSON metadata or filename.
                term = requested_term or detect_term(fname, data)

                if term:
                    data["term"], data["term_label"] = term, term_label(term)
                    save_folder = get_term_path(year, class_cat, term)

                else:
                    # No term = preserve existing general/root SS behaviour.
                    data.pop("term", None)
                    data.pop("term_label", None)
                    data.pop("exam_term", None)
                    data.pop("academic_term", None)
                    data.pop("term_name", None)

                    save_folder = get_class_path(year, class_cat)

            if not save_folder:
                failed.append({"filename": fname, "class_category": class_cat, "reason": "Unable to determine save folder"})
                continue

            os.makedirs(save_folder, exist_ok=True)
            save_path = os.path.join(save_folder, fname)

            try:
                with open(save_path, "w", encoding="utf-8") as output: json.dump(data, output, indent=4, ensure_ascii=False)
            except Exception as exc:
                failed.append({"filename": fname, "reason": f"Failed to save JSON: {exc}"})
                continue

        # ========================================================
        # DOCX UPLOAD
        # ========================================================

        else:
            if class_cat not in SUPPORTED_CLASSES:
                failed.append({"filename": fname, "reason": "Class could not be detected from DOCX filename"})
                continue

            # Preserve the existing DOCX upload behaviour.
            term = requested_term if is_term_aware_class(class_cat) else None

            class_folder = get_class_path(year, class_cat)
            os.makedirs(class_folder, exist_ok=True)
            save_path = os.path.join(class_folder, fname)

            try: file.save(save_path)
            except Exception as exc:
                failed.append({"filename": fname, "reason": f"Failed to save DOCX: {exc}"})
                continue

        results.append({
            "filename": fname, "year": int(year),
            "class_category": class_cat, "class_level": class_cat,
            "term": term, "term_label": term_label(term),
            "status": "saved",
        })

    return jsonify({
        "success": bool(results),
        "uploads": results, "failed": failed,
        "uploaded_count": len(results), "failed_count": len(failed),
    })


# ============================================================
# LIST JSON FILES FOR YEAR
#
# JSS — STRICT:
#   JSS1/FIRST/*.json
#   JSS1/SECOND/*.json
#   JSS1/THIRD/*.json
#
# SS — HYBRID:
#   SS1/*.json
#   SS1/FIRST/*.json
#   SS1/SECOND/*.json
#   SS1/THIRD/*.json
# ============================================================

@uploads_bp.route("/uploads/<year>", methods=["GET"])
def list_year_files(year):
    year = str(year or "").strip()

    if not valid_year(year):
        return jsonify({"success": False, "error": "Invalid year", "uploads": []}), 400

    year_folder = get_year_path(year)

    print("\n" + "=" * 90)
    print(f"EMIS UPLOAD LIBRARY SCAN | YEAR={year}")
    print(f"BASE_DIR      : {BASE_DIR}")
    print(f"SUBJECTS_ROOT : {SUBJECTS_ROOT}")
    print(f"YEAR_FOLDER   : {year_folder}")
    print(f"YEAR_EXISTS   : {os.path.isdir(year_folder)}")
    print("=" * 90)

    if not os.path.isdir(year_folder):
        return jsonify({"success": True, "year": int(year), "count": 0, "uploads": []})

    results = []

    for class_cat in SUPPORTED_CLASSES:
        class_folder = get_class_path(year, class_cat)

        print(f"[CLASS] {class_cat:<4} | {class_folder} | exists={os.path.isdir(class_folder)}")

        if not os.path.isdir(class_folder): continue

        # ========================================================
        # JSS1 / JSS2 / JSS3 — STRICT TERM FOLDERS
        # ========================================================

        if is_term_aware_class(class_cat):
            for term in ("FIRST", "SECOND", "THIRD"):
                term_folder = os.path.join(class_folder, term)

                print(f"    [TERM] {term:<6} | {term_folder} | exists={os.path.isdir(term_folder)}")

                results.extend(scan_library_folder(
                    year=year, class_cat=class_cat,
                    folder=term_folder, term=term, legacy=False,
                ))

            # Legacy flat JSS support remains available.
            # Example: JSS1/mathematics_jss1.json
            results.extend(scan_library_folder(
                year=year, class_cat=class_cat,
                folder=class_folder, term=None, legacy=True,
            ))

        # ========================================================
        # SS1 / SS2 / SS3 — HYBRID ROOT + TERM FOLDERS
        # ========================================================

        else:
            # General/root SS JSONs.
            print(f"    [GENERAL] {class_folder}")

            results.extend(scan_library_folder(
                year=year, class_cat=class_cat,
                folder=class_folder, term=None, legacy=False,
            ))

            # Optional FIRST / SECOND / THIRD SS JSONs.
            for term in ("FIRST", "SECOND", "THIRD"):
                term_folder = os.path.join(class_folder, term)

                print(f"    [TERM] {term:<6} | {term_folder} | exists={os.path.isdir(term_folder)}")

                results.extend(scan_library_folder(
                    year=year, class_cat=class_cat,
                    folder=term_folder, term=term, legacy=False,
                ))

    # ========================================================
    # SORT RESULTS
    # ========================================================

    class_order = {class_name: index for index, class_name in enumerate(SUPPORTED_CLASSES)}

    results.sort(key=lambda item: (
        class_order.get(item.get("class_category"), 999),
        TERM_ORDER.get(item.get("term"), 999),
        str(item.get("subject", "")).lower(),
        str(item.get("filename", "")).lower(),
    ))

    print("-" * 90)
    print(f"TOTAL FILES RETURNED FOR {year}: {len(results)}")

    for item in results:
        print(f" -> {item.get('class_category')} | {item.get('term') or 'GENERAL'} | {item.get('filename')}")

    print("=" * 90 + "\n")

    return jsonify({
        "success": True, "year": int(year),
        "count": len(results), "uploads": results,
    })


# ============================================================
# PREVIEW JSON
#
# JSS:
# /uploads/2017/mathematics_jss1.json?class=JSS1&term=FIRST
#
# SS GENERAL:
# /uploads/2026/mathematics_ss1.json?class=SS1
#
# SS TERM:
# /uploads/2026/mathematics_ss1.json?class=SS1&term=FIRST
# ============================================================

@uploads_bp.route("/uploads/<year>/<filename>", methods=["GET"])
def preview_json(year, filename):
    year = str(year or "").strip()
    if not valid_year(year): return jsonify({"error": "Invalid year"}), 400

    filename = safe_filename(filename)
    if not filename or not filename.lower().endswith(".json"): return jsonify({"error": "Invalid JSON filename"}), 400

    class_cat = request.args.get("class") or request.args.get("class_category") or detect_class_from_filename(filename)
    class_cat = normalize_class(class_cat)

    if class_cat not in SUPPORTED_CLASSES: return jsonify({"error": "Cannot detect class from filename"}), 400

    raw_term = str(request.args.get("term") or "").strip()
    term = normalize_term(raw_term)

    if raw_term and not term: return jsonify({"error": "Invalid term. Use FIRST, SECOND or THIRD"}), 400

    # JSS must always specify its term.
    if is_term_aware_class(class_cat) and not term:
        return jsonify({"error": "Term is required for JSS JSON preview"}), 400

    # SS may have term or remain general/root.
    json_path = get_json_path(year, class_cat, filename, term)

    print("\n" + "=" * 90)
    print("EMIS JSON PREVIEW")
    print(f"YEAR      : {year}")
    print(f"CLASS     : {class_cat}")
    print(f"TERM      : {term or 'GENERAL'}")
    print(f"FILENAME  : {filename}")
    print(f"JSON PATH : {json_path}")
    print(f"EXISTS    : {bool(json_path and os.path.isfile(json_path))}")
    print("=" * 90)

    if not json_path or not os.path.isfile(json_path):
        return jsonify({
            "error": "Not found", "year": int(year),
            "class_category": class_cat, "term": term,
            "filename": filename,
        }), 404

    data, error = read_json_file(json_path)

    if error:
        print(f"Preview JSON error [{json_path}]: {error}")
        return jsonify({"error": "Failed to read JSON", "details": error}), 500

    essay = data.get("essay") if isinstance(data, dict) else None
    essay_questions = essay.get("questions", []) if isinstance(essay, dict) else []

    print(f"QUESTIONS : {len(data.get('questions', [])) if isinstance(data.get('questions'), list) else 0}")
    print(f"HAS ESSAY : {isinstance(essay, dict)}")
    print(f"ESSAY Qs  : {len(essay_questions) if isinstance(essay_questions, list) else 0}")
    print("=" * 90 + "\n")

    response = jsonify(data)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

    return response


# ============================================================
# DELETE JSON
#
# JSS:
# /uploads/2017/delete/mathematics_jss1.json?class=JSS1&term=FIRST
#
# SS GENERAL:
# /uploads/2026/delete/mathematics_ss1.json?class=SS1
#
# SS TERM:
# /uploads/2026/delete/mathematics_ss1.json?class=SS1&term=FIRST
# ============================================================

@uploads_bp.route("/uploads/<year>/delete/<filename>", methods=["DELETE"])
def delete_json(year, filename):
    year = str(year or "").strip()
    if not valid_year(year): return jsonify({"error": "Invalid year"}), 400

    filename = safe_filename(filename)
    if not filename or not filename.lower().endswith(".json"): return jsonify({"error": "Invalid JSON filename"}), 400

    class_cat = request.args.get("class") or request.args.get("class_category") or detect_class_from_filename(filename)
    class_cat = normalize_class(class_cat)

    if class_cat not in SUPPORTED_CLASSES: return jsonify({"error": "Cannot detect class"}), 400

    raw_term = str(request.args.get("term") or "").strip()
    term = normalize_term(raw_term)

    if raw_term and not term: return jsonify({"error": "Invalid term. Use FIRST, SECOND or THIRD"}), 400

    # JSS deletion always requires a specific term.
    if is_term_aware_class(class_cat) and not term:
        return jsonify({"error": "Term is required for JSS deletion"}), 400

    # SS deletion:
    # term supplied    -> delete from SS1/FIRST etc.
    # no term supplied -> delete from SS1 root/general.
    json_path = get_json_path(year, class_cat, filename, term)

    if not json_path or not os.path.isfile(json_path):
        return jsonify({
            "error": "File not found", "year": int(year),
            "class_category": class_cat, "term": term,
            "filename": filename,
        }), 404

    try:
        os.remove(json_path)

        return jsonify({
            "success": True, "deleted": filename,
            "year": int(year),
            "class_category": class_cat, "class_level": class_cat,
            "term": term, "term_label": term_label(term),
        })

    except Exception as exc:
        print(f"Delete JSON error [{json_path}]: {exc}")
        return jsonify({"error": "Failed to delete", "details": str(exc)}), 500