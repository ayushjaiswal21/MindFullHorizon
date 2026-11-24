import logging

# Configure basic logging early to handle import errors
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import json
import re
import secrets  # Added for CSP nonce generation
import base64

from urllib.parse import quote
from werkzeug.utils import secure_filename
import uuid

import os
from datetime import datetime, timedelta, date, timezone
from sqlalchemy import func

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Debug: Check if .env was loaded successfully
logger.info(f".env file loaded: GEMINI_API_KEY present = {'Yes' if os.getenv('GEMINI_API_KEY') else 'No'}")

# Configure logging early
import logging

# Create a custom logger that outputs to both file and console
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Remove any existing handlers to avoid duplicates
for handler in logger.handlers[:]:
    logger.removeHandler(handler)

# File handler
file_handler = logging.FileHandler('mindful_horizon.log')
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# Console handler for terminal output
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_from_directory, g
import nltk

# Download NLTK data if not already present
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')
try:
    nltk.data.find('corpora/wordnet')
except LookupError:
    nltk.download('wordnet')
from flask_wtf.csrf import CSRFError
from flask_socketio import SocketIO, emit, join_room, leave_room, rooms
from flask_caching import Cache
from flask_assets import Environment, Bundle
# Import blueprints from routes package
from routes import all_blueprints
from routes.auth import is_strong_password
from ai.scoring import band_for, canonical_type

import ai.service as ai_service
from extensions import db, csrf, limiter
from models import User, Appointment, Gamification, DigitalDetoxLog, Notification, MoodLog  # the rest comes via `from models import *` below


# File upload configuration
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'wav', 'mp3', 'ogg'}
ALLOWED_MIME_TYPES = {
    'image/png', 'image/jpeg', 'image/jpg', 'image/gif',
    'audio/wav', 'audio/mpeg', 'audio/ogg'
}

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

# Import new dependencies for patient features
try:
    from textblob import TextBlob
    import librosa
    import numpy as np
    TEXTBLOB_AVAILABLE = True
    LIBROSA_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Some patient feature dependencies not available: {e}")
    TEXTBLOB_AVAILABLE = False
    LIBROSA_AVAILABLE = False

# Database configuration
app = Flask(__name__)

# Configure file uploads
app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///mindful_horizon.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
}

basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'instance', 'mindful_horizon.db')
logger.info(f"DATABASE_URL: {os.environ.get('DATABASE_URL')}")
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL') or f'sqlite:///{db_path}'
logger.info(f"Using database at: {app.config['SQLALCHEMY_DATABASE_URI']}")

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Database connection pooling configuration
engine_options = {
    'pool_size': 10,
    'pool_recycle': 120,
    'pool_pre_ping': True,
    'max_overflow': 20
}

# Improve SQLite compatibility with threaded servers (e.g., SocketIO)
if app.config.get('SQLALCHEMY_DATABASE_URI', '').startswith('sqlite:///'):
    engine_options['connect_args'] = {'check_same_thread': False}

app.config['SQLALCHEMY_ENGINE_OPTIONS'] = engine_options


# Same-origin only unless CORS_ORIGINS (comma separated) is set.
_cors = os.getenv('CORS_ORIGINS')
socketio = SocketIO(app, cors_allowed_origins=[o.strip() for o in _cors.split(',')] if _cors else None)

# Rate limiter (see extensions.py for the limits)
limiter.init_app(app)  # defined in extensions.py so blueprints can add per-route limits

# Rate limiting exemption for health checks and static files
@limiter.request_filter
def exempt_health_checks():
    """Exempt health check endpoints from rate limiting"""
    return request.endpoint in ['static', 'health_check']

# Initialize caching
cache = Cache(app, config={'CACHE_TYPE': 'simple'})

# Configure session BEFORE initializing extensions
_secret_key = os.getenv('SECRET_KEY')
if not _secret_key:
    if os.getenv('FLASK_ENV') == 'production':
        raise RuntimeError("SECRET_KEY must be set in production")
    logger.warning("SECRET_KEY not set: using a random per-process key (sessions reset on restart)")
    _secret_key = secrets.token_hex(32)
app.secret_key = _secret_key
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)  # Extended session lifetime
app.config['SESSION_COOKIE_SECURE'] = os.getenv('FLASK_ENV') == 'production'  # True in production with HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Prevent XSS attacks
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Strict would drop the cookie on the Google OAuth redirect
app.config['SESSION_COOKIE_NAME'] = 'mindfullhorizon_session'  # Custom session cookie name
app.config['SESSION_FILE_DIR'] = os.path.join(os.getcwd(), 'flask_session')
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
from utils.database_utils import check_database, init_db

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

