import logging
import sys

# Configure basic logging early to handle import errors (stdout: Render shows stdout in the dashboard)
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

import re
import secrets  # Added for CSP nonce generation

import os
from datetime import timedelta

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Debug: Check if .env was loaded successfully
logger.info(f".env file loaded: GEMINI_API_KEY present = {'Yes' if os.getenv('GEMINI_API_KEY') else 'No'}")

# The app logger is named 'app' explicitly. Production logs to stdout only; development adds logs/mindful_horizon.log.
from utils.log_config import setup_app_logging, APP_LOGGER
logger = setup_app_logging()

from flask import Flask, request, redirect, url_for, flash, session
from flask_wtf.csrf import CSRFError
from flask_socketio import SocketIO
from flask_assets import Environment, Bundle
# Import blueprints from routes package
from routes import all_blueprints
from ai.scoring import band_for, canonical_type

from extensions import db, csrf, limiter, cache
import utils.cache_utils  # noqa: F401  (registers the cache-invalidation session listeners)

# Database configuration
app = Flask(__name__)

app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max request size (voice logs are analysed in memory, never saved)

from utils.database_utils import normalize_db_url, engine_options

basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'instance', 'mindful_horizon.db')
app.config['SQLALCHEMY_DATABASE_URI'] = normalize_db_url(os.environ.get('DATABASE_URL')) or f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# Pool settings differ per dialect (SQLite vs PostgreSQL); see utils/database_utils.py and docs/PERFORMANCE.md
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = engine_options(app.config['SQLALCHEMY_DATABASE_URI'])


# Same-origin only unless CORS_ORIGINS (comma separated) is set.
_cors = os.getenv('CORS_ORIGINS')
socketio = SocketIO(app, cors_allowed_origins=[o.strip() for o in _cors.split(',')] if _cors else None)

# Rate limiter (see extensions.py for the limits)
limiter.init_app(app)  # defined in extensions.py so blueprints can add per-route limits
from utils.proxy import init_proxy  # ProxyFix behind Render's proxy (production or TRUST_PROXY=1)
init_proxy(app)

# Rate limiting exemption for health checks and static files
@limiter.request_filter
def exempt_health_checks():
    """Exempt health check endpoints from rate limiting"""
    return request.endpoint in ['static', 'ops.health', 'ops.ready']

# Caching is initialised in extensions.init_extensions (CACHE_TYPE env; `cache` is imported from extensions)

# Template and static caching: reload templates only in debug; keep compiled templates on disk
_debug = os.getenv('FLASK_DEBUG') == '1'
app.config['TEMPLATES_AUTO_RELOAD'] = _debug
if not _debug:
    try:
        from jinja2 import FileSystemBytecodeCache
        _jinja_cache_dir = os.path.join(basedir, 'instance', 'jinja_cache')
        os.makedirs(_jinja_cache_dir, exist_ok=True)
        app.jinja_env.bytecode_cache = FileSystemBytecodeCache(_jinja_cache_dir)
    except OSError:
        logger.warning("Jinja bytecode cache directory is not writable; compiling templates in memory")

# Configure session BEFORE initializing extensions
_secret_key = os.getenv('SECRET_KEY')
if not _secret_key:
    if os.getenv('FLASK_ENV') == 'production':
        raise RuntimeError("SECRET_KEY must be set in production")
    logger.warning("SECRET_KEY not set: using a random per-process key (sessions reset on restart)")
    _secret_key = secrets.token_hex(32)
app.secret_key = _secret_key
# Sessions are Flask's signed cookies (no server-side storage); utils/session_stamp.py makes them revocable.
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=int(os.getenv('SESSION_LIFETIME_HOURS', '24') or 24))  # shared campus machines: short
app.config['SESSION_COOKIE_SECURE'] = os.getenv('FLASK_ENV') == 'production'  # True in production with HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Prevent XSS attacks
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Strict would drop the cookie on the Google OAuth redirect
app.config['SESSION_COOKIE_NAME'] = 'mindfullhorizon_session'  # Custom session cookie name
app.config['WTF_CSRF_TIME_LIMIT'] = 604800  # 7 days, for prototype convenience

