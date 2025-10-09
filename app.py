import logging

# Configure basic logging early to handle import errors
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import json
import re

from werkzeug.utils import secure_filename
import uuid

import os
from datetime import datetime, timedelta, date, timezone
from functools import wraps
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError

from dotenv import load_dotenv
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

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_from_directory
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import word_tokenize
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
from flask_session import Session
from flask_compress import Compress
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect, CSRFError
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache

from ai_service import ai_service
from extensions import db, migrate, flask_session, compress, csrf
from models import User, Assessment, DigitalDetoxLog, RPMData, Gamification, ClinicalNote, InstitutionalAnalytics, Appointment, Goal, Medication, MedicationLog, BreathingExerciseLog, YogaLog, MusicTherapyLog, ProgressRecommendation, get_user_wellness_trend, get_institutional_summary, Notification
from models import BlogPost, BlogComment, BlogLike, BlogInsight, Prescription, MoodLog  # Ensure BlogPost and related models are imported

# In-memory storage for patient features (no database required)
patient_journal_entries = {}  # user_id -> list of journal entries
patient_voice_logs_data = {}       # user_id -> list of voice log entries

# File upload configuration
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'wav', 'mp3', 'ogg'}
ALLOWED_MIME_TYPES = {
    'image/png', 'image/jpeg', 'image/jpg', 'image/gif',
    'audio/wav', 'audio/mpeg', 'audio/ogg'
}

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

socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize rate limiter with simple storage backend for development
# For production, consider Redis or another persistent storage
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"  # Use memory storage but suppress warning for development
)

# Initialize caching
cache = Cache(app, config={'CACHE_TYPE': 'simple'})

# Configure session BEFORE initializing extensions
app.secret_key = os.getenv('SECRET_KEY', 'supersecretkey')  # Use environment variable or fallback
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)  # Extended session lifetime
app.config['SESSION_COOKIE_SECURE'] = os.getenv('FLASK_ENV') == 'production'  # True in production with HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Prevent XSS attacks
app.config['SESSION_COOKIE_SAMESITE'] = 'Strict'  # Prevent CSRF attacks
app.config['SESSION_FILE_DIR'] = os.path.join(os.getcwd(), 'flask_session')
app.config['WTF_CSRF_TIME_LIMIT'] = 604800  # 7 days, for prototype convenience

# Initialize database extensions AFTER session configuration
from extensions import init_extensions
init_extensions(app)

from models import *

# Enable CSRF protection for security
csrf.init_app(app)

