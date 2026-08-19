# ============================================================
# app.py — EMIS MAIN APPLICATION
# ============================================================

from flask import Flask, redirect, url_for
from dotenv import load_dotenv
import os


# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()


# ============================================================
# BLUEPRINT IMPORTS
# ============================================================

from modules.admin_routes import admin_bp
from modules.user_routes import user_bp
from modules.student_portal import student_portal_bp
from modules.api_routes import api_bp
from modules.document_routes import document_bp
from modules.notifications import notifications_bp
from modules.promotion_manager import promotion_bp
from modules.convert_routes import convert_bp

from uploads import uploads_bp
from push import push_bp

from modules import student_results

import user_credentials


# ============================================================
# FLASK APP
# ============================================================

app = Flask(__name__)

app.secret_key = os.getenv("SECRET_KEY", "fallback_secret_key")


# ============================================================
# REGISTER BLUEPRINTS
# ============================================================

app.register_blueprint(admin_bp)

app.register_blueprint(user_bp)

app.register_blueprint(student_portal_bp)

app.register_blueprint(api_bp)

app.register_blueprint(document_bp)

# ------------------------------------------------------------
# Upload JSON Library API
#
# uploads.py defines:
#   /uploads/<year>
#   /uploads/<year>/<filename>
#   /uploads/<year>/delete/<filename>
#
# With url_prefix="/api", these become:
#   /api/uploads/<year>
#   /api/uploads/<year>/<filename>
#   /api/uploads/<year>/delete/<filename>
# ------------------------------------------------------------

app.register_blueprint(uploads_bp, url_prefix="/api")

# ------------------------------------------------------------
# Portal Push API
# ------------------------------------------------------------

app.register_blueprint(push_bp, url_prefix="/api")

# ------------------------------------------------------------
# Promotion
# ------------------------------------------------------------

app.register_blueprint(promotion_bp)

# ------------------------------------------------------------
# Notifications
# ------------------------------------------------------------

app.register_blueprint(notifications_bp, url_prefix="/api/notifications")

# ------------------------------------------------------------
# Conversion
# ------------------------------------------------------------

app.register_blueprint(convert_bp)


# ============================================================
# ENVIRONMENT ADMIN CREDENTIALS
# ============================================================

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():
    return redirect(url_for("admin_bp.admin_login"))


# ============================================================
# OPTIONAL ROUTE DEBUGGING
#
# Useful while fixing route conflicts.
# You can remove this later if you want.
# ============================================================

# def print_registered_routes():
#     print("\n" + "=" * 100)
#     print("EMIS REGISTERED FLASK ROUTES")
#     print("=" * 100)

#     rules = sorted(app.url_map.iter_rules(), key=lambda rule: rule.rule)

#     for rule in rules:
#         methods = ",".join(sorted(method for method in rule.methods if method not in {"HEAD", "OPTIONS"}))
#         print(f"{methods:<15} {rule.rule:<60} -> {rule.endpoint}")

#     print("=" * 100 + "\n")


# ============================================================
# APPLICATION START
# ============================================================

if __name__ == "__main__":
    user_credentials.init_db()
    student_results.init_db()

    # print_registered_routes()

    app.run(host="0.0.0.0", port=5005, debug=True)