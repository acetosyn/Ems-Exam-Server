# modules/api_routes.py
from flask import Blueprint, jsonify, request, session, Response, stream_with_context
from pathlib import Path
from collections import deque
from threading import Lock
import json
import time
import uuid
import sqlite3
from datetime import datetime
from io import BytesIO
from flask import send_file
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.worksheet.page import PageMargins


from openpyxl import Workbook, load_workbook

from modules.supabase_results import (
    get_academic_settings,
    update_academic_settings,
)

from modules.excel_manager import (
    read_results,
    get_excel_path,
    EXPECTED_HEADERS,
    repair_missing_headers,
)

from modules.class_config import (
    SUPPORTED_CLASSES,
    normalize_class_level,
)


api_bp = Blueprint("api_bp", __name__)

BASE_DIR = Path(__file__).resolve().parent.parent
RESULTS_DIR = BASE_DIR / "RESULTS"


# ============================================================
# CONSTANTS
# ============================================================

VALID_TERMS = (
    "FIRST",
    "SECOND",
    "THIRD",
)

# ============================================================
# REAL-TIME ADMIN NOTIFICATION QUEUE
# Exact FIFO ordering, even when many students act together.
# ============================================================

ADMIN_NOTIFICATION_LIMIT = 1000
ADMIN_NOTIFICATIONS = deque(maxlen=ADMIN_NOTIFICATION_LIMIT)
ADMIN_NOTIFICATION_LOCK = Lock()
ADMIN_NOTIFICATION_SEQUENCE = 0


def push_admin_notification(event_type, message="", payload=None):
    global ADMIN_NOTIFICATION_SEQUENCE

    payload = payload if isinstance(payload, dict) else {}

    with ADMIN_NOTIFICATION_LOCK:
        ADMIN_NOTIFICATION_SEQUENCE += 1
        sequence = ADMIN_NOTIFICATION_SEQUENCE

        event = {
            "id": uuid.uuid4().hex,
            "sequence": sequence,
            "type": str(event_type or "notification").strip().lower(),
            "message": str(message or "").strip(),
            "payload": payload,
            "created_at": int(time.time() * 1000),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] if "datetime" in globals() else time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        ADMIN_NOTIFICATIONS.append(event)

    return event

# ============================================================
# HELPER — CHECK ACCESS ADMIN + TEACHER
# ============================================================

def can_view_results():
    return str(
        session.get("user_type", "")
    ).lower() in [
        "admin",
        "teacher",
    ]


# ============================================================
# HELPER — NORMALIZE CLASS LEVEL
#
# Accepts:
#   JSS1
#   JSS1A
#   JSS1B
#   SS1
#   SS1_GOLD
#   SS2B
#
# Returns:
#   JSS1
#   SS1
#   SS2
# ============================================================

def normalize_class(class_cat):
    return normalize_class_level(class_cat)


# ============================================================
# HELPER — IS JSS
# ============================================================

def is_jss_class(class_cat):
    class_level = normalize_class(class_cat)

    return bool(
        class_level
        and str(class_level).upper().startswith("JSS")
    )


# ============================================================
# HELPER — NORMALIZE TERM
#
# Accepts:
#   FIRST
#   FIRST TERM
#   first
#   1
#   TERM 1
#
# Returns:
#   FIRST
#   SECOND
#   THIRD
#   ""
# ============================================================

def normalize_term(value):
    raw = str(value or "").strip().upper()

    if not raw:
        return ""

    raw = (
        raw
        .replace("_", " ")
        .replace("-", " ")
    )

    raw = " ".join(raw.split())

    aliases = {
        "FIRST": "FIRST",
        "FIRST TERM": "FIRST",
        "TERM 1": "FIRST",
        "TERM ONE": "FIRST",
        "1": "FIRST",
        "1ST": "FIRST",
        "1ST TERM": "FIRST",

        "SECOND": "SECOND",
        "SECOND TERM": "SECOND",
        "TERM 2": "SECOND",
        "TERM TWO": "SECOND",
        "2": "SECOND",
        "2ND": "SECOND",
        "2ND TERM": "SECOND",

        "THIRD": "THIRD",
        "THIRD TERM": "THIRD",
        "TERM 3": "THIRD",
        "TERM THREE": "THIRD",
        "3": "THIRD",
        "3RD": "THIRD",
        "3RD TERM": "THIRD",
    }

    return aliases.get(raw, "")


# ============================================================
# HELPER — TERM LABEL
# ============================================================

def term_label(value):
    term = normalize_term(value)

    labels = {
        "FIRST": "FIRST TERM",
        "SECOND": "SECOND TERM",
        "THIRD": "THIRD TERM",
    }

    return labels.get(term, "")


# ============================================================
# HELPER — GET REQUESTED TERM
#
# Checks:
#   ?term=FIRST
#
# Then session:
#   selected_term
#
# Then academic settings.
# ============================================================

def get_requested_term(class_cat=""):
    if not is_jss_class(class_cat):
        return ""

    # --------------------------------------------------------
    # 1. Query string
    # --------------------------------------------------------

    term = normalize_term(
        request.args.get("term", "")
    )

    if term:
        return term

    # --------------------------------------------------------
    # 2. Session
    # --------------------------------------------------------

    term = normalize_term(
        session.get("selected_term", "")
    )

    if term:
        return term

    # --------------------------------------------------------
    # 3. Academic settings
    # --------------------------------------------------------

    try:
        settings = get_academic_settings() or {}

        term = normalize_term(
            settings.get("current_term", "")
        )

        if term:
            return term

    except Exception as error:
        print(
            "ACADEMIC TERM RESOLUTION ERROR:",
            error,
        )

    return ""


# ============================================================
# HELPER — CLEAN ROW VALUES
# ============================================================

def clean_records(records):
    clean = []

    for row in records:
        clean.append({
            key: (
                value
                if value is not None
                else ""
            )
            for key, value in row.items()
        })

    return clean


# ============================================================
# HELPER — NORMALIZE SCORE
# ============================================================

def normalize_score_value(value):
    raw = str(
        value or ""
    ).replace(
        "%",
        "",
    ).strip()

    try:
        return int(float(raw))

    except Exception:
        return 0


# ============================================================
# HELPER — NORMALIZE SUBJECT FOLDER
# ============================================================

def normalize_subject_folder(subject):
    return str(
        subject or ""
    ).strip()


# ============================================================
# HELPER — NORMALIZE RESULT RECORD
#
# Supports:
#
# Old:
#   Class
#
# New:
#   Class Level
#   Class Arm
#   Term
#
# Term is only mandatory for JSS.
# ============================================================

def normalize_result_record(
    row_dict,
    class_cat="",
    subject_name="",
    year="",
    term="",
):
    class_level_raw = (
        row_dict.get("Class Level")
        or row_dict.get("Class Category")
        or row_dict.get("Class")
        or class_cat
    )

    class_arm_raw = (
        row_dict.get("Class Arm")
        or row_dict.get("Class")
        or class_level_raw
    )

    class_level = (
        normalize_class(class_level_raw)
        or str(
            class_level_raw or ""
        ).upper().strip()
    )

    class_arm = str(
        class_arm_raw
        or class_level
    ).upper().strip()

    # --------------------------------------------------------
    # YEAR
    # --------------------------------------------------------

    row_dict["Year"] = (
        row_dict.get("Year")
        or year
    )

    # --------------------------------------------------------
    # CLASS
    # --------------------------------------------------------

    row_dict["Class Level"] = class_level
    row_dict["Class Arm"] = class_arm

    # Backward compatibility
    row_dict["Class"] = (
        class_arm
        or class_level
    )

    row_dict["Class Category"] = class_level

    # --------------------------------------------------------
    # TERM
    # --------------------------------------------------------

    row_term = normalize_term(
        row_dict.get("Term")
        or term
    )

    if is_jss_class(class_level):
        row_dict["Term"] = row_term
        row_dict["Term Label"] = term_label(
            row_term
        )
    else:
        # SS remains non-term based.
        row_dict["Term"] = (
            normalize_term(
                row_dict.get("Term")
            )
            or ""
        )

        row_dict["Term Label"] = (
            term_label(
                row_dict["Term"]
            )
            if row_dict["Term"]
            else ""
        )

    # --------------------------------------------------------
    # SUBJECT
    # --------------------------------------------------------

    row_dict["Subject"] = (
        row_dict.get("Subject")
        or str(
            subject_name or ""
        ).replace(
            "_",
            " ",
        ).upper()
    )

    row_dict["Subject Folder"] = (
        subject_name
    )

    # --------------------------------------------------------
    # SCORE
    # --------------------------------------------------------

    row_dict["Score Number"] = (
        normalize_score_value(
            row_dict.get("Score (%)")
        )
    )

    return row_dict


