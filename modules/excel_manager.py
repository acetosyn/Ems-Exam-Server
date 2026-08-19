# modules/excel_manager.py

from pathlib import Path
from datetime import datetime

from openpyxl import Workbook, load_workbook

from modules.class_config import SUPPORTED_CLASSES, normalize_class_level, normalize_class_arm


# =========================================================
# BASE PATHS
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent
RESULTS_BASE = BASE_DIR / "RESULTS"

VALID_TERMS = ("FIRST", "SECOND", "THIRD")


# =========================================================
# GENERAL HELPERS
# =========================================================

def ensure_folder(path: Path):
    path.mkdir(parents=True, exist_ok=True)
    return path


def normalize_class_category(class_category: str):
    level = normalize_class_level(class_category)
    return level if level in SUPPORTED_CLASSES else "UNKNOWN"


def normalize_result_class_arm(class_arm, fallback_level=""):
    arm = normalize_class_arm(class_arm, fallback_level)

    if arm:
        return arm

    level = normalize_class_category(fallback_level or class_arm)
    return level if level != "UNKNOWN" else "UNKNOWN"


def is_jss_class(class_category):
    class_level = normalize_class_category(class_category)
    return class_level != "UNKNOWN" and class_level.startswith("JSS")


# =========================================================
# TERM NORMALIZATION
# =========================================================

def normalize_result_term(value):
    raw = str(value or "").strip().upper().replace("_", " ").replace("-", " ")
    raw = " ".join(raw.split())

    aliases = {
        "FIRST": "FIRST", "FIRST TERM": "FIRST", "TERM 1": "FIRST", "TERM ONE": "FIRST", "1": "FIRST", "1ST": "FIRST", "1ST TERM": "FIRST",
        "SECOND": "SECOND", "SECOND TERM": "SECOND", "TERM 2": "SECOND", "TERM TWO": "SECOND", "2": "SECOND", "2ND": "SECOND", "2ND TERM": "SECOND",
        "THIRD": "THIRD", "THIRD TERM": "THIRD", "TERM 3": "THIRD", "TERM THREE": "THIRD", "3": "THIRD", "3RD": "THIRD", "3RD TERM": "THIRD",
    }

    return aliases.get(raw, "")


def result_term_label(value):
    term = normalize_result_term(value)
    return {"FIRST": "FIRST TERM", "SECOND": "SECOND TERM", "THIRD": "THIRD TERM"}.get(term, "")


# =========================================================
# SUBJECT NORMALIZATION
# =========================================================

def normalize_subject(subject: str):
    if not subject:
        return "Unknown"

    key = str(subject).strip().lower()

    mapping = {
        "biology": "Biology",
        "chemistry": "Chemistry",

        "civic education": "Civic_education", "civic": "Civic_education",

        "computer science": "Computer_studies", "computer studies": "Computer_studies", "computer": "Computer_studies",

        "economics": "Economics",

        "english language": "English_language", "english": "English_language",

        "financial accounting": "Financial_accounting", "financial account": "Financial_accounting",
        "accounting": "Financial_accounting", "accounts": "Financial_accounting", "account": "Financial_accounting",

        "geography": "Geography",
        "government": "Government",

        "literature-in-english": "Literature", "literature in english": "Literature", "literature": "Literature",

        "mathematics": "Mathematics", "maths": "Mathematics",

        "physics": "Physics",

        "technical drawing": "Technical", "technical": "Technical",

        "yoruba language": "Yoruba_language", "yoruba": "Yoruba_language",

        "history": "History",

        "irk": "IRK", "irs": "IRS",

        "cca": "CCA",

        "arabic language": "Arabic_language", "arabic": "Arabic_language",

        "business studies": "Business_studies",

        "poise": "Poise",

        "islamiyyah": "Islamiyyah", "islamiyah": "Islamiyyah",

        "hort & crop production": "Hort_crop_production",
        "hort and crop production": "Hort_crop_production",
        "horticulture and crop production": "Hort_crop_production",

        "digital tech.": "Digital_tech", "digital tech": "Digital_tech", "digital technology": "Digital_tech",

        "inter science": "Inter_science", "integrated science": "Inter_science",

        "garment making": "Garment_making",

        "soc. & cit. std": "Soc_cit_std", "soc & cit std": "Soc_cit_std", "social and citizenship studies": "Soc_cit_std",

        "p.h.e": "PHE", "p.h.e.": "PHE", "phe": "PHE", "physical health education": "PHE",

        "bst": "BST",

        "national value": "National_value", "national values": "National_value",

        "pvs": "PVS",

        "hausa language": "Hausa_language", "hausa": "Hausa_language",

        "cit & her. std": "Cit_her_std", "cit & her std": "Cit_her_std", "cit and her std": "Cit_her_std",
        "citizenship and heritage studies": "Cit_her_std", "heritage and citizenship studies": "Cit_her_std",
        "heritage & citizenship studies": "Cit_her_std", "civic and heritage studies": "Cit_her_std",

        "commerce": "Commerce",

        "marketing": "Marketing", "marketting": "Marketing",

        "further mathematics": "Further_mathematics", "further maths": "Further_mathematics",

        "agricultural science": "Agricultural_science", "agriculture": "Agricultural_science",
    }

    if key in mapping:
        return mapping[key]

    return str(subject).strip().replace("&", "and").replace(".", "").replace("-", "_").replace("/", "_").replace(" ", "_").capitalize()


