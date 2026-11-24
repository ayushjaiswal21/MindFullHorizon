from flask import Blueprint, render_template, session, redirect, url_for, flash, request, jsonify, abort, current_app
from models import (User, Gamification, DigitalDetoxLog, Assessment, Goal, Medication,
                MedicationLog, BreathingExerciseLog, YogaLog, ProgressRecommendation,
                Prescription, MoodLog, RPMData, Appointment, ClinicalNote, BlogInsight, CrisisEvent, db, get_institutional_summary)
from decorators import login_required, role_required
from sqlalchemy import or_, and_, func
from datetime import datetime, date, timedelta
import json
import ai.service as ai_service
from ai.scoring import band_for, canonical_type

provider_bp = Blueprint('provider', __name__, url_prefix='/provider')

def normalize_institution_name(institution_name):
    """Normalize institution name for exact matching."""
    if not institution_name:
        return ''
    return institution_name.lower().strip()

def institution_patients():
    """Patients of the provider's own institution (exact, case-insensitive match; none if unset)."""
    inst = normalize_institution_name(session.get('user_institution'))
    if not inst:
        return User.query.filter(db.false())
    return User.query.filter(User.role == 'patient', func.lower(func.trim(User.institution)) == inst)

def scoped_patient_or_404(patient_id):
    """The patient, if in this provider's institution or booked with this provider; else 404."""
    patient = User.query.filter_by(id=patient_id, role='patient').first_or_404()
    if institution_patients().filter(User.id == patient_id).first():
        return patient
    if Appointment.query.filter_by(user_id=patient_id, provider_id=session['user_id']).first():
        return patient
    abort(404)

def severity_band(assessment_type, score):
    """Display band ('Moderate', ...) from ai.scoring; None for other types or no score. Old rows hold long titles, hence canonical_type."""
    band = band_for(canonical_type(assessment_type), score)
    return band.capitalize() if band else None

def latest_scores(ids):
    """{user_id: {'PHQ-9': row, 'GAD-7': row}} newest first, one query."""
    out = {}
    if ids:
        for a in Assessment.query.filter(Assessment.user_id.in_(ids)).order_by(Assessment.created_at.desc(), Assessment.id.desc()):
            t = canonical_type(a.assessment_type)
            if t:
                out.setdefault(a.user_id, {}).setdefault(t, a)
    return out

def risk_from_band(band):
    return {'Moderate': 'Medium', 'Moderately severe': 'High', 'Severe': 'High'}.get(band, 'Low')

def latest_by_user(model, ids, order_cols, key='user_id', *conditions):
    """{user_id: newest row} in one query. shortcut: reads every row of these users; use a subquery if tables grow large."""
    out = {}
    if ids:
        for row in model.query.filter(getattr(model, key).in_(ids), *conditions).order_by(*order_cols):
            out.setdefault(getattr(row, key), row)
    return out

def unacknowledged_crises():
    ids = institution_patients().with_entities(User.id)
    return (CrisisEvent.query.filter(CrisisEvent.acknowledged_at.is_(None), CrisisEvent.user_id.in_(ids))
            .order_by(CrisisEvent.created_at.desc()).all())

def can_handle_appointment(appointment):
    """Own appointments, or unassigned ones from this institution."""
    if appointment.provider_id is not None:
        return appointment.provider_id == session['user_id']
    return institution_patients().filter(User.id == appointment.user_id).first() is not None

