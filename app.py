# MODULE: EMIS Main Application
# Initializes Flask, loads environment configuration, registers EMIS blueprints,
# and enforces strict production-safe cache protection for HTML, JS, CSS,
# static assets and API responses.
#
# CACHE PROTECTION DESIGN:
#   1. Every Jinja url_for("static", ...) receives an automatic per-file version.
#   2. Version changes automatically whenever the physical static file changes.
#   3. Hardcoded /static/... src/href links inside rendered HTML are also upgraded.
#   4. HTML pages are never served from stale browser cache.
#   5. API responses are never served from stale browser/proxy cache.
#   6. JS/CSS are forced to revalidate and also receive unique version URLs.
#   7. Jinja templates auto-reload when HTML files change.
#
# IMPORTANT:
#   Python .py changes still require a Passenger / Flask restart.
#   Static JS/CSS/HTML changes no longer require manual ?v= edits.

import os
import re
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode, unquote

from flask import Flask, redirect, request, url_for as flask_url_for
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
from modules.result_sync import sync_bp, init_sync_db, trigger_background_sync, sender_enabled
from modules.academic_settings import get_academic_settings


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
# PATHS
# ==========================================================

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


# ==========================================================
# FLASK APPLICATION
# ==========================================================

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "fallback_secret_key")


# ==========================================================
# STRICT TEMPLATE / STATIC CONFIGURATION
# ==========================================================

# Never allow Flask to tell browsers to keep stale static resources
# for long periods.
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

# Ensure changed HTML/Jinja templates are detected without requiring
# a Python restart simply because a template file changed.
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.jinja_env.auto_reload = True


# ==========================================================
# GLOBAL DEPLOYMENT VERSION
# ==========================================================
#
# This is only a FALLBACK.
#
# Static files use their own filesystem modification timestamp + size.
# This means replacing admin_results.js changes ONLY that file's version
# without needing to manually change ASSET_VERSION.
#
# ASSET_VERSION may still be supplied through .env if desired.
# ==========================================================

STARTUP_VERSION = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
ASSET_VERSION = os.getenv("ASSET_VERSION", "").strip() or STARTUP_VERSION


# ==========================================================
# STATIC ENDPOINT / PATH HELPERS
# ==========================================================

def _static_root_for_endpoint(endpoint):
    """
    Resolve the physical static directory belonging to Flask's main
    static endpoint or a Blueprint static endpoint.

    Main app:
        static -> <project>/static

    Blueprint:
        blueprint_name.static -> blueprint's static directory
    """

    if endpoint == "static":
        try:
            return Path(app.static_folder).resolve()
        except Exception:
            return STATIC_DIR.resolve()

    if str(endpoint or "").endswith(".static"):
        blueprint_name = str(endpoint).rsplit(".", 1)[0]
        blueprint = app.blueprints.get(blueprint_name)

        if blueprint and blueprint.static_folder:
            try:
                static_path = Path(blueprint.static_folder)

                if not static_path.is_absolute():
                    static_path = Path(blueprint.root_path) / static_path

                return static_path.resolve()

            except Exception:
                pass

    return None


def _safe_asset_path(static_root, filename):
    """
    Resolve a static filename safely and prevent ../ traversal outside
    the configured static directory.
    """

    if not static_root:
        return None

    filename = str(filename or "").strip().replace("\\", "/").lstrip("/")

    if not filename:
        return None

    try:
        root = Path(static_root).resolve()
        candidate = (root / filename).resolve()
        candidate.relative_to(root)

        return candidate

    except Exception:
        return None


# ==========================================================
# PER-FILE STATIC VERSIONING
# ==========================================================

def static_asset_version(filename, endpoint="static"):
    """
    Generate a version tied directly to the physical file.

    Example:
        /static/js/admin_results.js
            ↓
        /static/js/admin_results.js?v=20260916143821-178958...
    
    When that file is replaced on cPanel, its mtime/size changes,
    therefore the URL changes automatically.

    No template version editing is required.
    """

    static_root = _static_root_for_endpoint(endpoint)
    asset_path = _safe_asset_path(static_root, filename)

    if asset_path:
        try:
            stat = asset_path.stat()

            # nanosecond mtime gives us much finer protection than
            # ordinary second-resolution modification timestamps.
            modification = int(stat.st_mtime_ns)
            size = int(stat.st_size)

            return f"{ASSET_VERSION}-{modification}-{size}"

        except OSError:
            pass

    # File missing/unavailable:
    # still return a deployment-specific fallback instead of producing
    # an unversioned URL.
    return ASSET_VERSION


# ==========================================================
# GLOBAL VERSIONED URL_FOR
# ==========================================================

