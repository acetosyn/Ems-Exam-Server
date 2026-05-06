import requests
import os
from email.message import EmailMessage


def _smtp_send(msg: EmailMessage) -> bool:
    """
    Sends email via the Flask relay server hosted on PythonAnywhere.
    Converts EmailMessage to HTML and posts to the /send endpoint.
    """
    SMTP_HOST = os.getenv("SMTP_HOST", "acetosyn097007.pythonanywhere.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "443"))

    try:
        # Extract fields
        subject = msg["Subject"]
        to = msg["To"]
        html = msg.get_body(preferencelist=('html')).get_content()

        # Send via HTTPS to relay
        url = f"https://{SMTP_HOST}/send"
        payload = {"subject": subject, "to": to, "html": html}
        response = requests.post(url, json=payload, timeout=20)

        if response.status_code == 200:
            print(f"[email_server] ✅ Email sent to {to}")
            return True
        else:
            print(f"[email_server] ⚠️ Relay error {response.status_code}: {response.text}")
            return False

    except Exception as e:
        print(f"[email_server] ❌ Relay send error: {e}")
        return False


"""
email_server.py
Real-time email notifications (admin + candidate) with PDF attachment for EMIS.

Environment variables (example in your .env):
  SMTP_HOST=smtp.gmail.com
  SMTP_PORT=587
  SMTP_USER=epiconsultdiagnostics1@gmail.com
  SMTP_PASS=ubvbncjejczudcol
  EMAIL_FROM=portal.epitomeschools@gmail.com
  NOTIFY_EMAIL=portal.epitomeschools@gmail.com

Notes:
- EMAIL_FROM controls the 'From' header (Gmail may display your SMTP_USER,
  but the header will still be set correctly).
- Admin email gets PDF + today's CSV log (if present).
- Candidate email gets the same PDF.
"""

import os
import io
import smtplib
from email.message import EmailMessage
from email.utils import formatdate
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from dotenv import load_dotenv

# PDF generation
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import mm

# Paths
LOGS_DIR = Path("logs")

# Load env (safe to call many times; no-op if already loaded)
load_dotenv()


# ---------------------------
# Utilities
# ---------------------------
def _fmt_time(seconds: int) -> str:
    try:
        seconds = int(seconds or 0)
    except Exception:
        seconds = 0
    m, s = divmod(seconds, 60)
    return f"{m}m {s:02d}s"


def _compute_pass_fail(result: Dict) -> str:
    """
    Business rule: PASS if correct >= 20 out of 40; else FAILED.
    If 'pass_fail' is already present, use it.
    """
    if "pass_fail" in result and result["pass_fail"]:
        return result["pass_fail"]
    correct = int(result.get("correct") or 0)
    return "PASS" if correct >= 20 else "FAILED"


def _compose_subject_admin(result: Dict) -> str:
    """
    Subject example:
      [EMIS] Exam Completion — candidate0001 — PASS (21/40, BIOLOGY)
    """
    username = result.get("username") or "unknown"
    status   = _compute_pass_fail(result)
    correct  = int(result.get("correct") or 0)
    total    = int(result.get("total") or 0)
    subject  = (result.get("subject") or "EXAM").upper()
    return f"[EMIS] Exam Completion — {username} — {status} ({correct}/{total}, {subject})"


def _compose_subject_candidate(result: Dict) -> str:
    """
    Subject example to candidate:
      [EMIS] Your Exam Result — PASS (21/40, BIOLOGY)
    """
    status   = _compute_pass_fail(result)
    correct  = int(result.get("correct") or 0)
    total    = int(result.get("total") or 0)
    subject  = (result.get("subject") or "EXAM").upper()
    return f"[EMIS] Your Exam Result — {status} ({correct}/{total}, {subject})"



def _compose_body_admin_text(result: Dict) -> str:
    full_name = result.get("fullname") or "Candidate"
    username  = result.get("username") or "N/A"
    subject   = (result.get("subject") or "Exam").upper()
    correct   = int(result.get("correct") or 0)
    total     = int(result.get("total") or 0)
    percent   = int(result.get("score") or 0)
    status    = _compute_pass_fail(result)
    time_tk   = _fmt_time(result.get("time_taken"))
    submitted = result.get("submitted_at") or datetime.utcnow().isoformat()

    opening = (
        "has successfully completed their examination. The candidate PASSED."
        if status == "PASS"
        else "has completed their examination. The candidate did not meet the pass threshold."
    )

    return f"""Dear Epitome Administration,

This is to notify you that candidate {username} ({full_name}) {opening}

• Subject: {subject}
• Score: {correct}/{total} ({percent}%)
• Outcome: {status}
• Time Taken: {time_tk}
• Submitted: {submitted}

A one-page PDF summary is attached. The rolling CSV log for today is also attached (if available).

Warm regards,
EMIS Exam Portal
"""


def _compose_body_admin_html(result: Dict) -> str:
    full_name = result.get("fullname") or "Candidate"
    username  = result.get("username") or "N/A"
    subject   = (result.get("subject") or "Exam").upper()
    correct   = int(result.get("correct") or 0)
    total     = int(result.get("total") or 0)
    percent   = int(result.get("score") or 0)
    status    = _compute_pass_fail(result)
    time_tk   = _fmt_time(result.get("time_taken"))
    submitted = result.get("submitted_at") or datetime.utcnow().isoformat()

    badge_color = "#16a34a" if status == "PASS" else "#dc2626"
    badge_bg    = "#dcfce7" if status == "PASS" else "#fee2e2"
    intro = (
        "has successfully completed their examination. <b>The candidate PASSED.</b>"
        if status == "PASS" else
        "has completed their examination. <b>The candidate did not meet the pass threshold.</b>"
    )

    return f"""
  <div style="font-family:Inter,Arial,sans-serif;color:#111827;line-height:1.5;">
    <p>Dear Epitome Administration,</p>
    <p>
      This is to notify you that candidate <b>{username}</b> ({full_name}) {intro}
    </p>

    <div style="margin:16px 0;padding:12px;border:1px solid #e5e7eb;border-radius:10px;">
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
        <span style="background:{badge_bg};color:{badge_color};padding:6px 10px;border-radius:999px;font-weight:700;">{status}</span>
        <span style="font-weight:600">{subject}</span>
      </div>
      <div>Score: <b>{correct}/{total} ({percent}%)</b></div>
      <div>Time Taken: <b>{time_tk}</b></div>
      <div>Submitted: <b>{submitted}</b></div>
    </div>

    <p>
      A one-page PDF summary is attached. The rolling CSV log for today is also attached (if available).
    </p>
    <p>Warm regards,<br/>EMIS Exam Portal</p>
  </div>
  """.strip()


def _compose_body_candidate_text(result: Dict) -> str:
    full_name = result.get("fullname") or "Candidate"
    subject   = (result.get("subject") or "Exam").upper()
    correct   = int(result.get("correct") or 0)
    total     = int(result.get("total") or 0)
    percent   = int(result.get("score") or 0)
    status    = _compute_pass_fail(result)
    time_tk   = _fmt_time(result.get("time_taken"))
    submitted = result.get("submitted_at") or datetime.utcnow().isoformat()

    summary_line = (
        "Congratulations on successfully completing your examination. You PASSED."
        if status == "PASS" else
        "You have completed your examination. You did not meet the pass threshold this time."
    )

    return f"""Dear {full_name},

{summary_line}

• Subject: {subject}
• Score: {correct}/{total} ({percent}%)
• Outcome: {status}
• Time Taken: {time_tk}
• Submitted: {submitted}

A one-page PDF summary of your result is attached for your record.

Warm regards,
Epitome Model Islamic Schools (EMIS)
"""


def _compose_body_candidate_html(result: Dict) -> str:
    full_name = result.get("fullname") or "Candidate"
    subject   = (result.get("subject") or "Exam").upper()
    correct   = int(result.get("correct") or 0)
    total     = int(result.get("total") or 0)
    percent   = int(result.get("score") or 0)
    status    = _compute_pass_fail(result)
    time_tk   = _fmt_time(result.get("time_taken"))
    submitted = result.get("submitted_at") or datetime.utcnow().isoformat()

    badge_color = "#16a34a" if status == "PASS" else "#dc2626"
    badge_bg    = "#dcfce7" if status == "PASS" else "#fee2e2"
    intro = (
        "Congratulations on successfully completing your examination. <b>You PASSED.</b>"
        if status == "PASS" else
        "You have completed your examination. <b>You did not meet the pass threshold this time.</b>"
    )

    return f"""
  <div style="font-family:Inter,Arial,sans-serif;color:#111827;line-height:1.5;">
    <p>Dear {full_name},</p>
    <p>{intro}</p>

    <div style="margin:16px 0;padding:12px;border:1px solid #e5e7eb;border-radius:10px;">
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
        <span style="background:{badge_bg};color:{badge_color};padding:6px 10px;border-radius:999px;font-weight:700;">{status}</span>
        <span style="font-weight:600">{subject}</span>
      </div>
      <div>Score: <b>{correct}/{total} ({percent}%)</b></div>
      <div>Time Taken: <b>{time_tk}</b></div>
      <div>Submitted: <b>{submitted}</b></div>
    </div>

    <p>A one-page PDF summary of your result is attached for your record.</p>
    <p>Warm regards,<br/>Epitome Model Islamic Schools (EMIS)</p>
  </div>
  """.strip()


def _generate_pdf_bytes(result: Dict) -> bytes:
    """
    Generate a simple, branded one-page PDF in-memory with reportlab.
    """
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    # Margins
    left = 22 * mm
    top_y = height - 25 * mm

    # Title / Header
    c.setFillColor(colors.HexColor("#0f2b46"))
    c.setFont("Helvetica-Bold", 18)
    c.drawString(left, top_y, "EMIS — Examination Result Summary")

    c.setFillColor(colors.black)
    c.setFont("Helvetica", 11)

    # Horizontal line
    c.setStrokeColor(colors.HexColor("#38bdf8"))
    c.setLineWidth(2)
    c.line(left, top_y - 6 * mm, width - left, top_y - 6 * mm)

    # Body content
    y = top_y - 15 * mm

    def row(label, value):
        nonlocal y
        c.setFont("Helvetica-Bold", 11)
        c.drawString(left, y, f"{label}:")
        c.setFont("Helvetica", 11)
        c.drawString(left + 42 * mm, y, value)
        y -= 8 * mm

    # Data
    username  = result.get("username") or "N/A"
    fullname  = result.get("fullname") or "N/A"
    subject   = (result.get("subject") or "EXAM").upper()
    correct   = int(result.get("correct") or 0)
    total     = int(result.get("total") or 0)
    percent   = int(result.get("score") or 0)
    status    = _compute_pass_fail(result)
    time_tk   = _fmt_time(result.get("time_taken"))
    submitted = result.get("submitted_at") or datetime.utcnow().isoformat()

    # Status Badge
    badge_color = colors.HexColor("#16a34a") if status == "PASS" else colors.HexColor("#dc2626")
    c.setFillColor(badge_color)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(left, y, f"Outcome: {status}")
    y -= 10 * mm

    c.setFillColor(colors.black)
    row("Candidate", f"{fullname} ({username})")
    row("Subject", subject)
    row("Score", f"{correct}/{total}  ({percent}%)")
    row("Time Taken", time_tk)
    row("Submitted", submitted)

    # Footer note
    c.setFillColor(colors.HexColor("#6b7280"))
    c.setFont("Helvetica-Oblique", 9)
    c.drawString(left, 20 * mm, "Generated automatically by EMIS Exam Portal")

    c.showPage()
    c.save()
    return buf.getvalue()


def _build_base_message(to_email: str, subject: str, text: str, html: str) -> EmailMessage:
    EMAIL_FROM = os.getenv("EMAIL_FROM", os.getenv("SMTP_USER", "no-reply@emis.local"))
    msg = EmailMessage()
    msg["From"] = EMAIL_FROM
    msg["To"] = to_email
    msg["Date"] = formatdate(localtime=True)
    msg["Subject"] = subject
    # Optional reply-to could be set to EMAIL_FROM as well:
    msg["Reply-To"] = EMAIL_FROM
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    return msg




def _smtp_send(msg: EmailMessage) -> bool:
    """
    Sends email either directly via Gmail SMTP or via Flask relay (PythonAnywhere),
    depending on which environment variables are present.
    """
    try:
        # --- Check if direct Gmail SMTP is configured ---
        smtp_host = os.getenv("MAIL_SERVER")
        smtp_user = os.getenv("MAIL_USERNAME")
        smtp_pass = os.getenv("MAIL_PASSWORD")

        if smtp_host and smtp_user and smtp_pass:
            smtp_port = int(os.getenv("MAIL_PORT", 587))
            use_tls = os.getenv("MAIL_USE_TLS", "True").lower() == "true"

            print(f"[email_server] 📧 Sending directly via SMTP ({smtp_host}:{smtp_port})")

            with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
                if use_tls:
                    server.starttls()
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)

            print(f"[email_server] ✅ Email sent directly to {msg['To']}")
            return True

        # --- Otherwise fallback to HTTP relay ---
        relay_url = os.getenv("RELAY_URL")
        if relay_url:
            subject = msg["Subject"]
            to = msg["To"]
            html_part = msg.get_body(preferencelist=('html'))
            html = html_part.get_content() if html_part else msg.get_content()

            payload = {"subject": subject, "to": to, "html": html}
            print(f"[email_server] 🌐 Relaying email to {relay_url}")
            response = requests.post(relay_url, json=payload, timeout=20)

            if response.status_code == 200:
                print(f"[email_server] ✅ Email relayed successfully to {to}")
                return True
            else:
                print(f"[email_server] ⚠️ Relay error {response.status_code}: {response.text}")
                return False

        print("[email_server] ⚠️ No SMTP or RELAY configuration found.")
        return False

    except Exception as e:
        print(f"[email_server] ❌ Send error: {e}")
        return False