# =========================================================
# RESULT PATH
#
# JSS:
# RESULTS/<year>/CLASS/JSS1/FIRST/Mathematics/results.xlsx
#
# SS:
# RESULTS/<year>/CLASS/SS1/Mathematics/results.xlsx
#
# Calling without term still supports legacy JSS paths.
# =========================================================

def get_excel_path(class_category: str, subject: str, year: str, term=""):
    year = str(year or datetime.now().year).strip()
    class_level = normalize_class_category(class_category)
    subject_folder_name = normalize_subject(subject)

    class_root = RESULTS_BASE / year / "CLASS" / class_level

    if is_jss_class(class_level):
        normalized_term = normalize_result_term(term)

        if normalized_term:
            return class_root / normalized_term / subject_folder_name / "results.xlsx"

    return class_root / subject_folder_name / "results.xlsx"


def get_preferred_excel_path(class_category: str, subject: str, year: str, term=""):
    class_level = normalize_class_category(class_category)
    normalized_term = normalize_result_term(term)

    if is_jss_class(class_level) and normalized_term:
        return get_excel_path(class_level, subject, year, normalized_term)

    return get_excel_path(class_level, subject, year)


def find_existing_excel_path(class_category: str, subject: str, year: str, term=""):
    class_level = normalize_class_category(class_category)
    normalized_term = normalize_result_term(term)

    if is_jss_class(class_level) and normalized_term:
        term_path = get_excel_path(class_level, subject, year, normalized_term)

        if term_path.exists():
            return term_path

    legacy_path = get_excel_path(class_level, subject, year)

    if legacy_path.exists():
        return legacy_path

    return get_preferred_excel_path(class_level, subject, year, normalized_term)


# =========================================================
# EXCEL HEADERS
# =========================================================

EXPECTED_HEADERS = [
    "Student Name",
    "Admission No",
    "Class Level",
    "Class Arm",
    "Subject",
    "Term",
    "Score (%)",
    "Correct",
    "Total",
    "Status",
    "Time Taken",
    "Submitted At",
]


# =========================================================
# HEADER ALIASES
# =========================================================

HEADER_ALIASES = {
    "Student Name": {"Student Name", "Name", "Full Name", "Full_Name"},
    "Admission No": {"Admission No", "Admission Number", "Admission_number", "Admission No.", "Admission"},
    "Class Level": {"Class Level", "Class Category", "Class_category", "ClassLevel"},
    "Class Arm": {"Class Arm", "Class", "Class Name", "Class_arm"},
    "Subject": {"Subject"},
    "Term": {"Term", "Exam Term", "Academic Term", "Term Name"},
    "Score (%)": {"Score (%)", "Score", "Percentage", "Percent"},
    "Correct": {"Correct", "Correct Answers"},
    "Total": {"Total", "Total Questions"},
    "Status": {"Status", "Result"},
    "Time Taken": {"Time Taken", "Time", "Duration"},
    "Submitted At": {"Submitted At", "Submitted", "Date", "Timestamp"},
}


def normalize_header_name(value):
    text = str(value or "").strip()

    for canonical, aliases in HEADER_ALIASES.items():
        if text in aliases:
            return canonical

    return text