# --- CSP Report-Only: generate nonce per request and set CSP-Report-Only header ---
@app.before_request
def generate_csp_nonce():
    # 18 random bytes -> base64 ascii nonce
    g.csp_nonce = base64.b64encode(os.urandom(18)).decode('ascii')



# Report-only until templates stop using inline handlers/scripts, then switch to enforcing.
CSP_REPORT_ONLY = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://cdn.socket.io https://unpkg.com; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
    "font-src 'self' data: https://fonts.gstatic.com https://cdnjs.cloudflare.com; "
    "img-src 'self' data: https:; media-src 'self' https:; connect-src 'self' ws: wss:; "
    "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
)

@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Permissions-Policy"] = "camera=(self), microphone=(self), geolocation=()"
    response.headers["Content-Security-Policy-Report-Only"] = CSP_REPORT_ONLY
    if os.getenv('FLASK_ENV') == 'production':
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
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
    return redirect(url_for('core.index'))





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
    return render_template('chat.html', user_name=session['user_name'])


@app.route('/api/message', methods=['POST'])
@login_required
def api_message():
    try:
        data = request.get_json() or {}
        recipient_id = data.get('recipient_id')
        message = data.get('message', '').strip()
        if not recipient_id or not message:
            return jsonify(success=False, error='recipient_id and message are required'), 400

        # create notification
        notif = Notification(sender_id=session.get('user_id'), recipient_id=recipient_id, message=message, type='message', payload=None)
        db.session.add(notif)
        db.session.commit()
        return jsonify(success=True, id=notif.id)
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to create message: {e}")
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

        # Handle profile picture upload with enhanced security
        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file and file.filename:
                is_valid, error_message = validate_file_security(file)
                if is_valid:
                    try:
                        filename = secure_filename(file.filename)
                        # Ensure unique filename to prevent overwrites and path traversal
                        unique_filename = str(uuid.uuid4()) + '_' + filename
                        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)

                        # Additional security: ensure path is within upload folder
                        if not os.path.abspath(file_path).startswith(os.path.abspath(app.config['UPLOAD_FOLDER'])):
                            flash('Invalid file path detected.', 'error')
                        else:
                            # Use context manager to ensure file is properly closed
                            try:
                                with open(file_path, 'wb') as f:
                                    file.seek(0)  # Reset file pointer
                                    f.write(file.read())
                                user.profile_pic = unique_filename
                                flash('Profile picture updated successfully!', 'success')
                            except Exception as e:
                                logger.error(f"Error saving profile picture: {e}")
                                flash('Error saving profile picture.', 'error')
                    except Exception as e:
                        logger.error(f"Error processing profile picture upload: {e}")
                        flash('Error processing profile picture.', 'error')
                else:
                    flash(error_message, 'error')

        try:
            db.session.commit()
            session['user_name'] = user.name  # Update session name if changed
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

