from flask import Blueprint, render_template, session, redirect, url_for, flash, request, jsonify, abort, current_app
from models import (User, Gamification, DigitalDetoxLog, Assessment, Goal, Medication,
                MedicationLog, BreathingExerciseLog, YogaLog, ProgressRecommendation,
                Prescription, MoodLog, RPMData, Appointment, ClinicalNote, BlogInsight, CrisisEvent, db, get_institutional_summary)
from decorators import login_required, role_required, prescriptions_required, can_join_telehealth
from sqlalchemy import or_, and_, func
from datetime import datetime, date, timedelta
import json
import os
from models import ProviderPatient
from utils.audit import audit
from utils.state import TransitionError, transition, CONFLICT_MESSAGE
from utils.timeutil import ist_today, utcnow
from sqlalchemy.exc import IntegrityError
from utils.assignments import link_provider_patient
from utils.cache_utils import cached, SUMMARY_TTL, ANALYTICS_TTL
from utils.pagination import page_args, page_meta
from utils.query_utils import latest_rows
import ai.service as ai_service
from utils.ai_cap import run_capped
from ai.scoring import band_for, canonical_type

provider_bp = Blueprint('provider', __name__, url_prefix='/provider', cli_group=None)

def normalize_institution_name(institution_name):
    """Normalize institution name for exact matching."""
    if not institution_name:
        return ''
    return institution_name.lower().strip()

def all_institution_patients():
    """Every patient of the provider's institution. Aggregates and the crisis safety override ONLY, never individual lists."""
    inst = normalize_institution_name(session.get('user_institution'))
    if not inst:
        return User.query.filter(db.false())
    return User.query.filter(User.role == 'patient', func.lower(func.trim(User.institution)) == inst)

def assigned_patients():
    """Patients linked to the logged-in provider by a ProviderPatient row (decision P-02), same institution only."""
    return (all_institution_patients().join(ProviderPatient, ProviderPatient.patient_id == User.id)
            .filter(ProviderPatient.provider_id == session['user_id']))

institution_patients = assigned_patients  # old name, now assignment-scoped so no caller can list the whole institution

def scoped_patient_or_404(patient_id):
    """The patient, if assigned to this provider; else 404 (never 403, so existence does not leak)."""
    patient = assigned_patients().filter(User.id == patient_id).first()
    if patient is None:
        abort(404)
    return patient

def min_group():
    """Minimum cell size K for institution aggregates (env MIN_AGGREGATE_GROUP, default 5)."""
    try:
        return max(1, int(os.getenv('MIN_AGGREGATE_GROUP', '5')))
    except ValueError:
        return 5

def institution_summary(institution):
    """Cached (60 s TTL, bumped by writes to the watched tables, see utils/cache_utils.py). Aggregate only, key = institution."""
    return cached('inst', ('summary', normalize_institution_name(institution), min_group()), SUMMARY_TTL,
                  lambda: _institution_summary(institution))

def _institution_summary(institution):
    """get_institutional_summary with small-cell suppression: a figure drawn from fewer than K people becomes None ('n/a')."""
    k = min_group()
    out = get_institutional_summary(institution, db)
    if (out['total_users'] or 0) < k:
        return {name: None for name in out}
    pids = all_institution_patients().with_entities(User.id)
    since = ist_today() - timedelta(days=7)
    detox_n = db.session.query(func.count(func.distinct(DigitalDetoxLog.user_id))).filter(
        DigitalDetoxLog.user_id.in_(pids), DigitalDetoxLog.date >= since).scalar() or 0
    asmt_n = db.session.query(func.count(func.distinct(Assessment.user_id))).filter(
        Assessment.user_id.in_(pids), Assessment.created_at >= datetime.utcnow() - timedelta(days=30)).scalar() or 0
    if (out['active_users'] or 0) < k:
        out['active_users'] = out['engagement_rate'] = None
    if detox_n < k:
        out['avg_screen_time'] = out['high_risk_users'] = None
    elif 0 < (out['high_risk_users'] or 0) < k:
        out['high_risk_users'] = None
    if asmt_n < k:
        out['avg_wellness_score'] = None
    if (out['completion_rate'] is not None and
            Appointment.query.filter(Appointment.user_id.in_(pids), Appointment.status.in_(('completed', 'cancelled')),
                                     Appointment.date >= since).count() < k):
        out['completion_rate'] = None
    return out

