# MODULE: Academic Settings — Persistent global EMIS academic period
# PURPOSE: One authoritative default year/session/term shared by staff modules.
# STORAGE: static/data/academic/academic_settings.json
# NOTE: Explicit page/class selections may still override these defaults when required.

import json
import os
import re
from pathlib import Path
from threading import RLock
from datetime import datetime, timezone

BASE_DIR = Path(__file__).resolve().parent.parent
SETTINGS_DIR = BASE_DIR / "static" / "data" / "academic"
SETTINGS_FILE = SETTINGS_DIR / "academic_settings.json"
SETTINGS_LOCK = RLock()

YEAR_MIN = 2025
YEAR_MAX = 2040
VALID_TERMS = ("FIRST", "SECOND", "THIRD")


def clean(value):
    return str(value or "").strip()


def normalize_year(value):
    raw = clean(value)
    if not raw:
        return ""
    match = re.search(r"\b(\d{4})\b", raw)
    if not match:
        return ""
    year = int(match.group(1))
    return str(year) if YEAR_MIN <= year <= YEAR_MAX else ""


def academic_session_from_year(year):
    normalized = normalize_year(year)
    if not normalized:
        return ""
    start = int(normalized)
    return f"{start:04d}/{start + 1:04d}"


def year_from_academic_session(value):
    raw = clean(value)
    match = re.fullmatch(r"(\d{4})\s*[/\-]\s*(\d{4})", raw)
    if not match:
        return ""
    start, end = int(match.group(1)), int(match.group(2))
    if end != start + 1:
        return ""
    return normalize_year(start)


def normalize_term(value):
    raw = " ".join(clean(value).upper().replace("_", " ").replace("-", " ").split())
    aliases = {
        "FIRST": "FIRST", "FIRST TERM": "FIRST", "TERM 1": "FIRST", "TERM ONE": "FIRST", "1": "FIRST", "1ST": "FIRST", "1ST TERM": "FIRST",
        "SECOND": "SECOND", "SECOND TERM": "SECOND", "TERM 2": "SECOND", "TERM TWO": "SECOND", "2": "SECOND", "2ND": "SECOND", "2ND TERM": "SECOND",
        "THIRD": "THIRD", "THIRD TERM": "THIRD", "TERM 3": "THIRD", "TERM THREE": "THIRD", "3": "THIRD", "3RD": "THIRD", "3RD TERM": "THIRD",
    }
    return aliases.get(raw, "")


def term_label(value):
    return {"FIRST": "FIRST TERM", "SECOND": "SECOND TERM", "THIRD": "THIRD TERM"}.get(normalize_term(value), "")


def short_term_label(value):
    return {"FIRST": "1st Term", "SECOND": "2nd Term", "THIRD": "3rd Term"}.get(normalize_term(value), "")


def _utc_now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _default_year():
    current = datetime.now().year
    if current < YEAR_MIN:
        current = YEAR_MIN
    elif current > YEAR_MAX:
        current = YEAR_MAX
    return str(current)


def _normalize_settings(data=None):
    data = data if isinstance(data, dict) else {}
    year = normalize_year(data.get("current_year") or data.get("year"))
    if not year:
        year = year_from_academic_session(data.get("current_session") or data.get("academic_session"))
    if not year:
        year = _default_year()

    term = normalize_term(data.get("current_term") or data.get("term"))
    session_value = academic_session_from_year(year)

    return {
        "current_year": year,
        "year": year,
        "current_session": session_value,
        "academic_session": session_value,
        "session": session_value,
        "current_term": term,
        "term": term,
        "current_term_label": term_label(term),
        "term_label": term_label(term),
        "short_term_label": short_term_label(term),
        "updated_at": clean(data.get("updated_at")),
        "updated_by": clean(data.get("updated_by")),
        "source": clean(data.get("source")) or "local",
        "configured": bool(year and term),
        "year_min": YEAR_MIN,
        "year_max": YEAR_MAX,
    }


def _read_json_file():
    if not SETTINGS_FILE.exists():
        return {}
    try:
        value = json.loads(SETTINGS_FILE.read_text(encoding="utf-8-sig"))
        return value if isinstance(value, dict) else {}
    except Exception as error:
        print("[EMIS ACADEMIC SETTINGS] Read warning:", error)
        return {}


def get_academic_settings():
    """Return the persistent global academic default without mutating storage."""
    with SETTINGS_LOCK:
        return _normalize_settings(_read_json_file())


def save_academic_settings(current_year="", current_session="", current_term="", updated_by="", source="local", updated_at=""):
    """Validate and persist the global academic period atomically."""
    year = normalize_year(current_year) or year_from_academic_session(current_session)
    term = normalize_term(current_term)

    if not year:
        raise ValueError(f"Academic year must be between {YEAR_MIN} and {YEAR_MAX}.")
    if not term:
        raise ValueError("Academic term must be FIRST, SECOND or THIRD.")

    payload = _normalize_settings({
        "current_year": year,
        "current_term": term,
        "updated_at": clean(updated_at) or _utc_now_iso(),
        "updated_by": clean(updated_by) or "EMIS Admin",
        "source": clean(source) or "local",
    })

    with SETTINGS_LOCK:
        SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        temp_path = SETTINGS_FILE.with_suffix(".tmp")
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp_path, SETTINGS_FILE)

    return dict(payload)


def apply_academic_settings_sync_event(action, payload, event=None):
    """Apply one trusted Local -> Cloud academic-settings synchronization event."""
    if clean(action).lower() != "set":
        raise ValueError(f"Unsupported academic settings sync action: {action}")
    if not isinstance(payload, dict):
        raise ValueError("Academic settings sync payload must be an object.")

    remote_server = clean((event or {}).get("server_id"))
    saved = save_academic_settings(
        current_year=payload.get("current_year") or payload.get("year"),
        current_session=payload.get("current_session") or payload.get("academic_session") or payload.get("session"),
        current_term=payload.get("current_term") or payload.get("term"),
        updated_by=payload.get("updated_by") or (f"Sync from {remote_server}" if remote_server else "EMIS Sync"),
        source=f"sync:{remote_server}" if remote_server else "sync",
        updated_at=payload.get("updated_at"),
    )

    return {
        "current_year": saved["current_year"],
        "current_session": saved["current_session"],
        "current_term": saved["current_term"],
        "updated_at": saved["updated_at"],
    }
