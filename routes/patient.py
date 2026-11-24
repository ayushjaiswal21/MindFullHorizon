from flask import Blueprint, render_template, session, redirect, url_for, flash, request, jsonify, current_app
from models import (User, Gamification, DigitalDetoxLog, Assessment, Goal, Medication,
                MedicationLog, BreathingExerciseLog, YogaLog, ProgressRecommendation,
                Prescription, MoodLog, RPMData, Appointment, JournalEntry, VoiceLog, db)
import os
from decorators import patient_required, login_required
from sqlalchemy.orm import joinedload
from datetime import datetime, date, timedelta, timezone
import json
import ai.service as ai_service
from ai.scoring import canonical_type
from utils.gamification import award_points
import logging


# TextBlob for sentiment analysis
try:
    from textblob import TextBlob
    TEXTBLOB_AVAILABLE = True
except ImportError:
    TEXTBLOB_AVAILABLE = False

logger = logging.getLogger(__name__)

def get_ai_journal_suggestions(title, content):
    """Get AI-powered suggestions for journal entries with optimized prompts."""
    try:
        # Simple sentiment check for context (optional, can be improved)
        sentiment = "Neutral" 
        if TEXTBLOB_AVAILABLE:
             try:
                 blob = TextBlob(content)
                 if blob.sentiment.polarity > 0.1: sentiment = "Positive"
                 elif blob.sentiment.polarity < -0.1: sentiment = "Negative"
             except: pass

        # Use the dedicated AI service function
        suggestions = ai_service.generate_journal_insights(title, content, sentiment)

        # Clean up and format the response for better readability
        suggestions = suggestions.strip()[:800]  # Limit length

        # Ensure we have meaningful content
        if len(suggestions) < 50:  # Too short, probably error
            suggestions = "Thank you for sharing your thoughts. Consider discussing these feelings with a trusted friend or mental health professional."

        return suggestions

    except Exception as e:
        logger.warning(f"AI suggestion generation failed: {e}")
        return "Thank you for sharing your thoughts. Consider discussing these feelings with a trusted friend or mental health professional."

def _day_streak(timestamps):
    """Consecutive UTC days ending today (or yesterday), counting each day once."""
    days = {t.date() for t in timestamps}
    day = datetime.now(timezone.utc).date()
    if day not in days:
        day -= timedelta(days=1)
    streak = 0
    while day in days:
        streak += 1
        day -= timedelta(days=1)
    return streak

# Create the patient blueprint with the name 'patient' and URL prefix
patient_bp = Blueprint('patient', __name__, url_prefix='/patient')

@patient_bp.route('/dashboard')
@login_required
@patient_required
def patient_dashboard():
    user_id = session['user_id']
    
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
        'rpm_data': {  # None = no reading yet; the template shows "No data yet"
            'heart_rate': rpm_data.heart_rate if rpm_data else None,
            'sleep_duration': rpm_data.sleep_duration if rpm_data else None,
            'steps': rpm_data.steps if rpm_data else None,
            'mood_score': latest_mood.mood_score if latest_mood else None
        }
    }

    alerts = []
    if rpm_data:
        if rpm_data.heart_rate and rpm_data.heart_rate > 100:
            alerts.append('High heart rate detected')
        if rpm_data.sleep_duration and rpm_data.sleep_duration < 6:
            alerts.append('Insufficient sleep detected')

    return render_template('patient_dashboard.html',
                         user_name=session['user_name'],
                         user=db.session.get(User, user_id),
                         data=data,
                         alerts=alerts,
                         upcoming_appointments=upcoming_appointments,
                         past_appointments=past_appointments,
                         latest_mood=latest_mood)

