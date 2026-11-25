from flask import Blueprint, render_template, session, redirect, url_for, flash, request, jsonify, current_app
from models import (User, Gamification, DigitalDetoxLog, Assessment, Goal, Medication,
                MedicationLog, BreathingExerciseLog, YogaLog, ProgressRecommendation,
                Prescription, MoodLog, RPMData, Appointment, JournalEntry, VoiceLog, db)
import os
from decorators import patient_required, login_required, prescriptions_required
from utils.assignments import link_provider_patient
from routes.rx_patient import dashboard_context, list_page
from utils.booking import staff_options, booking_extras, record_erx_consent, schedule_context
from sqlalchemy.orm import joinedload, load_only
from utils.pagination import paginate, set_page_headers
from datetime import datetime, date, timedelta, timezone
import json
import ai.service as ai_service
from ai.scoring import canonical_type, band_for
from utils.gamification import award_points
from utils.ai_cap import run_capped
from utils import ai_caveats, idempotency as idem
from utils.state import TransitionError, transition, CONFLICT_MESSAGE
from utils.timeutil import ist_now, ist_today, ist_day_bounds, to_ist_date, utcnow
from utils.validation import parse_duration, MIN_DURATION_MINUTES, MAX_DURATION_MINUTES
from sqlalchemy.exc import IntegrityError
import logging


# TextBlob for sentiment analysis (imported lazily, see utils/sentiment.py)
from utils.sentiment import TextBlob, TEXTBLOB_AVAILABLE

logger = logging.getLogger(__name__)
AI_REQUEST_CAP = 8.0  # seconds a save request may wait for the model, then it uses the plain fallback

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
        ok, suggestions = run_capped(ai_service.generate_journal_insights, title, content, sentiment, seconds=AI_REQUEST_CAP)
        if not ok or not isinstance(suggestions, str):
            raise RuntimeError('ai unavailable')

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
    """Consecutive IST days ending today (or yesterday), counting each day once. Timestamps are naive UTC."""
    days = {to_ist_date(t) for t in timestamps}
    day = ist_today()
    if day not in days:
        day -= timedelta(days=1)
    streak = 0
    while day in days:
        streak += 1
        day -= timedelta(days=1)
    return streak

# Create the patient blueprint with the name 'patient' and URL prefix
patient_bp = Blueprint('patient', __name__, url_prefix='/patient')
patient_bp.register_error_handler(idem.InvalidKey, idem.handle_invalid_key)

