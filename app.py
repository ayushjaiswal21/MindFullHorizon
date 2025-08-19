from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from models import db, User, Assessment, DigitalDetoxLog, RPMData, Gamification, ClinicalNote, InstitutionalAnalytics, Appointment, Goal, get_user_wellness_trend, get_institutional_summary
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
from functools import wraps
import random
import logging
import json
import os
import time
from ai_service import ai_service
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'supersecretkey')  # Use environment variable or fallback

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

# Database configuration
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(basedir, "mindful_horizon.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db.init_app(app)

def init_database():
    """Initialize database with sample data"""
    with app.app_context():
        db.create_all()
        
        # Check if users already exist
        if User.query.first() is None:
            # Create sample users
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
            
            # Create sample gamification data
            gamification = Gamification(
                user_id=patient.id,
                points=1250,
                streak=7,
                badges=['Early Bird', 'Consistency Champion', 'Mood Tracker'],
                last_activity=date.today()
            )
            
            # Create sample RPM data
            rpm_data = RPMData(
                user_id=patient.id,
                date=date.today(),
                heart_rate=72,
                sleep_duration=7.5,
                steps=8500,
                mood_score=8
            )
            
            # Create sample digital detox data
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
init_database()

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
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']
        
        # Query database for user
        user = User.query.filter_by(email=email, role=role).first()
        
        if user and user.check_password(password):
            session['user_email'] = email
            session['user_role'] = role
            session['user_name'] = user.name
            session['user_id'] = user.id
            session['user_institution'] = user.institution
            
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
            
        except Exception as e:
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
    gamification = Gamification.query.filter_by(user_id=user_id).first()
    rpm_data = RPMData.query.filter_by(user_id=user_id).order_by(RPMData.date.desc()).first()

    # Get appointments
    today = date.today()
    all_appointments = Appointment.query.filter_by(user_id=user_id).order_by(Appointment.date.asc(), Appointment.time.asc()).all()

    upcoming_appointments = []
    past_appointments = []

    for appt in all_appointments:
        appt_datetime_str = f"{appt.date} {appt.time}"
        appt_datetime = datetime.strptime(appt_datetime_str, '%Y-%m-%d %H:%M')
        if appt_datetime >= datetime.now():
            upcoming_appointments.append(appt)
        else:
            past_appointments.append(appt)

    # Prepare data structure
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

    # Check for RPM alerts
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
        # Get latest digital detox data for risk assessment
        latest_detox = DigitalDetoxLog.query.filter_by(user_id=patient.id).order_by(DigitalDetoxLog.date.desc()).first()
        latest_session = ClinicalNote.query.filter_by(patient_id=patient.id).order_by(ClinicalNote.session_date.desc()).first()
        
        # Determine risk level based on AI score and screen time
        risk_level = 'Low'
        if latest_detox:
            if latest_detox.screen_time_hours > 8 or latest_detox.ai_score == 'Needs Improvement':
                risk_level = 'High'
            elif latest_detox.screen_time_hours > 6 or latest_detox.ai_score == 'Good':
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
    
    # Get institutional analytics
    institutional_data = get_institutional_summary(institution)
    
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

def generate_clinical_note(transcript):
    """Simulate AI-powered clinical note generation"""
    return f"""
CLINICAL NOTE - Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}

PATIENT PRESENTATION:
Based on the session transcript, the patient presented with concerns related to their mental health status.

KEY OBSERVATIONS:
- Patient engagement level: High
- Emotional state: Stable with some areas of concern
- Treatment compliance: Good

ASSESSMENT:
The patient demonstrates good insight into their condition and shows willingness to engage in therapeutic interventions.

PLAN:
1. Continue current therapeutic approach
2. Monitor progress in next session
3. Consider additional resources if needed

SESSION SUMMARY:
{transcript[:200]}{'...' if len(transcript) > 200 else ''}

Next appointment recommended within 1-2 weeks.

Dr. {session.get('user_name', 'Provider')}
Licensed Mental Health Professional
"""

@app.route('/telehealth')
@login_required
def telehealth():
    return render_template('telehealth.html', user_name=session['user_name'])

@app.route('/assessment')
@login_required
@role_required('patient')
def assessment():
    user_id = session['user_id']
    assessments = Assessment.query.filter_by(user_id=user_id).order_by(Assessment.created_at.desc()).all()
    return render_template('assessment.html', user_name=session['user_name'], assessments=assessments)

@app.route('/api/save-assessment', methods=['POST'])
@login_required
@role_required('patient')
def api_save_assessment():
    user_id = session['user_id']
    assessment_type = request.json.get('assessment_type')
    score = request.json.get('score')
    responses = request.json.get('responses')

    try:
        new_assessment = Assessment(
            user_id=user_id,
            assessment_type=assessment_type,
            score=score,
            responses=responses
        )
        db.session.add(new_assessment)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Assessment saved successfully!'}), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error saving assessment for user {user_id}: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/progress')
