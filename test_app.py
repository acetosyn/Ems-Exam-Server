from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory
from dotenv import load_dotenv
import os
import user_credentials  # credential generator / DB handler
import engine            # file upload handler
import mimetypes
import user_exam   # new module for exam results
import email_server 
from datetime import datetime
from threading import Thread
# Load environment variables
from pathlib import Path
import csv
from uploads import upload_bp



# Define logs directory
BASE_DIR = Path(__file__).resolve().parent
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)  # create folder if missing

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "fallback_secret_key")
app.register_blueprint(upload_bp)

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")



def _send_emails_async(result_payload: dict):
    """Fire-and-forget email sending so the HTTP response is snappy."""
    try:
        status = email_server.send_result_emails(result_payload)
        app.logger.info(f"[email] send_result_emails -> {status}")
    except Exception as e:
        app.logger.exception(f"[email] send_result_emails failed: {e}")


@app.route('/')
def home():
    """Landing page redirects to admin login by default."""
    return redirect(url_for('admin_login'))


# -------------------- ADMIN LOGIN --------------------
@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session.clear()
            session['user_type'] = 'admin'
            session['username'] = username
            return redirect(url_for('admin_dashboard'))
        else:
            return render_template('admin_login.html', error="Invalid credentials")

    return render_template('admin_login.html')


# -------------------- USER LOGIN --------------------
@app.route('/user_login', methods=['GET', 'POST'])
def user_login():
    # Admin opens this page for candidates (public page)
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip()
        gender = request.form.get('gender', '').strip()
        subject = request.form.get('subject', '').strip()   # <-- NEW
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        # Validate against generated + issued accounts
        if user_credentials.validate_credentials(username, password):
            session.clear()
            session['user_type'] = 'user'
            session['username'] = username
            session['full_name'] = full_name
            session['email'] = email
            session['gender'] = gender
            session['subject'] = subject                   # <-- NEW
            session['exam_started'] = False
            session['exam_submitted'] = False
            return redirect(url_for('user_portal'))

        return render_template('user_login.html', error="Invalid login details")

    return render_template('user_login.html')


# -------------------- ADMIN DASHBOARD --------------------
@app.route('/admin')
def admin_dashboard():
    if session.get('user_type') != 'admin':
        return redirect(url_for('admin_login'))
    return render_template('dashboard.html')


# -------------------- ADMIN SUB-PAGES --------------------

@app.route('/admin/dashboard')
def admin_dashboard_page():
    if session.get('user_type') != 'admin':
        return redirect(url_for('admin_login'))
    return render_template('dashboard.html')


@app.route('/admin/teachers')
def admin_teachers():
    if session.get('user_type') != 'admin':
        return redirect(url_for('admin_login'))
    return render_template('teachers.html')


@app.route('/admin/students')
def admin_students():
    if session.get('user_type') != 'admin':
        return redirect(url_for('admin_login'))
    return render_template('students.html')


@app.route('/admin/ids')
def admin_ids():
    if session.get('user_type') != 'admin':
        return redirect(url_for('admin_login'))
    return render_template('ids.html')


@app.route('/admin/past_questions')
def admin_past_questions():
    if session.get('user_type') != 'admin':
        return redirect(url_for('admin_login'))
    return render_template('past_questions.html')


@app.route('/admin/mock_exam')
def admin_mock_exam():
    if session.get('user_type') != 'admin':
        return redirect(url_for('admin_login'))
    return render_template('mock_exam.html')


@app.route('/admin/results')
def admin_results():
    if session.get('user_type') != 'admin':
        return redirect(url_for('admin_login'))
    return render_template('result.html')


@app.route('/admin/third_party')
def admin_third_party():
    if session.get('user_type') != 'admin':
        return redirect(url_for('admin_login'))
    return render_template('third_party.html')


@app.route('/admin/activities')
def admin_activities():
    if session.get('user_type') != 'admin':
        return redirect(url_for('admin_login'))
    return render_template('activities.html')


@app.route('/admin/settings')
def admin_settings():
    if session.get('user_type') != 'admin':
        return redirect(url_for('admin_login'))
    return render_template('settings.html')


@app.route('/admin/support')
def admin_support():
    if session.get('user_type') != 'admin':
        return redirect(url_for('admin_login'))
    return render_template('support.html')

# -------------------- TEACHER TOOL SUB-PAGES (Dynamic Loading) --------------------