def severity_band(assessment_type, score):
    """Display band ('Moderate', ...) from ai.scoring; None for other types or no score. Old rows hold long titles, hence canonical_type."""
    band = band_for(canonical_type(assessment_type), score)
    return band.capitalize() if band else None

def latest_scores(ids):
    """{user_id: {'PHQ-9': row, 'GAD-7': row}} newest first. One query: the newest row per (user, stored type string),
    then merged by canonical type in Python (old rows carry long titles), so cost is flat in history length."""
    out = {}
    rows = latest_rows(Assessment, Assessment.user_id, (Assessment.created_at.desc(), Assessment.id.desc()), ids,
                       extra_partition=(Assessment.assessment_type,))
    for a in sorted(rows, key=lambda r: (r.created_at, r.id), reverse=True):
        t = canonical_type(a.assessment_type)
        if t:
            out.setdefault(a.user_id, {}).setdefault(t, a)
    return out

def risk_from_band(band):
    return {'Moderate': 'Medium', 'Moderately severe': 'High', 'Severe': 'High'}.get(band, 'Low')

def latest_by_user(model, ids, order_cols, key='user_id', *conditions):
    """{user_id: newest row} in one query (ROW_NUMBER window), so cost does not grow with history length."""
    return {getattr(row, key): row for row in latest_rows(model, getattr(model, key), order_cols, ids, *conditions)}

def unacknowledged_crises():
    """Safety override: open crisis events of the provider's whole institution, not only assigned patients."""
    ids = all_institution_patients().with_entities(User.id)
    return (CrisisEvent.query.filter(CrisisEvent.acknowledged_at.is_(None), CrisisEvent.user_id.in_(ids))
            .order_by(CrisisEvent.created_at.desc()).all())

def can_handle_appointment(appointment):
    """Own appointments, or unassigned requests from this institution (accepting one assigns the patient)."""
    if appointment.provider_id is not None:
        return appointment.provider_id == session['user_id']
    return all_institution_patients().filter(User.id == appointment.user_id).first() is not None

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
        audit(session['user_id'], 'ack_crisis', 'crisis_event', event.id)
    db.session.commit()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify(success=True)
    flash('Crisis alert acknowledged.', 'success')
    return redirect(url_for('provider.provider_dashboard'))

@provider_bp.route('/appointments/accept/<int:appointment_id>', methods=['POST'])
@login_required
@role_required('provider')
def accept_appointment(appointment_id):
    return _move_appointment(appointment_id, 'accepted', 'Appointment accepted successfully',
                             link_patient=True, provider_id=session['user_id'])

@provider_bp.route('/appointments/reject/<int:appointment_id>', methods=['POST'])
@login_required
@role_required('provider')
def reject_appointment(appointment_id):
    data = request.get_json(silent=True) or {}
    reason = data.get('reason') if isinstance(data.get('reason'), str) else None
    return _move_appointment(appointment_id, 'rejected', 'Appointment rejected successfully',
                             rejection_reason=(reason or 'No reason provided')[:500])

@provider_bp.route('/appointments/complete/<int:appointment_id>', methods=['POST'])
@login_required
@role_required('provider')
def complete_appointment(appointment_id):
    """Mark an accepted appointment completed (feeds the completion rate)."""
    return _move_appointment(appointment_id, 'completed', 'Appointment marked as completed')

@provider_bp.route('/appointments/cancel/<int:appointment_id>', methods=['POST'])
@login_required
@role_required('provider')
def cancel_appointment(appointment_id):
    """Cancel an accepted appointment (a pending request is rejected, not cancelled, by the provider)."""
    return _move_appointment(appointment_id, 'cancelled', 'Appointment cancelled')

def _move_appointment(appointment_id, new_status, ok_message, link_patient=False, **fields):
    """One provider-driven status change through the state machine. 403 outside scope, 409 on an illegal or lost-race move."""
    appointment = Appointment.query.get_or_404(appointment_id)
    if not can_handle_appointment(appointment):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    try:
        transition(appointment, new_status, 'provider', **fields)
        if link_patient:
            link_provider_patient(session['user_id'], appointment.user_id)  # P-02: accepting a request assigns the patient
        db.session.commit()
        return jsonify({'success': True, 'message': ok_message, 'status': new_status})
    except TransitionError:
        db.session.rollback()
        return jsonify({'success': False, 'message': CONFLICT_MESSAGE}), 409
    except IntegrityError:  # the slot was taken by another live appointment
        db.session.rollback()
        return jsonify({'success': False, 'message': 'That time slot is already taken.'}), 409
    except Exception:
        db.session.rollback()
        current_app.logger.exception('appointment status change failed')
        return jsonify({'success': False, 'message': 'Could not update the appointment'}), 500