@login_required
@role_required('patient')
def progress():
    try:
        user_id = session['user_id']
        goals = Goal.query.filter_by(user_id=user_id).all() or []
        achievements = [goal.description for goal in goals if goal.status == 'completed']
        
        # Initialize with None values for new users
        latest_gad7 = None
        latest_phq9 = None
        latest_mood = None
        
        # Fetch latest assessment scores if they exist
        assessments = Assessment.query.filter_by(user_id=user_id).all()
        if assessments:
            latest_gad7 = next((a for a in assessments if a.assessment_type == 'GAD-7'), None)
            latest_phq9 = next((a for a in assessments if a.assessment_type == 'PHQ-9'), None)
            latest_mood = next((a for a in assessments if a.assessment_type == 'Daily Mood'), None)

        # Initialize empty data structures
        mood_data = []
        assessment_chart_data = {}
        all_assessment_dates = set()
    
        # Only process if we have assessments
        if assessments:
            # Fetch historical mood data for chart (last 30 days)
            mood_assessments = [a for a in assessments if a.assessment_type == 'Daily Mood']
            mood_assessments = sorted(mood_assessments, key=lambda x: x.created_at)[-30:]  # Last 30 entries
            if mood_assessments:
                mood_data = [{'date': m.created_at.strftime('%Y-%m-%d'), 'score': m.score} for m in mood_assessments]
            
            # Process GAD-7 and PHQ-9 data for chart
            gad7_assessments = [a for a in assessments if a.assessment_type == 'GAD-7']
            phq9_assessments = [a for a in assessments if a.assessment_type == 'PHQ-9']
            
            for a in gad7_assessments:
                date_str = a.created_at.strftime('%Y-%m-%d')
                all_assessment_dates.add(date_str)
                if date_str not in assessment_chart_data:
                    assessment_chart_data[date_str] = {'gad7': None, 'phq9': None}
                assessment_chart_data[date_str]['gad7'] = a.score
                
            for a in phq9_assessments:
                date_str = a.created_at.strftime('%Y-%m-%d')
                all_assessment_dates.add(date_str)
                if date_str not in assessment_chart_data:
                    assessment_chart_data[date_str] = {'gad7': None, 'phq9': None}
                assessment_chart_data[date_str]['phq9'] = a.score

        # Prepare chart data with proper null handling
        if all_assessment_dates:
            sorted_dates = sorted(list(all_assessment_dates))
            assessment_chart_labels = sorted_dates
            assessment_chart_gad7_data = [assessment_chart_data.get(d, {}).get('gad7') for d in sorted_dates]
            assessment_chart_phq9_data = [assessment_chart_data.get(d, {}).get('phq9') for d in sorted_dates]
        else:
            # Empty data for charts when no assessments exist
            assessment_chart_labels = []
            assessment_chart_gad7_data = []
            assessment_chart_phq9_data = []

        # Calculate overall wellness score only if we have data
        overall_wellness_score = 'No data'
        scores_to_average = []

        if latest_gad7 and hasattr(latest_gad7, 'score'):
            try:
                gad7_score = float(latest_gad7.score) if latest_gad7.score is not None else 0
                scores_to_average.append(10 - (gad7_score / 21 * 9))  # Normalize GAD-7 (0-21 to 10-1)
            except (ValueError, TypeError):
                pass
                
        if latest_phq9 and hasattr(latest_phq9, 'score'):
            try:
                phq9_score = float(latest_phq9.score) if latest_phq9.score is not None else 0
                scores_to_average.append(10 - (phq9_score / 27 * 9))  # Normalize PHQ-9 (0-27 to 10-1)
            except (ValueError, TypeError):
                pass
                
        if latest_mood and hasattr(latest_mood, 'score'):
            try:
                mood_score = float(latest_mood.score) if latest_mood.score is not None else 0
                scores_to_average.append(mood_score * 2)  # Normalize Mood (0-5 to 0-10)
            except (ValueError, TypeError):
                pass

        if scores_to_average:
            overall_wellness_score = round(sum(scores_to_average) / len(scores_to_average), 1)

        # Ensure we have valid data for the template
        # Ensure user_name is set in session
        if 'user_name' not in session:
            user = User.query.get(user_id)
            if user:
                # Safely get user's name, defaulting to 'User' if not available
                user_name = getattr(user, 'name', None) or getattr(user, 'first_name', 'User')
                session['user_name'] = user_name

        return render_template(
            'progress.html',
            user_name=session.get('user_name', 'User'),
            latest_gad7=latest_gad7,
            latest_phq9=latest_phq9,
            latest_mood=latest_mood,
            overall_wellness_score=overall_wellness_score,
            mood_data=json.dumps(mood_data or []),
            assessment_chart_labels=json.dumps(assessment_chart_labels or []),
            assessment_chart_gad7_data=json.dumps(assessment_chart_gad7_data or []),
            assessment_chart_phq9_data=json.dumps(assessment_chart_phq9_data or []),
            goals=goals,
            achievements=achievements,
        )
    except Exception as e:
        app.logger.error(f"Error in progress route: {str(e)}")
        # Provide a more user-friendly error message
        return render_template('error.html', 
                            error_message="Please complete your first assessment before viewing progress. Click the button below to start your assessment.",
                            status_code=200)