@app.route('/admin/uploads')
def admin_uploads():
    if session.get('user_type') != 'admin':
        return redirect(url_for('admin_login'))
    return render_template('uploads.html')


@app.route('/admin/exam_dashboard')
def admin_exam_dashboard():
    if session.get('user_type') != 'admin':
        return redirect(url_for('admin_login'))
    return render_template('dashboard.html')


@app.route('/admin/dash_results')
def admin_dash_results():
    if session.get('user_type') != 'admin':
        return redirect(url_for('admin_login'))
    return render_template('dash_results.html')


@app.route('/admin/reports')
def admin_reports():
    if session.get('user_type') != 'admin':
        return redirect(url_for('admin_login'))
    return render_template('reports.html')


@app.route('/admin/analytics')
def admin_analytics():
    if session.get('user_type') != 'admin':
        return redirect(url_for('admin_login'))
    return render_template('analytics.html')


@app.route('/admin/resources')
def admin_resources():
    if session.get('user_type') != 'admin':
        return redirect(url_for('admin_login'))
    return render_template('resources.html')




# -------------------- USER PORTAL (Dashboard-first) --------------------
@app.route('/user_portal')
def user_portal():
    if session.get('user_type') != 'user':
        return redirect(url_for('user_login'))

    return render_template(
        'user_portal.html',
        full_name=session.get('full_name'),
        username=session.get('username'),
        email=session.get('email'),
        gender=session.get('gender'),
        subject=session.get('subject'),        # <-- NEW
        exam_started=session.get('exam_started', False),
        exam_submitted=session.get('exam_submitted', False)
    )


# -------------------- START EXAM (sets flag, then go to /exam) --------------------
@app.route('/start_exam', methods=['POST'])
def start_exam():
    if session.get('user_type') != 'user':
        return redirect(url_for('user_login'))

    # Gate: only allow if not already submitted
    if session.get('exam_submitted'):
        return redirect(url_for('result'))

    session['exam_started'] = True
    return redirect(url_for('exam'))


# -------------------- EXAM PAGE --------------------
@app.route('/exam')
def exam():
    if session.get('user_type') != 'user':
        return redirect(url_for('user_login'))

    # Always render exam.html
    return render_template(
        'exam.html',
        full_name=session.get('full_name'),
        username=session.get('username'),
        subject=session.get('subject'),   # ✅ inject subject here
        exam_started=session.get('exam_started', False)
    )


# -------------------- SUBMIT / END EXAM --------------------
@app.route('/submit_exam', methods=['POST'])
def submit_exam():
    if session.get('user_type') != 'user':
        return redirect(url_for('user_login'))

    # Mark submitted, clear started flag
    session['exam_submitted'] = True
    session['exam_started'] = False
    return redirect(url_for('result'))


# -------------------- RESULT PAGE --------------------
@app.route('/result')
def result():
    if session.get('user_type') != 'user':
        return redirect(url_for('user_login'))

    username = session.get('username')
    latest = user_exam.get_user_latest_result(username)

    return render_template(
        'result.html',
        full_name=session.get('full_name'),
        username=username,
        result=latest or {}
    )

# -------------------- API: Generate Credentials --------------------
@app.route('/generate_credentials', methods=['POST'])
def generate_credentials_route():
    if session.get('user_type') != 'admin':
        return jsonify({"error": "Unauthorized"}), 403

    count = int(request.form.get("count", 1))
    prefix = request.form.get("prefix", "candidate")
    pwd_length = int(request.form.get("pwd_length", 8))
    result = user_credentials.generate_credentials(count, prefix, pwd_length)
    return jsonify(result)


# -------------------- API: List Credentials --------------------
@app.route('/list_credentials')
def list_credentials():
    if session.get('user_type') != 'admin':
        return jsonify({"error": "Unauthorized"}), 403
    return jsonify(user_credentials.get_credentials())


# -------------------- API: Mark Issued --------------------
@app.route('/mark_issued', methods=['POST'])
def mark_issued():
    if session.get('user_type') != 'admin':
        return jsonify({"error": "Unauthorized"}), 403

    usernames = request.json.get("usernames", [])
    ok = user_credentials.mark_issued(usernames)
    return jsonify({"success": ok})