@provider_bp.route('/dashboard')
@login_required
@role_required('provider')
def provider_dashboard():
    institution = session.get('user_institution') or ''

    patients = institution_patients().order_by(User.name).all()
    ids = [p.id for p in patients]
    latest_detox = latest_by_user(DigitalDetoxLog, ids, (DigitalDetoxLog.date.desc(), DigitalDetoxLog.id.desc()))
    latest_note = latest_by_user(ClinicalNote, ids, (ClinicalNote.session_date.desc(), ClinicalNote.id.desc()), 'patient_id')
    scores = latest_scores(ids)
    crises = unacknowledged_crises()
    crisis_user_ids = {c.user_id for c in crises}
    names = {p.id: p.name for p in patients}

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
            'status': 'Active' if detox and detox.date >= date.today() - timedelta(days=7) else 'Inactive',
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
    overdue = Appointment.query.filter(Appointment.provider_id == session.get('user_id'), Appointment.status == 'accepted', Appointment.date < date.today()).order_by(Appointment.date.desc()).limit(5).all()
    overdue_names = {u.id: u.name for u in User.query.filter(User.id.in_([o.user_id for o in overdue])).all()} if overdue else {}
    for o in overdue:
        tasks.append({'title': f'Complete appointment note for {overdue_names.get(o.user_id, o.user_id)}', 'patient_id': o.user_id, 'due': o.date.strftime('%Y-%m-%d'), 'type': 'appointment'})
    for c in caseload_data:
        if c.get('status') == 'Inactive':
            tasks.append({'title': f'Check-in with {c.get("name")}', 'patient_id': c.get('user_id'), 'due': '', 'type': 'followup'})

    institutional_data = get_institutional_summary(institution, db)

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
                      'severity': c.severity, 'reason': c.reason,
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
                         crisis_events=crisis_events)

@provider_bp.route('/crisis/<int:event_id>/acknowledge', methods=['POST'])
@login_required
@role_required('provider')
def acknowledge_crisis(event_id):
    event = CrisisEvent.query.get_or_404(event_id)
    scoped_patient_or_404(event.user_id)
    if event.acknowledged_at is None:
        event.acknowledged_at = datetime.utcnow()
        event.acknowledged_by = session['user_id']
        db.session.commit()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify(success=True)
    flash('Crisis alert acknowledged.', 'success')
    return redirect(url_for('provider.provider_dashboard'))

@provider_bp.route('/appointments/accept/<int:appointment_id>', methods=['POST'])
@login_required
@role_required('provider')
def accept_appointment(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)
    if not can_handle_appointment(appointment):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    try:
        if appointment.provider_id is None:
            appointment.provider_id = session['user_id']
        appointment.status = 'accepted'
        appointment.updated_at = datetime.utcnow()
        db.session.commit()
        return jsonify({'success': True, 'message': 'Appointment accepted successfully'})
    except Exception:
        db.session.rollback()
        current_app.logger.exception('accept_appointment failed')
        return jsonify({'success': False, 'message': 'Could not accept the appointment'}), 500

@provider_bp.route('/appointments/reject/<int:appointment_id>', methods=['POST'])
@login_required
@role_required('provider')
def reject_appointment(appointment_id):
    data = request.get_json(silent=True) or {}
    appointment = Appointment.query.get_or_404(appointment_id)
    if not can_handle_appointment(appointment):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    try:
        appointment.status = 'rejected'
        appointment.rejection_reason = data.get('reason', 'No reason provided')
        appointment.updated_at = datetime.utcnow()
        db.session.commit()
        return jsonify({'success': True, 'message': 'Appointment rejected successfully'})
    except Exception:
        db.session.rollback()
        current_app.logger.exception('reject_appointment failed')
        return jsonify({'success': False, 'message': 'Could not reject the appointment'}), 500

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
                Appointment.user_id.in_(institution_patients().with_entities(User.id))
            )
        )
    )

    if status_filter != 'all':
        query = query.filter_by(status=status_filter)

    appointments = query.order_by(Appointment.date.asc(), Appointment.time.asc()).all()

    ids = list({a.user_id for a in appointments})
    users = {u.id: u for u in User.query.filter(User.id.in_(ids)).all()} if ids else {}
    latest_assessment = {uid: max(v.values(), key=lambda a: (a.created_at, a.id)) for uid, v in latest_scores(ids).items()}
    latest_detox = latest_by_user(DigitalDetoxLog, ids, (DigitalDetoxLog.date.desc(), DigitalDetoxLog.id.desc()))
    latest_rpm = latest_by_user(RPMData, ids, (RPMData.date.desc(), RPMData.id.desc()))

    appointments_data = []
    for appt in appointments:
        user = users.get(appt.user_id)
        urgency = 'normal'
        patient_health_data = None
        if user:
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
            'patient_email': user.email if user else 'Unknown',
            'patient_id': user.id if user else None,
            'date': appt.date.strftime('%Y-%m-%d'),
            'time': appt.time,
            'type': appt.appointment_type,
            'status': appt.status,
            'notes': appt.notes,
            'rejection_reason': appt.rejection_reason,
            'provider_id': appt.provider_id,
            'patient_health_data': patient_health_data,
            'created_at': appt.created_at.strftime('%Y-%m-%d %H:%M:%S') if appt.created_at else None,
            'updated_at': appt.updated_at.strftime('%Y-%m-%d %H:%M:%S') if appt.updated_at else None,
            'urgency_level': urgency
        })

    return jsonify({'success': True, 'appointments': appointments_data})