# Add Content Security Policy headers for XSS protection
@app.after_request
def add_security_headers(response):
    """Add security headers to all responses"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    
    # Content Security Policy
    csp = (
        "default-src * 'unsafe-inline' 'unsafe-eval' data: blob:; "
        "script-src * 'unsafe-inline' 'unsafe-eval' data: blob:; "
        "style-src * 'unsafe-inline' 'unsafe-eval' data: blob:; "
        "font-src * 'unsafe-inline' 'unsafe-eval' data: blob:; "
        "img-src * 'unsafe-inline' 'unsafe-eval' data: blob:; "
        "connect-src * 'unsafe-inline' 'unsafe-eval' data: blob:; "
        "frame-src * 'unsafe-inline' 'unsafe-eval' data: blob:; "
    )
    response.headers['Content-Security-Policy'] = csp
    return response

# Secure CSRF error handler
@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    logger.warning(f"CSRF error for user {session.get('user_email', 'anonymous')}: {request.endpoint}")
    flash('Session expired or invalid request. Please try again.', 'error')
    return redirect(url_for('login'))

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
    if request.endpoint == 'patient_journal' and request.method == 'POST':
        flash('Invalid request. Please check your input and try again.', 'error')
        return redirect(url_for('patient_journal'))
    flash('Invalid request. Please try again.', 'error')
    return redirect(url_for('index'))

@app.errorhandler(500)
def handle_internal_error(e):
    logger.error(f"Internal server error: {e}")
    # For journal-related requests, redirect back to journal instead of index
    if request.endpoint == 'patient_journal' and request.method == 'POST':
        flash('An error occurred while saving your journal entry. Please try again.', 'error')
        return redirect(url_for('patient_journal'))
    flash('An internal error occurred. Please try again later.', 'error')
    return redirect(url_for('index'))

# Yoga Video Library Page (correct placement)
@app.route('/yoga-videos')
def yoga_videos():
    return render_template('yoga_videos.html')


# Cached blog insights function
@cache.memoize(timeout=300)  # Cache for 5 minutes
def get_blog_insights():
    return {
        'total_posts': BlogPost.query.count(),
        'total_likes': 0,
        'total_comments': 0,
        'total_views': 0,
        'most_popular_post': None
    }

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_file_security(file):
    """Comprehensive file validation for security"""
    if not file or not file.filename:
        return False, "No file provided"
    
    # Check file extension
    if not allowed_file(file.filename):
        return False, "Invalid file type. Only PNG, JPG, JPEG, and GIF files are allowed."
    
    # Check file size (additional check beyond Flask's MAX_CONTENT_LENGTH)
    file.seek(0, 2)  # Seek to end
    file_size = file.tell()
    file.seek(0)  # Reset to beginning
    
    if file_size > 5 * 1024 * 1024:  # 5MB
        return False, "File too large. Maximum size is 5MB."
    
    # Check MIME type
    file_mime = file.content_type
    if file_mime not in ALLOWED_MIME_TYPES:
        return False, "Invalid file type detected."
    
    # Check for path traversal attempts
    if '..' in file.filename or '/' in file.filename or '\\' in file.filename:
        return False, "Invalid filename detected."
    
    return True, "File is valid"

def is_strong_password(password):
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r"[0-9]", password):
        return False, "Password must contain at least one number."
    if not re.search(r"[\W_]", password):
        return False, "Password must contain at least one special character."
    return True, ""

# Import gamification functions
from gamification_engine import award_points

def normalize_institution_name(institution_name):
    """Normalize institution name for better matching."""
    if not institution_name:
        return ''
    return institution_name.lower().strip()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify(success=False, message='Authentication required'), 401
            return redirect(url_for('login'))
        
        # Refresh session on activity to prevent unexpected timeouts
        session.permanent = True
        session.modified = True
        return f(*args, **kwargs)
    return decorated_function

# Favicon route to prevent 404 errors
@app.route('/favicon.ico')
def favicon():
    try:
        return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')
    except FileNotFoundError:
        # Return empty response for missing favicon to avoid 404
        return '', 204

# Blog Delete Route (placed after app, login_required, and abort are defined)
@app.route('/blog/<int:post_id>/delete', methods=['POST'])
@login_required
def blog_delete(post_id):
    post = BlogPost.query.get_or_404(post_id)
    # Optional: Only allow author or admin to delete
    if post.author_id != session.get('user_id'):
        abort(403)
    try:
        db.session.delete(post)
        db.session.commit()
        flash('Blog post deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Failed to delete blog post.', 'error')
    return redirect(url_for('blog_list'))

def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_role' not in session or session['user_role'] != role:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify(success=False, message='Insufficient permissions'), 403
                flash('Access denied. Insufficient permissions.', 'error')
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.route('/')
def index():
    # Get blog insights for the landing page
    try:
        blog_insights = get_blog_insights()

        # Get featured/recent blog posts for display
        featured_posts = BlogPost.query.filter_by(
            is_published=True,
            is_featured=True
        ).order_by(BlogPost.created_at.desc()).limit(3).all()

        # If no featured posts, get recent ones
        if not featured_posts:
            featured_posts = BlogPost.query.filter_by(
                is_published=True
            ).order_by(BlogPost.created_at.desc()).limit(3).all()

        # Student-focused homepage theme data
        landing_theme = {
            "hero_title": "Welcome to MindFull Horizon",
            "hero_subtitle": "Empowering Students for Better Mental Wellness",
            "hero_message": "Track your mood, set goals, join wellness challenges, and connect with campus providers. Your journey to a healthier mind starts here!",
            "features": [
                {
                    "title": "Daily Mood Tracker",
                    "desc": "Check in with your feelings and see your progress over time."
                },
                {
                    "title": "Digital Detox",
                    "desc": "Reduce screen time and boost your academic and social life."
                },
                {
                    "title": "Gamified Wellness",
                    "desc": "Earn points, badges, and rewards for healthy habits and activities."
                }
            ]
        }

        # FAQ section data
        faqs = [
            {
                "question": "What is MindFull Horizon?",
                "answer": "MindFull Horizon is a student wellness platform designed to help you track your mood, set goals, and improve your mental health."
            },
            {
                "question": "How do I join wellness challenges?",
                "answer": "Sign up and visit your dashboard to participate in ongoing wellness challenges and earn rewards."
            },
            {
                "question": "Is my data private?",
                "answer": "Yes, your data is securely stored and only accessible to you and authorized campus providers."
            },
            {
                "question": "Can I connect with campus counselors?",
                "answer": "Absolutely! Use the telehealth feature to book appointments and chat with campus counselors."
            }
        ]

    except Exception as e:
        logger.error(f"Error getting blog insights for homepage: {e}")
        blog_insights = None
        featured_posts = []
        landing_theme = {
            "hero_title": "Welcome to MindFull Horizon",
            "hero_subtitle": "Empowering Students for Better Mental Wellness",
            "hero_message": "Track your mood, set goals, join wellness challenges, and connect with campus providers. Your journey to a healthier mind starts here!",
            "features": []
        }
        faqs = []

    return render_template(
        'index.html',
        blog_insights=blog_insights,
        featured_posts=featured_posts,
        landing_theme=landing_theme,
        faqs=faqs,
        datetime=datetime
    )

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")  # Rate limit login attempts
def login():
    if request.method == 'POST':
        # Use .get to avoid KeyError and normalize inputs
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        role = (request.form.get('role') or '').strip().lower()

        if not email or not password or not role:
            flash('Please provide email, password, and select a role.', 'error')
            return render_template('login.html')

        user = User.query.filter_by(email=email).first()

        if not user:
            flash('No account found with that email. Please sign up first.', 'error')
            return render_template('login.html')

        if user.role.lower() != role:
            flash('Selected role does not match account role. Please choose the correct role.', 'error')
            return render_template('login.html')

        if not user.check_password(password):
            flash('Invalid credentials. Please check your email and password.', 'error')
            return render_template('login.html')

        # Successful login
        session.clear()
        session.permanent = True
        session['user_email'] = email
        session['user_role'] = role
        session['user_name'] = user.name
        session['user_id'] = user.id
        session['user_institution'] = user.institution
        session.modified = True

        if role == 'patient':
            return redirect(url_for('patient_dashboard'))
        else:
            return redirect(url_for('provider_dashboard'))

    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        logger.info('Signup form submitted')
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        role = request.form['role']
        institution = request.form.get('institution', 'Default University')
        logger.info(f'Form data: {name}, {email}, {role}, {institution}')

        if not all([name, email, password, confirm_password, role]):
            logger.warning('All fields are required')
            flash('All fields are required.', 'error')
            return render_template('signup.html')

        if password != confirm_password:
            logger.warning('Passwords do not match')
            flash('Passwords do not match.', 'error')
            return render_template('signup.html')

        is_strong, message = is_strong_password(password)
        if not is_strong:
            logger.warning(f'Weak password: {message}')
            flash(message, 'error')
            return render_template('signup.html')

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            logger.warning(f'Email already registered: {email}')
            flash('Email already registered. Please use a different email or login.', 'error')
            return render_template('signup.html')

        new_user = User(
            name=name,
            email=email,
            role=role,
            institution=institution
        )
        new_user.set_password(password)

        try:
            db.session.add(new_user)
            db.session.commit()
            logger.info(f'New user created: {email}')

            if role == 'patient':
                gamification = Gamification(
                    user_id=new_user.id,
                    points=0,
                    streak=0,
                    badges=[],
                    last_activity=None
                )
                db.session.add(gamification)
                db.session.commit()
                logger.info(f'Gamification profile created for user: {email}')

            flash('Registration successful! Please login with your credentials.', 'success')
            logger.info('Flash message set for successful registration')
            return redirect(url_for('login'))

        except Exception as e:
            db.session.rollback()
            logger.error(f'Error creating new user: {e}')
            flash('Registration failed. Please try again.', 'error')
            return render_template('signup.html')

    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('index'))

@app.route('/patient-dashboard')
@login_required
@role_required('patient')
def patient_dashboard():
    user_id = session['user_id']
    
    from sqlalchemy.orm import joinedload
    gamification = Gamification.query.filter_by(user_id=user_id).first()
    rpm_data = RPMData.query.filter_by(user_id=user_id).order_by(RPMData.date.desc()).first()
    all_appointments = Appointment.query.filter_by(user_id=user_id).order_by(Appointment.date.asc(), Appointment.time.asc()).all()
    latest_mood = MoodLog.query.filter_by(user_id=user_id).order_by(MoodLog.created_at.desc()).first()

    upcoming_appointments = []
    past_appointments = []

    for appt in all_appointments:
        try:
            appt_datetime_str = f"{appt.date} {appt.time}"
            appt_datetime = datetime.strptime(appt_datetime_str, '%Y-%m-%d %H:%M')
            if appt_datetime >= datetime.now():
                upcoming_appointments.append(appt)
            else:
                past_appointments.append(appt)
        except Exception as e:
            continue

    data = {
        'points': gamification.points if gamification else 0,
        'streak': gamification.streak if gamification else 0,
        'badges': gamification.badges if gamification else [],
        'rpm_data': {
            'heart_rate': rpm_data.heart_rate if rpm_data else 72,
            'sleep_duration': rpm_data.sleep_duration if rpm_data else 7.5,
            'steps': rpm_data.steps if rpm_data else 8500,
            'mood_score': rpm_data.mood_score if rpm_data else 8
        }
    }

    alerts = []
    if rpm_data:
        if rpm_data.heart_rate and rpm_data.heart_rate > 100:
            alerts.append('High heart rate detected')
        if rpm_data.sleep_duration and rpm_data.sleep_duration < 6:
            alerts.append('Insufficient sleep detected')
        if rpm_data.mood_score and rpm_data.mood_score < 4:
            alerts.append('Low mood score detected')

    return render_template('patient_dashboard.html',
                         user_name=session['user_name'],
                         user=db.session.get(User, user_id),
                         data=data,
                         alerts=alerts,
                         upcoming_appointments=upcoming_appointments,
                         past_appointments=past_appointments,
                         latest_mood=latest_mood)

@app.route('/provider-dashboard')
@login_required
@role_required('provider')
def provider_dashboard():
    institution = session.get('user_institution', 'Sample University')

    # Normalize the provider's institution for better matching
    normalized_provider_institution = normalize_institution_name(institution)

    # More flexible institution matching for better patient-provider visibility
    # Split institution name into keywords for partial matching
    institution_keywords = set(normalized_provider_institution.split())

    # Fetch all patients and filter them based on institution similarity
    from sqlalchemy.orm import joinedload
    all_patients = User.query.options(
        joinedload(User.digital_detox_logs),
        joinedload(User.clinical_notes)
    ).filter_by(role='patient').all()

    # Filter patients based on institution similarity
    patients = []
    for patient in all_patients:
        patient_institution = patient.institution or ''
        normalized_patient_institution = normalize_institution_name(patient_institution)
        patient_keywords = set(normalized_patient_institution.split())

        # Check for similarity (partial match, case-insensitive)
        if institution_keywords & patient_keywords:  # Intersection of keywords
            patients.append(patient)
        elif not patient_institution and institution == 'Sample University':
            # Include patients with no institution if provider is using default
            patients.append(patient)

    # If no patients found with flexible matching, fall back to exact match for backward compatibility
    if not patients:
        patients = User.query.options(
            joinedload(User.digital_detox_logs),
            joinedload(User.clinical_notes)
        ).filter_by(role='patient', institution=institution).all()

    caseload_data = []
    for patient in patients:
        # Get latest detox and session from already loaded relationships (prevents N+1 queries)
        latest_detox = patient.digital_detox_logs[0] if patient.digital_detox_logs else None
        latest_session = patient.clinical_notes[0] if patient.clinical_notes else None

        risk_level = 'Low'
        if latest_detox:
            if latest_detox.screen_time_hours > 8 or (latest_detox.ai_score and latest_detox.ai_score == 'Needs Improvement'):
                risk_level = 'High'
            elif latest_detox.screen_time_hours > 6 or (latest_detox.ai_score and latest_detox.ai_score == 'Good'):
                risk_level = 'Medium'

        caseload_data.append({
            'user_id': patient.id,
            'name': patient.name,
            'email': patient.email,
            'risk_level': risk_level,
            'last_session': latest_session.session_date.strftime('%Y-%m-%d') if latest_session else 'No sessions',
            'status': 'Active' if latest_detox and latest_detox.date >= date.today() - timedelta(days=7) else 'Inactive',
            'digital_score': latest_detox.ai_score if latest_detox and latest_detox.ai_score else 'No data'
        })
    
    # --- Apply client-side filters/search if provided ---
    search_q = request.args.get('q', '').strip()
    filter_risk = request.args.get('risk', '').strip()

    filtered_caseload = caseload_data
    if search_q:
        q_lower = search_q.lower()
        filtered_caseload = [c for c in filtered_caseload if q_lower in (c.get('name') or '').lower() or q_lower in (c.get('email') or '').lower()]

    if filter_risk in ('High', 'Medium', 'Low'):
        filtered_caseload = [c for c in filtered_caseload if c.get('risk_level') == filter_risk]

    # --- Simple Tasks derivation (quick wins): overdue appointments and inactive follow-ups ---
    tasks = []
    try:
        # Overdue appointments assigned to this provider (status 'booked' and date < today)
        overdue = Appointment.query.filter(Appointment.provider_id == session.get('user_id'), Appointment.status == 'booked', Appointment.date < date.today()).order_by(Appointment.date.desc()).limit(5).all()
        for o in overdue:
            tasks.append({'title': f'Complete appointment note for {o.user.name if o.user else o.user_id}', 'patient_id': o.user_id, 'due': o.date.strftime('%Y-%m-%d'), 'type': 'appointment'})
    except Exception:
        # If Appointment table/query fails for any reason, ignore tasks generation gracefully
        tasks = []

    # Also add patients with no recent activity (>7 days)
    try:
        for c in caseload_data:
            if c.get('status') == 'Inactive':
                tasks.append({'title': f'Check-in with {c.get("name")}', 'patient_id': c.get('user_id'), 'due': '', 'type': 'followup'})
    except Exception:
        pass

    institutional_data = get_institutional_summary(institution, db)
    
    bi_data = {
        'patient_engagement': institutional_data['engagement_rate'],
        'avg_session_duration': institutional_data['avg_session_duration'],
        'completion_rate': institutional_data['completion_rate'],
        'satisfaction_score': institutional_data['satisfaction_score'],
        'total_patients': institutional_data['total_users'],
        'high_risk_patients': institutional_data['high_risk_users'],
        'avg_screen_time': institutional_data['avg_screen_time']
    }
    
    return render_template('provider_dashboard.html', 
                         user_name=session['user_name'],
                         caseload=filtered_caseload,
                         bi_data=bi_data,
                         institution=institution,
                         search_q=search_q,
                         filter_risk=filter_risk,
                         tasks=tasks)


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
        return jsonify(success=False, error=str(e)), 500

@app.route('/schedule', methods=['GET', 'POST'])
@login_required
def schedule():
    if request.method == 'POST':
        date_str = request.form['date']
        time_str = request.form['time']
        appointment_type = request.form['appointment_type']
        notes = request.form.get('notes', '')
        provider_id = request.form.get('provider_id')  # Optional provider selection
        user_id = session['user_id']

        try:
            appointment_date = datetime.strptime(date_str, '%Y-%m-%d').date()

            new_appointment = Appointment(
                user_id=user_id,
                provider_id=int(provider_id) if provider_id else None,
                date=appointment_date,
                time=time_str,
                appointment_type=appointment_type,
                notes=notes,
                status='pending'  # Changed to pending for provider approval
            )
            db.session.add(new_appointment)
            db.session.commit()
            
            logger.info(f"Appointment created successfully: ID={new_appointment.id}, User={user_id}, Provider={provider_id}, Status={new_appointment.status}")
            
            # Notify provider via SocketIO if provider is selected, or all providers if none selected
            if provider_id:
                # Notify specific provider
                socketio.emit('new_appointment', {
                    'appointment_id': new_appointment.id,
                    'patient_name': session['user_name'],
                    'patient_id': user_id,
                    'date': date_str,
                    'time': time_str,
                    'type': appointment_type,
                    'notes': notes,
                    'urgency': 'normal'
                }, room=f'user_{provider_id}')
            else:
                # Notify all providers in the same institution
                user_institution = session.get('user_institution', 'Sample University')
                providers = User.query.filter_by(role='provider', institution=user_institution).all()
                for provider in providers:
                    socketio.emit('new_appointment', {
                        'appointment_id': new_appointment.id,
                        'patient_name': session['user_name'],
                        'patient_id': user_id,
                        'date': date_str,
                        'time': time_str,
                        'type': appointment_type,
                        'notes': notes,
                        'urgency': 'normal',
                        'unassigned': True
                    }, room=f'user_{provider.id}')
            
            flash(f'Appointment successfully booked for {date_str} at {time_str}!', 'success')
            return redirect(url_for('patient_dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error booking appointment: {e}', 'error')
            logger.error(f"Error booking appointment for user {user_id}: {e}")
            return redirect(url_for('schedule'))
    
    # Get list of providers for the dropdown
    user_institution = session.get('user_institution', 'Sample University')
    providers = User.query.filter_by(role='provider', institution=user_institution).all()
    
    return render_template('schedule.html', user_name=session['user_name'], providers=providers)

@app.route('/appointments/accept/<int:appointment_id>', methods=['POST'])
@login_required
@role_required('provider')
def accept_appointment(appointment_id):
    try:
        appointment = Appointment.query.get_or_404(appointment_id)
        provider_id = session['user_id']
        
        # Verify the provider has access to this appointment
        # Allow if it's assigned to this provider OR if it's unassigned (provider_id is None)
        if appointment.provider_id is not None and appointment.provider_id != provider_id:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403
        
        # If appointment was unassigned, assign it to this provider
        if appointment.provider_id is None:
            appointment.provider_id = provider_id
            
        appointment.status = 'accepted'
        appointment.updated_at = datetime.utcnow()
        db.session.commit()
        
        # Notify patient via SocketIO
        socketio.emit('appointment_accepted', {
            'appointment_id': appointment.id,
            'date': appointment.date.strftime('%Y-%m-%d'),
            'time': appointment.time,
            'type': appointment.appointment_type
        }, room=f'user_{appointment.user_id}')
        
        return jsonify({'success': True, 'message': 'Appointment accepted successfully'})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error accepting appointment {appointment_id}: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/appointments/reject/<int:appointment_id>', methods=['POST'])
@login_required
@role_required('provider')
def reject_appointment(appointment_id):
    try:
        data = request.get_json() or {}
        rejection_reason = data.get('reason', 'No reason provided')
        
        appointment = Appointment.query.get_or_404(appointment_id)
        provider_id = session['user_id']
        
        # Verify the provider has access to this appointment
        # Allow if it's assigned to this provider OR if it's unassigned (provider_id is None)
        if appointment.provider_id is not None and appointment.provider_id != provider_id:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403
        
        appointment.status = 'rejected'
        appointment.rejection_reason = rejection_reason
        appointment.updated_at = datetime.utcnow()
        db.session.commit()
        
        # Notify patient via SocketIO
        socketio.emit('appointment_rejected', {
            'appointment_id': appointment.id,
            'date': appointment.date.strftime('%Y-%m-%d'),
            'time': appointment.time,
            'type': appointment.appointment_type,
            'reason': rejection_reason
        }, room=f'user_{appointment.user_id}')
        
        return jsonify({'success': True, 'message': 'Appointment rejected successfully'})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error rejecting appointment {appointment_id}: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/appointments/provider', methods=['GET'])
@login_required
@role_required('provider')
def provider_appointments():
    """Get provider's appointments with optional status filter"""
    status_filter = request.args.get('status', 'all')
    provider_id = session['user_id']
    
    logger.info(f"Provider {provider_id} requesting appointments with status filter: {status_filter}")
    
    # Show appointments assigned to this provider OR unassigned appointments from same institution
    from sqlalchemy import or_, and_
    provider_institution = session.get('user_institution', 'Sample University')
    
    # Get user IDs from the same institution for filtering unassigned appointments
    same_institution_users = User.query.filter_by(role='patient', institution=provider_institution).with_entities(User.id).all()
    same_institution_user_ids = [user.id for user in same_institution_users]
    logger.info(f"Provider institution: {provider_institution}, Same institution patient IDs: {same_institution_user_ids}")
    
    query = Appointment.query.filter(
        or_(
            Appointment.provider_id == provider_id,
            and_(
                Appointment.provider_id.is_(None),
                Appointment.user_id.in_(same_institution_user_ids)
            )
        )
    )
    
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    
    appointments = query.order_by(Appointment.date.asc(), Appointment.time.asc()).all()
    logger.info(f"Found {len(appointments)} appointments for provider {provider_id}")
    
    appointments_data = []
    for appt in appointments:
        # Get patient's recent health data for provider decision-making
        patient_health_data = None
        if appt.user:
            # Get latest assessment
            latest_assessment = Assessment.query.filter_by(user_id=appt.user.id).order_by(Assessment.created_at.desc()).first()
            # Get latest digital detox data
            latest_detox = DigitalDetoxLog.query.filter_by(user_id=appt.user.id).order_by(DigitalDetoxLog.date.desc()).first()
            # Get latest RPM data
            latest_rpm = RPMData.query.filter_by(user_id=appt.user.id).order_by(RPMData.date.desc()).first()
            
            patient_health_data = {
                'latest_assessment': {
                    'type': latest_assessment.assessment_type if latest_assessment else None,
                    'score': latest_assessment.score if latest_assessment else None,
                    'date': latest_assessment.created_at.strftime('%Y-%m-%d') if latest_assessment else None
                } if latest_assessment else None,
                'digital_wellness': {
                    'screen_time': latest_detox.screen_time_hours if latest_detox else None,
                    'ai_score': latest_detox.ai_score if latest_detox else None,
                    'date': latest_detox.date.strftime('%Y-%m-%d') if latest_detox else None
                } if latest_detox else None,
                'vital_signs': {
                    'heart_rate': latest_rpm.heart_rate if latest_rpm else None,
                    'sleep_duration': latest_rpm.sleep_duration if latest_rpm else None,
                    'mood_score': latest_rpm.mood_score if latest_rpm else None,
                    'date': latest_rpm.date.strftime('%Y-%m-%d') if latest_rpm else None
                } if latest_rpm else None
            }

        appointments_data.append({
            'id': appt.id,
            'patient_name': appt.user.name if appt.user else 'Unknown',
            'patient_email': appt.user.email if appt.user else 'Unknown',
            'patient_id': appt.user.id if appt.user else None,
            'date': appt.date.strftime('%Y-%m-%d'),
            'time': appt.time,
            'type': appt.appointment_type,
            'status': appt.status,
            'notes': appt.notes,
            'rejection_reason': appt.rejection_reason,
            'provider_id': appt.provider_id,
            'patient_health_data': patient_health_data,
            'created_at': appt.created_at.strftime('%Y-%m-%d %H:%M:%S') if appt.created_at else None,
            'updated_at': appt.updated_at.strftime('%Y-%m-%d %H:%M:%S') if appt.updated_at else None,
            'urgency_level': 'high' if patient_health_data and patient_health_data.get('latest_assessment') and patient_health_data['latest_assessment'].get('score', 0) > 15 else 'normal'
        })
    
    logger.info(f"Returning {len(appointments_data)} appointments to provider {provider_id}")
    
    # Debug: Print the actual appointments data being returned
    for appt_data in appointments_data:
        logger.info(f"Appointment data: ID={appt_data['id']}, Patient={appt_data['patient_name']}, Status={appt_data['status']}")
    
    return jsonify({'success': True, 'appointments': appointments_data})