@patient_bp.route('/schedule', methods=['GET', 'POST'], endpoint='schedule_appointment')
@login_required
@patient_required
def schedule_appointment():
    if request.method == 'POST':
        date_str = request.form.get('date', '').strip()
        time_str = request.form.get('time', '').strip()
        appointment_type = request.form.get('appointment_type', '').strip()
        notes = request.form.get('notes', '')
        provider_id = request.form.get('provider_id')  # Optional provider selection
        user_id = session['user_id']

        def bad(msg):
            flash(msg, 'error')
            providers = User.query.filter_by(role='provider', institution=session.get('user_institution')).all()
            return render_template('schedule.html', user_name=session['user_name'], providers=providers), 400

        if not (date_str and time_str and appointment_type):
            return bad('Please choose a date, a time and an appointment type.')
        try:
            appointment_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            time_str = datetime.strptime(time_str, '%H:%M').strftime('%H:%M')
        except ValueError:
            return bad('Please enter a valid date (YYYY-MM-DD) and time (HH:MM).')
        if appointment_date < datetime.now(timezone.utc).date():
            return bad('That date is in the past. Please pick a future date.')
        provider = None
        if provider_id:
            provider = db.session.get(User, int(provider_id)) if provider_id.isdigit() else None
            if not provider or provider.role != 'provider':
                return bad('Please choose a valid provider.')
            taken = Appointment.query.filter(Appointment.provider_id == provider.id, Appointment.date == appointment_date,
                                             Appointment.time == time_str, Appointment.status.in_(['pending', 'accepted'])).first()
            if taken:
                return bad('That time slot is already booked. Please pick another.')

        try:
            new_appointment = Appointment(
                user_id=user_id,
                provider_id=provider.id if provider else None,
                date=appointment_date,
                time=time_str,
                appointment_type=appointment_type,
                notes=notes,
                status='pending'  # Changed to pending for provider approval
            )
            db.session.add(new_appointment)
            db.session.commit()
            
            flash(f'Appointment successfully booked for {date_str} at {time_str}!', 'success')
            return redirect(url_for('patient.patient_dashboard'))
        except Exception as e:
            db.session.rollback()
            logger.exception('appointment booking failed')
            flash('Could not book the appointment. Please try again.', 'error')
            return redirect(url_for('patient.schedule_appointment'))
    
    user_institution = session.get('user_institution', 'Sample University')
    providers = User.query.filter_by(role='provider', institution=user_institution).all()
    
    return render_template('schedule.html', user_name=session['user_name'], providers=providers)

@patient_bp.route('/medication', methods=['GET', 'POST'])
@login_required
@patient_required
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
        return redirect(url_for('patient.medication'))

    medications = Medication.query.filter_by(user_id=user_id, is_active=True).all()
    
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
    todays_logs = MedicationLog.query.filter(
        MedicationLog.user_id == user_id,
        MedicationLog.taken_at >= today_start
    ).all()
    
    logged_med_ids = {log.medication_id for log in todays_logs}
    
    today = date.today()
    return render_template('medication.html', 
                         user_name=session['user_name'], 
                         medications=medications,
                         logged_med_ids=logged_med_ids,
                         moment=datetime,
                         today=today)

@patient_bp.route('/log-medication', methods=['POST'])
@login_required
@patient_required
def log_medication():
    user_id = session['user_id']
    medication_id = request.form.get('medication_id', '')
    medication = Medication.query.filter_by(id=int(medication_id), user_id=user_id).first() if medication_id.isdigit() else None
    if not medication:
        return jsonify({'success': False, 'message': 'Medication not found.'}), 404

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)  # taken_at is naive UTC
    if MedicationLog.query.filter(MedicationLog.medication_id == medication.id, MedicationLog.user_id == user_id,
                                  MedicationLog.taken_at >= today_start).first():
        return jsonify({'success': False, 'message': 'You already logged this medication today.'})

    db.session.add(MedicationLog(user_id=user_id, medication_id=medication.id, taken_at=datetime.utcnow()))
    db.session.commit()
    award_points(user_id, 10, 'log_medication')
    return jsonify({'success': True, 'message': 'Medication logged. Nice work looking after yourself.'})