@app.route('/digital-detox', methods=['GET', 'POST'])
@login_required
@role_required('patient')
def digital_detox():
    user_id = session['user_id']
    
    if request.method == 'POST':
        # Handle form submission - save to database
        screen_time = float(request.form.get('screen_time', 0))
        academic_score = int(request.form.get('academic_score', 0))
        social_interactions = request.form.get('social_interactions', '')
        
        # Get historical data for AI analysis
        historical_logs = DigitalDetoxLog.query.filter_by(user_id=user_id).order_by(DigitalDetoxLog.date.desc()).limit(30).all()
        historical_data = [
            {
                'screen_time_hours': log.screen_time_hours,
                'academic_score': log.academic_score,
                'social_interactions': log.social_interactions,
                'date': log.date.strftime('%Y-%m-%d')
            } for log in historical_logs
        ]
        
        # Use AI service for analysis with logging
        logger.info(f"Starting AI analysis for user {user_id} - screen_time: {screen_time}h, academic_score: {academic_score}")
        start_time = time.time()
        
        ai_analysis = ai_service.analyze_digital_wellness(
            screen_time=screen_time,
            academic_score=academic_score,
            social_interactions=social_interactions,
            historical_data=historical_data
        )
        
        analysis_time = time.time() - start_time
        logger.info(f"AI analysis completed in {analysis_time:.2f} seconds for user {user_id}")
        logger.debug(f"AI analysis result: {ai_analysis}")
        
        # Save to database with AI insights
        new_log = DigitalDetoxLog(
            user_id=user_id,
            date=date.today(),
            screen_time_hours=screen_time,
            academic_score=academic_score,
            social_interactions=social_interactions,
            ai_score=ai_analysis.get('score'),
            ai_suggestion=ai_analysis.get('suggestion')
        )
        
        # Check if entry for today already exists
        existing_log = DigitalDetoxLog.query.filter_by(user_id=user_id, date=date.today()).first()
        if existing_log:
            # Update existing entry
            existing_log.screen_time_hours = screen_time
            existing_log.academic_score = academic_score
            existing_log.social_interactions = social_interactions
            existing_log.ai_score = ai_analysis.get('score')
            existing_log.ai_suggestion = ai_analysis.get('suggestion')
        else:
            db.session.add(new_log)
        
        # Update gamification
        gamification = Gamification.query.filter_by(user_id=user_id).first()
        points_earned = 10
        badge_earned = None
        new_badges = []
        
        if gamification:
            gamification.points += points_earned
            
            # Update streak
            if gamification.last_activity and gamification.last_activity == date.today() - timedelta(days=1):
                gamification.streak += 1
            elif gamification.last_activity != date.today(): # Reset streak if not consecutive but not already logged today
                gamification.streak = 1
            
            gamification.last_activity = date.today()
            
            # Award badges based on AI score
            if ai_analysis.get('score') == 'Excellent' and 'Digital Wellness Master' not in gamification.badges:
                gamification.badges.append('Digital Wellness Master')
                gamification.points += 50
                points_earned += 50
                new_badges.append('Digital Wellness Master')

            # Award streak badges
            if gamification.streak >= 7 and '7-Day Streak' not in gamification.badges:
                gamification.badges.append('7-Day Streak')
                gamification.points += 25
                new_badges.append('7-Day Streak')
            if gamification.streak >= 30 and '30-Day Streak' not in gamification.badges:
                gamification.badges.append('30-Day Streak')
                gamification.points += 100
                new_badges.append('30-Day Streak')

            # Award reduced mobile usage badge
            # Fetch historical data for comparison (last 14 days for 7-day comparison)
            past_14_days_logs = DigitalDetoxLog.query.filter(
                DigitalDetoxLog.user_id == user_id,
                DigitalDetoxLog.date >= date.today() - timedelta(days=14),
                DigitalDetoxLog.date < date.today() - timedelta(days=7) # Previous week
            ).all()
            
            if past_14_days_logs:
                prev_week_avg_screen_time = sum(log.screen_time_hours for log in past_14_days_logs) / len(past_14_days_logs)
                if screen_time < prev_week_avg_screen_time * 0.9 and 'Screen Time Reducer' not in gamification.badges: # 10% reduction
                    gamification.badges.append('Screen Time Reducer')
                    gamification.points += 75
                    new_badges.append('Screen Time Reducer')

        try:
            db.session.commit()
            logger.info(f"Digital detox log saved for user {user_id} with AI score: {ai_analysis.get('score')}")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error saving digital detox log for user {user_id}: {e}")
            flash('An error occurred while saving your data. Please try again.', 'error')
            return redirect(url_for('digital_detox'))
        
        # Enhanced success message with gamification feedback
        flash_message = f'✅ Check-in saved! You earned {points_earned} points.'
        if new_badges:
            flash_message += f' 🎉 New badges earned: {", ".join(new_badges)}!'
        flash(flash_message, 'success')
        
        return redirect(url_for('digital_detox'))
    
    # Get data from database
    screen_time_logs = DigitalDetoxLog.query.filter_by(user_id=user_id).order_by(DigitalDetoxLog.date.desc()).limit(30).all()
    
    # Prepare data for template
    screen_time_log = [
        {
            'date': log.date.strftime('%Y-%m-%d'),
            'hours': log.screen_time_hours,
            'academic_score': log.academic_score,
            'social_interactions': log.social_interactions
        } for log in screen_time_logs
    ]
    
    # Calculate average screen time
    avg_screen_time = round(sum(log.screen_time_hours for log in screen_time_logs) / len(screen_time_logs), 1) if screen_time_logs else 0
    
    # Get latest AI analysis
    latest_log = screen_time_logs[0] if screen_time_logs else None
    score = latest_log.ai_score if latest_log and latest_log.ai_score else 'No data yet'
    suggestion = latest_log.ai_suggestion if latest_log and latest_log.ai_suggestion else 'Log your daily data to receive AI-powered insights!'
    
    return render_template('digital_detox.html', 
                         user_name=session['user_name'],
                         screen_time_log=screen_time_log,
                         avg_screen_time=avg_screen_time,
                         score=score,
                         suggestion=suggestion)