# =========================================================
# WORKBOOK HEADER REPAIR
#
# Important difference:
# We DO NOT blindly shift existing columns when introducing
# Term. Old files continue mapping correctly.
# =========================================================

def repair_missing_headers(ws):
    if ws.max_row < 1 or ws.max_column < 1:
        for index, header in enumerate(EXPECTED_HEADERS, start=1):
            ws.cell(row=1, column=index).value = header

        return EXPECTED_HEADERS.copy()

    raw_headers = [ws.cell(row=1, column=index).value for index in range(1, ws.max_column + 1)]
    normalized_headers = [normalize_header_name(value) for value in raw_headers]

    header_matches = sum(1 for value in normalized_headers if value in EXPECTED_HEADERS)

    # Row one appears to contain data rather than headers.
    if header_matches < 2:
        ws.insert_rows(1)

        # Preserve legacy column order; Term is appended rather than
        # inserted into the middle of historical data.
        legacy_headers = [
            "Student Name", "Admission No", "Class Level", "Class Arm", "Subject",
            "Score (%)", "Correct", "Total", "Status", "Time Taken", "Submitted At",
        ]

        for index, header in enumerate(legacy_headers, start=1):
            ws.cell(row=1, column=index).value = header

        ws.cell(row=1, column=len(legacy_headers) + 1).value = "Term"

        return legacy_headers + ["Term"]

    # Canonicalize existing header names without changing positions.
    for index, header in enumerate(normalized_headers, start=1):
        ws.cell(row=1, column=index).value = header

    # Add any missing required headers to the END of the workbook.
    existing = set(normalized_headers)

    for header in EXPECTED_HEADERS:
        if header not in existing:
            ws.cell(row=1, column=ws.max_column + 1).value = header
            normalized_headers.append(header)
            existing.add(header)

    return normalized_headers


# =========================================================
# MAP RAW WORKSHEET ROW
# =========================================================

def map_result_row(row, headers=None):
    values = list(row or [])

    if not any(value is not None and str(value).strip() != "" for value in values):
        return None

    if headers:
        normalized_headers = [normalize_header_name(header) for header in headers]
        row_dict = {}

        for index, header in enumerate(normalized_headers):
            if not header:
                continue

            row_dict[header] = values[index] if index < len(values) else None

        for header in EXPECTED_HEADERS:
            row_dict.setdefault(header, None)

    else:
        # New 12-column format.
        if len(values) >= 12:
            mapped_values = values[:12]

        # Existing modern 11-column format — missing Term.
        elif len(values) == 11:
            mapped_values = [
                values[0], values[1], values[2], values[3], values[4],
                None,
                values[5], values[6], values[7], values[8], values[9], values[10],
            ]

        # Legacy 10-column format — missing Class Arm and Term.
        elif len(values) == 10:
            mapped_values = [
                values[0], values[1], values[2], values[2], values[3],
                None,
                values[4], values[5], values[6], values[7], values[8], values[9],
            ]

        # Legacy 9-column format — missing Class Arm, Term, Time.
        elif len(values) == 9:
            mapped_values = [
                values[0], values[1], values[2], values[2], values[3],
                None,
                values[4], values[5], values[6], values[7], None, values[8],
            ]

        else:
            mapped_values = values[:len(EXPECTED_HEADERS)]
            mapped_values += [None] * (len(EXPECTED_HEADERS) - len(mapped_values))

        row_dict = dict(zip(EXPECTED_HEADERS, mapped_values))

    raw_class_level = row_dict.get("Class Level") or row_dict.get("Class Arm")
    raw_class_arm = row_dict.get("Class Arm") or raw_class_level

    class_level = normalize_class_category(raw_class_level)
    class_arm = normalize_result_class_arm(raw_class_arm, class_level)

    if class_level != "UNKNOWN":
        row_dict["Class Level"] = class_level

    if class_arm != "UNKNOWN":
        row_dict["Class Arm"] = class_arm

    term = normalize_result_term(row_dict.get("Term"))

    row_dict["Term"] = term
    row_dict["Term Label"] = result_term_label(term) if term else ""

    return row_dict


# =========================================================
# CREATE RESULT WORKBOOK
# =========================================================

def create_results_workbook(excel_path: Path):
    ensure_folder(excel_path.parent)

    wb = Workbook()
    ws = wb.active
    ws.title = "Results"
    ws.append(EXPECTED_HEADERS)
    wb.save(excel_path)