@app.route('/api/mood-music', methods=['GET'])
def api_mood_music():
    """Return a curated mapping of moods to YouTube search queries (and optional curated video IDs).

    The frontend can fetch this and either open a search page or use curated video IDs to embed a player.
    """
    # Default static mapping (fallback)
    mood_map = {
        'happy': {'query': 'binaural beats happy uplifting 528hz', 'videos': []},
        'sad': {'query': 'binaural beats sad calming 432hz', 'videos': []},
        'angry': {'query': 'binaural beats anger release calming bass', 'videos': []},
        'calm': {'query': 'binaural beats calm relaxation 432hz mindfulness', 'videos': []},
        'anxious': {'query': 'binaural beats anxiety relief slow tempo 432hz', 'videos': []},
        'focus': {'query': 'binaural beats focus concentration alpha waves 432hz', 'videos': []}
    }

    # Prefer DB-backed tracks if the optional `binaural_tracks` table has entries.
    try:
        from models import BinauralTrack
        db_tracks_exist = BinauralTrack.query.limit(1).first() is not None
    except Exception:
        db_tracks_exist = False

    if db_tracks_exist:
        try:
            from models import BinauralTrack
            # Build mood_map from DB
            mapping = {
                'happy': [], 'sad': [], 'angry': [], 'calm': [], 'anxious': [], 'focus': []
            }
            for t in BinauralTrack.query.all():
                e = (t.emotion or '').lower()
                # Simple heuristic mapping from stored emotion to our mood buckets
                if any(x in e for x in ('happy', 'uplift', 'joy', 'positive')):
                    mapping['happy'].append(t)
                elif any(x in e for x in ('sad', 'melancholy', 'blue')):
                    mapping['sad'].append(t)
                elif any(x in e for x in ('angry', 'anger', 'irritat')):
                    mapping['angry'].append(t)
                elif any(x in e for x in ('calm', 'relax', 'peace')):
                    mapping['calm'].append(t)
                elif any(x in e for x in ('anxious', 'anxiety', 'tense')):
                    mapping['anxious'].append(t)
                elif any(x in e for x in ('focus', 'concentr', 'study', 'attention')):
                    mapping['focus'].append(t)
                else:
                    # fallback: put in calm
                    mapping['calm'].append(t)

            # Convert to response shape using dictionary comprehensions
            resp_map = {
                k: {'query': mood_map[k]['query'], 'videos': []}
                for k in mapping.keys()
            }

            # Process each mood's tracks
            for k in mapping:
                for t in mapping[k]:
                    if t.youtube_id:
                        resp_map[k]['videos'].append({'id': t.youtube_id, 'title': t.title})
                    else:
                        resp_map[k]['query'] = resp_map[k]['query'] + ' ' + t.title

            # Deduplicate
            for k in resp_map:
                seen = set()
                dedup = []
                for it in resp_map[k]['videos']:
                    if it['id'] and it['id'] not in seen:
                        seen.add(it['id'])
                        dedup.append(it)
                resp_map[k]['videos'] = dedup

            return jsonify({'success': True, 'moods': resp_map})

        except Exception as e:
            logger.debug(f"Failed to build mood map from DB tracks: {e}")
            # fall through to file-based parsing/fallback

    # Attempt to enrich mapping from a local copy of the binaural-beats dataset
    # Expected location: ./data/binaural-beats-dataset/ (user can git clone the repo there)
    dataset_dir = os.path.join(basedir, 'data', 'binaural-beats-dataset')
    try:
        if os.path.isdir(dataset_dir):
            # Try common filenames in the dataset
            possible_files = ['tracks.csv', 'dataset.csv', 'tracks.json', 'data.json']
            found = None
            for fn in possible_files:
                path = os.path.join(dataset_dir, fn)
                if os.path.isfile(path):
                    found = path
                    break

            if found:
                # Prefer CSV, otherwise JSON
                if found.lower().endswith('.csv'):
                    import csv
                    with open(found, 'r', encoding='utf-8') as fh:
                        reader = csv.DictReader(fh)
                        for row in reader:
                            # Dataset may have columns like: title, artist, emotion, youtube_id, tags
                            emotion = (row.get('emotion') or row.get('mood') or '').strip().lower()
                            youtube_id = (row.get('youtube_id') or row.get('video_id') or row.get('youtube') or '').strip()
                            title = (row.get('title') or row.get('name') or '').strip()
                            if not emotion:
                                continue

                            # Map dataset emotion labels to our mood keys
                            mapping = {
                                'happy': ['happy', 'uplifting', 'joy', 'positive'],
                                'sad': ['sad', 'melancholy', 'blue'],
                                'angry': ['angry', 'anger', 'irritated'],
                                'calm': ['calm', 'relaxed', 'relaxation', 'peaceful'],
                                'anxious': ['anxious', 'anxiety', 'tense'],
                                'focus': ['focus', 'concentration', 'study', 'attention']
                            }

                            for mood_key, labels in mapping.items():
                                if any(label in emotion for label in labels):
                                    if youtube_id:
                                        mood_map[mood_key]['videos'].append({'id': youtube_id, 'title': title})
                                    else:
                                        # If no direct video id, append title to query suggestions
                                        mood_map[mood_key]['query'] = mood_map[mood_key]['query'] + ' ' + title
                                    break

                else:
                    # JSON file
                    import json
                    with open(found, 'r', encoding='utf-8') as fh:
                        data = json.load(fh)
                        # Expect list of tracks
                        items = data if isinstance(data, list) else data.get('tracks') or data.get('data') or []
                        for item in items:
                            emotion = (item.get('emotion') or item.get('mood') or '')
                            if emotion:
                                emotion = emotion.strip().lower()
                            youtube_id = (item.get('youtube_id') or item.get('video_id') or item.get('youtube') or '')
                            title = (item.get('title') or item.get('name') or '')
                            if not emotion:
                                continue

                            mapping = {
                                'happy': ['happy', 'uplifting', 'joy', 'positive'],
                                'sad': ['sad', 'melancholy', 'blue'],
                                'angry': ['angry', 'anger', 'irritated'],
                                'calm': ['calm', 'relaxed', 'relaxation', 'peaceful'],
                                'anxious': ['anxious', 'anxiety', 'tense'],
                                'focus': ['focus', 'concentration', 'study', 'attention']
                            }

                            for mood_key, labels in mapping.items():
                                if any(label in emotion for label in labels):
                                    if youtube_id:
                                        mood_map[mood_key]['videos'].append({'id': youtube_id, 'title': title})
                                    else:
                                        mood_map[mood_key]['query'] = mood_map[mood_key]['query'] + ' ' + title
                                    break

    except Exception as e:
        # Fail gracefully — keep default mapping and log
        logger.debug(f"Failed to load local binaural-beats dataset: {e}")

    # Deduplicate video lists by id
    for k, v in mood_map.items():
        vids = v.get('videos') or []
        seen = set()
        deduped = []
        for it in vids:
            vid = it.get('id')
            if not vid:
                continue
            if vid in seen:
                continue
            seen.add(vid)
            deduped.append(it)
        mood_map[k]['videos'] = deduped

    return jsonify({'success': True, 'moods': mood_map})


