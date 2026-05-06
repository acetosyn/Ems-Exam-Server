# ============================================================
#   YEAR-AWARE EMIS RESULT ENGINE (FINAL 2025)
#   Admin can now:
#     ✓ Select YEAR
#     ✓ Select CLASS (SS1/SS2/SS3)
#     ✓ Select SUBJECT
#     ✓ Load/Delete results per YEAR
# ============================================================

from flask import Blueprint, jsonify, request, session
from pathlib import Path
from modules.excel_manager import read_results, get_excel_path

api_bp = Blueprint("api_bp", __name__)

BASE_DIR = Path(__file__).resolve().parent.parent
RESULTS_DIR = BASE_DIR / "RESULTS"


# ============================================================
#   Helper: Check Access (Admin + Teacher)
# ============================================================
def can_view_results():
    user = session.get("user_type")
    if not user:
        return False
    return user.lower() in ["admin", "teacher"]


# ============================================================
#   1️⃣ Get Available YEARS (based on RESULTS folder)
# ============================================================
@api_bp.route("/api/results/years")
def get_years():
    if not can_view_results():
        return jsonify({"error": "Unauthorized"}), 403

    if not RESULTS_DIR.exists():
        return jsonify({"years": []})

    years = sorted([f.name for f in RESULTS_DIR.iterdir() if f.is_dir()])
    return jsonify({"years": years})


# ============================================================
#   2️⃣ Get CLASSES for a given YEAR
#       Example: RESULTS/2023/CLASS/SS1
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

    classes = sorted([f.name for f in class_root.iterdir() if f.is_dir()])
    return jsonify({"classes": classes})


# ============================================================
#   3️⃣ Get SUBJECTS for YEAR + CLASS
#       Example: RESULTS/2023/CLASS/SS1/Biology
# ============================================================
@api_bp.route("/api/results/subjects")
def get_subjects_for_class_and_year():
    if not can_view_results():
        return jsonify({"error": "Unauthorized"}), 403

    year = request.args.get("year", "").strip()
    class_cat = request.args.get("class", "").strip().upper()

    if not year or not class_cat:
        return jsonify({"subjects": []})

    class_folder = RESULTS_DIR / year / "CLASS" / class_cat
    if not class_folder.exists():
        return jsonify({"subjects": []})

    subjects = sorted([f.name for f in class_folder.iterdir() if f.is_dir()])
    return jsonify({"subjects": subjects})


# ============================================================
#   4️⃣ LOAD RESULTS (YEAR + CLASS + SUBJECT)
# ============================================================
@api_bp.route("/api/results/load")
def load_excel_results():
    if not can_view_results():
        return jsonify({"error": "Unauthorized"}), 403

    year = request.args.get("year", "").strip()
    class_cat = request.args.get("class", "").strip().upper()
    subject = request.args.get("subject", "").strip()

    if not year or not class_cat or not subject:
        return jsonify({"error": "Missing parameters"}), 400

    try:
        records = read_results(class_cat, subject, year)
        return jsonify({"results": records}), 200
    except Exception as e:
        return jsonify({"error": str(e), "results": []})


# ============================================================
#   5️⃣ FILE CHECK — Does results.xlsx exist for YEAR?
# ============================================================
@api_bp.route("/api/results/exists")
def excel_exists():
    if not can_view_results():
        return jsonify({"error": "Unauthorized"}), 403

    year = request.args.get("year", "").strip()
    class_cat = request.args.get("class", "").strip().upper()
    subject = request.args.get("subject", "").strip()

    if not year or not class_cat or not subject:
        return jsonify({"exists": False})

    excel_path = get_excel_path(class_cat, subject, year)

    return jsonify({
        "exists": excel_path.exists(),
        "path": str(excel_path)
    })


# ============================================================
#   6️⃣ MAIN ADMIN RESULT LOADER (YEAR + CLASS + SUBJECT)
# ============================================================
@api_bp.route("/api/results")
def api_get_results():
    year = request.args.get("year", "").strip()
    class_cat = request.args.get("class", "").strip().upper()
    subject = request.args.get("subject", "").strip()

    if not year or not class_cat or not subject:
        return jsonify({"error": "Missing parameters", "results": []}), 400

    try:
        records = read_results(class_cat, subject, year)

        if not records:
            return jsonify({"results": []}), 200

        # Clean up None values (UI-friendly)
        clean_records = []
        for row in records:
            clean_row = {k: (v if v is not None else "") for k, v in row.items()}
            clean_records.append(clean_row)

        return jsonify({"results": clean_records}), 200

    except Exception as e:
        print("❌ ERROR reading results:", e)
        return jsonify({"error": "Failed to read results", "results": []}), 500


# ============================================================
#   7️⃣ DELETE RESULTS (YEAR + CLASS + SUBJECT)
# ============================================================
@api_bp.route("/api/results/delete", methods=["POST"])
def delete_excel_results():
    if not can_view_results():
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json()

    year = str(data.get("year"))
    class_cat = data.get("class_category", "").strip().upper()
    subject = data.get("subject", "").strip()
    delete_list = data.get("delete_items", [])

    if not year or not class_cat or not subject:
        return jsonify({"error": "Missing parameters"}), 400

    if not delete_list:
        return jsonify({"error": "No items to delete"}), 400

    excel_path = get_excel_path(class_cat, subject, year)

    if not excel_path.exists():
        return jsonify({"error": "Result file does not exist"}), 404

    # Load results
    results = read_results(class_cat, subject, year)

    # Normalize delete targets
    delete_targets = set(
        (item["Student Name"].strip().upper(), item["Admission No"].strip().upper())
        for item in delete_list
    )

    # Filter results
    updated = []
    for r in results:
        key = (
            str(r.get("Student Name", "")).strip().upper(),
            str(r.get("Admission No", "")).strip().upper()
        )
        if key not in delete_targets:
            updated.append(r)

    # Save back
    import pandas as pd
    df = pd.DataFrame(updated)
    df.to_excel(excel_path, index=False)

    return jsonify({"status": "ok", "message": "Records deleted successfully"})




# ============================================================
# 8️⃣ GLOBAL SEARCH — Admission No + Student Name (ANY YEAR)
# ============================================================
@api_bp.route("/api/results/search_admission")
def search_admission():
    if not can_view_results():
        return jsonify({"error": "Unauthorized"}), 403

    q = request.args.get("q", "").strip().lower()

    if len(q) < 2:
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

            class_cat = class_folder.name

            for subject_folder in class_folder.iterdir():
                if not subject_folder.is_dir():
                    continue

                subject = subject_folder.name
                excel_path = subject_folder / "results.xlsx"

                if not excel_path.exists():
                    continue

                import pandas as pd
                try:
                    df = pd.read_excel(excel_path)
                except Exception:
                    continue

                for _, row in df.iterrows():
                    admission = str(row.get("Admission No", "")).strip().lower()
                    name = str(row.get("Student Name", "")).strip().lower()

                    # ⭐ Match: admission, first name, last name, or partial
                    if q in admission or q in name:
                        row_dict = {k: (v if pd.notna(v) else "") for k, v in row.items()}
                        row_dict["Year"] = year
                        row_dict["Class"] = class_cat
                        row_dict["Subject"] = subject
                        matches.append(row_dict)

    return jsonify({"results": matches})