# =========================================================
# APPEND RESULT TO EXCEL
# =========================================================

def append_result_to_excel(result: dict):
    raw_class_value = (
        result.get("class_level")
        or result.get("class_category")
        or result.get("class_name")
        or result.get("class")
        or result.get("class_arm")
    )

    class_level = normalize_class_category(raw_class_value)

    raw_class_arm = result.get("class_arm") or result.get("class") or result.get("class_name") or raw_class_value
    class_arm = normalize_result_class_arm(raw_class_arm, class_level)

    subject = str(result.get("subject", "UNKNOWN")).strip()
    year = str(result.get("year", datetime.now().year)).strip()

    term = normalize_result_term(result.get("term"))

    if is_jss_class(class_level) and not term:
        raise ValueError(f"Term is required when saving JSS result: class={class_level}, subject={subject}, year={year}")

    if not is_jss_class(class_level):
        term = ""

    excel_path = get_preferred_excel_path(class_level, subject, year, term)

    if not excel_path.exists():
        create_results_workbook(excel_path)

    wb = load_workbook(excel_path)
    ws = wb.active

    headers = repair_missing_headers(ws)

    try:
        score_value = result.get("score", result.get("score_percentage", result.get("percentage", result.get("Score (%)", 0))))
        score_percent = int(float(str(score_value or 0).replace("%", "").strip()))
    except (TypeError, ValueError):
        score_percent = 0

    status = str(result.get("status") or "").strip().upper()

    if status not in {"PASS", "FAIL"}:
        status = "PASS" if score_percent >= 50 else "FAIL"

    time_taken = result.get("time_taken") or result.get("timeTaken") or result.get("Time Taken") or 0
    submitted_at = result.get("submitted_at") or result.get("submittedAt") or datetime.now().strftime("%Y-%m-%d %H:%M")

    admission_number = (
        result.get("admission_number")
        or result.get("admission_no")
        or result.get("student_id")
        or ""
    )

    full_name = result.get("full_name") or result.get("student_name") or result.get("name") or ""

    row_data = {
        "Student Name": full_name,
        "Admission No": admission_number,
        "Class Level": class_level,
        "Class Arm": class_arm,
        "Subject": subject.upper(),
        "Term": term,
        "Score (%)": f"{score_percent}%",
        "Correct": result.get("correct", 0),
        "Total": result.get("total", 0),
        "Status": status,
        "Time Taken": time_taken,
        "Submitted At": submitted_at,
    }

    ws.append([row_data.get(header, "") for header in headers])

    wb.save(excel_path)

    return True


# =========================================================
# READ EXCEL RESULTS
#
# Optional term keeps old callers compatible:
#
# read_results(class, subject, year)
#
# New JSS usage:
#
# read_results(class, subject, year, term)
# =========================================================

def read_results(class_category: str, subject: str, year: str, term=""):
    class_level = normalize_class_category(class_category)
    normalized_term = normalize_result_term(term)

    paths_to_try = []

    if is_jss_class(class_level) and normalized_term:
        paths_to_try.append(get_excel_path(class_level, subject, year, normalized_term))

    # Legacy fallback.
    paths_to_try.append(get_excel_path(class_level, subject, year))

    seen_paths = set()

    for excel_path in paths_to_try:
        if excel_path in seen_paths:
            continue

        seen_paths.add(excel_path)

        if not excel_path.exists():
            continue

        try:
            wb = load_workbook(excel_path)
            ws = wb.active

            headers = repair_missing_headers(ws)
            rows = list(ws.iter_rows(values_only=True))

            wb.save(excel_path)

        except Exception as error:
            print(f"RESULT READ ERROR [{excel_path}]:", error)
            continue

        if len(rows) < 2:
            return []

        results = []

        for row in rows[1:]:
            row_dict = map_result_row(row, headers)

            if not row_dict:
                continue

            if normalized_term and is_jss_class(class_level):
                row_term = normalize_result_term(row_dict.get("Term"))

                # Result is physically inside the selected term folder,
                # so old rows without a Term cell inherit that folder.
                if not row_term and excel_path.parent.parent.name.upper() == normalized_term:
                    row_dict["Term"] = normalized_term
                    row_dict["Term Label"] = result_term_label(normalized_term)
                    row_term = normalized_term

                if row_term and row_term != normalized_term:
                    continue

            results.append(row_dict)

        return results

    return []


