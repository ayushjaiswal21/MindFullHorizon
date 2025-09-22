import json
import logging
import os
from datetime import datetime, timedelta, date
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_from_directory
from flask_session import Session
from flask_compress import Compress
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect, CSRFError

from ai_service import ai_service
from database import db
from models import User, Assessment, DigitalDetoxLog, RPMData, Gamification, ClinicalNote, InstitutionalAnalytics, Appointment, Goal, Medication, MedicationLog, BreathingExerciseLog, YogaLog, ProgressRecommendation, get_user_wellness_trend, get_institutional_summary

# Load environment variables from .env file
try:
    load_dotenv(encoding='utf-8-sig')
except Exception as e:
    print(f"Warning: Could not load .env file: {e}")
    print("Continuing with default configuration...")

app = Flask(__name__)

# Configure session
app.secret_key = os.getenv('SECRET_KEY', 'supersecretkey')  # Use environment variable or fallback
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=1)  # Session expires after 1 day
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_FILE_DIR'] = os.path.join(os.getcwd(), 'flask_session')

# Initialize Flask-Session
Session(app)

# Initialize CSRF protection
csrf = CSRFProtect()
csrf.init_app(app)

# Disable CSRF for all views by default
app.config['WTF_CSRF_ENABLED'] = False

# Enable CSRF only for specific forms that need it
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
logger.info("--- SCRIPT START: app.py is being executed ---")

# Enable gzip compression and static caching for low-bandwidth optimization
app.config['COMPRESS_ALGORITHM'] = ['gzip']
app.config['COMPRESS_LEVEL'] = 6
app.config['COMPRESS_MIN_SIZE'] = 500  # Only compress responses > 500 bytes
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = timedelta(days=30)  # Cache static assets for 30 days
compress = Compress(app)

