# ============================================================
#  EMIS REAL-TIME NOTIFICATION ENGINE (2025)
# ============================================================

from flask import Blueprint, request, jsonify, session
from datetime import datetime

notifications_bp = Blueprint("notifications_bp", __name__)

# ============================================================
# IN-MEMORY QUEUE
# ============================================================
NOTIFICATION_QUEUE = []
MAX_QUEUE_SIZE = 200


def push_notification(n_type, message, payload=None):
    notif = {
        "type": n_type,
        "message": message,
        "payload": payload or {},
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    NOTIFICATION_QUEUE.append(notif)

    if len(NOTIFICATION_QUEUE) > MAX_QUEUE_SIZE:
        del NOTIFICATION_QUEUE[:50]

    return notif


# ============================================================
# ADMIN CHECK
# ============================================================
def is_admin():
    user = session.get("user_type", "")
    return user.lower() in ("admin", "teacher")


# ============================================================
# 1️⃣ STUDENT LOGIN NOTIFICATION
# ============================================================
@notifications_bp.route("/notify/login", methods=["POST"])
def notify_login():
    data = request.get_json(force=True)

    print("🔥 Login notification received:", data)

    name = data.get("student_name", "Unknown Student")
    adm  = data.get("admission_number", "???")
    cls  = data.get("class_category", "Unknown")

    message = f"{name} ({adm}) logged in — {cls}"

    notif = push_notification(
        "login",
        message,
        payload=data
    )

    return jsonify({"status": "ok", "notification": notif})


# ============================================================
# 2️⃣ EXAM START NOTIFICATION
# ============================================================
@notifications_bp.route("/notify/exam_start", methods=["POST"])
def notify_exam_start():
    data = request.get_json(force=True)

    print("🔥 Exam START notification:", data)

    name = data.get("student_name", "").strip() or "Unknown Student"
    adm  = data.get("admission_number", "???")
    subject = data.get("subject", "")
    cls  = data.get("class_category", "")
    year = data.get("year", "")

    message = f"STARTED: {name} ({adm}) — {subject} | {cls} | {year}"

    notif = push_notification(
        "exam_start",
        message,
        payload=data
    )

    return jsonify({"status": "ok", "notification": notif})


# ============================================================
# 3️⃣ EXAM END / SUBMISSION NOTIFICATION
# ============================================================
@notifications_bp.route("/notify/exam_end", methods=["POST"])
def notify_exam_end():
    data = request.get_json(force=True)

    print("🔥 Exam END notification:", data)

    name   = data.get("student_name", "")
    adm    = data.get("admission_number", "")
    sub    = data.get("subject", "")
    cls    = data.get("class_category", "")
    year   = data.get("year", "")
    score  = data.get("score", 0)   # RAW SCORE
    total  = data.get("total_questions", 0)
    status = data.get("status", "completed")

    # 🔥 Clean message: RAW SCORE + TOTAL, no percent
    message = (
        f"SUBMITTED: {name} ({adm}) — {sub} | Score: {score}/{total} "
        f"| {cls} | {year} | Status: {status}"
    )

    notif = push_notification(
        "exam_end",
        message,
        payload=data
    )

    return jsonify({"status": "ok", "notification": notif})



# ============================================================
# 4️⃣ ADMIN POLL — FETCH NOTIFICATIONS
# ============================================================
@notifications_bp.route("/fetch")
def fetch_notifications():
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 403

    return jsonify({"notifications": NOTIFICATION_QUEUE})


# ============================================================
# 5️⃣ CLEAR NOTIFICATIONS
# ============================================================
@notifications_bp.route("/clear", methods=["POST"])
def clear_notifications():
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 403

    NOTIFICATION_QUEUE.clear()
    return jsonify({"status": "cleared"})
