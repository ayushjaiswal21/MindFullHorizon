"""AI-assisted clinical documentation (never calls the model while the page itself renders the GET)."""
from flask import current_app, flash, render_template, request, session

import ai.service as ai_service
from decorators import login_required, role_required
from models import ClinicalNote, Gamification, User, db
from utils.ai_cap import run_capped
from utils.audit import audit
from utils.timeutil import utcnow

from . import provider_bp
from .helpers import assigned_patients


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
                gamification = Gamification.query.filter_by(user_id=patient.id).first()

                # No unvalidated AI-generated number (DigitalDetoxLog.ai_score) is fed in here: an AI estimate
                # shaping another AI generation that becomes a counsellor-facing note is exactly the cascading-AI
                # risk SYNTHESIS.md c2 warns against, worse than showing the estimate directly because the note
                # drafter can restate it as if it were a fact with no caveat attached. Only real logged
                # engagement (points/streak) goes in.
                patient_context = {
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