@provider_bp.route('/telehealth/<int:user_id>')
@login_required
@role_required('provider')
def telehealth_session(user_id):
    patient = scoped_patient_or_404(user_id)
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
                found = User.query.filter_by(email=patient_email, role='patient').first()
                if found is None:
                    flash('No patient with that email.', 'error')
                    return render_template('ai_documentation.html', user_name=session['user_name'], transcript=transcript, patient_email=patient_email)
                patient = scoped_patient_or_404(found.id)
                recent_detox = DigitalDetoxLog.query.filter_by(user_id=patient.id).order_by(DigitalDetoxLog.date.desc(), DigitalDetoxLog.id.desc()).first()
                gamification = Gamification.query.filter_by(user_id=patient.id).first()

                patient_context = {
                    'wellness_trend': recent_detox.ai_score if recent_detox and recent_detox.ai_score else 'Not available',
                    'digital_score': recent_detox.ai_score if recent_detox and recent_detox.ai_score else 'Not available',
                    'engagement': f'{gamification.points} points, {gamification.streak} day streak' if gamification else 'Low'
                }

            generate = getattr(ai_service, 'generate_clinical_note', None)
            try:
                clinical_note = generate(transcript, patient_context) if generate else None
            except Exception:
                current_app.logger.exception('clinical note generation failed')
                clinical_note = None
            if not clinical_note:
                clinical_note = 'AI note unavailable. The transcript was saved; please write the note manually.'

            if patient:
                db.session.add(ClinicalNote(
                    provider_id=session['user_id'],
                    patient_id=patient.id,
                    session_date=datetime.now(),
                    transcript=transcript,
                    ai_generated_note=clinical_note
                ))
                db.session.commit()

            return render_template('ai_documentation.html',
                                 user_name=session['user_name'],
                                 transcript=transcript,
                                 clinical_note=clinical_note,
                                 patient_email=patient_email)
        else:
            flash('Please provide a session transcript.', 'error')

    return render_template('ai_documentation.html', user_name=session['user_name'])