@app.route('/api/play-mood', methods=['POST'])
@api_login_required
def api_play_mood():
    """Attempt to play a binaural track for the requested mood.

    Priority:
      1. Look for local audio files in data/binaural-beats-dataset/audio/ whose filename contains the mood.
         If found, return its /audio/ URL for the browser to play (never launch anything on the server).
      2. If DB has BinauralTrack with youtube_id for the mood, return a YouTube URL for frontend to open.
      3. Otherwise return a YouTube search URL for the mood query.

    Returns JSON: { success: True, action: 'local'|'youtube', url }
    """
    data = request.get_json(silent=True)
    mood = str(data.get('mood') or '').strip().lower() if isinstance(data, dict) else ''

    if not mood:
        return jsonify({'success': False, 'message': 'Missing mood parameter'}), 400

    # 1) local audio folder
    audio_dir = os.path.join(basedir, 'data', 'binaural-beats-dataset', 'audio')
    try:
        if os.path.isdir(audio_dir):
            # look for files containing the mood in filename
            for fn in os.listdir(audio_dir):
                if mood in fn.lower() and fn.lower().endswith(('.mp3', '.wav', '.m4a', '.flac')):
                    return jsonify({'success': True, 'action': 'local', 'url': f'/audio/audio/{quote(fn)}'})

    except Exception as e:
        logger.debug(f"Error while searching for local audio files: {e}")

    # 2) DB-backed YouTube id
    try:
        from models import BinauralTrack
        tracks = BinauralTrack.query.filter(BinauralTrack.emotion.ilike(f"%{mood}%")).all()
        if tracks:
            # Prefer tracks with youtube_id
            for t in tracks:
                if t.youtube_id:
                    url = f"https://www.youtube.com/watch?v={t.youtube_id}"
                    return jsonify({'success': True, 'action': 'youtube', 'url': url})
    except Exception:
        pass

    # Removed YouTube fallback. If no local file/DB record found return not found.
    return jsonify({'success': False, 'message': 'No local audio or DB track found for this mood.'}), 404


