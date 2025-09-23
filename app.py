
import json

from werkzeug.utils import secure_filename
import uuid

import logging
import os
from datetime import datetime, timedelta, date, timezone
from functools import wraps
from sqlalchemy import func

from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_from_directory, abort
from flask_session import Session
from flask_compress import Compress
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect, CSRFError
from flask_socketio import SocketIO, emit, join_room, leave_room

from ai_service import ai_service
from extensions import db, migrate, flask_session, compress, csrf
from models import User, Assessment, DigitalDetoxLog, RPMData, Gamification, ClinicalNote, InstitutionalAnalytics, Appointment, Goal, Medication, MedicationLog, BreathingExerciseLog, YogaLog, ProgressRecommendation, get_user_wellness_trend, get_institutional_summary
from models import BlogPost, BlogComment, BlogLike, BlogInsight, Prescription  # Ensure BlogPost and related models are imported

# Load environment variables from .env file
try:
    load_dotenv(encoding='utf-8-sig')
except Exception as e:
    print(f"Warning: Could not load .env file: {e}")
    print("Continuing with default configuration...")


app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Configure session
app.secret_key = os.getenv('SECRET_KEY', 'supersecretkey')  # Use environment variable or fallback
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=1)  # Session expires after 1 day
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_FILE_DIR'] = os.path.join(os.getcwd(), 'flask_session')

# Initialize CSRF protection
app.config['WTF_CSRF_ENABLED'] = False
app.config['WTF_CSRF_TIME_LIMIT'] = None  # No time limit for CSRF tokens

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('mindful_horizon.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Yoga Video Library Page (correct placement)
@app.route('/yoga-videos')
def yoga_videos():
    return render_template('yoga_videos.html')


# Enable gzip compression and static caching for low-bandwidth optimization
app.config['COMPRESS_ALGORITHM'] = ['gzip']
app.config['COMPRESS_LEVEL'] = 6
app.config['COMPRESS_MIN_SIZE'] = 500  # Only compress responses > 500 bytes
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = timedelta(days=30)  # Cache static assets for 30 days

# Database configuration
basedir = os.path.abspath(os.path.dirname(__file__))
# Ensure instance folder exists
os.makedirs(os.path.join(basedir, 'instance'), exist_ok=True)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(basedir, "instance", "mindful_horizon.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Upload folder for profile pictures
UPLOAD_FOLDER = os.path.join(basedir, 'static/profile_pics')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Ensure the upload folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Initialize database and migrations
db.init_app(app)
migrate = Migrate(app, db)

# Initialize all extensions
from extensions import init_extensions
init_extensions(app)

# Stub for get_blog_insights (replace with real logic as needed)
def get_blog_insights():
    return {
        'total_posts': BlogPost.query.count(),
        'total_likes': 0,
        'total_comments': 0,
        'total_views': 0,
        'most_popular_post': None
    }

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Stub for award_points (replace with real logic as needed)
def award_points(user_id, points, reason):
    pass

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

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

    from datetime import datetime
    return render_template(
        'index.html',
        blog_insights=blog_insights,
        featured_posts=featured_posts,
        landing_theme=landing_theme,
        faqs=faqs,
        datetime=datetime
    )

@app.route('/login', methods=['GET', 'POST'])
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
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        role = request.form['role']
        institution = request.form.get('institution', 'Default University')
        
        if not all([name, email, password, confirm_password, role]):
            flash('All fields are required.', 'error')
            return render_template('signup.html')
        
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('signup.html')
        
        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'error')
            return render_template('signup.html')
        
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
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
            
            flash('Registration successful! Please login with your credentials.', 'success')
            return redirect(url_for('login'))
            
        except Exception:
            db.session.rollback()
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
    
    gamification = Gamification.query.filter_by(user_id=user_id).first()
    rpm_data = RPMData.query.filter_by(user_id=user_id).order_by(RPMData.date.desc()).first()
    all_appointments = Appointment.query.filter_by(user_id=user_id).order_by(Appointment.date.asc(), Appointment.time.asc()).all()

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
            logger.error(f"Error processing appointment {appt.id}: {e}")
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
                         past_appointments=past_appointments)