@patient_bp.route('/dashboard')
@login_required
@patient_required
def patient_dashboard():
    user_id = session['user_id']
    
    gamification = Gamification.query.filter_by(user_id=user_id).first()
    rpm_data = RPMData.query.filter_by(user_id=user_id).order_by(RPMData.date.desc()).first()
    all_appointments = Appointment.query.filter_by(user_id=user_id).order_by(Appointment.date.asc(), Appointment.time.asc()).limit(500).all()
    latest_mood = MoodLog.query.filter_by(user_id=user_id).order_by(MoodLog.created_at.desc()).first()
    latest_screening = None  # newest PHQ-9 / GAD-7 for the dashboard card (band from ai.scoring)
    for a in Assessment.query.filter_by(user_id=user_id).order_by(Assessment.created_at.desc()).limit(20):
        kind = canonical_type(a.assessment_type)
        if kind:
            latest_screening = {'type': kind, 'score': a.score, 'band': band_for(kind, a.score), 'date': a.created_at}
            break

    upcoming_appointments = []
    past_appointments = []

    for appt in all_appointments:
        try:
            appt_datetime_str = f"{appt.date} {appt.time}"
            appt_datetime = datetime.strptime(appt_datetime_str, '%Y-%m-%d %H:%M')
            if appt_datetime >= ist_now():  # appointment date/time are IST wall-clock
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
                         latest_mood=latest_mood,
                         latest_screening=latest_screening,
                         **dashboard_context(user_id))

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

        key = idem.get_key()
        if idem.existing(Appointment, user_id, key):  # replay of a request that already succeeded
            return redirect(url_for('patient.patient_dashboard'))

        def bad(msg, status=400):
            flash(msg, 'error')
            return render_template('schedule.html', user_name=session['user_name'], appointments=_my_appointments(user_id),
                                   error=msg, form=request.form, **schedule_context(user_id, session.get('user_institution'))), status

        if not (date_str and time_str and appointment_type):
            return bad('Please choose a date, a time and an appointment type.')
        try:
            appointment_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            time_str = datetime.strptime(time_str, '%H:%M').strftime('%H:%M')
        except ValueError:
            return bad('Please enter a valid date (YYYY-MM-DD) and time (HH:MM).')
        if appointment_date < ist_today():
            return bad('That date is in the past. Please pick a future date.')
        provider, modality = None, None
        if provider_id:
            provider = db.session.get(User, int(provider_id)) if provider_id.isdigit() else None
            if not provider or provider.id not in {u.id for u in staff_options(session.get('user_institution'))}:
                return bad('Please choose a valid provider.')
            modality, extras_error = booking_extras(provider, request.form, user_id)
            if extras_error:
                return bad(extras_error)
            taken = Appointment.query.filter(Appointment.provider_id == provider.id, Appointment.date == appointment_date,
                                             Appointment.time == time_str, Appointment.status.in_(['pending', 'accepted', 'booked'])).first()
            if taken:
                return bad('That time slot is already booked. Please pick another.', 409)

        try:
            new_appointment = Appointment(
                user_id=user_id,
                provider_id=provider.id if provider else None,
                date=appointment_date,
                time=time_str,
                appointment_type=appointment_type,
                notes=notes,
                status='pending',  # Changed to pending for provider approval
                client_request_id=key,
                **({'modality': modality} if modality else {})
            )
            db.session.add(new_appointment)
            if provider:
                link_provider_patient(provider.id, user_id)  # P-02: booking is what lets this provider see the patient
            db.session.commit()
            record_erx_consent(provider, request.form, user_id)

            flash(f'Appointment successfully booked for {date_str} at {time_str}!', 'success')
            return redirect(url_for('patient.patient_dashboard'))
        except IntegrityError:  # double submit (same key) or the slot was taken a moment ago
            db.session.rollback()
            if idem.existing(Appointment, user_id, key):
                return redirect(url_for('patient.patient_dashboard'))
            return bad('That time slot is already booked. Please pick another.', 409)
        except Exception as e:
            db.session.rollback()
            logger.exception('appointment booking failed')
            flash('Could not book the appointment. Please try again.', 'error')
            return redirect(url_for('patient.schedule_appointment'))
    
    return render_template('schedule.html', user_name=session['user_name'], appointments=_my_appointments(session['user_id']),
                           error=None, form={}, **schedule_context(session['user_id'], session.get('user_institution', 'Sample University')))


def _my_appointments(user_id):
    return (Appointment.query.options(joinedload(Appointment.provider)).filter_by(user_id=user_id)
            .order_by(Appointment.date.desc(), Appointment.time.desc()).limit(50).all())


@patient_bp.route('/appointments/<int:appointment_id>/cancel', methods=['POST'])
@login_required
@patient_required
def cancel_appointment(appointment_id):
    appt = Appointment.query.filter_by(id=appointment_id, user_id=session['user_id']).first()
    if not appt:
        flash('Appointment not found.', 'error')
    else:
        try:
            transition(appt, 'cancelled', 'patient')
            db.session.commit()
            flash('Appointment cancelled.', 'success')
        except TransitionError:
            db.session.rollback()
            flash('This appointment can no longer be cancelled.', 'error')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
                return jsonify(success=False, message=CONFLICT_MESSAGE), 409
    return redirect(url_for('patient.schedule_appointment'))

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
    
    today = ist_today()
    todays_logs = MedicationLog.query.filter(
        MedicationLog.user_id == user_id,
        MedicationLog.log_date == today
    ).all()

    logged_med_ids = {log.medication_id for log in todays_logs}

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

    # One log per medication per IST day (DB unique uq_medlog_med_day): a repeat or a race is "already logged", never a second row.
    today = ist_today()
    already = jsonify({'success': False, 'already_logged': True, 'message': 'You already logged this medication today.'})
    if MedicationLog.query.filter_by(medication_id=medication.id, log_date=today).first():
        return already
    log = MedicationLog(user_id=user_id, medication_id=medication.id, taken_at=utcnow(), log_date=today)
    db.session.add(log)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return already
    award_points(user_id, 10, 'log_medication', ref=f'medlog:{log.id}')
    return jsonify({'success': True, 'message': 'Medication logged. Nice work looking after yourself.'})