@provider_bp.route('/analytics')
@login_required
@role_required('provider')
def analytics():
    institution = session.get('user_institution') or ''

    # Get institutional analytics data
    institutional_data = get_institutional_summary(institution, db)

    # Get recent blog insights
    recent_blog_insights = BlogInsight.query.order_by(BlogInsight.created_at.desc()).limit(10).all()

    # Get patient engagement trends
    patient_ids = [p.id for p in institution_patients().with_entities(User.id).all()]

    # Get recent digital detox data for trends
    recent_detox = DigitalDetoxLog.query.filter(
        DigitalDetoxLog.user_id.in_(patient_ids),
        DigitalDetoxLog.date >= datetime.now().date() - timedelta(days=30)
    ).all()

    # Calculate engagement metrics
    active_patients = len(set([log.user_id for log in recent_detox]))
    total_patients = len(patient_ids)

    # Get assessment completion rates
    assessments_30_days = Assessment.query.filter(
        Assessment.user_id.in_(patient_ids),
        Assessment.created_at >= datetime.now() - timedelta(days=30)
    ).count()

    # Get gamification stats
    gamification_stats = db.session.query(
        func.avg(Gamification.points),
        func.avg(Gamification.streak),
        func.count(Gamification.id)
    ).filter(Gamification.user_id.in_(patient_ids)).first()

    # Get wellness trend data for charts
    detox_trends = {}
    for log in recent_detox:
        date_str = log.date.strftime('%Y-%m-%d')
        if date_str not in detox_trends:
            detox_trends[date_str] = {'total_hours': 0, 'count': 0, 'ai_scores': []}
        detox_trends[date_str]['total_hours'] += log.screen_time_hours
        detox_trends[date_str]['count'] += 1
        if log.ai_score:
            detox_trends[date_str]['ai_scores'].append(log.ai_score)

    # Calculate average daily screen time and wellness scores
    chart_labels = sorted(detox_trends.keys())
    screen_time_data = []
    wellness_score_data = []
    score_values = {'Excellent': 5, 'Good': 4, 'Fair': 3, 'Needs Improvement': 2, 'Poor': 1}

    for day in chart_labels:
        data = detox_trends[day]
        avg_screen_time = data['total_hours'] / data['count'] if data['count'] > 0 else 0
        screen_time_data.append(round(avg_screen_time, 1))

        # Convert AI scores to numeric values for averaging
        numeric_scores = [score_values[s] for s in data['ai_scores'] if s in score_values]
        avg_wellness = sum(numeric_scores) / len(numeric_scores) if numeric_scores else 0
        wellness_score_data.append(round(avg_wellness, 1))

    analytics_data = {
        'institution': institution,
        'total_patients': total_patients,
        'active_patients': active_patients,
        'engagement_rate': round((active_patients / total_patients) * 100, 1) if total_patients > 0 else 0,
        'assessments_30_days': assessments_30_days,
        'avg_gamification_points': round(gamification_stats[0], 1) if gamification_stats[0] else 0,
        'avg_streak': round(gamification_stats[1], 1) if gamification_stats[1] else 0,
        'total_gamified_users': gamification_stats[2],
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

@provider_bp.route('/send_prescription/<int:patient_id>', methods=['POST'])
@login_required
@role_required('provider')
def send_prescription(patient_id):
    provider_id = session['user_id']
    patient = scoped_patient_or_404(patient_id)

    medication_name = request.form.get('medication_name')
    dosage = request.form.get('dosage')
    instructions = request.form.get('instructions')
    expiry_date_str = request.form.get('expiry_date')

    if not all([medication_name, dosage]):
        flash('Medication name and dosage are required.', 'error')
        return redirect(url_for('provider.wellness_report', user_id=patient_id))

    expiry_date = None
    if expiry_date_str:
        try:
            expiry_date = datetime.strptime(expiry_date_str, '%Y-%m-%d')
        except ValueError:
            flash('Invalid expiry date format. Please use YYYY-MM-DD.', 'error')
            return redirect(url_for('provider.wellness_report', user_id=patient_id))

    try:
        new_prescription = Prescription(
            provider_id=provider_id,
            patient_id=patient_id,
            medication_name=medication_name,
            dosage=dosage,
            instructions=instructions,
            expiry_date=expiry_date
        )
        db.session.add(new_prescription)
        db.session.commit()
        flash(f'Prescription for {medication_name} sent to {patient.name}.', 'success')
    except Exception:
        db.session.rollback()
        current_app.logger.exception('send_prescription failed')
        flash('Could not send the prescription. Please try again.', 'error')

    return redirect(url_for('provider.wellness_report', user_id=patient_id))

@provider_bp.route('/wellness-report/<int:user_id>')
@login_required
@role_required('provider')
def wellness_report(user_id):
    patient = scoped_patient_or_404(user_id)

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

    # Prepare patient data for AI goal suggestions
    insights = None
    if ai_analysis and ai_analysis.ai_insights:
        try:
            insights = json.loads(ai_analysis.ai_insights)
        except ValueError:
            insights = None
    patient_data_for_ai = {
        'latest_assessment': {
            'type': ai_analysis.assessment_type,
            'score': ai_analysis.score,
            'insights': insights
        } if ai_analysis else None,
        'recent_goals': [{'title': g.title, 'status': g.status, 'progress': g.progress_percentage} for g in Goal.query.filter_by(user_id=user_id).order_by(Goal.created_at.desc()).limit(5).all()],
        'recent_digital_detox': [{'screen_time_hours': d.screen_time_hours, 'ai_score': d.ai_score} for d in digital_detox_logs[:5]]
    }
    ai_goal_suggestions = ai_service.generate_goal_suggestions(patient_data_for_ai)

    # Fetch medication logs for AI adherence analysis
    medication_logs = MedicationLog.query.filter_by(user_id=user_id).order_by(MedicationLog.taken_at.desc()).limit(30).all()
    medication_logs_data = [{'medication_id': log.medication_id, 'taken_at': log.taken_at.isoformat()} for log in medication_logs]
    ai_medication_adherence_insights = ai_service.analyze_medication_adherence(medication_logs_data, patient_data_for_ai)

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
                         datetime=datetime)
