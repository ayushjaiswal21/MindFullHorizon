import logging
import sys

# Configure basic logging early to handle import errors (stdout: Render shows stdout in the dashboard)
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

import json
import re
import secrets  # Added for CSP nonce generation
import base64

from urllib.parse import quote

import os
from datetime import datetime, timedelta, date, timezone
from sqlalchemy import func

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Debug: Check if .env was loaded successfully
logger.info(f".env file loaded: GEMINI_API_KEY present = {'Yes' if os.getenv('GEMINI_API_KEY') else 'No'}")

# The app logger is named 'app' explicitly. Production logs to stdout only; development adds logs/mindful_horizon.log.
from utils.log_config import setup_app_logging, APP_LOGGER
logger = setup_app_logging()

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_from_directory, g
from flask_wtf.csrf import CSRFError
from flask_socketio import SocketIO, emit, join_room, leave_room, rooms
from flask_assets import Environment, Bundle
# Import blueprints from routes package
from routes import all_blueprints
from routes.auth import is_strong_password
from ai.scoring import band_for, canonical_type

import ai.service as ai_service
from extensions import db, csrf, limiter, cache
import utils.cache_utils  # noqa: F401  (registers the cache-invalidation session listeners)
from models import User, Appointment, Gamification, DigitalDetoxLog, Notification, MoodLog  # the rest comes via `from models import *` below


# File upload configuration
ALLOWED_EXTENSIONS = {'wav', 'mp3', 'ogg'}  # voice logs only; nothing uploaded is stored on disk
ALLOWED_MIME_TYPES = {'audio/wav', 'audio/mpeg', 'audio/ogg'}

def validate_file_security(file):
    """
    Comprehensive file validation for security and compatibility
    Returns: (is_valid: bool, error_message: str)
    """
    try:
        # Check if file exists
        if not file or not file.filename:
            return False, "No file selected"
        
        # Check file extension
        if not ('.' in file.filename and 
                file.filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS):
            return False, f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        
        # Get file size
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)  # Reset file pointer
        
        # Check file size (16MB max)
        max_size = 16 * 1024 * 1024
        if file_size > max_size:
            return False, f"File too large. Maximum size: {max_size // (1024*1024)}MB"
        
        # Check for malicious content in filename
        if any(char in file.filename for char in ['..', '/', '\\', ':', '*', '?', '"', '<', '>', '|']):
            return False, "Invalid characters in filename"
        
        return True, "File validation successful"
        
    except Exception as e:
        logger.error(f"Error during file validation: {e}")
        return False, "File validation error"

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
from utils.session_stamp import init_session_stamp, stamp_session  # revocable cookie sessions
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

css_bundle = Bundle(
    'css/enhanced.css',
    'css/fallback-cards.css',
    'css/styles.css',
    filters='cssmin',
    output='gen/packed.css'
)
assets.register('css_all', css_bundle)

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





# Import gamification functions
from utils.gamification import award_points



from decorators import login_required, api_login_required, role_required, can_join_telehealth


# Favicon route to prevent 404 errors
@app.route('/favicon.ico')
def favicon():
    try:
        return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')
    except FileNotFoundError:
        # Return empty response for missing favicon to avoid 404
        return '', 204










@app.route('/chat')
@login_required
def chat():
    from utils.chat_templates import public_list
    return render_template('chat.html', user_name=session['user_name'], starters=public_list())


