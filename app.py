# MODULE: EMIS Main Application — Initializes Flask, loads environment configuration,
# registers application blueprints and provides automatic static asset cache busting.

import os
from datetime import datetime, timezone

from flask import Flask, redirect, url_for as flask_url_for
from dotenv import load_dotenv

load_dotenv()

from modules.admin_routes import admin_bp
from modules.user_routes import user_bp
from modules.student_portal import student_portal_bp
from modules.api_routes import api_bp
from modules.document_routes import document_bp
from modules.notifications import notifications_bp
from modules.promotion_manager import promotion_bp
from modules.convert_routes import convert_bp
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
#
# Every app restart generates a new asset version automatically.
#
# Existing template code such as:
#
#   {{ url_for('static', filename='css/admin1.css') }}
#
# automatically becomes:
#
#   /static/css/admin1.css?v=20260913081530
#
# This prevents browsers / LiteSpeed from serving old CSS or JS
# after a new deployment.
# ==========================================================

ASSET_VERSION = os.getenv("ASSET_VERSION", "").strip() or datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def versioned_url_for(endpoint, **values):
    if (endpoint == "static" or endpoint.endswith(".static")) and "v" not in values:
        values["v"] = ASSET_VERSION

    return flask_url_for(endpoint, **values)


# Replace Jinja's normal url_for with the cache-busting wrapper.
# Non-static routes continue behaving normally.
app.jinja_env.globals["url_for"] = versioned_url_for

# Also expose the version directly in case a template ever needs it.
app.jinja_env.globals["ASSET_VERSION"] = ASSET_VERSION


# ==========================================================
# STATIC FILE CACHE CONFIGURATION
# ==========================================================

# Query-string versioning above is the main cache-busting mechanism.
# Setting max-age to zero also encourages browsers/proxies to revalidate
# static files instead of blindly holding old versions.
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0


# ==========================================================
# REGISTER APPLICATION BLUEPRINTS
# ==========================================================

app.register_blueprint(admin_bp)
app.register_blueprint(user_bp)
app.register_blueprint(student_portal_bp)
app.register_blueprint(api_bp)
app.register_blueprint(document_bp)
app.register_blueprint(uploads_bp, url_prefix="/api")
app.register_blueprint(push_bp, url_prefix="/api")
app.register_blueprint(promotion_bp)
app.register_blueprint(notifications_bp, url_prefix="/api/notifications")
app.register_blueprint(convert_bp)
app.register_blueprint(exam_document_export_bp, url_prefix="/api")


# ==========================================================
# HOME
# ==========================================================

@app.route("/")
def home():
    return redirect(flask_url_for("admin_bp.admin_login"))


# ==========================================================
# APPLICATION STARTUP
# ==========================================================

if __name__ == "__main__":
    user_credentials.init_db()
    student_results.init_db()

    print(f"[EMIS] Static asset version: {ASSET_VERSION}")

    app.run(host="0.0.0.0", port=5005, debug=True)