@app.route('/ai-documentation', methods=['GET', 'POST'])
@login_required
@role_required('provider')
def ai_documentation():
    if request.method == 'POST':
        transcript = request.form.get('transcript', '')
        patient_email = request.form.get('patient_email', '')
        
        if transcript:
            patient_context = None
            if patient_email:
                patient = User.query.filter_by(email=patient_email, role='patient').first()
                if patient:
                    recent_detox = DigitalDetoxLog.query.filter_by(user_id=patient.id).order_by(DigitalDetoxLog.date.desc()).first()
                    gamification = Gamification.query.filter_by(user_id=patient.id).first()
                    
                    patient_context = {
                        'wellness_trend': recent_detox.ai_score if recent_detox and recent_detox.ai_score else 'Not available',
                        'digital_score': recent_detox.ai_score if recent_detox else 'Not available',
                        'engagement': f'{gamification.points} points, {gamification.streak} day streak' if gamification else 'Low'
                    }
            
            clinical_note = ai_service.generate_clinical_note(transcript, patient_context)
            
            if patient_email and patient:
                clinical_note_record = ClinicalNote(
                    provider_id=session['user_id'],
                    patient_id=patient.id,
                    session_date=datetime.now(),
                    transcript=transcript,
                    ai_generated_note=clinical_note
                )
                db.session.add(clinical_note_record)
                db.session.commit()
            
            return render_template('ai_documentation.html', 
                                 user_name=session['user_name'],
                                 transcript=transcript,
                                 clinical_note=clinical_note,
                                 patient_email=patient_email)
        else:
            flash('Please provide a session transcript.', 'error')
    
    return render_template('ai_documentation.html', user_name=session['user_name'])

@app.route('/analytics')
@login_required
@role_required('provider')
def analytics():
    institution = session.get('user_institution', 'Sample University')

    # Get institutional analytics data
    institutional_data = get_institutional_summary(institution, db)

    # Get recent blog insights
    recent_blog_insights = BlogInsight.query.order_by(BlogInsight.created_at.desc()).limit(10).all()

    # Get patient engagement trends
    patients = User.query.filter_by(role='patient', institution=institution).all()
    patient_ids = [p.id for p in patients]

    # Get recent digital detox data for trends
    recent_detox = DigitalDetoxLog.query.filter(
        DigitalDetoxLog.user_id.in_(patient_ids),
        DigitalDetoxLog.date >= datetime.now().date() - timedelta(days=30)
    ).all()

    # Calculate engagement metrics
    active_patients = len(set([log.user_id for log in recent_detox]))
    total_patients = len(patients)

    # Get assessment completion rates
    assessments_30_days = Assessment.query.filter(
        Assessment.user_id.in_(patient_ids),
        Assessment.created_at >= datetime.now() - timedelta(days=30)
    ).count()

    # Get gamification stats
    gamification_stats = db.session.query(
        func.avg(Gamification.points),
        func.avg(Gamification.streak),
        func.count(Gamification.id)
    ).filter(Gamification.user_id.in_(patient_ids)).first()

    # Get wellness trend data for charts
    detox_trends = {}
    for log in recent_detox:
        date_str = log.date.strftime('%Y-%m-%d')
        if date_str not in detox_trends:
            detox_trends[date_str] = {'total_hours': 0, 'count': 0, 'ai_scores': []}
        detox_trends[date_str]['total_hours'] += log.screen_time_hours
        detox_trends[date_str]['count'] += 1
        if log.ai_score:
            detox_trends[date_str]['ai_scores'].append(log.ai_score)

    # Calculate average daily screen time and wellness scores
    chart_labels = sorted(detox_trends.keys())
    screen_time_data = []
    wellness_score_data = []

    for date in chart_labels:
        data = detox_trends[date]
        avg_screen_time = data['total_hours'] / data['count'] if data['count'] > 0 else 0
        screen_time_data.append(round(avg_screen_time, 1))

        # Convert AI scores to numeric values for averaging
        numeric_scores = []
        for score in data['ai_scores']:
            if score == 'Excellent':
                numeric_scores.append(5)
            elif score == 'Good':
                numeric_scores.append(4)
            elif score == 'Fair':
                numeric_scores.append(3)
            elif score == 'Needs Improvement':
                numeric_scores.append(2)
            elif score == 'Poor':
                numeric_scores.append(1)

        avg_wellness = sum(numeric_scores) / len(numeric_scores) if numeric_scores else 0
        wellness_score_data.append(round(avg_wellness, 1))

    analytics_data = {
        'institution': institution,
        'total_patients': total_patients,
        'active_patients': active_patients,
        'engagement_rate': round((active_patients / total_patients) * 100, 1) if total_patients > 0 else 0,
        'assessments_30_days': assessments_30_days,
        'avg_gamification_points': round(gamification_stats[0], 1) if gamification_stats[0] else 0,
        'avg_streak': round(gamification_stats[1], 1) if gamification_stats[1] else 0,
        'total_gamified_users': gamification_stats[2],
        'chart_labels': chart_labels,
        'screen_time_data': screen_time_data,
        'wellness_score_data': wellness_score_data,
        'blog_insights': recent_blog_insights,
        'institutional_data': institutional_data
    }

    return render_template('analytics.html',
                         user_name=session['user_name'],
                         analytics_data=analytics_data,
                         datetime=datetime)

@app.route('/medication', methods=['GET', 'POST'])
@login_required
@role_required('patient')
def medication():
    user_id = session['user_id']
    
    if request.method == 'POST':
        name = request.form.get('name')
        dosage = request.form.get('dosage')
        frequency = request.form.get('frequency')
        time_of_day = request.form.get('time_of_day')

        if not name or not dosage or not frequency:
            flash('Medication name, dosage, and frequency are required.', 'error')
        else:
            new_medication = Medication(
                user_id=user_id,
                name=name,
                dosage=dosage,
                frequency=frequency,
                time_of_day=time_of_day
            )
            db.session.add(new_medication)
            db.session.commit()
            flash(f'{name} has been added to your tracker.', 'success')
        return redirect(url_for('medication'))

    medications = Medication.query.filter_by(user_id=user_id, is_active=True).all()
    
    today_start = datetime.combine(date.today(), datetime.min.time())
    today_end = datetime.combine(date.today(), datetime.max.time())
    
    todays_logs = MedicationLog.query.filter(
        MedicationLog.user_id == user_id,
        MedicationLog.taken_at >= today_start,
        MedicationLog.taken_at <= today_end
    ).all()
    
    logged_med_ids = {log.medication_id for log in todays_logs}
    
    today = date.today()
    return render_template('medication.html', 
                         user_name=session['user_name'], 
                         medications=medications,
                         logged_med_ids=logged_med_ids,
                         moment=datetime,
                         today=today)

@app.route('/log-medication', methods=['POST'])
@login_required
@role_required('patient')
def log_medication():
    user_id = session['user_id']
    medication_id = request.form.get('medication_id')
    
    if medication_id:
        today_start = datetime.combine(date.today(), datetime.min.time())
        existing_log = MedicationLog.query.filter(
            MedicationLog.medication_id == medication_id,
            MedicationLog.user_id == user_id,
            MedicationLog.taken_at >= today_start
        ).first()

        if not existing_log:
            new_log = MedicationLog(user_id=user_id, medication_id=medication_id)
            db.session.add(new_log)
            db.session.commit()
            award_points(user_id, 10, 'log_medication')
            return jsonify({'success': True, 'message': 'Medication logged successfully!'})
        else:
            return jsonify({'success': False, 'message': 'Medication already logged for today.'})
            
    return jsonify({'success': False, 'message': 'Invalid request.'})

