# modules/notifications.py

from flask import Blueprint, request, jsonify, session, Response, stream_with_context
from datetime import datetime
import json
import time
import uuid


notifications_bp = Blueprint("notifications_bp", __name__)

NOTIFICATION_QUEUE = []
MAX_QUEUE_SIZE = 500


def now_stamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def push_notification(n_type, message, payload=None):
    notif = {
        "id": str(uuid.uuid4()),
        "type": n_type,
        "message": message,
        "payload": payload or {},
        "timestamp": now_stamp(),
        "created_at": time.time()
    }

    NOTIFICATION_QUEUE.append(notif)

    if len(NOTIFICATION_QUEUE) > MAX_QUEUE_SIZE:
        del NOTIFICATION_QUEUE[:100]

    return notif


def is_admin():
    return str(session.get("user_type", "")).lower() in ["admin", "teacher"]


def get_class_label(data):
    class_category = str(data.get("class_category", "Unknown")).strip()
    class_name = str(data.get("class_name") or data.get("class") or "").strip()

    if class_name and class_name.upper() != class_category.upper():
        return f"{class_name} / {class_category}"

    return class_category


@notifications_bp.route("/notify/login", methods=["POST"])
def notify_login():
    data = request.get_json(force=True) or {}

    name = data.get("student_name") or data.get("full_name") or "Unknown Student"
    adm = data.get("admission_number") or data.get("admission_no") or "???"
    cls = get_class_label(data)

    message = f"{name} ({adm}) logged in — {cls}"

    notif = push_notification("login", message, payload=data)

    return jsonify({"status": "ok", "notification": notif})


@notifications_bp.route("/notify/exam_start", methods=["POST"])
def notify_exam_start():
    data = request.get_json(force=True) or {}

    name = data.get("student_name") or data.get("full_name") or "Unknown Student"
    adm = data.get("admission_number") or data.get("admission_no") or "???"
    subject = data.get("subject", "")
    cls = get_class_label(data)
    year = data.get("year", "")

    message = f"STARTED: {name} ({adm}) — {subject} | {cls} | {year}"

    notif = push_notification("exam_start", message, payload=data)

    return jsonify({"status": "ok", "notification": notif})


@notifications_bp.route("/notify/exam_end", methods=["POST"])
def notify_exam_end():
    data = request.get_json(force=True) or {}

    name = data.get("student_name") or data.get("full_name") or "Unknown Student"
    adm = data.get("admission_number") or data.get("admission_no") or "???"
    subject = data.get("subject", "")
    cls = get_class_label(data)
    year = data.get("year", "")
    score = data.get("score", 0)
    total = data.get("total_questions") or data.get("total") or 0
    status = data.get("status", "completed")

    message = (
        f"SUBMITTED: {name} ({adm}) — {subject} | Score: {score}/{total} "
        f"| {cls} | {year} | Status: {status}"
    )

    notif = push_notification("exam_end", message, payload=data)

    return jsonify({"status": "ok", "notification": notif})


@notifications_bp.route("/fetch")
def fetch_notifications():
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 403

    since = request.args.get("since", "").strip()

    if since:
        notifications = [
            n for n in NOTIFICATION_QUEUE
            if str(n.get("created_at", 0)) > since
        ]
    else:
        notifications = NOTIFICATION_QUEUE

    return jsonify({
        "notifications": notifications,
        "last_event_time": NOTIFICATION_QUEUE[-1]["created_at"] if NOTIFICATION_QUEUE else 0
    })


@notifications_bp.route("/stream")
def stream_notifications():
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 403

    def event_stream():
        last_index = len(NOTIFICATION_QUEUE)

        yield "event: connected\n"
        yield f"data: {json.dumps({'status': 'connected', 'timestamp': now_stamp()})}\n\n"

        while True:
            try:
                if len(NOTIFICATION_QUEUE) > last_index:
                    new_items = NOTIFICATION_QUEUE[last_index:]
                    last_index = len(NOTIFICATION_QUEUE)

                    for item in new_items:
                        yield "event: notification\n"
                        yield f"data: {json.dumps(item)}\n\n"
                else:
                    yield "event: ping\n"
                    yield f"data: {json.dumps({'timestamp': now_stamp()})}\n\n"

                time.sleep(2)

            except GeneratorExit:
                break

    return Response(
        stream_with_context(event_stream()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )


@notifications_bp.route("/clear", methods=["POST"])
def clear_notifications():
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 403

    NOTIFICATION_QUEUE.clear()

    return jsonify({"status": "cleared"})