# Database configuration
basedir = os.path.abspath(os.path.dirname(__file__))
# Ensure instance folder exists
os.makedirs(os.path.join(basedir, 'instance'), exist_ok=True)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(basedir, "instance", "mindful_horizon.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database and migrations
db.init_app(app)
migrate = Migrate(app, db)

# Light HTML caching (10 minutes) to reduce repeat downloads on slow connections
@app.after_request
def add_cache_headers(response):
    content_type = response.headers.get('Content-Type', '')
    if 'text/html' in content_type:
        response.headers['Cache-Control'] = 'public, max-age=600'
    return response

def init_database(app_instance):
    """Initialize database with sample data"""
    with app_instance.app_context():
        db.create_all()
        
        if User.query.first() is None:
            patient = User(
                email='patient@example.com',
                name='John Doe',
                role='patient',
                institution='Sample University'
            )
            patient.set_password('password')
            
            provider = User(
                email='provider@example.com',
                name='Dr. Smith',
                role='provider',
                institution='Sample University'
            )
            provider.set_password('password')
            
            db.session.add(patient)
            db.session.add(provider)
            db.session.commit()
            
            gamification = Gamification(
                user_id=patient.id,
                points=1250,
                streak=7,
                badges=['Early Bird', 'Consistency Champion', 'Mood Tracker'],
                last_activity=date.today()
            )
            
            rpm_data = RPMData(
                user_id=patient.id,
                date=date.today(),
                heart_rate=72,
                sleep_duration=7.5,
                steps=8500,
                mood_score=8
            )
            
            for i in range(7):
                detox_log = DigitalDetoxLog(
                    user_id=patient.id,
                    date=date.today() - timedelta(days=i),
                    screen_time_hours=6.5 - i * 0.3,
                    academic_score=85 + i,
                    social_interactions='medium' if i % 2 == 0 else 'high'
                )
                db.session.add(detox_log)
            
            db.session.add(gamification)
            db.session.add(rpm_data)
            db.session.commit()

# Initialize database on startup
# init_database()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

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
    return render_template('landing.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']
        
        # Query database for user
        user = User.query.filter_by(email=email, role=role).first()
        
        if user and user.check_password(password):
            # Clear any existing session data
            session.clear()
            
            # Set session data
            session.permanent = True  # Make the session persistent
            session['user_email'] = email
            session['user_role'] = role
            session['user_name'] = user.name
            session['user_id'] = user.id
            session['user_institution'] = user.institution
            
            # Ensure session is saved
            session.modified = True
            
            print(f"\n=== Login Successful ===")
            print(f"User ID: {user.id}")
            print(f"User Role: {role}")
            print(f"Session ID: {session.sid if hasattr(session, 'sid') else 'N/A'}")
            print(f"Session keys: {list(session.keys())}")
            print("======================\n")
            
            if role == 'patient':
                return redirect(url_for('patient_dashboard'))
            else:
                return redirect(url_for('provider_dashboard'))
        else:
            flash('Invalid credentials. Please check your email, password, and role.', 'error')
    
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
        
        # Validation
        if not all([name, email, password, confirm_password, role]):
            flash('All fields are required.', 'error')
            return render_template('signup.html')
        
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('signup.html')
        
        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'error')
            return render_template('signup.html')
        
        # Check if user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email already registered. Please use a different email or login.', 'error')
            return render_template('signup.html')
        
        # Create new user
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
            
            # Initialize gamification for patients
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
    
    # Get user data from database
    try:
        gamification = Gamification.query.filter_by(user_id=user_id).first()
        rpm_data = RPMData.query.filter_by(user_id=user_id).order_by(RPMData.date.desc()).first()
        logger.info(f"Loaded gamification data for user {user_id}: {gamification}")
        logger.info(f"Loaded RPM data for user {user_id}: {rpm_data}")

        # Get appointments
        all_appointments = Appointment.query.filter_by(user_id=user_id).order_by(Appointment.date.asc(), Appointment.time.asc()).all()
    except Exception as e:
        logger.error(f"Error loading user data for {user_id}: {e}")
        gamification = None
        rpm_data = None
        all_appointments = []

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
            # Skip malformed appointments
            continue

    # Prepare data structure
    try:
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
    except Exception as e:
        logger.error(f"Error preparing data structure: {e}")
        data = {
            'points': 0,
            'streak': 0,
            'badges': [],
            'rpm_data': {
                'heart_rate': 72,
                'sleep_duration': 7.5,
                'steps': 8500,
                'mood_score': 8
            }
        }

    # Check for RPM alerts
    alerts = []
    try:
        if rpm_data:
            if rpm_data.heart_rate and rpm_data.heart_rate > 100:
                alerts.append('High heart rate detected')
            if rpm_data.sleep_duration and rpm_data.sleep_duration < 6:
                alerts.append('Insufficient sleep detected')
            if rpm_data.mood_score and rpm_data.mood_score < 4:
                alerts.append('Low mood score detected')
    except Exception as e:
        logger.error(f"Error checking RPM alerts: {e}")
        alerts = []

    return render_template('patient_dashboard.html', 
                         user_name=session['user_name'], 
                         data=data, 
                         alerts=alerts,
                         upcoming_appointments=upcoming_appointments,
                         past_appointments=past_appointments)

