@patient_bp.route('/log_mood', methods=['POST'])
@login_required
@role_required('patient')
def log_mood():
    user_id = session['user_id']
    mood = request.form.get('mood')
    notes = request.form.get('notes')

    if not mood:
        flash('Mood is required.', 'error')
        return redirect(url_for('patient.patient_dashboard'))

    new_mood_log = MoodLog(
        user_id=user_id,
        mood=mood,
        notes=notes
    )
    db.session.add(new_mood_log)
    db.session.commit()
    flash('Mood logged successfully!', 'success')
    return redirect(url_for('patient.patient_dashboard'))