def _wants_json():
    return request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', '')


def _post_duration_log(model, name_field, name_label, award_type, noun, endpoint):
    """Create a breathing/yoga log. Duration must be a whole number of minutes in [MIN_DURATION_MINUTES, MAX_DURATION_MINUTES].

    JSON/XHR callers get JSON (400 with a message on bad input; 200 with the existing row on a replayed
    client_request_id); plain form posts get a flash and a redirect.
    """
    user_id = session['user_id']
    data = request.get_json(silent=True) if request.is_json else request.form
    data = data if hasattr(data, 'get') else {}
    key = idem.get_key()
    name = str(data.get(name_field) or '').strip()
    minutes = parse_duration(data.get('duration_minutes'))
    error = (f'{name_label} is required (100 characters at most).' if not name or len(name) > 100 else
             f'Duration must be a whole number of minutes from {MIN_DURATION_MINUTES} to {MAX_DURATION_MINUTES}.' if minutes is None else None)

    def done(row, created):
        msg = f'Your {name} session has been logged!' if created else 'This session was already logged.'
        if _wants_json():
            return jsonify(success=True, id=row.id, message=msg)
        flash(msg, 'success')
        return redirect(url_for(endpoint))

    row = idem.existing(model, user_id, key)
    if row:
        return done(row, False)
    if error:
        if _wants_json():
            return jsonify(success=False, message=error), 400
        flash(error, 'error')
        return redirect(url_for(endpoint))
    row, created = idem.add_once(model, model(user_id=user_id, duration_minutes=minutes, client_request_id=key,
                                              created_at=utcnow(), **{name_field: name}), key)
    if created:
        award_points(user_id, 20, award_type, ref=f'{noun}:{row.id}')
    return done(row, created)


@patient_bp.route('/breathing', methods=['GET', 'POST'])
@login_required
@patient_required
def breathing():
    user_id = session['user_id']

    if request.method == 'POST':
        return _post_duration_log(BreathingExerciseLog, 'exercise_name', 'Exercise name', 'breathing_exercise',
                                  'breathing', 'patient.breathing')

    recent_logs = BreathingExerciseLog.query.filter_by(user_id=user_id).order_by(BreathingExerciseLog.created_at.desc()).limit(10).all()
    
    all_logs = (BreathingExerciseLog.query.filter_by(user_id=user_id)
                .options(load_only(BreathingExerciseLog.created_at, BreathingExerciseLog.duration_minutes)).all())
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
        return _post_duration_log(YogaLog, 'session_name', 'Session name', 'yoga_session', 'yoga', 'patient.yoga')

    recent_logs = YogaLog.query.filter_by(user_id=user_id).order_by(YogaLog.created_at.desc()).limit(10).all()
    
    all_logs = (YogaLog.query.filter_by(user_id=user_id)
                .options(load_only(YogaLog.created_at, YogaLog.duration_minutes)).all())
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
                         suggestion=suggestion, logged_count=len(screen_time_log), detox_caveat=ai_caveats.DETOX_CAVEAT)

@patient_bp.route('/goals', methods=['GET', 'POST'])
@login_required
@patient_required
def goals():
    # ... (rest of the code remains the same)
    user_id = session['user_id']
    
    if request.method == 'POST':
        key = idem.get_key()
        title = request.form.get('title')
        description = request.form.get('description', '')
        category = request.form.get('category', 'mental_health')
        priority = request.form.get('priority', 'medium')
        priority = priority if priority in ('low', 'medium', 'high') else 'medium'
        target_value = request.form.get('target_value')
        unit = request.form.get('unit', '')
        target_date = request.form.get('target_date')

        if idem.existing(Goal, user_id, key):  # replay: already created
            flash('Goal created successfully!', 'success')
        elif not title:
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
                    start_date=ist_today(),
                    client_request_id=key
                )
                if new_goal.target_value is not None and not new_goal.target_value >= 0:
                    raise ValueError('negative target')
                db.session.add(new_goal)
                db.session.commit()
                flash('Goal created successfully!', 'success')
            except ValueError:
                db.session.rollback()
                flash('Target value must be a number and the date must be valid.', 'error')
            except Exception as e:
                db.session.rollback()
                if isinstance(e, IntegrityError) and idem.existing(Goal, user_id, key):  # concurrent double submit
                    flash('Goal created successfully!', 'success')
                else:
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
        assessment_objects = Assessment.query.filter_by(user_id=user_id).order_by(Assessment.created_at.desc()).limit(500).all()
        
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

