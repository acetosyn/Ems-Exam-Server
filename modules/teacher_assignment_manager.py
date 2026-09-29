# MODULE: Teacher Assignment Manager — session-aware Teacher -> Class/Arm -> Subject assignment engine
# STORAGE: database.db (teacher_assignments + teacher_assignment_audit)

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock

from modules.academic_records import is_valid_academic_session, normalize_academic_session
from modules.academic_settings import get_academic_settings
from modules.class_config import CLASS_ARMS_BY_LEVEL, get_ss_track, normalize_class_arm, normalize_configured_class_level
from modules.school_structure import ALL_CONFIGURED_CLASSES, SCHOOL_SECTIONS, SCHOOL_SECTION_ORDER, get_class_metadata, school_section_for_class
from modules.subject_registry import get_class_subject_rows, get_subject


BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "database.db"
ASSIGNMENT_LOCK = RLock()
VALID_TEACHER_STATUSES = {"active", "inactive"}


def clean(value): return " ".join(str(value or "").strip().split())
def utc_now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _connect():
    conn = sqlite3.connect(DB_PATH, timeout=30); conn.row_factory = sqlite3.Row
    return conn


def init_teacher_assignment_tables():
    """Create Phase 3 assignment/audit storage without altering existing teacher credentials."""
    with ASSIGNMENT_LOCK:
        conn = _connect()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS teacher_assignments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    teacher_id TEXT NOT NULL,
                    academic_session TEXT NOT NULL,
                    school_section TEXT NOT NULL,
                    class_level TEXT NOT NULL,
                    class_arm TEXT NOT NULL DEFAULT '',
                    subject_key TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(teacher_id, academic_session, class_level, class_arm, subject_key)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS teacher_assignment_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    teacher_id TEXT NOT NULL,
                    academic_session TEXT NOT NULL,
                    action TEXT NOT NULL,
                    changed_by TEXT NOT NULL DEFAULT '',
                    assignment_count INTEGER NOT NULL DEFAULT 0,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_teacher_assignments_teacher_session ON teacher_assignments(teacher_id, academic_session, active)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_teacher_assignments_class ON teacher_assignments(academic_session, class_level, class_arm, active)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_teacher_assignments_subject ON teacher_assignments(academic_session, subject_key, active)")
            conn.commit()
        finally:
            conn.close()


def _default_session():
    try: settings = get_academic_settings() or {}
    except Exception: settings = {}
    value = normalize_academic_session(settings.get("current_session") or settings.get("academic_session") or settings.get("session"))
    return value if is_valid_academic_session(value) else ""


def normalize_assignment_session(value=""):
    session_value = normalize_academic_session(value or _default_session())
    if not is_valid_academic_session(session_value): raise ValueError("A valid academic session such as 2026/2027 is required.")
    return session_value


def _teacher_row(conn, teacher_id):
    token = clean(teacher_id).upper()
    if not token: return None
    return conn.execute("SELECT id, teacher_id, full_name, status, created_at FROM teachers WHERE UPPER(teacher_id)=? LIMIT 1", (token,)).fetchone()


def get_teacher(teacher_id):
    init_teacher_assignment_tables(); conn = _connect()
    try:
        row = _teacher_row(conn, teacher_id)
        return dict(row) if row else None
    finally: conn.close()


def update_teacher_profile(teacher_id, full_name=None, status=None):
    """Update non-secret Teacher profile metadata. Passwords remain owned by ID Management."""
    init_teacher_assignment_tables(); token = clean(teacher_id).upper(); name = clean(full_name) if full_name is not None else None
    normalized_status = clean(status).lower() if status is not None else None
    if normalized_status is not None and normalized_status not in VALID_TEACHER_STATUSES: raise ValueError("Teacher status must be active or inactive.")

    with ASSIGNMENT_LOCK:
        conn = _connect()
        try:
            current = _teacher_row(conn, token)
            if not current: raise ValueError("Teacher account not found.")
            if name is not None: conn.execute("UPDATE teachers SET full_name=? WHERE teacher_id=?", (name, current["teacher_id"]))
            if normalized_status is not None: conn.execute("UPDATE teachers SET status=? WHERE teacher_id=?", (normalized_status, current["teacher_id"]))
            conn.commit(); row = _teacher_row(conn, current["teacher_id"])
            return dict(row)
        finally: conn.close()


