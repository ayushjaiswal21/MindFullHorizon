"""Patient progress page and its AI suggestions endpoint (attached to the patient blueprint).

The page renders from the database only. The model-written suggestions load afterwards from
`GET /patient/api/progress/suggestions`, which answers from a stored recommendation when one is current, else
asks the model with a hard time cap and remembers a failure for ten minutes so a slow model is not retried on every visit.
"""
import logging
from datetime import timedelta

from flask import flash, jsonify, redirect, render_template, session, url_for

import ai.service as ai_service
from ai import gemini_impl
from ai.scoring import canonical_type
from decorators import login_required, patient_required
from extensions import db
from models import Assessment, Goal, ProgressRecommendation, User
from routes.patient import patient_bp
from utils.ai_cap import NegativeCache, run_capped
from utils.timeutil import utcnow

logger = logging.getLogger(__name__)

AI_CAP_SECONDS = 8.0
FAIL_TTL_SECONDS = 600.0
MAX_AGE = timedelta(days=7)
FAILED = NegativeCache(ttl=FAIL_TTL_SECONDS, limit=2000)
UNAVAILABLE = 'Suggestions are not available right now. Your scores and goals on this page are up to date. Try again later.'
EMPTY = 'Complete a screening or log your mood and suggestions will appear here.'


def _day(a):
    return a.created_at.strftime('%Y-%m-%d')


def _chart_series(assessments, kind):
    """{date: score} for one screening type, first entry of each day (oldest first)."""
    out = {}
    for a in sorted((a for a in assessments if canonical_type(a.assessment_type) == kind), key=lambda x: x.created_at):
        out.setdefault(_day(a), a.score)
    return out


def _wellness(latest_gad7, latest_phq9, latest_mood):
    parts = []
    if latest_gad7 and latest_gad7.score is not None:
        parts.append(10 - (latest_gad7.score / 21 * 9))
    if latest_phq9 and latest_phq9.score is not None:
        parts.append(10 - (latest_phq9.score / 27 * 9))
    if latest_mood and latest_mood.score is not None:
        parts.append(latest_mood.score)
    return round(sum(parts) / len(parts), 1) if parts else 0


@patient_bp.route('/progress')
@login_required
@patient_required
def progress():
    user_id = session['user_id']
    if not db.session.get(User, user_id):
        flash('User not found. Please log in again.', 'error')
        return redirect(url_for('auth.login'))
    try:
        goals = Goal.query.filter_by(user_id=user_id).all()
        assessments = Assessment.query.filter_by(user_id=user_id).order_by(Assessment.created_at.desc()).limit(1000).all()
    except Exception:
        logger.exception('progress data failed')
        return 'An error occurred while fetching your data. Please try again later.', 500

    latest_gad7 = next((a for a in assessments if canonical_type(a.assessment_type) == 'GAD-7'), None)
    latest_phq9 = next((a for a in assessments if canonical_type(a.assessment_type) == 'PHQ-9'), None)
    moods = sorted((a for a in assessments if a.assessment_type == 'Daily Mood'), key=lambda x: x.created_at)
    gad, phq = _chart_series(assessments, 'GAD-7'), _chart_series(assessments, 'PHQ-9')
    labels = sorted(set(gad) | set(phq))
    return render_template(
        'progress.html', user_name=session['user_name'], goals=goals,
        achievements=[g.title for g in goals if g.status == 'completed'],
        latest_gad7=latest_gad7, latest_phq9=latest_phq9,
        overall_wellness_score=_wellness(latest_gad7, latest_phq9, moods[-1] if moods else None),
        mood_data=[{'date': _day(m), 'score': m.score} for m in moods[-30:]],
        assessment_chart_labels=labels,
        assessment_chart_gad7_data=[gad.get(d) for d in labels],
        assessment_chart_phq9_data=[phq.get(d) for d in labels])


# ai/service.py swallows model errors and returns these stock titles; that is "no answer", not a suggestion to store.
CANNED_TITLES = {'Keep Going', 'Stay Consistent', 'Continue Daily Monitoring', 'Practice Self-Care', 'Progress Tracking',
                 'Wellness Focus', 'Daily Check-ins', 'Healthy Lifestyle'}


def _is_canned(rec):
    items = [i for i in (rec.get('insights') or []) + (rec.get('actions') or []) if isinstance(i, dict)]
    return all(i.get('title') in CANNED_TITLES for i in items)


def _valid(rec):
    return (isinstance(rec, dict) and isinstance(rec.get('insights', []), list) and isinstance(rec.get('actions', []), list)
            and bool(rec.get('insights') or rec.get('actions')))


def _reply(status, rec=None, message=None):
    body = {'status': status}
    if rec is not None:
        body.update(insights=rec.get('insights') or [], actions=rec.get('actions') or [])
    if message:
        body['message'] = message
    return jsonify(body)


@patient_bp.route('/api/progress/suggestions')
@login_required
@patient_required
def progress_suggestions():
    """JSON: status ok (insights, actions), empty or unavailable (message). Never waits longer than AI_CAP_SECONDS."""
    user_id = session['user_id']
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'status': 'unavailable', 'message': UNAVAILABLE}), 404
    stored = ProgressRecommendation.query.filter_by(user_id=user_id).order_by(ProgressRecommendation.created_at.desc()).first()
    since = user.last_assessment_at
    if (stored and _valid(stored.recommendations) and not _is_canned(stored.recommendations) and utcnow() - stored.created_at < MAX_AGE
            and (since is None or stored.created_at > since)):
        return _reply('ok', stored.recommendations)

    goals = Goal.query.filter_by(user_id=user_id).all()
    rows = Assessment.query.filter_by(user_id=user_id).order_by(Assessment.created_at.desc()).limit(200).all()
    if not rows and not goals:
        return _reply('empty', message=EMPTY)
    if FAILED.blocked(user_id) or not gemini_impl.PROVIDER.configured():
        return _reply('unavailable', message=UNAVAILABLE)

    gad7 = next((a for a in rows if canonical_type(a.assessment_type) == 'GAD-7'), None)
    phq9 = next((a for a in rows if canonical_type(a.assessment_type) == 'PHQ-9'), None)
    data = {'gad7_score': gad7.score if gad7 else 0, 'phq9_score': phq9.score if phq9 else 0,
            'wellness_score': _wellness(gad7, phq9, next((a for a in rows if a.assessment_type == 'Daily Mood'), None)),
            'completed_goals': sum(1 for g in goals if g.status == 'completed'), 'total_goals': len(goals),
            'days_since_assessment': (utcnow() - rows[0].created_at).days if rows and rows[0].created_at else 0}
    ok, rec = run_capped(ai_service.generate_progress_recommendations, data, seconds=AI_CAP_SECONDS)
    if not ok or not _valid(rec) or _is_canned(rec):
        FAILED.add(user_id)
        return _reply('unavailable', message=UNAVAILABLE)
    if gemini_impl.BREAKER.state == 'closed':  # the service swaps in canned text when the model fails: do not store that
        try:
            db.session.add(ProgressRecommendation(user_id=user_id, recommendations=rec))
            db.session.commit()
        except Exception:
            db.session.rollback()
            logger.exception('could not store progress recommendation')
    else:
        FAILED.add(user_id)
    return _reply('ok', rec)
