from flask import Blueprint, render_template, session, redirect, url_for, flash, request, jsonify
from models import (User, Gamification, DigitalDetoxLog, Assessment, Goal, Medication, 
                MedicationLog, BreathingExerciseLog, YogaLog, ProgressRecommendation, 
                Prescription, MoodLog, RPMData, Appointment, db)
from decorators import patient_required, login_required
from sqlalchemy.orm import joinedload
from datetime import datetime, date, timedelta, timezone
import json
from ai.service import ask as ai_service
from gamification_engine import award_points
import logging
import uuid

# Import shared data storage instead of importing from app to avoid circular imports
from shared_data import patient_journal_entries, patient_voice_logs_data

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

@patient_bp.route('/schedule', methods=['GET', 'POST'], endpoint='schedule_appointment')
@login_required
@patient_required
def schedule_appointment():
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
            
            flash(f'Appointment successfully booked for {date_str} at {time_str}!', 'success')
            return redirect(url_for('patient.patient_dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error booking appointment: {e}', 'error')
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

@patient_bp.route('/log-medication', methods=['POST'])
@login_required
@patient_required
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
        return redirect(url_for('patient.patient_journal'))

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
        return f"An internal error occurred: {str(e)}. Please try again later.", 500

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
    if not request.is_json:
        return jsonify({'success': False, 'message': 'Request must be JSON'}), 400
        
    user_id = session['user_id']
    data = request.get_json()
    
    assessment_type = data.get('assessment_type')
    score = data.get('score')
    responses = data.get('responses', [])
    contextual_responses = data.get('contextual_responses', {})
    
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
        ai_insights_generated_successfully = False
        ai_insights = {
            'summary': 'AI insights are currently unavailable. Please try again later.',
            'recommendations': [],
            'resources': []
        }

    try:
        assessment = Assessment(
            user_id=user_id,
            assessment_type=assessment_type.upper(),
            score=score,
            responses=responses,
            contextual_responses=contextual_responses,
            ai_insights=json.dumps(ai_insights) if ai_insights else None
        )
        
        db.session.add(assessment)

        gamification = award_points(user_id, 20, 'assessment')

        user = db.session.get(User, user_id)
        if not user:
            return jsonify({
                'success': False,
                'message': 'User not found. Please log in again.'
            }), 400

        user.last_assessment_at = datetime.now(timezone.utc)
        
        db.session.commit()
        
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
        return jsonify({
            'success': False,
            'message': f'Failed to save assessment: {str(e)}',
            'insights': ai_insights if 'ai_insights' in locals() else None
        }), 500

@patient_bp.route('/my-prescriptions')
@login_required
@patient_required
def my_prescriptions():
    user_id = session['user_id']
    prescriptions = Prescription.query.options(joinedload(Prescription.provider)).filter_by(patient_id=user_id).order_by(Prescription.issue_date.desc()).all()
    return render_template('my_prescriptions.html', 
                           user_name=session['user_name'],
                           prescriptions=prescriptions)

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
        return redirect(url_for('patient.patient_journal'))

    # GET request - display journal entries
    user_entries = patient_journal_entries.get(user_id, [])

    return render_template('patient_journal.html',
                         user_name=session['user_name'],
                         journal_entries=user_entries)

@patient_bp.route('/api/save-mood', methods=['POST'])
@patient_required
def save_mood():
    if not request.is_json:
        return jsonify({'success': False, 'message': 'Request must be JSON'}), 400
        
    user_id = session['user_id']
    data = request.get_json()
    
    if not data or 'mood' not in data:
        return jsonify({'success': False, 'message': 'Missing mood data'}), 400
    
    try:
        mood = int(data.get('mood'))
        if not (1 <= mood <= 5):
            return jsonify({'success': False, 'message': 'Mood must be between 1 and 5'}), 400
            
        # Create new assessment for the mood
        mood_assessment = Assessment(
            user_id=user_id,
            assessment_type='Daily Mood',
            score=mood,
            responses={'mood': mood, 'notes': data.get('notes', '')}
        )
        db.session.add(mood_assessment)
        
        # Also update RPM data for dashboard
        today = datetime.utcnow().date()
        rpm_data = RPMData.query.filter_by(user_id=user_id, date=today).first()
        if not rpm_data:
            rpm_data = RPMData(user_id=user_id, date=today, mood_score=mood)
            db.session.add(rpm_data)
        else:
            rpm_data.mood_score = mood
        
        # Update gamification points
        gamification = Gamification.query.filter_by(user_id=user_id).first()
        if not gamification:
            gamification = Gamification(user_id=user_id, points=0, streak=0)
            db.session.add(gamification)
            
        # Add points for mood check-in
        gamification.points += 10
        
        # Check for streak
        if gamification.last_activity:
            last_activity = gamification.last_activity.date() if hasattr(gamification.last_activity, 'date') else gamification.last_activity
            if last_activity == today - timedelta(days=1):
                gamification.streak += 1
            elif last_activity < today - timedelta(days=1):
                gamification.streak = 1
        else:
            gamification.streak = 1
        
        gamification.last_activity = today

        # Update user's last assessment time
        user = db.session.get(User, user_id)
        if not user:
            return jsonify({
                'success': False,
                'message': 'User not found. Please log in again.'
            }), 400

        user.last_assessment_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Mood saved successfully',
            'points': gamification.points,
            'streak': gamification.streak
        })
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Error saving mood: {str(e)}')
        return jsonify({
            'success': False,
            'message': f'Failed to save mood: {str(e)}'
        }), 500

@patient_bp.route('/voice-logs', methods=['GET'])
@login_required
@patient_required
def patient_voice_logs():
    """Voice logs page for patients."""
    try:
        user_id = session['user_id']
        user_logs = patient_voice_logs_data.get(user_id, [])
        
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
            return jsonify({'success': False, 'message': f'Error deleting goal: {str(e)}'})
    
    elif request.method == 'PUT':
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