def _normalize_arm(class_level, class_arm=""):
    level = normalize_configured_class_level(class_level)
    raw = clean(class_arm)
    if not level: raise ValueError(f"Invalid configured class: {class_level}")
    configured_arms = list(CLASS_ARMS_BY_LEVEL.get(level, []))
    if not raw: return ""
    if not configured_arms: raise ValueError(f"{get_class_metadata(level).get('label', level)} does not currently use class arms in EMIS.")
    arm = normalize_class_arm(raw, level)
    if arm not in configured_arms: raise ValueError(f"{raw} is not a configured class arm for {level}.")
    return arm


def _subject_row_for_class(class_level, subject_value):
    wanted = clean(subject_value).upper()
    for row in get_class_subject_rows(class_level, active_only=True):
        if wanted in {clean(row.get("id")).upper(), clean(row.get("key")).upper(), clean(row.get("name")).upper(), clean(row.get("catalog_name")).upper()}: return row
    return None


def _normalize_assignment(item):
    if not isinstance(item, dict): raise ValueError("Each teacher assignment must be an object.")
    level = normalize_configured_class_level(item.get("class_level") or item.get("class"))
    if level not in ALL_CONFIGURED_CLASSES: raise ValueError(f"Invalid configured class: {item.get('class_level') or item.get('class')}")
    arm = _normalize_arm(level, item.get("class_arm") or item.get("arm")); subject = _subject_row_for_class(level, item.get("subject_id") or item.get("subject_key") or item.get("subject"))
    if not subject: raise ValueError(f"The selected subject is not active for {get_class_metadata(level).get('label', level)}.")

    if level.startswith("SS") and arm:
        track = get_ss_track(arm); allowed_tracks = [clean(value).upper() for value in subject.get("tracks") or []]; compatible = track in allowed_tracks or (track == "ART_COMMERCIAL" and bool({"ART", "COMMERCIAL"} & set(allowed_tracks)))
        if track and allowed_tracks and not compatible: raise ValueError(f"{subject.get('name')} is not assigned to the {track.replace('_', '/').title()} track for {arm}.")

    return {"school_section": school_section_for_class(level), "class_level": level, "class_arm": arm, "subject_key": clean(subject.get("key")).upper()}


def _assignment_identity(row): return "|".join([clean(row.get("class_level")).upper(), clean(row.get("class_arm")).upper(), clean(row.get("subject_key")).upper()])


def _subject_display(subject_key, class_level=""):
    row = _subject_row_for_class(class_level, subject_key) if class_level else None
    if row: return clean(row.get("name") or row.get("catalog_name") or row.get("key"))
    subject = get_subject(subject_key) or {}
    return clean(subject.get("name") or subject.get("key") or subject_key)


def _enrich_assignment(row):
    value = dict(row); level = clean(value.get("class_level")).upper(); arm = clean(value.get("class_arm")); subject_key = clean(value.get("subject_key")).upper(); meta = get_class_metadata(level)
    value.update({
        "active": bool(value.get("active", 1)), "class_label": meta.get("label", level), "class_arm_label": arm or "All applicable arms",
        "section_label": SCHOOL_SECTIONS.get(value.get("school_section"), {}).get("label", value.get("school_section", "")), "subject_name": _subject_display(subject_key, level),
        "assignment_key": _assignment_identity(value),
    })
    return value


def get_teacher_assignments(teacher_id, academic_session="", active_only=True):
    init_teacher_assignment_tables(); session_value = normalize_assignment_session(academic_session); token = clean(teacher_id).upper(); conn = _connect()
    try:
        where = "teacher_id=? AND academic_session=?" + (" AND active=1" if active_only else "")
        rows = conn.execute(f"SELECT * FROM teacher_assignments WHERE {where} ORDER BY school_section, class_level, class_arm, subject_key", (token, session_value)).fetchall()
        return [_enrich_assignment(row) for row in rows]
    finally: conn.close()


