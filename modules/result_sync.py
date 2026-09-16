# MODULE: EMIS Result Sync — Durable local result queue + authenticated cloud receiver
#
# Core rule:
#   1. Exam submission is saved locally first.
#   2. Sync is queued only after the local save succeeds.
#   3. Network failure never makes the student's local submission fail.
#   4. The deployed receiver writes through the normal student_results.save_result()
#      path, so Admin Results continues reading the normal RESULTS/.../results.xlsx files.

import hashlib
import hmac
import json
import os
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib import error as urllib_error
from urllib import request as urllib_request

from flask import Blueprint, jsonify, request, session

from modules.student_results import result_exists, save_result
from modules.excel_manager import read_results, normalize_result_term
from modules.class_config import normalize_class_level


sync_bp = Blueprint("result_sync_bp", __name__)

BASE_DIR = Path(__file__).resolve().parent.parent
SYNC_DIR = BASE_DIR / "sync_data"
SYNC_DB_PATH = SYNC_DIR / "result_sync.db"

DEFAULT_INTERVAL_SECONDS = 30
DEFAULT_TIMEOUT_SECONDS = 5
DEFAULT_MAX_BACKOFF_SECONDS = 15 * 60
DEFAULT_RECEIVER_CLOCK_SKEW_SECONDS = 5 * 60

_worker_lock = threading.Lock()
_flush_lock = threading.Lock()
_receiver_lock = threading.Lock()
_worker_event = threading.Event()
_worker_thread = None


# ============================================================
# CONFIGURATION
# ============================================================

def _clean(value):
    return str(value or "").strip()


def _env_bool(name, default=False):
    raw = os.getenv(name)
    if raw is None:
        return bool(default)
    return _clean(raw).lower() in {"1", "true", "yes", "on", "enabled"}


def sender_enabled():
    return _env_bool("EMIS_SYNC_SENDER_ENABLED", False)


def receiver_enabled():
    return _env_bool("EMIS_SYNC_RECEIVER_ENABLED", False)


def sync_target():
    return _clean(os.getenv("EMIS_SYNC_TARGET"))


def sync_secret():
    return _clean(os.getenv("EMIS_SYNC_KEY"))


def server_id():
    return _clean(os.getenv("EMIS_SYNC_SERVER_ID")) or "EMIS-LOCAL-01"


def sync_interval_seconds():
    try:
        return max(10, int(os.getenv("EMIS_SYNC_INTERVAL_SECONDS", DEFAULT_INTERVAL_SECONDS)))
    except (TypeError, ValueError):
        return DEFAULT_INTERVAL_SECONDS


