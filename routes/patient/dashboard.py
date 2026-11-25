"""Patient dashboard and appointment scheduling."""
from datetime import datetime
from flask import render_template, session, redirect, url_for, flash, request, jsonify
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import IntegrityError
import logging

from extensions import db
from models import User, Gamification, RPMData, Appointment, MoodLog, Assessment
from decorators import patient_required, login_required
from utils.assignments import link_provider_patient
from routes.rx_patient import dashboard_context
from utils.booking import staff_options, booking_extras, record_erx_consent, schedule_context
from utils import idempotency as idem
from utils.state import TransitionError, transition, CONFLICT_MESSAGE
from utils.timeutil import ist_now, ist_today
from ai.scoring import canonical_type, band_for

from . import patient_bp

logger = logging.getLogger(__name__)


@patient_bp.route('/dashboard')
@login_required
@patient_required
def patient_dashboard():
    user_id = session['user_id']

    gamification = Gamification.query.filter_by(user_id=user_id).first()
    rpm_data = RPMData.query.filter_by(user_id=user_id).order_by(RPMData.date.desc()).first()
    all_appointments = Appointment.query.filter_by(user_id=user_id).order_by(Appointment.date.asc(), Appointment.time.asc()).limit(500).all()
    latest_mood = MoodLog.query.filter_by(user_id=user_id).order_by(MoodLog.created_at.desc()).first()
    latest_screening = None  # newest PHQ-9 / GAD-7 for the dashboard card (band from ai.scoring)
    for a in Assessment.query.filter_by(user_id=user_id).order_by(Assessment.created_at.desc()).limit(20):
        kind = canonical_type(a.assessment_type)
        if kind:
            latest_screening = {'type': kind, 'score': a.score, 'band': band_for(kind, a.score), 'date': a.created_at}
            break

    upcoming_appointments = []
    past_appointments = []

    for appt in all_appointments:
        try:
            appt_datetime_str = f"{appt.date} {appt.time}"
            appt_datetime = datetime.strptime(appt_datetime_str, '%Y-%m-%d %H:%M')
            if appt_datetime >= ist_now():  # appointment date/time are IST wall-clock
                upcoming_appointments.append(appt)
            else:
                past_appointments.append(appt)
        except Exception:
            continue

    data = {
        'points': gamification.points if gamification else 0,
        'streak': gamification.streak if gamification else 0,
        'badges': gamification.badges if gamification else [],
        'rpm_data': {  # None = no reading yet; the template shows "No data yet"
            'heart_rate': rpm_data.heart_rate if rpm_data else None,
            'sleep_duration': rpm_data.sleep_duration if rpm_data else None,
            'steps': rpm_data.steps if rpm_data else None,
            'mood_score': latest_mood.mood_score if latest_mood else None
        }
    }

    alerts = []
    if rpm_data:
        if rpm_data.heart_rate and rpm_data.heart_rate > 100:
            alerts.append('High heart rate detected')
        if rpm_data.sleep_duration and rpm_data.sleep_duration < 6:
            alerts.append('Insufficient sleep detected')

    return render_template('patient_dashboard.html',
                         user_name=session['user_name'],
                         user=db.session.get(User, user_id),
                         data=data,
                         alerts=alerts,
                         upcoming_appointments=upcoming_appointments,
                         past_appointments=past_appointments,
                         latest_mood=latest_mood,
                         latest_screening=latest_screening,
                         **dashboard_context(user_id))