# ============================================================
# HELPER — READ DIRECT EXCEL FILE
#
# Does not create any folders.
# ============================================================

def read_excel_file_direct(excel_path: Path):
    if not excel_path.exists():
        return []

    wb = load_workbook(excel_path)
    ws = wb.active

    repair_missing_headers(ws)

    rows = list(
        ws.iter_rows(
            values_only=True
        )
    )

    # Preserve any repaired headers.
    wb.save(excel_path)

    if len(rows) < 2:
        return []

    headers = list(rows[0])
    results = []

    for row in rows[1:]:
        values = list(row)

        if len(values) < len(headers):
            values += (
                [None]
                * (
                    len(headers)
                    - len(values)
                )
            )

        row_dict = dict(
            zip(
                headers,
                values[:len(headers)],
            )
        )

        if (
            row_dict.get("Student Name")
            or row_dict.get("Admission No")
        ):
            results.append(
                row_dict
            )

    return results


# ============================================================
# HELPER — BUILD RESULT ROOT
#
# Base:
#
# RESULTS/<year>/CLASS/<class>/
# ============================================================

def get_class_result_root(
    year,
    class_cat,
):
    return (
        RESULTS_DIR
        / str(year)
        / "CLASS"
        / str(class_cat)
    )


# ============================================================
# HELPER — BUILD TERM-AWARE RESULT PATH
#
# Preferred JSS structure:
#
# RESULTS/
#   2017/
#     CLASS/
#       JSS1/
#         FIRST/
#           mathematics/
#             results.xlsx
#
# SS structure:
#
# RESULTS/
#   2026/
#     CLASS/
#       SS1/
#         mathematics/
#           results.xlsx
# ============================================================

def get_term_result_path(
    class_cat,
    subject,
    year,
    term="",
):
    class_cat = normalize_class(
        class_cat
    )

    subject = normalize_subject_folder(
        subject
    )

    year = str(
        year or ""
    ).strip()

    term = normalize_term(
        term
    )

    class_root = get_class_result_root(
        year,
        class_cat,
    )

    if is_jss_class(class_cat):
        if not term:
            return None

        return (
            class_root
            / term
            / subject
            / "results.xlsx"
        )

    return (
        class_root
        / subject
        / "results.xlsx"
    )


# ============================================================
# HELPER — LEGACY RESULT PATH
#
# Existing excel_manager structure.
# ============================================================

def get_legacy_result_path(
    class_cat,
    subject,
    year,
):
    try:
        return get_excel_path(
            class_cat,
            subject,
            year,
        )

    except Exception:
        return (
            RESULTS_DIR
            / str(year)
            / "CLASS"
            / str(class_cat)
            / str(subject)
            / "results.xlsx"
        )


# ============================================================
# HELPER — FIND EXISTING RESULT PATH
#
# Priority:
#
# JSS:
#   1. term-aware path
#   2. legacy path
#
# SS:
#   1. normal path
#   2. legacy get_excel_path()
# ============================================================

def find_existing_result_path(
    class_cat,
    subject,
    year,
    term="",
):
    class_cat = normalize_class(
        class_cat
    )

    term_path = get_term_result_path(
        class_cat,
        subject,
        year,
        term,
    )

    if (
        term_path
        and term_path.exists()
    ):
        return term_path

    legacy_path = get_legacy_result_path(
        class_cat,
        subject,
        year,
    )

    if (
        legacy_path
        and legacy_path.exists()
    ):
        return legacy_path

    # Return preferred path even if it doesn't exist.
    if term_path:
        return term_path

    return legacy_path



# ============================================================
# HELPER — READ RESULTS TERM AWARE
# ============================================================

def read_results_term_aware(class_cat, subject, year, term=""):
    class_cat = normalize_class(class_cat)
    term = normalize_term(term)

    excel_path = find_existing_result_path(class_cat, subject, year, term)

    if excel_path and excel_path.exists():
        return read_excel_file_direct(excel_path)

    try:
        return read_results(class_cat, subject, year, term)
    except Exception as error:
        print("TERM-AWARE RESULT READ FALLBACK ERROR:", error)
        return []

# ============================================================
# HELPER — GET TERMS FOR CLASS
# ============================================================

def get_terms_for_class(
    year,
    class_cat,
):
    class_cat = normalize_class(
        class_cat
    )

    if not is_jss_class(class_cat):
        return []

    class_root = get_class_result_root(
        year,
        class_cat,
    )

    if not class_root.exists():
        return []

    terms = []

    for folder in class_root.iterdir():
        if not folder.is_dir():
            continue

        normalized = normalize_term(
            folder.name
        )

        if normalized:
            terms.append(
                normalized
            )

    return sorted(
        set(terms),
        key=lambda value: (
            VALID_TERMS.index(value)
            if value in VALID_TERMS
            else 999
        ),
    )


# ============================================================
# HELPER — GET SUBJECT FOLDERS
# ============================================================

def get_subject_folders(
    year,
    class_cat,
    term="",
):
    class_cat = normalize_class(
        class_cat
    )

    class_root = get_class_result_root(
        year,
        class_cat,
    )

    if not class_root.exists():
        return []

    # --------------------------------------------------------
    # JSS
    # --------------------------------------------------------

    if is_jss_class(class_cat):
        term = normalize_term(
            term
        )

        if term:
            term_root = (
                class_root
                / term
            )

            if term_root.exists():
                return sorted([
                    folder.name
                    for folder in term_root.iterdir()
                    if (
                        folder.is_dir()
                        and not normalize_term(
                            folder.name
                        )
                    )
                ])

        # ----------------------------------------------------
        # Legacy JSS fallback
        #
        # Old structure:
        #
        # JSS1/
        #   mathematics/
        # ----------------------------------------------------

        return sorted([
            folder.name
            for folder in class_root.iterdir()
            if (
                folder.is_dir()
                and not normalize_term(
                    folder.name
                )
            )
        ])

    # --------------------------------------------------------
    # SS
    # --------------------------------------------------------

    return sorted([
        folder.name
        for folder in class_root.iterdir()
        if folder.is_dir()
    ])


# ============================================================
# HELPER — ITERATE RESULT FILES
#
# Returns:
#
# {
#   "year": ...,
#   "class": ...,
#   "term": ...,
#   "subject": ...,
#   "path": ...
# }
# ============================================================

