from datetime import date, datetime

from flask import Blueprint, render_template, jsonify, request, session, current_app
from sqlalchemy.exc import SQLAlchemyError
from decorators import api_login_required

core_bp = Blueprint('core', __name__)

ASSESSMENTS = ('PHQ-9', 'GAD-7')


def _patient_home(user_id):
    """Real data for the patient home: last mood, next screening, next appointment, recent activity."""
    from models import Appointment, Assessment, JournalEntry, MoodLog
    today = date.today()
    last_mood = MoodLog.query.filter_by(user_id=user_id).order_by(MoodLog.created_at.desc()).first()

    # Screening that was done longest ago (or never) is the suggested next one.
    last_done = {}
    for a in Assessment.query.filter(Assessment.user_id == user_id, Assessment.assessment_type.in_(ASSESSMENTS))             .order_by(Assessment.created_at.desc()).all():
        last_done.setdefault(a.assessment_type, a)
    next_type = min(ASSESSMENTS, key=lambda t: last_done[t].created_at if t in last_done else datetime.min)

    appointment = Appointment.query.filter(
        Appointment.user_id == user_id, Appointment.date >= today, Appointment.status.in_(['pending', 'accepted'])
    ).order_by(Appointment.date.asc(), Appointment.time.asc()).first()

    activity = [{'kind': 'Mood', 'text': f'Mood {m.mood_score} of 10', 'when': m.created_at, 'href': 'patient.progress'}
                for m in MoodLog.query.filter_by(user_id=user_id).order_by(MoodLog.created_at.desc()).limit(5).all()]
    activity += [{'kind': 'Screening', 'text': f'{a.assessment_type} completed, score {a.score}', 'when': a.created_at,
                  'href': 'patient.assessment'}
                 for a in Assessment.query.filter(Assessment.user_id == user_id, Assessment.assessment_type.in_(ASSESSMENTS))
                 .order_by(Assessment.created_at.desc()).limit(5).all()]
    activity += [{'kind': 'Journal', 'text': 'Journal entry saved', 'when': j.created_at, 'href': 'patient.patient_journal'}
                 for j in JournalEntry.query.filter_by(user_id=user_id).order_by(JournalEntry.created_at.desc()).limit(5).all()]
    activity = sorted((a for a in activity if a['when']), key=lambda a: a['when'], reverse=True)[:5]

    return {
        'mood_today': bool(last_mood and last_mood.created_at.date() == datetime.utcnow().date()),
        'last_mood': last_mood,
        'next_assessment': next_type,
        'next_assessment_last': last_done[next_type].created_at if next_type in last_done else None,
        'appointment': appointment,
        'activity': activity,
    }


def _provider_home(user_id):
    """Counts from the provider's own appointments only; caseload and crisis alerts live on the dashboard."""
    from models import Appointment, User
    today = date.today()
    mine = Appointment.query.filter(Appointment.provider_id == user_id)
    todays = mine.filter(Appointment.date == today, Appointment.status == 'accepted')         .order_by(Appointment.time.asc()).all()
    names = {u.id: u.name for u in User.query.filter(User.id.in_({a.user_id for a in todays})).all()} if todays else {}
    return {
        'pending_count': mine.filter(Appointment.status == 'pending').count(),
        'today': [{'time': a.time, 'name': names.get(a.user_id, 'Patient'), 'type': a.appointment_type} for a in todays],
    }


@core_bp.route('/')
def index():
    # Logged-in users get the app home; visitors get the public landing page.
    if session.get('user_id'):
        role, home = session.get('user_role'), {}
        try:
            if role == 'patient':
                home = _patient_home(session['user_id'])
            elif role == 'provider':
                home = _provider_home(session['user_id'])
        except SQLAlchemyError:
            current_app.logger.exception('home data failed')
        return render_template('index.html', role=role, home=home)
    return render_template('landing.html')


@core_bp.route('/ai')
def how_ai_works():
    return render_template('how_ai_works.html')

@core_bp.route('/api/status')
def status():
    return jsonify({"status": "ok"})

@core_bp.route('/api/tip')
@api_login_required
def tip():
    """Tip of the day: general content, no user data. Starts the once-a-day model call, answers at once."""
    from utils import daily_tip
    return jsonify(daily_tip.get_tip(refresh=True))


@core_bp.route('/api/ask', methods=['POST'])
@api_login_required
def ask_route():
    from ai.service import ask_guarded
    data = request.get_json(silent=True)
    prompt = data.get('prompt') if isinstance(data, dict) else None
    if not isinstance(prompt, str) or not prompt.strip():
        return jsonify({"error": "prompt is required"}), 400
    # crisis floor, per-user budget (session id), sanitising and output guard live in ask_guarded
    res = ask_guarded(prompt, user_id=session['user_id'])
    if res['rate_limited']:
        from utils.helplines import get_helplines
        return jsonify({"error": res['notice'], "rate_limited": True, "retry_after": res['retry_after'],
                        "helplines": get_helplines()}), 429
    return jsonify({"response": res['reply'], "ai_unavailable": res['ai_unavailable']})
