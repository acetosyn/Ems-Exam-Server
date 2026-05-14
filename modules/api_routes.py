# modules/api_routes.py

from flask import Blueprint, jsonify, request, session
from pathlib import Path
from openpyxl import Workbook, load_workbook

from modules.excel_manager import read_results, get_excel_path, EXPECTED_HEADERS, repair_missing_headers
from modules.class_config import SUPPORTED_CLASSES


api_bp = Blueprint("api_bp", __name__)

BASE_DIR = Path(__file__).resolve().parent.parent
RESULTS_DIR = BASE_DIR / "RESULTS"


# ============================================================
# Helper — Check Access Admin + Teacher
# ============================================================
def can_view_results():
    return str(session.get("user_type", "")).lower() in ["admin", "teacher"]


# ============================================================
# Helper — Normalize class
# ============================================================
def normalize_class(class_cat):
    value = str(class_cat or "").upper().strip()

    if value in SUPPORTED_CLASSES:
        return value

    for cls in SUPPORTED_CLASSES:
        if value.startswith(cls):
            return cls

    return ""


# ============================================================
# Helper — Clean row values
# ============================================================
def clean_records(records):
    clean = []

    for row in records:
        clean.append({
            k: (v if v is not None else "")
            for k, v in row.items()
        })

    return clean


# ============================================================
# Helper — Normalize score
# ============================================================
def normalize_score_value(value):
    raw = str(value or "").replace("%", "").strip()

    try:
        return int(float(raw))
    except Exception:
        return 0


# ============================================================
# Helper — Read direct Excel file without creating folders
# ============================================================
def read_excel_file_direct(excel_path: Path):
    if not excel_path.exists():
        return []

    wb = load_workbook(excel_path)
    ws = wb.active

    repair_missing_headers(ws)
    rows = list(ws.iter_rows(values_only=True))

    wb.save(excel_path)

    if len(rows) < 2:
        return []

    results = []

    for row in rows[1:]:
        values = list(row)

        if len(values) < len(EXPECTED_HEADERS):
            values += [None] * (len(EXPECTED_HEADERS) - len(values))

        row_dict = dict(zip(EXPECTED_HEADERS, values[:len(EXPECTED_HEADERS)]))

        if row_dict.get("Student Name") or row_dict.get("Admission No"):
            results.append(row_dict)

    return results


# ============================================================
# 1. Get Available YEARS
# ============================================================
@api_bp.route("/api/results/years")
def get_years():
    if not can_view_results():
        return jsonify({"error": "Unauthorized"}), 403

    if not RESULTS_DIR.exists():
        return jsonify({"years": []})

    years = sorted([
        f.name for f in RESULTS_DIR.iterdir()
        if f.is_dir()
    ], reverse=True)

    return jsonify({"years": years})


# ============================================================
# 2. Get CLASSES for selected YEAR
# ============================================================
@api_bp.route("/api/results/classes")
def get_classes_for_year():
    if not can_view_results():
        return jsonify({"error": "Unauthorized"}), 403

    year = request.args.get("year", "").strip()

    if not year:
        return jsonify({"classes": []})

    class_root = RESULTS_DIR / year / "CLASS"

    if not class_root.exists():
        return jsonify({"classes": []})

    classes = sorted([
        f.name for f in class_root.iterdir()
        if f.is_dir() and f.name in SUPPORTED_CLASSES
    ])

    return jsonify({"classes": classes})


# ============================================================
# 3. Get SUBJECTS for YEAR + CLASS
# ============================================================
@api_bp.route("/api/results/subjects")
def get_subjects_for_class_and_year():
    if not can_view_results():
        return jsonify({"error": "Unauthorized"}), 403

    year = request.args.get("year", "").strip()
    class_cat = normalize_class(request.args.get("class", ""))

    if not year or not class_cat:
        return jsonify({"subjects": []})

    class_folder = RESULTS_DIR / year / "CLASS" / class_cat

    if not class_folder.exists():
        return jsonify({"subjects": []})

    subjects = sorted([
        f.name for f in class_folder.iterdir()
        if f.is_dir()
    ])

    return jsonify({"subjects": subjects})