@patient_bp.route('/breathing', methods=['GET', 'POST'])
@login_required
@patient_required
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
        return redirect(url_for('patient.breathing'))

    recent_logs = BreathingExerciseLog.query.filter_by(user_id=user_id).order_by(BreathingExerciseLog.created_at.desc()).limit(10).all()
    
    all_logs = BreathingExerciseLog.query.filter_by(user_id=user_id).all()
    total_sessions = len(all_logs)
    total_minutes = sum(log.duration_minutes for log in all_logs)
    
    streak = _day_streak(log.created_at for log in all_logs if log.created_at)
    
    stats = {
        'total_sessions': total_sessions,
        'total_minutes': total_minutes,
        'streak': streak
    }
    
    return render_template('breathing.html', 
                         user_name=session['user_name'],
                         recent_logs=recent_logs,
                         stats=stats)

# Every id below was checked against YouTube oEmbed (Nov 2026); re-verify before adding more.
YOGA_VIDEOS = [
    {"id": "v7AYKMP6rOE", "title": "Yoga For Complete Beginners (20 min)", "channel": "Yoga With Adriene", "focus": "Beginner"},
    {"id": "4pKly2JojMw", "title": "10 Min Morning Yoga Full Body Stretch", "channel": "Yoga with Kassandra", "focus": "Morning"},
    {"id": "8TuRYV71Rgo", "title": "10 Minute Yoga for Stress and Anxiety", "channel": "Yoga With Bird", "focus": "Stress relief"},
    {"id": "sTANio_2E0Q", "title": "20 Min Full Body Stretch/Yoga for Stress & Anxiety Relief", "channel": "MadFit", "focus": "Stress relief"},
    {"id": "--jhKVdZOJM", "title": "Home - Day 1 | 30 Days of Yoga", "channel": "Yoga With Adriene", "focus": "Routine"},
    {"id": "GLy2rYHwUqY", "title": "Total Body Yoga | Deep Stretch (45 min)", "channel": "Yoga With Adriene", "focus": "Flexibility"},
]


@patient_bp.route('/yoga/videos')
@login_required
@patient_required
def yoga_videos():
    return render_template('yoga_videos.html', videos=YOGA_VIDEOS)


@patient_bp.route('/yoga', methods=['GET', 'POST'])
@login_required
@patient_required
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
        return redirect(url_for('patient.yoga'))

    recent_logs = YogaLog.query.filter_by(user_id=user_id).order_by(YogaLog.created_at.desc()).limit(10).all()
    
    all_logs = YogaLog.query.filter_by(user_id=user_id).all()
    total_sessions = len(all_logs)
    total_minutes = sum(log.duration_minutes for log in all_logs)
    avg_duration = round(total_minutes / total_sessions, 1) if total_sessions > 0 else 0
    
    streak = _day_streak(log.created_at for log in all_logs if log.created_at)
    
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

@patient_bp.route('/digital-detox')
@login_required
@patient_required
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

