# modules/excel_manager.py

from pathlib import Path
from openpyxl import Workbook, load_workbook
from datetime import datetime

from modules.class_config import SUPPORTED_CLASSES


BASE_DIR = Path(__file__).resolve().parent.parent
RESULTS_BASE = BASE_DIR / "RESULTS"


# =========================================================
# Ensure folder exists
# =========================================================
def ensure_folder(path: Path):
    path.mkdir(parents=True, exist_ok=True)
    return path


# =========================================================
# Normalize class category
# Accepts:
#   JSS1A -> JSS1
#   SS1_GOLD -> SS1
#   SS2_B -> SS2
# =========================================================
def normalize_class_category(class_category: str):
    value = str(class_category or "").upper().strip()

    if value in SUPPORTED_CLASSES:
        return value

    for cls in SUPPORTED_CLASSES:
        if value.startswith(cls):
            return cls

    return "UNKNOWN"


# =========================================================
# Normalize subject folder name
# =========================================================
def normalize_subject(subject: str):
    if not subject:
        return "Unknown"

    key = str(subject).strip().lower()

    mapping = {
        # Existing SS subjects
        "biology": "Biology",
        "chemistry": "Chemistry",

        "civic education": "Civic_education",
        "civic": "Civic_education",

        "computer science": "Computer_studies",
        "computer studies": "Computer_studies",
        "computer": "Computer_studies",

        "economics": "Economics",

        "english language": "English_language",
        "english": "English_language",

        "financial accounting": "Financial_accounting",
        "financial account": "Financial_accounting",
        "accounting": "Financial_accounting",
        "accounts": "Financial_accounting",

        "geography": "Geography",
        "government": "Government",

        "literature-in-english": "Literature",
        "literature in english": "Literature",
        "literature": "Literature",

        "mathematics": "Mathematics",
        "maths": "Mathematics",

        "physics": "Physics",

        "technical drawing": "Technical",
        "technical": "Technical",

        # New JSS / full-school subjects
        "yoruba language": "Yoruba_language",
        "yoruba": "Yoruba_language",

        "history": "History",

        "irk": "IRK",
        "irs": "IRS",

        "cca": "CCA",

        "arabic language": "Arabic_language",
        "arabic": "Arabic_language",

        "business studies": "Business_studies",

        "poise": "Poise",

        "islamiyyah": "Islamiyyah",

        "hort & crop production": "Hort_crop_production",
        "hort and crop production": "Hort_crop_production",

        "digital tech.": "Digital_tech",
        "digital tech": "Digital_tech",
        "digital technology": "Digital_tech",

        "inter science": "Inter_science",
        "integrated science": "Inter_science",

        "garment making": "Garment_making",

        "soc. & cit. std": "Soc_cit_std",
        "soc & cit std": "Soc_cit_std",
        "social and citizenship studies": "Soc_cit_std",

        "p.h.e": "PHE",
        "phe": "PHE",

        "bst": "BST",

        "national value": "National_value",
        "national values": "National_value",

        "pvs": "PVS",

        "hausa language": "Hausa_language",
        "hausa": "Hausa_language",

        "cit & her. std": "Cit_her_std",
        "cit and her std": "Cit_her_std",
        "civic and heritage studies": "Cit_her_std",

        "commerce": "Commerce",

        "marketing": "Marketing",

        "further mathematics": "Further_mathematics",
        "further maths": "Further_mathematics",

        "agricultural science": "Agricultural_science",
        "agriculture": "Agricultural_science",
    }

    if key in mapping:
        return mapping[key]

    return (
        str(subject)
        .strip()
        .replace("&", "and")
        .replace(".", "")
        .replace("-", "_")
        .replace("/", "_")
        .replace(" ", "_")
        .capitalize()
    )


# =========================================================
# Build Excel path
# RESULTS/<YEAR>/CLASS/<JSS1-SS3>/<Subject>/results.xlsx
# =========================================================
def get_excel_path(class_category: str, subject: str, year: str):
    year = str(year or datetime.now().year).strip()
    class_cat = normalize_class_category(class_category)

    year_folder = ensure_folder(RESULTS_BASE / year)
    class_root = ensure_folder(year_folder / "CLASS")
    class_folder = ensure_folder(class_root / class_cat)
    subject_folder = ensure_folder(class_folder / normalize_subject(subject))

    return subject_folder / "results.xlsx"


# =========================================================
# Excel headers
# =========================================================
EXPECTED_HEADERS = [
    "Student Name",
    "Admission No",
    "Class",
    "Subject",
    "Score (%)",
    "Correct",
    "Total",
    "Status",
    "Time Taken",
    "Submitted At",
]