# Additional security configurations
app.config['SESSION_COOKIE_MAX_AGE'] = 604800  # 7 days in seconds
app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=30)  # Remember me functionality
app.config['REMEMBER_COOKIE_SECURE'] = os.getenv('FLASK_ENV') == 'production'
app.config['REMEMBER_COOKIE_HTTPONLY'] = True
app.config['REMEMBER_COOKIE_SAMESITE'] = 'Lax'

# Initialize database extensions AFTER session configuration
from extensions import init_extensions
init_extensions(app)

from models import *
logger = logging.getLogger(APP_LOGGER)  # `from models import *` rebinds `logger` to models' logger
from utils.database_utils import check_database, init_db
from utils.session_stamp import init_session_stamp  # revocable cookie sessions
init_session_stamp(app)

# Check database connection at startup
with app.app_context():
    if not check_database():
        app.logger.warning("Database not initialized or connection failed. Attempting to initialize...")
        if init_db():
            app.logger.info("Database initialized successfully")
        else:
            app.logger.error("Failed to initialize database. Some features may not work correctly.")

# Enable CSRF protection for security
csrf.init_app(app)

# Register all blueprints
for blueprint in all_blueprints:
    app.register_blueprint(blueprint)

from utils.logging_setup import init_logging  # request ids, access log, log redaction
from utils.jobs import init_jobs  # job queue CLI + optional in-process worker (JOBS_INPROCESS)
init_logging(app)
init_jobs(app)
from services.admin_cli import init_admin_cli  # flask create-admin and friends
from services.ops_jobs import init_ops_cli  # flask ops-daily-schedule
from ai.kb import init_kb_cli  # flask list-kb-drafts (chat router knowledge-base review)
init_admin_cli(app)
init_ops_cli(app)
init_kb_cli(app)

# Asset management
assets = Environment(app)

js_bundle = Bundle(
    'js/modal-utils.js',
    'js/scripts.js',
    filters='jsmin',
    output='gen/packed.js'
)
assets.register('js_all', js_bundle)
# css_all (enhanced.css + fallback-cards.css + styles.css) removed 2026-11-25: never rendered by any
# template (`{% assets "css_all" %}` had no caller) and enhanced.css/fallback-cards.css had no other
# reference either; see docs/TRACKER.md O-10. styles.css is still served directly via base.html legacy_head.

from utils.security_headers import init_security_headers  # nonce, CSP and the other security headers
init_security_headers(app)

# Versioned static files (?v=..., webassets ?<hash>, or a hash in the file name) never change under the same URL
_HASHED_NAME = re.compile(r'\.[0-9a-f]{8,}\.[a-z0-9]+$')

@app.after_request
def add_cache_headers(response):
    """Cheap, header-only caching policy (a route's own Cache-Control wins; static files are the exception, see below)."""
    path = request.path
    if path.startswith('/static/'):
        # Versioned URLs never change content: ?v=..., any query on /static/gen/ (webassets hash) or a hash in the name.
        if response.status_code == 200 and ('v' in request.args or (request.args and path.startswith('/static/gen/'))
                                            or _HASHED_NAME.search(path)):
            response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
        return response  # other static: Flask's ETag + Last-Modified conditional responses (304)
    if 'Cache-Control' in response.headers or response.status_code >= 500:
        return response
    mimetype = response.mimetype
    if mimetype == 'text/html':
        response.headers['Cache-Control'] = 'private, no-cache' if session.get('user_id') else 'no-cache'
        response.vary.add('Cookie')
    elif mimetype == 'application/json':
        response.headers['Cache-Control'] = 'no-store'  # API bodies can hold personal health data
    return response

# Secure CSRF error handler
@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    logger.warning(f"CSRF error for user {session.get('user_email', 'anonymous')}: {request.endpoint}")
    flash('Session expired or invalid request. Please try again.', 'error')
    return redirect(url_for('auth.login'))

# Global error handlers for security
@app.errorhandler(413)
def handle_file_too_large(e):
    logger.warning(f"File too large upload attempt from {request.remote_addr}")
    flash('File too large. Maximum size is 5MB.', 'error')
    return redirect(request.url)

