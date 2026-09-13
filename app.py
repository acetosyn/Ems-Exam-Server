# MODULE: EMIS Main Application — Initializes Flask, loads environment configuration and registers application blueprints

import os

from flask import Flask, redirect, url_for
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


app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "fallback_secret_key")


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
    return redirect(url_for("admin_bp.admin_login"))



# # ==========================================================
# # TEMPORARY CHEMISTRY IMAGE TEST
# # ==========================================================
# @app.route("/test-chemistry-image")
# def test_chemistry_image():
#     return """
#     <!DOCTYPE html>
#     <html>
#     <head>
#         <title>Chemistry Diagram Test</title>
#     </head>
#     <body style="padding:40px;font-family:Arial,sans-serif;">
#         <h2>Chemistry Diagram Test</h2>

#         <h3>Essay 5A</h3>
#         <img
#             src="/static/uploads/diagrams/2021/chemistry_ss1/essay_5a.PNG"
#             style="display:block;max-width:900px;width:100%;border:2px solid red;margin-bottom:40px;"
#         >

#         <h3>Essay 5B</h3>
#         <img
#             src="/static/uploads/diagrams/2021/chemistry_ss1/essay_5b.PNG"
#             style="display:block;max-width:900px;width:100%;border:2px solid blue;"
#         >
#     </body>
#     </html>
#     """

# ==========================================================
# APPLICATION STARTUP
# ==========================================================
if __name__ == "__main__":
    user_credentials.init_db()
    student_results.init_db()
    app.run(host="0.0.0.0", port=5005, debug=True)