@app.route('/breathing', methods=['GET', 'POST'])
@login_required
@role_required('patient')
def breathing():
    user_id = session['user_id']

    if request.method == 'POST':
        exercise_name = request.form.get('exercise_name')
        duration_minutes = request.form.get('duration_minutes')

        if not exercise_name or not duration_minutes:
            flash('Exercise name and duration are required.', 'error')
        else:
            try:
                new_log = BreathingExerciseLog(
                    user_id=user_id,
                    exercise_name=exercise_name,
                    duration_minutes=int(duration_minutes),
                    created_at=datetime.now(timezone.utc)
                )
                db.session.add(new_log)
                db.session.commit()
                award_points(user_id, 20, 'breathing_exercise')
                flash(f'Your {exercise_name} session has been logged!', 'success')
            except ValueError:
                flash('Invalid duration. Please enter a number.', 'error')
        return redirect(url_for('breathing'))

    recent_logs = BreathingExerciseLog.query.filter_by(user_id=user_id).order_by(BreathingExerciseLog.created_at.desc()).limit(10).all()
    
    all_logs = BreathingExerciseLog.query.filter_by(user_id=user_id).all()
    total_sessions = len(all_logs)
    total_minutes = sum(log.duration_minutes for log in all_logs)
    
    streak = 0
    if all_logs:
        dates = sorted([log.created_at.date() for log in all_logs], reverse=True)
        current_date = date.today()
        for i, log_date in enumerate(dates):
            if log_date == current_date - timedelta(days=i):
                streak += 1
            else:
                break
    
    stats = {
        'total_sessions': total_sessions,
        'total_minutes': total_minutes,
        'streak': streak
    }
    
    return render_template('breathing.html', 
                         user_name=session['user_name'],
                         recent_logs=recent_logs,
                         stats=stats)

@app.route('/yoga', methods=['GET', 'POST'])
@login_required
@role_required('patient')
def yoga():
    user_id = session['user_id']

    if request.method == 'POST':
        session_name = request.form.get('session_name')
        duration_minutes = request.form.get('duration_minutes')

        if not session_name or not duration_minutes:
            flash('Session name and duration are required.', 'error')
        else:
            try:
                new_log = YogaLog(
                    user_id=user_id,
                    session_name=session_name,
                    duration_minutes=int(duration_minutes),
                    created_at=datetime.now(timezone.utc)
                )
                db.session.add(new_log)
                db.session.commit()
                award_points(user_id, 20, 'yoga_session')
                flash(f'Your {session_name} session has been logged!', 'success')
            except ValueError:
                flash('Invalid duration. Please enter a number.', 'error')
        return redirect(url_for('yoga'))

    recent_logs = YogaLog.query.filter_by(user_id=user_id).order_by(YogaLog.created_at.desc()).limit(10).all()
    
    all_logs = YogaLog.query.filter_by(user_id=user_id).all()
    total_sessions = len(all_logs)
    total_minutes = sum(log.duration_minutes for log in all_logs)
    avg_duration = round(total_minutes / total_sessions, 1) if total_sessions > 0 else 0
    
    streak = 0
    if all_logs:
        dates = sorted([log.created_at.date() for log in all_logs], reverse=True)
        current_date = date.today()
        for i, log_date in enumerate(dates):
            if log_date == current_date - timedelta(days=i):
                streak += 1
            else:
                break
    
    stats = {
        'total_sessions': total_sessions,
        'total_minutes': total_minutes,
        'streak': streak,
        'avg_duration': avg_duration
    }
    
    return render_template('yoga.html', 
                         user_name=session['user_name'],
                         recent_logs=recent_logs,
                         stats=stats)

@app.route('/telehealth_session/<int:user_id>')
@login_required
def telehealth_session(user_id):
    patient = User.query.get_or_404(user_id)
    return render_template('telehealth.html', 
                           user_name=session['user_name'],
                           patient_id=patient.id,
                           patient_name=patient.name)

@app.route('/telehealth')
@login_required
def telehealth():
    return render_template('telehealth.html', user_name=session['user_name'])

@app.route('/digital-detox')
@login_required
@role_required('patient')
def digital_detox():
    user_id = session['user_id']
    
    screen_time_logs = DigitalDetoxLog.query.filter_by(user_id=user_id).order_by(DigitalDetoxLog.date.desc()).limit(30).all()
    
    screen_time_log = []
    for log in screen_time_logs:
        screen_time_log.append({
            'date': log.date.strftime('%Y-%m-%d'),
            'hours': log.screen_time_hours,
            'academic_score': log.academic_score,
            'social_interactions': log.social_interactions,
            'ai_score': log.ai_score
        })
    
    avg_screen_time = 0
    if screen_time_log:
        total_hours = sum(log['hours'] for log in screen_time_log)
        avg_screen_time = round(total_hours / len(screen_time_log), 1)

    latest_log = DigitalDetoxLog.query.filter_by(user_id=user_id).order_by(DigitalDetoxLog.date.desc()).first()
    score = None
    suggestion = None
    if latest_log:
        score = latest_log.ai_score
        suggestion = latest_log.ai_suggestion
    
    return render_template('digital_detox.html', 
                         user_name=session['user_name'],
                         screen_time_log=screen_time_log,
                         avg_screen_time=avg_screen_time,
                         score=score,
                         suggestion=suggestion)

@app.route('/progress')
@login_required
@role_required('patient')
def progress():
    try:
        user_id = session['user_id']
        goals = Goal.query.filter_by(user_id=user_id).all()
        
        achievements = [goal.title for goal in goals if goal.status == 'completed']
        
        assessments = Assessment.query.filter_by(user_id=user_id).order_by(Assessment.created_at.desc()).all()
        
        latest_gad7 = next((a for a in assessments if a.assessment_type == 'GAD-7'), None)
        latest_phq9 = next((a for a in assessments if a.assessment_type == 'PHQ-9'), None)
        latest_mood = next((a for a in assessments if a.assessment_type == 'Daily Mood'), None)

        mood_assessments = sorted([a for a in assessments if a.assessment_type == 'Daily Mood'], key=lambda x: x.created_at)[-30:]
        mood_data = [{'date': m.created_at.strftime('%Y-%m-%d'), 'score': m.score} for m in mood_assessments]
        
        gad7_assessments = sorted([a for a in assessments if a.assessment_type == 'GAD-7'], key=lambda x: x.created_at)
        phq9_assessments = sorted([a for a in assessments if a.assessment_type == 'PHQ-9'], key=lambda x: x.created_at)

        assessment_chart_labels = sorted(list(set([a.created_at.strftime('%Y-%m-%d') for a in gad7_assessments + phq9_assessments])))
        assessment_chart_gad7_data = [next((a.score for a in gad7_assessments if a.created_at.strftime('%Y-%m-%d') == date), None) for date in assessment_chart_labels]
        assessment_chart_phq9_data = [next((a.score for a in phq9_assessments if a.created_at.strftime('%Y-%m-%d') == date), None) for date in assessment_chart_labels]

        days_since_assessment = (datetime.now() - assessments[0].created_at).days if assessments else 'N/A'
        
        user_data_for_ai = {
            'gad7_score': latest_gad7.score if latest_gad7 else 'N/A',
            'phq9_score': latest_phq9.score if latest_phq9 else 'N/A',
            'wellness_score': 'calculating...',
            'completed_goals': len(achievements),
            'total_goals': len(goals),
            'days_since_assessment': days_since_assessment
        }
        
        user = db.session.get(User, user_id)
        if not user:
            flash('User not found. Please log in again.', 'error')
            return redirect(url_for('login'))

        last_assessment_at = user.last_assessment_at

        latest_recommendation = ProgressRecommendation.query.filter_by(user_id=user_id).order_by(ProgressRecommendation.created_at.desc()).first()

        ai_recommendations = None
        if latest_recommendation and last_assessment_at and latest_recommendation.created_at > last_assessment_at:
            ai_recommendations = latest_recommendation.recommendations
        
        if not ai_recommendations:
            try:
                ai_recommendations = ai_service.generate_progress_recommendations(user_data_for_ai)
                new_recommendation = ProgressRecommendation(
                    user_id=user_id,
                    recommendations=ai_recommendations
                )
                db.session.add(new_recommendation)
                db.session.commit()
            except Exception as ai_error:
                logger.error(f"AI service error in progress page: {ai_error}")
                ai_recommendations = {
                    'summary': 'Your progress data has been recorded.',
                    'recommendations': ['Continue with your current mental health routine.'],
                    'priority_actions': []
                }

        scores_to_average = []
        if latest_gad7 and latest_gad7.score is not None:
            scores_to_average.append(10 - (latest_gad7.score / 21 * 9))
        if latest_phq9 and latest_phq9.score is not None:
            scores_to_average.append(10 - (latest_phq9.score / 27 * 9))
        if latest_mood and latest_mood.score is not None:
            scores_to_average.append(latest_mood.score)

        overall_wellness_score = round(sum(scores_to_average) / len(scores_to_average), 1) if scores_to_average else 0
        user_data_for_ai['wellness_score'] = overall_wellness_score

        return render_template('progress.html', 
                             user_name=session['user_name'], 
                             goals=goals, 
                             achievements=achievements,
                             latest_gad7=latest_gad7,
                             latest_phq9=latest_phq9,
                             overall_wellness_score=overall_wellness_score,
                             mood_data=mood_data,
                             assessment_chart_labels=assessment_chart_labels,
                             assessment_chart_gad7_data=assessment_chart_gad7_data,
                             assessment_chart_phq9_data=assessment_chart_phq9_data,
                             ai_recommendations=ai_recommendations)
    except Exception as e:
        logger.exception(f"An error occurred in the progress route: {e}")
        return "An internal error occurred. Please try again later.", 500