@provider_bp.route('/appointments', methods=['GET'])
@login_required
@role_required('provider')
def provider_appointments():
    """Get provider's appointments with optional status filter"""
    status_filter = request.args.get('status', 'all')
    provider_id = session['user_id']

    query = Appointment.query.filter(
        or_(
            Appointment.provider_id == provider_id,
            and_(
                Appointment.provider_id.is_(None),
                Appointment.user_id.in_(all_institution_patients().with_entities(User.id))  # unassigned requests: name and slot only
            )
        )
    )

    if status_filter != 'all':
        query = query.filter_by(status=status_filter)

    # The dashboard JS has no paging UI yet, so the default page is 100 (cap 100); `meta` tells it when there is more.
    page, per_page = page_args(default=100)
    total = query.order_by(None).count()
    appointments = (query.order_by(Appointment.date.asc(), Appointment.time.asc(), Appointment.id.asc())
                    .limit(per_page).offset((page - 1) * per_page).all())

    all_ids = list({a.user_id for a in appointments})
    users = {u.id: u for u in User.query.filter(User.id.in_(all_ids)).all()} if all_ids else {}
    # health data and email only for assigned patients (P-02); other requesters show name and slot
    ids = [r.id for r in assigned_patients().filter(User.id.in_(all_ids)).with_entities(User.id).all()] if all_ids else []
    latest_assessment = {uid: max(v.values(), key=lambda a: (a.created_at, a.id)) for uid, v in latest_scores(ids).items()}
    latest_detox = latest_by_user(DigitalDetoxLog, ids, (DigitalDetoxLog.date.desc(), DigitalDetoxLog.id.desc()))
    latest_rpm = latest_by_user(RPMData, ids, (RPMData.date.desc(), RPMData.id.desc()))

    appointments_data = []
    for appt in appointments:
        user = users.get(appt.user_id)
        urgency = 'normal'
        patient_health_data = None
        if user and user.id in ids:
            a, d, r = latest_assessment.get(user.id), latest_detox.get(user.id), latest_rpm.get(user.id)
            band = severity_band(a.assessment_type, a.score) if a else None
            if risk_from_band(band) == 'High':
                urgency = 'high'
            patient_health_data = {
                'latest_assessment': {
                    'type': canonical_type(a.assessment_type),
                    'score': a.score,
                    'severity': band,
                    'risk': risk_from_band(band),
                    'date': a.created_at.strftime('%Y-%m-%d') if a.created_at else None
                } if a else None,
                'digital_wellness': {
                    'screen_time': d.screen_time_hours,
                    'ai_score': d.ai_score,
                    'date': d.date.strftime('%Y-%m-%d')
                } if d else None,
                'vital_signs': {
                    'heart_rate': r.heart_rate,
                    'sleep_duration': r.sleep_duration,
                    'mood_score': r.mood_score,
                    'date': r.date.strftime('%Y-%m-%d')
                } if r else None
            }

        appointments_data.append({
            'id': appt.id,
            'patient_name': user.name if user else 'Unknown',
            'patient_email': user.email if user and user.id in ids else None,
            'patient_id': user.id if user and user.id in ids else None,
            'date': appt.date.strftime('%Y-%m-%d'),
            'time': appt.time,
            'type': appt.appointment_type,
            'modality': appt.modality,  # 'video' | 'in_person' | None (doctor appointments only)
            'status': appt.status,
            'notes': appt.notes if appt.user_id in ids else None,
            'rejection_reason': appt.rejection_reason,
            'provider_id': appt.provider_id,
            'patient_health_data': patient_health_data,
            'created_at': appt.created_at.strftime('%Y-%m-%d %H:%M:%S') if appt.created_at else None,
            'updated_at': appt.updated_at.strftime('%Y-%m-%d %H:%M:%S') if appt.updated_at else None,
            'urgency_level': urgency
        })

    return jsonify({'success': True, 'appointments': appointments_data, 'meta': page_meta(page, per_page, total)})

