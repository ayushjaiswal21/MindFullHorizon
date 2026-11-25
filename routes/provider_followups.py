"""Follow-up tracker routes and template context for counsellors and doctors (docs/FOLLOWUPS.md).

Same style as routes/provider_meds.py: its own blueprint, role decorators on every route, and the assigned-only rule
(`scoped_patient_or_404`) before any change. Plans are acted on only by providers assigned to the patient (404 for
everyone else). Writes are audited with ids and codes; an optional note is stored as a ClinicalNote, never on the step.
The context processor feeds the dashboard panel, the caseload flags and the report timeline without growing routes/provider.py.
"""
from flask import Blueprint, jsonify, request, session
from sqlalchemy import select

from decorators import login_required, provider_required
from extensions import db
from models import Appointment, ClinicalNote, FollowUpPlan, FollowUpStep
from utils import appt_reminders, followup_views, followups, score_flags, trend_flags
from utils.audit import audit
from utils.timeutil import ist_today, utcnow

provider_followups_bp = Blueprint('provider_followups', __name__)
STEP_ACTIONS = ('done', 'missed', 'skipped')
TREND_MAX = {'mood': 10, 'sleep': 12}  # fixed chart scale: mood 1-10, sleep hours capped for display only


def _combined_flags(provider_id):
    """Score-change flags (score_flags.py) and mood/sleep trend flags (trend_flags.py), merged per patient."""
    out = {uid: list(f) for uid, f in score_flags.flags_for_provider(provider_id).items()}
    for uid, f in trend_flags.flags_for_provider(provider_id).items():
        out.setdefault(uid, []).extend(f)
    return out


def _context():
    """Template variables for the two provider pages that show the tracker; nothing for any other endpoint."""
    endpoint = request.endpoint
    if session.get('user_role') != 'provider':
        return {}
    if endpoint == 'provider.provider_dashboard':
        return {'score_flags': _combined_flags(session['user_id']),
                'fu_panel': followup_views.panel(session['user_id']), 'fu_outcomes': followups.OUTCOMES}
    if endpoint == 'provider.wellness_report':  # the route has already 404ed unassigned patients
        pid = (request.view_args or {}).get('user_id')
        history = score_flags.history_for_patient(pid)
        spark = {k: {'xy': score_flags.sparkline_xy([s for _, s in v], k), 'rows': v, 'max': score_flags.MAX[k],
                     'flags': [f for f in score_flags.flags_from_series({k: [s for _, s in v]})]}
                 for k, v in history.items()}
        trend_history = trend_flags.history_for_patient(pid)
        trend_spark = {k: {'xy': trend_flags.sparkline_xy([v for _, v in rows], TREND_MAX[k]), 'rows': rows,
                            'max': TREND_MAX[k], 'flags': [f for f in [trend_flags.flag_from_series(k, rows)] if f]}
                       for k, rows in trend_history.items()}
        return {'fu_plans': followup_views.timeline(pid), 'fu_spark': spark, 'trend_spark': trend_spark,
                'fu_outcomes': followups.OUTCOMES, 'fu_close_reasons': followups.CLOSE_REASONS}
    return {}


provider_followups_bp.app_context_processor(_context)


def _bad(message='Check the form and try again.', status=400):
    return jsonify(success=False, message=message), status


def _plan_for_step(step_id):
    from routes.provider import scoped_patient_or_404
    step = db.get_or_404(FollowUpStep, step_id)
    plan = db.session.get(FollowUpPlan, step.plan_id)
    scoped_patient_or_404(plan.patient_id)  # 404 unless the patient is assigned to this provider
    return step, plan


@provider_followups_bp.route('/provider/api/followups/steps/<int:step_id>', methods=['POST'])
@login_required
@provider_required
def api_step(step_id):
    step, plan = _plan_for_step(step_id)
    data = request.get_json(silent=True) or {}
    action, outcome = data.get('action'), data.get('outcome') if data.get('action') == 'done' else None
    note = data.get('note') if isinstance(data.get('note'), str) else ''
    if action not in STEP_ACTIONS or (outcome is not None and not isinstance(outcome, str)):
        return _bad()
    try:
        changed = followups.set_step(step, action, session['user_id'], outcome)
        if changed and note.strip():
            db.session.add(ClinicalNote(provider_id=session['user_id'], patient_id=plan.patient_id, session_date=utcnow(),
                                        provider_notes=note.strip()[:2000]))
            audit(session['user_id'], 'add_clinical_note', 'user', plan.patient_id)
        db.session.commit()
    except followups.FollowUpConflict:
        db.session.rollback()
        return _bad(followups.CONFLICT_MESSAGE, 409)
    except followups.FollowUpError:
        db.session.rollback()
        return _bad()
    db.session.refresh(plan)
    return jsonify(success=True, status=action, plan_status=plan.status)


@provider_followups_bp.route('/provider/api/followups/plans/<int:plan_id>/close', methods=['POST'])
@login_required
@provider_required
def api_close(plan_id):
    from routes.provider import scoped_patient_or_404
    plan = db.get_or_404(FollowUpPlan, plan_id)
    scoped_patient_or_404(plan.patient_id)
    reason = (request.get_json(silent=True) or {}).get('reason')
    try:
        followups.close_plan(plan, reason if isinstance(reason, str) else '', session['user_id'])
        db.session.commit()
    except followups.FollowUpConflict:
        db.session.rollback()
        return _bad(followups.CONFLICT_MESSAGE, 409)
    except followups.FollowUpError:
        db.session.rollback()
        return _bad()
    return jsonify(success=True, plan_status='closed_early')


@provider_followups_bp.route('/provider/api/appointment-reminders')
@login_required
@provider_required
def api_reminders():
    """{appointment id: {'state': 'scheduled'|'sent', 'at': '2026-11-25 10:00'}} for the provider's upcoming accepted appointments."""
    rows = db.session.execute(select(Appointment.id, Appointment.date, Appointment.time).where(
        Appointment.provider_id == session['user_id'], Appointment.status.in_(('accepted', 'booked')),
        Appointment.date >= ist_today())).all()
    state = appt_reminders.states([r.id for r in rows])
    return jsonify(success=True, reminders={str(r.id): {'state': state[r.id], 'at': f'{r.date} {r.time}'}
                                            for r in rows if r.id in state})