@app.route('/audio/<path:filename>')
def serve_audio(filename):
    """Serve audio files from data/binaural-beats-dataset for in-browser playback.

    Supports both 'audio/' and 'tracks/' subdirectories found in common datasets.

    NOTE: This route is intentionally simple. If you deploy publicly, consider adding
    authentication and range requests for large files.
    """
    base_dir = os.path.join(basedir, 'data', 'binaural-beats-dataset')

    # Hosted deploys keep the big mp3s off git: set AUDIO_BASE_URL (e.g. an R2/S3 bucket URL)
    # and any file missing locally is redirected there.
    audio_base = os.environ.get('AUDIO_BASE_URL', '').rstrip('/')
    if audio_base and '..' not in filename.replace('\\', '/').split('/') \
            and not os.path.isfile(os.path.join(base_dir, filename)):
        from urllib.parse import quote
        return redirect(f"{audio_base}/{quote(filename)}")

    if not os.path.isdir(base_dir):
        return jsonify({'success': False, 'message': 'Audio directory not found'}), 404

    # Prevent directory traversal and ensure the file resides within base_dir
    safe_filename = os.path.normpath(filename).replace('\\', '/')
    if safe_filename.startswith('../') or safe_filename.startswith('..\\') or '..' in safe_filename.split('/'):
        return jsonify({'success': False, 'message': 'Invalid filename'}), 400

    full_path = os.path.join(base_dir, safe_filename)
    try:
        full_path = os.path.normpath(full_path)
        # Ensure full_path is inside base_dir
        if not full_path.startswith(os.path.normpath(base_dir)):
            return jsonify({'success': False, 'message': 'Invalid path'}), 400
        # Serve via send_from_directory using base_dir and the relative safe path
        return send_from_directory(base_dir, safe_filename)
    except Exception:
        return jsonify({'success': False, 'message': 'File not found'}), 404