def sync_timeout_seconds():
    try:
        return max(1, min(30, int(os.getenv("EMIS_SYNC_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS))))
    except (TypeError, ValueError):
        return DEFAULT_TIMEOUT_SECONDS


def sender_configured():
    return bool(sender_enabled() and sync_target() and sync_secret() and server_id())


def receiver_configured():
    return bool(receiver_enabled() and sync_secret())


# ============================================================
# TIME / JSON HELPERS
# ============================================================

def _utc_now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _json_dumps(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True, default=str)


def _safe_json_loads(value, default=None):
    try:
        return json.loads(value)
    except Exception:
        return {} if default is None else default


def _payload_hash(payload):
    return hashlib.sha256(_json_dumps(payload).encode("utf-8")).hexdigest()


def _new_sync_id(payload):
    # A stable UUID for this exact submission. submitted_at is part of the source
    # payload, so an intentionally different future submission receives a new id.
    source = "|".join([
        server_id(),
        _clean(payload.get("admission_number") or payload.get("student_id")),
        _clean(payload.get("subject")),
        _clean(payload.get("year")),
        _clean(payload.get("academic_session") or payload.get("session")),
        _clean(payload.get("term")),
        _clean(payload.get("submitted_at") or payload.get("submittedAt")),
    ])
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"emis-result-sync:{source}"))


# ============================================================
# DATABASE
# ============================================================

def _connect():
    SYNC_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(SYNC_DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=15000")
    return conn


def init_sync_db():
    conn = _connect()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sync_queue (
                sync_id TEXT PRIMARY KEY,
                server_id TEXT NOT NULL,
                payload TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING',
                retry_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_attempt_at TEXT,
                next_attempt_at REAL NOT NULL DEFAULT 0,
                last_error TEXT,
                remote_ack TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_sync_queue_status_next
            ON sync_queue(status, next_attempt_at);

            CREATE TABLE IF NOT EXISTS sync_receipts (
                sync_id TEXT PRIMARY KEY,
                server_id TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                result_key TEXT,
                receipt_status TEXT NOT NULL,
                received_at TEXT NOT NULL
            );
        """)
        conn.commit()
    finally:
        conn.close()


# ============================================================
# LOCAL QUEUE
# ============================================================

def queue_result_for_sync(result):
    """Persist a result for delivery. Never performs the network call inline."""
    if not sender_enabled():
        return {"queued": False, "status": "DISABLED", "sync_id": ""}

    if not sync_target() or not sync_secret():
        return {"queued": False, "status": "NOT_CONFIGURED", "sync_id": ""}

    payload = dict(result or {})
    sync_id = _clean(payload.get("sync_id")) or _new_sync_id(payload)
    payload["sync_id"] = sync_id
    serialized = _json_dumps(payload)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    now = _utc_now_iso()

    init_sync_db()
    conn = _connect()
    try:
        existing = conn.execute("SELECT status FROM sync_queue WHERE sync_id = ?", (sync_id,)).fetchone()
        if existing:
            return {"queued": True, "status": existing["status"], "sync_id": sync_id, "existing": True}

        conn.execute("""
            INSERT INTO sync_queue (
                sync_id, server_id, payload, payload_hash, status,
                retry_count, created_at, updated_at, next_attempt_at
            ) VALUES (?, ?, ?, ?, 'PENDING', 0, ?, ?, 0)
        """, (sync_id, server_id(), serialized, digest, now, now))
        conn.commit()
    finally:
        conn.close()

    return {"queued": True, "status": "PENDING", "sync_id": sync_id, "existing": False}


def _pending_rows(limit=50, force=False):
    init_sync_db()
    conn = _connect()
    try:
        now_epoch = time.time()
        if force:
            rows = conn.execute("""
                SELECT * FROM sync_queue
                WHERE status IN ('PENDING', 'FAILED')
                ORDER BY created_at ASC
                LIMIT ?
            """, (int(limit),)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM sync_queue
                WHERE status IN ('PENDING', 'FAILED')
                  AND COALESCE(next_attempt_at, 0) <= ?
                ORDER BY created_at ASC
                LIMIT ?
            """, (now_epoch, int(limit))).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def _result_key(payload):
    return "|".join([
        _clean(payload.get("admission_number") or payload.get("student_id")).lower(),
        _clean(payload.get("subject")).upper(),
        _clean(payload.get("year")),
        _clean(payload.get("academic_session") or payload.get("session")),
        _clean(payload.get("term")).upper(),
    ])


def _mark_attempt(sync_id):
    now = _utc_now_iso()
    conn = _connect()
    try:
        conn.execute("""
            UPDATE sync_queue
            SET retry_count = retry_count + 1,
                last_attempt_at = ?, updated_at = ?
            WHERE sync_id = ?
        """, (now, now, sync_id))
        conn.commit()
    finally:
        conn.close()


def _mark_synced(sync_id, acknowledgement):
    now = _utc_now_iso()
    conn = _connect()
    try:
        conn.execute("""
            UPDATE sync_queue
            SET status = 'SYNCED', updated_at = ?, next_attempt_at = 0,
                last_error = '', remote_ack = ?
            WHERE sync_id = ?
        """, (now, _json_dumps(acknowledgement or {}), sync_id))
        conn.commit()
    finally:
        conn.close()


def _mark_failed(sync_id, message):
    conn = _connect()
    try:
        row = conn.execute("SELECT retry_count FROM sync_queue WHERE sync_id = ?", (sync_id,)).fetchone()
        retries = int((row or {"retry_count": 1})["retry_count"] or 1)
        delay = min(DEFAULT_MAX_BACKOFF_SECONDS, max(sync_interval_seconds(), sync_interval_seconds() * (2 ** max(0, retries - 1))))
        conn.execute("""
            UPDATE sync_queue
            SET status = 'FAILED', updated_at = ?, next_attempt_at = ?, last_error = ?
            WHERE sync_id = ?
        """, (_utc_now_iso(), time.time() + delay, _clean(message)[:2000], sync_id))
        conn.commit()
    finally:
        conn.close()


def _signed_headers(raw_body, sync_id):
    timestamp = str(int(time.time()))
    signature = hmac.new(
        sync_secret().encode("utf-8"),
        timestamp.encode("utf-8") + b"." + raw_body,
        hashlib.sha256,
    ).hexdigest()

    return {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "EMIS-Result-Sync/1.0",
        "X-EMIS-Server-ID": server_id(),
        "X-EMIS-Sync-ID": sync_id,
        "X-EMIS-Timestamp": timestamp,
        "X-EMIS-Signature": signature,
    }


def _send_queue_row(row):
    payload = _safe_json_loads(row.get("payload"), {})
    sync_id = _clean(row.get("sync_id"))
    envelope = {"sync_id": sync_id, "server_id": server_id(), "result": payload}
    raw = _json_dumps(envelope).encode("utf-8")

    req = urllib_request.Request(
        sync_target(),
        data=raw,
        headers=_signed_headers(raw, sync_id),
        method="POST",
    )

    try:
        with urllib_request.urlopen(req, timeout=sync_timeout_seconds()) as response:
            response_body = response.read().decode("utf-8", errors="replace")
            acknowledgement = _safe_json_loads(response_body, {})
            if int(response.status) < 200 or int(response.status) >= 300:
                raise RuntimeError(f"Remote sync returned HTTP {response.status}")
            if acknowledgement.get("ok") is not True or acknowledgement.get("acknowledged") is not True:
                raise RuntimeError(acknowledgement.get("error") or "Remote server did not acknowledge the result")
            return acknowledgement

    except urllib_error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", errors="replace")
            parsed = _safe_json_loads(detail, {})
            detail = parsed.get("error") or parsed.get("details") or detail
        except Exception:
            detail = str(exc)
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    except urllib_error.URLError as exc:
        raise RuntimeError(f"Connection failed: {getattr(exc, 'reason', exc)}") from exc


def flush_sync_queue(limit=50, force=False):
    """Try eligible queued results. Safe to call repeatedly."""
    if not sender_configured():
        return {"configured": False, "attempted": 0, "synced": 0, "failed": 0}

    if not _flush_lock.acquire(blocking=False):
        return {"configured": True, "busy": True, "attempted": 0, "synced": 0, "failed": 0}

    attempted = synced = failed = 0
    try:
        for row in _pending_rows(limit=limit, force=force):
            attempted += 1
            sync_id = row["sync_id"]
            _mark_attempt(sync_id)
            try:
                ack = _send_queue_row(row)
                _mark_synced(sync_id, ack)
                synced += 1
            except Exception as exc:
                _mark_failed(sync_id, str(exc))
                failed += 1
        return {"configured": True, "busy": False, "attempted": attempted, "synced": synced, "failed": failed}
    finally:
        _flush_lock.release()


def _worker_loop():
    while True:
        _worker_event.wait(timeout=sync_interval_seconds())
        _worker_event.clear()
        try:
            flush_sync_queue(limit=100, force=False)
        except Exception as exc:
            print("[RESULT SYNC] Background worker error:", exc)


def trigger_background_sync():
    """Wake/start the local retry worker. No-op when sender is disabled."""
    global _worker_thread

    if not sender_configured():
        return False

    with _worker_lock:
        if _worker_thread is None or not _worker_thread.is_alive():
            _worker_thread = threading.Thread(target=_worker_loop, name="emis-result-sync", daemon=True)
            _worker_thread.start()

    _worker_event.set()
    return True


# ============================================================
# STATUS
# ============================================================

def sync_status_summary():
    init_sync_db()
    conn = _connect()
    try:
        counts = {"PENDING": 0, "FAILED": 0, "SYNCED": 0}
        for row in conn.execute("SELECT status, COUNT(*) AS count FROM sync_queue GROUP BY status").fetchall():
            counts[str(row["status"] or "").upper()] = int(row["count"] or 0)

        latest = conn.execute("""
            SELECT sync_id, status, retry_count, updated_at, last_attempt_at, last_error
            FROM sync_queue ORDER BY updated_at DESC LIMIT 1
        """).fetchone()
        received_count = int(conn.execute("SELECT COUNT(*) FROM sync_receipts").fetchone()[0] or 0)
        latest_receipt = conn.execute("""
            SELECT sync_id, server_id, receipt_status, received_at
            FROM sync_receipts ORDER BY received_at DESC LIMIT 1
        """).fetchone()

        return {
            "sender_enabled": sender_enabled(),
            "sender_configured": sender_configured(),
            "receiver_enabled": receiver_enabled(),
            "receiver_configured": receiver_configured(),
            "server_id": server_id(),
            "target": sync_target(),
            "pending": counts.get("PENDING", 0),
            "failed": counts.get("FAILED", 0),
            "synced": counts.get("SYNCED", 0),
            "received": received_count,
            "latest": dict(latest) if latest else None,
            "latest_receipt": dict(latest_receipt) if latest_receipt else None,
        }
    finally:
        conn.close()


def _staff_allowed():
    return _clean(session.get("user_type")).lower() in {"admin", "teacher"}


@sync_bp.route("/api/sync/status", methods=["GET"])
def api_sync_status():
    if not _staff_allowed():
        return jsonify({"error": "Unauthorized"}), 403
    return jsonify(sync_status_summary()), 200


@sync_bp.route("/api/sync/flush", methods=["POST"])
def api_sync_flush():
    if not _staff_allowed():
        return jsonify({"error": "Unauthorized"}), 403
    result = flush_sync_queue(limit=100, force=True)
    result["status"] = sync_status_summary()
    return jsonify(result), 200


# ============================================================
# DEPLOYED RECEIVER AUTHENTICATION
# ============================================================

def _allowed_server(server_name):
    configured = [item.strip() for item in _clean(os.getenv("EMIS_SYNC_ALLOWED_SERVERS")).split(",") if item.strip()]
    return not configured or server_name in configured


def _verify_receiver_request(raw_body):
    if not receiver_enabled():
        return False, "Result sync receiver is disabled", 404

    secret = sync_secret()
    if not secret:
        return False, "Result sync receiver is not configured", 503

    remote_server = _clean(request.headers.get("X-EMIS-Server-ID"))
    timestamp = _clean(request.headers.get("X-EMIS-Timestamp"))
    signature = _clean(request.headers.get("X-EMIS-Signature"))

    if not remote_server or not _allowed_server(remote_server):
        return False, "Sync server is not allowed", 403

    try:
        timestamp_value = int(timestamp)
    except (TypeError, ValueError):
        return False, "Invalid sync timestamp", 401

    try:
        skew = max(30, int(os.getenv("EMIS_SYNC_MAX_CLOCK_SKEW_SECONDS", DEFAULT_RECEIVER_CLOCK_SKEW_SECONDS)))
    except (TypeError, ValueError):
        skew = DEFAULT_RECEIVER_CLOCK_SKEW_SECONDS

    if abs(int(time.time()) - timestamp_value) > skew:
        return False, "Expired sync request", 401

    expected = hmac.new(
        secret.encode("utf-8"),
        timestamp.encode("utf-8") + b"." + raw_body,
        hashlib.sha256,
    ).hexdigest()

    if not signature or not hmac.compare_digest(signature, expected):
        return False, "Invalid sync signature", 401

    return True, remote_server, 200


def _receipt(sync_id):
    init_sync_db()
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM sync_receipts WHERE sync_id = ?", (sync_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _store_receipt(sync_id, remote_server, payload, receipt_status):
    init_sync_db()
    conn = _connect()
    try:
        conn.execute("""
            INSERT OR IGNORE INTO sync_receipts (
                sync_id, server_id, payload_hash, result_key, receipt_status, received_at
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            sync_id,
            remote_server,
            _payload_hash(payload),
            _result_key(payload),
            receipt_status,
            _utc_now_iso(),
        ))
        conn.commit()
    finally:
        conn.close()


def _excel_result_exists(payload):
    """Check the authoritative Excel result store before accepting a remote retry."""
    admission = _clean(payload.get("admission_number") or payload.get("student_id")).lower()
    subject = _clean(payload.get("subject"))
    year = _clean(payload.get("year"))
    term = normalize_result_term(payload.get("term"))
    academic_session = _clean(payload.get("academic_session") or payload.get("session"))
    class_level = normalize_class_level(
        payload.get("class_level")
        or payload.get("class_category")
        or payload.get("class_arm")
        or payload.get("class")
        or payload.get("class_name")
    )

    if not admission or not subject or not year or not class_level:
        return False

    try:
        rows = read_results(class_level, subject, year, term)
    except Exception:
        return False

    for row in rows or []:
        row_admission = _clean(row.get("Admission No") or row.get("Admission Number") or row.get("admission_number")).lower()
        if row_admission != admission:
            continue

        row_session = _clean(row.get("Session") or row.get("academic_session"))
        row_term = normalize_result_term(row.get("Term"))

        if academic_session and row_session and row_session != academic_session:
            continue
        if term and row_term and row_term != term:
            continue

        return True

    return False


def _semantic_result_exists(payload):
    # Excel is the Admin Results source of truth. SQLite remains part of the
    # existing save_result() write-through path, so check both stores.
    if _excel_result_exists(payload):
        return True

    return result_exists(
        admission_number=_clean(payload.get("admission_number") or payload.get("student_id")),
        subject=_clean(payload.get("subject")),
        year=_clean(payload.get("year")),
        academic_session=_clean(payload.get("academic_session") or payload.get("session")),
        term=_clean(payload.get("term")),
    )


# ============================================================
# DEPLOYED RESULT RECEIVER
# ============================================================

@sync_bp.route("/api/sync/results", methods=["POST"])
def receive_synced_result():
    raw_body = request.get_data(cache=True) or b""

    if not raw_body:
        return jsonify({"ok": False, "error": "Empty sync request"}), 400

    if len(raw_body) > 1024 * 1024:
        return jsonify({"ok": False, "error": "Sync request is too large"}), 413

    verified, auth_value, status_code = _verify_receiver_request(raw_body)
    if not verified:
        return jsonify({"ok": False, "error": auth_value}), status_code

    remote_server = auth_value
    envelope = request.get_json(silent=True) or {}
    sync_id = _clean(envelope.get("sync_id") or request.headers.get("X-EMIS-Sync-ID"))
    payload = envelope.get("result")

    if not sync_id:
        return jsonify({"ok": False, "error": "sync_id is required"}), 400

    if not isinstance(payload, dict) or not payload:
        return jsonify({"ok": False, "error": "Result payload is required"}), 400

    envelope_server = _clean(envelope.get("server_id"))
    if envelope_server and envelope_server != remote_server:
        return jsonify({"ok": False, "error": "Sync server identity mismatch"}), 400

    # Serialise receiver writes in this process. save_result() already protects
    # the normal SQLite/Excel write path; this lock closes the tiny duplicate
    # race between receipt lookup and semantic duplicate detection.
    with _receiver_lock:
        existing_receipt = _receipt(sync_id)
        if existing_receipt:
            return jsonify({
                "ok": True,
                "acknowledged": True,
                "sync_id": sync_id,
                "server_id": remote_server,
                "result": "already_received",
                "receipt_status": existing_receipt.get("receipt_status"),
            }), 200

        try:
            if _semantic_result_exists(payload):
                _store_receipt(sync_id, remote_server, payload, "DUPLICATE_EXISTING")
                return jsonify({
                    "ok": True,
                    "acknowledged": True,
                    "sync_id": sync_id,
                    "server_id": remote_server,
                    "result": "already_exists",
                    "receipt_status": "DUPLICATE_EXISTING",
                }), 200

            saved = save_result(dict(payload))

            if saved is False:
                _store_receipt(sync_id, remote_server, payload, "DUPLICATE_EXISTING")
                receipt_status = "DUPLICATE_EXISTING"
                result_text = "already_exists"
            else:
                _store_receipt(sync_id, remote_server, payload, "SAVED")
                receipt_status = "SAVED"
                result_text = "saved"

            return jsonify({
                "ok": True,
                "acknowledged": True,
                "sync_id": sync_id,
                "server_id": remote_server,
                "result": result_text,
                "receipt_status": receipt_status,
            }), 200

        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc), "sync_id": sync_id}), 400
        except Exception as exc:
            print(f"[RESULT SYNC] Receiver save error [{sync_id}]:", exc)
            return jsonify({"ok": False, "error": "Could not save synchronized result", "details": str(exc), "sync_id": sync_id}), 500