@app.errorhandler(400)
def handle_bad_request(e):
    logger.warning(f"Bad request from {request.remote_addr}: {request.endpoint}")
    # For journal-related requests, redirect back to journal instead of index
    if request.endpoint == 'patient.patient_journal' and request.method == 'POST':
        flash('Invalid request. Please check your input and try again.', 'error')
        return redirect(url_for('patient.patient_journal'))
    flash('Invalid request. Please try again.', 'error')
    return redirect(url_for('core.index'))

@app.errorhandler(500)
def handle_internal_error(e):
    logger.error(f"Internal server error: {e}")
    # For journal-related requests, redirect back to journal instead of index
    if request.endpoint == 'patient.patient_journal' and request.method == 'POST':
        flash('An error occurred while saving your journal entry. Please try again.', 'error')
        return redirect(url_for('patient.patient_journal'))
    from utils.site_context import render_error_page
    return render_error_page(500)

from utils.site_context import init_site_context  # context processor + 404 handler (templates/errors)
init_site_context(app)

# Routes that used to live directly on `app` have moved to routes/ modules (O-15); each is registered
# with its own register_X(app)/register_X(socketio) call so endpoint names and URLs stay unchanged.
from routes.profile_onboarding import register_profile_onboarding_routes
register_profile_onboarding_routes(app)

from routes.chat_telehealth import register_chat_telehealth_routes
register_chat_telehealth_routes(app)

from routes.audio import register_audio_routes
register_audio_routes(app)

from routes.journal_voice import register_journal_voice_routes
register_journal_voice_routes(app)

from routes.misc import register_misc_routes
register_misc_routes(app)

from routes.sockets import register_socketio_handlers
register_socketio_handlers(socketio)

from routes.google_oauth import register_google_oauth
google_logged_in = register_google_oauth(app)  # exposed as app.google_logged_in: some tests call it directly


@app.context_processor
def utility_processor():
    def get_severity_info(assessment_type, score):
        if score is None:
            return {'severity': 'N/A', 'color': 'gray'}
        score = float(score)
        kind = canonical_type(assessment_type)
        if kind:
            band = band_for(kind, score)
            color = {'minimal': 'green', 'mild': 'yellow', 'moderate': 'orange'}.get(band, 'red')
            return {'severity': band.title(), 'color': color}
        if assessment_type == 'Daily Mood':
            if score >= 7:  # mood is stored 1-10
                return {'severity': 'Positive', 'color': 'green'}
            elif score >= 4:
                return {'severity': 'Neutral', 'color': 'yellow'}
            else:
                return {'severity': 'Negative', 'color': 'red'}
        else:
            return {'severity': 'N/A', 'color': 'gray'}
    return dict(get_severity_info=get_severity_info)


if __name__ == '__main__':
    import signal
    import sys

    def signal_handler(sig, frame):
        print("\nINFO - Received interrupt signal (Ctrl+C)")
        print("INFO - Shutting down MindFullHorizon server gracefully...")
        sys.exit(0)

    # Register signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)

    debug = os.getenv('FLASK_DEBUG') == '1'
    try:
        print("INFO - ==================================================")
        print("INFO - Starting MindFullHorizon server...")
        print(f"INFO - Server available at: http://localhost:5000")
        print(f"INFO - Debug mode: {debug}")
        print("INFO - CSRF Protection: Enabled")
        print("INFO - Press Ctrl+C to stop the server")
        print("INFO - ==================================================")

        # SocketIO server for real-time features
        # On Windows, the Flask reloader can start two processes, causing a port-in-use error with SocketIO/eventlet.
        # Disable the reloader on Windows to avoid binding twice.
        use_reloader = debug and os.name != 'nt'
        socketio.run(app, host='127.0.0.1', port=5000, debug=debug, use_reloader=use_reloader, allow_unsafe_werkzeug=True)

    except KeyboardInterrupt:
        print("\nINFO - Server interrupted by user (Ctrl+C)")
        print("INFO - Shutting down gracefully...")
        sys.exit(0)
    except Exception as e:
        print(f"ERROR - Failed to start server: {e}")
        sys.exit(1)