@app.route('/api/mood-audio', methods=['POST'])
def api_mood_audio():
    """Return a list of audio URLs for the requested mood, using local audio files only.

    Searches common subdirectories in the dataset ('audio/', 'tracks/').
    Supports additional filtering by frequency range, type, and sorting.

    Response: { success: True, files: [ { url: '/audio/..', filename: '...' }, ... ] }
    """
    data = request.get_json() or {}
    mood = (data.get('mood') or '').strip().lower()
    min_freq = data.get('min_frequency')
    max_freq = data.get('max_frequency')
    filter_type = (data.get('type') or '').strip().lower()
    sort_by = (data.get('sort_by') or 'default').strip().lower()
    
    if not mood:
        return jsonify({'success': False, 'message': 'Missing mood parameter'}), 400

    base_dir = os.path.join(basedir, 'data', 'binaural-beats-dataset')
    if not os.path.isdir(base_dir):
        return jsonify({'success': False, 'files': []})

    subdirs = ['audio', 'tracks']

    # Enhanced mood mapping with more comprehensive keywords and frequency ranges
    mood_keywords = {
        'calm': {
            'keywords': ['delta', 'theta', 'calm', 'relax', 'peace', 'meditat', 'sleep', 'rest'],
            'brainwaves': ['delta', 'theta'],
            'freq_range': (0.5, 8.0),  # Delta: 0.5-4 Hz, Theta: 4-8 Hz
            'priority_freq': [2.0, 4.0, 6.0]
        },
        'focus': {
            'keywords': ['alpha', 'beta', 'focus', 'concentr', 'study', 'work', 'attent', 'alert'],
            'brainwaves': ['alpha', 'beta'],
            'freq_range': (8.0, 30.0),  # Alpha: 8-12 Hz, Beta: 12-30 Hz
            'priority_freq': [10.0, 12.0, 15.0, 20.0]
        },
        'anxious': {
            'keywords': ['theta', 'delta', 'anxiety', 'stress', 'tension', 'worry', 'calm', 'sooth'],
            'brainwaves': ['theta', 'delta'],
            'freq_range': (0.5, 8.0),
            'priority_freq': [4.0, 6.0, 8.0]
        },
        'happy': {
            'keywords': ['alpha', 'gamma', 'happy', 'joy', 'uplift', 'positive', 'energiz', 'boost'],
            'brainwaves': ['alpha', 'gamma'],
            'freq_range': (8.0, 100.0),  # Alpha: 8-12 Hz, Gamma: 30+ Hz
            'priority_freq': [10.0, 40.0, 60.0]
        },
        'sad': {
            'keywords': ['theta', 'delta', 'sad', 'melanchol', 'blue', 'depress', 'comfort', 'heal'],
            'brainwaves': ['theta', 'delta'],
            'freq_range': (0.5, 8.0),
            'priority_freq': [4.0, 6.0]
        },
        'angry': {
            'keywords': ['delta', 'theta', 'anger', 'rage', 'frustrat', 'calm', 'cool', 'release'],
            'brainwaves': ['delta', 'theta'],
            'freq_range': (0.5, 8.0),
            'priority_freq': [2.0, 4.0, 6.0]
        }
    }
    
    mood_config = mood_keywords.get(mood, {
        'keywords': [mood],
        'brainwaves': [],
        'freq_range': (0.0, 1000.0),
        'priority_freq': []
    })
    keywords = mood_config['keywords']

    def parse_track_info(filename):
        # Example names:
        # Alpha_12_Hz.mp3
        # Alpha_10_Hz_Isochronic_Pulses.mp3
        # Alpha_12_Hz_Solfeggio_396_Hz.mp3
        try:
            base = os.path.splitext(filename)[0]
            parts = base.split('_')
            info = {
                'brainwave': None,
                'frequency': None,
                'type': 'pure',  # pure|isochronic|solfeggio
                'solfeggio_frequency': None,
                'label': filename,
                'length_hint': 'short'  # long for solfeggio (15m), others are usually short
            }
            if parts:
                bw = parts[0].lower()
                if bw in ('alpha','beta','delta','gamma','theta'):
                    info['brainwave'] = bw
            # Find main Hz
            for i, p in enumerate(parts):
                if p.lower() == 'hz' and i > 0:
                    try:
                        info['frequency'] = float(parts[i-1])
                    except Exception:
                        pass
            name_l = filename.lower()
            if 'isochronic_pulses' in name_l:
                info['type'] = 'isochronic'
            if 'solfeggio' in name_l:
                info['type'] = 'solfeggio'
                info['length_hint'] = 'long'
                # Extract solfeggio frequency
                try:
                    # ..._Solfeggio_396_Hz
                    idx = parts.index('Solfeggio') if 'Solfeggio' in parts else parts.index('Solfeggio'.lower())
                except Exception:
                    idx = -1
                if idx != -1 and idx + 2 < len(parts) and parts[idx+2].lower() == 'Hz'.lower():
                    try:
                        info['solfeggio_frequency'] = float(parts[idx+1])
                    except Exception:
                        pass
            # Build label
            bw_label = (info['brainwave'] or '').capitalize()
            freq_label = f"{int(info['frequency']) if info['frequency'] and info['frequency'].is_integer() else info['frequency']} Hz" if info['frequency'] else ''
            suffix = ''
            if info['type'] == 'isochronic':
                suffix = ' (Isochronic)'
            elif info['type'] == 'solfeggio':
                sf = f" {int(info['solfeggio_frequency']) if info['solfeggio_frequency'] and float(info['solfeggio_frequency']).is_integer() else info['solfeggio_frequency']} Hz" if info['solfeggio_frequency'] else ''
                suffix = f" (Solfeggio{sf})"
            pretty = ' '.join([s for s in [bw_label, freq_label] if s]).strip() + suffix
            info['label'] = pretty or filename
            return info
        except Exception:
            return {
                'brainwave': None,
                'frequency': None,
                'type': 'pure',
                'solfeggio_frequency': None,
                'label': filename,
                'length_hint': 'short'
            }

    matches = []
    for sub in subdirs:
        d = os.path.join(base_dir, sub)
        if not os.path.isdir(d):
            continue
        try:
            for fn in os.listdir(d):
                name_l = fn.lower()
                if not name_l.endswith(('.mp3', '.wav', '.m4a', '.flac')):
                    continue
                # Enhanced matching logic
                meta = parse_track_info(fn)
                should_include = False
                
                # Check keyword matching
                if any(kw in name_l for kw in keywords):
                    should_include = True
                
                # Check brainwave matching
                if meta['brainwave'] and meta['brainwave'].lower() in mood_config['brainwaves']:
                    should_include = True
                
                # Check frequency range matching
                if meta['frequency'] and mood_config['freq_range']:
                    freq = meta['frequency']
                    min_range, max_range = mood_config['freq_range']
                    if min_range <= freq <= max_range:
                        should_include = True
                
                if should_include:
                    # Apply additional filters
                    if min_freq is not None and meta['frequency'] and meta['frequency'] < min_freq:
                        continue
                    if max_freq is not None and meta['frequency'] and meta['frequency'] > max_freq:
                        continue
                    if filter_type and filter_type != 'all' and meta['type'] != filter_type:
                        continue
                        
                    rel = f"{sub}/{fn}"
                    # Ensure URL uses forward slashes
                    rel_url = rel.replace('\\', '/').replace('\\', '/')
                    
                    # Calculate relevance score for sorting
                    relevance_score = 0
                    if meta['brainwave'] and meta['brainwave'].lower() in mood_config['brainwaves']:
                        relevance_score += 10
                    if meta['frequency'] and meta['frequency'] in mood_config['priority_freq']:
                        relevance_score += 5
                    if any(kw in name_l for kw in keywords[:3]):  # Prioritize first 3 keywords
                        relevance_score += 3
                        
                    matches.append({
                        'url': url_for('serve_audio', filename=rel_url),
                        'filename': fn,
                        'label': meta['label'],
                        'length_hint': meta['length_hint'],
                        'type': meta['type'],
                        'brainwave': meta['brainwave'],
                        'frequency': meta['frequency'],
                        'solfeggio_frequency': meta['solfeggio_frequency'],
                        'relevance_score': relevance_score
                    })
        except Exception as e:
            logger.debug(f"Failed to scan directory {d}: {e}")

    # Enhanced sorting logic
    def get_sort_key(item, sort_method):
        if sort_method == 'relevance':
            return (-item.get('relevance_score', 0), item.get('label', 'zzz'))
        elif sort_method == 'frequency_asc':
            return (item.get('frequency') or 1e9, item.get('label', 'zzz'))
        elif sort_method == 'frequency_desc':
            return (-(item.get('frequency') or 0), item.get('label', 'zzz'))
        elif sort_method == 'duration':
            # Solfeggio tracks are typically longer
            length_priority = {'solfeggio': 0, 'isochronic': 1, 'pure': 2}
            return (length_priority.get(item.get('type', 'pure'), 2), item.get('label', 'zzz'))
        elif sort_method == 'brainwave':
            brainwave_order = {'delta': 0, 'theta': 1, 'alpha': 2, 'beta': 3, 'gamma': 4}
            return (brainwave_order.get(item.get('brainwave', 'unknown'), 5), item.get('frequency', 0))
        else:  # default
            # Default: relevance first, then type, then brainwave, then frequency
            type_rank = {'solfeggio': 0, 'isochronic': 1, 'pure': 2}
            return (
                -item.get('relevance_score', 0),
                type_rank.get(item.get('type') or 'pure', 2),
                item.get('brainwave') or 'zzzz',
                item.get('frequency') or 1e9
            )
    
    matches.sort(key=lambda x: get_sort_key(x, sort_by))

    return jsonify({'success': True, 'files': matches})