@provider_bp.route('/telehealth/<int:user_id>')
@login_required
@role_required('provider')
def telehealth_session(user_id):
    if not can_join_telehealth(user_id):  # same rule as the socket join and /telehealth_session (decorators.py)
        abort(404)
    patient = User.query.filter_by(id=user_id, role='patient').first_or_404()
    return render_template('telehealth.html',
                           user_name=session['user_name'],
                           patient_id=patient.id,
                           patient_name=patient.name)

@provider_bp.route('/ai-documentation', methods=['GET', 'POST'])
@login_required
@role_required('provider')
def ai_documentation():
    if request.method == 'POST':
        transcript = request.form.get('transcript', '')
        patient_email = request.form.get('patient_email', '').strip()

        if transcript:
            patient = None
            patient_context = None
            if patient_email:
                patient = assigned_patients().filter(User.email == patient_email.lower()).first()
                if patient is None:  # same answer for "no such user" and "not your patient": no existence leak
                    flash('No assigned patient with that email.', 'error')
                    return render_template('ai_documentation.html', user_name=session['user_name'], transcript=transcript, patient_email=patient_email)
                recent_detox = DigitalDetoxLog.query.filter_by(user_id=patient.id).order_by(DigitalDetoxLog.date.desc(), DigitalDetoxLog.id.desc()).first()
                gamification = Gamification.query.filter_by(user_id=patient.id).first()

                patient_context = {
                    'wellness_trend': recent_detox.ai_score if recent_detox and recent_detox.ai_score else 'Not available',
                    'digital_score': recent_detox.ai_score if recent_detox and recent_detox.ai_score else 'Not available',
                    'engagement': f'{gamification.points} points, {gamification.streak} day streak' if gamification else 'Low'
                }

            generate = getattr(ai_service, 'generate_clinical_note', None)
            try:
                ok, clinical_note = run_capped(generate, transcript, patient_context, seconds=20.0) if generate else (False, None)
            except Exception:
                current_app.logger.exception('clinical note generation failed')
                clinical_note = None
            if not clinical_note:
                clinical_note = 'AI note unavailable. The transcript was saved; please write the note manually.'

            if patient:
                db.session.add(ClinicalNote(
                    provider_id=session['user_id'],
                    patient_id=patient.id,
                    session_date=utcnow(),
                    transcript=transcript,
                    ai_generated_note=clinical_note
                ))
                audit(session['user_id'], 'add_clinical_note', 'user', patient.id)
                db.session.commit()

            return render_template('ai_documentation.html',
                                 user_name=session['user_name'],
                                 transcript=transcript,
                                 clinical_note=clinical_note,
                                 patient_email=patient_email)
        else:
            flash('Please provide a session transcript.', 'error')

    return render_template('ai_documentation.html', user_name=session['user_name'])

def _analytics_core(k):
    """Institution aggregates for the analytics page, all computed in SQL (no per-row Python loops). Cached by the caller."""
    pids = all_institution_patients().with_entities(User.id)
    total_patients = pids.count()
    since = ist_today() - timedelta(days=30)
    active_patients = db.session.query(func.count(func.distinct(DigitalDetoxLog.user_id))).filter(
        DigitalDetoxLog.user_id.in_(pids), DigitalDetoxLog.date >= since).scalar() or 0
    assessments_30_days = Assessment.query.filter(
        Assessment.user_id.in_(pids), Assessment.created_at >= utcnow() - timedelta(days=30)).count()
    stats = db.session.query(func.avg(Gamification.points), func.avg(Gamification.streak), func.count(Gamification.id)
                             ).filter(Gamification.user_id.in_(pids)).first()

    # one row per (day, ai_score): the day's log count, hours and score mix are folded in Python from a few rows
    days = {}
    for day, score, n, hours in db.session.query(
            DigitalDetoxLog.date, DigitalDetoxLog.ai_score, func.count(), func.sum(DigitalDetoxLog.screen_time_hours)
    ).filter(DigitalDetoxLog.user_id.in_(pids), DigitalDetoxLog.date >= since).group_by(DigitalDetoxLog.date, DigitalDetoxLog.ai_score):
        d = days.setdefault(day.strftime('%Y-%m-%d'), {'count': 0, 'hours': 0.0, 'scores': []})
        d['count'] += n
        d['hours'] += hours or 0
        if score:
            d['scores'] += [score] * n
    score_values = {'Excellent': 5, 'Good': 4, 'Fair': 3, 'Needs Improvement': 2, 'Poor': 1}
    labels = [d for d in sorted(days) if days[d]['count'] >= k] if total_patients >= k else []
    screen, wellness = [], []
    for day in labels:
        d = days[day]
        screen.append(round(d['hours'] / d['count'], 1))
        nums = [score_values[s] for s in d['scores'] if s in score_values]
        wellness.append(round(sum(nums) / len(nums), 1) if nums else 0)
    return {'total_patients': total_patients, 'active_patients': active_patients, 'assessments_30_days': assessments_30_days,
            'gamification_stats': tuple(stats), 'chart_labels': labels, 'screen_time_data': screen, 'wellness_score_data': wellness}