def iter_result_files():
    if not RESULTS_DIR.exists():
        return

    for year_folder in RESULTS_DIR.iterdir():
        if not year_folder.is_dir():
            continue

        year = year_folder.name

        class_root = (
            year_folder
            / "CLASS"
        )

        if not class_root.exists():
            continue

        for class_folder in class_root.iterdir():
            if not class_folder.is_dir():
                continue

            class_cat = normalize_class(
                class_folder.name
            )

            if not class_cat:
                continue

            # =================================================
            # JSS
            # =================================================

            if is_jss_class(class_cat):

                # ---------------------------------------------
                # NEW TERM-AWARE STRUCTURE
                # ---------------------------------------------

                for term_folder in class_folder.iterdir():
                    if not term_folder.is_dir():
                        continue

                    term = normalize_term(
                        term_folder.name
                    )

                    if not term:
                        continue

                    for subject_folder in term_folder.iterdir():
                        if not subject_folder.is_dir():
                            continue

                        excel_path = (
                            subject_folder
                            / "results.xlsx"
                        )

                        if not excel_path.exists():
                            continue

                        yield {
                            "year": year,
                            "class": class_cat,
                            "term": term,
                            "subject": subject_folder.name,
                            "path": excel_path,
                        }

                # ---------------------------------------------
                # LEGACY JSS STRUCTURE
                #
                # JSS1/
                #   mathematics/
                #     results.xlsx
                # ---------------------------------------------

                for subject_folder in class_folder.iterdir():
                    if not subject_folder.is_dir():
                        continue

                    # Skip FIRST / SECOND / THIRD.
                    if normalize_term(
                        subject_folder.name
                    ):
                        continue

                    excel_path = (
                        subject_folder
                        / "results.xlsx"
                    )

                    if not excel_path.exists():
                        continue

                    yield {
                        "year": year,
                        "class": class_cat,
                        "term": "",
                        "subject": subject_folder.name,
                        "path": excel_path,
                    }

            # =================================================
            # SS
            # =================================================

            else:
                for subject_folder in class_folder.iterdir():
                    if not subject_folder.is_dir():
                        continue

                    excel_path = (
                        subject_folder
                        / "results.xlsx"
                    )

                    if not excel_path.exists():
                        continue

                    yield {
                        "year": year,
                        "class": class_cat,
                        "term": "",
                        "subject": subject_folder.name,
                        "path": excel_path,
                    }


# ============================================================
# HELPER — GET OUTPUT HEADERS
#
# Adds Term if the current EXPECTED_HEADERS does not contain it.
# This keeps compatibility with the existing Excel manager.
# ============================================================

def get_output_headers():
    headers = list(
        EXPECTED_HEADERS
    )

    if "Term" not in headers:
        # Put Term after Subject when possible.
        if "Subject" in headers:
            index = (
                headers.index("Subject")
                + 1
            )

            headers.insert(
                index,
                "Term",
            )
        else:
            headers.append(
                "Term"
            )

    return headers



# ============================================================
# STUDENT NOTIFICATION — EXAM START
# Called by exam-core.js only after questions load + timer starts
# ============================================================

@api_bp.route("/api/notifications/notify/exam_start", methods=["POST"])
def notify_exam_start():
    if str(session.get("user_type", "")).lower() != "student":
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json(silent=True) or {}
    student = session.get("student") if isinstance(session.get("student"), dict) else {}

    student_name = str(data.get("student_name") or session.get("student_name") or student.get("full_name") or "Student").strip()
    admission_number = str(data.get("admission_number") or session.get("admission_number") or student.get("admission_number") or "").strip()

    payload = {
        "student_name": student_name,
        "full_name": student_name,
        "admission_number": admission_number,
        "student_id": admission_number,
        "class_category": data.get("class_category") or session.get("class_category") or student.get("class_category") or "",
        "class_level": data.get("class_level") or session.get("class_level") or student.get("class_level") or "",
        "class_arm": data.get("class_arm") or session.get("class_arm") or student.get("class_arm") or "",
        "subject": data.get("subject") or session.get("selected_subject") or "",
        "year": str(data.get("year") or session.get("selected_year") or ""),
        "term": normalize_term(data.get("term") or session.get("selected_term") or ""),
        "term_label": data.get("term_label") or "",
        "started_at": data.get("started_at") or "",
    }

    event = push_admin_notification("exam_start", f"{student_name} started {payload['subject'] or 'an examination'}.", payload)

    print("[NOTIFICATION] EXAM START:", event["sequence"], admission_number, payload["subject"])

    return jsonify({"status": "ok", "notification": event}), 200




# ============================================================
# STUDENT NOTIFICATION — EXAM END
# Called by exam-core.js when exam is submitted / timed out
# ============================================================

@api_bp.route("/api/notifications/notify/exam_end", methods=["POST"])
def notify_exam_end():
    if str(session.get("user_type", "")).lower() != "student":
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json(silent=True) or {}
    student = session.get("student") if isinstance(session.get("student"), dict) else {}

    student_name = str(data.get("student_name") or session.get("student_name") or student.get("full_name") or "Student").strip()
    admission_number = str(data.get("admission_number") or session.get("admission_number") or student.get("admission_number") or "").strip()
    status = str(data.get("status") or "completed").strip().lower()

    payload = {
        "student_name": student_name,
        "full_name": student_name,
        "admission_number": admission_number,
        "student_id": admission_number,
        "class_category": data.get("class_category") or session.get("class_category") or student.get("class_category") or "",
        "class_level": data.get("class_level") or session.get("class_level") or student.get("class_level") or "",
        "class_arm": data.get("class_arm") or session.get("class_arm") or student.get("class_arm") or "",
        "subject": data.get("subject") or session.get("selected_subject") or "",
        "year": str(data.get("year") or session.get("selected_year") or ""),
        "term": normalize_term(data.get("term") or session.get("selected_term") or ""),
        "term_label": data.get("term_label") or "",
        "score": data.get("score", ""),
        "total_questions": data.get("total_questions", ""),
        "flagged": data.get("flagged", 0),
        "submitted_at": data.get("submitted_at") or "",
        "status": status,
    }

    event_type = "timeout" if status in {"timeout", "timed_out"} else "exam_end"
    event_message = f"{student_name}'s examination timed out." if event_type == "timeout" else f"{student_name} submitted {payload['subject'] or 'an examination'}."

    event = push_admin_notification(event_type, event_message, payload)

    print("[NOTIFICATION] EXAM END:", event["sequence"], admission_number, payload["subject"], status)

    return jsonify({"status": "ok", "notification": event}), 200




# ============================================================
# REAL-TIME NOTIFICATIONS — FETCH
# Uses sequence instead of timestamp for exact FIFO delivery.
# ============================================================

@api_bp.route("/api/notifications/fetch", methods=["GET"])
def fetch_admin_notifications():
    if not can_view_results():
        return jsonify({"error": "Unauthorized", "notifications": []}), 403

    try:
        since_sequence = int(request.args.get("since_sequence", 0) or 0)
    except (TypeError, ValueError):
        since_sequence = 0

    with ADMIN_NOTIFICATION_LOCK:
        notifications = [dict(item) for item in ADMIN_NOTIFICATIONS]

    if since_sequence > 0:
        notifications = [item for item in notifications if int(item.get("sequence", 0) or 0) > since_sequence]

    notifications.sort(key=lambda item: int(item.get("sequence", 0) or 0))

    latest_sequence = max([int(item.get("sequence", 0) or 0) for item in notifications], default=since_sequence)

    return jsonify({
        "notifications": notifications,
        "count": len(notifications),
        "latest_sequence": latest_sequence,
    }), 200

# ============================================================
# REAL-TIME NOTIFICATIONS — SERVER SENT EVENTS
# ============================================================

# ============================================================
# REAL-TIME NOTIFICATIONS — SERVER SENT EVENTS
# Exact FIFO delivery + polling-safe reconciliation
# ============================================================