@app.route('/api/message', methods=['POST'])
@login_required
@limiter.limit('30 per minute')
def api_message():
    """Quick message between a patient and a provider who are linked (ProviderPatient row or an appointment)."""
    from models import ProviderPatient
    data = request.get_json(silent=True)
    data = data if isinstance(data, dict) else {}
    recipient_id, message = data.get('recipient_id'), data.get('message')
    if isinstance(recipient_id, str) and recipient_id.isdigit():
        recipient_id = int(recipient_id)
    if isinstance(recipient_id, bool) or not isinstance(recipient_id, int) or not isinstance(message, str) or not message.strip():
        return jsonify(success=False, error='recipient_id and message are required'), 400
    message = message.strip()
    if len(message) > 1000:
        return jsonify(success=False, error='Message is too long (1000 characters at most)'), 400
    sender_id, role = session.get('user_id'), session.get('user_role')
    recipient = db.session.get(User, recipient_id) if recipient_id != sender_id else None
    allowed = False
    if recipient and {role, recipient.role} == {'patient', 'provider'}:
        patient_id, provider_id = (sender_id, recipient_id) if role == 'patient' else (recipient_id, sender_id)
        allowed = (ProviderPatient.query.filter_by(provider_id=provider_id, patient_id=patient_id).first() is not None
                   or Appointment.query.filter_by(user_id=patient_id, provider_id=provider_id).first() is not None)
    if not allowed:  # same answer for unknown, self, wrong role and unlinked recipients: no user enumeration
        return jsonify(success=False, error='You cannot message this recipient'), 403
    try:
        notif = Notification(sender_id=sender_id, recipient_id=recipient_id, message=message, type='message', payload=None)
        db.session.add(notif)
        db.session.commit()
        return jsonify(success=True, id=notif.id)
    except Exception as e:
        db.session.rollback()
        logger.error("Failed to create message: %s", type(e).__name__)
        return jsonify(success=False, error='Could not send message'), 500








@app.route('/telehealth_session/<int:user_id>')
@login_required
def telehealth_session(user_id):
    if session.get('user_role') != 'provider' or not can_join_telehealth(user_id):
        return "Forbidden", 403
    patient = User.query.get_or_404(user_id)
    return render_template('telehealth.html', 
                           user_name=session['user_name'],
                           patient_id=patient.id,
                           patient_name=patient.name)

@app.route('/telehealth')
@login_required
def telehealth():
    return render_template('telehealth.html', user_name=session['user_name'])




