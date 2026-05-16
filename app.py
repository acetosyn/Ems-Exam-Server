# app.py
from flask import Flask, redirect, url_for, session
from dotenv import load_dotenv
import os

# ----------------------------
# BLUEPRINT IMPORTS
# ----------------------------
from modules.admin_routes import admin_bp
from modules.user_routes import user_bp
from modules.student_portal import student_portal_bp
from modules.api_routes import api_bp
from modules.document_routes import document_bp
from uploads import uploads_bp
from push import push_bp
from modules import student_results
from modules.notifications import notifications_bp
from modules.promotion_manager import promotion_bp


# Other system modules
import user_credentials

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "fallback_secret_key")

# ----------------------------
# REGISTER BLUEPRINTS
# ----------------------------
app.register_blueprint(admin_bp)
app.register_blueprint(user_bp)
app.register_blueprint(student_portal_bp)  # NEW STUDENT PORTAL MODULE
app.register_blueprint(api_bp)
app.register_blueprint(document_bp)
app.register_blueprint(uploads_bp)
app.register_blueprint(push_bp, url_prefix="/api")
app.register_blueprint(promotion_bp)
app.register_blueprint(notifications_bp, url_prefix="/api/notifications")



ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")


@app.route('/')
def home():
    return redirect(url_for("admin_bp.admin_login"))

if __name__ == '__main__':
    user_credentials.init_db()
    student_results.init_db()
    app.run(host='0.0.0.0', port=5005, debug=True)