@patient_bp.route('/progress')
@login_required
@patient_required
def progress():
    try:
        logger.info("Entering progress route")
        user_id = session['user_id']
        logger.info(f"User ID: {user_id}")
        
        # Get user's goals and assessments with error handling
        try:
            goals = Goal.query.filter_by(user_id=user_id).all()
            logger.info(f"Found {len(goals)} goals")
            
            assessments = Assessment.query.filter_by(user_id=user_id).order_by(Assessment.created_at.desc()).all()
            logger.info(f"Found {len(assessments)} assessments")
            
            achievements = [goal.title for goal in goals if goal.status == 'completed']
            logger.info(f"Found {len(achievements)} completed goals")
            
        except Exception as e:
            logger.error(f"Error fetching goals or assessments: {str(e)}", exc_info=True)
            return "An error occurred while fetching your data. Please try again later.", 500
        
        latest_gad7 = next((a for a in assessments if canonical_type(a.assessment_type) == 'GAD-7'), None)
        latest_phq9 = next((a for a in assessments if canonical_type(a.assessment_type) == 'PHQ-9'), None)
        latest_mood = next((a for a in assessments if a.assessment_type == 'Daily Mood'), None)

        mood_assessments = sorted([a for a in assessments if a.assessment_type == 'Daily Mood'], key=lambda x: x.created_at)[-30:]
        mood_data = [{'date': m.created_at.strftime('%Y-%m-%d'), 'score': m.score} for m in mood_assessments]
        
        gad7_assessments = sorted([a for a in assessments if canonical_type(a.assessment_type) == 'GAD-7'], key=lambda x: x.created_at)
        phq9_assessments = sorted([a for a in assessments if canonical_type(a.assessment_type) == 'PHQ-9'], key=lambda x: x.created_at)

        assessment_chart_labels = sorted(list(set([a.created_at.strftime('%Y-%m-%d') for a in gad7_assessments + phq9_assessments])))
        assessment_chart_gad7_data = [next((a.score for a in gad7_assessments if a.created_at.strftime('%Y-%m-%d') == date), None) for date in assessment_chart_labels]
        assessment_chart_phq9_data = [next((a.score for a in phq9_assessments if a.created_at.strftime('%Y-%m-%d') == date), None) for date in assessment_chart_labels]

        days_since_assessment = (datetime.now(assessments[0].created_at.tzinfo) - assessments[0].created_at).days if assessments and assessments[0].created_at else 'N/A'
        
        user_data_for_ai = {
            'gad7_score': latest_gad7.score if latest_gad7 else 0,  # Default to 0 instead of 'N/A' for calculations
            'phq9_score': latest_phq9.score if latest_phq9 else 0,  # Default to 0 instead of 'N/A' for calculations
            'wellness_score': 'calculating...',
            'completed_goals': len(achievements),
            'total_goals': len(goals),
            'days_since_assessment': days_since_assessment if days_since_assessment != 'N/A' else 0  # Default to 0 for calculations
        }
        
        user = db.session.get(User, user_id)
        if not user:
            flash('User not found. Please log in again.', 'error')
            return redirect(url_for('auth.login'))

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
        logger.error(f"Error in progress route: {str(e)}", exc_info=True)
        return "An internal error occurred. Please try again later.", 500

@patient_bp.route('/goals', methods=['GET', 'POST'])
@login_required
@patient_required
def goals():
    # ... (rest of the code remains the same)
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
            except ValueError:
                db.session.rollback()
                flash('Target value must be a number and the date must be valid.', 'error')
            except Exception as e:
                db.session.rollback()
                flash('Failed to create goal.', 'error')
        return redirect(url_for('patient.goals'))

    goals = Goal.query.filter_by(user_id=user_id).all()
    return render_template('goals.html', user_name=session['user_name'], goals=goals)

@patient_bp.route('/api/assessment/questions/<assessment_type>')
@login_required
@patient_required
def get_assessment_questions(assessment_type):
    try:
        questions_file_path = os.path.join(os.getcwd(), 'static', 'questions.json')
        
        if not os.path.exists(questions_file_path):
            return jsonify({'success': False, 'message': 'Assessment questions file not found.'}), 500

        with open(questions_file_path, 'r') as f:
            all_questions = json.load(f)
        
        questions = all_questions.get(assessment_type)
        
        if questions:
            return jsonify({'success': True, 'questions': questions})
        else:
            return jsonify({'success': False, 'message': 'Invalid assessment type.'}), 404
            
    except Exception as e:
        return jsonify({'success': False, 'message': 'An internal error occurred.'}), 500

@patient_bp.route('/assessment')
@login_required
@patient_required
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
        flash('Error loading assessments. Please try again.', 'error')
        return render_template('assessment.html', 
                               user_name=session['user_name'], 
                               assessments=[],
                               latest_insights=None)