def _assessment_replay(a):
    """The save-assessment response rebuilt from the stored row (score and band are deterministic)."""
    from ai.scoring import score_assessment
    from utils.helplines import get_helplines
    result = score_assessment(a.assessment_type, a.responses)
    insights = json.loads(a.ai_insights) if a.ai_insights else {}
    crisis = bool(result.get('item9_positive') or result['severe'])
    return jsonify({
        'success': True, 'message': 'Assessment saved successfully', 'assessment_id': a.id, 'score': a.score,
        'band': result['band'], 'ai_insights': insights,
        'ai_insights_generated': not crisis and not str(insights.get('summary', '')).startswith('AI insights are currently unavailable'),
        'crisis': crisis, 'helplines': get_helplines() if crisis else [],
    })


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
    key = idem.get_key()
    first = idem.existing(Assessment, user_id, key)
    if first:  # replay: same body as the first answer, no second row, no second AI call
        return _assessment_replay(first)
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
            ok, ai_insights = run_capped(ai_service.generate_assessment_insights, assessment_type=assessment_type,
                                         score=score, responses=responses, seconds=AI_REQUEST_CAP)
            if not ok or not isinstance(ai_insights, dict):
                raise RuntimeError('ai unavailable')
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
                                ai_insights=json.dumps(ai_insights), client_request_id=key)
        db.session.add(assessment)
        user.last_assessment_at = utcnow()
        if crisis_reason:  # O-01: the crisis event and its alert job commit WITH the assessment (all or nothing)
            record_crisis(user_id, 'phq9', 9 if result.get('item9_positive') else 7, crisis_reason)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        first = idem.existing(Assessment, user_id, key) if isinstance(exc, IntegrityError) else None
        if first:  # concurrent double submit: the other request won; answer with its row
            return _assessment_replay(first)
        logger.error("Failed to save assessment user=%s crisis=%s err=%s", user_id, bool(crisis_reason), type(exc).__name__)
        fail = {'success': False, 'message': 'Failed to save assessment.'}
        if crisis_reason:  # the emergency text and helplines never depend on the DB write
            fail.update(crisis=True, ai_insights=ai_insights, helplines=get_helplines())
        return jsonify(fail), 500

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
@prescriptions_required
@login_required
@patient_required
def my_prescriptions():
    return list_page()  # logic lives in routes/rx_patient.py; the endpoint name stays

@patient_bp.route('/api/progress', methods=['GET'])
@login_required
@patient_required
def get_progress():
    try:
        # Import models at function-time to avoid circular imports in some setups
        user_id = session['user_id']
        # newest page first per series (?page=, ?per_page=, default 100 because these feed history charts), returned chronologically
        assessments, a_meta = paginate(Assessment.query.filter_by(user_id=user_id).order_by(Assessment.created_at.desc(), Assessment.id.desc()), default=100)
        moods, m_meta = paginate(MoodLog.query.filter_by(user_id=user_id).order_by(MoodLog.created_at.desc(), MoodLog.id.desc()), default=100)
        assessments.reverse()
        moods.reverse()

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

        return jsonify({"ok": True, "assessments": a_out, "moods": m_out, "meta": {"assessments": a_meta, "moods": m_meta}}), 200
    except Exception as e:
        current_app.logger.exception("progress fetch failed")
        return jsonify({"ok": False, "error": "Could not load progress."}), 500