@app.route('/provider-dashboard')
@login_required
@role_required('provider')
def provider_dashboard():
    institution = session.get('user_institution', 'Sample University')
    
    # Get patients from the same institution
    patients = User.query.filter_by(role='patient', institution=institution).all()
    
    # Build caseload data with real database information
    caseload_data = []
    for patient in patients:
        try:
            # Get latest digital detox data for risk assessment
            latest_detox = DigitalDetoxLog.query.filter_by(user_id=patient.id).order_by(DigitalDetoxLog.date.desc()).first()
            latest_session = ClinicalNote.query.filter_by(patient_id=patient.id).order_by(ClinicalNote.session_date.desc()).first()
            
            # Determine risk level based on AI score and screen time
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
        except Exception as e:
            logger.error(f"Error processing patient {patient.id}: {e}")
            # Add patient with default values if there's an error
            caseload_data.append({
                'user_id': patient.id,
                'name': patient.name,
                'email': patient.email,
                'risk_level': 'Unknown',
                'last_session': 'No sessions',
                'status': 'Unknown',
                'digital_score': 'No data'
            })
    
    # Get institutional analytics
    try:
        institutional_data = get_institutional_summary(institution, db)
    except Exception as e:
        logger.error(f"Error getting institutional data: {e}")
        institutional_data = None
    
    # Enhanced BI data with real calculations
    bi_data = {
        'patient_engagement': institutional_data['engagement_rate'] if institutional_data else 0,
        'avg_session_duration': 45,  # Could be calculated from clinical notes
        'completion_rate': 82,
        'satisfaction_score': 4.2,
        'total_patients': institutional_data['total_users'] if institutional_data else 0,
        'high_risk_patients': institutional_data['high_risk_users'] if institutional_data else 0,
        'avg_screen_time': institutional_data['avg_screen_time'] if institutional_data else 0
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
            # Convert date string to date object
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
            # Get patient context for AI analysis
            patient_context = None
            if patient_email:
                patient = User.query.filter_by(email=patient_email, role='patient').first()
                if patient:
                    # Get recent wellness data for context
                    recent_detox = DigitalDetoxLog.query.filter_by(user_id=patient.id).order_by(DigitalDetoxLog.date.desc()).first()
                    gamification = Gamification.query.filter_by(user_id=patient.id).first()
                    
                    patient_context = {
                        'wellness_trend': recent_detox.ai_score if recent_detox and recent_detox.ai_score else 'Not available',
                        'digital_score': recent_detox.ai_score if recent_detox else 'Not available',
                        'engagement': f'{gamification.points} points, {gamification.streak} day streak' if gamification else 'Low'
                    }
            
            # Use AI service for clinical note generation
            clinical_note = ai_service.generate_clinical_note(transcript, patient_context)
            
            # Save to database if patient is specified
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

    # Fetch all active medications for the user
    medications = Medication.query.filter_by(user_id=user_id, is_active=True).all()
    
    # Get today's medication logs
    today_start = datetime.combine(date.today(), datetime.min.time())
    today_end = datetime.combine(date.today(), datetime.max.time())
    
    todays_logs = MedicationLog.query.filter(
        MedicationLog.user_id == user_id,
        MedicationLog.taken_at >= today_start,
        MedicationLog.taken_at <= today_end
    ).all()
    
    # Create a set of medication IDs that have been logged today
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
        # Check if already logged today
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
            flash('Medication logged successfully!', 'success')
        else:
            flash('Medication already logged for today.', 'info')
            
    return redirect(url_for('medication'))

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
                    created_at=datetime.utcnow()
                )
                db.session.add(new_log)
                db.session.commit()
                flash(f'Your {exercise_name} session has been logged!', 'success')
            except ValueError:
                flash('Invalid duration. Please enter a number.', 'error')
        return redirect(url_for('breathing'))

    # Fetch recent breathing logs for the user
    recent_logs = BreathingExerciseLog.query.filter_by(user_id=user_id).order_by(BreathingExerciseLog.created_at.desc()).limit(10).all()
    
    # Calculate statistics
    all_logs = BreathingExerciseLog.query.filter_by(user_id=user_id).all()
    total_sessions = len(all_logs)
    total_minutes = sum(log.duration_minutes for log in all_logs)
    
    # Calculate streak (consecutive days with sessions)
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
                    created_at=datetime.utcnow()
                )
                db.session.add(new_log)
                db.session.commit()
                flash(f'Your {session_name} session has been logged!', 'success')
            except ValueError:
                flash('Invalid duration. Please enter a number.', 'error')
        return redirect(url_for('yoga'))

    # Fetch recent yoga logs for the user
    recent_logs = YogaLog.query.filter_by(user_id=user_id).order_by(YogaLog.created_at.desc()).limit(10).all()
    
    # Calculate statistics
    all_logs = YogaLog.query.filter_by(user_id=user_id).all()
    total_sessions = len(all_logs)
    total_minutes = sum(log.duration_minutes for log in all_logs)
    avg_duration = round(total_minutes / total_sessions, 1) if total_sessions > 0 else 0
    
    # Calculate streak (consecutive days with sessions)
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