@patient_bp.route('/api/save-assessment', methods=['POST'])
@login_required
@patient_required
def api_save_assessment():
    from ai.scoring import ScoreError, canonical_type, score_assessment
    from utils.crisis import record_crisis
    from utils.helplines import get_helplines, helplines_lines
    if not request.is_json:
        return jsonify({'success': False, 'message': 'Request must be JSON'}), 400

    user_id = session['user_id']
    data = request.get_json(silent=True) or {}
    assessment_type = canonical_type(data.get('assessment_type'))
    responses = data.get('responses')
    try:  # the score is always recomputed here; any client-sent score is ignored
        result = score_assessment(assessment_type, responses)
    except ScoreError:
        return jsonify({'success': False, 'message': 'Invalid assessment type or responses.'}), 400
    score = result['total']
    contextual = data.get('contextual_responses')
    contextual = contextual if isinstance(contextual, dict) else {}

    crisis_reason = ('phq9_item9_positive' if result.get('item9_positive')
                     else f"{assessment_type.lower().replace('-', '')}_severe" if result['severe'] else None)
    if crisis_reason:  # no model-written advice for a possible crisis: fixed supportive text and helplines
        ai_insights = {
            'summary': f"Your {assessment_type} score is {score} ({result['band']}). This is a screening result, "
                       "not a diagnosis. Please talk to someone you trust and consider contacting a helpline or a clinician soon.",
            'recommendations': ['Reach out to a counselor or doctor in the next few days',
                                'Tell a trusted friend or family member how you are feeling'],
            'resources': helplines_lines(),
        }
        ai_ok = False
    else:
        try:
            ai_insights = ai_service.generate_assessment_insights(assessment_type=assessment_type, score=score,
                                                                  responses=responses)
            ai_ok = True
        except Exception:
            ai_ok = False
            ai_insights = {'summary': 'AI insights are currently unavailable. Please try again later.',
                           'recommendations': [], 'resources': helplines_lines()}

    try:
        user = db.session.get(User, user_id)
        if not user:
            return jsonify({'success': False, 'message': 'User not found. Please log in again.'}), 400
        assessment = Assessment(user_id=user_id, assessment_type=assessment_type, score=score,
                                responses=responses, contextual_responses=contextual,
                                ai_insights=json.dumps(ai_insights))
        db.session.add(assessment)
        user.last_assessment_at = datetime.now(timezone.utc)
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("Failed to save assessment")
        return jsonify({'success': False, 'message': 'Failed to save assessment.'}), 500

    if crisis_reason:
        record_crisis(user_id, 'phq9', 9 if result.get('item9_positive') else 7, crisis_reason)
    # no points or streaks for assessments (policy: never reward scores)
    return jsonify({
        'success': True,
        'message': 'Assessment saved successfully',
        'assessment_id': assessment.id,
        'score': score,
        'band': result['band'],
        'ai_insights': ai_insights,
        'ai_insights_generated': ai_ok,
        'crisis': bool(crisis_reason),
        'helplines': get_helplines() if crisis_reason else [],
    })

@patient_bp.route('/my-prescriptions')
@login_required
@patient_required
def my_prescriptions():
    user_id = session['user_id']
    prescriptions = Prescription.query.options(joinedload(Prescription.provider)).filter_by(patient_id=user_id).order_by(Prescription.issue_date.desc()).all()
    return render_template('my_prescriptions.html', 
                           user_name=session['user_name'],
                           prescriptions=prescriptions)

@patient_bp.route('/api/progress', methods=['GET'])
@login_required
@patient_required
def get_progress():
    try:
        # Import models at function-time to avoid circular imports in some setups
        user_id = session['user_id']
        assessments = Assessment.query.filter_by(user_id=user_id).order_by(Assessment.created_at.asc()).limit(500).all()
        moods = MoodLog.query.filter_by(user_id=user_id).order_by(MoodLog.created_at.asc()).limit(500).all()

        a_out = []
        for a in assessments:
            a_out.append({
                "id": a.id,
                "assessment_type": getattr(a, 'assessment_type', None),
                "score": getattr(a, 'score', None),
                "created_at": a.created_at.isoformat() if hasattr(a, 'created_at') else None
            })

        m_out = []
        for m in moods:
            m_out.append({
                "id": m.id,
                "mood": getattr(m, 'mood_score', None),
                "created_at": m.created_at.isoformat() if hasattr(m, 'created_at') else None
            })

        return jsonify({"ok": True, "assessments": a_out, "moods": m_out}), 200
    except Exception as e:
        current_app.logger.exception("progress fetch failed")
        return jsonify({"ok": False, "error": "Could not load progress."}), 500

@patient_bp.route('/api/digital-detox-data')
@login_required
@patient_required
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

