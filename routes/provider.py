from flask import Blueprint, render_template, session, redirect, url_for, flash, request, jsonify
from models import (User, Gamification, DigitalDetoxLog, Assessment, Goal, Medication, 
                MedicationLog, BreathingExerciseLog, YogaLog, ProgressRecommendation, 
                Prescription, MoodLog, RPMData, Appointment, ClinicalNote, BlogInsight, db, get_institutional_summary)
from decorators import login_required, role_required
from sqlalchemy.orm import joinedload
from sqlalchemy import or_, and_
from datetime import datetime, date, timedelta
import json
from ai import ask as ai_service

provider_bp = Blueprint('provider', __name__, url_prefix='/provider')

def normalize_institution_name(institution_name):
    """Normalize institution name for better matching."""
    if not institution_name:
        return ''
    return institution_name.lower().strip()

@provider_bp.route('/dashboard')
@login_required
@role_required('provider')
def provider_dashboard():
    institution = session.get('user_institution', 'Sample University')

    # Normalize the provider's institution for better matching
    normalized_provider_institution = normalize_institution_name(institution)

    # More flexible institution matching for better patient-provider visibility
    # Split institution name into keywords for partial matching
    institution_keywords = set(normalized_provider_institution.split())

    # Fetch all patients and filter them based on institution similarity
    all_patients = User.query.options(
        joinedload(User.digital_detox_logs),
        joinedload(User.clinical_notes)
    ).filter_by(role='patient').all()

    # Filter patients based on institution similarity
    patients = []
    for patient in all_patients:
        patient_institution = patient.institution or ''
        normalized_patient_institution = normalize_institution_name(patient_institution)
        patient_keywords = set(normalized_patient_institution.split())

        # Check for similarity (partial match, case-insensitive)
        if institution_keywords & patient_keywords:  # Intersection of keywords
            patients.append(patient)
        elif not patient_institution and institution == 'Sample University':
            # Include patients with no institution if provider is using default
            patients.append(patient)

    # If no patients found with flexible matching, fall back to exact match for backward compatibility
    if not patients:
        patients = User.query.options(
            joinedload(User.digital_detox_logs),
            joinedload(User.clinical_notes)
        ).filter_by(role='patient', institution=institution).all()

    caseload_data = []
    for patient in patients:
        # Get latest detox and session from already loaded relationships (prevents N+1 queries)
        latest_detox = patient.digital_detox_logs[0] if patient.digital_detox_logs else None
        latest_session = patient.clinical_notes[0] if patient.clinical_notes else None

        risk_level = 'Low'
        if latest_detox:
            if latest_detox.screen_time_hours > 8 or (latest_detox.ai_score and latest_detox.ai_score == 'Needs Improvement'):
                risk_level = 'High'
            elif latest_detox.screen_time_hours > 6 or (latest_detox.ai_score and latest_detox.ai_score == 'Good'):
                risk_level = 'Medium'

        caseload_data.append({
            'user_id': patient.id,
            'name': patient.name,
            'email': patient.email,
            'risk_level': risk_level,
            'last_session': latest_session.session_date.strftime('%Y-%m-%d') if latest_session else 'No sessions',
            'status': 'Active' if latest_detox and latest_detox.date >= date.today() - timedelta(days=7) else 'Inactive',
            'digital_score': latest_detox.ai_score if latest_detox and latest_detox.ai_score else 'No data'
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

    # --- Simple Tasks derivation (quick wins): overdue appointments and inactive follow-ups ---
    tasks = []
    try:
        # Overdue appointments assigned to this provider (status 'booked' and date < today)
        overdue = Appointment.query.filter(Appointment.provider_id == session.get('user_id'), Appointment.status == 'booked', Appointment.date < date.today()).order_by(Appointment.date.desc()).limit(5).all()
        for o in overdue:
            tasks.append({'title': f'Complete appointment note for {o.user.name if o.user else o.user_id}', 'patient_id': o.user_id, 'due': o.date.strftime('%Y-%m-%d'), 'type': 'appointment'})
    except Exception:
        # If Appointment table/query fails for any reason, ignore tasks generation gracefully
        tasks = []

    # Also add patients with no recent activity (>7 days)
    try:
        for c in caseload_data:
            if c.get('status') == 'Inactive':
                tasks.append({'title': f'Check-in with {c.get("name")}', 'patient_id': c.get('user_id'), 'due': '', 'type': 'followup'})
    except Exception:
        pass

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
    
    return render_template('provider_dashboard.html', 
                         user_name=session['user_name'],
                         caseload=filtered_caseload,
                         bi_data=bi_data,
                         institution=institution,
                         search_q=search_q,
                         filter_risk=filter_risk,
                         tasks=tasks)

@provider_bp.route('/appointments/accept/<int:appointment_id>', methods=['POST'])
@login_required
@role_required('provider')
def accept_appointment(appointment_id):
    try:
        appointment = Appointment.query.get_or_404(appointment_id)
        provider_id = session['user_id']
        
        if appointment.provider_id is not None and appointment.provider_id != provider_id:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403
        
        if appointment.provider_id is None:
            appointment.provider_id = provider_id
            
        appointment.status = 'accepted'
        appointment.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Appointment accepted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@provider_bp.route('/appointments/reject/<int:appointment_id>', methods=['POST'])
@login_required
@role_required('provider')
def reject_appointment(appointment_id):
    try:
        data = request.get_json() or {}
        rejection_reason = data.get('reason', 'No reason provided')
        
        appointment = Appointment.query.get_or_404(appointment_id)
        provider_id = session['user_id']
        
        if appointment.provider_id is not None and appointment.provider_id != provider_id:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403
        
        appointment.status = 'rejected'
        appointment.rejection_reason = rejection_reason
        appointment.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Appointment rejected successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@provider_bp.route('/appointments', methods=['GET'])
@login_required
@role_required('provider')
def provider_appointments():
    """Get provider's appointments with optional status filter"""
    status_filter = request.args.get('status', 'all')
    provider_id = session['user_id']
    
    provider_institution = session.get('user_institution', 'Sample University')
    
    same_institution_users = User.query.filter_by(role='patient', institution=provider_institution).with_entities(User.id).all()
    same_institution_user_ids = [user.id for user in same_institution_users]
    
    query = Appointment.query.options(joinedload(Appointment.user)).filter(
        or_(
            Appointment.provider_id == provider_id,
            and_(
                Appointment.provider_id.is_(None),
                Appointment.user_id.in_(same_institution_user_ids)
            )
        )
    )
    
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    
    appointments = query.order_by(Appointment.date.asc(), Appointment.time.asc()).all()
    
    appointments_data = []
    for appt in appointments:
        patient_health_data = None
        if appt.user:
            latest_assessment = Assessment.query.filter_by(user_id=appt.user.id).order_by(Assessment.created_at.desc()).first()
            latest_detox = DigitalDetoxLog.query.filter_by(user_id=appt.user.id).order_by(DigitalDetoxLog.date.desc()).first()
            latest_rpm = RPMData.query.filter_by(user_id=appt.user.id).order_by(RPMData.date.desc()).first()
            
            patient_health_data = {
                'latest_assessment': {
                    'type': latest_assessment.assessment_type if latest_assessment else None,
                    'score': latest_assessment.score if latest_assessment else None,
                    'date': latest_assessment.created_at.strftime('%Y-%m-%d') if latest_assessment else None
                } if latest_assessment else None,
                'digital_wellness': {
                    'screen_time': latest_detox.screen_time_hours if latest_detox else None,
                    'ai_score': latest_detox.ai_score if latest_detox else None,
                    'date': latest_detox.date.strftime('%Y-%m-%d') if latest_detox else None
                } if latest_detox else None,
                'vital_signs': {
                    'heart_rate': latest_rpm.heart_rate if latest_rpm else None,
                    'sleep_duration': latest_rpm.sleep_duration if latest_rpm else None,
                    'mood_score': latest_rpm.mood_score if latest_rpm else None,
                    'date': latest_rpm.date.strftime('%Y-%m-%d') if latest_rpm else None
                } if latest_rpm else None
            }

        appointments_data.append({
            'id': appt.id,
            'patient_name': appt.user.name if appt.user else 'Unknown',
            'patient_email': appt.user.email if appt.user else 'Unknown',
            'patient_id': appt.user.id if appt.user else None,
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
            'urgency_level': 'high' if patient_health_data and patient_health_data.get('latest_assessment') and patient_health_data['latest_assessment'].get('score', 0) > 15 else 'normal'
        })
    
    return jsonify({'success': True, 'appointments': appointments_data})

@provider_bp.route('/ai-documentation', methods=['GET', 'POST'])
@login_required
@role_required('provider')
def ai_documentation():
    if request.method == 'POST':
        transcript = request.form.get('transcript', '')
        patient_email = request.form.get('patient_email', '')
        
        if transcript:
            patient_context = None
            if patient_email:
                patient = User.query.filter_by(email=patient_email, role='patient').first()
                if patient:
                    recent_detox = DigitalDetoxLog.query.filter_by(user_id=patient.id).order_by(DigitalDetoxLog.date.desc()).first()
                    gamification = Gamification.query.filter_by(user_id=patient.id).first()
                    
                    patient_context = {
                        'wellness_trend': recent_detox.ai_score if recent_detox and recent_detox.ai_score else 'Not available',
                        'digital_score': recent_detox.ai_score if recent_detox else 'Not available',
                        'engagement': f'{gamification.points} points, {gamification.streak} day streak' if gamification else 'Low'
                    }
            
            clinical_note = ai_service.generate_clinical_note(transcript, patient_context)
            
            if patient_email and patient:
                clinical_note_record = ClinicalNote(
                    provider_id=session['user_id'],
                    patient_id=patient.id,
                    session_date=datetime.now(),
                    transcript=transcript,
                    ai_generated_note=clinical_note
                )
                db.session.add(clinical_note_record)
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
    institution = session.get('user_institution', 'Sample University')

    # Get institutional analytics data
    institutional_data = get_institutional_summary(institution, db)

    # Get recent blog insights
    recent_blog_insights = BlogInsight.query.order_by(BlogInsight.created_at.desc()).limit(10).all()

    # Get patient engagement trends
    patients = User.query.filter_by(role='patient', institution=institution).all()
    patient_ids = [p.id for p in patients]

    # Get recent digital detox data for trends
    recent_detox = DigitalDetoxLog.query.filter(
        DigitalDetoxLog.user_id.in_(patient_ids),
        DigitalDetoxLog.date >= datetime.now().date() - timedelta(days=30)
    ).all()

    # Calculate engagement metrics
    active_patients = len(set([log.user_id for log in recent_detox]))
    total_patients = len(patients)

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

    for date in chart_labels:
        data = detox_trends[date]
        avg_screen_time = data['total_hours'] / data['count'] if data['count'] > 0 else 0
        screen_time_data.append(round(avg_screen_time, 1))

        # Convert AI scores to numeric values for averaging
        numeric_scores = []
        for score in data['ai_scores']:
            if score == 'Excellent':
                numeric_scores.append(5)
            elif score == 'Good':
                numeric_scores.append(4)
            elif score == 'Fair':
                numeric_scores.append(3)
            elif score == 'Needs Improvement':
                numeric_scores.append(2)
            elif score == 'Poor':
                numeric_scores.append(1)

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
        flash(f'Prescription for {medication_name} sent successfully to patient {patient_id}!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error sending prescription: {e}', 'error')

    return redirect(url_for('provider.wellness_report', user_id=patient_id))

@provider_bp.route('/wellness-report/<int:user_id>')
@login_required
@role_required('provider')
def wellness_report(user_id):
    from datetime import datetime
    
    patient = User.query.get_or_404(user_id)
    
    gamification = Gamification.query.filter_by(user_id=user_id).first()
    
    ai_analysis = Assessment.query.filter_by(user_id=user_id).order_by(Assessment.created_at.desc()).first()
    
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
        if assessment.assessment_type == 'GAD-7':
            gad7_data[idx] = assessment.score
        elif assessment.assessment_type == 'PHQ-9':
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
    patient_data_for_ai = {
        'latest_assessment': {
            'type': ai_analysis.assessment_type,
            'score': ai_analysis.score,
            'insights': json.loads(ai_analysis.ai_insights) if ai_analysis and ai_analysis.ai_insights else None
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