@api_bp.route("/api/notifications/stream")
def stream_admin_notifications():
    if not can_view_results():
        return jsonify({"error": "Unauthorized"}), 403

    try:
        starting_sequence = int(request.args.get("since_sequence", 0) or 0)
    except (TypeError, ValueError):
        starting_sequence = 0

    @stream_with_context
    def event_stream():
        last_sequence = starting_sequence

        yield f'event: connected\ndata: {json.dumps({"status": "connected", "sequence": last_sequence})}\n\n'

        while True:
            with ADMIN_NOTIFICATION_LOCK:
                new_events = [dict(item) for item in ADMIN_NOTIFICATIONS if int(item.get("sequence", 0) or 0) > last_sequence]

            new_events.sort(key=lambda item: int(item.get("sequence", 0) or 0))

            for item in new_events:
                sequence = int(item.get("sequence", 0) or 0)
                last_sequence = max(last_sequence, sequence)
                yield f"event: notification\ndata: {json.dumps(item, ensure_ascii=False)}\n\n"

            yield ": keepalive\n\n"
            time.sleep(1)

    return Response(event_stream(), mimetype="text/event-stream", headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no", "Connection": "keep-alive"})


# ============================================================
# 1. GET AVAILABLE YEARS
# ============================================================

@api_bp.route("/api/results/years")
def get_years():
    if not can_view_results():
        return jsonify({
            "error": "Unauthorized"
        }), 403

    if not RESULTS_DIR.exists():
        return jsonify({
            "years": []
        })

    years = sorted(
        [
            folder.name
            for folder in RESULTS_DIR.iterdir()
            if folder.is_dir()
        ],
        reverse=True,
    )

    return jsonify({
        "years": years
    })


# ============================================================
# 2. GET CLASSES FOR SELECTED YEAR
# ============================================================

@api_bp.route("/api/results/classes")
def get_classes_for_year():
    if not can_view_results():
        return jsonify({
            "error": "Unauthorized"
        }), 403

    year = request.args.get(
        "year",
        "",
    ).strip()

    if not year:
        return jsonify({
            "classes": []
        })

    class_root = (
        RESULTS_DIR
        / year
        / "CLASS"
    )

    if not class_root.exists():
        return jsonify({
            "classes": []
        })

    classes = sorted([
        folder.name
        for folder in class_root.iterdir()
        if (
            folder.is_dir()
            and normalize_class(
                folder.name
            ) in SUPPORTED_CLASSES
        )
    ])

    return jsonify({
        "classes": classes
    })


# ============================================================
# 3. GET TERMS FOR YEAR + CLASS
#
# Example:
#
# /api/results/terms?year=2017&class=JSS1
#
# Response:
#
# {
#   "terms": ["FIRST", "SECOND", "THIRD"]
# }
#
# SS returns [].
# ============================================================

@api_bp.route("/api/results/terms")
def get_terms_for_year_and_class():
    if not can_view_results():
        return jsonify({
            "error": "Unauthorized"
        }), 403

    year = request.args.get(
        "year",
        "",
    ).strip()

    class_cat = normalize_class(
        request.args.get(
            "class",
            "",
        )
    )

    if not year or not class_cat:
        return jsonify({
            "terms": []
        })

    terms = get_terms_for_class(
        year,
        class_cat,
    )

    return jsonify({
        "terms": terms,
        "class": class_cat,
        "requires_term": is_jss_class(
            class_cat
        ),
    })


# ============================================================
# 4. GET SUBJECTS FOR YEAR + CLASS + TERM
#
# JSS:
#
# /api/results/subjects
#     ?year=2017
#     &class=JSS1
#     &term=FIRST
#
# SS:
#
# /api/results/subjects
#     ?year=2026
#     &class=SS1
# ============================================================

@api_bp.route("/api/results/subjects")
def get_subjects_for_class_and_year():
    if not can_view_results():
        return jsonify({
            "error": "Unauthorized"
        }), 403

    year = request.args.get(
        "year",
        "",
    ).strip()

    class_cat = normalize_class(
        request.args.get(
            "class",
            "",
        )
    )

    if not year or not class_cat:
        return jsonify({
            "subjects": []
        })

    term = get_requested_term(
        class_cat
    )

    subjects = get_subject_folders(
        year,
        class_cat,
        term,
    )

    return jsonify({
        "subjects": subjects,
        "year": year,
        "class": class_cat,
        "term": term,
        "requires_term": is_jss_class(
            class_cat
        ),
    })


# ============================================================
# 5. LOAD RESULTS
#
# JSS:
#
# /api/results/load
#   ?year=2017
#   &class=JSS1
#   &term=FIRST
#   &subject=mathematics
#
# SS:
#
# /api/results/load
#   ?year=2026
#   &class=SS1
#   &subject=mathematics
# ============================================================

@api_bp.route("/api/results/load")
def load_excel_results():
    if not can_view_results():
        return jsonify({"error": "Unauthorized", "results": []}), 403

    year = request.args.get("year", "").strip()
    class_cat = normalize_class(request.args.get("class", ""))
    subject = request.args.get("subject", "").strip()

    if not year or not class_cat or not subject:
        return jsonify({"error": "Missing parameters", "results": []}), 400

    term = get_requested_term(class_cat)

    if is_jss_class(class_cat) and not term:
        return jsonify({"error": "Term is required for JSS results", "results": []}), 400

    if not is_jss_class(class_cat):
        term = ""

    try:
        records = read_results_term_aware(class_cat, subject, year, term)

        for record in records:
            normalize_result_record(record, class_cat, subject, year, term)

        return jsonify({
            "results": clean_records(records),
            "year": year,
            "class": class_cat,
            "subject": subject,
            "term": term,
            "term_label": term_label(term) if term else "",
            "requires_term": is_jss_class(class_cat),
            "count": len(records),
        }), 200

    except Exception as error:
        print("Error loading results:", error)

        return jsonify({
            "error": "Failed to load results",
            "details": str(error),
            "results": [],
            "year": year,
            "class": class_cat,
            "subject": subject,
            "term": term,
        }), 500
    
# ============================================================
# 6. CHECK IF RESULT EXCEL EXISTS
# ============================================================

@api_bp.route("/api/results/exists")
def excel_exists():
    if not can_view_results():
        return jsonify({
            "error": "Unauthorized"
        }), 403

    year = request.args.get(
        "year",
        "",
    ).strip()

    class_cat = normalize_class(
        request.args.get(
            "class",
            "",
        )
    )

    subject = request.args.get(
        "subject",
        "",
    ).strip()

    if (
        not year
        or not class_cat
        or not subject
    ):
        return jsonify({
            "exists": False
        })

    term = get_requested_term(
        class_cat
    )

    if (
        is_jss_class(class_cat)
        and not term
    ):
        return jsonify({
            "exists": False,
            "error": "Term is required for JSS results",
        })

    excel_path = find_existing_result_path(
        class_cat,
        subject,
        year,
        term,
    )

    exists = bool(
        excel_path
        and excel_path.exists()
    )

    return jsonify({
        "exists": exists,
        "path": (
            str(excel_path)
            if excel_path
            else ""
        ),
        "year": year,
        "class": class_cat,
        "subject": subject,
        "term": term,
    })


# ============================================================
# 7. MAIN ADMIN RESULT LOADER
#
# Examples:
#
# JSS:
# /api/results
#   ?year=2017
#   &class=JSS1
#   &term=FIRST
#   &subject=Mathematics
#
# SS:
# /api/results
#   ?year=2026
#   &class=SS1
#   &subject=Mathematics
#
# ALL:
# /api/results
#   ?year=all
#   &class=all
#   &term=all
#   &subject=all
# ============================================================

@api_bp.route("/api/results")
def api_get_results():
    if not can_view_results():
        return jsonify({
            "error": "Unauthorized",
            "results": [],
        }), 403

    year = request.args.get(
        "year",
        "",
    ).strip()

    class_cat_raw = request.args.get(
        "class",
        "",
    ).strip()

    subject = request.args.get(
        "subject",
        "",
    ).strip()

    term_raw = request.args.get(
        "term",
        "",
    ).strip()

    if (
        not year
        or year.lower() == "all"
        or not class_cat_raw
        or class_cat_raw.lower() == "all"
        or not subject
        or subject.lower() == "all"
        or term_raw.lower() == "all"
    ):
        return api_get_all_results()

    class_cat = normalize_class(
        class_cat_raw
    )

    if not class_cat:
        return jsonify({
            "error": "Invalid class",
            "results": [],
        }), 400

    term = get_requested_term(
        class_cat
    )

    if (
        is_jss_class(class_cat)
        and not term
    ):
        return jsonify({
            "error": "Term is required for JSS results",
            "results": [],
        }), 400

    try:
        records = read_results_term_aware(
            class_cat,
            subject,
            year,
            term,
        )

        for record in records:
            normalize_result_record(
                record,
                class_cat,
                subject,
                year,
                term,
            )

        return jsonify({
            "results": clean_records(
                records
            ),
            "year": year,
            "class": class_cat,
            "subject": subject,
            "term": term,
        }), 200

    except Exception as error:
        print(
            "Error reading results:",
            error,
        )

        return jsonify({
            "error": "Failed to read results",
            "details": str(error),
            "results": [],
        }), 500


# ============================================================
# 7B. LOAD ALL RESULTS
#
# Supports filters:
#
# ?year=all
# ?class=all
# ?subject=all
# ?term=all
#
# JSS term folders are scanned automatically.
# SS remains non-term based.
# ============================================================

@api_bp.route("/api/results/all")
def api_get_all_results():
    if not can_view_results():
        return jsonify({
            "error": "Unauthorized",
            "results": [],
        }), 403

    year_filter = request.args.get(
        "year",
        "all",
    ).strip()

    class_filter_raw = request.args.get(
        "class",
        "all",
    ).strip()

    subject_filter = request.args.get(
        "subject",
        "all",
    ).strip()

    term_filter_raw = request.args.get(
        "term",
        "all",
    ).strip()

    class_filter = (
        normalize_class(
            class_filter_raw
        )
        if class_filter_raw.lower() != "all"
        else "all"
    )

    term_filter = (
        normalize_term(
            term_filter_raw
        )
        if term_filter_raw.lower() != "all"
        else "all"
    )

    if not RESULTS_DIR.exists():
        return jsonify({
            "results": [],
            "summary": {
                "total": 0,
                "years": [],
                "classes": [],
                "terms": [],
                "subjects": [],
            },
        })

    all_results = []

    years_found = set()
    classes_found = set()
    terms_found = set()
    subjects_found = set()

    for info in iter_result_files():

        year = info["year"]
        class_cat = info["class"]
        term = info["term"]
        subject_name = info["subject"]
        excel_path = info["path"]

        # ----------------------------------------------------
        # YEAR FILTER
        # ----------------------------------------------------

        if (
            year_filter
            and year_filter.lower() != "all"
            and year != year_filter
        ):
            continue

        # ----------------------------------------------------
        # CLASS FILTER
        # ----------------------------------------------------

        if (
            class_filter
            and class_filter != "all"
            and class_cat != class_filter
        ):
            continue

        # ----------------------------------------------------
        # TERM FILTER
        # ----------------------------------------------------

        if (
            term_filter != "all"
            and is_jss_class(class_cat)
            and term != term_filter
        ):
            continue

        # ----------------------------------------------------
        # SUBJECT FILTER
        # ----------------------------------------------------

        if (
            subject_filter
            and subject_filter.lower() != "all"
            and subject_filter.lower()
            not in subject_name.lower()
        ):
            continue

        try:
            records = read_excel_file_direct(
                excel_path
            )

        except Exception as error:
            print(
                f"Could not read {excel_path}: "
                f"{error}"
            )

            continue

        for record in records:
            normalize_result_record(
                record,
                class_cat,
                subject_name,
                year,
                term,
            )

            all_results.append(
                record
            )

            years_found.add(
                year
            )

            classes_found.add(
                class_cat
            )

            if term:
                terms_found.add(
                    term
                )

            subjects_found.add(
                subject_name
            )

    all_results.sort(
        key=lambda record: str(
            record.get(
                "Submitted At",
                "",
            )
        ),
        reverse=True,
    )

    return jsonify({
        "results": clean_records(
            all_results
        ),
        "summary": {
            "total": len(
                all_results
            ),
            "years": sorted(
                years_found,
                reverse=True,
            ),
            "classes": sorted(
                classes_found
            ),
            "terms": sorted(
                terms_found,
                key=lambda value: (
                    VALID_TERMS.index(value)
                    if value in VALID_TERMS
                    else 999
                ),
            ),
            "subjects": sorted(
                subjects_found
            ),
        },
    }), 200


# ============================================================
# 8. DELETE SELECTED RESULT RECORDS
#
# Term-aware for JSS.
#
# Each delete item can contain:
#
# Year
# Class Level
# Class Arm
# Subject
# Subject Folder
# Term
# Student Name
# Admission No
# ============================================================
# ============================================================
# DELETE RESULT RECORDS — PERMANENT
# ============================================================

@api_bp.route("/api/results/delete", methods=["POST"])
def delete_excel_results():
    if not can_view_results():
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json(silent=True) or {}
    delete_list = data.get("delete_items", [])

    if not isinstance(delete_list, list) or not delete_list:
        return jsonify({"error": "No items to delete"}), 400

    grouped = {}
    skipped = []

    # ========================================================
    # BUILD DELETE GROUPS
    # ========================================================

    for item in delete_list:
        if not isinstance(item, dict):
            continue

        year = str(item.get("Year") or item.get("year") or data.get("year") or "").strip()

        class_cat = normalize_class(
            item.get("Class Level")
            or item.get("Class Category")
            or item.get("class_level")
            or item.get("class_category")
            or item.get("Class")
            or item.get("class")
            or data.get("class_category")
            or data.get("class")
        )

        subject = str(
            item.get("Subject Folder")
            or item.get("subject_folder")
            or item.get("Subject")
            or item.get("subject")
            or data.get("subject")
            or ""
        ).strip()

        term = normalize_term(item.get("Term") or item.get("term") or data.get("term") or "")

        student_name = str(
            item.get("Student Name")
            or item.get("full_name")
            or item.get("student_name")
            or ""
        ).strip().upper()

        admission_no = str(
            item.get("Admission No")
            or item.get("admission_number")
            or item.get("student_id")
            or ""
        ).strip().upper()

        # ----------------------------------------------------
        # JSS TERM FALLBACK
        # ----------------------------------------------------

        if class_cat and is_jss_class(class_cat) and not term:
            term = get_requested_term(class_cat)

        # ----------------------------------------------------
        # BASIC VALIDATION
        # ----------------------------------------------------

        if not year or not class_cat or not subject:
            skipped.append({
                "reason": "Missing year, class or subject",
                "year": year,
                "class": class_cat,
                "subject": subject,
                "admission": admission_no,
            })
            continue

        if not student_name and not admission_no:
            skipped.append({
                "reason": "Missing student identity",
                "year": year,
                "class": class_cat,
                "subject": subject,
            })
            continue

        # ----------------------------------------------------
        # IMPORTANT:
        # JSS WITHOUT TERM IS ALLOWED HERE.
        #
        # The delete engine will search FIRST/SECOND/THIRD
        # instead of rejecting immediately.
        # ----------------------------------------------------

        key = (year, class_cat, term, subject)

        grouped.setdefault(key, set()).add((student_name, admission_no))

    if not grouped:
        return jsonify({
            "error": "No valid result records were supplied for deletion",
            "deleted": 0,
            "skipped": skipped,
        }), 400

    deleted_count = 0
    sqlite_deleted = 0
    touched_files = 0

    # ========================================================
    # SQLITE DATABASE PATH
    # ========================================================

    sqlite_path = BASE_DIR / "database.db"

    # ========================================================
    # PROCESS EACH RESULT GROUP
    # ========================================================

    for (year, class_cat, term, subject), delete_targets in grouped.items():

        # ====================================================
        # DETERMINE POSSIBLE RESULT FILES
        # ====================================================

        candidate_paths = []

        # ----------------------------------------------------
        # JSS — TERM SUPPLIED
        # ----------------------------------------------------

        if is_jss_class(class_cat) and term:
            excel_path = find_existing_result_path(class_cat, subject, year, term)

            if excel_path and excel_path.exists():
                candidate_paths.append((excel_path, term))

        # ----------------------------------------------------
        # JSS — TERM MISSING
        #
        # Search all three term folders + legacy fallback.
        # ----------------------------------------------------

        elif is_jss_class(class_cat):
            for possible_term in ("FIRST", "SECOND", "THIRD"):
                excel_path = find_existing_result_path(class_cat, subject, year, possible_term)

                if excel_path and excel_path.exists():
                    candidate_paths.append((excel_path, possible_term))

            legacy_path = find_existing_result_path(class_cat, subject, year, "")

            if legacy_path and legacy_path.exists():
                candidate_paths.append((legacy_path, ""))

        # ----------------------------------------------------
        # SS — NO TERM
        # ----------------------------------------------------

        else:
            excel_path = find_existing_result_path(class_cat, subject, year, "")

            if excel_path and excel_path.exists():
                candidate_paths.append((excel_path, ""))

        # ----------------------------------------------------
        # REMOVE DUPLICATE PATHS
        # ----------------------------------------------------

        unique_candidates = []
        seen_paths = set()

        for excel_path, candidate_term in candidate_paths:
            path_key = str(excel_path.resolve())

            if path_key in seen_paths:
                continue

            seen_paths.add(path_key)
            unique_candidates.append((excel_path, candidate_term))

        candidate_paths = unique_candidates

        if not candidate_paths:
            skipped.append({
                "reason": "Result file not found",
                "year": year,
                "class": class_cat,
                "term": term,
                "subject": subject,
            })
            continue

        # ====================================================
        # SEARCH / DELETE FROM EACH MATCHING FILE
        # ====================================================

        for excel_path, actual_term in candidate_paths:
            try:
                results = read_excel_file_direct(excel_path)

            except Exception as error:
                print(f"DELETE READ ERROR [{excel_path}]:", error)

                skipped.append({
                    "reason": "Could not read result file",
                    "file": str(excel_path),
                })

                continue

            updated = []
            removed = []

            # =================================================
            # MATCH RESULT RECORD
            # =================================================

            for record in results:
                record_name = str(record.get("Student Name") or "").strip().upper()
                record_admission = str(record.get("Admission No") or "").strip().upper()

                should_delete = False

                for target_name, target_admission in delete_targets:

                    # Admission number is preferred because it is unique.
                    if target_admission and record_admission == target_admission:
                        should_delete = True
                        break

                    # Fallback to name only if admission number was absent.
                    if not target_admission and target_name and record_name == target_name:
                        should_delete = True
                        break

                if should_delete:
                    removed.append(record)
                else:
                    updated.append(record)

            if not removed:
                continue

            # =================================================
            # REBUILD PHYSICAL EXCEL FILE
            # =================================================

            wb = Workbook()
            ws = wb.active
            ws.title = "Results"

            headers = get_output_headers()
            ws.append(headers)

            for row in updated:
                normalized = normalize_result_record(row, class_cat, subject, year, actual_term)
                ws.append([normalized.get(header, "") for header in headers])

            excel_path.parent.mkdir(parents=True, exist_ok=True)
            wb.save(excel_path)

            deleted_count += len(removed)
            touched_files += 1

            # =================================================
            # DELETE SAME RESULT FROM SQLITE
            # =================================================

            if sqlite_path.exists():
                conn = None

                try:
                    conn = sqlite3.connect(sqlite_path)
                    cursor = conn.cursor()

                    for removed_record in removed:
                        removed_admission = str(removed_record.get("Admission No") or "").strip()
                        removed_name = str(removed_record.get("Student Name") or "").strip()
                        removed_subject = str(removed_record.get("Subject") or subject).strip()

                        db_term = normalize_term(
                            removed_record.get("Term")
                            or actual_term
                            or term
                            or ""
                        )

                        if not is_jss_class(class_cat):
                            db_term = ""

                        # ----------------------------------------
                        # DELETE USING ADMISSION NUMBER
                        # ----------------------------------------

                        if removed_admission:
                            cursor.execute("""
                                DELETE FROM student_results
                                WHERE LOWER(TRIM(COALESCE(admission_number, ''))) = LOWER(TRIM(?))
                                  AND TRIM(COALESCE(year, '')) = TRIM(?)
                                  AND UPPER(TRIM(COALESCE(class_level, ''))) = UPPER(TRIM(?))
                                  AND UPPER(TRIM(COALESCE(subject, ''))) = UPPER(TRIM(?))
                                  AND UPPER(TRIM(COALESCE(term, ''))) = UPPER(TRIM(?))
                            """, (removed_admission, year, class_cat, removed_subject, db_term))

                        # ----------------------------------------
                        # FALLBACK — DELETE USING STUDENT NAME
                        # ----------------------------------------

                        elif removed_name:
                            cursor.execute("""
                                DELETE FROM student_results
                                WHERE LOWER(TRIM(COALESCE(full_name, ''))) = LOWER(TRIM(?))
                                  AND TRIM(COALESCE(year, '')) = TRIM(?)
                                  AND UPPER(TRIM(COALESCE(class_level, ''))) = UPPER(TRIM(?))
                                  AND UPPER(TRIM(COALESCE(subject, ''))) = UPPER(TRIM(?))
                                  AND UPPER(TRIM(COALESCE(term, ''))) = UPPER(TRIM(?))
                            """, (removed_name, year, class_cat, removed_subject, db_term))

                        sqlite_deleted += max(cursor.rowcount, 0)

                    conn.commit()

                except Exception as error:
                    print("SQLITE RESULT DELETE ERROR:", error)

                    if conn:
                        conn.rollback()

                finally:
                    if conn:
                        conn.close()

            # =================================================
            # IF TERM WAS EXPLICIT, STOP AFTER THAT FILE
            # =================================================

            if term:
                break

    # ========================================================
    # NOTHING FOUND
    # ========================================================

    if deleted_count == 0:
        return jsonify({
            "status": "not_found",
            "error": "No matching result record was found to delete.",
            "deleted": 0,
            "sqlite_deleted": sqlite_deleted,
            "files_updated": touched_files,
            "skipped": skipped,
        }), 404

    # ========================================================
    # SUCCESS
    # ========================================================

    return jsonify({
        "status": "ok",
        "message": "Result records permanently deleted.",
        "deleted": deleted_count,
        "sqlite_deleted": sqlite_deleted,
        "files_updated": touched_files,
        "skipped": skipped,
    }), 200

# ============================================================
# 9. GLOBAL SEARCH
#
# Searches:
#   Admission No
#   Student Name
#
# Across:
#   all years
#   all classes
#   all JSS terms
#   all subjects
# ============================================================

@api_bp.route(
    "/api/results/search_admission"
)
def search_admission():
    if not can_view_results():
        return jsonify({
            "error": "Unauthorized"
        }), 403

    q = request.args.get(
        "q",
        "",
    ).strip().lower()

    if len(q) < 2:
        return jsonify({
            "results": []
        })

    if not RESULTS_DIR.exists():
        return jsonify({
            "results": []
        })

    matches = []

    for info in iter_result_files():

        year = info["year"]
        class_cat = info["class"]
        term = info["term"]
        subject = info["subject"]
        excel_path = info["path"]

        try:
            records = read_excel_file_direct(
                excel_path
            )

        except Exception as error:
            print(
                f"Search could not read "
                f"{excel_path}: {error}"
            )

            continue

        for row_dict in records:

            admission = str(
                row_dict.get(
                    "Admission No",
                    "",
                )
            ).strip().lower()

            name = str(
                row_dict.get(
                    "Student Name",
                    "",
                )
            ).strip().lower()

            if (
                q in admission
                or q in name
            ):
                normalize_result_record(
                    row_dict,
                    class_cat,
                    subject,
                    year,
                    term,
                )

                matches.append(
                    row_dict
                )

    matches.sort(
        key=lambda record: str(
            record.get(
                "Submitted At",
                "",
            )
        ),
        reverse=True,
    )

    return jsonify({
        "results": clean_records(
            matches
        )
    })


# ============================================================
# 10. ACADEMIC SETTINGS
#
# Current Session + Current Term
# ============================================================

@api_bp.route(
    "/api/academic-settings",
    methods=["GET"],
)
def api_get_academic_settings():
    if not can_view_results():
        return jsonify({
            "error": "Unauthorized"
        }), 403

    try:
        settings = (
            get_academic_settings()
            or {}
        )

        current_term = normalize_term(
            settings.get(
                "current_term",
                "",
            )
        )

        # Keep normalized information available to frontend.
        settings["current_term"] = (
            current_term
            or settings.get(
                "current_term",
                "",
            )
        )

        settings["current_term_label"] = (
            term_label(
                current_term
            )
            if current_term
            else ""
        )

        return jsonify({
            "success": True,
            "settings": settings,
        })

    except Exception as error:
        print(
            "ACADEMIC SETTINGS FETCH ERROR:",
            error,
        )

        return jsonify({
            "success": False,
            "error": str(error),
        }), 500


# ============================================================
# UPDATE ACADEMIC SETTINGS
# ============================================================

@api_bp.route(
    "/api/academic-settings",
    methods=["POST"],
)
def api_update_academic_settings():
    if not can_view_results():
        return jsonify({
            "error": "Unauthorized"
        }), 403

    try:
        data = (
            request.get_json(
                silent=True
            )
            or {}
        )

        session_value = str(
            data.get(
                "current_session",
                "",
            )
        ).strip()

        raw_term = str(
            data.get(
                "current_term",
                "",
            )
        ).strip()

        term_value = normalize_term(
            raw_term
        )

        if not session_value:
            return jsonify({
                "success": False,
                "error": (
                    "Academic session is required"
                ),
            }), 400

        if not term_value:
            return jsonify({
                "success": False,
                "error": (
                    "A valid academic term is required. "
                    "Use FIRST, SECOND or THIRD."
                ),
            }), 400

        # ----------------------------------------------------
        # Save canonical term.
        #
        # FIRST
        # SECOND
        # THIRD
        # ----------------------------------------------------

        update_academic_settings(
            session_value,
            term_value,
        )

        # Keep current Flask session synchronized where useful.
        session["selected_term"] = term_value

        return jsonify({
            "success": True,
            "message": (
                "Academic settings updated successfully"
            ),
            "settings": {
                "current_session": session_value,
                "current_term": term_value,
                "current_term_label": term_label(
                    term_value
                ),
            },
        })

    except Exception as error:
        print(
            "ACADEMIC SETTINGS UPDATE ERROR:",
            error,
        )

        return jsonify({
            "success": False,
            "error": str(error),
        }), 500



# ============================================================
# PROFESSIONAL RESULTS EXCEL EXPORT
# Creates a real Microsoft Excel .xlsx workbook
# ============================================================

@api_bp.route("/api/results/export/excel", methods=["POST"])
def export_results_excel():
    if not can_view_results():
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json(silent=True) or {}
    records = data.get("results", [])

    if not isinstance(records, list) or not records:
        return jsonify({"error": "No results supplied for export"}), 400

    filters = data.get("filters", {}) if isinstance(data.get("filters"), dict) else {}
    generated_at = datetime.now().strftime("%d %B %Y, %I:%M %p")

    def value(row, *keys, default=""):
        for key in keys:
            if key in row and row.get(key) not in (None, ""):
                return row.get(key)
        return default

    def normalize_term_label(raw):
        text = str(raw or "").strip().upper().replace("_", " ").replace("-", " ")

        if text in {"FIRST", "FIRST TERM", "1", "1ST", "1ST TERM"}:
            return "1st Term"

        if text in {"SECOND", "SECOND TERM", "2", "2ND", "2ND TERM"}:
            return "2nd Term"

        if text in {"THIRD", "THIRD TERM", "3", "3RD", "3RD TERM"}:
            return "3rd Term"

        return str(raw or "").strip()

    def numeric_score(row):
        raw = value(row, "Score (%)", "Score Number", "score", "score_percentage", "percentage", default=0)

        try:
            return float(str(raw).replace("%", "").strip())
        except (TypeError, ValueError):
            return 0.0

    def result_status(row):
        explicit = str(value(row, "Status", "status", default="")).strip().upper()

        if explicit in {"PASS", "FAIL"}:
            return explicit

        return "PASS" if numeric_score(row) >= 50 else "FAIL"

    wb = Workbook()
    ws = wb.active
    ws.title = "Examination Results"
    ws.sheet_view.showGridLines = False

    # ========================================================
    # COLOURS / STYLES
    # ========================================================

    dark = "17324D"
    teal = "0F766E"
    teal_light = "E7F5F3"
    header_fill = "334155"
    border_colour = "D5DEE8"
    soft_fill = "F8FAFC"
    green = "15803D"
    green_fill = "DCFCE7"
    red = "B91C1C"
    red_fill = "FEE2E2"
    gold = "B7791F"
    gold_fill = "FEF3C7"
    white = "FFFFFF"
    text = "17202A"
    muted = "64748B"

    thin = Side(style="thin", color=border_colour)
    cell_border = Border(left=thin, right=thin, top=thin, bottom=thin)

    # ========================================================
    # DOCUMENT TITLE
    # ========================================================

    headers = ["S/N", "Student Name", "Admission No", "Year", "Class Level", "Class Arm", "Term", "Subject", "Score (%)", "Correct", "Total", "Status", "Time Taken", "Submitted At", "Session"]
    total_columns = len(headers)

    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=total_columns)
    title_cell = ws.cell(row=1, column=1, value="EMIS CBT — EXAMINATION RESULTS")
    title_cell.font = Font(name="Calibri", size=18, bold=True, color=white)
    title_cell.fill = PatternFill("solid", fgColor=dark)
    title_cell.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 32

    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=total_columns)
    subtitle_cell = ws.cell(row=2, column=1, value="Official Examination Results Report")
    subtitle_cell.font = Font(name="Calibri", size=12, bold=True, color=teal)
    subtitle_cell.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[2].height = 23

    # ========================================================
    # FILTER / REPORT INFORMATION
    # ========================================================

    year_filter = str(filters.get("year") or "All Years")
    class_filter = str(filters.get("class") or "All Classes")
    term_filter = normalize_term_label(filters.get("term")) or "All Terms"
    subject_filter = str(filters.get("subject") or "All Subjects")
    session_filter = str(filters.get("session") or "All Sessions")

    report_info = [
        ("Academic Year", year_filter),
        ("Class", class_filter),
        ("Term", term_filter),
        ("Subject", subject_filter),
        ("Session", session_filter),
        ("Generated", generated_at),
    ]

    info_row = 4

    for index, (label, content) in enumerate(report_info):
        start_column = 1 + ((index % 3) * 5)
        row = info_row + (index // 3)

        ws.cell(row=row, column=start_column, value=label).font = Font(name="Calibri", size=10, bold=True, color=muted)
        ws.cell(row=row, column=start_column + 1, value=content).font = Font(name="Calibri", size=11, bold=True, color=text)

        ws.merge_cells(start_row=row, start_column=start_column + 1, end_row=row, end_column=start_column + 3)

    # ========================================================
    # SUMMARY
    # ========================================================

    scores = [numeric_score(row) for row in records]
    pass_count = sum(1 for row in records if result_status(row) == "PASS")
    fail_count = len(records) - pass_count
    average_score = sum(scores) / len(scores) if scores else 0
    highest_score = max(scores) if scores else 0

    summary_row = 7

    summary_items = [
        ("TOTAL RESULTS", len(records), teal, teal_light),
        ("PASS", pass_count, green, green_fill),
        ("FAIL", fail_count, red, red_fill),
        ("AVERAGE SCORE", f"{average_score:.1f}%", gold, gold_fill),
        ("HIGHEST SCORE", f"{highest_score:.1f}%", teal, teal_light),
    ]

    summary_width = 3

    for index, (label, summary_value, font_colour, fill_colour) in enumerate(summary_items):
        start_column = 1 + (index * summary_width)
        end_column = min(start_column + summary_width - 1, total_columns)

        ws.merge_cells(start_row=summary_row, start_column=start_column, end_row=summary_row, end_column=end_column)
        ws.merge_cells(start_row=summary_row + 1, start_column=start_column, end_row=summary_row + 1, end_column=end_column)

        label_cell = ws.cell(row=summary_row, column=start_column, value=label)
        value_cell = ws.cell(row=summary_row + 1, column=start_column, value=summary_value)

        label_cell.font = Font(name="Calibri", size=9, bold=True, color=muted)
        value_cell.font = Font(name="Calibri", size=15, bold=True, color=font_colour)

        label_cell.fill = PatternFill("solid", fgColor=fill_colour)
        value_cell.fill = PatternFill("solid", fgColor=fill_colour)

        label_cell.alignment = Alignment(horizontal="center", vertical="center")
        value_cell.alignment = Alignment(horizontal="center", vertical="center")

        for row_number in (summary_row, summary_row + 1):
            for column_number in range(start_column, end_column + 1):
                ws.cell(row=row_number, column=column_number).border = cell_border

    ws.row_dimensions[summary_row].height = 19
    ws.row_dimensions[summary_row + 1].height = 28

    # ========================================================
    # TABLE HEADER
    # ========================================================

    header_row = 11

    for column_index, heading in enumerate(headers, start=1):
        cell = ws.cell(row=header_row, column=column_index, value=heading)
        cell.font = Font(name="Calibri", size=11, bold=True, color=white)
        cell.fill = PatternFill("solid", fgColor=header_fill)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = cell_border

    ws.row_dimensions[header_row].height = 28

    # ========================================================
    # RESULT ROWS
    # ========================================================

    first_data_row = header_row + 1

    for serial, row in enumerate(records, start=1):
        excel_row = header_row + serial

        student_name = str(value(row, "Student Name", "full_name", "student_name", default="Unknown Student")).strip()
        admission = str(value(row, "Admission No", "admission_number", "student_id", default="")).strip()
        year = str(value(row, "Year", "year", default="")).strip()
        class_level = str(value(row, "Class Level", "Class Category", "class_level", "class_category", default="")).strip()
        class_arm = str(value(row, "Class Arm", "class_arm", "Class", "class", default=class_level)).strip()
        term = normalize_term_label(value(row, "Term", "term", "Term Label", default=""))
        subject = str(value(row, "Subject", "subject", "Subject Folder", "subject_folder", default="")).replace("_", " ").upper().strip()
        score = numeric_score(row)
        correct = value(row, "Correct", "correct", default=0)
        total = value(row, "Total", "total", default=0)
        status = result_status(row)
        time_taken = value(row, "Time Taken", "time_taken", "timeTaken", default="")
        submitted_at = value(row, "Submitted At", "submitted_at", "submittedAt", default="")
        session_value = value(row, "Session", "session", "Academic Session", "academic_session", default="")

        values = [serial, student_name, admission, year, class_level, class_arm, term, subject, score / 100, correct, total, status, time_taken, submitted_at, session_value]

        row_fill = PatternFill("solid", fgColor=soft_fill if serial % 2 == 0 else white)

        for column_index, content in enumerate(values, start=1):
            cell = ws.cell(row=excel_row, column=column_index, value=content)
            cell.font = Font(name="Calibri", size=11, color=text)
            cell.fill = row_fill
            cell.border = cell_border
            cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=False)

        # Student name: larger + bold
        name_cell = ws.cell(row=excel_row, column=2)
        name_cell.font = Font(name="Calibri", size=12, bold=True, color=dark)

        # Admission / class information
        for column_index in [1, 3, 4, 5, 6, 7, 10, 11, 12]:
            ws.cell(row=excel_row, column=column_index).alignment = Alignment(horizontal="center", vertical="center")

        # Subject
        ws.cell(row=excel_row, column=8).font = Font(name="Calibri", size=11, bold=True, color=text)

        # SCORE — highly visible
        score_cell = ws.cell(row=excel_row, column=9)
        score_cell.number_format = "0.0%"
        score_cell.font = Font(name="Calibri", size=13, bold=True, color=green if score >= 50 else red)
        score_cell.alignment = Alignment(horizontal="center", vertical="center")
        score_cell.fill = PatternFill("solid", fgColor=green_fill if score >= 50 else red_fill)

        # STATUS
        status_cell = ws.cell(row=excel_row, column=12)
        status_cell.font = Font(name="Calibri", size=11, bold=True, color=green if status == "PASS" else red)
        status_cell.fill = PatternFill("solid", fgColor=green_fill if status == "PASS" else red_fill)

        ws.row_dimensions[excel_row].height = 25

    last_data_row = header_row + len(records)

    # ========================================================
    # EXCEL TABLE
    # ========================================================

    table_reference = f"A{header_row}:O{last_data_row}"

    result_table = Table(displayName="EMISResultsTable", ref=table_reference)
    result_table.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showFirstColumn=False, showLastColumn=False, showRowStripes=False, showColumnStripes=False)

    ws.add_table(result_table)

    # ========================================================
    # COLUMN WIDTHS
    # ========================================================

    widths = {
        "A": 7,
        "B": 28,
        "C": 16,
        "D": 10,
        "E": 13,
        "F": 15,
        "G": 13,
        "H": 24,
        "I": 13,
        "J": 10,
        "K": 10,
        "L": 12,
        "M": 14,
        "N": 22,
        "O": 16,
    }

    for column, width in widths.items():
        ws.column_dimensions[column].width = width

    # ========================================================
    # FREEZE / FILTER / VIEW
    # ========================================================

    ws.freeze_panes = f"A{first_data_row}"
    ws.auto_filter.ref = table_reference

    ws.sheet_view.zoomScale = 90
    ws.sheet_view.zoomScaleNormal = 90

    # ========================================================
    # PROFESSIONAL A4 PRINT SETTINGS
    # ========================================================

    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.orientation = ws.ORIENTATION_LANDSCAPE
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True

    ws.page_margins = PageMargins(left=0.25, right=0.25, top=0.45, bottom=0.45, header=0.2, footer=0.2)

    ws.print_title_rows = f"{header_row}:{header_row}"
    ws.print_area = f"A1:O{last_data_row}"

    ws.oddHeader.center.text = "&BEMIS CBT — EXAMINATION RESULTS"
    ws.oddHeader.center.size = 10

    ws.oddFooter.left.text = "EMIS CBT"
    ws.oddFooter.center.text = "Page &P of &N"
    ws.oddFooter.right.text = "Generated &D"

    ws.sheet_properties.outlinePr.summaryBelow = True

    # ========================================================
    # SAVE WORKBOOK
    # ========================================================

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    year_name = str(filters.get("year") or "all_years").replace("/", "-").replace(" ", "_")
    class_name = str(filters.get("class") or "all_classes").replace("/", "-").replace(" ", "_")
    term_name = str(filters.get("term") or "all_terms").replace("/", "-").replace(" ", "_")

    filename = f"EMIS_Results_{year_name}_{class_name}_{term_name}_{datetime.now().strftime('%Y-%m-%d')}.xlsx"

    return send_file(output, as_attachment=True, download_name=filename, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")