@patient_bp.route('/api/log-digital-detox', methods=['POST'])
@login_required
@patient_required
def log_digital_detox():
    user_id = session['user_id']
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'success': False, 'message': 'Request must be JSON.'}), 400

    try:
        screen_time = float(data.get('screen_time'))
        academic_score = int(float(data.get('academic_score')))
        social_interactions = str(data.get('social_interactions') or '').lower()
        if not (0 <= screen_time <= 24) or screen_time != screen_time:
            return jsonify({'success': False, 'message': 'Screen time must be between 0 and 24 hours.'}), 400
        if not 0 <= academic_score <= 100:
            return jsonify({'success': False, 'message': 'Academic score must be between 0 and 100.'}), 400
        if social_interactions not in ('low', 'medium', 'high'):
            return jsonify({'success': False, 'message': 'Social interactions must be low, medium or high.'}), 400

        # Call AI service for digital detox insights
        detox_data = {
            'screen_time': screen_time,
            'academic_score': academic_score,
            'social_interactions': social_interactions
        }
        ai_analysis = ai_service.generate_digital_detox_insights(detox_data)

        # One log per day: a second submission today updates it (and earns no extra points).
        new_log = DigitalDetoxLog.query.filter_by(user_id=user_id, date=datetime.now(timezone.utc).date()).first()
        is_new = new_log is None
        if is_new:
            new_log = DigitalDetoxLog(user_id=user_id, date=datetime.now(timezone.utc).date())
            db.session.add(new_log)
        new_log.screen_time_hours = screen_time
        new_log.academic_score = academic_score
        new_log.social_interactions = social_interactions
        new_log.ai_score = ai_analysis.get('ai_score', 'N/A')
        new_log.ai_suggestion = ai_analysis.get('ai_suggestion', 'No suggestion available')
        db.session.commit()

        if is_new:
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
        return jsonify({'success': False, 'message': 'Invalid data format.'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'An internal error occurred.'}), 500

# Add missing routes from app.py

@patient_bp.route('/journal', methods=['GET', 'POST'])
@patient_required
def patient_journal():
    """Journal entries page for patients."""
    # Ensure user is logged in and has valid session
    if 'user_id' not in session:
        flash('Please log in to access your journal.', 'error')
        return redirect(url_for('auth.login'))

    user_id = session['user_id']

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()

        if not title or not content:
            flash('Both title and content are required.', 'error')
            return redirect(url_for('patient.patient_journal'))

        if len(title) > 100:
            flash('Title must be less than 100 characters.', 'error')
            return redirect(url_for('patient.patient_journal'))

        if len(content) > 5000:
            flash('Content must be less than 5000 characters.', 'error')
            return redirect(url_for('patient.patient_journal'))

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

        db.session.add(JournalEntry(user_id=user_id, title=title, content=content,
                                    sentiment=sentiment_result, ai_suggestions=ai_suggestions))
        db.session.commit()

        # Award points for journaling
        award_points(user_id, 15, 'journal_entry')

        flash('Journal entry saved successfully!', 'success')
        return redirect(url_for('patient.patient_journal'))

    # GET request - display journal entries
    user_entries = JournalEntry.query.filter_by(user_id=user_id).order_by(JournalEntry.created_at.asc(), JournalEntry.id.asc()).all()  # template reverses

    return render_template('patient_journal.html',
                         user_name=session['user_name'],
                         journal_entries=user_entries)