@app.route('/telehealth')
@login_required
def telehealth():
    return render_template('telehealth.html', user_name=session['user_name'])

@app.route('/digital-detox')
@login_required
@role_required('patient')
def digital_detox():
    user_id = session['user_id']
    
    # Get digital detox logs for the user
    screen_time_logs = DigitalDetoxLog.query.filter_by(user_id=user_id).order_by(DigitalDetoxLog.date.desc()).limit(30).all()
    
    # Convert to list of dictionaries for JSON serialization
    screen_time_log = []
    for log in screen_time_logs:
        screen_time_log.append({
            'date': log.date.strftime('%Y-%m-%d'),
            'hours': log.screen_time_hours,
            'academic_score': log.academic_score,
            'social_interactions': log.social_interactions,
            'ai_score': log.ai_score
        })
    
    # Calculate average screen time
    avg_screen_time = 0
    if screen_time_log:
        total_hours = sum(log['hours'] for log in screen_time_log)
        avg_screen_time = round(total_hours / len(screen_time_log), 1)

    # Get the latest AI insights
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

@app.route('/analytics')
@login_required
@role_required('provider')
def analytics():
    return render_template('analytics.html', user_name=session['user_name'])

@app.route('/wellness-report/<int:user_id>')
@login_required
@role_required('provider')
def wellness_report(user_id):
    from datetime import datetime
    
    patient = User.query.get_or_404(user_id)
    
    # Get gamification data
    gamification = Gamification.query.filter_by(user_id=user_id).first()
    
    # Get AI analysis data
    ai_analysis = Assessment.query.filter_by(user_id=user_id).order_by(Assessment.created_at.desc()).first()
    
    # Get wellness trend data (last 90 days)
    digital_detox_logs = DigitalDetoxLog.query.filter_by(user_id=user_id).order_by(DigitalDetoxLog.date.desc()).limit(90).all()
    assessments = Assessment.query.filter_by(user_id=user_id).order_by(Assessment.created_at.desc()).limit(20).all()
    
    # Convert digital detox logs to JSON serializable format
    digital_detox_data = []
    for log in digital_detox_logs:
        digital_detox_data.append({
            'date': log.date.strftime('%Y-%m-%d'),
            'screen_time_hours': log.screen_time_hours,
            'academic_score': log.academic_score,
            'social_interactions': log.social_interactions,
            'ai_score': log.ai_score
        })
    
    # Convert assessments to JSON serializable format
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
    
    # Get recent clinical sessions (mock data for now)
    recent_sessions = []
    
    return render_template('wellness_report.html', 
                         user_name=session['user_name'], 
                         patient=patient,
                         gamification=gamification,
                         ai_analysis=ai_analysis,
                         wellness_trend=wellness_trend,
                         recent_sessions=recent_sessions,
                         datetime=datetime)

@app.route('/profile')
@login_required
def profile():
    user_id = session['user_id']
    user = User.query.filter_by(email=session['user_email']).first()
    
    # Get gamification data
    gamification = Gamification.query.filter_by(user_id=user_id).first()
    
    # Get digital detox data for averages
    digital_detox_logs = DigitalDetoxLog.query.filter_by(user_id=user_id).order_by(DigitalDetoxLog.date.desc()).all()
    
    # Calculate screen time averages
    avg_screen_time_7_days = None
    avg_screen_time_30_days = None
    
    if digital_detox_logs:
        # Last 7 days
        recent_7_days = digital_detox_logs[:7]
        if recent_7_days:
            avg_screen_time_7_days = sum(log.screen_time_hours for log in recent_7_days) / len(recent_7_days)
        
        # Last 30 days
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

