"""Medication tracker and daily medication logging."""
from datetime import datetime
from flask import render_template, session, redirect, url_for, flash, request, jsonify
from sqlalchemy.exc import IntegrityError

from core.extensions import db
from models import Medication, MedicationLog
from core.decorators import patient_required, login_required
from utils.gamification import award_points
from utils.timeutil import ist_today, utcnow

from . import patient_bp


@patient_bp.route('/medication', methods=['GET', 'POST'])
@login_required
@patient_required
def medication():
    user_id = session['user_id']

    if request.method == 'POST':
        name = request.form.get('name')
        dosage = request.form.get('dosage')
        frequency = request.form.get('frequency')
        time_of_day = request.form.get('time_of_day')

        if not name or not dosage or not frequency:
            flash('Medication name, dosage, and frequency are required.', 'error')
        else:
            new_medication = Medication(
                user_id=user_id,
                name=name,
                dosage=dosage,
                frequency=frequency,
                time_of_day=time_of_day
            )
            db.session.add(new_medication)
            db.session.commit()
            flash(f'{name} has been added to your tracker.', 'success')
        return redirect(url_for('patient.medication'))

    medications = Medication.query.filter_by(user_id=user_id, is_active=True).all()

    today = ist_today()
    todays_logs = MedicationLog.query.filter(
        MedicationLog.user_id == user_id,
        MedicationLog.log_date == today
    ).all()

    logged_med_ids = {log.medication_id for log in todays_logs}

    return render_template('medication.html',
                         user_name=session['user_name'],
                         medications=medications,
                         logged_med_ids=logged_med_ids,
                         moment=datetime,
                         today=today)


@patient_bp.route('/log-medication', methods=['POST'])
@login_required
@patient_required
def log_medication():
    user_id = session['user_id']
    medication_id = request.form.get('medication_id', '')
    medication = Medication.query.filter_by(id=int(medication_id), user_id=user_id).first() if medication_id.isdigit() else None
    if not medication:
        return jsonify({'success': False, 'message': 'Medication not found.'}), 404

    # One log per medication per IST day (DB unique uq_medlog_med_day): a repeat or a race is "already logged", never a second row.
    today = ist_today()
    already = jsonify({'success': False, 'already_logged': True, 'message': 'You already logged this medication today.'})
    if MedicationLog.query.filter_by(medication_id=medication.id, log_date=today).first():
        return already
    log = MedicationLog(user_id=user_id, medication_id=medication.id, taken_at=utcnow(), log_date=today)
    db.session.add(log)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return already
    award_points(user_id, 10, 'log_medication', ref=f'medlog:{log.id}')
    return jsonify({'success': True, 'message': 'Medication logged. Nice work looking after yourself.'})