@patient_bp.route('/schedule', methods=['GET', 'POST'], endpoint='schedule_appointment')
@login_required
@patient_required
def schedule_appointment():
    if request.method == 'POST':
        date_str = request.form.get('date', '').strip()
        time_str = request.form.get('time', '').strip()
        appointment_type = request.form.get('appointment_type', '').strip()
        notes = request.form.get('notes', '')
        provider_id = request.form.get('provider_id')  # Optional provider selection
        user_id = session['user_id']

        key = idem.get_key()
        if idem.existing(Appointment, user_id, key):  # replay of a request that already succeeded
            return redirect(url_for('patient.patient_dashboard'))

        def bad(msg, status=400):
            flash(msg, 'error')
            return render_template('schedule.html', user_name=session['user_name'], appointments=_my_appointments(user_id),
                                   error=msg, form=request.form, **schedule_context(user_id, session.get('user_institution'))), status

        if not (date_str and time_str and appointment_type):
            return bad('Please choose a date, a time and an appointment type.')
        try:
            appointment_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            time_str = datetime.strptime(time_str, '%H:%M').strftime('%H:%M')
        except ValueError:
            return bad('Please enter a valid date (YYYY-MM-DD) and time (HH:MM).')
        if appointment_date < ist_today():
            return bad('That date is in the past. Please pick a future date.')
        provider, modality = None, None
        if provider_id:
            provider = db.session.get(User, int(provider_id)) if provider_id.isdigit() else None
            if not provider or provider.id not in {u.id for u in staff_options(session.get('user_institution'))}:
                return bad('Please choose a valid provider.')
            modality, extras_error = booking_extras(provider, request.form, user_id)
            if extras_error:
                return bad(extras_error)
            taken = Appointment.query.filter(Appointment.provider_id == provider.id, Appointment.date == appointment_date,
                                             Appointment.time == time_str, Appointment.status.in_(['pending', 'accepted', 'booked'])).first()
            if taken:
                return bad('That time slot is already booked. Please pick another.', 409)

        try:
            new_appointment = Appointment(
                user_id=user_id,
                provider_id=provider.id if provider else None,
                date=appointment_date,
                time=time_str,
                appointment_type=appointment_type,
                notes=notes,
                status='pending',  # Changed to pending for provider approval
                client_request_id=key,
                **({'modality': modality} if modality else {})
            )
            db.session.add(new_appointment)
            if provider:
                link_provider_patient(provider.id, user_id)  # P-02: booking is what lets this provider see the patient
            db.session.commit()
            record_erx_consent(provider, request.form, user_id)

            flash(f'Appointment successfully booked for {date_str} at {time_str}!', 'success')
            return redirect(url_for('patient.patient_dashboard'))
        except IntegrityError:  # double submit (same key) or the slot was taken a moment ago
            db.session.rollback()
            if idem.existing(Appointment, user_id, key):
                return redirect(url_for('patient.patient_dashboard'))
            return bad('That time slot is already booked. Please pick another.', 409)
        except Exception:
            db.session.rollback()
            logger.exception('appointment booking failed')
            flash('Could not book the appointment. Please try again.', 'error')
            return redirect(url_for('patient.schedule_appointment'))

    return render_template('schedule.html', user_name=session['user_name'], appointments=_my_appointments(session['user_id']),
                           error=None, form={}, **schedule_context(session['user_id'], session.get('user_institution', 'Sample University')))


def _my_appointments(user_id):
    return (Appointment.query.options(joinedload(Appointment.provider)).filter_by(user_id=user_id)
            .order_by(Appointment.date.desc(), Appointment.time.desc()).limit(50).all())


@patient_bp.route('/appointments/<int:appointment_id>/cancel', methods=['POST'])
@login_required
@patient_required
def cancel_appointment(appointment_id):
    appt = Appointment.query.filter_by(id=appointment_id, user_id=session['user_id']).first()
    if not appt:
        flash('Appointment not found.', 'error')
    else:
        try:
            transition(appt, 'cancelled', 'patient')
            db.session.commit()
            flash('Appointment cancelled.', 'success')
        except TransitionError:
            db.session.rollback()
            flash('This appointment can no longer be cancelled.', 'error')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
                return jsonify(success=False, message=CONFLICT_MESSAGE), 409
    return redirect(url_for('patient.schedule_appointment'))