@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user_id = session['user_id']
    user = User.query.get(user_id)
    if not user:
        flash('User not found. Please log in again.', 'error')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        user.name = request.form.get('name', user.name)
        user.email = request.form.get('email', user.email)
        user.institution = request.form.get('institution', user.institution)

        # Handle password change
        password = request.form.get('password')
        if password:
            is_strong, message = is_strong_password(password)
            if not is_strong:
                flash(message, 'error')
                return redirect(url_for('profile'))
            user.set_password(password)

        try:
            db.session.commit()
            session['user_name'] = user.name  # Update session name if changed
            stamp_session(user)  # a new password changes the stamp: keep THIS session valid
            flash('Profile updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating profile for user {user_id}: {e}")
            flash('Failed to update profile.', 'error')
        return redirect(url_for('profile'))

    gamification = Gamification.query.filter_by(user_id=user_id).first()
    digital_detox_logs = DigitalDetoxLog.query.filter_by(user_id=user_id).order_by(DigitalDetoxLog.date.desc()).all()

    avg_screen_time_7_days = None
    avg_screen_time_30_days = None

    if digital_detox_logs:
        recent_7_days = digital_detox_logs[:7]
        if recent_7_days:
            avg_screen_time_7_days = sum(log.screen_time_hours for log in recent_7_days) / len(recent_7_days)

        recent_30_days = digital_detox_logs[:30]
        if recent_30_days:
            avg_screen_time_30_days = sum(log.screen_time_hours for log in recent_30_days) / len(recent_30_days)

    return render_template('profile.html',
                         user_name=session['user_name'],
                         user=user,
                         gamification=gamification,
                         digital_detox_logs=digital_detox_logs,
                         avg_screen_time_7_days=avg_screen_time_7_days,
                         avg_screen_time_30_days=avg_screen_time_30_days)

from routes.audio import register_audio_routes
register_audio_routes(app)


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

# --- PATIENT JOURNAL ROUTES ---

@app.route('/api/delete-journal-entry/<int:entry_id>', methods=['DELETE'])
@login_required
@role_required('patient')
def delete_journal_entry(entry_id):
    """Delete one of the session user's journal entries."""
    from models import JournalEntry
    entry = JournalEntry.query.filter_by(id=entry_id, user_id=session['user_id']).first()
    if not entry:
        return jsonify({'success': False, 'message': 'Journal entry not found'}), 404
    try:
        db.session.delete(entry)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Journal entry deleted successfully'})
    except Exception:
        db.session.rollback()
        logger.exception("Error deleting journal entry")
        return jsonify({'success': False, 'message': 'Failed to delete journal entry'}), 500


@app.route('/api/delete-voice-log/<int:voice_log_id>', methods=['DELETE'])
@login_required
@role_required('patient')
def delete_voice_log(voice_log_id):
    """Delete one of the session user's voice logs (measurements and note; no audio is stored)."""
    from models import VoiceLog
    voice_log = VoiceLog.query.filter_by(id=voice_log_id, user_id=session['user_id']).first()
    if not voice_log:
        return jsonify({'success': False, 'message': 'Voice log not found'}), 404
    try:
        db.session.delete(voice_log)
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("Error deleting voice log")
        return jsonify({'success': False, 'message': 'Failed to delete voice log'}), 500
    return jsonify({'success': True, 'message': 'Voice log deleted successfully'})


@app.route('/api/upload-voice', methods=['POST'])
@login_required
@role_required('patient')
@limiter.limit("5 per hour")  # Limit voice uploads
def upload_voice():
    """Upload a voice recording, analyse it if possible and store a VoiceLog for the session user."""
    from models import VoiceLog
    user_id = session['user_id']
    audio_file = request.files.get('audio')
    if not audio_file or not audio_file.filename:
        return jsonify({'success': False, 'message': 'No audio file provided'}), 400
    if not (audio_file.content_type or '').startswith('audio/'):
        return jsonify({'success': False, 'message': 'Invalid file type. Please upload an audio file.'}), 400
    is_valid, error_message = validate_file_security(audio_file)
    if not is_valid:
        return jsonify({'success': False, 'message': error_message}), 400

    try:
        from utils.voice_features import extract_features  # analysed in memory/temp file; only duration is stored
        audio_features = extract_features(audio_file, audio_file.filename.rsplit('.', 1)[1].lower())
        voice_log = VoiceLog(
            user_id=user_id,
            filename='not-stored',  # placeholder for the non-null column: the audio is never kept
            audio_features=audio_features,
        )
        db.session.add(voice_log)
        db.session.commit()
        award_points(user_id, 20, 'voice_log', ref=f'voice:{voice_log.id}')

        return jsonify({
            'success': True,
            'message': 'Voice log saved. The audio was analysed and not kept.',
            'voice_log': {'id': voice_log.id, 'audio_features': audio_features}
        })
    except Exception:
        db.session.rollback()
        logger.exception("Error uploading voice file")
        return jsonify({'success': False, 'message': 'Failed to process voice recording'}), 500


# /health and /ready live in routes/ops.py (ops_bp)

@app.route('/api/ai-status')
@login_required
def ai_status():
    """Check the status of the AI service."""
    status = ai_service.check_api_status()
    return jsonify(status)

# Error logging endpoint for client-side errors
@app.route('/api/log-error', methods=['POST'])
@csrf.exempt
@limiter.limit("10 per minute")  # Rate limit error logging
def log_client_error():
    """Log client-side JavaScript errors for debugging."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'success': False, 'message': 'No data provided'}), 400

    def clean(v, n):  # one line, bounded: client text must not forge log lines
        return re.sub(r'[^ -~]', ' ', str(v))[:n]

    logger.warning(f"Client-side error: {clean(data.get('message', 'Unknown error'), 300)} "
                   f"at {clean(data.get('filename', 'unknown'), 200)}:{clean(data.get('lineno', 'unknown'), 10)} "
                   f"from {request.remote_addr}")
    return jsonify({'success': True, 'message': 'Error logged'}), 200

# --- SocketIO User Room Management ---
@socketio.on('connect')
def handle_connect():
    """Handle user connection and join their personal room"""
    if 'user_id' in session:
        user_room = f'user_{session["user_id"]}'
        join_room(user_room)
        logger.info(f"User {session['user_id']} connected and joined room {user_room}")
        emit('connected', {'message': 'Connected to notification system'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle user disconnection"""
    if 'user_id' in session:
        user_room = f'user_{session["user_id"]}'
        leave_room(user_room)
        logger.info(f"User {session['user_id']} disconnected from room {user_room}")

# --- SocketIO Chat Handler ---
@socketio.on('chat_message')
def handle_chat_message(data):
    # Basic validation - check if user is logged in via session
    if 'user_email' not in session:
        emit('error', {'message': 'Authentication required'})
        return
    
    user_message = data.get('message')
    if not user_message or not isinstance(user_message, str):
        emit('error', {'message': 'Invalid message format'})
        return
    
    # Sanitize user input
    user_message = user_message.strip()[:500]  # Limit message length
    if not user_message:
        emit('error', {'message': 'Message cannot be empty'})
        return
    
    try:
        ai_resp = ai_service.generate_chat_response(user_message)
        if isinstance(ai_resp, dict):
            reply_text = ai_resp.get('response') or ai_resp.get('reply') or str(ai_resp)
            is_crisis = bool(ai_resp.get('needs_followup')) or bool(ai_resp.get('is_crisis'))
        else:
            reply_text = str(ai_resp)
            is_crisis = False
        
        # Log the interaction for monitoring
        logger.info(f"Chat interaction - User: {session.get('user_email', 'unknown')}, Length: {len(user_message)}, Crisis: {is_crisis}")
        
    except Exception as e:
        logger.error(f"Chat handler error: {e}")
        reply_text = "I apologize, but I'm having trouble responding right now. Please try again in a moment."
        is_crisis = False

    # O-02: rule-based floor, independent of the model; the emergency reply below never waits on the DB write
    from utils.crisis import text_is_crisis, try_record_crisis
    if text_is_crisis(user_message):
        is_crisis = True
        try_record_crisis(session.get('user_id'), 'chat', 9, 'chat_self_harm')

    emit('chat_response', {'reply': reply_text, 'is_crisis': is_crisis})

# --- SocketIO Telehealth Handlers ---
TELEHEALTH_ROOM = re.compile(r'telehealth_room_(\d+)')

def _room_of(data):
    """Room name from a socket payload, or None if malformed or not a telehealth room."""
    room = data.get('room') if isinstance(data, dict) else None
    return room if isinstance(room, str) and TELEHEALTH_ROOM.fullmatch(room) else None

def _joined_room(data):
    """Room for signalling events: the caller must be logged in and already (authorised) in it."""
    room = _room_of(data)
    return room if room and session.get('user_id') and room in rooms() else None

@socketio.on('join')
def on_join(data):
    room = _room_of(data)
    if not room or not can_join_telehealth(int(TELEHEALTH_ROOM.fullmatch(room).group(1))):
        emit('join_error', {'message': 'Not allowed to join this session'})
        return {'ok': False, 'error': 'forbidden'}
    join_room(room)
    emit('message', 'A participant has joined the session.', to=room)
    # Notify the other user in the room that a peer is ready
    emit('ready', to=room, include_self=False)
    return {'ok': True}

@socketio.on('offer')
def on_offer(data):
    if room := _joined_room(data):
        emit('offer', data, to=room, include_self=False)

@socketio.on('answer')
def on_answer(data):
    if room := _joined_room(data):
        emit('answer', data, to=room, include_self=False)

@socketio.on('candidate')
def on_candidate(data):
    if room := _joined_room(data):
        emit('candidate', data, to=room, include_self=False)

@socketio.on('leave')
def on_leave(data):
    if room := _joined_room(data):
        leave_room(room)
        emit('_disconnect', to=room, include_self=False)
        emit('message', 'A participant has left the session.', to=room)

# Google OAuth Configuration
app.config["GOOGLE_OAUTH_CLIENT_ID"] = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
app.config["GOOGLE_OAUTH_CLIENT_SECRET"] = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")

from flask_dance.contrib.google import make_google_blueprint, google

google_bp = make_google_blueprint(
    scope=["openid", "https://www.googleapis.com/auth/userinfo.profile", "https://www.googleapis.com/auth/userinfo.email"]
)
app.register_blueprint(google_bp, url_prefix="/login")

from flask_dance.consumer import oauth_authorized

@oauth_authorized.connect_via(google_bp)
def google_logged_in(blueprint, token):
    """Handles the logic after a user logs in with Google."""
    if not token:
        flash("Failed to log in with Google.", "danger")
        return redirect(url_for("auth.login"))

    try:
        logger.info("Google authorized, fetching user info.")
        resp = blueprint.session.get("/oauth2/v2/userinfo")
        assert resp.ok, resp.text
        user_info = resp.json()
        google_id = user_info['id']
        email = (user_info['email'] or '').strip().lower()
        name = user_info.get('name', 'User')

        logger.info(f"Looking for user with google_id={google_id}")
        user = User.query.filter_by(google_id=google_id).first()
        new_google_user = False

        if not user:
            logger.info(f"User not found with google_id, looking for user with email={email}")
            user = User.query.filter_by(email=email).first()
            if user and not (user_info.get('verified_email') or user_info.get('email_verified')):
                # never attach a Google identity to an existing account unless Google vouches for the address
                flash("Your Google email is not verified, so we cannot sign you in with it.", "danger")
                return redirect(url_for("auth.login"))
            if user:
                logger.info(f"User found with email, linking google_id")
                user.google_id = google_id
                db.session.commit()
                logger.info("google_id linked to existing user.")
            else:
                logger.info("No existing user found, creating a new user with default patient role.")
                new_google_user = True
                # Create new user with default patient role and institution
                user = User(
                    email=email, 
                    google_id=google_id, 
                    name=name,
                    role='patient',  # Default role for Google OAuth users
                    institution='Default University'
                )
                user.set_password(secrets.token_urlsafe(32))  # random, never shown: password login stays unusable
                db.session.add(user)
                db.session.commit()
                logger.info("New user created with patient role.")
                
                # Create gamification profile for new patient
                try:
                    gamification = Gamification(
                        user_id=user.id,
                        points=0,
                        streak=0,
                        badges=[],
                        last_activity=None
                    )
                    db.session.add(gamification)
                    db.session.commit()
                    logger.info(f'Gamification profile created for Google OAuth user: {email}')
                except Exception as gam_error:
                    logger.error(f'Error creating gamification profile for Google user: {gam_error}')
                    db.session.rollback()

        if user.role == 'admin' or user.deactivated_at is not None:  # admins sign in with a password at /admin/login only
            flash("Please sign in with your email and password.", "danger")
            return redirect(url_for("auth.login"))

        logger.info(f"Logging in user: {user.email} (id={user.id})")
        
        # Ensure user has a role - assign default if missing
        if not user.role:
            logger.warning(f"User {user.email} has no role, assigning default 'patient' role.")
            user.role = 'patient'
            user.institution = user.institution or 'Default University'
            try:
                db.session.commit()
                logger.info("Default role assigned to user.")
                
                # Create gamification profile if it doesn't exist
                if not Gamification.query.filter_by(user_id=user.id).first():
                    gamification = Gamification(
                        user_id=user.id,
                        points=0,
                        streak=0,
                        badges=[],
                        last_activity=None
                    )
                    db.session.add(gamification)
                    db.session.commit()
                    logger.info(f'Gamification profile created for user: {user.email}')
            except Exception as role_error:
                logger.error(f'Error assigning default role: {role_error}')
                db.session.rollback()
                # Continue with session creation even if role assignment fails
        
        session.clear()
        session.permanent = True
        session['user_id'] = user.id
        session['user_email'] = user.email
        session['user_name'] = user.name
        session['user_role'] = user.role
        session['user_institution'] = user.institution or 'Default University'
        stamp_session(user)
        session.modified = True
        logger.info("Session created for user.")

        from routes.auth import needs_reconsent
        if new_google_user or needs_reconsent(user):  # no consent was recorded for this sign-in yet (P-05)
            session['consent_pending'] = True
            return redirect(url_for('auth.consent'))

        if user.role == 'patient':
            logger.info("User is a patient, redirecting to patient_dashboard.")
            return redirect(url_for('patient.patient_dashboard'))
        else:
            logger.info("User is a provider, redirecting to provider_dashboard.")
            return redirect(url_for('provider.provider_dashboard'))

    except Exception as e:
        logger.error(f"An error occurred during Google login: {e}", exc_info=True)
        flash("Google sign-in failed. Please try again.", "danger")
        return redirect(url_for('auth.login'))


@app.route('/role_selection')
def role_selection():
    """Renders the role selection page for new users."""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    return render_template('role_selection.html')

@app.route('/save_role', methods=['POST'])
@login_required
def save_role():
    """Lets a role-less/patient account confirm 'patient'. Provider accounts are only created via the signup invite code."""
    user = db.session.get(User, session['user_id'])
    if request.form.get('role') != 'patient' or not user or user.role not in (None, '', 'patient'):
        flash("That role cannot be selected here.", "warning")
        return redirect(url_for('role_selection'))
    try:
        user.role = 'patient'
        db.session.commit()
        session['user_role'] = 'patient'
        stamp_session(user)  # the role is part of the stamp
        return redirect(url_for('patient.patient_dashboard'))
    except Exception as e:
        db.session.rollback()
        logger.error(f"Could not save user role: {e}")
        flash("Could not save your role. Please try again.", "danger")
        return redirect(url_for('role_selection'))

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