@app.route('/music')
def music():
    """Render the music discovery page which allows users to pick a mood and play binaural beats."""
    return render_template('music.html')


@app.route('/api/log-mood-selection', methods=['POST'])
@limiter.limit('30 per hour')
def api_log_mood_selection():
    """Log a user's mood music selection for analytics/debugging.

    Accepts JSON: { mood: 'calm', query: '...', video: 'youtube_id' }
    Logging is appended to `mood_selections.log` and written to the application logger.
    """
    if not request.is_json:
        return jsonify({'success': False, 'message': 'Request must be JSON'}), 400

    data = request.get_json() or {}
    mood = data.get('mood')
    query = data.get('query')
    video = data.get('video')
    user_id = session.get('user_id')

    if not mood:
        return jsonify({'success': False, 'message': 'Missing mood field'}), 400

    log_entry = {
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'user_id': user_id,
        'mood': mood,
        'query': query,
        'video': video,
        'ip': request.remote_addr
    }

    try:
        # Log via application logger for centralized logs
        logger.info(f"Mood selection: {log_entry}")

        # Also append to a simple file for quick analytics without DB migration
        try:
            with open(os.path.join(basedir, 'instance', 'mood_selections.log'), 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception as file_err:
            logger.debug(f"Failed to write mood selection to file: {file_err}")

        return jsonify({'success': True, 'message': 'Selection logged'})
    except Exception as e:
        logger.error(f"Error logging mood selection: {e}")
        return jsonify({'success': False, 'message': 'Failed to log selection'}), 500

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
            if score >= 4:
                return {'severity': 'Positive', 'color': 'green'}
            elif score >= 3:
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
    """Delete one of the session user's voice logs and its audio file."""
    from models import VoiceLog
    voice_log = VoiceLog.query.filter_by(id=voice_log_id, user_id=session['user_id']).first()
    if not voice_log:
        return jsonify({'success': False, 'message': 'Voice log not found'}), 404
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], os.path.basename(voice_log.filename))
    try:
        db.session.delete(voice_log)
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("Error deleting voice log")
        return jsonify({'success': False, 'message': 'Failed to delete voice log'}), 500
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except OSError:
        logger.warning("Could not delete audio file")
    return jsonify({'success': True, 'message': 'Voice log deleted successfully'})