# =========================================================
# Repair missing/corrupt headers
# =========================================================
def repair_missing_headers(ws):
    rows = list(ws.iter_rows(values_only=True))

    if not rows:
        for col, val in enumerate(EXPECTED_HEADERS, start=1):
            ws.cell(row=1, column=col).value = val
        return EXPECTED_HEADERS

    first_row = list(rows[0])

    if any(cell is None or str(cell).strip() == "" for cell in first_row):
        for col, val in enumerate(EXPECTED_HEADERS, start=1):
            ws.cell(row=1, column=col).value = val
        return EXPECTED_HEADERS

    if first_row[0] not in ("Student Name", "Name", "Full Name"):
        ws.insert_rows(1)
        for col, val in enumerate(EXPECTED_HEADERS, start=1):
            ws.cell(row=1, column=col).value = val
        return EXPECTED_HEADERS

    if len(first_row) != len(EXPECTED_HEADERS):
        for col, val in enumerate(EXPECTED_HEADERS, start=1):
            ws.cell(row=1, column=col).value = val
        return EXPECTED_HEADERS

    return first_row


# =========================================================
# Append result to Excel
# =========================================================
def append_result_to_excel(result: dict):
    class_cat = normalize_class_category(
        result.get("class_category") or result.get("class_name")
    )

    subject = str(result.get("subject", "UNKNOWN")).strip()
    year = str(result.get("year", datetime.now().year)).strip()

    excel_path = get_excel_path(class_cat, subject, year)

    if not excel_path.exists():
        wb = Workbook()
        ws = wb.active
        ws.title = "Results"
        ws.append(EXPECTED_HEADERS)
        wb.save(excel_path)

    wb = load_workbook(excel_path)
    ws = wb.active

    repair_missing_headers(ws)

    score_percent = int(result.get("score") or 0)
    status = "PASS" if score_percent >= 50 else "FAIL"

    time_taken = (
        result.get("time_taken")
        or result.get("timeTaken")
        or 0
    )

    submitted_at = (
        result.get("submitted_at")
        or result.get("submittedAt")
        or datetime.now().strftime("%Y-%m-%d %H:%M")
    )

    ws.append([
        result.get("full_name"),
        result.get("admission_number"),
        class_cat,
        subject.upper(),
        f"{score_percent}%",
        result.get("correct", 0),
        result.get("total", 0),
        status,
        time_taken,
        submitted_at,
    ])

    wb.save(excel_path)
    return True


# =========================================================
# Read Excel results
# =========================================================
def read_results(class_category: str, subject: str, year: str):
    excel_path = get_excel_path(class_category, subject, year)

    if not excel_path.exists():
        return []

    wb = load_workbook(excel_path)
    ws = wb.active

    headers = repair_missing_headers(ws)
    rows = list(ws.iter_rows(values_only=True))

    wb.save(excel_path)

    if len(rows) < 2:
        return []

    data = []

    for row in rows[1:]:
        values = list(row)

        if len(values) == 10:
            mapped_values = values[:10]

        elif len(values) == 9:
            mapped_values = values[:8] + [None, values[8]]

        else:
            mapped_values = values[:len(EXPECTED_HEADERS)]
            if len(mapped_values) < len(EXPECTED_HEADERS):
                mapped_values += [None] * (
                    len(EXPECTED_HEADERS) - len(mapped_values)
                )

        row_dict = dict(zip(EXPECTED_HEADERS, mapped_values))

        if not row_dict.get("Admission No"):
            try:
                idx = headers.index("Admission Number")
                row_dict["Admission No"] = row[idx]
            except Exception:
                pass

        data.append(row_dict)

    return data


# =========================================================
# Student history across all years
# =========================================================
def read_student_history(full_name: str, class_category: str):
    results = []
    class_cat = normalize_class_category(class_category)

    if not RESULTS_BASE.exists():
        return results

    for year_folder in RESULTS_BASE.iterdir():
        if not year_folder.is_dir():
            continue

        class_root = year_folder / "CLASS" / class_cat

        if not class_root.exists():
            continue

        for subject_folder in class_root.iterdir():
            excel_file = subject_folder / "results.xlsx"

            if not excel_file.exists():
                continue

            wb = load_workbook(excel_file)
            ws = wb.active
            headers = repair_missing_headers(ws)
            rows = list(ws.iter_rows(values_only=True))
            wb.save(excel_file)

            if len(rows) < 2:
                continue

            for row in rows[1:]:
                values = list(row)

                if len(values) == 10:
                    mapped_values = values[:10]
                elif len(values) == 9:
                    mapped_values = values[:8] + [None, values[8]]
                else:
                    mapped_values = values[:len(EXPECTED_HEADERS)]
                    if len(mapped_values) < len(EXPECTED_HEADERS):
                        mapped_values += [None] * (
                            len(EXPECTED_HEADERS) - len(mapped_values)
                        )

                row_dict = dict(zip(EXPECTED_HEADERS, mapped_values))

                if (
                    str(row_dict.get("Student Name", "")).strip().upper()
                    == str(full_name or "").strip().upper()
                ):
                    row_dict["Year"] = year_folder.name
                    row_dict["Subject Folder"] = subject_folder.name
                    results.append(row_dict)

    return results