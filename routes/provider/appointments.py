"""Provider-side appointment status changes, listing, and the provider telehealth route."""
from flask import abort, jsonify, render_template, request, session
from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError

from decorators import can_join_telehealth, login_required, role_required
from models import Appointment, DigitalDetoxLog, RPMData, User, db
from utils.assignments import link_provider_patient, unlink_if_unrequested
from utils.pagination import page_args, page_meta
from utils.state import CONFLICT_MESSAGE, TransitionError, transition
from ai.scoring import canonical_type

from . import provider_bp
from .helpers import (all_institution_patients, assigned_patients, can_handle_appointment, latest_by_user,
                      latest_scores, risk_from_band, severity_band)


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
    from flask import current_app

    appointment = Appointment.query.get_or_404(appointment_id)
    if not can_handle_appointment(appointment):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    try:
        transition(appointment, new_status, 'provider', **fields)
        if link_patient:
            link_provider_patient(session['user_id'], appointment.user_id)  # P-02: accepting a request assigns the patient
        if new_status == 'rejected':
            unlink_if_unrequested(appointment.provider_id, appointment.user_id)  # O-14: don't leave a reject-only link
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
