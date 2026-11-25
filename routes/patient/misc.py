"""Small leftover views: the prescriptions list redirect, progress API and voice logs page."""
import logging
from flask import render_template, session, flash, redirect, url_for, jsonify, current_app

from models import Assessment, MoodLog, VoiceLog
from decorators import patient_required, login_required, prescriptions_required
from routes.rx_patient import list_page
from utils.pagination import paginate

from . import patient_bp

logger = logging.getLogger(__name__)


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
    except Exception:
        current_app.logger.exception("progress fetch failed")
        return jsonify({"ok": False, "error": "Could not load progress."}), 500


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