def _audit(conn, teacher_id, session_value, action, assignments, changed_by=""):
    payload = [{"school_section": row.get("school_section"), "class_level": row.get("class_level"), "class_arm": row.get("class_arm"), "subject_key": row.get("subject_key")} for row in assignments]
    conn.execute("INSERT INTO teacher_assignment_audit(teacher_id, academic_session, action, changed_by, assignment_count, payload_json, created_at) VALUES(?,?,?,?,?,?,?)", (teacher_id, session_value, clean(action), clean(changed_by), len(payload), json.dumps(payload, ensure_ascii=False, separators=(",", ":")), utc_now()))


def replace_teacher_assignments(teacher_id, assignments, academic_session="", changed_by="", require_teacher=True, audit=True):
    """Atomically replace one teacher's complete assignment set for one academic session."""
    init_teacher_assignment_tables(); token = clean(teacher_id).upper(); session_value = normalize_assignment_session(academic_session); assignments = assignments if isinstance(assignments, list) else []
    normalized = []; seen = set()
    for item in assignments:
        row = _normalize_assignment(item); identity = _assignment_identity(row)
        if identity in seen: continue
        seen.add(identity); normalized.append(row)

    with ASSIGNMENT_LOCK:
        conn = _connect()
        try:
            conn.execute("BEGIN IMMEDIATE"); teacher = _teacher_row(conn, token)
            if require_teacher and not teacher: raise ValueError("Teacher account not found.")
            canonical_teacher_id = teacher["teacher_id"] if teacher else token
            now = utc_now(); conn.execute("UPDATE teacher_assignments SET active=0, updated_at=? WHERE teacher_id=? AND academic_session=?", (now, canonical_teacher_id, session_value))
            for row in normalized:
                conn.execute("""
                    INSERT INTO teacher_assignments(teacher_id, academic_session, school_section, class_level, class_arm, subject_key, active, created_at, updated_at)
                    VALUES(?,?,?,?,?,?,1,?,?)
                    ON CONFLICT(teacher_id, academic_session, class_level, class_arm, subject_key) DO UPDATE SET school_section=excluded.school_section, active=1, updated_at=excluded.updated_at
                """, (canonical_teacher_id, session_value, row["school_section"], row["class_level"], row["class_arm"], row["subject_key"], now, now))
            if audit: _audit(conn, canonical_teacher_id, session_value, "replace", normalized, changed_by)
            conn.commit()
        except Exception:
            conn.rollback(); raise
        finally: conn.close()

    return get_teacher_assignments(canonical_teacher_id, session_value)


def delete_teacher_assignments(teacher_id):
    init_teacher_assignment_tables(); token = clean(teacher_id).upper(); conn = _connect()
    try:
        cursor = conn.execute("DELETE FROM teacher_assignments WHERE UPPER(teacher_id)=?", (token,)); conn.commit(); return int(cursor.rowcount or 0)
    finally: conn.close()


def get_teacher_assignment_stats(academic_session=""):
    init_teacher_assignment_tables(); session_value = normalize_assignment_session(academic_session); conn = _connect()
    try:
        teacher_total = int(conn.execute("SELECT COUNT(*) FROM teachers").fetchone()[0] or 0); active_teachers = int(conn.execute("SELECT COUNT(*) FROM teachers WHERE LOWER(COALESCE(status,'active'))='active'").fetchone()[0] or 0)
        assignment_count = int(conn.execute("SELECT COUNT(*) FROM teacher_assignments WHERE academic_session=? AND active=1", (session_value,)).fetchone()[0] or 0)
        teachers_assigned = int(conn.execute("SELECT COUNT(DISTINCT teacher_id) FROM teacher_assignments WHERE academic_session=? AND active=1", (session_value,)).fetchone()[0] or 0)
        return {"academic_session": session_value, "teacher_count": teacher_total, "active_teacher_count": active_teachers, "teachers_assigned": teachers_assigned, "teachers_unassigned": max(0, teacher_total - teachers_assigned), "assignment_count": assignment_count}
    finally: conn.close()


