# MODULE: EMIS Main Application — Initializes Flask, loads environment configuration,
# registers application blueprints and provides automatic static asset cache busting.

import os
from datetime import datetime, timezone

from flask import Flask, redirect, url_for as flask_url_for
from dotenv import load_dotenv

load_dotenv()


# ==========================================================
# CORE EMIS BLUEPRINTS
# ==========================================================

from modules.admin_routes import admin_bp
from modules.user_routes import user_bp
from modules.student_portal import student_portal_bp
from modules.api_routes import api_bp
from modules.document_routes import document_bp
from modules.notifications import notifications_bp
from modules.promotion_manager import promotion_bp
from modules.convert_routes import convert_bp
from modules.result_sync import sync_bp


# ==========================================================
# ACADEMIC MANAGEMENT BLUEPRINTS
# ==========================================================

from modules.attendance_manager import attendance_bp
from modules.ca_test_manager import ca_test_bp
from modules.report_sheet_manager import report_sheet_bp


# ==========================================================
# OTHER EMIS MODULES
# ==========================================================

from modules import student_results
from exam_document_export import exam_document_export_bp
from uploads import uploads_bp
from push import push_bp

import user_credentials


# ==========================================================
# FLASK APPLICATION
# ==========================================================

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "fallback_secret_key")


# ==========================================================
# STATIC ASSET CACHE BUSTING
# ==========================================================

ASSET_VERSION = os.getenv("ASSET_VERSION", "").strip() or datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def versioned_url_for(endpoint, **values):
    if (endpoint == "static" or endpoint.endswith(".static")) and "v" not in values: values["v"] = ASSET_VERSION
    return flask_url_for(endpoint, **values)


app.jinja_env.globals["url_for"] = versioned_url_for
app.jinja_env.globals["ASSET_VERSION"] = ASSET_VERSION


# ==========================================================
# STATIC FILE CACHE CONFIGURATION
# ==========================================================

app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0


# ==========================================================
# REGISTER CORE EMIS BLUEPRINTS
# ==========================================================

app.register_blueprint(admin_bp)
app.register_blueprint(user_bp)
app.register_blueprint(student_portal_bp)
app.register_blueprint(api_bp)
app.register_blueprint(document_bp)
app.register_blueprint(promotion_bp)
app.register_blueprint(convert_bp)
app.register_blueprint(sync_bp)


# ==========================================================
# REGISTER UPLOAD / EXAM BLUEPRINTS
# ==========================================================

app.register_blueprint(uploads_bp, url_prefix="/api")
app.register_blueprint(push_bp, url_prefix="/api")
app.register_blueprint(notifications_bp, url_prefix="/api/notifications")
app.register_blueprint(exam_document_export_bp, url_prefix="/api")


# ==========================================================
# REGISTER ACADEMIC MANAGEMENT BLUEPRINTS
# ==========================================================

app.register_blueprint(attendance_bp)
app.register_blueprint(ca_test_bp)
app.register_blueprint(report_sheet_bp)


# ==========================================================
# HOME
# ==========================================================

@app.route("/")
def home():
    return redirect(flask_url_for("admin_bp.admin_login"))


# ==========================================================
# ACADEMIC / SYNC ROUTE DEBUGGING
# ==========================================================

def print_academic_routes():
    prefixes = ("/api/attendance", "/api/ca-tests", "/api/report-sheets", "/api/sync")
    rules = sorted((rule for rule in app.url_map.iter_rules() if str(rule).startswith(prefixes)), key=lambda rule: str(rule))

    print("\n[EMIS] ACADEMIC + RESULT SYNC ROUTES")

    if not rules:
        print("[EMIS] WARNING: No academic-management or result-sync API routes were registered.")
        return

    for rule in rules:
        methods = sorted(method for method in rule.methods if method not in {"HEAD", "OPTIONS"})
        print(f"[EMIS] {','.join(methods):<12} {rule} -> {rule.endpoint}")

    print()


# ==========================================================
# APPLICATION STARTUP
# ==========================================================

if __name__ == "__main__":
    user_credentials.init_db()
    student_results.init_db()

    print(f"[EMIS] Static asset version: {ASSET_VERSION}")
    print("[EMIS] Attendance Manager: registered")
    print("[EMIS] CA/Test Manager: registered")
    print("[EMIS] Report Sheet Manager: registered")
    print("[EMIS] Result Sync Engine: registered")

    print_academic_routes()

    app.run(host="0.0.0.0", port=5005, debug=True)