# ============================================================
# 4. Load Results — Single Year + Class + Subject
# ============================================================
@api_bp.route("/api/results/load")
def load_excel_results():
    if not can_view_results():
        return jsonify({"error": "Unauthorized"}), 403

    year = request.args.get("year", "").strip()
    class_cat = normalize_class(request.args.get("class", ""))
    subject = request.args.get("subject", "").strip()

    if not year or not class_cat or not subject:
        return jsonify({"error": "Missing parameters", "results": []}), 400

    try:
        records = read_results(class_cat, subject, year)

        for r in records:
            r["Year"] = year
            r["Class"] = r.get("Class") or class_cat
            r["Class Category"] = class_cat
            r["Subject Folder"] = subject

        return jsonify({"results": clean_records(records)}), 200

    except Exception as e:
        print("Error loading results:", e)
        return jsonify({"error": str(e), "results": []}), 500


# ============================================================
# 5. Check if Result Excel Exists
# ============================================================
@api_bp.route("/api/results/exists")
def excel_exists():
    if not can_view_results():
        return jsonify({"error": "Unauthorized"}), 403

    year = request.args.get("year", "").strip()
    class_cat = normalize_class(request.args.get("class", ""))
    subject = request.args.get("subject", "").strip()

    if not year or not class_cat or not subject:
        return jsonify({"exists": False})

    excel_path = get_excel_path(class_cat, subject, year)

    return jsonify({
        "exists": excel_path.exists(),
        "path": str(excel_path)
    })


# ============================================================
# 6. Main Admin Result Loader
# Supports:
#   /api/results?year=2026&class=JSS1&subject=Mathematics
#   /api/results?year=all&class=all&subject=all
# ============================================================
@api_bp.route("/api/results")
def api_get_results():
    if not can_view_results():
        return jsonify({"error": "Unauthorized", "results": []}), 403

    year = request.args.get("year", "").strip()
    class_cat_raw = request.args.get("class", "").strip()
    subject = request.args.get("subject", "").strip()

    if (
        not year
        or year.lower() == "all"
        or not class_cat_raw
        or class_cat_raw.lower() == "all"
        or not subject
        or subject.lower() == "all"
    ):
        return api_get_all_results()

    class_cat = normalize_class(class_cat_raw)

    if not class_cat:
        return jsonify({"error": "Invalid class", "results": []}), 400

    try:
        records = read_results(class_cat, subject, year)

        for r in records:
            r["Year"] = year
            r["Class"] = r.get("Class") or class_cat
            r["Class Category"] = class_cat
            r["Subject Folder"] = subject

        return jsonify({"results": clean_records(records)}), 200

    except Exception as e:
        print("Error reading results:", e)
        return jsonify({"error": "Failed to read results", "results": []}), 500


# ============================================================
# 6B. Load ALL RESULTS — JSS1 to SS3, all years, all subjects
# ============================================================
@api_bp.route("/api/results/all")
def api_get_all_results():
    if not can_view_results():
        return jsonify({"error": "Unauthorized", "results": []}), 403

    year_filter = request.args.get("year", "all").strip()
    class_filter = request.args.get("class", "all").strip().upper()
    subject_filter = request.args.get("subject", "all").strip()

    if not RESULTS_DIR.exists():
        return jsonify({
            "results": [],
            "summary": {
                "total": 0,
                "years": [],
                "classes": [],
                "subjects": []
            }
        })

    all_results = []
    years_found = set()
    classes_found = set()
    subjects_found = set()

    for year_folder in RESULTS_DIR.iterdir():
        if not year_folder.is_dir():
            continue

        year = year_folder.name

        if year_filter and year_filter.lower() != "all" and year != year_filter:
            continue

        class_root = year_folder / "CLASS"

        if not class_root.exists():
            continue

        for class_folder in class_root.iterdir():
            if not class_folder.is_dir():
                continue

            class_cat = normalize_class(class_folder.name)

            if not class_cat:
                continue

            if class_filter and class_filter.lower() != "all" and class_cat != class_filter:
                continue

            for subject_folder in class_folder.iterdir():
                if not subject_folder.is_dir():
                    continue

                subject_name = subject_folder.name

                if (
                    subject_filter
                    and subject_filter.lower() != "all"
                    and subject_filter.lower() not in subject_name.lower()
                ):
                    continue

                excel_path = subject_folder / "results.xlsx"

                if not excel_path.exists():
                    continue

                try:
                    records = read_excel_file_direct(excel_path)
                except Exception as e:
                    print(f"Could not read {excel_path}: {e}")
                    continue

                for r in records:
                    r["Year"] = year
                    r["Class"] = r.get("Class") or class_cat
                    r["Class Category"] = class_cat
                    r["Subject"] = r.get("Subject") or subject_name.replace("_", " ").upper()
                    r["Subject Folder"] = subject_name
                    r["Score Number"] = normalize_score_value(r.get("Score (%)"))

                    all_results.append(r)

                    years_found.add(year)
                    classes_found.add(class_cat)
                    subjects_found.add(subject_name)

    all_results.sort(
        key=lambda r: str(r.get("Submitted At", "")),
        reverse=True
    )

    return jsonify({
        "results": clean_records(all_results),
        "summary": {
            "total": len(all_results),
            "years": sorted(years_found, reverse=True),
            "classes": sorted(classes_found),
            "subjects": sorted(subjects_found)
        }
    }), 200