def send_admin_email(result: Dict) -> bool:
    """
    Sends the admin email with PDF and today's CSV attached (if available).
    Supports multiple recipients (comma-separated in NOTIFY_EMAIL).
    """
    # Read recipients directly (comma-separated string is valid)
    admin_to = os.getenv("NOTIFY_EMAIL", "spectrobana@gmail.com")

    subject = _compose_subject_admin(result)
    text    = _compose_body_admin_text(result)
    html    = _compose_body_admin_html(result)

    msg = _build_base_message(admin_to, subject, text, html)

    # Attach PDF
    pdf_bytes = _generate_pdf_bytes(result)
    username  = result.get("username") or "candidate"
    ts        = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_filename = f"EMIS_Result_{username}_{ts}.pdf"
    msg.add_attachment(pdf_bytes, maintype="application", subtype="pdf", filename=pdf_filename)

    # Attach today's CSV if present
    today_csv = LOGS_DIR / f"exam_results_{datetime.now().strftime('%Y-%m-%d')}.csv"
    if today_csv.exists():
        with open(today_csv, "rb") as f:
            msg.add_attachment(
                f.read(),
                maintype="text",
                subtype="csv",
                filename=today_csv.name
            )

    return _smtp_send(msg)



def send_candidate_email(result: Dict) -> bool:
    """
    Sends the candidate email (with the same one-page PDF).
    Supports multiple addresses if `email` contains commas.
    """
    candidate_env = result.get("email", "").strip()
    if not candidate_env:
        print("[email_server] Candidate email missing; skipping candidate email.")
        return False

    # Split in case multiple addresses are given
    candidate_list = [addr.strip() for addr in candidate_env.split(",") if addr.strip()]

    subject = _compose_subject_candidate(result)
    text    = _compose_body_candidate_text(result)
    html    = _compose_body_candidate_html(result)

    pdf_bytes = _generate_pdf_bytes(result)
    username  = result.get("username") or "candidate"
    ts        = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_filename = f"EMIS_Result_{username}_{ts}.pdf"

    all_ok = True
    for to_email in candidate_list:
        print(f"[email_server] Sending candidate result to {to_email}")
        msg = _build_base_message(to_email, subject, text, html)
        msg.add_attachment(pdf_bytes, maintype="application", subtype="pdf", filename=pdf_filename)
        if not _smtp_send(msg):
            all_ok = False

    return all_ok


def send_result_emails(result: Dict) -> Dict[str, bool]:
    """
    Convenience wrapper to send both emails.
    Returns { "admin": bool, "candidate": bool }
    """
    # Ensure status is computed if missing
    result = {**result, "pass_fail": _compute_pass_fail(result)}
    admin_ok = send_admin_email(result)
    cand_ok  = send_candidate_email(result)
    return {"admin": admin_ok, "candidate": cand_ok}