def versioned_url_for(endpoint, **values):
    """
    Global replacement for Jinja's url_for.

    ALL normal template calls such as:

        {{ url_for('static', filename='js/admin_results.js') }}

    automatically become versioned.

    Even if an old template manually supplies ?v=123, this function
    deliberately replaces it with the authoritative current version.
    """

    endpoint = str(endpoint or "")

    if endpoint == "static" or endpoint.endswith(".static"):
        filename = str(values.get("filename") or "").strip()

        if filename:
            values["v"] = static_asset_version(filename, endpoint)

        else:
            values["v"] = ASSET_VERSION

    return flask_url_for(endpoint, **values)


# Replace url_for globally inside every Jinja template.
app.jinja_env.globals["url_for"] = versioned_url_for

# Still expose these helpers in case any template/module needs them.
app.jinja_env.globals["ASSET_VERSION"] = ASSET_VERSION
app.jinja_env.globals["static_asset_version"] = static_asset_version


# ==========================================================
# GLOBAL ACADEMIC CONTEXT
# ==========================================================

@app.context_processor
def inject_global_academic_context():
    """Expose the persistent academic year/session/term to every Jinja page."""
    try:
        academic_context = get_academic_settings()
    except Exception as error:
        print("[EMIS ACADEMIC SETTINGS] Template context warning:", error)
        academic_context = {}

    return {"global_academic_context": academic_context}


# ==========================================================
# HARDCODED STATIC LINK PROTECTION
# ==========================================================
#
# Some old EMIS templates may contain:
#
#     <script src="/static/js/file.js"></script>
#
# instead of:
#
#     {{ url_for('static', filename='js/file.js') }}
#
# Those links normally bypass our Jinja url_for override.
#
# To safeguard old pages too, every rendered HTML response is scanned
# and same-origin /static/... src/href/poster URLs are automatically
# upgraded with the current physical file version.
#
# Therefore you do NOT have to manually search every HTML file.
# ==========================================================

STATIC_HTML_ATTRIBUTE_RE = re.compile(
    r'(?P<prefix>\b(?:src|href|poster)\s*=\s*["\'])'
    r'(?P<url>[^"\']*?/static/[^"\']+)'
    r'(?P<suffix>["\'])',
    flags=re.IGNORECASE,
)