@app.route('/api/institutional-trends')
@login_required
@role_required('provider')
def institutional_trends():
    return jsonify([])

@app.route('/api/institutional-mood-trends')
@login_required
@role_required('provider')
def institutional_mood_trends():
    return jsonify([])

@app.route('/api/institutional-assessment-history')
@login_required
@role_required('provider')
def institutional_assessment_history():
    return jsonify([])

@app.route('/api/digital-detox-data')
@login_required
@role_required('patient')
def digital_detox_data():
    user_id = session['user_id']
    
    # Get digital detox logs for the user
    screen_time_logs = DigitalDetoxLog.query.filter_by(user_id=user_id).order_by(DigitalDetoxLog.date.desc()).limit(30).all()
    
    # Convert to list of dictionaries for JSON response
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

@app.route('/api/log-breathing-session', methods=['POST'])
@login_required
def log_breathing_session():
    """Log a breathing exercise session"""
    try:
        data = request.json
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data provided.'
            }), 400
        
        exercise_name = data.get('exercise_name', 'Custom Session')
        duration_minutes = int(data.get('duration_minutes', 0))
        notes = data.get('notes', '')
        
        # Validate data
        if duration_minutes <= 0 or duration_minutes > 120:
            return jsonify({
                'success': False,
                'message': 'Invalid duration. Must be between 1-120 minutes.'
            }), 400
        
        # Create new breathing log entry
        new_log = BreathingExerciseLog(
            user_id=session.get('user_id'),
            exercise_name=exercise_name,
            duration_minutes=duration_minutes,
            notes=notes,
            created_at=datetime.now()
        )
        
        db.session.add(new_log)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Breathing session logged successfully!'
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error logging breathing session for user {session.get('user_id')}: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to log session. Please try again.'
        }), 500

@app.route('/api/log-yoga-session', methods=['POST'])
@login_required
def log_yoga_session():
    """Log a yoga session"""
    try:
        data = request.json
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data provided.'
            }), 400
        
        session_name = data.get('session_name', 'Custom Session')
        duration_minutes = int(data.get('duration_minutes', 0))
        difficulty_level = data.get('difficulty_level', 'Beginner')
        notes = data.get('notes', '')
        
        # Validate data
        if duration_minutes <= 0 or duration_minutes > 120:
            return jsonify({
                'success': False,
                'message': 'Invalid duration. Must be between 1-120 minutes.'
            }), 400
        
        # Create new yoga log entry
        new_log = YogaLog(
            user_id=session.get('user_id'),
            session_name=session_name,
            duration_minutes=duration_minutes,
            difficulty_level=difficulty_level,
            notes=notes,
            created_at=datetime.utcnow() # Use utcnow for consistency
        )
        
        db.session.add(new_log)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Yoga session logged successfully!'
        })
    except ValueError as ve:
        db.session.rollback()
        logger.error(f"Validation error in yoga session for user {session.get('user_id')}: {ve}")
        return jsonify({
            'success': False,
            'message': f'Validation error: {str(ve)}'
        }), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error logging yoga session for user {session.get('user_id')}: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'message': 'Failed to log session. Please try again.'
        }), 500