# -------------------- LOGOUT --------------------
# -------------------- LOGOUT --------------------
@app.route('/logout')
def logout():
    # capture user type before clearing the session
    user_type = session.get('user_type')
    session.clear()

    # send candidates back to candidate login; admins to admin login
    if user_type == 'user':
        return redirect(url_for('user_login'))
    return redirect(url_for('admin_login'))



# -------------------- API: Document Upload --------------------
@app.route('/upload_document', methods=['POST'])
def upload_document():
    if session.get('user_type') != 'admin':
        return jsonify({"error": "Unauthorized"}), 403

    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    result = engine.save_uploaded_file(file)
    if result["success"]:
        return jsonify({
            "message": "File uploaded successfully",
            "filename": result["filename"],
            "path": result["path"]
        })
    else:
        return jsonify({"error": result["error"]}), 400


# -------------------- API: List/Search Documents --------------------
@app.route('/documents')
def list_documents_route():
    if session.get('user_type') != 'admin':
        return jsonify({"error": "Unauthorized"}), 403
    q = request.args.get("q", "", type=str)
    docs = engine.list_documents(q)
    # attach URLs for frontend
    for d in docs:
        d["url"] = url_for('serve_upload', filename=d["name"])
    return jsonify({"documents": docs})


# -------------------- Serve uploaded files inline --------------------
@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    if session.get('user_type') != 'admin':
        return jsonify({"error": "Unauthorized"}), 403
    
    file_path = os.path.join(engine.UPLOAD_FOLDER, filename)
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404

    # guess mime type (important for inline preview)
    mime, _ = mimetypes.guess_type(file_path)
    mime = mime or "application/octet-stream"

    # force Content-Disposition:inline so browser tries preview, not download
    resp = send_from_directory(engine.UPLOAD_FOLDER, filename, as_attachment=False, mimetype=mime)
    resp.headers["Content-Disposition"] = f'inline; filename="{filename}"'
    return resp



# -------------------- API: Exam Submission (Realtime) --------------------
# -------------------- API: Exam Submission (Realtime) --------------------
@app.route('/api/exam/submit', methods=['POST'])
def api_exam_submit():
    if session.get('user_type') != 'user':
        return jsonify({"error": "Unauthorized"}), 403

    data = request.json or {}
    username = session.get("username")
    fullname = session.get("full_name")
    subject  = session.get("subject")
    email    = session.get("email")

    # Extract score data from JS payload
    score        = data.get("score", 0)          # percentage
    correct      = data.get("correct", 0)
    total        = data.get("total", 0)
    answered     = data.get("answered", 0)
    time_taken   = data.get("timeTaken", 0)
    submitted_at = data.get("submittedAt") or datetime.utcnow().isoformat()
    status       = data.get("status", "completed")  # completed | timeout | disqualified, etc.

    # Save result into DB with status
    user_exam.save_exam_result(
        username=username,
        fullname=fullname,
        email=email,
        subject=subject,
        score=score,
        correct=correct,
        total=total,
        answered=answered,
        time_taken=time_taken,
        submitted_at=submitted_at,
        status=status
    )

    # Prepare payload for email_server
    result_payload = {
        "username": username,
        "fullname": fullname,
        "email": email,            # candidate email (may be blank)
        "subject": subject,
        "score": score,            # percent
        "correct": correct,
        "total": total,
        "answered": answered,
        "time_taken": time_taken,
        "submitted_at": submitted_at,
        "status": status
    }

    # Send emails in the background (admin + candidate)
    Thread(target=_send_emails_async, args=(result_payload,), daemon=True).start()

    # Mark session flags
    session['exam_submitted'] = True
    session['exam_started'] = False

    return jsonify({"success": True, "message": f"Exam result recorded ({status})"})



# ============================================================
# ✅ Unified Results & Credentials APIs (Dynamic + Delete + Filters)
# ============================================================

