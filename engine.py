# engine.py — handles business logic (file uploads, listing, etc.)
import os, mimetypes, datetime
from werkzeug.utils import secure_filename
import os
import sqlite3
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")

ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "xls", "xlsx"}
UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads")  # /uploads in project root
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def save_uploaded_file(file_storage):
    """Save uploaded file securely."""
    if file_storage and allowed_file(file_storage.filename):
        filename = secure_filename(file_storage.filename)
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file_storage.save(file_path)
        return {"success": True, "path": file_path, "filename": filename}
    return {"success": False, "error": "Invalid file type"}

def list_documents(query: str | None = None):
    """Return metadata for files in uploads. Optional partial name filter."""
    try:
        files = []
        q = (query or "").strip().lower()
        for name in os.listdir(UPLOAD_FOLDER):
            full = os.path.join(UPLOAD_FOLDER, name)
            if not os.path.isfile(full):
                continue
            ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
            if ext not in ALLOWED_EXTENSIONS:
                continue
            if q and q not in name.lower():
                continue
            st = os.stat(full)
            mtime = datetime.datetime.fromtimestamp(st.st_mtime)
            mime, _ = mimetypes.guess_type(full)
            files.append({
                "name": name,
                "ext": ext,
                "size": st.st_size,
                "mtime": st.st_mtime,
                "mtime_str": mtime.strftime("%Y-%m-%d %H:%M"),
                "mime": mime or "application/octet-stream",
                # url built in app.py route /uploads/<filename>
            })
        # newest first
        files.sort(key=lambda x: x["mtime"], reverse=True)
        return files
    except Exception as e:
        return []

# ===========================================================
# TEACHER ID GENERATION & AUTH MANAGEMENT (Updated)
# ===========================================================



# -------------------------------
# INIT
# -------------------------------
def init_teacher_table():
    """Ensure the teachers table exists."""
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS teachers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                teacher_id TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                full_name TEXT,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()


# -------------------------------
# GENERATE TEACHER IDS
# -------------------------------
def generate_teacher_ids(start_num=1, count=1):
    """
    Generate new teacher IDs and passwords.
    Example output: EMT001 / ems1, EMT002 / ems2 ...
    """
    init_teacher_table()
    generated = []
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()

        # Find the last numeric ID used
        c.execute("SELECT teacher_id FROM teachers ORDER BY id DESC LIMIT 1")
        last_id = c.fetchone()
        start_index = start_num

        if last_id:
            try:
                num_part = int(''.join(filter(str.isdigit, last_id[0])))
                start_index = num_part + 1
            except Exception:
                start_index = start_num

        # Generate new IDs
        for i in range(count):
            teacher_id = f"EMT{str(start_index + i).zfill(3)}"
            password = f"ems{start_index + i}"
            c.execute("""
                INSERT OR IGNORE INTO teachers (teacher_id, password)
                VALUES (?, ?)
            """, (teacher_id, password))
            generated.append({
                "teacher_id": teacher_id,
                "password": password,
                "status": "active",
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
        conn.commit()

    return generated


# -------------------------------
# FETCH ALL TEACHERS
# -------------------------------
def get_all_teachers():
    """Return all teacher records."""
    init_teacher_table()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM teachers ORDER BY id DESC")
        return [dict(r) for r in c.fetchall()]


# -------------------------------
# VALIDATE LOGIN
# -------------------------------
def validate_teacher_login(teacher_id, password):
    """Authenticate teacher credentials."""
    init_teacher_table()
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            SELECT * FROM teachers 
            WHERE teacher_id=? AND password=? AND status='active'
        """, (teacher_id.strip(), password.strip()))
        return c.fetchone() is not None




# -------------------------------
# DELETE TEACHER BY ID
# -------------------------------
def delete_teacher_from_db(row_id: int):
    """Delete teacher record by SQLite row ID."""
    init_teacher_table()
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM teachers WHERE id = ?", (row_id,))
        conn.commit()
        return c.rowcount > 0  # True if deleted, False if not found