@app.route('/provider-dashboard')
@login_required
@role_required('provider')
def provider_dashboard():
    institution = session.get('user_institution', 'Sample University')
    
    # Fetch all patients for the institution with their latest detox logs and clinical notes
    patients = User.query.filter_by(role='patient', institution=institution).all()

    caseload_data = []
    for patient in patients:
        latest_detox = DigitalDetoxLog.query.filter_by(user_id=patient.id).order_by(DigitalDetoxLog.date.desc()).first()
        latest_session = ClinicalNote.query.filter_by(patient_id=patient.id).order_by(ClinicalNote.session_date.desc()).first()
        
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
                         caseload=caseload_data,
                         bi_data=bi_data,
                         institution=institution)


@app.route('/chat')
@login_required
def chat():
    return render_template('chat.html', user_name=session['user_name'])

@app.route('/schedule', methods=['GET', 'POST'])
@login_required
def schedule():
    if request.method == 'POST':
        date_str = request.form['date']
        time_str = request.form['time']
        appointment_type = request.form['appointment_type']
        notes = request.form.get('notes', '')
        user_id = session['user_id']

        try:
            appointment_date = datetime.strptime(date_str, '%Y-%m-%d').date()

            new_appointment = Appointment(
                user_id=user_id,
                date=appointment_date,
                time=time_str,
                appointment_type=appointment_type,
                notes=notes,
                status='booked'
            )
            db.session.add(new_appointment)
            db.session.commit()
            flash(f'Appointment successfully booked for {date_str} at {time_str}!', 'success')
            return redirect(url_for('patient_dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error booking appointment: {e}', 'error')
            logger.error(f"Error booking appointment for user {user_id}: {e}")
            return redirect(url_for('schedule'))
    
    return render_template('schedule.html', user_name=session['user_name'])

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
                    created_at=datetime.now(datetime.UTC)
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
                    created_at=datetime.now(datetime.UTC)
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
    
    user = User.query.get(user_id)
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

@app.route('/assessment')
@login_required
@role_required('patient')
def assessment():
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

@app.route('/api/save-assessment', methods=['POST'])
@login_required
@role_required('patient')
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
        user = User.query.get(user_id)
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
            user.set_password(password)

        # Handle profile picture upload
        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                # Ensure unique filename to prevent overwrites
                unique_filename = str(uuid.uuid4()) + '_' + filename
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                file.save(file_path)
                user.profile_pic = unique_filename
                flash('Profile picture updated successfully!', 'success')
            elif file.filename != '':
                flash('Invalid file type for profile picture.', 'error')

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

@app.route('/api/goals', methods=['GET', 'POST'])
@login_required
@role_required('patient')
def handle_goals():
    user_id = session['user_id']

    if request.method == 'POST':
        data = request.json
        title = data.get('title')
        description = data.get('description', '')
        category = data.get('category', 'mental_health')
        priority = data.get('priority', 'medium')
        target_value = data.get('target_value')
        unit = data.get('unit', '')
        target_date = data.get('target_date')

        if not title:
            return jsonify({'success': False, 'message': 'Goal title is required.'}), 400

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
        user = User.query.get(user_id)
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
    except SQLAlchemyError as e:
        logger.error(f"Error fetching blog posts: {e}")
        posts = []
    return render_template('blog_list.html', posts=posts)

@app.route('/blog/<int:post_id>')
def blog_detail(post_id):
    post = BlogPost.query.get_or_404(post_id)
    return render_template('blog_detail.html', post=post)

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


# Serve manifest.json from root directory
@app.route('/manifest.json')
def manifest():
    return send_from_directory(os.path.join(app.root_path), 'manifest.json', mimetype='application/manifest+json')

# Serve other static files from root directory if needed
@app.route('/<path:filename>')
def serve_static(filename):
    if filename.endswith('.json') or filename.endswith('.txt') or filename.endswith('.xml'):
        return send_from_directory(app.root_path, filename)
    return "File not found", 404

# --- SocketIO Chat Handler ---
@socketio.on('chat_message')
def handle_chat_message(data):
    user_message = data.get('message')
    try:
        reply = ai_service.generate_chat_response(user_message)
    except Exception as e:
        reply = "Sorry, the AI is currently unavailable."
    emit('chat_response', {'reply': reply, 'is_crisis': False})

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

if __name__ == '__main__':
    socketio.run(app, debug=True, port=5000)