@provider_bp.route('/analytics')
@login_required
@role_required('provider')
def analytics():
    institution = session.get('user_institution') or ''

    # Get institutional analytics data
    institutional_data = institution_summary(institution)

    # Get recent blog insights
    recent_blog_insights = BlogInsight.query.order_by(BlogInsight.created_at.desc()).limit(10).all()

    # Institution-wide aggregates (not individual data); every figure below is hidden when fewer than K people stand behind it.
    k = min_group()
    cell = lambda n: None if n is not None and 0 < n < k else n
    core = cached('inst', ('analytics', normalize_institution_name(institution), k), ANALYTICS_TTL, lambda: _analytics_core(k))
    total_patients, active_patients, assessments_30_days, gamification_stats = (
        core['total_patients'], core['active_patients'], core['assessments_30_days'], core['gamification_stats'])
    chart_labels, screen_time_data, wellness_score_data = core['chart_labels'], core['screen_time_data'], core['wellness_score_data']

    big = total_patients >= k  # below K nothing about the group is shown
    active_ok = big and (active_patients == 0 or active_patients >= k)
    analytics_data = {
        'institution': institution,
        'min_group': k,
        'total_patients': total_patients if big else None,
        'active_patients': active_patients if active_ok else None,
        'engagement_rate': round((active_patients / total_patients) * 100, 1) if active_ok and total_patients > 0 else None,
        'assessments_30_days': cell(assessments_30_days) if big else None,
        'avg_gamification_points': (round(gamification_stats[0], 1) if gamification_stats[0] else 0) if big else None,
        'avg_streak': (round(gamification_stats[1], 1) if gamification_stats[1] else 0) if big else None,
        'total_gamified_users': cell(gamification_stats[2]) if big else None,
        'chart_labels': chart_labels,
        'screen_time_data': screen_time_data,
        'wellness_score_data': wellness_score_data,
        'blog_insights': recent_blog_insights,
        'institutional_data': institutional_data
    }

    return render_template('analytics.html',
                         user_name=session['user_name'],
                         analytics_data=analytics_data,
                         datetime=datetime)

