"""Provider dashboard (caseload + crisis panel) and crisis acknowledgement."""
from datetime import timedelta

from flask import abort, flash, jsonify, redirect, render_template, request, session, url_for

from core.decorators import login_required, role_required
from models import Appointment, ClinicalNote, CrisisEvent, DigitalDetoxLog, User, db
from utils.audit import audit
from utils.followups import on_acknowledged
from utils.timeutil import ist_today, utcnow

from . import provider_bp
from .helpers import (all_institution_patients, institution_patients, institution_summary, latest_by_user,
                      latest_scores, min_group, risk_from_band, severity_band, unacknowledged_crises)


@provider_bp.route('/dashboard')
@login_required
@role_required('provider')
def provider_dashboard():
    institution = session.get('user_institution') or ''

    patients = institution_patients().order_by(User.name).limit(1000).all()  # cap: one counsellor's caseload, never unbounded
    ids = [p.id for p in patients]
    latest_detox = latest_by_user(DigitalDetoxLog, ids, (DigitalDetoxLog.date.desc(), DigitalDetoxLog.id.desc()))
    latest_note = latest_by_user(ClinicalNote, ids, (ClinicalNote.session_date.desc(), ClinicalNote.id.desc()), 'patient_id')
    scores = latest_scores(ids)
    crises = unacknowledged_crises()
    crisis_user_ids = {c.user_id for c in crises}
    names = {u.id: u.name for u in User.query.filter(User.id.in_({c.user_id for c in crises})).all()} if crises else {}
    if crises:  # safety override view: ids and counts only in the audit row, never patient text
        audit(session['user_id'], 'view_crisis_panel', 'crisis_event', None, event_ids=[c.id for c in crises])
        db.session.commit()

    from routes.provider_meds import rx_patient_ids  # "Rx" badge: patients with an active prescription (one query)
    rx_ids = rx_patient_ids(ids)
    caseload_data = []
    for patient in patients:
        detox = latest_detox.get(patient.id)
        note = latest_note.get(patient.id)
        levels = [risk_from_band(severity_band(a.assessment_type, a.score))
                  for a in scores.get(patient.id, {}).values()]
        # Risk comes from PHQ-9 / GAD-7 and unacknowledged crisis events, never from screen time.
        risk_level = 'High' if patient.id in crisis_user_ids or 'High' in levels else 'Medium' if 'Medium' in levels else 'Low'

        caseload_data.append({
            'user_id': patient.id,
            'name': patient.name,
            'email': patient.email,
            'risk_level': risk_level,
            'last_session': note.session_date.strftime('%Y-%m-%d') if note else 'No sessions',
            'status': 'Active' if detox and detox.date >= ist_today() - timedelta(days=7) else 'Inactive',
            'has_rx': patient.id in rx_ids,
            'digital_score': detox.ai_score if detox and detox.ai_score else 'No data'
        })

    # --- Apply client-side filters/search if provided ---
    search_q = request.args.get('q', '').strip()
    filter_risk = request.args.get('risk', '').strip()

    filtered_caseload = caseload_data
    if search_q:
        q_lower = search_q.lower()
        filtered_caseload = [c for c in filtered_caseload if q_lower in (c.get('name') or '').lower() or q_lower in (c.get('email') or '').lower()]

    if filter_risk in ('High', 'Medium', 'Low'):
        filtered_caseload = [c for c in filtered_caseload if c.get('risk_level') == filter_risk]

    # --- Tasks: accepted appointments already past, and inactive patients ---
    tasks = []
    overdue = Appointment.query.filter(Appointment.provider_id == session.get('user_id'), Appointment.status.in_(('accepted', 'booked')), Appointment.date < ist_today()).order_by(Appointment.date.desc()).limit(5).all()
    overdue_names = {u.id: u.name for u in User.query.filter(User.id.in_([o.user_id for o in overdue])).all()} if overdue else {}
    for o in overdue:
        tasks.append({'title': f'Complete appointment note for {overdue_names.get(o.user_id, o.user_id)}', 'patient_id': o.user_id, 'due': o.date.strftime('%Y-%m-%d'), 'type': 'appointment'})
    for c in caseload_data:
        if c.get('status') == 'Inactive':
            tasks.append({'title': f'Check-in with {c.get("name")}', 'patient_id': c.get('user_id'), 'due': '', 'type': 'followup'})

    institutional_data = institution_summary(institution)  # None means "n/a": fewer than K people behind the figure

    bi_data = {
        'patient_engagement': institutional_data['engagement_rate'],
        'avg_session_duration': institutional_data['avg_session_duration'],
        'completion_rate': institutional_data['completion_rate'],
        'satisfaction_score': institutional_data['satisfaction_score'],
        'total_patients': institutional_data['total_users'],
        'high_risk_patients': institutional_data['high_risk_users'],
        'avg_screen_time': institutional_data['avg_screen_time']
    }

    crisis_events = [{'id': c.id, 'user_id': c.user_id, 'name': names.get(c.user_id, 'Patient'), 'source': c.source,
                      'severity': c.severity, 'escalation_level': c.escalation_level or 0,
                      'can_view': c.user_id in ids,  # false: alert visible by safety override, no assignment, no report link
                      'created_at': c.created_at.strftime('%Y-%m-%d %H:%M') if c.created_at else ''}
                     for c in crises]

    return render_template('provider_dashboard.html',
                         user_name=session['user_name'],
                         caseload=filtered_caseload,
                         bi_data=bi_data,
                         institution=institution,
                         search_q=search_q,
                         filter_risk=filter_risk,
                         tasks=tasks,
                         assigned_count=len(patients),
                         aggregates_hidden=institutional_data['total_users'] is None,
                         min_group=min_group(),
                         crisis_events=crisis_events)


@provider_bp.route('/crisis/<int:event_id>/acknowledge', methods=['POST'])
@login_required
@role_required('provider')
def acknowledge_crisis(event_id):
    event = CrisisEvent.query.get_or_404(event_id)
    if not all_institution_patients().filter(User.id == event.user_id).first():  # safety override covers the institution
        abort(404)
    # compare-and-set: the first acknowledger wins, later or concurrent calls change and audit nothing (idempotent)
    won = CrisisEvent.query.filter(CrisisEvent.id == event.id, CrisisEvent.acknowledged_at.is_(None)).update(
        {'acknowledged_at': utcnow(), 'acknowledged_by': session['user_id']}, synchronize_session=False)
    if won:
        on_acknowledged(event, session['user_id'])  # audits ack_crisis and opens the follow-up plan (utils/followups.py)
    db.session.commit()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify(success=True)
    flash('Crisis alert acknowledged.', 'success')
    return redirect(url_for('provider.provider_dashboard'))
