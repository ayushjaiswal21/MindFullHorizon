"""Breathing, yoga and digital-detox self-logging."""
from flask import render_template, session, redirect, url_for, flash, request, jsonify
from sqlalchemy.orm import load_only
from sqlalchemy.exc import IntegrityError
from datetime import timedelta

from core.extensions import db
from models import BreathingExerciseLog, YogaLog, DigitalDetoxLog
from core.decorators import patient_required, login_required
from utils import idempotency as idem, ai_caveats
from utils.gamification import award_points
from utils.ai_cap import run_capped
from utils.timeutil import ist_today, to_ist_date, utcnow
from utils.validation import parse_duration, MIN_DURATION_MINUTES, MAX_DURATION_MINUTES
from utils.pagination import paginate, set_page_headers
import ai.service as ai_service

from . import patient_bp, AI_REQUEST_CAP


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

    except (ValueError, TypeError):
        return jsonify({'success': False, 'message': 'Invalid data format.'}), 400
    except Exception:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'An internal error occurred.'}), 500