@app.route('/api/digital-detox-data')
@login_required
def api_digital_detox_data():
    user_id = session['user_id']
    
    # Get data from database
    logs = DigitalDetoxLog.query.filter_by(user_id=user_id).order_by(DigitalDetoxLog.date.desc()).limit(30).all()
    
    screen_time_data = [
        {
            'date': log.date.strftime('%Y-%m-%d'),
            'hours': log.screen_time_hours
        } for log in reversed(logs)  # Reverse to show chronological order
    ]
    
    return jsonify(screen_time_data)

@app.route('/analytics')
@login_required
@role_required('provider')
def analytics():
    """Advanced analytics dashboard for providers"""
    institution = session.get('user_institution', 'Sample University')
    
    # Get institutional data and AI analysis
    institutional_data = get_institutional_summary(institution)
    
    if institutional_data:
        # Use AI service for institutional analysis
        ai_insights = ai_service.analyze_institutional_trends(institutional_data)
    else:
        ai_insights = {
            'overall_status': 'No Data',
            'key_insights': ['No data available yet'],
            'recommendations': ['Encourage student participation'],
            'priority_actions': ['Set up data collection']
        }
    
    # Get detailed patient analytics
    patients = User.query.filter_by(role='patient', institution=institution).all()
    patient_analytics = []
    
    for patient in patients:
        wellness_trend = get_user_wellness_trend(patient.id, days=30)
        recent_detox = wellness_trend['digital_detox'][-1] if wellness_trend.get('digital_detox') else None
        
        patient_analytics.append({
            'id': patient.id,
            'name': patient.name,
            'email': patient.email,
            'trend_data': [
                {
                    'date': log.date.strftime('%Y-%m-%d'),
                    'screen_time': log.screen_time_hours,
                    'academic_score': log.academic_score,
                    'ai_score': log.ai_score
                } for log in wellness_trend['digital_detox'][-14:]  # Last 14 days
            ],
            'current_status': recent_detox.ai_score if recent_detox and recent_detox.ai_score else 'No data'
        })
    
    return render_template('analytics.html',
                         user_name=session['user_name'],
                         institution=institution,
                         institutional_data=institutional_data,
                         ai_insights=ai_insights,
                         patient_analytics=patient_analytics)

