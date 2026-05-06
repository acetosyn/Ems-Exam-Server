# # user_exam.py
# import sqlite3
# from pathlib import Path
# from datetime import datetime
# import csv

# DB_PATH = Path("database.db")
# LOGS_DIR = Path("logs")
# LOGS_DIR.mkdir(exist_ok=True)

# # ==========================
# #   INIT
# # ==========================
# def init_db():
#     """Ensure exam_results table exists (with status column)."""
#     conn = sqlite3.connect(DB_PATH)
#     cursor = conn.cursor()
#     cursor.execute("""
#         CREATE TABLE IF NOT EXISTS exam_results (
#             id INTEGER PRIMARY KEY AUTOINCREMENT,
#             username TEXT NOT NULL,
#             fullname TEXT NOT NULL,
#             email TEXT,
#             subject TEXT NOT NULL,
#             score INTEGER NOT NULL,
#             correct INTEGER,
#             total INTEGER,
#             answered INTEGER,
#             time_taken INTEGER,
#             submitted_at TEXT NOT NULL,
#             status TEXT DEFAULT 'completed'
#         )
#     """)
#     conn.commit()
#     conn.close()

# # ==========================
# #   SAVE RESULT
# # ==========================
# def save_exam_result(username, fullname, email, subject,
#                      score, correct, total, answered,
#                      time_taken, submitted_at=None,
#                      status="completed"):
#     """Save candidate exam results into DB and CSV log."""
#     init_db()
#     conn = sqlite3.connect(DB_PATH)
#     cursor = conn.cursor()

#     if not submitted_at:
#         submitted_at = datetime.utcnow().isoformat()

#     cursor.execute("""
#         INSERT INTO exam_results (
#             username, fullname, email, subject,
#             score, correct, total, answered,
#             time_taken, submitted_at, status
#         ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
#     """, (
#         username, fullname, email, subject,
#         score, correct, total, answered,
#         time_taken, submitted_at, status
#     ))
#     conn.commit()
#     conn.close()

#     save_exam_to_csv(username, fullname, email, subject,
#                      score, correct, total, answered,
#                      time_taken, submitted_at, status)

#     return True

# def save_exam_to_csv(username, fullname, email, subject,
#                      score, correct, total, answered,
#                      time_taken, submitted_at, status):
#     """Append exam results to CSV log file."""
#     today = datetime.now().strftime("%Y-%m-%d")
#     log_file = LOGS_DIR / f"exam_results_{today}.csv"
#     new_file = not log_file.exists()
#     with open(log_file, "a", newline="") as csvfile:
#         fieldnames = [
#             "username", "fullname", "email", "subject",
#             "score", "correct", "total", "answered",
#             "time_taken", "submitted_at", "status"
#         ]
#         writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
#         if new_file:
#             writer.writeheader()
#         writer.writerow({
#             "username": username,
#             "fullname": fullname,
#             "email": email,
#             "subject": subject,
#             "score": score,
#             "correct": correct,
#             "total": total,
#             "answered": answered,
#             "time_taken": time_taken,
#             "submitted_at": submitted_at,
#             "status": status
#         })

# # ==========================
# #   GET RESULTS
# # ==========================
# def get_exam_results(limit=100):
#     """Fetch latest exam results for admin dashboard."""
#     init_db()
#     conn = sqlite3.connect(DB_PATH)
#     cursor = conn.cursor()
#     cursor.execute("""
#         SELECT username, fullname, email, subject,
#                score, correct, total, answered,
#                time_taken, submitted_at, status
#         FROM exam_results
#         ORDER BY id DESC
#         LIMIT ?
#     """, (limit,))
#     rows = cursor.fetchall()
#     conn.close()

#     return [
#         {
#             "username": r[0],
#             "fullname": r[1],
#             "email": r[2],
#             "subject": r[3],
#             "score": r[4],
#             "correct": r[5],
#             "total": r[6],
#             "answered": r[7],
#             "time_taken": r[8],
#             "submitted_at": r[9],
#             "status": r[10]
#         }
#         for r in rows
#     ]


# def delete_result(username):
#     """Delete all exam results for a given username from the database and CSV logs."""
#     init_db()
#     conn = sqlite3.connect(DB_PATH)
#     cursor = conn.cursor()

#     # Delete from DB
#     cursor.execute("DELETE FROM exam_results WHERE username = ?", (username,))
#     deleted_count = cursor.rowcount
#     conn.commit()
#     conn.close()

#     # Optional: clean up CSV logs too
#     for file in LOGS_DIR.glob("exam_results_*.csv"):
#         try:
#             rows = []
#             with open(file, "r", encoding="utf-8") as f:
#                 reader = csv.DictReader(f)
#                 for row in reader:
#                     if row.get("username") != username:
#                         rows.append(row)
#             with open(file, "w", newline="", encoding="utf-8") as f:
#                 writer = csv.DictWriter(f, fieldnames=rows[0].keys() if rows else [])
#                 if rows:
#                     writer.writeheader()
#                     writer.writerows(rows)
#         except Exception as e:
#             print(f"⚠️ Error cleaning CSV {file}: {e}")

#     return deleted_count > 0



# def get_user_latest_result(username):
#     """Fetch the most recent exam result for a given username."""
#     init_db()
#     conn = sqlite3.connect(DB_PATH)
#     cursor = conn.cursor()
#     cursor.execute("""
#         SELECT username, fullname, email, subject,
#                score, correct, total, answered,
#                time_taken, submitted_at, status
#         FROM exam_results
#         WHERE username = ?
#         ORDER BY id DESC
#         LIMIT 1
#     """, (username,))
#     row = cursor.fetchone()
#     conn.close()

#     if not row:
#         return None

#     return {
#         "username": row[0],
#         "fullname": row[1],
#         "email": row[2],
#         "subject": row[3],
#         "score": row[4],
#         "correct": row[5],
#         "total": row[6],
#         "answered": row[7],
#         "time_taken": row[8],
#         "submitted_at": row[9],
#         "status": row[10],
#         # add placeholders for frontend
#         "flagged": 0,
#         "tabSwitches": 0
#     }
