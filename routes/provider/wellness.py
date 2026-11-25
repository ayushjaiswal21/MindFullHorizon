"""Per-patient wellness report (assessment/detox/RPM trends + read-only medications panel)."""
from datetime import datetime

from flask import render_template, session

from core.decorators import login_required, role_required
from models import Assessment, ClinicalNote, DigitalDetoxLog, Gamification, RPMData, db
from utils.audit import audit
from ai.scoring import canonical_type

from . import provider_bp
from .helpers import scoped_patient_or_404


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