@provider_bp.route('/wellness-report/<int:user_id>')
@login_required
@role_required('provider')
def wellness_report(user_id):
    patient = scoped_patient_or_404(user_id)
    audit(session['user_id'], 'view_patient', 'user', patient.id)
    from routes.provider_meds import panel_context  # read-only medications panel; audits view_patient_meds
    meds_ctx = panel_context(patient.id)
    db.session.commit()

    gamification = Gamification.query.filter_by(user_id=user_id).first()

    ai_analysis = Assessment.query.filter_by(user_id=user_id).order_by(Assessment.created_at.desc(), Assessment.id.desc()).first()

    digital_detox_logs = DigitalDetoxLog.query.filter_by(user_id=user_id).order_by(DigitalDetoxLog.date.desc()).limit(90).all()
    assessments = Assessment.query.filter_by(user_id=user_id).order_by(Assessment.created_at.desc()).limit(20).all()

    digital_detox_data = []
    for log in digital_detox_logs:
        digital_detox_data.append({
            'date': log.date.strftime('%Y-%m-%d'),
            'screen_time_hours': log.screen_time_hours,
            'academic_score': log.academic_score,
            'social_interactions': log.social_interactions,
            'ai_score': log.ai_score
        })

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

    recent_sessions = ClinicalNote.query.filter_by(patient_id=user_id).order_by(ClinicalNote.session_date.desc()).limit(10).all()

    # Fetch RPM data for mood charting
    rpm_logs = RPMData.query.filter_by(user_id=user_id).order_by(RPMData.date.asc()).limit(90).all()
    mood_chart_labels = [log.date.strftime('%Y-%m-%d') for log in rpm_logs]
    mood_chart_data = [log.mood_score if log.mood_score else 0 for log in rpm_logs]

    # Fetch assessments for mental health charting
    mental_health_assessments = Assessment.query.filter_by(user_id=user_id).order_by(Assessment.created_at.asc()).all()
    mh_chart_labels = []
    gad7_data = []
    phq9_data = []

    for assessment in mental_health_assessments:
        date_str = assessment.created_at.strftime('%Y-%m-%d')
        if date_str not in mh_chart_labels:
            mh_chart_labels.append(date_str)
            gad7_data.append(None) # Initialize with None
            phq9_data.append(None) # Initialize with None

        idx = mh_chart_labels.index(date_str)
        if canonical_type(assessment.assessment_type) == 'GAD-7':
            gad7_data[idx] = assessment.score
        elif canonical_type(assessment.assessment_type) == 'PHQ-9':
            phq9_data[idx] = assessment.score

    # Filter out dates where both GAD-7 and PHQ-9 are None
    filtered_mh_chart_labels = []
    filtered_gad7_data = []
    filtered_phq9_data = []
    for i, label in enumerate(mh_chart_labels):
        if gad7_data[i] is not None or phq9_data[i] is not None:
            filtered_mh_chart_labels.append(label)
            filtered_gad7_data.append(gad7_data[i])
            filtered_phq9_data.append(phq9_data[i])

    # No model call while the page renders. The template only shows AI goal and adherence text when it is a
    # mapping with 'suggestions' / 'summary', which the service never returned, so both were always empty and cost 2 calls.
    ai_goal_suggestions = None
    ai_medication_adherence_insights = None

    return render_template('wellness_report.html',
                         user_name=session['user_name'],
                         patient=patient,
                         gamification=gamification,
                         ai_analysis=ai_analysis,
                         wellness_trend=wellness_trend,
                         recent_sessions=recent_sessions,
                         mood_chart_labels=mood_chart_labels,
                         mood_chart_data=mood_chart_data,
                         mh_chart_labels=filtered_mh_chart_labels,
                         gad7_data=filtered_gad7_data,
                         phq9_data=filtered_phq9_data,
                         ai_goal_suggestions=ai_goal_suggestions,
                         ai_medication_adherence_insights=ai_medication_adherence_insights,
                         datetime=datetime, **meds_ctx)


# --- CLI: manual assignment (flask assign-patient <provider_email> <patient_email>) ---
import click  # noqa: E402


@provider_bp.cli.command('assign-patient')
@click.argument('provider_email')
@click.argument('patient_email')
def assign_patient_cli(provider_email, patient_email):
    """Link a patient to a provider of the same institution (source 'manual')."""
    prov = User.query.filter_by(email=provider_email.strip().lower(), role='provider').first()
    pat = User.query.filter_by(email=patient_email.strip().lower(), role='patient').first()
    if not (prov and pat):
        raise click.ClickException('Provider or patient not found.')
    if not link_provider_patient(prov.id, pat.id, 'manual'):
        raise click.ClickException('Provider and patient must belong to the same institution.')
    audit(None, 'assign_patient', 'user', pat.id, provider_id=prov.id, source='manual')
    db.session.commit()
    click.echo('Assigned.')


@provider_bp.cli.command('backfill-assignments')
def backfill_assignments_cli():
    """One-off for databases that predate P-02: link every patient who already has a non-rejected appointment with a provider."""
    rows = (db.session.query(Appointment.provider_id, Appointment.user_id)
            .filter(Appointment.provider_id.isnot(None), Appointment.status != 'rejected').distinct().all())
    n = sum(bool(link_provider_patient(p, u)) for p, u in rows)
    db.session.commit()
    click.echo(f'Linked {n} of {len(rows)} provider-patient pairs.')

from routes.provider_rx import register as _register_rx; _register_rx(provider_bp)  # prescribing routes (design 5.3)