@app.route('/api/submit-digital-detox', methods=['POST'])
@login_required
@role_required('patient')
def submit_digital_detox():
    try:
        user_id = session['user_id']
        data = request.json
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data provided.'
            }), 400
        
        screen_time = float(data.get('screen_time', 0))
        academic_score = int(data.get('academic_score', 0))
        social_interactions = data.get('social_interactions', 'medium')
        
        # Validate data
        if screen_time < 0 or screen_time > 24:
            return jsonify({
                'success': False,
                'message': 'Invalid screen time value.'
            }), 400
        
        if academic_score < 0 or academic_score > 100:
            return jsonify({
                'success': False,
                'message': 'Invalid academic score value.'
            }), 400
        
        # Create new digital detox log entry
        new_log = DigitalDetoxLog(
            user_id=user_id,
            date=date.today(),
            screen_time_hours=screen_time,
            academic_score=academic_score,
            social_interactions=social_interactions
        )
        
        # Check if entry for today already exists
        existing_log = DigitalDetoxLog.query.filter_by(
            user_id=user_id,
            date=date.today()
        ).first()
        
        if existing_log:
            # Update existing entry
            existing_log.screen_time_hours = screen_time
            existing_log.academic_score = academic_score
            existing_log.social_interactions = social_interactions
        else:
            # Add new entry
            db.session.add(new_log)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Digital wellness data saved successfully!'
        })
        
    except ValueError as e:
        db.session.rollback()
        logger.error(f"Validation error in digital detox data for user {session.get('user_id')}: {e}")
        return jsonify({
            'success': False,
            'message': 'Invalid data format. Please check your input.'
        }), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error saving digital detox data for user {session.get('user_id')}: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to save data. Please try again.'
        }), 500


@app.route('/api/analyze-digital-detox', methods=['POST'])
@login_required
@role_required('patient')
def api_analyze_digital_detox():
    user_id = session['user_id']
    logger.info(f"Starting digital detox analysis for user {user_id}")
    
    # Get the most recent digital detox log
    latest_log = DigitalDetoxLog.query.filter_by(user_id=user_id).order_by(DigitalDetoxLog.date.desc()).first()
    
    if not latest_log:
        logger.warning(f"No digital detox data found for user {user_id}")
        return jsonify({'success': False, 'message': 'No digital detox data found.'}), 404
        
    # Prepare data for AI service
    detox_data = {
        'screen_time_hours': latest_log.screen_time_hours,
        'academic_score': latest_log.academic_score,
        'social_interactions': latest_log.social_interactions
    }
    logger.info(f"Digital detox data for user {user_id}: {detox_data}")
    
    try:
        # Generate insights
        logger.info(f"Generating digital detox insights for user {user_id}")
        insights = ai_service.generate_digital_detox_insights(detox_data)
        logger.info(f"Digital detox insights for user {user_id}: {insights}")
        
        # Update the log with the new insights
        latest_log.ai_score = insights.get('ai_score')
        latest_log.ai_suggestion = insights.get('ai_suggestion')
        
        db.session.commit()
        logger.info(f"Digital detox insights saved for user {user_id}")
        
        return jsonify({'success': True, 'insights': insights})
        
    except Exception as e:
        logger.error(f"Error analyzing digital detox for user {user_id}: {e}")
        return jsonify({'success': False, 'message': 'An error occurred while analyzing your data.'}), 500