@patient_bp.route('/api/save-mood', methods=['POST'])
@patient_required
def save_mood():
    """Daily mood check-in for the session user. No points or streak: mood scores are never gamified."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'success': False, 'message': 'Request must be JSON'}), 400

    mood = data.get('mood')
    if isinstance(mood, str) and mood.strip().isdigit():
        mood = int(mood)
    if isinstance(mood, bool) or not isinstance(mood, int) or not 1 <= mood <= 10:
        return jsonify({'success': False, 'message': 'Mood must be a whole number from 1 to 10'}), 400
    notes = str(data.get('notes') or '').strip()[:500] or None

    user_id = session['user_id']
    try:
        db.session.add(MoodLog(user_id=user_id, mood_score=mood, notes=notes))
        # Same entry as a 'Daily Mood' assessment: the trend/progress code reads that type.
        db.session.add(Assessment(user_id=user_id, assessment_type='Daily Mood', score=mood,
                                  responses={'mood': mood, 'notes': notes or ''}))
        user = db.session.get(User, user_id)
        if user:
            user.last_assessment_at = datetime.utcnow()
        db.session.commit()
        return jsonify({'success': True, 'message': 'Mood saved. Thanks for checking in.'})
    except Exception:
        db.session.rollback()
        logger.exception('Error saving mood')
        return jsonify({'success': False, 'message': 'Could not save your mood. Please try again.'}), 500

@patient_bp.route('/voice-logs', methods=['GET'])
@login_required
@patient_required
def patient_voice_logs():
    """Voice logs page for patients."""
    try:
        user_id = session['user_id']
        user_logs = VoiceLog.query.filter_by(user_id=user_id).order_by(VoiceLog.created_at.desc()).all()
        
        return render_template('patient_voice_logs.html',
                             user_name=session.get('user_name', 'User'),
                             voice_logs=user_logs)
    except Exception as e:
        logger.error(f"Error in patient_voice_logs: {str(e)}")
        flash('An error occurred while loading the voice logs.', 'error')
        return redirect(url_for('patient.patient_dashboard'))


@patient_bp.route('/api/goals', methods=['GET', 'POST'])
@patient_required
def handle_goals():
    """Handle goal creation and updates."""
    user_id = session['user_id']

    if request.method == 'POST':
        try:
            data = request.get_json(silent=True) or {}
            title = data.get('title')
            description = data.get('description')
            category = data.get('category') or 'mental_health'
            target_value = data.get('target_value')
            unit = data.get('unit')
            priority = data.get('priority') or 'medium'
            target_date = data.get('target_date')

            if not title:
                return jsonify({'success': False, 'message': 'Title is required.'}), 400

            try:
                target_value = float(target_value) if target_value not in (None, '') else None
                parsed_target_date = datetime.strptime(target_date, '%Y-%m-%d').date() if target_date else None
            except (TypeError, ValueError):
                return jsonify({'success': False, 'message': 'Target value must be a number and the date YYYY-MM-DD.'}), 400

            new_goal = Goal(
                user_id=user_id,
                title=title,
                description=description,
                category=category,
                priority=priority,
                target_value=target_value,
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

@patient_bp.route('/api/goals/<int:goal_id>', methods=['PUT', 'DELETE'])
@patient_required
def handle_goal(goal_id):
    user_id = session['user_id']
    goal = Goal.query.filter_by(id=goal_id, user_id=user_id).first()

    if not goal:
        return jsonify({'success': False, 'message': 'Goal not found.'}), 404

    if request.method == 'DELETE':
        try:
            db.session.delete(goal)
            db.session.commit()
            return jsonify({'success': True, 'message': 'Goal deleted successfully!'})
        except Exception as e:
            db.session.rollback()
            logger.exception('goal delete failed')
            return jsonify({'success': False, 'message': 'Could not delete the goal.'}), 500
    
    elif request.method == 'PUT':
        data = request.get_json(silent=True) or {}

        try:
            for field in ('target_value', 'current_value'):
                if field in data:
                    setattr(goal, field, float(data[field]) if data[field] not in (None, '') else None)
        except (TypeError, ValueError):
            db.session.rollback()
            return jsonify({'success': False, 'message': 'Values must be numbers.'}), 400
        for field in ('title', 'description', 'category', 'priority', 'unit'):
            if field in data:
                setattr(goal, field, data[field])

        # 'completed' (bool) or 'status' change the status; if neither is sent it stays as it is.
        new_status = None
        if 'completed' in data:
            new_status = 'completed' if data['completed'] is True else 'active'
        elif 'status' in data:
            new_status = data['status']
        if new_status is not None and new_status not in ('active', 'completed', 'paused'):
            db.session.rollback()
            return jsonify({'success': False, 'message': 'Invalid status.'}), 400

        try:
            if new_status is not None and new_status != goal.status:
                goal.status = new_status
                goal.completed_date = datetime.utcnow().date() if new_status == 'completed' else None

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
            logger.exception('goal update failed')
            return jsonify({'success': False, 'message': 'Could not update the goal.'}), 500