# ============================================================
# 7. Delete Selected Result Records
# Supports deleting from multiple result files
# ============================================================
@api_bp.route("/api/results/delete", methods=["POST"])
def delete_excel_results():
    if not can_view_results():
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json() or {}

    delete_list = data.get("delete_items", [])

    if not delete_list:
        return jsonify({"error": "No items to delete"}), 400

    grouped = {}

    for item in delete_list:
        year = str(item.get("Year") or data.get("year") or "").strip()
        class_cat = normalize_class(
            item.get("Class Category")
            or item.get("class_category")
            or item.get("Class")
            or data.get("class_category")
            or data.get("class")
        )
        subject = str(
            item.get("Subject Folder")
            or item.get("Subject")
            or data.get("subject")
            or ""
        ).strip()

        student_name = str(item.get("Student Name", "")).strip().upper()
        admission_no = str(item.get("Admission No", "")).strip().upper()

        if not year or not class_cat or not subject:
            continue

        if not student_name and not admission_no:
            continue

        key = (year, class_cat, subject)
        grouped.setdefault(key, set()).add((student_name, admission_no))

    if not grouped:
        return jsonify({"error": "Missing parameters"}), 400

    deleted_count = 0
    touched_files = 0

    for (year, class_cat, subject), delete_targets in grouped.items():
        excel_path = get_excel_path(class_cat, subject, year)

        if not excel_path.exists():
            continue

        results = read_results(class_cat, subject, year)

        updated = []

        for r in results:
            key = (
                str(r.get("Student Name", "")).strip().upper(),
                str(r.get("Admission No", "")).strip().upper()
            )

            if key in delete_targets:
                deleted_count += 1
            else:
                updated.append(r)

        wb = Workbook()
        ws = wb.active
        ws.title = "Results"
        ws.append(EXPECTED_HEADERS)

        for row in updated:
            ws.append([
                row.get("Student Name", ""),
                row.get("Admission No", ""),
                row.get("Class", ""),
                row.get("Subject", ""),
                row.get("Score (%)", ""),
                row.get("Correct", ""),
                row.get("Total", ""),
                row.get("Status", ""),
                row.get("Time Taken", ""),
                row.get("Submitted At", ""),
            ])

        wb.save(excel_path)
        touched_files += 1

    return jsonify({
        "status": "ok",
        "message": "Records deleted successfully",
        "deleted": deleted_count,
        "files_updated": touched_files
    })


# ============================================================
# 8. Global Search — Admission No + Student Name
# ============================================================
@api_bp.route("/api/results/search_admission")
def search_admission():
    if not can_view_results():
        return jsonify({"error": "Unauthorized"}), 403

    q = request.args.get("q", "").strip().lower()

    if len(q) < 2:
        return jsonify({"results": []})

    if not RESULTS_DIR.exists():
        return jsonify({"results": []})

    matches = []

    for year_folder in RESULTS_DIR.iterdir():
        if not year_folder.is_dir():
            continue

        year = year_folder.name
        class_root = year_folder / "CLASS"

        if not class_root.exists():
            continue

        for class_folder in class_root.iterdir():
            if not class_folder.is_dir():
                continue

            class_cat = normalize_class(class_folder.name)

            if not class_cat:
                continue

            for subject_folder in class_folder.iterdir():
                if not subject_folder.is_dir():
                    continue

                subject = subject_folder.name
                excel_path = subject_folder / "results.xlsx"

                if not excel_path.exists():
                    continue

                try:
                    records = read_excel_file_direct(excel_path)
                except Exception:
                    continue

                for row_dict in records:
                    admission = str(row_dict.get("Admission No", "")).strip().lower()
                    name = str(row_dict.get("Student Name", "")).strip().lower()

                    if q in admission or q in name:
                        row_dict["Year"] = year
                        row_dict["Class"] = row_dict.get("Class") or class_cat
                        row_dict["Class Category"] = class_cat
                        row_dict["Subject"] = row_dict.get("Subject") or subject
                        row_dict["Subject Folder"] = subject
                        matches.append(row_dict)

    return jsonify({"results": clean_records(matches)})