@app.route('/assessment')
@login_required
@role_required('patient')
def assessment():
    # Debug session data
    print("\n=== Session Debug Info ===")
    print(f"User ID in session: {session.get('user_id')}")
    print(f"User email in session: {session.get('user_email')}")
    print(f"User role in session: {session.get('user_role')}")
    print(f"Session keys: {list(session.keys())}")
    print("=========================\n")
    
    if 'user_id' not in session:
        print("ERROR: User ID not found in session")
        flash('Please log in to continue', 'error')
        return redirect(url_for('login'))
        
    user_id = session['user_id']
    assessment_objects = Assessment.query.filter_by(user_id=user_id).order_by(Assessment.created_at.desc()).all()
    
    # Convert SQLAlchemy objects to a list of dictionaries
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
        
        # Parse ai_insights if it exists
        if assessment.ai_insights:
            if isinstance(assessment.ai_insights, str):
                try:
                    assessment_dict['ai_insights'] = json.loads(assessment.ai_insights)
                except json.JSONDecodeError:
                    assessment_dict['ai_insights'] = {}
            else:
                assessment_dict['ai_insights'] = assessment.ai_insights
        
        assessments.append(assessment_dict)
    
    # Get the latest insights to display on the page
    latest_insights = None
    if assessments:
        # The first assessment in the sorted list is the latest one
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
        print("DEBUG: Request is not JSON.")
        return jsonify({'success': False, 'message': 'Request must be JSON'}), 400
        
    user_id = session['user_id']
    data = request.get_json()
    print(f"DEBUG: Received assessment data: {data}")
    
    # Extract data from request
    assessment_type = data.get('assessment_type')
    score = data.get('score')
    responses = data.get('responses', {})
    
    if not all([assessment_type, score is not None]):
        print("DEBUG: Missing required fields for assessment.")
        return jsonify({
            'success': False,
            'message': 'Missing required fields: assessment_type and score are required'
        }), 400

    # Generate AI insights
    ai_insights = {}
    ai_insights_generated_successfully = True
    try:
        print("DEBUG: Generating AI insights for assessment.")
        ai_insights = ai_service.generate_assessment_insights(
            assessment_type=assessment_type,
            score=score,
            responses=responses
        )
        print(f"DEBUG: AI insights generated: {ai_insights}")
    except Exception as e:
        logger.error(f"Error generating AI insights: {e}")
        print(f"DEBUG: Error generating AI insights: {e}")
        ai_insights_generated_successfully = False
        ai_insights = {
            'summary': 'AI insights are currently unavailable. Please try again later.',
            'recommendations': [],
            'resources': []
        }

    try:
        print("DEBUG: Creating new assessment record.")
        # Create new assessment record
        assessment = Assessment(
            user_id=user_id,
            assessment_type=assessment_type.upper(),  # GAD-7 or PHQ-9
            score=score,
            responses=responses,
            ai_insights=json.dumps(ai_insights) if ai_insights else None
        )
        
        db.session.add(assessment)
        print("DEBUG: Assessment added to session.")
        
        # Update gamification points
        gamification = Gamification.query.filter_by(user_id=user_id).first()
        if not gamification:
            gamification = Gamification(user_id=user_id, points=0, streak=0)
            db.session.add(gamification)
            print("DEBUG: New gamification record added to session.")
        
        # Add points for completing assessment
        gamification.points += 20  # More points for completing an assessment
        print(f"DEBUG: Gamification points updated: {gamification.points}")
        
        # Update streak if this is the first assessment today
        today = datetime.utcnow().date()
        if not gamification.last_activity or gamification.last_activity < today:
            gamification.streak += 1
            print(f"DEBUG: Gamification streak updated: {gamification.streak}")
        gamification.last_activity = datetime.utcnow().date()

        # Update user's last assessment time
        user = User.query.get(user_id)
        user.last_assessment_at = datetime.utcnow()
        
        print("DEBUG: Attempting to commit changes to database.")
        db.session.commit()
        print("DEBUG: Changes committed successfully.")
        
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
        print(f"DEBUG: Error saving assessment: {e}")
        return jsonify({
            'success': False,
            'message': f'Failed to save assessment: {str(e)}',
            'insights': ai_insights if 'ai_insights' in locals() else None
        }), 500

@app.route('/goals')
@login_required
@role_required('patient')
def goals():
    return render_template('goals.html', user_name=session['user_name'])

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
        
        user = User.query.get(user_id)
        last_assessment_at = user.last_assessment_at

        # Check for cached recommendations
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
        logger.error(f"Error loading progress page for user {session.get('user_id')}: {e}")
        flash('An error occurred while loading your progress page. Please try again later.', 'error')
        return redirect(url_for('patient_dashboard'))

@app.route('/api/goals', methods=['GET'])
@login_required
@role_required('patient')
def get_goals():
    user_id = session['user_id']
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

@app.route('/api/goals', methods=['POST'])
@login_required
@role_required('patient')
def add_goal():
    user_id = session['user_id']
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
        # Parse target_date if provided
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
            target_value=float(target_value) if target_value else None,
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

@app.route('/api/goals/<int:goal_id>', methods=['PUT'])
@login_required
@role_required('patient')
def update_goal(goal_id):
    user_id = session['user_id']
    goal = Goal.query.filter_by(id=goal_id, user_id=user_id).first()

    if not goal:
        return jsonify({'success': False, 'message': 'Goal not found.'}), 404

    data = request.json
    completed = data.get('completed')
    if 'priority' in data:
        goal.priority = data['priority']

    try:
        if completed:
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