@app.route('/goals', methods=['GET', 'POST'])
@login_required
@role_required('patient')
def goals():
    user_id = session['user_id']
    
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description', '')
        category = request.form.get('category', 'mental_health')
        priority = request.form.get('priority', 'medium')
        target_value = request.form.get('target_value')
        unit = request.form.get('unit', '')
        target_date = request.form.get('target_date')

        if not title:
            flash('Goal title is required.', 'error')
        else:
            try:
                parsed_target_date = None
                if target_date:
                    parsed_target_date = datetime.strptime(target_date, '%Y-%m-%d').date()

                new_goal = Goal(
                    user_id=user_id,
                    title=title,
                    description=description,
                    category=category,
                    priority=priority,
                    status='active',
                    target_value=float(target_value) if target_value and target_value.strip() else None,
                    current_value=0.0,
                    unit=unit,
                    target_date=parsed_target_date,
                    start_date=datetime.utcnow().date()
                )
                db.session.add(new_goal)
                db.session.commit()
                flash('Goal created successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error adding goal for user {user_id}: {e}")
                flash('Failed to create goal.', 'error')
        return redirect(url_for('goals'))

    goals = Goal.query.filter_by(user_id=user_id).all()
    return render_template('goals.html', user_name=session['user_name'], goals=goals)

@app.route('/api/assessment/questions/<assessment_type>')
@login_required
@role_required('patient')
def get_assessment_questions(assessment_type):
    try:
        # Construct the full path to the questions.json file
        questions_file_path = os.path.join(app.static_folder, 'questions.json')
        
        # Check if the file exists
        if not os.path.exists(questions_file_path):
            logger.error(f"questions.json not found at {questions_file_path}")
            return jsonify({'success': False, 'message': 'Assessment questions file not found.'}), 500

        # Load the questions from the JSON file
        with open(questions_file_path, 'r') as f:
            all_questions = json.load(f)
        
        # Get the questions for the requested assessment type
        questions = all_questions.get(assessment_type)
        
        if questions:
            return jsonify({'success': True, 'questions': questions})
        else:
            return jsonify({'success': False, 'message': 'Invalid assessment type.'}), 404
            
    except Exception as e:
        logger.error(f"Error fetching assessment questions: {e}")
        return jsonify({'success': False, 'message': 'An internal error occurred.'}), 500

@app.route('/assessment')
@login_required
@role_required('patient')
def assessment():
    try:
        user_id = session['user_id']
        assessment_objects = Assessment.query.filter_by(user_id=user_id).order_by(Assessment.created_at.desc()).all()
        
        assessments = []
        for assessment in assessment_objects:
            assessment_dict = {
                'id': assessment.id,
                'user_id': assessment.user_id,
                'assessment_type': assessment.assessment_type,
                'score': assessment.score,
                'responses': assessment.responses,
                'created_at': assessment.created_at.isoformat() if assessment.created_at else None,
                'ai_insights': {}
            }
            
            if assessment.ai_insights:
                if isinstance(assessment.ai_insights, str):
                    try:
                        assessment_dict['ai_insights'] = json.loads(assessment.ai_insights)
                    except json.JSONDecodeError:
                        assessment_dict['ai_insights'] = {}
                else:
                    assessment_dict['ai_insights'] = assessment.ai_insights
            
            assessments.append(assessment_dict)
        
        latest_insights = None
        if assessments:
            latest_insights = assessments[0].get('ai_insights')

        return render_template('assessment.html', 
                               user_name=session['user_name'], 
                               assessments=assessments,
                               latest_insights=latest_insights)
    except Exception as e:
        logger.error(f"Error in assessment route: {e}")
        flash('Error loading assessments. Please try again.', 'error')
        return render_template('assessment.html', 
                               user_name=session['user_name'], 
                               assessments=[],
                               latest_insights=None)

@app.route('/api/save-assessment', methods=['POST'])
@login_required
@role_required('patient')
@limiter.limit("5 per minute")  # Rate limit assessment saving
def api_save_assessment():
    if not request.is_json:
        return jsonify({'success': False, 'message': 'Request must be JSON'}), 400
        
    user_id = session['user_id']
    data = request.get_json()
    
    assessment_type = data.get('assessment_type')
    score = data.get('score')
    responses = data.get('responses', {})
    
    if not all([assessment_type, score is not None]):
        return jsonify({
            'success': False,
            'message': 'Missing required fields: assessment_type and score are required'
        }), 400

    ai_insights = {}
    ai_insights_generated_successfully = True
    try:
        ai_insights = ai_service.generate_assessment_insights(
            assessment_type=assessment_type,
            score=score,
            responses=responses
        )
    except Exception as e:
        logger.error(f"Error generating AI insights: {e}")
        ai_insights_generated_successfully = False
        ai_insights = {
            'summary': 'AI insights are currently unavailable. Please try again later.',
            'recommendations': [],
            'resources': []
        }

    try:
        logger.debug("Attempting to create assessment object.")
        assessment = Assessment(
            user_id=user_id,
            assessment_type=assessment_type.upper(),
            score=score,
            responses=responses,
            ai_insights=json.dumps(ai_insights) if ai_insights else None
        )
        logger.debug("Assessment object created.")
        
        db.session.add(assessment)
        logger.debug("Assessment added to session.")

        logger.debug("Awarding points and updating gamification.")
        gamification = award_points(user_id, 20, 'assessment')
        logger.debug(f"Gamification points awarded. Total points: {gamification.points}")

        logger.debug("Updating user's last assessment time.")
        user = db.session.get(User, user_id)
        if not user:
            return jsonify({
                'success': False,
                'message': 'User not found. Please log in again.'
            }), 400

        user.last_assessment_at = datetime.now(timezone.utc)
        logger.debug("User's last assessment time updated.")
        
        db.session.commit()
        logger.debug("Database commit successful.")
        
        return jsonify({
            'success': True,
            'message': 'Assessment saved successfully',
            'assessment_id': assessment.id,
            'points_earned': 20,
            'total_points': gamification.points,
            'ai_insights': ai_insights,
            'ai_insights_generated': ai_insights_generated_successfully
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error saving assessment for user {user_id}: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Failed to save assessment: {str(e)}',
            'insights': ai_insights if 'ai_insights' in locals() else None
        }), 500

@app.route('/send_prescription/<int:patient_id>', methods=['POST'])
@login_required
@role_required('provider')
def send_prescription(patient_id):
    provider_id = session['user_id']
    
    medication_name = request.form.get('medication_name')
    dosage = request.form.get('dosage')
    instructions = request.form.get('instructions')
    expiry_date_str = request.form.get('expiry_date')

    if not all([medication_name, dosage]):
        flash('Medication name and dosage are required.', 'error')
        return redirect(url_for('wellness_report', user_id=patient_id))

    expiry_date = None
    if expiry_date_str:
        try:
            expiry_date = datetime.strptime(expiry_date_str, '%Y-%m-%d')
        except ValueError:
            flash('Invalid expiry date format. Please use YYYY-MM-DD.', 'error')
            return redirect(url_for('wellness_report', user_id=patient_id))

    try:
        new_prescription = Prescription(
            provider_id=provider_id,
            patient_id=patient_id,
            medication_name=medication_name,
            dosage=dosage,
            instructions=instructions,
            expiry_date=expiry_date
        )
        db.session.add(new_prescription)
        db.session.commit()
        flash(f'Prescription for {medication_name} sent successfully to patient {patient_id}!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error sending prescription: {e}', 'error')
        logger.error(f"Error sending prescription for patient {patient_id} by provider {provider_id}: {e}")

    return redirect(url_for('wellness_report', user_id=patient_id))

@app.route('/my_prescriptions')
@login_required
@role_required('patient')
def my_prescriptions():
    user_id = session['user_id']
    prescriptions = Prescription.query.filter_by(patient_id=user_id).order_by(Prescription.issue_date.desc()).all()
    return render_template('my_prescriptions.html', 
                           user_name=session['user_name'],
                           prescriptions=prescriptions)

@app.route('/wellness-report/<int:user_id>')
@login_required
@role_required('provider')
def wellness_report(user_id):
    from datetime import datetime
    
    patient = User.query.get_or_404(user_id)
    
    gamification = Gamification.query.filter_by(user_id=user_id).first()
    
    ai_analysis = Assessment.query.filter_by(user_id=user_id).order_by(Assessment.created_at.desc()).first()
    
    digital_detox_logs = DigitalDetoxLog.query.filter_by(user_id=user_id).order_by(DigitalDetoxLog.date.desc()).limit(90).all()
    assessments = Assessment.query.filter_by(user_id=user_id).order_by(Assessment.created_at.desc()).limit(20).all()
    
    digital_detox_data = []
    for log in digital_detox_logs:
        digital_detox_data.append({
            'date': log.date.strftime('%Y-%m-%d'),
            'screen_time_hours': log.screen_time_hours,
            'academic_score': log.academic_score,
            'social_interactions': log.social_interactions,
            'ai_score': log.ai_score
        })
    
    assessment_data = []
    for assessment in assessments:
        assessment_data.append({
            'id': assessment.id,
            'assessment_type': assessment.assessment_type,
            'score': assessment.score,
            'created_at': assessment.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'ai_analysis': assessment.ai_insights
        })
    
    wellness_trend = {
        'digital_detox': digital_detox_data,
        'assessments': assessment_data
    }
    
    recent_sessions = ClinicalNote.query.filter_by(patient_id=user_id).order_by(ClinicalNote.session_date.desc()).limit(10).all()

    # Fetch RPM data for mood charting
    rpm_logs = RPMData.query.filter_by(user_id=user_id).order_by(RPMData.date.asc()).limit(90).all()
    mood_chart_labels = [log.date.strftime('%Y-%m-%d') for log in rpm_logs]
    mood_chart_data = [log.mood_score if log.mood_score else 0 for log in rpm_logs]

    # Fetch assessments for mental health charting
    mental_health_assessments = Assessment.query.filter_by(user_id=user_id).order_by(Assessment.created_at.asc()).all()
    mh_chart_labels = []
    gad7_data = []
    phq9_data = []

    for assessment in mental_health_assessments:
        date_str = assessment.created_at.strftime('%Y-%m-%d')
        if date_str not in mh_chart_labels:
            mh_chart_labels.append(date_str)
            gad7_data.append(None) # Initialize with None
            phq9_data.append(None) # Initialize with None

        idx = mh_chart_labels.index(date_str)
        if assessment.assessment_type == 'GAD-7':
            gad7_data[idx] = assessment.score
        elif assessment.assessment_type == 'PHQ-9':
            phq9_data[idx] = assessment.score

    # Filter out dates where both GAD-7 and PHQ-9 are None
    filtered_mh_chart_labels = []
    filtered_gad7_data = []
    filtered_phq9_data = []
    for i, label in enumerate(mh_chart_labels):
        if gad7_data[i] is not None or phq9_data[i] is not None:
            filtered_mh_chart_labels.append(label)
            filtered_gad7_data.append(gad7_data[i])
            filtered_phq9_data.append(phq9_data[i])

    # Prepare patient data for AI goal suggestions
    patient_data_for_ai = {
        'latest_assessment': {
            'type': ai_analysis.assessment_type,
            'score': ai_analysis.score,
            'insights': json.loads(ai_analysis.ai_insights) if ai_analysis and ai_analysis.ai_insights else None
        } if ai_analysis else None,
        'recent_goals': [{'title': g.title, 'status': g.status, 'progress': g.progress_percentage} for g in Goal.query.filter_by(user_id=user_id).order_by(Goal.created_at.desc()).limit(5).all()],
        'recent_digital_detox': [{'screen_time_hours': d.screen_time_hours, 'ai_score': d.ai_score} for d in digital_detox_logs[:5]]
    }
    ai_goal_suggestions = ai_service.generate_goal_suggestions(patient_data_for_ai)

    # Fetch medication logs for AI adherence analysis
    medication_logs = MedicationLog.query.filter_by(user_id=user_id).order_by(MedicationLog.taken_at.desc()).limit(30).all()
    medication_logs_data = [{'medication_id': log.medication_id, 'taken_at': log.taken_at.isoformat()} for log in medication_logs]
    ai_medication_adherence_insights = ai_service.analyze_medication_adherence(medication_logs_data, patient_data_for_ai)

    return render_template('wellness_report.html', 
                         user_name=session['user_name'], 
                         patient=patient,
                         gamification=gamification,
                         ai_analysis=ai_analysis,
                         wellness_trend=wellness_trend,
                         recent_sessions=recent_sessions,
                         mood_chart_labels=mood_chart_labels,
                         mood_chart_data=mood_chart_data,
                         mh_chart_labels=filtered_mh_chart_labels,
                         gad7_data=filtered_gad7_data,
                         phq9_data=filtered_phq9_data,
                         ai_goal_suggestions=ai_goal_suggestions,
                         ai_medication_adherence_insights=ai_medication_adherence_insights,
                         datetime=datetime)

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user_id = session['user_id']
    user = User.query.get(user_id)
    if not user:
        flash('User not found. Please log in again.', 'error')
        return redirect(url_for('login'))

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
                            with open(file_path, 'wb') as f:
                                file.seek(0)  # Reset file pointer
                                f.write(file.read())
                            user.profile_pic = unique_filename
                            flash('Profile picture updated successfully!', 'success')
                    except Exception as e:
                        logger.error(f"Error saving profile picture: {e}")
                        flash('Error saving profile picture.', 'error')
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

@app.route('/api/digital-detox-data')
@login_required
@role_required('patient')
def digital_detox_data():
    user_id = session['user_id']
    
    screen_time_logs = DigitalDetoxLog.query.filter_by(user_id=user_id).order_by(DigitalDetoxLog.date.desc()).limit(30).all()
    
    data = []
    for log in screen_time_logs:
        data.append({
            'date': log.date.strftime('%Y-%m-%d'),
            'hours': log.screen_time_hours,
            'academic_score': log.academic_score,
            'social_interactions': log.social_interactions,
            'ai_score': log.ai_score
        })
    
    return jsonify(data)

@app.route('/api/log-digital-detox', methods=['POST'])
@login_required
@role_required('patient')
def log_digital_detox():
    user_id = session['user_id']
    data = request.get_json()

    try:
        screen_time = float(data.get('screen_time'))
        academic_score = int(data.get('academic_score'))
        social_interactions = data.get('social_interactions')

        if not all([screen_time is not None, academic_score is not None, social_interactions]):
            return jsonify({'success': False, 'message': 'Missing required fields.'}), 400

        # Get historical data for better AI analysis
        historical_data = DigitalDetoxLog.query.filter_by(user_id=user_id).order_by(DigitalDetoxLog.date.asc()).limit(30).all()
        history_for_ai = [{'screen_time_hours': log.screen_time_hours, 'academic_score': log.academic_score} for log in historical_data]

        # Call AI service for digital detox insights
        detox_data = {
            'screen_time': screen_time,
            'academic_score': academic_score,
            'social_interactions': social_interactions
        }
        ai_analysis = ai_service.generate_digital_detox_insights(detox_data)

        # Create new log entry
        new_log = DigitalDetoxLog(
            user_id=user_id,
            date=date.today(),
            screen_time_hours=screen_time,
            academic_score=academic_score,
            social_interactions=social_interactions,
            ai_score=ai_analysis.get('ai_score', 'N/A'),
            ai_suggestion=ai_analysis.get('ai_suggestion', 'No suggestion available')
        )

        db.session.add(new_log)
        db.session.commit()

        # Award points for logging
        award_points(user_id, 15, 'digital_detox_log')

        return jsonify({
            'success': True,
            'message': 'Digital detox data logged successfully!',
            'log': {
                'date': new_log.date.strftime('%Y-%m-%d'),
                'hours': new_log.screen_time_hours,
                'academic_score': new_log.academic_score,
                'social_interactions': new_log.social_interactions,
                'ai_score': new_log.ai_score
            },
            'ai_analysis': ai_analysis
        })

    except (ValueError, TypeError) as e:
        logger.error(f"Invalid data for digital detox log: {e}")
        return jsonify({'success': False, 'message': 'Invalid data format.'}), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error logging digital detox data for user {user_id}: {e}")
        return jsonify({'success': False, 'message': 'An internal error occurred.'}), 500


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

            # Convert to response shape
            resp_map = {}
            for k in mapping:
                resp_map[k] = {'query': mood_map[k]['query'], 'videos': []}
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
def api_play_mood():
    """Attempt to play a binaural track for the requested mood.

    Priority:
      1. Look for local audio files in data/binaural-beats-dataset/audio/ whose filename contains the mood.
         If found and running on Windows, open with os.startfile (user's default music player).
      2. If DB has BinauralTrack with youtube_id for the mood, return a YouTube URL for frontend to open.
      3. Otherwise return a YouTube search URL for the mood query.

    Returns JSON: { success: True, action: 'local'|'youtube'|'search', url: optional }
    """
    data = request.get_json() or {}
    mood = (data.get('mood') or '').strip().lower()

    if not mood:
        return jsonify({'success': False, 'message': 'Missing mood parameter'}), 400

    # 1) local audio folder
    audio_dir = os.path.join(basedir, 'data', 'binaural-beats-dataset', 'audio')
    try:
        if os.path.isdir(audio_dir):
            # look for files containing the mood in filename
            for fn in os.listdir(audio_dir):
                if mood in fn.lower() and fn.lower().endswith(('.mp3', '.wav', '.m4a', '.flac')):
                    path = os.path.join(audio_dir, fn)
                    try:
                        # On Windows, this opens the default program for the file
                        if os.name == 'nt':
                            os.startfile(path)
                            return jsonify({'success': True, 'action': 'local', 'path': path})
                        else:
                            # Non-blocking attempt for other OSes
                            import subprocess
                            subprocess.Popen(['xdg-open' if os.name == 'posix' else 'open', path])
                            return jsonify({'success': True, 'action': 'local', 'path': path})
                    except Exception as e:
                        logger.debug(f"Failed to open local audio file {path}: {e}")

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
                    rel_url = rel.replace('\\\\', '/').replace('\\', '/')
                    
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

@app.route('/api/goals', methods=['GET', 'POST'])
@login_required
@role_required('patient')
@limiter.limit("20 per minute")  # Rate limit goal operations
def handle_goals():
    user_id = session['user_id']

    if request.method == 'POST':
        try:
            data = request.get_json()
            title = data.get('title')
            description = data.get('description')
            category = data.get('category')
            target_value = data.get('target_value')
            unit = data.get('unit')
            priority = data.get('priority')
            target_date = data.get('target_date')

            if not title:
                return jsonify({'success': False, 'message': 'Title is required.'}), 400

            parsed_target_date = None
            if target_date:
                parsed_target_date = datetime.strptime(target_date, '%Y-%m-%d').date()

            new_goal = Goal(
                user_id=user_id,
                title=title,
                description=description,
                category=category,
                priority=priority,
                target_value=float(target_value) if target_value else None,
                unit=unit,
                target_date=parsed_target_date,
                start_date=datetime.utcnow().date()
            )
            db.session.add(new_goal)
            db.session.commit()

            return jsonify({
                'success': True,
                'message': 'Goal created successfully!',
                'goal': {
                    'id': new_goal.id,
                    'title': new_goal.title,
                    'description': new_goal.description
                }
            }), 201
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error adding goal for user {user_id}: {e}")
            return jsonify({'success': False, 'message': 'Failed to create goal.'}), 500

    # GET request logic
    goals = Goal.query.filter_by(user_id=user_id).all()
    goals_data = []
    for goal in goals:
        goals_data.append({
            'id': goal.id,
            'title': goal.title,
            'description': goal.description,
            'category': goal.category,
            'status': goal.status,
            'priority': goal.priority,
            'target_value': goal.target_value,
            'current_value': goal.current_value,
            'unit': goal.unit,
            'target_date': goal.target_date.strftime('%Y-%m-%d') if goal.target_date else None,
            'progress_percentage': goal.progress_percentage,
            'created_at': goal.created_at.strftime('%Y-%m-%d') if goal.created_at else None
        })
    return jsonify({'success': True, 'goals': goals_data})

@app.route('/api/goals/<int:goal_id>', methods=['PUT'])
@login_required
@role_required('patient')
def update_goal(goal_id):
    user_id = session['user_id']
    goal = Goal.query.filter_by(id=goal_id, user_id=user_id).first()

    if not goal:
        return jsonify({'success': False, 'message': 'Goal not found.'}), 404

    data = request.json

    editable_fields = [
        'title',
        'description',
        'category',
        'priority',
        'target_value',
        'current_value',
        'unit'
    ]

    for field in editable_fields:
        if field in data:
            setattr(goal, field, data[field])

    completed = data.get('completed')

    try:
        if completed is not None:
            goal.status = 'completed'
            goal.completed_date = datetime.utcnow().date()
        else:
            goal.status = 'active'
            goal.completed_date = None
        
        goal.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Goal updated successfully!',
            'goal': {
                'id': goal.id,
                'title': goal.title,
                'description': goal.description,
                'category': goal.category,
                'status': goal.status,
                'priority': goal.priority,
                'progress_percentage': goal.progress_percentage
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error updating goal: {str(e)}'})

@app.context_processor
def utility_processor():
    def get_severity_info(assessment_type, score):
        if score is None:
            return {'severity': 'N/A', 'color': 'gray'}
        score = float(score)
        if assessment_type == 'GAD-7':
            if score <= 4:
                return {'severity': 'Minimal', 'color': 'green'}
            elif score <= 9:
                return {'severity': 'Mild', 'color': 'yellow'}
            elif score <= 14:
                return {'severity': 'Moderate', 'color': 'orange'}
            else:
                return {'severity': 'Severe', 'color': 'red'}
        elif assessment_type == 'PHQ-9':
            if score <= 4:
                return {'severity': 'Minimal', 'color': 'green'}
            elif score <= 9:
                return {'severity': 'Mild', 'color': 'yellow'}
            elif score <= 14:
                return {'severity': 'Moderate', 'color': 'orange'}
            else:
                return {'severity': 'Severe', 'color': 'red'}
        elif assessment_type == 'Daily Mood':
            if score >= 4:
                return {'severity': 'Positive', 'color': 'green'}
            elif score >= 3:
                return {'severity': 'Neutral', 'color': 'yellow'}
            else:
                return {'severity': 'Negative', 'color': 'red'}
        else:
            return {'severity': 'N/A', 'color': 'gray'}
    return dict(get_severity_info=get_severity_info)

@app.route('/api/save-mood', methods=['POST'])
@login_required
@role_required('patient')
@limiter.limit("10 per minute")  # Rate limit mood saving
def save_mood():
    if not request.is_json:
        print("DEBUG: Request is not JSON.")
        return jsonify({'success': False, 'message': 'Request must be JSON'}), 400
        
    user_id = session['user_id']
    data = request.get_json()
    print(f"DEBUG: Received mood data: {data}")
    
    if not data or 'mood' not in data:
        print("DEBUG: Missing mood data.")
        return jsonify({'success': False, 'message': 'Missing mood data'}), 400
    
    try:
        mood = int(data.get('mood'))
        if not (1 <= mood <= 5):
            print("DEBUG: Mood score out of range.")
            return jsonify({'success': False, 'message': 'Mood must be between 1 and 5'}), 400
            
        print("DEBUG: Creating new mood assessment.")
        # Create new assessment for the mood
        mood_assessment = Assessment(
            user_id=user_id,
            assessment_type='Daily Mood',
            score=mood,
            responses={'mood': mood, 'notes': data.get('notes', '')}
        )
        db.session.add(mood_assessment)
        print("DEBUG: Mood assessment added to session.")
        
        # Also update RPM data for dashboard
        today = datetime.utcnow().date()
        rpm_data = RPMData.query.filter_by(user_id=user_id, date=today).first()
        if not rpm_data:
            rpm_data = RPMData(user_id=user_id, date=today, mood_score=mood)
            db.session.add(rpm_data)
            print("DEBUG: New RPM data added to session.")
        else:
            rpm_data.mood_score = mood
            print("DEBUG: Existing RPM data updated.")
        
        # Update gamification points
        gamification = Gamification.query.filter_by(user_id=user_id).first()
        if not gamification:
            gamification = Gamification(user_id=user_id, points=0, streak=0)
            db.session.add(gamification)
            print("DEBUG: New gamification record added to session.")
            
        # Add points for mood check-in
        gamification.points += 10
        print(f"DEBUG: Gamification points updated: {gamification.points}")
        
        # Check for streak
        if gamification.last_activity:
            last_activity = gamification.last_activity.date() if hasattr(gamification.last_activity, 'date') else gamification.last_activity
            if last_activity == today - timedelta(days=1):
                gamification.streak += 1
                print(f"DEBUG: Gamification streak updated: {gamification.streak}")
            elif last_activity < today - timedelta(days=1):
                gamification.streak = 1
                print("DEBUG: Gamification streak reset.")
        else:
            gamification.streak = 1
            print("DEBUG: Gamification streak initialized.")
        
        gamification.last_activity = today
        print(f"DEBUG: Gamification last_activity updated: {gamification.last_activity}")

        # Update user's last assessment time
        user = db.session.get(User, user_id)
        if not user:
            return jsonify({
                'success': False,
                'message': 'User not found. Please log in again.'
            }), 400

        user.last_assessment_at = datetime.utcnow()
        
        print("DEBUG: Attempting to commit changes to database.")
        db.session.commit()
        print("DEBUG: Changes committed successfully.")
        
        return jsonify({
            'success': True,
            'message': 'Mood saved successfully',
            'points': gamification.points,
            'streak': gamification.streak
        })
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Error saving mood: {str(e)}')
        print(f"DEBUG: Error saving mood: {e}")
        return jsonify({
            'success': False,
            'message': f'Failed to save mood: {str(e)}'
        }), 500



# --- BLOG ROUTES ---

@app.route('/blog')
def blog_list():
    try:
        posts = BlogPost.query.filter_by(is_published=True).order_by(BlogPost.created_at.desc()).all()
        # Get blog insights for display
        insights = {
            'total_posts': BlogPost.query.count(),
            'total_likes': 0,
            'total_comments': 0,
            'total_views': sum([post.views for post in posts]) if posts else 0,
            'most_popular_post': None
        }
        if posts:
            insights['most_popular_post'] = max(posts, key=lambda p: p.views) if posts else None
    except SQLAlchemyError as e:
        logger.error(f"Error fetching blog posts: {e}")
        posts = []
        insights = None
    return render_template('blog_list.html', posts=posts, insights=insights)

@app.route('/blog/<int:post_id>')
def blog_detail(post_id):
    post = BlogPost.query.get_or_404(post_id)
    
    # Increment view count
    post.views += 1
    db.session.commit()
    
    # Get comments for this post
    comments = BlogComment.query.filter_by(post_id=post_id).order_by(BlogComment.created_at.asc()).all()
    
    # Check if current user has liked this post
    user_has_liked = False
    if session.get('user_id'):
        user_has_liked = BlogLike.query.filter_by(
            user_id=session['user_id'], 
            post_id=post_id
        ).first() is not None
    
    return render_template('blog_detail.html', 
                         post=post, 
                         comments=comments, 
                         user_has_liked=user_has_liked)

@app.route('/blog/create', methods=['GET', 'POST'])
@login_required
def blog_create():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        category = request.form.get('category')
        tags = request.form.get('tags')
        is_published = bool(request.form.get('is_published', 'True'))
        author_id = session.get('user_id')
        try:
            post = BlogPost(
                title=title,
                content=content,
                category=category,
                tags=tags,
                is_published=is_published,
                author_id=author_id,
                created_at=datetime.now()
            )
            db.session.add(post)
            db.session.commit()
            flash('Blog post created successfully!', 'success')
            return redirect(url_for('blog_list'))
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Error creating blog post: {e}")
            flash('Failed to create blog post.', 'error')
    return render_template('blog_create.html')

@app.route('/blog/<int:post_id>/edit', methods=['GET', 'POST'])
@login_required
def blog_edit(post_id):
    post = BlogPost.query.get_or_404(post_id)
    if request.method == 'POST':
        post.title = request.form.get('title')
        post.content = request.form.get('content')
        post.category = request.form.get('category')
        post.tags = request.form.get('tags')
        post.is_published = bool(request.form.get('is_published'))
        try:
            db.session.commit()
            flash('Blog post updated successfully!', 'success')
            return redirect(url_for('blog_detail', post_id=post.id))
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Error updating blog post: {e}")
            flash('Failed to update blog post.', 'error')
    return render_template('blog_edit.html', post=post)

# Blog API routes for AJAX functionality
@app.route('/api/blog/<int:post_id>/like', methods=['POST'])
@login_required
def blog_like(post_id):
    """Toggle like for a blog post"""
    user_id = session['user_id']
    post = BlogPost.query.get_or_404(post_id)
    
    # Check if user already liked this post
    existing_like = BlogLike.query.filter_by(user_id=user_id, post_id=post_id).first()
    
    try:
        if existing_like:
            # Unlike the post
            db.session.delete(existing_like)
            liked = False
        else:
            # Like the post
            new_like = BlogLike(user_id=user_id, post_id=post_id)
            db.session.add(new_like)
            liked = True
        
        db.session.commit()
        
        # Get updated like count
        like_count = BlogLike.query.filter_by(post_id=post_id).count()
        
        return jsonify({
            'success': True,
            'liked': liked,
            'like_count': like_count
        })
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Error toggling like for post {post_id}: {e}")
        return jsonify({'success': False, 'message': 'Failed to update like'}), 500

@app.route('/api/blog/<int:post_id>/comment', methods=['POST'])
@login_required
def blog_comment(post_id):
    """Add a comment to a blog post"""
    user_id = session['user_id']
    post = BlogPost.query.get_or_404(post_id)
    
    if not request.is_json:
        return jsonify({'success': False, 'message': 'Request must be JSON'}), 400
    
    data = request.get_json()
    content = data.get('content', '').strip()
    
    if not content:
        return jsonify({'success': False, 'message': 'Comment content is required'}), 400
    
    if len(content) > 1000:
        return jsonify({'success': False, 'message': 'Comment is too long (max 1000 characters)'}), 400
    
    try:
        new_comment = BlogComment(
            user_id=user_id,
            post_id=post_id,
            content=content
        )
        db.session.add(new_comment)
        db.session.commit()
        
        # Get updated comment count
        comment_count = BlogComment.query.filter_by(post_id=post_id).count()
        
        # Get user info for response
        user = User.query.get(user_id)
        
        return jsonify({
            'success': True,
            'comment': {
                'id': new_comment.id,
                'content': new_comment.content,
                'author_name': user.name,
                'created_at': new_comment.created_at.strftime('%B %d, %Y • %I:%M %p')
            },
            'comment_count': comment_count
        })
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Error adding comment to post {post_id}: {e}")
        return jsonify({'success': False, 'message': 'Failed to add comment'}), 500


# --- PATIENT JOURNAL ROUTES ---

@app.route('/patient/journal', methods=['GET', 'POST'])
@login_required
@role_required('patient')
def patient_journal():
    """Journal entries page for patients."""
    # Ensure user is logged in and has valid session
    if 'user_id' not in session:
        flash('Please log in to access your journal.', 'error')
        return redirect(url_for('login'))

    user_id = session['user_id']

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()

        if not title or not content:
            flash('Both title and content are required.', 'error')
            return redirect(url_for('patient_journal'))

        if len(title) > 100:
            flash('Title must be less than 100 characters.', 'error')
            return redirect(url_for('patient_journal'))

        if len(content) > 5000:
            flash('Content must be less than 5000 characters.', 'error')
            return redirect(url_for('patient_journal'))

        # Perform sentiment analysis
        sentiment_result = 'Neutral'  # Default fallback
        if TEXTBLOB_AVAILABLE:
            try:
                blob = TextBlob(content)
                polarity = blob.sentiment.polarity
                if polarity > 0.1:
                    sentiment_result = 'Positive'
                elif polarity < -0.1:
                    sentiment_result = 'Negative'
                else:
                    sentiment_result = 'Neutral'
            except Exception as e:
                logger.warning(f"Sentiment analysis failed: {e}")
                sentiment_result = 'Neutral'

        # Get AI suggestions for the journal entry
        ai_suggestions = get_ai_journal_suggestions(title, content)

        # Create journal entry
        journal_entry = {
            'id': str(uuid.uuid4()),
            'title': title,
            'content': content,
            'sentiment': sentiment_result,
            'ai_suggestions': ai_suggestions,
            'created_at': datetime.now(),
            'updated_at': datetime.now()
        }

        # Initialize user's journal entries if not exists
        if user_id not in patient_journal_entries:
            patient_journal_entries[user_id] = []

        patient_journal_entries[user_id].append(journal_entry)

        # Award points for journaling
        award_points(user_id, 15, 'journal_entry')

        flash('Journal entry saved successfully!', 'success')
        return redirect(url_for('patient_journal'))

    # GET request - display journal entries
    user_entries = patient_journal_entries.get(user_id, [])

    return render_template('patient_journal.html',
                         user_name=session['user_name'],
                         journal_entries=user_entries)


def get_ai_journal_suggestions(title, content):
    """Get AI-powered suggestions for journal entries with optimized prompts."""
    try:
        # Enhanced prompt with better structure and context
        prompt = f"""
        You are Dr. Anya, a compassionate AI wellness coach. Analyze this journal entry and provide supportive, actionable insights.

        JOURNAL ENTRY:
        Title: {title}
        Content: {content}

        Please provide a structured response in this exact format:

        INSIGHTS:
        [2-3 sentences identifying key themes, emotions, or patterns]

        SUGGESTIONS:
        [3 specific, actionable suggestions for wellbeing, each on a new line]

        COPING STRATEGIES:
        [2-3 relevant coping strategies or techniques]

        ENCOURAGEMENT:
        [1-2 sentences of supportive, empathetic encouragement]

        Keep your response concise (under 800 characters total), supportive, and focused on wellness and growth.
        Use bullet points for suggestions and strategies. Be empathetic and non-judgmental.
        """

        # Use the AI service to get suggestions with optimized parameters
        ai_response = ai_service.generate_chat_response(prompt)

        if isinstance(ai_response, dict):
            suggestions = ai_response.get('response') or ai_response.get('reply') or str(ai_response)
        else:
            suggestions = str(ai_response)

        # Clean up and format the response for better readability
        suggestions = suggestions.strip()[:800]  # Limit length

        # Ensure we have meaningful content
        if len(suggestions) < 50:  # Too short, probably error
            suggestions = "Thank you for sharing your thoughts. Consider discussing these feelings with a trusted friend or mental health professional."

        return suggestions

    except Exception as e:
        logger.warning(f"AI suggestion generation failed: {e}")
        return "Thank you for sharing your thoughts. Consider discussing these feelings with a trusted friend or mental health professional."

@app.route('/api/delete-journal-entry/<entry_id>', methods=['DELETE'])
@login_required
@role_required('patient')
def delete_journal_entry(entry_id):
    """Delete a specific journal entry."""
    user_id = session['user_id']

    # Find the journal entry
    if user_id not in patient_journal_entries:
        return jsonify({'success': False, 'message': 'No journal entries found'}), 404

    journal_entries = patient_journal_entries[user_id]
    journal_entry = None

    for entry in journal_entries:
        if entry['id'] == entry_id:
            journal_entry = entry
            break

    if not journal_entry:
        return jsonify({'success': False, 'message': 'Journal entry not found'}), 404

    try:
        # Remove the journal entry from the list
        patient_journal_entries[user_id].remove(journal_entry)

        return jsonify({
            'success': True,
            'message': 'Journal entry deleted successfully'
        })

    except Exception as e:
        logger.error(f"Error deleting journal entry {entry_id}: {e}")
        return jsonify({'success': False, 'message': 'Failed to delete journal entry'}), 500


@app.route('/patient/voice-logs')
@login_required
@role_required('patient')
def patient_voice_logs():
    """Voice logs page for patients."""
    user_id = session['user_id']
    user_logs = patient_voice_logs_data.get(user_id, [])

    return render_template('patient_voice_logs.html',
                         user_name=session['user_name'],
                         voice_logs=user_logs)


@app.route('/api/delete-voice-log/<voice_log_id>', methods=['DELETE'])
@login_required
@role_required('patient')
def delete_voice_log(voice_log_id):
    """Delete a specific voice log entry."""
    user_id = session['user_id']

    # Find the voice log entry
    if user_id not in patient_voice_logs_data:
        return jsonify({'success': False, 'message': 'No voice logs found'}), 404

    voice_logs = patient_voice_logs_data[user_id]
    voice_log = None

    for log in voice_logs:
        if log['id'] == voice_log_id:
            voice_log = log
            break

    if not voice_log:
        return jsonify({'success': False, 'message': 'Voice log not found'}), 404

    try:
        # Remove the voice log from the list
        patient_voice_logs_data[user_id].remove(voice_log)

        # Delete the audio file if it exists
        try:
            if 'file_path' in voice_log and os.path.exists(voice_log['file_path']):
                os.remove(voice_log['file_path'])
                logger.info(f"Deleted audio file: {voice_log['file_path']}")
        except Exception as file_error:
            logger.warning(f"Could not delete audio file: {file_error}")

        return jsonify({
            'success': True,
            'message': 'Voice log deleted successfully'
        })

    except Exception as e:
        logger.error(f"Error deleting voice log {voice_log_id}: {e}")
        return jsonify({'success': False, 'message': 'Failed to delete voice log'}), 500


@app.route('/api/upload-voice', methods=['POST'])
@login_required
@role_required('patient')
@limiter.limit("5 per hour")  # Limit voice uploads
def upload_voice():
    """Upload and process voice recording."""
    user_id = session['user_id']

    if 'audio' not in request.files:
        return jsonify({'success': False, 'message': 'No audio file provided'}), 400

    audio_file = request.files['audio']

    if audio_file.filename == '':
        return jsonify({'success': False, 'message': 'No audio file selected'}), 400

    if not audio_file.content_type.startswith('audio/'):
        return jsonify({'success': False, 'message': 'Invalid file type. Please upload an audio file.'}), 400

    try:
        # Ensure uploads directory exists
        uploads_dir = app.config['UPLOAD_FOLDER']
        os.makedirs(uploads_dir, exist_ok=True)

        # Generate unique filename
        filename = secure_filename(f"{user_id}_{uuid.uuid4()}.wav")
        file_path = os.path.join(uploads_dir, filename)
        
        # Store relative path for serving
        relative_path = os.path.join('uploads', filename)

        # Save the file
        audio_file.save(file_path)

        # Process audio features if librosa is available
        audio_features = {}
        emotion_result = 'neutral'  # Default fallback

        if LIBROSA_AVAILABLE:
            try:
                # Load audio file
                y, sr = librosa.load(file_path, duration=120)  # Max 2 minutes

                # Extract basic features
                audio_features = {
                    'duration': len(y) / sr,
                    'sample_rate': sr
                }

                # Extract acoustic features
                try:
                    # Pitch (fundamental frequency)
                    pitches, magnitudes = librosa.piptrack(y=y, sr=sr)
                    pitch_values = pitches[pitches > 0]
                    if len(pitch_values) > 0:
                        audio_features['mean_pitch'] = float(np.mean(pitch_values))
                        audio_features['pitch_std'] = float(np.std(pitch_values))

                    # Energy (RMS)
                    rms = librosa.feature.rms(y=y)
                    audio_features['mean_energy'] = float(np.mean(rms))
                    audio_features['energy_std'] = float(np.std(rms))

                    # Zero-crossing rate (related to voice quality)
                    zcr = librosa.feature.zero_crossing_rate(y)
                    audio_features['mean_zcr'] = float(np.mean(zcr))
                    audio_features['zcr_std'] = float(np.std(zcr))

                    # Spectral features
                    spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
                    audio_features['mean_spectral_centroid'] = float(np.mean(spectral_centroid))
                    audio_features['spectral_centroid_std'] = float(np.std(spectral_centroid))

                except Exception as feature_error:
                    logger.warning(f"Feature extraction error: {feature_error}")

                # Simple emotion classification based on features
                emotion_result = classify_emotion(audio_features)
            except Exception as audio_error:
                logger.warning(f"Audio processing error: {audio_error}")
                emotion_result = 'neutral'

        # Get AI-powered emotion analysis for voice
        emotion_result = get_ai_voice_emotion_analysis(file_path, audio_features)

        # Create voice log entry
        voice_log = {
            'id': str(uuid.uuid4()),
            'filename': filename,
            'file_path': file_path,
            'audio_features': audio_features,
            'emotion': emotion_result,
            'ai_analysis': emotion_result,  # Store AI analysis result
            'created_at': datetime.now()
        }

        # Initialize user's voice logs if not exists
        if user_id not in patient_voice_logs_data:
            patient_voice_logs_data[user_id] = []
            
        patient_voice_logs_data[user_id].append(voice_log)

        # Award points for voice logging
        award_points(user_id, 20, 'voice_log')

        return jsonify({
            'success': True,
            'message': 'Voice log uploaded and processed successfully!',
            'voice_log': {
                'id': voice_log['id'],
                'emotion': voice_log['emotion'],
                'audio_features': voice_log['audio_features']
            }
        })

    except Exception as e:
        logger.error(f"Error uploading voice file: {e}")
        return jsonify({'success': False, 'message': f'Upload failed: {str(e)}'}), 500


import speech_recognition as sr

def transcribe_audio(file_path):
    r = sr.Recognizer()
    with sr.AudioFile(file_path) as source:
        audio = r.record(source)
    try:
        return r.recognize_google(audio)
    except sr.UnknownValueError:
        return ""
    except sr.RequestError as e:
        logger.error(f"Could not request results from Google Speech Recognition service; {e}")
        return ""

def get_ai_voice_emotion_analysis(file_path, audio_features):
    # Initialize lemmatizer
    lemmatizer = WordNetLemmatizer()

    transcribed_text = transcribe_audio(file_path)

    # Lemmatize the text
    if transcribed_text:
        tokens = word_tokenize(transcribed_text)
        lemmatized_text = ' '.join([lemmatizer.lemmatize(word) for word in tokens])
    else:
        lemmatized_text = ""

    """Get AI-powered emotion analysis for voice recordings with optimized prompts."""
    try:
        # Enhanced prompt with better structure and audio features
        prompt = f"""
        You are Dr. Anya, an AI wellness coach analyzing voice recordings for emotional insights.

                TRANSCRIBED & LEMMATIZED TEXT:
        {lemmatized_text}

        AUDIO ANALYSIS:
        Duration: {audio_features.get('duration', 0):.1f}s
        Mean Pitch: {audio_features.get('mean_pitch', 0):.0f} Hz
        Mean Energy: {audio_features.get('mean_energy', 0):.4f}
        Spectral Centroid: {audio_features.get('mean_spectral_centroid', 0):.0f} Hz

        Based on these acoustic features, determine the primary emotion expressed:

        EMOTIONS: happy, sad, stressed, angry, calm, excited, neutral, anxious, confident

        Respond in this exact format:

        EMOTION: [primary emotion]
        CONFIDENCE: [high/medium/low]
        INSIGHTS: [2-3 sentences explaining the emotion based on audio features]
        SUGGESTIONS: [2 specific wellness suggestions based on detected emotion]

        Keep response concise and supportive.
        """

        # Use the AI service to get emotion analysis with optimized parameters
        ai_response = ai_service.generate_chat_response(prompt)

        if isinstance(ai_response, dict):
            analysis = ai_response.get('response') or ai_response.get('reply') or str(ai_response)
        else:
            analysis = str(ai_response)

        # Extract the primary emotion from the response
        analysis_lower = analysis.lower()

        # Look for emotion keywords in the response
        emotions = ['happy', 'sad', 'stressed', 'angry', 'calm', 'excited', 'neutral', 'anxious', 'confident']
        detected_emotion = 'neutral'  # default fallback

        for emotion in emotions:
            if emotion in analysis_lower:
                detected_emotion = emotion
                break

        # Clean up the response and limit length
        analysis = analysis.strip()[:400]  # Limit to 400 characters

        return f"{detected_emotion.capitalize()}: {analysis}"

    except Exception as e:
        logger.warning(f"AI voice emotion analysis failed: {e}")
        return "Neutral: Voice analysis completed. Consider how you're feeling and what might be affecting your emotional state."


def classify_emotion(audio_features):
    """Simple emotion classification based on acoustic features."""
    if not audio_features:
        return 'neutral'

    try:
        # Simple heuristic-based classification
        pitch = audio_features.get('mean_pitch', 0)
        energy = audio_features.get('mean_energy', 0)
        zcr = audio_features.get('mean_zcr', 0)

        # Higher pitch and energy might indicate excitement/happiness
        if pitch > 200 and energy > 0.1:
            return 'happy'
        # Lower pitch and energy might indicate sadness
        elif pitch < 150 and energy < 0.05:
            return 'sad'
        # Higher zero-crossing rate might indicate stress/agitation
        elif zcr > 0.1:
            return 'stressed'
        # Medium pitch and energy might indicate calmness
        elif 150 <= pitch <= 200 and 0.05 <= energy <= 0.1:
            return 'calm'
        else:
            return 'neutral'

    except Exception as e:
        logger.warning(f"Emotion classification error: {e}")
        return 'neutral'


# Health check endpoint for monitoring
@app.route('/health')
def health_check():
    """Health check endpoint for monitoring and load balancers."""
    try:
        # Test database connection
        db.session.execute(db.text('SELECT 1'))
        db_status = 'healthy'
    except Exception as e:
        db_status = f'unhealthy: {str(e)}'

    # Test AI services
    try:
        ai_check = ai_service.check_api_status()
        ai_status = 'available' if ai_check.get('model_available') else 'unavailable'
    except Exception as e:
        ai_status = f'error: {str(e)}'

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
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400
        
        # Log the error (in production, you might want to send this to a logging service)
        logger.warning(f"Client-side error: {data.get('message', 'Unknown error')} "
                      f"at {data.get('filename', 'unknown')}:{data.get('lineno', 'unknown')} "
                      f"from {request.remote_addr}")
        
        return jsonify({'success': True, 'message': 'Error logged'}), 200
    except Exception as e:
        logger.error(f"Error logging client error: {e}")
        return jsonify({'success': False, 'message': 'Failed to log error'}), 500

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
@socketio.on('join')
def on_join(data):
    room = data['room']
    join_room(room)
    emit('message', f'User has joined the room {room}.', to=room)
    # Notify the other user in the room that a peer is ready
    emit('ready', to=room, include_self=False)

@socketio.on('offer')
def on_offer(data):
    room = data['room']
    emit('offer', data, to=room, include_self=False)

@socketio.on('answer')
def on_answer(data):
    room = data['room']
    emit('answer', data, to=room, include_self=False)

@socketio.on('candidate')
def on_candidate(data):
    room = data['room']
    emit('candidate', data, to=room, include_self=False)

@socketio.on('leave')
def on_leave(data):
    room = data['room']
    leave_room(room)
    emit('_disconnect', to=room, include_self=False)
    emit('message', f'User has left the room {room}.', to=room)

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
        return redirect(url_for("login"))

    try:
        logger.info("Google authorized, fetching user info.")
        resp = blueprint.session.get("/oauth2/v2/userinfo")
        assert resp.ok, resp.text
        user_info = resp.json()
        logger.info(f"Google user info: {user_info}")
        google_id = user_info['id']
        email = user_info['email']
        name = user_info.get('name', 'User')

        logger.info(f"Looking for user with google_id={google_id}")
        user = User.query.filter_by(google_id=google_id).first()

        if not user:
            logger.info(f"User not found with google_id, looking for user with email={email}")
            user = User.query.filter_by(email=email).first()
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
            return redirect(url_for('patient_dashboard'))
        else:
            logger.info("User is a provider, redirecting to provider_dashboard.")
            return redirect(url_for('provider_dashboard'))

    except Exception as e:
        logger.error(f"An error occurred during Google login: {e}", exc_info=True)
        flash(f"An error occurred: {e}", "danger")
        return redirect(url_for('login'))

@app.route('/login/google')
def login_google():
    """Redirects to Google to initiate OAuth authentication."""
    return redirect(url_for("google.login"))


@app.route('/role_selection')
def role_selection():
    """Renders the role selection page for new users."""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('role_selection.html')

@app.route('/save_role', methods=['POST'])
def save_role():
    """Saves the user's chosen role to the database."""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    role = request.form.get('role')

    if role in ['patient', 'provider']:
        try:
            user = db.session.get(User, user_id)
            user.role = role
            db.session.commit()
            session['user_role'] = role
            if role == 'patient':
                return redirect(url_for('patient_dashboard'))
            else:
                return redirect(url_for('provider_dashboard'))
        except Exception as e:
            logger.error(f"Could not save user role: {e}")
            flash(f"Could not save your role: {e}", "danger")
            return redirect(url_for('role_selection'))
    else:
        flash("Invalid role selected.", "warning")
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
    
    try:
        print("INFO - ==================================================")
        print("INFO - Starting MindFullHorizon server...")
        print(f"INFO - Server available at: http://localhost:5000")
        print("INFO - Debug mode: True")
        print("INFO - CSRF Protection: Enabled")
        print("INFO - Press Ctrl+C to stop the server")
        print("INFO - ==================================================")

        # SocketIO server for real-time features
        # On Windows, the Flask reloader can start two processes, causing a port-in-use error with SocketIO/eventlet.
        # Disable the reloader on Windows to avoid binding twice.
        use_reloader = False if os.name == 'nt' else True
        socketio.run(app, host='127.0.0.1', port=5000, debug=True, use_reloader=use_reloader)

    except KeyboardInterrupt:
        print("\nINFO - Server interrupted by user (Ctrl+C)")
        print("INFO - Shutting down gracefully...")
        sys.exit(0)
    except Exception as e:
        print(f"ERROR - Failed to start server: {e}")
        sys.exit(1)