# =========================================================
# ITERATE RESULT FILES FOR CLASS
#
# Supports:
#   JSS term folders
#   legacy JSS folders
#   SS normal folders
# =========================================================

def iter_class_result_files(class_category):
    class_level = normalize_class_category(class_category)

    if not RESULTS_BASE.exists() or class_level == "UNKNOWN":
        return

    for year_folder in RESULTS_BASE.iterdir():
        if not year_folder.is_dir():
            continue

        class_root = year_folder / "CLASS" / class_level

        if not class_root.exists():
            continue

        if is_jss_class(class_level):
            # Term-aware structure.
            for term_folder in class_root.iterdir():
                if not term_folder.is_dir():
                    continue

                term = normalize_result_term(term_folder.name)

                if not term:
                    continue

                for subject_folder in term_folder.iterdir():
                    if not subject_folder.is_dir():
                        continue

                    excel_file = subject_folder / "results.xlsx"

                    if excel_file.exists():
                        yield {
                            "year": year_folder.name,
                            "term": term,
                            "subject_folder": subject_folder.name,
                            "path": excel_file,
                        }

            # Legacy flat JSS structure.
            for subject_folder in class_root.iterdir():
                if not subject_folder.is_dir() or normalize_result_term(subject_folder.name):
                    continue

                excel_file = subject_folder / "results.xlsx"

                if excel_file.exists():
                    yield {
                        "year": year_folder.name,
                        "term": "",
                        "subject_folder": subject_folder.name,
                        "path": excel_file,
                    }

        else:
            for subject_folder in class_root.iterdir():
                if not subject_folder.is_dir():
                    continue

                excel_file = subject_folder / "results.xlsx"

                if excel_file.exists():
                    yield {
                        "year": year_folder.name,
                        "term": "",
                        "subject_folder": subject_folder.name,
                        "path": excel_file,
                    }


# =========================================================
# READ STUDENT HISTORY
# =========================================================

def read_student_history(full_name: str, class_category: str):
    results = []
    target_name = str(full_name or "").strip().upper()

    if not target_name:
        return results

    for info in iter_class_result_files(class_category) or []:
        try:
            wb = load_workbook(info["path"])
            ws = wb.active

            headers = repair_missing_headers(ws)
            rows = list(ws.iter_rows(values_only=True))

            wb.save(info["path"])

        except Exception:
            continue

        for row in rows[1:]:
            row_dict = map_result_row(row, headers)

            if not row_dict:
                continue

            row_name = str(row_dict.get("Student Name", "")).strip().upper()

            if row_name != target_name:
                continue

            row_dict["Year"] = info["year"]
            row_dict["Subject Folder"] = info["subject_folder"]

            if info["term"] and not row_dict.get("Term"):
                row_dict["Term"] = info["term"]
                row_dict["Term Label"] = result_term_label(info["term"])

            results.append(row_dict)

    results.sort(key=lambda item: str(item.get("Submitted At", "")), reverse=True)

    return results


# ============================================================================
# STUDENT HISTORY BY ADMISSION NUMBER
# ============================================================================

def read_student_history_by_admission(admission_number: str, class_category: str):
    results = []
    target_admission = str(admission_number or "").strip().lower()

    if not target_admission:
        return results

    for info in iter_class_result_files(class_category) or []:
        try:
            wb = load_workbook(info["path"])
            ws = wb.active

            headers = repair_missing_headers(ws)
            rows = list(ws.iter_rows(values_only=True))

            wb.save(info["path"])

        except Exception:
            continue

        for row in rows[1:]:
            row_dict = map_result_row(row, headers)

            if not row_dict:
                continue

            row_admission = str(row_dict.get("Admission No", "")).strip().lower()

            if row_admission != target_admission:
                continue

            row_dict["Year"] = info["year"]
            row_dict["Subject Folder"] = info["subject_folder"]

            if info["term"] and not row_dict.get("Term"):
                row_dict["Term"] = info["term"]
                row_dict["Term Label"] = result_term_label(info["term"])

            results.append(row_dict)

    results.sort(key=lambda item: str(item.get("Submitted At", "")), reverse=True)

    return results