"""Validate, issue, cancel and amend (design 3.7, 3.8, 5.5)."""
from flask import g, jsonify

from core.decorators import login_required, prescriptions_required, verified_prescriber_required
from core.extensions import db, limiter
from services import prescriptions
from services.errors import ServiceError
from services.http import idem_key, json_body, service_errors
from services.prescriptions._common import own_rx

DOCTOR_CANCEL_REASONS = ('error', 'patient_request', 'clinical_change')  # 'amended' and 'system' are not the doctor's to pick


def init(bp):
    def guarded(rule, rate=None):
        def deco(fn):
            fn = service_errors(fn)
            for dec in (verified_prescriber_required, login_required, prescriptions_required):
                fn = dec(fn)
            if rate:
                fn = limiter.limit(rate)(fn)
            return bp.route(rule, methods=['POST'])(fn)
        return deco

    @guarded('/api/rx/prescriptions/<int:rx_id>/validate')
    def rx_api_validate(rx_id):
        res = prescriptions.validate(g.actor.id, rx_id)
        return jsonify(success=True, ok=res.ok, errors=res.errors, warnings=res.warnings)

    @guarded('/api/rx/prescriptions/<int:rx_id>/issue', rate='20 per minute')
    def rx_api_issue(rx_id):
        key = idem_key()
        ack = json_body().get('acknowledged_warnings') or []
        if not isinstance(ack, list) or not all(isinstance(c, str) for c in ack):
            raise ServiceError('field_invalid', 422, fields={'acknowledged_warnings': 'A list of warning codes.'})
        result = prescriptions.issue(g.actor.id, rx_id, key, ack)
        db.session.commit()
        body = jsonify(success=True, replayed=result.replayed,
                       prescription=prescriptions.serialize(result.prescription, 'doctor'))
        return body, 200 if result.replayed else 201

    @guarded('/api/rx/prescriptions/<int:rx_id>/cancel')
    def rx_api_cancel(rx_id):
        reason = json_body().get('reason_code')
        if reason not in DOCTOR_CANCEL_REASONS:
            raise ServiceError('field_invalid', 422, fields={'reason_code': 'Choose a reason.'})
        rx = prescriptions.cancel(g.actor.id, rx_id, reason)
        db.session.commit()
        return jsonify(success=True, prescription=prescriptions.serialize(rx, 'doctor'))

    @guarded('/api/rx/prescriptions/<int:rx_id>/amend')
    def rx_api_amend(rx_id):
        own_rx(g.actor.id, rx_id)
        draft = prescriptions.amend(g.actor.id, rx_id)
        db.session.commit()
        return jsonify(success=True, prescription=prescriptions.serialize(draft, 'doctor')), 201