def classify_emotion(audio_features):
    """Rough emotion guess from pitch/energy/zero-crossing features (heuristic, not a clinical signal)."""
    pitch = audio_features.get('mean_pitch', 0)
    energy = audio_features.get('mean_energy', 0)
    zcr = audio_features.get('mean_zcr', 0)
    if pitch > 200 and energy > 0.1:
        return 'happy'
    if pitch and pitch < 150 and energy < 0.05:
        return 'sad'
    if zcr > 0.1:
        return 'stressed'
    if 150 <= pitch <= 200 and 0.05 <= energy <= 0.1:
        return 'calm'
    return 'neutral'


def get_ai_voice_emotion_analysis(file_path, audio_features, basic_emotion='neutral'):
    """Return "emotion: explanation". Uses Gemini when a key is set, else the acoustic guess."""
    fallback = f"{basic_emotion.title()}: Estimated from the sound of your recording only."
    if not os.environ.get('GEMINI_API_KEY'):
        return fallback
    try:
        text = ai_service.analyze_voice_emotion('', audio_features) or ''
        m = re.search(r'EMOTION:\s*([A-Za-z]+)', text)
        if m:
            insight = re.search(r'INSIGHTS:\s*(.+)', text)
            return f"{m.group(1)}: {insight.group(1).strip() if insight else 'AI analysis of your recording.'}"[:500]
    except Exception:
        logger.warning("AI voice analysis unavailable")
    return fallback


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

    file_path = None
    try:
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        ext = audio_file.filename.rsplit('.', 1)[1].lower()
        filename = secure_filename(f"{user_id}_{uuid.uuid4()}.{ext}")
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        audio_file.save(file_path)

        audio_features = {}
        emotion = 'neutral'
        if LIBROSA_AVAILABLE:
            try:
                y, sr = librosa.load(file_path, duration=120)  # max 2 minutes
                audio_features = {'duration': len(y) / sr, 'sample_rate': sr}
                pitches, _ = librosa.piptrack(y=y, sr=sr)
                pitch_values = pitches[pitches > 0]
                if len(pitch_values) > 0:
                    audio_features['mean_pitch'] = float(np.mean(pitch_values))
                    audio_features['pitch_std'] = float(np.std(pitch_values))
                audio_features['mean_energy'] = float(np.mean(librosa.feature.rms(y=y)))
                audio_features['mean_zcr'] = float(np.mean(librosa.feature.zero_crossing_rate(y)))
                audio_features['mean_spectral_centroid'] = float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr)))
                emotion = classify_emotion(audio_features)
            except Exception:
                logger.warning("Audio feature extraction failed; using neutral")

        analysis = get_ai_voice_emotion_analysis(file_path, audio_features, emotion)
        voice_log = VoiceLog(
            user_id=user_id,
            filename=filename,
            emotion=analysis.split(':')[0].strip().lower()[:30] or emotion,
            audio_features=audio_features,
            ai_analysis=analysis,
        )
        db.session.add(voice_log)
        db.session.commit()
        award_points(user_id, 20, 'voice_log')

        return jsonify({
            'success': True,
            'message': 'Voice log uploaded and processed successfully!',
            'voice_log': {'id': voice_log.id, 'emotion': voice_log.emotion, 'audio_features': audio_features}
        })
    except Exception:
        db.session.rollback()
        logger.exception("Error uploading voice file")
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        return jsonify({'success': False, 'message': 'Failed to process voice recording'}), 500


# Health check endpoint for monitoring
@app.route('/health')
def health_check():
    """Health check endpoint for monitoring and load balancers."""
    try:
        # Test database connection
        db.session.execute(db.text('SELECT 1'))
        db_status = 'healthy'
    except Exception as e:
        logger.error(f"Health check DB error: {e}")
        db_status = 'unhealthy'

    # Test AI services
    try:
        ai_check = ai_service.check_api_status()
        ai_status = 'available' if ai_check.get('model_available') else 'unavailable'
    except Exception as e:
        logger.error(f"Health check AI error: {e}")
        ai_status = 'error'

    return jsonify({
        'status': 'healthy',
        'database': db_status,
        'ai_service': ai_status,
        'timestamp': datetime.now().isoformat()
    }), 200

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
        session.modified = True
        logger.info("Session created for user.")
        
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