# -------------------- API: Get All Exam Results (for Admin Dashboard) --------------------
@app.route('/api/exam/results')
def api_exam_results():
    """Return filtered exam results from DB (supports subject/date filters)."""
    if session.get('user_type') != 'admin':
        return jsonify({"error": "Unauthorized"}), 403

    subject = request.args.get("subject")
    from_date = request.args.get("from")
    to_date = request.args.get("to")

    try:
        results = user_exam.get_exam_results() or []

        # Apply filters if present
        if subject and subject.lower() != "all":
            results = [r for r in results if (r.get("subject") or "").lower() == subject.lower()]

        def parse_date(d):
            try:
                return datetime.fromisoformat(d.replace("Z", ""))
            except:
                return None

        if from_date:
            from_dt = parse_date(from_date)
            results = [r for r in results if parse_date(r.get("submitted_at")) and parse_date(r["submitted_at"]) >= from_dt]
        if to_date:
            to_dt = parse_date(to_date)
            results = [r for r in results if parse_date(r.get("submitted_at")) and parse_date(r["submitted_at"]) <= to_dt]

        results.sort(key=lambda r: r.get("submitted_at", ""), reverse=True)
        return jsonify({"results": results})

    except Exception as e:
        print(f"⚠️ Error fetching results from DB: {e}")
        return jsonify({"results": []})


# -------------------- DELETE SINGLE RESULT --------------------
@app.route("/delete_result", methods=["POST"])
def delete_result():
    """Delete a specific result permanently (from DB and CSV)."""
    if session.get("user_type") != "admin":
        return jsonify({"error": "Unauthorized"}), 403

    data = request.json or {}
    username = data.get("username")
    if not username:
        return jsonify({"error": "Username required"}), 400

    try:
        ok = user_exam.delete_result(username)
        if ok:
            print(f"✅ Deleted result for {username}")
            return jsonify({"success": True, "message": f"Deleted result for {username}"})
        else:
            return jsonify({"success": False, "message": "Result not found"})
    except Exception as e:
        print(f"⚠️ Delete result error: {e}")
        return jsonify({"success": False, "message": str(e)})


# -------------------- CLEAR RESULTS (ALL / SUBJECT / DATE RANGE) --------------------
@app.route("/clear_results", methods=["POST"])
def clear_results():
    """Delete all results or filter by subject/date."""
    if session.get("user_type") != "admin":
        return jsonify({"error": "Unauthorized"}), 403

    data = request.json or {}
    subject = data.get("subject")
    from_date = data.get("from")
    to_date = data.get("to")

    try:
        count = user_exam.clear_results(subject=subject, from_date=from_date, to_date=to_date)
        return jsonify({"success": True, "deleted": count})
    except Exception as e:
        print(f"⚠️ Clear results error: {e}")
        return jsonify({"success": False, "message": str(e)})


# -------------------- VIEW CREDENTIALS --------------------
@app.route("/view_credentials")
def view_credentials():
    """Load latest credentials_YYYY-MM-DD.csv from logs folder safely."""
    files = sorted(LOGS_DIR.glob("credentials_*.csv"), reverse=True)
    if not files:
        return jsonify({"credentials": []})
    latest = files[0]
    creds = []
    try:
        with open(latest, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                creds.append({
                    "username": row.get("username", "").strip(),
                    "password": row.get("password", "").strip()
                })
    except Exception as e:
        print(f"⚠️ Error reading credentials file: {e}")
    return jsonify({"credentials": creds})


# -------------------- VIEW RESULTS (Dynamic DB First, CSV Fallback) --------------------
# -------------------- VIEW RESULTS (Dynamic DB First, CSV Fallback) --------------------
@app.route("/view_results")
def view_results():
    """Load live results (DB first) and fallback to CSV logs if none."""
    if session.get('user_type') != 'admin':
        return jsonify({"error": "Unauthorized"}), 403

    results = []
    try:
        results = user_exam.get_exam_results() or []
    except Exception as e:
        print(f"⚠️ DB fetch failed: {e}")

    # ✅ If DB empty, fallback to CSV logs
    if not results:
        files = sorted(LOGS_DIR.glob("exam_results_*.csv"), reverse=True)
        for file in files:
            try:
                with open(file, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        cleaned = {k.strip(): (v or "").strip() for k, v in row.items()}
                        results.append(cleaned)
            except Exception as e:
                print(f"⚠️ Error reading {file.name}: {e}")

    # Sort by submission time (latest first)
    results.sort(key=lambda r: r.get("submitted_at", ""), reverse=True)
    return jsonify({"results": results})


@app.route("/debug/email_test")
def debug_email_test():
    from email_server import send_test_email
    ok = send_test_email()
    return {"sent": ok}


if __name__ == '__main__':
    user_credentials.init_db()
    user_exam.init_db()   # ensure exam_results table exists
    app.run(host='0.0.0.0', port=5000, debug=True)