@app.route('/api/institutional-trends')
@login_required
@role_required('provider')
def api_institutional_trends():
    """API endpoint for institutional trend data"""
    institution = session.get('user_institution', 'Sample University')
    
    # Get trends over the last 30 days
    trends = []
    for i in range(30):
        trend_date = date.today() - timedelta(days=i)
        
        # Get daily institutional metrics (this would be more sophisticated in production)
        daily_logs = db.session.query(DigitalDetoxLog).join(User).filter(
            User.institution == institution,
            DigitalDetoxLog.date == trend_date
        ).all()
        
        if daily_logs:
            avg_screen_time = sum(log.screen_time_hours for log in daily_logs) / len(daily_logs)
            avg_academic = sum(log.academic_score for log in daily_logs if log.academic_score) / max(1, len([log for log in daily_logs if log.academic_score]))
            
            trends.append({
                'date': trend_date.strftime('%Y-%m-%d'),
                'avg_screen_time': round(avg_screen_time, 1),
                'avg_academic_score': round(avg_academic, 1),
                'active_users': len(daily_logs)
            })
    
    return jsonify(list(reversed(trends)))  # Return chronological order

@app.route('/api/institutional-mood-trends')
@login_required
@role_required('provider')
def api_institutional_mood_trends():
    """API endpoint for institutional mood trend data"""
    institution = session.get('user_institution', 'Sample University')
    
    # Get mood trends over the last 30 days
    mood_trends = []
    for i in range(30):
        trend_date = date.today() - timedelta(days=i)
        
        # Get daily mood assessments for the institution
        daily_moods = db.session.query(Assessment).join(User).filter(
            User.institution == institution,
            Assessment.assessment_type == 'Daily Mood',
            func.date(Assessment.created_at) == trend_date
        ).all()
        
        if daily_moods:
            avg_mood = sum(mood.score for mood in daily_moods) / len(daily_moods)
            mood_trends.append({
                'date': trend_date.strftime('%Y-%m-%d'),
                'avg_mood': round(avg_mood, 1),
                'mood_count': len(daily_moods)
            })
    
    return jsonify(list(reversed(mood_trends)))  # Return chronological order

@app.route('/api/institutional-assessment-history')
@login_required
@role_required('provider')
def api_institutional_assessment_history():
    """API endpoint for institutional assessment history data"""
    institution = session.get('user_institution', 'Sample University')
    
    # Get assessment history over the last 12 months
    assessment_history = []
    for i in range(12):
        # Calculate the start and end of each month accurately
        end_of_month = date.today().replace(day=1) - relativedelta(months=i)
        start_of_month = end_of_month.replace(day=1)
        # To get the correct end date for the query, we go to the next month and subtract one day
        end_of_month_for_query = (start_of_month + relativedelta(months=1)) - timedelta(days=1)

        # Get GAD-7 assessments for the month
        gad7_assessments = db.session.query(Assessment).join(User).filter(
            User.institution == institution,
            Assessment.assessment_type == 'GAD-7',
            Assessment.created_at >= start_of_month,
            Assessment.created_at <= end_of_month_for_query
        ).all()

        # Get PHQ-9 assessments for the month
        phq9_assessments = db.session.query(Assessment).join(User).filter(
            User.institution == institution,
            Assessment.assessment_type == 'PHQ-9',
            Assessment.created_at >= start_of_month,
            Assessment.created_at <= end_of_month_for_query
        ).all()
        
        avg_gad7 = None
        avg_phq9 = None
        
        if gad7_assessments:
            avg_gad7 = round(sum(a.score for a in gad7_assessments) / len(gad7_assessments), 1)
        
        if phq9_assessments:
            avg_phq9 = round(sum(a.score for a in phq9_assessments) / len(phq9_assessments), 1)
        
        if avg_gad7 is not None or avg_phq9 is not None:
            assessment_history.append({
                'date': start_date.strftime('%Y-%m-%d'),
                'avg_gad7': avg_gad7,
                'avg_phq9': avg_phq9,
                'assessment_count': len(gad7_assessments) + len(phq9_assessments)
            })
    
    return jsonify(list(reversed(assessment_history)))  # Return chronological order