@app.route('/api/goals/<int:goal_id>', methods=['DELETE'])
@login_required
@role_required('patient')
def delete_goal(goal_id):
    """Delete a goal"""
    goal = Goal.query.get_or_404(goal_id)
    
    if goal.user_id != session['user_id']:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    try:
        db.session.delete(goal)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Goal deleted successfully!'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error deleting goal: {str(e)}'})

@app.route('/api/chat-message', methods=['POST'])
@login_required
def api_chat_message():
    user_id = session['user_id']
    user_message = request.json.get('message')

    if not user_message:
        return jsonify({'reply': 'No message received.'})

    # Check for crisis keywords
    crisis_keywords = ['suicide', 'kill myself', 'hopeless', 'end it all', 'self-harm']
    if any(keyword in user_message.lower() for keyword in crisis_keywords):
        return jsonify({
            'reply': 'It sounds like you are going through a difficult time. Please reach out for immediate help. You can call the National Suicide Prevention Lifeline at 988 or visit their website. You are not alone.',
            'is_crisis': True
        })

    # Get user context for AI
    gamification = Gamification.query.filter_by(user_id=user_id).first()
    wellness_trend = get_user_wellness_trend(user_id)

    context = {
        'wellness_score': wellness_trend.get('current_score', 'N/A'),
        'engagement_level': f"{gamification.points} points, {gamification.streak} day streak" if gamification else 'Low'
    }

    try:
        # Generate AI chat response
        ai_reply = ai_service.generate_chat_response(user_message, context)
        return jsonify({'reply': ai_reply, 'is_crisis': False})
    except Exception as e:
        logger.error(f"Error in AI chat for user {user_id}: {e}")
        return jsonify({'reply': 'I am having trouble connecting right now. Please know that your feelings are valid.'}), 500


@app.route('/api/institutional-analytics')
@login_required
@role_required('provider')
def api_institutional_analytics():
    institution = session.get('user_institution')
    if not institution:
        return jsonify({'error': 'Institution not found for user'}), 404

    summary = get_institutional_summary(institution)
    return jsonify(summary)

@app.route('/api/ai-status')
@login_required
@role_required('provider')
def api_ai_status():
    """Check AI service status and rate limits"""
    try:
        status = ai_service.check_api_status()
        model_info = ai_service.get_model_info()
        
        return jsonify({
            'status': status,
            'model_info': model_info,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error checking AI status: {e}")
        return jsonify({
            'status': {'status': 'error', 'message': str(e)},
            'model_info': ai_service.get_model_info(),
            'timestamp': datetime.now().isoformat()
        })

@app.route('/api/enhanced-clinical-analysis', methods=['POST'])
@login_required
@role_required('provider')
def api_enhanced_clinical_analysis():
    """Generate enhanced clinical analysis using multiple AI models"""
    try:
        data = request.json
        transcript = data.get('transcript', '')
        patient_data = data.get('patient_data', {})
        
        if not transcript:
            return jsonify({'error': 'Transcript is required'}), 400
        
        # Generate enhanced analysis
        analysis = ai_service.generate_enhanced_clinical_analysis(transcript, patient_data)
        
        return jsonify({
            'success': True,
            'analysis': analysis
        })
        
    except Exception as e:
        logger.error(f"Error in enhanced clinical analysis: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

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

@app.context_processor
def utility_processor():
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

if __name__ == '__main__':
    # Create an app context for database initialization
    with app.app_context():
        # Create all database tables
        db.create_all()
        
        # Check if database needs initialization
        if User.query.first() is None:
            print("Initializing database with sample data...")
            init_database(app)
            print("Database initialized successfully!")
    
    # Start the Flask development server
    app.run(debug=True, port=5000, use_reloader=False)