"""Start and complete a consult (design 3.3). The start time is the doctor's own recorded action, not proof of a call."""
from flask import flash, g, jsonify, redirect, request, url_for

from decorators import login_required, prescriptions_required, verified_prescriber_required
from extensions import db
from models import Appointment
from services.db_util import cas
from services.errors import ServiceError
from services.http import fail, iso, service_errors
from services.prescriptions.eligibility import QUALIFYING_MODALITIES
from utils.audit import audit
from utils.state import TransitionError, transition
from utils.timeutil import ist_today, utcnow

OPEN = ('accepted', 'booked')


def _wants_json():
    return request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest' \
        or 'application/json' in request.headers.get('Accept', '')


def _own_appointment(appointment_id):
    a = Appointment.query.filter_by(id=appointment_id, provider_id=g.actor.id).first()
    if a is None:
        raise ServiceError('not_found', 404)
    return a


def _respond(result, **payload):
    if _wants_json():
        return jsonify(success=True, **payload)
    flash(result, 'success')
    return redirect(url_for('provider.provider_dashboard'))


def init(bp):
    @bp.route('/appointments/<int:appointment_id>/start-consult', methods=['POST'])
    @prescriptions_required
    @login_required
    @verified_prescriber_required
    @service_errors
    def consult_start(appointment_id):
        a = _own_appointment(appointment_id)
        if a.status not in OPEN or a.date != ist_today():
            raise ServiceError('bad_transition', 409)
        if a.modality not in QUALIFYING_MODALITIES:
            raise ServiceError('field_invalid', 422, fields={'modality': 'Only video or in-person consults count.'})
        if cas(Appointment, (Appointment.id == a.id, Appointment.consult_started_at.is_(None)),
               consult_started_at=utcnow()):  # a repeat press keeps the first start time
            audit(g.actor.id, 'consult_start', 'appointment', a.id, modality=a.modality)
        db.session.commit()
        db.session.refresh(a)
        return _respond('Consult started.', started_at=iso(a.consult_started_at))

    @bp.route('/appointments/<int:appointment_id>/complete-consult', methods=['POST'])
    @prescriptions_required
    @login_required
    @verified_prescriber_required
    @service_errors
    def consult_complete(appointment_id):
        a = _own_appointment(appointment_id)
        if a.consult_started_at is None:
            raise ServiceError('bad_transition', 409)
        try:
            transition(a, 'completed', 'provider')
        except TransitionError:
            db.session.rollback()
            return fail(ServiceError('bad_transition', 409))
        audit(g.actor.id, 'consult_complete', 'appointment', appointment_id, modality=a.modality)
        db.session.commit()
        return _respond('Consult completed.', status='completed')
