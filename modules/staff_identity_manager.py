# MODULE: Staff Identity Manager — Admin-owned EMT / ADM / IMS credential lifecycle and role-aware authentication
# STORAGE: database.db (teachers + staff_identity_audit)

import secrets
import sqlite3
import string
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "database.db"
STAFF_LOCK = RLock()
_STAFF_SCHEMA_READY = False
ROLE_CONFIG = {
    "teacher": {"prefix": "EMT", "label": "Teacher"},
    "teacher_admin": {"prefix": "ADM", "label": "Teacher Admin"},
    "islamiyyah_teacher": {"prefix": "IMS", "label": "Islamiyyah Teacher"},
}
VALID_STATUSES = {"active", "inactive"}


def clean(value): return " ".join(str(value or "").strip().split())
def utc_now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def _connect():
    conn = sqlite3.connect(DB_PATH, timeout=30); conn.row_factory = sqlite3.Row
    return conn


def _columns(conn, table="teachers"):
    try: return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    except sqlite3.Error: return set()


def init_staff_identity_tables():
    """Upgrade the legacy teachers table once per process without breaking existing EMT credentials."""
    global _STAFF_SCHEMA_READY
    if _STAFF_SCHEMA_READY: return
    with STAFF_LOCK:
        if _STAFF_SCHEMA_READY: return
        conn = _connect()
        try:
            conn.execute("""CREATE TABLE IF NOT EXISTS teachers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                teacher_id TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                full_name TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'active',
                staff_role TEXT NOT NULL DEFAULT 'teacher',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT '',
                created_by TEXT NOT NULL DEFAULT ''
            )""")
            cols = _columns(conn)
            upgrades = {
                "full_name": "TEXT NOT NULL DEFAULT ''",
                "status": "TEXT NOT NULL DEFAULT 'active'",
                "staff_role": "TEXT NOT NULL DEFAULT 'teacher'",
                "created_at": "TEXT NOT NULL DEFAULT ''",
                "updated_at": "TEXT NOT NULL DEFAULT ''",
                "created_by": "TEXT NOT NULL DEFAULT ''",
            }
            for name, ddl in upgrades.items():
                if name not in cols: conn.execute(f"ALTER TABLE teachers ADD COLUMN {name} {ddl}")
            conn.execute("""CREATE TABLE IF NOT EXISTS staff_identity_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                staff_id TEXT NOT NULL DEFAULT '',
                staff_role TEXT NOT NULL DEFAULT '',
                action TEXT NOT NULL,
                changed_by TEXT NOT NULL DEFAULT '',
                note TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            )""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_staff_identity_role ON teachers(staff_role, status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_staff_identity_audit_created ON staff_identity_audit(created_at)")
            # Legacy EMT accounts automatically remain normal Teacher accounts; IMS always resolves to Islamiyyah.
            conn.execute("UPDATE teachers SET staff_role='islamiyyah_teacher' WHERE UPPER(teacher_id) LIKE 'IMS%' AND COALESCE(staff_role,'')!='islamiyyah_teacher'")
            conn.execute("UPDATE teachers SET staff_role='teacher_admin' WHERE UPPER(teacher_id) LIKE 'ADM%' AND COALESCE(staff_role,'')!='teacher_admin'")
            conn.execute("UPDATE teachers SET staff_role='teacher' WHERE (staff_role IS NULL OR TRIM(staff_role)='') AND UPPER(teacher_id) NOT LIKE 'IMS%' AND UPPER(teacher_id) NOT LIKE 'ADM%'")
            conn.commit(); _STAFF_SCHEMA_READY = True
        finally: conn.close()


def normalize_role(role):
    token = clean(role).lower().replace("-", "_").replace(" ", "_")
    aliases = {"islamiyah": "islamiyyah_teacher", "islamiyah_teacher": "islamiyyah_teacher", "islamiyyah": "islamiyyah_teacher", "ims": "islamiyyah_teacher", "emt": "teacher", "normal_teacher": "teacher", "adm": "teacher_admin", "teacheradmin": "teacher_admin", "admin_teacher": "teacher_admin"}
    token = aliases.get(token, token)
    if token not in ROLE_CONFIG: raise ValueError("Staff type must be Teacher, Teacher Admin or Islamiyyah Teacher.")
    return token


def role_from_staff_id(staff_id, stored_role=""):
    token = clean(staff_id).upper(); role = clean(stored_role).lower()
    if token.startswith("IMS"): return "islamiyyah_teacher"
    if token.startswith("ADM"): return "teacher_admin"
    if role in ROLE_CONFIG: return role
    return "teacher"


def _audit(conn, staff_id, staff_role, action, changed_by="", note=""):
    conn.execute("INSERT INTO staff_identity_audit(staff_id, staff_role, action, changed_by, note, created_at) VALUES(?,?,?,?,?,?)", (clean(staff_id).upper(), clean(staff_role), clean(action).upper(), clean(changed_by), clean(note), utc_now()))


def _serialize(row, include_password=False):
    if not row: return None
    data = dict(row); staff_id = clean(data.get("teacher_id")).upper(); role = role_from_staff_id(staff_id, data.get("staff_role")); status = clean(data.get("status")).lower() or "active"
    payload = {"id": data.get("id"), "staff_id": staff_id, "teacher_id": staff_id, "full_name": clean(data.get("full_name")), "status": status, "staff_role": role, "role_label": ROLE_CONFIG[role]["label"], "prefix": ROLE_CONFIG[role]["prefix"], "created_at": clean(data.get("created_at")), "updated_at": clean(data.get("updated_at")), "created_by": clean(data.get("created_by"))}
    if include_password: payload["password"] = str(data.get("password") or "")
    return payload


def list_staff_accounts(role="", include_password=False):
    init_staff_identity_tables(); normalized = normalize_role(role) if clean(role) else ""; conn = _connect()
    try:
        rows = conn.execute("SELECT * FROM teachers ORDER BY CASE WHEN UPPER(teacher_id) LIKE 'EMT%' THEN 0 WHEN UPPER(teacher_id) LIKE 'ADM%' THEN 1 WHEN UPPER(teacher_id) LIKE 'IMS%' THEN 2 ELSE 3 END, UPPER(teacher_id)").fetchall(); accounts = [_serialize(row, include_password=include_password) for row in rows]
        return [row for row in accounts if not normalized or row.get("staff_role") == normalized]
    finally: conn.close()


def get_staff_account(staff_id, include_password=False):
    init_staff_identity_tables(); token = clean(staff_id).upper(); conn = _connect()
    try:
        row = conn.execute("SELECT * FROM teachers WHERE UPPER(teacher_id)=? LIMIT 1", (token,)).fetchone(); return _serialize(row, include_password=include_password)
    finally: conn.close()


def _next_number(conn, prefix):
    # Reuse deleted numbers safely: allocate the lowest positive number not currently held by a live credential.
    live = [row[0] for row in conn.execute("SELECT teacher_id FROM teachers WHERE UPPER(teacher_id) LIKE ?", (f"{prefix}%",)).fetchall()]; used = set()
    for raw in live:
        token = clean(raw).upper()
        if token.startswith(prefix) and token[len(prefix):].isdigit(): used.add(int(token[len(prefix):]))
    number = 1
    while number in used: number += 1
    return number


def _password(length=10):
    letters = string.ascii_lowercase
    # Easy staff passwords: normal/Islamiyyah = abc12 (5 chars); Teacher Admin = abc123 (6 chars).
    digits = 3 if int(length) == 6 else 2
    return "".join(secrets.choice(letters) for _ in range(3)) + "".join(secrets.choice(string.digits) for _ in range(digits))


def generate_staff_ids(role="teacher", count=1, created_by=""):
    normalized = normalize_role(role); prefix = ROLE_CONFIG[normalized]["prefix"]
    try: count = int(count)
    except (TypeError, ValueError): raise ValueError("A valid ID quantity is required.")
    if count < 1 or count > 100: raise ValueError("Generate between 1 and 100 IDs at a time.")
    init_staff_identity_tables(); generated = []
    with STAFF_LOCK:
        conn = _connect()
        try:
            number = _next_number(conn, prefix)
            for _ in range(count):
                while conn.execute("SELECT 1 FROM teachers WHERE UPPER(teacher_id)=?", (f"{prefix}{number}",)).fetchone(): number += 1
                staff_id = f"{prefix}{number}"; password = _password(6 if normalized == "teacher_admin" else 5); now = utc_now()
                cursor = conn.execute("INSERT INTO teachers(teacher_id,password,full_name,status,staff_role,created_at,updated_at,created_by) VALUES(?,?,?,?,?,?,?,?)", (staff_id, password, "", "active", normalized, now, now, clean(created_by)))
                _audit(conn, staff_id, normalized, "CREATE", created_by, f"Generated {ROLE_CONFIG[normalized]['label']} credential")
                generated.append({"id": cursor.lastrowid, "staff_id": staff_id, "teacher_id": staff_id, "password": password, "full_name": "", "status": "active", "staff_role": normalized, "role_label": ROLE_CONFIG[normalized]["label"], "prefix": prefix, "created_at": now, "created_by": clean(created_by)})
                number += 1
            conn.commit(); return generated
        finally: conn.close()


def validate_staff_login(username, password):
    """Return the active staff account on success, otherwise None. Legacy plaintext credentials remain compatible."""
    init_staff_identity_tables(); token = clean(username).upper(); supplied = str(password or "")
    if not token or not supplied: return None
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM teachers WHERE UPPER(teacher_id)=? LIMIT 1", (token,)).fetchone()
        if not row: return None
        account = _serialize(row, include_password=True)
        if account.get("status") != "active" or str(account.get("password") or "") != supplied: return None
        account.pop("password", None); return account
    finally: conn.close()


def set_staff_status(row_id, status, changed_by=""):
    normalized = clean(status).lower()
    if normalized not in VALID_STATUSES: raise ValueError("Status must be active or inactive.")
    init_staff_identity_tables()
    with STAFF_LOCK:
        conn = _connect()
        try:
            row = conn.execute("SELECT * FROM teachers WHERE id=?", (int(row_id),)).fetchone()
            if not row: raise ValueError("Staff credential not found.")
            account = _serialize(row); now = utc_now(); conn.execute("UPDATE teachers SET status=?, updated_at=? WHERE id=?", (normalized, now, int(row_id))); _audit(conn, account["staff_id"], account["staff_role"], "STATUS", changed_by, f"Set account {normalized}"); conn.commit(); return get_staff_account(account["staff_id"])
        finally: conn.close()


def delete_staff_account(row_id, changed_by=""):
    init_staff_identity_tables()
    with STAFF_LOCK:
        conn = _connect()
        try:
            row = conn.execute("SELECT * FROM teachers WHERE id=?", (int(row_id),)).fetchone()
            if not row: return False
            account = _serialize(row); conn.execute("BEGIN IMMEDIATE"); _audit(conn, account["staff_id"], account["staff_role"], "DELETE", changed_by, "Credential deleted by administrator; numeric Staff ID slot released for reuse")
            # Remove orphanable teaching-load rows so a deleted account cannot leave privileges behind. Audit history remains timestamped even if the numeric ID is later reused.
            table_exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='teacher_assignments'").fetchone()
            if table_exists: conn.execute("DELETE FROM teacher_assignments WHERE UPPER(teacher_id)=?", (account["staff_id"],))
            conn.execute("DELETE FROM teachers WHERE id=?", (int(row_id),)); conn.commit(); return True
        except Exception:
            conn.rollback(); raise
        finally: conn.close()


def staff_identity_stats():
    accounts = list_staff_accounts(); teacher = [r for r in accounts if r["staff_role"] == "teacher"]; teacher_admin = [r for r in accounts if r["staff_role"] == "teacher_admin"]; islamiyyah = [r for r in accounts if r["staff_role"] == "islamiyyah_teacher"]
    return {"total": len(accounts), "teachers": len(teacher), "teacher_admins": len(teacher_admin), "islamiyyah_teachers": len(islamiyyah), "active": sum(1 for r in accounts if r.get("status") == "active"), "inactive": sum(1 for r in accounts if r.get("status") != "active")}


def list_staff_identity_audit(limit=80):
    init_staff_identity_tables(); limit = max(1, min(int(limit or 80), 250)); conn = _connect()
    try: return [dict(row) for row in conn.execute("SELECT id,staff_id,staff_role,action,changed_by,note,created_at FROM staff_identity_audit ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]
    finally: conn.close()
