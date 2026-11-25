"""Draft prescription CRUD (design 5.3, 5.5). A draft belongs to one doctor; another doctor's id answers 404."""
from flask import g, jsonify, request

from core.decorators import login_required, prescriptions_required, verified_prescriber_required
from core.extensions import db
from models import Prescription
from services import prescriptions
from services.errors import ServiceError
from services.http import json_body, service_errors
from services.prescriptions._common import own_rx
from utils import idempotency as idem
from utils.pagination import page_args

BUCKETS = ('draft', 'issued', 'closed')


def _crid():
    try:
        return idem.get_key()
    except idem.InvalidKey:
        raise ServiceError('idempotency_key_required', 400)


def init(bp):
    def guarded(rule, **kw):
        """route + the decorator stack every prescribing JSON endpoint carries (order: flag, login, verified doctor)."""
        def deco(fn):
            fn = service_errors(fn)
            for dec in (verified_prescriber_required, login_required, prescriptions_required):
                fn = dec(fn)
            return bp.route(rule, **kw)(fn)
        return deco

    @guarded('/api/rx/prescriptions')
    def rx_api_list():
        bucket = request.args.get('status') if request.args.get('status') in BUCKETS else 'issued'
        page, per_page = page_args(default=20)
        rows, meta = prescriptions.list_for_doctor(g.actor.id, bucket, request.args.get('q'), page, per_page)
        return jsonify(success=True, items=rows, meta=meta)

    @guarded('/api/rx/prescriptions', methods=['POST'])
    def rx_api_create():
        patient_id = json_body().get('patient_id')
        if not isinstance(patient_id, int) or isinstance(patient_id, bool):
            raise ServiceError('field_invalid', 422, fields={'patient_id': 'A patient is required.'})
        key = _crid()
        replay = bool(key and Prescription.query.filter_by(provider_id=g.actor.id, client_request_id=key).first())
        rx = prescriptions.create_draft(g.actor.id, patient_id, key)
        db.session.commit()
        return jsonify(success=True, prescription=prescriptions.serialize(rx, 'doctor')), 200 if replay else 201

    @guarded('/api/rx/prescriptions/<int:rx_id>')
    def rx_api_get(rx_id):
        return jsonify(success=True, prescription=prescriptions.serialize(own_rx(g.actor.id, rx_id), 'doctor'))

    @guarded('/api/rx/prescriptions/<int:rx_id>', methods=['PUT'])
    def rx_api_update(rx_id):
        body = json_body()
        version = body.get('row_version')
        if not isinstance(version, int) or isinstance(version, bool):
            raise ServiceError('field_invalid', 422, fields={'row_version': 'Send the version you loaded.'})
        rx = prescriptions.save_draft(g.actor.id, rx_id, body, version)
        db.session.commit()
        return jsonify(success=True, prescription=prescriptions.serialize(rx, 'doctor'))

    @guarded('/api/rx/prescriptions/<int:rx_id>', methods=['DELETE'])
    def rx_api_delete(rx_id):
        prescriptions.delete_draft(g.actor.id, rx_id)
        db.session.commit()
        return jsonify(success=True)