def list_teachers_with_assignment_summary(academic_session=""):
    init_teacher_assignment_tables(); session_value = normalize_assignment_session(academic_session); conn = _connect()
    try:
        rows = conn.execute("""
            SELECT t.id, t.teacher_id, t.full_name, t.status, t.created_at,
                   COUNT(a.id) AS assignment_count,
                   COUNT(DISTINCT CASE WHEN a.active=1 THEN a.class_level || '|' || a.class_arm END) AS class_count,
                   COUNT(DISTINCT CASE WHEN a.active=1 THEN a.subject_key END) AS subject_count
            FROM teachers t LEFT JOIN teacher_assignments a ON a.teacher_id=t.teacher_id AND a.academic_session=? AND a.active=1
            GROUP BY t.id, t.teacher_id, t.full_name, t.status, t.created_at ORDER BY COALESCE(NULLIF(TRIM(t.full_name),''), t.teacher_id) COLLATE NOCASE
        """, (session_value,)).fetchall()
        return [{**dict(row), "assignment_count": int(row["assignment_count"] or 0), "class_count": int(row["class_count"] or 0), "subject_count": int(row["subject_count"] or 0)} for row in rows]
    finally: conn.close()


def get_teacher_assignment_config(academic_session="", include_teachers=True):
    session_value = normalize_assignment_session(academic_session); sections = []
    for section_key in SCHOOL_SECTION_ORDER:
        section = SCHOOL_SECTIONS.get(section_key, {}); classes = []
        for level in section.get("classes", []):
            meta = get_class_metadata(level); arms = list(CLASS_ARMS_BY_LEVEL.get(level, [])); subjects = []
            for row in get_class_subject_rows(level, active_only=True): subjects.append({"id": row.get("id"), "key": row.get("key"), "name": row.get("name") or row.get("catalog_name"), "tracks": list(row.get("tracks") or [])})
            classes.append({"key": level, "label": meta.get("label", level), "database_active": bool(meta.get("database_active")), "arms": arms, "subjects": subjects})
        sections.append({"key": section_key, "label": section.get("label", section_key.title()), "classes": classes})
    payload = {"academic_session": session_value, "sections": sections, "stats": get_teacher_assignment_stats(session_value)}
    if include_teachers: payload["teachers"] = list_teachers_with_assignment_summary(session_value)
    return payload


def build_teacher_assignment_sync_payload(teacher_id, academic_session=""):
    session_value = normalize_assignment_session(academic_session); teacher = get_teacher(teacher_id) or {}; assignments = get_teacher_assignments(teacher_id, session_value)
    return {
        "teacher_id": clean(teacher_id).upper(), "teacher_name": clean(teacher.get("full_name")), "teacher_status": clean(teacher.get("status")) or "active", "academic_session": session_value,
        "assignments": [{"school_section": row.get("school_section"), "class_level": row.get("class_level"), "class_arm": row.get("class_arm"), "subject_key": row.get("subject_key")} for row in assignments], "updated_at": utc_now(),
    }


def apply_teacher_assignment_sync_event(action, payload, event=None):
    """Apply trusted assignment snapshots without creating a reverse sync loop or credential records."""
    if clean(action).lower() != "replace_teacher_session": raise ValueError(f"Unsupported teacher assignment sync action: {action}")
    if not isinstance(payload, dict): raise ValueError("Teacher assignment sync payload must be an object.")
    teacher_id = clean(payload.get("teacher_id")).upper(); session_value = normalize_assignment_session(payload.get("academic_session")); assignments = payload.get("assignments") or []
    if not teacher_id: raise ValueError("Synchronized teacher_id is required.")
    saved = replace_teacher_assignments(teacher_id, assignments, session_value, changed_by=f"sync:{clean((event or {}).get('server_id'))}", require_teacher=False, audit=True)
    return {"teacher_id": teacher_id, "academic_session": session_value, "assignment_count": len(saved), "updated_at": clean(payload.get("updated_at")) or utc_now()}