@app.route('/wellness-report/<int:user_id>')
@login_required
@role_required('provider')
def wellness_report(user_id):
    """Generate comprehensive wellness report for a specific patient"""
    patient = User.query.get_or_404(user_id)
    
    # Ensure provider can only access patients from their institution
    if patient.institution != session.get('user_institution'):
        flash('Access denied. Patient not in your institution.', 'error')
        return redirect(url_for('provider_dashboard'))
    
    # Get comprehensive wellness data
    wellness_trend = get_user_wellness_trend(user_id, days=90)  # 3 months
    gamification = Gamification.query.filter_by(user_id=user_id).first()
    recent_sessions = ClinicalNote.query.filter_by(patient_id=user_id).order_by(ClinicalNote.session_date.desc()).limit(5).all()
    
    # Generate AI-powered wellness summary
    if wellness_trend['digital_detox']:
        historical_data = [
            {
                'screen_time_hours': log.screen_time_hours,
                'academic_score': log.academic_score,
                'social_interactions': log.social_interactions,
                'date': log.date.strftime('%Y-%m-%d')
            } for log in wellness_trend['digital_detox']
        ]
        
        # Use AI for comprehensive analysis
        latest_log = wellness_trend['digital_detox'][-1]
        ai_analysis = ai_service.analyze_digital_wellness(
            screen_time=latest_log.screen_time_hours,
            academic_score=latest_log.academic_score,
            social_interactions=latest_log.social_interactions,
            historical_data=historical_data
        )
    else:
        ai_analysis = {
            'score': 'No data',
            'suggestion': 'Patient has not logged any digital wellness data yet.',
            'detailed_analysis': 'No historical data available for analysis.',
            'action_items': ['Encourage patient to start logging daily data']
        }
    
    return render_template('wellness_report.html',
                         patient=patient,
                         wellness_trend=wellness_trend,
                         gamification=gamification,
                         recent_sessions=recent_sessions,
                         ai_analysis=ai_analysis,
                         user_name=session['user_name'])

@app.route('/profile')
@login_required
def profile():
    user_id = session['user_id']
    user = User.query.get(user_id)
    gamification = Gamification.query.filter_by(user_id=user_id).first()
    digital_detox_logs = DigitalDetoxLog.query.filter_by(user_id=user_id).order_by(DigitalDetoxLog.date.desc()).limit(30).all()

    # Calculate average screen time for last 7 and 30 days
    today = date.today()
    last_7_days_logs = [log for log in digital_detox_logs if log.date >= today - timedelta(days=7)]
    last_30_days_logs = [log for log in digital_detox_logs if log.date >= today - timedelta(days=30)]

    avg_screen_time_7_days = round(sum(log.screen_time_hours for log in last_7_days_logs) / len(last_7_days_logs), 1) if last_7_days_logs else 0
    avg_screen_time_30_days = round(sum(log.screen_time_hours for log in last_30_days_logs) / len(last_30_days_logs), 1) if last_30_days_logs else 0

    return render_template(
        'profile.html',
        user=user,
        gamification=gamification,
        digital_detox_logs=digital_detox_logs,
        avg_screen_time_7_days=avg_screen_time_7_days,
        avg_screen_time_30_days=avg_screen_time_30_days
    )

# Helper function for Jinja2 to get assessment severity info
def get_severity_info(assessment_type, score):
    severity, color = 'N/A', 'gray'
    if assessment_type == 'GAD-7':
        if score <= 4: severity, color = 'Minimal', 'green'
        elif score <= 9: severity, color = 'Mild', 'yellow'
        elif score <= 14: severity, color = 'Moderate', 'orange'
        else: severity, color = 'Severe', 'red'
    elif assessment_type == 'PHQ-9':
        if score <= 4: severity, color = 'Minimal', 'green'
        elif score <= 9: severity, color = 'Mild', 'yellow'
        elif score <= 14: severity, color = 'Moderate', 'orange'
        else: severity, color = 'Severe', 'red'
    elif assessment_type == 'Daily Mood':
        if score >= 4: severity, color = 'Positive', 'green'
        elif score >= 3: severity, color = 'Neutral', 'yellow'
        else: severity, color = 'Negative', 'red'
    return {'severity': severity, 'color': color}

app.jinja_env.globals.update(get_severity_info=get_severity_info)