def _version_static_url(raw_url):
    raw_url = str(raw_url or "").strip()

    if not raw_url:
        return raw_url

    try:
        parts = urlsplit(raw_url)

        # Never modify somebody else's external static URL.
        if parts.netloc and parts.netloc.lower() != request.host.lower():
            return raw_url

        path = parts.path or ""
        marker = "/static/"

        marker_index = path.find(marker)

        if marker_index < 0:
            return raw_url

        filename = unquote(path[marker_index + len(marker):]).strip()

        if not filename:
            return raw_url

        current_version = static_asset_version(filename, "static")

        query_items = [
            (key, value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if key.lower() != "v"
        ]

        query_items.append(("v", current_version))

        return urlunsplit((
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(query_items),
            parts.fragment,
        ))

    except Exception:
        # Never break an HTML page merely because one URL cannot be parsed.
        return raw_url


def rewrite_static_urls_in_html(html):
    """
    Automatically version hardcoded static src/href/poster references.
    """

    if not html or "/static/" not in html:
        return html

    def replace(match):
        return (
            match.group("prefix")
            + _version_static_url(match.group("url"))
            + match.group("suffix")
        )

    return STATIC_HTML_ATTRIBUTE_RE.sub(replace, html)


# ==========================================================
# CACHE HEADER HELPERS
# ==========================================================

def _set_no_store_headers(response):
    """
    Strict protection used for HTML and API responses.
    """

    response.headers["Cache-Control"] = (
        "no-store, no-cache, must-revalidate, max-age=0, private"
    )
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

    # Helps protect against reverse-proxy / intermediary caching.
    response.headers["Surrogate-Control"] = "no-store"

    return response


def _set_static_revalidation_headers(response):
    """
    Static resources may be stored temporarily by a browser but MUST
    revalidate before reuse.

    Combined with unique per-file ?v= versions this prevents old JS/CSS
    from surviving deployments while avoiding unnecessarily aggressive
    handling of large images/fonts.
    """

    response.headers["Cache-Control"] = (
        "no-cache, must-revalidate, max-age=0"
    )
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

    return response


def _set_code_asset_headers(response):
    """
    JavaScript and CSS contain executable/application logic.
    Be stricter with these than images/fonts.

    Browser must not retain an obsolete JS/CSS implementation.
    """

    response.headers["Cache-Control"] = (
        "no-store, no-cache, must-revalidate, max-age=0"
    )
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    response.headers["Surrogate-Control"] = "no-store"

    return response


# ==========================================================
# GLOBAL RESPONSE CACHE POLICY
# ==========================================================

@app.after_request
def apply_emis_cache_policy(response):
    """
    Central cache policy for the entire EMIS application.

    HTML:
        Never trust a stale browser copy.
        Also rewrite hardcoded static URLs before sending.

    API:
        Never cache student/result/attendance/CA/report/sync data.

    JS/CSS:
        Strict no-store protection + automatic unique URL version.

    Other static assets:
        Revalidate before reuse.
    """

    try:
        request_path = str(request.path or "")
        mimetype = str(response.mimetype or "").lower()

        # ------------------------------------------------------
        # HTML PAGES
        # ------------------------------------------------------

        if mimetype == "text/html":
            if response.status_code == 200 and not response.direct_passthrough:
                try:
                    html = response.get_data(as_text=True)
                    rewritten = rewrite_static_urls_in_html(html)

                    if rewritten != html:
                        response.set_data(rewritten)

                except Exception as error:
                    print("[EMIS CACHE] HTML static URL rewrite warning:", error)

            _set_no_store_headers(response)

            # Staff/student pages depend heavily on session state.
            existing_vary = response.headers.get("Vary", "")

            if "cookie" not in existing_vary.lower():
                response.headers["Vary"] = (
                    f"{existing_vary}, Cookie".strip(", ")
                    if existing_vary
                    else "Cookie"
                )

            return response

        # ------------------------------------------------------
        # API RESPONSES
        # ------------------------------------------------------

        if request_path.startswith("/api/"):
            _set_no_store_headers(response)
            return response

        # ------------------------------------------------------
        # STATIC ASSETS
        # ------------------------------------------------------

        if request_path.startswith("/static/"):
            extension = Path(request_path).suffix.lower()

            # Application code must always be treated most strictly.
            if extension in {".js", ".css", ".mjs"}:
                _set_code_asset_headers(response)

            else:
                _set_static_revalidation_headers(response)

            return response

    except Exception as error:
        # Cache protection must never crash a genuine EMIS response.
        print("[EMIS CACHE] Response policy warning:", error)

    return response


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
# SYNC WORKER BOOTSTRAP
# ==========================================================

_SYNC_WORKER_BOOTSTRAPPED = False


@app.before_request
def ensure_local_sync_worker():
    """Start/resume the durable Local -> Cloud sync worker on first request.

    This is important under Passenger/WSGI because the __main__ startup block is
    not executed there. Deployed/cloud instances normally have sender disabled,
    so this becomes a harmless one-time database initialization on those hosts.
    """
    global _SYNC_WORKER_BOOTSTRAPPED

    if _SYNC_WORKER_BOOTSTRAPPED:
        return None

    try:
        init_sync_db()
        if sender_enabled():
            trigger_background_sync()
        _SYNC_WORKER_BOOTSTRAPPED = True
    except Exception as error:
        # Never block a user request because the background sync worker failed
        # to initialize. The next request will retry initialization.
        print("[EMIS SYNC] Worker bootstrap warning:", error)

    return None


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
    prefixes = (
        "/api/academic-settings",
        "/api/attendance",
        "/api/ca-tests",
        "/api/report-sheets",
        "/api/sync",
    )

    rules = sorted(
        (
            rule
            for rule in app.url_map.iter_rules()
            if str(rule).startswith(prefixes)
        ),
        key=lambda rule: str(rule),
    )

    print("\n[EMIS] ACADEMIC + RESULT SYNC ROUTES")

    if not rules:
        print(
            "[EMIS] WARNING: No academic-management or "
            "result-sync API routes were registered."
        )
        return

    for rule in rules:
        methods = sorted(
            method
            for method in rule.methods
            if method not in {"HEAD", "OPTIONS"}
        )

        print(
            f"[EMIS] {','.join(methods):<12} "
            f"{rule} -> {rule.endpoint}"
        )

    print()


# ==========================================================
# CACHE CONFIGURATION DEBUG
# ==========================================================

def print_cache_configuration():
    print("\n[EMIS] CACHE PROTECTION")
    print(f"[EMIS] Deployment fallback version : {ASSET_VERSION}")
    print(f"[EMIS] Static directory            : {STATIC_DIR}")
    print("[EMIS] Per-file static versioning  : ENABLED")
    print("[EMIS] Hardcoded HTML URL rewrite  : ENABLED")
    print("[EMIS] HTML no-store protection    : ENABLED")
    print("[EMIS] API no-store protection     : ENABLED")
    print("[EMIS] JS/CSS strict protection    : ENABLED")
    print("[EMIS] Template auto reload        : ENABLED")
    print()


# ==========================================================
# APPLICATION STARTUP
# ==========================================================

if __name__ == "__main__":
    user_credentials.init_db()
    student_results.init_db()

    print_cache_configuration()

    print("[EMIS] Attendance Manager: registered")
    print("[EMIS] CA/Test Manager: registered")
    print("[EMIS] Report Sheet Manager: registered")
    print("[EMIS] Offline-First Sync Engine: registered")

    print_academic_routes()

    app.run(
        host="0.0.0.0",
        port=5005,
        debug=True,
    )