@patient_bp.route('/api/digital-detox-data')
@login_required
@patient_required
def digital_detox_data():
    user_id = session['user_id']
    
    # default 30 rows (a month chart); the body is a bare array, so paging info goes in X-* headers
    screen_time_logs, detox_meta = paginate(DigitalDetoxLog.query.filter_by(user_id=user_id).order_by(DigitalDetoxLog.date.desc(), DigitalDetoxLog.id.desc()), default=30)
    
    data = []
    for log in screen_time_logs:
        data.append({
            'date': log.date.strftime('%Y-%m-%d'),
            'hours': log.screen_time_hours,
            'academic_score': log.academic_score,
            'social_interactions': log.social_interactions,
            'ai_score': log.ai_score
        })
    
    return set_page_headers(jsonify(data), detox_meta)

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
        ok, ai_analysis = run_capped(ai_service.generate_digital_detox_insights, detox_data, seconds=AI_REQUEST_CAP)
        ai_analysis = ai_analysis if ok and isinstance(ai_analysis, dict) else {}

        # One log per day: a second submission today updates it (and earns no extra points).
        today = ist_today()  # the log date is the patient's IST day; DB unique (user_id, date) backs this up

        def fill(log):
            log.screen_time_hours = screen_time
            log.academic_score = academic_score
            log.social_interactions = social_interactions
            log.ai_score = ai_analysis.get('score', 'N/A')
            log.ai_suggestion = ai_analysis.get('analysis', 'No suggestion available')

        new_log = DigitalDetoxLog.query.filter_by(user_id=user_id, date=today).first()
        is_new = new_log is None
        if is_new:
            new_log = DigitalDetoxLog(user_id=user_id, date=today)
            db.session.add(new_log)
        fill(new_log)
        try:
            db.session.commit()
        except IntegrityError:  # two first submissions raced: the other one created today's row, update it instead
            db.session.rollback()
            is_new = False
            new_log = DigitalDetoxLog.query.filter_by(user_id=user_id, date=today).first()
            fill(new_log)
            db.session.commit()

        if is_new:
            award_points(user_id, 15, 'digital_detox_log', ref=f'detox:{new_log.id}')

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
            'ai_analysis': ai_analysis,
            'logged_count': DigitalDetoxLog.query.filter_by(user_id=user_id).count(), 'caveat': ai_caveats.DETOX_CAVEAT
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
        key = idem.get_key()
        if idem.existing(JournalEntry, user_id, key):  # replay: already saved
            flash('Journal entry saved successfully!', 'success')
            return redirect(url_for('patient.patient_journal'))
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

        # O-02: rule-based check on the text; the event holds a code only, never the text. Same transaction as the entry.
        from utils.crisis import record_crisis, text_is_crisis_detailed
        from utils.helplines import helplines_text
        crisis, crisis_matched_via = text_is_crisis_detailed(f"{title}\n{content}")
        try:
            entry = JournalEntry(user_id=user_id, title=title, content=content, sentiment=sentiment_result,
                                 ai_suggestions=ai_suggestions, client_request_id=key)
            db.session.add(entry)
            if crisis:  # '_fuzzy' suffix = audit-only tag, hit via the edit-distance-1 layer, not an exact regex
                record_crisis(user_id, 'journal', 9, 'journal_self_harm_fuzzy' if crisis_matched_via == 'fuzzy' else 'journal_self_harm')
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            if isinstance(exc, IntegrityError) and idem.existing(JournalEntry, user_id, key):  # concurrent double submit
                flash('Journal entry saved successfully!', 'success')
                return redirect(url_for('patient.patient_journal'))
            logger.error("Journal save FAILED user=%s crisis=%s err=%s", user_id, crisis, type(exc).__name__)
            flash('Could not save your journal entry. Please try again.', 'error')
            if crisis:
                flash('You are not alone. If you are in danger call 112. Free support: ' + helplines_text(), 'warning')
            return redirect(url_for('patient.patient_journal'))

        # Award points for journaling
        if not crisis:  # no cheerful rewards right after a crisis flag
            award_points(user_id, 15, 'journal_entry', ref=f'journal:{entry.id}')

        flash('Journal entry saved successfully!', 'success')
        if crisis:
            flash('We noticed your words sound painful. You do not have to carry this alone. '
                  'If you are in danger call 112. Free support: ' + helplines_text(), 'warning')
        return redirect(url_for('patient.patient_journal'))

    # GET request - display journal entries
    # newest page first (?page=, ?per_page=, default 50, max 100), handed over oldest-to-newest (the template reverses)
    user_entries, journal_pagination = paginate(JournalEntry.query.filter_by(user_id=user_id)
                                                .order_by(JournalEntry.created_at.desc(), JournalEntry.id.desc()), default=50)
    user_entries.reverse()

    return render_template('patient_journal.html',
                         user_name=session['user_name'],
                         journal_entries=user_entries,
                         pagination=journal_pagination)

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
    key = idem.get_key()
    saved = jsonify({'success': True, 'message': 'Mood saved. Thanks for checking in.'})
    if idem.existing(MoodLog, user_id, key):  # replay: same 200 body, no second row
        return saved
    try:
        db.session.add(MoodLog(user_id=user_id, mood_score=mood, notes=notes, client_request_id=key))
        # Same entry as a 'Daily Mood' assessment: the trend/progress code reads that type.
        db.session.add(Assessment(user_id=user_id, assessment_type='Daily Mood', score=mood,
                                  responses={'mood': mood, 'notes': notes or ''}, client_request_id=key))
        user = db.session.get(User, user_id)
        if user:
            user.last_assessment_at = utcnow()
        db.session.commit()
        return saved
    except IntegrityError:
        db.session.rollback()
        if idem.existing(MoodLog, user_id, key):  # concurrent double submit
            return saved
        logger.exception('Error saving mood')
        return jsonify({'success': False, 'message': 'Could not save your mood. Please try again.'}), 500
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
        user_logs, voice_pagination = paginate(VoiceLog.query.filter_by(user_id=user_id).order_by(VoiceLog.created_at.desc(), VoiceLog.id.desc()), default=50)
        
        return render_template('patient_voice_logs.html',
                             user_name=session.get('user_name', 'User'),
                             voice_logs=user_logs,
                             pagination=voice_pagination)
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
        key = None
        try:
            data = request.get_json(silent=True) or {}
            title = data.get('title')
            description = data.get('description')
            category = data.get('category') or 'mental_health'
            target_value = data.get('target_value')
            unit = data.get('unit')
            priority = data.get('priority') or 'medium'
            priority = priority if priority in ('low', 'medium', 'high') else 'medium'
            target_date = data.get('target_date')
            key = idem.get_key()
            first = idem.existing(Goal, user_id, key)
            if first:  # replay: the goal already exists
                return jsonify({'success': True, 'message': 'Goal created successfully!',
                                'goal': {'id': first.id, 'title': first.title, 'description': first.description}})

            if not title:
                return jsonify({'success': False, 'message': 'Title is required.'}), 400

            try:
                target_value = float(target_value) if target_value not in (None, '') else None
                parsed_target_date = datetime.strptime(target_date, '%Y-%m-%d').date() if target_date else None
                if target_value is not None and not target_value >= 0:
                    raise ValueError('negative target')
            except (TypeError, ValueError):
                return jsonify({'success': False, 'message': 'Target value must be a number and the date YYYY-MM-DD.'}), 400

            new_goal = Goal(
                client_request_id=key,
                user_id=user_id,
                title=title,
                description=description,
                category=category,
                priority=priority,
                target_value=target_value,
                unit=unit,
                target_date=parsed_target_date,
                start_date=ist_today()
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
        except idem.InvalidKey:
            raise
        except Exception as e:
            db.session.rollback()
            first = idem.existing(Goal, user_id, key) if isinstance(e, IntegrityError) else None
            if first:  # concurrent double submit: the other request created it
                return jsonify({'success': True, 'message': 'Goal created successfully!',
                                'goal': {'id': first.id, 'title': first.title, 'description': first.description}})
            logger.error("Error adding goal for user %s: %s", user_id, type(e).__name__)
            return jsonify({'success': False, 'message': 'Failed to create goal.'}), 500

    # GET request logic
    # default page 100: the goals page has no paging UI yet; `meta` says when there are more
    goals, goals_meta = paginate(Goal.query.filter_by(user_id=user_id).order_by(Goal.created_at.desc(), Goal.id.desc()), default=100)
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
    return jsonify({'success': True, 'goals': goals_data, 'meta': goals_meta})

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
                goal.completed_date = ist_today() if new_status == 'completed' else None

            goal.updated_at = datetime.utcnow()
            db.session.commit()
            if 'current_value' in data or new_status == 'completed':  # progress or completion, not a title edit
                award_points(user_id, 10, 'goal_progress', ref=f'goal:{goal.id}:{ist_today().isoformat()}')  # once per goal per day

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