# AJAX API endpoints for enhanced user experience
@app.route('/api/submit-digital-detox', methods=['POST'])
@login_required
@role_required('patient')
def api_submit_digital_detox():
    """AJAX endpoint for digital detox submission with AI analysis"""
    user_id = session['user_id']
    
    try:
        # Get form data
        screen_time = float(request.json.get('screen_time', 0))
        academic_score = int(request.json.get('academic_score', 0))
        social_interactions = request.json.get('social_interactions', '')
        
        logger.info(f"AJAX digital detox submission for user {user_id}")
        
        # Get historical data for AI analysis
        historical_logs = DigitalDetoxLog.query.filter_by(user_id=user_id).order_by(DigitalDetoxLog.date.desc()).limit(30).all()
        historical_data = [
            {
                'screen_time_hours': log.screen_time_hours,
                'academic_score': log.academic_score,
                'social_interactions': log.social_interactions,
                'date': log.date.strftime('%Y-%m-%d')
            } for log in historical_logs
        ]
        
        # Simulate AI processing time for demo effect
        time.sleep(1.5)
        
        # Use AI service for analysis
        logger.info(f"Starting AI analysis for user {user_id} via AJAX")
        start_time = time.time()
        
        ai_analysis = ai_service.analyze_digital_wellness(
            screen_time=screen_time,
            academic_score=academic_score,
            social_interactions=social_interactions,
            historical_data=historical_data
        )
        
        analysis_time = time.time() - start_time
        logger.info(f"AI analysis completed in {analysis_time:.2f} seconds")
        
        # Save to database
        existing_log = DigitalDetoxLog.query.filter_by(user_id=user_id, date=date.today()).first()
        if existing_log:
            existing_log.screen_time_hours = screen_time
            existing_log.academic_score = academic_score
            existing_log.social_interactions = social_interactions
            existing_log.ai_score = ai_analysis.get('score')
            existing_log.ai_suggestion = ai_analysis.get('suggestion')
        else:
            new_log = DigitalDetoxLog(
                user_id=user_id,
                date=date.today(),
                screen_time_hours=screen_time,
                academic_score=academic_score,
                social_interactions=social_interactions,
                ai_score=ai_analysis.get('score'),
                ai_suggestion=ai_analysis.get('suggestion')
            )
            db.session.add(new_log)
        
        # Update gamification
        gamification = Gamification.query.filter_by(user_id=user_id).first()
        points_earned = 10
        badge_earned = None
        
        if gamification:
            gamification.points += points_earned
            
            # Update streak
            if gamification.last_activity == date.today() - timedelta(days=1):
                gamification.streak += 1
            elif gamification.last_activity != date.today():
                gamification.streak = 1
            
            gamification.last_activity = date.today()
            
            # Award badges based on AI score
            if ai_analysis.get('score') == 'Excellent' and 'Digital Wellness Master' not in gamification.badges:
                gamification.badges.append('Digital Wellness Master')
                gamification.points += 50
                points_earned += 50
                badge_earned = 'Digital Wellness Master'
        
        db.session.commit()
        logger.info(f"Digital detox data saved successfully for user {user_id}")
        
        return jsonify({
            'success': True,
            'ai_analysis': ai_analysis,
            'points_earned': points_earned,
            'badge_earned': badge_earned,
            'analysis_time': round(analysis_time, 2),
            'message': 'Digital detox check-in completed successfully!'
        })
        
    except Exception as e:
        logger.error(f"Error in AJAX digital detox submission: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Goals Management Routes
@app.route('/goals')
@login_required
@role_required('patient')
def goals():
    """Display goals management page"""
    user_id = session['user_id']
    goals = Goal.query.filter_by(user_id=user_id).order_by(Goal.created_at.desc()).all()
    return render_template('goals.html', goals=goals)

@app.route('/api/goals', methods=['GET'])
@login_required
@role_required('patient')
def get_goals():
    """Get all goals for the current user"""
    user_id = session['user_id']
    goals = Goal.query.filter_by(user_id=user_id).order_by(Goal.created_at.desc()).all()
    goals_data = []
    for goal in goals:
        goals_data.append({
            'id': goal.id,
            'title': goal.title,
            'description': goal.description,
            'category': goal.category,
            'target_value': goal.target_value,
            'current_value': goal.current_value,
            'unit': goal.unit,
            'status': goal.status,
            'priority': goal.priority,
            'start_date': goal.start_date.strftime('%Y-%m-%d') if goal.start_date else None,
            'target_date': goal.target_date.strftime('%Y-%m-%d') if goal.target_date else None,
            'progress_percentage': goal.progress_percentage,
            'created_at': goal.created_at.strftime('%Y-%m-%d %H:%M')
        })
    return jsonify({'success': True, 'goals': goals_data})

@app.route('/api/goals', methods=['POST'])
@login_required
@role_required('patient')
def add_goal():
    """Create a new goal"""
    user_id = session['user_id']
    data = request.json
    
    title = data.get('title', '').strip()
    description = data.get('description', '').strip()
    category = data.get('category', 'general')
    target_value = data.get('target_value')
    unit = data.get('unit', '').strip()
    priority = data.get('priority', 'medium')
    target_date = data.get('target_date')
    
    if not title:
        return jsonify({'success': False, 'message': 'Title is required'})
    
    try:
        new_goal = Goal(
            user_id=user_id,
            title=title,
            description=description,
            category=category,
            target_value=float(target_value) if target_value else None,
            unit=unit if unit else None,
            priority=priority,
            start_date=date.today(),
            target_date=datetime.strptime(target_date, '%Y-%m-%d').date() if target_date else None
        )
        
        db.session.add(new_goal)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Goal created successfully!',
            'goal': {
                'id': new_goal.id,
                'title': new_goal.title,
                'description': new_goal.description,
                'category': new_goal.category,
                'status': new_goal.status,
                'priority': new_goal.priority,
                'progress_percentage': new_goal.progress_percentage
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error creating goal: {str(e)}'})

@app.route('/api/goals/<int:goal_id>', methods=['PUT'])
@login_required
@role_required('patient')
def update_goal(goal_id):
    """Update an existing goal"""
    goal = Goal.query.get_or_404(goal_id)
    
    if goal.user_id != session['user_id']:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    data = request.json
    
    try:
        # Update goal fields
        if 'current_value' in data:
            goal.current_value = float(data['current_value'])
        if 'status' in data:
            goal.status = data['status']
            if data['status'] == 'completed' and not goal.completed_date:
                goal.completed_date = date.today()
        if 'title' in data:
            goal.title = data['title']
        if 'description' in data:
            goal.description = data['description']
        if 'priority' in data:
            goal.priority = data['priority']
        
        goal.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Goal updated successfully!',
            'goal': {
                'id': goal.id,
                'progress_percentage': goal.progress_percentage,
                'status': goal.status
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
    return jsonify({'success': False, 'message': 'Goal not found'})

@app.route('/api/rpm-data')
@login_required
@role_required('patient')
def api_rpm_data():
    """API endpoint for real-time RPM data simulation"""
    user_id = session['user_id']
    
    # Get latest RPM data or create simulated data
    rpm_data = RPMData.query.filter_by(user_id=user_id).order_by(RPMData.created_at.desc()).first()
    
    if not rpm_data:
        # Create initial RPM data
        rpm_data = RPMData(
            user_id=user_id,
            date=date.today(),
            heart_rate=72,
            sleep_duration=7.5,
            steps=8500,
            mood_score=7
        )
        db.session.add(rpm_data)
        db.session.commit()
    
    # Simulate real-time variations
    import random
    current_time = datetime.now()
    
    # Generate realistic variations
    heart_rate = max(60, min(100, rpm_data.heart_rate + random.randint(-5, 5)))
    sleep_duration = max(4, min(12, rpm_data.sleep_duration + random.uniform(-0.5, 0.5)))
    steps = max(0, rpm_data.steps + random.randint(-200, 300))
    mood_score = max(1, min(10, rpm_data.mood_score + random.uniform(-0.5, 0.5)))
    
    return jsonify({
        'heart_rate': heart_rate,
        'sleep_duration': round(sleep_duration, 1),
        'steps': steps,
        'mood_score': round(mood_score, 1),
        'timestamp': current_time.strftime('%H:%M:%S'),
        'alerts': []
    })

@app.route('/api/chat-message', methods=['POST'])
@login_required
def api_chat_message():
    """AJAX endpoint for chat functionality"""
    user_message = request.json.get('message', '')
    user_id = session['user_id']
    
    logger.info(f"Chat message from user {user_id}: {user_message}")
    
    # Get user context for AI
    user_context = {
        'wellness_score': 'Good',  # Could be fetched from user data
        'engagement_level': 'Active'
    }
    
    # Generate AI response
    chat_result = ai_service.generate_chat_response(user_message, user_context)
    
    return jsonify({
        'success': True,
        'response': chat_result['response'],
        'is_ai_powered': chat_result['is_ai_powered'],
        'timestamp': datetime.now().strftime('%H:%M')
    })

if __name__ == '__main__':
    init_database()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)