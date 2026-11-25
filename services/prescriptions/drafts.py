"""Draft prescriptions: create, edit (row_version), delete (design 3.2, 3.8)."""
from sqlalchemy.exc import IntegrityError

from core.extensions import db
from models import Medicine, Prescription, PrescriptionItem, User
from services import config, prescriber
from services.db_util import cas
from services.errors import ServiceError
from services.prescriptions._common import assigned_patient, clean, own_rx
from services.roles import norm_inst
from utils.audit import audit

STATUS3 = ('none_reported', 'listed', 'unknown')
MAX_DRAFT_ITEMS = 20  # hard bound on a payload; the policy limit (RX_MAX_ITEMS) is checked at validate and issue


def create_draft(doctor_id, patient_id, client_request_id=None):
    """A new draft for an assigned patient. The same (doctor, client_request_id) returns the first draft."""
    prescriber.require_verified(doctor_id)
    doctor = db.session.get(User, doctor_id)
    if client_request_id:
        first = Prescription.query.filter_by(provider_id=doctor_id, client_request_id=client_request_id).first()
        if first:
            return first
    if assigned_patient(doctor, patient_id) is None:
        raise ServiceError('patient_not_assigned', 404)
    rx = Prescription(provider_id=doctor_id, patient_id=patient_id, status='draft', client_request_id=client_request_id,
                      institution_key=norm_inst(doctor.institution), institution_name=(doctor.institution or '')[:100],
                      expiry_days=config.rx_expiry_days())
    db.session.add(rx)
    try:
        db.session.flush()
    except IntegrityError:  # a concurrent double submit with the same key won the race
        db.session.rollback()
        first = Prescription.query.filter_by(provider_id=doctor_id, client_request_id=client_request_id).first()
        if first is None:
            raise
        return first
    audit(doctor_id, 'rx_draft_create', 'prescription', rx.id, patient_id=patient_id)
    return rx


def _int(value, field, low, high):
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ServiceError('field_invalid', 422, fields={field: f'A whole number from {low} to {high}.'})
    return value


def _items(raw):
    """Validate the items array of a PUT. Dose and frequency may still be empty in a draft (validate flags them)."""
    if not isinstance(raw, list):
        raise ServiceError('field_invalid', 422, fields={'items': 'A list is expected.'})
    if len(raw) > MAX_DRAFT_ITEMS:
        raise ServiceError('too_many_items', 422)
    out, seen = [], set()
    for n, it in enumerate(raw, 1):
        if not isinstance(it, dict):
            raise ServiceError('field_invalid', 422, fields={'items': 'Each item must be an object.'})
        mid = _int(it.get('medicine_id'), 'medicine_id', 1, 2 ** 31 - 1)
        if mid in seen:
            raise ServiceError('duplicate_medicine', 422)
        seen.add(mid)
        if db.session.get(Medicine, mid) is None:
            raise ServiceError('not_found', 404)
        out.append(dict(line_no=n, medicine_id=mid, dose_text=clean(it.get('dose_text'), 60, 'dose_text') or '',
                        frequency=clean(it.get('frequency'), 60, 'frequency') or '',
                        duration_days=_int(it.get('duration_days'), 'duration_days', 1, 90),
                        quantity=_int(it.get('quantity'), 'quantity', 1, 500),
                        instructions=clean(it.get('instructions'), 200, 'instructions')))
    return out


def _fields(payload):
    """Editable scalar fields from a PUT payload (only the keys that are present)."""
    out = {}
    for key, limit in (('diagnosis', 120), ('allergies', 300), ('current_meds', 300)):
        if key in payload:
            out[key] = clean(payload[key], limit, key)
    for key in ('allergies_status', 'current_meds_status'):
        if key in payload:
            if payload[key] not in STATUS3 + (None,):
                raise ServiceError('field_invalid', 422, fields={key: 'Choose one of the options.'})
            out[key] = payload[key]
    if 'expiry_days' in payload:
        out['expiry_days'] = _int(payload['expiry_days'], 'expiry_days', 1, config.rx_expiry_days())
    if 'same_condition_attested' in payload:
        out['same_condition_attested'] = bool(payload['same_condition_attested'])
    return out


def save_draft(doctor_id, rx_id, payload, row_version):
    """Replace the editable fields and the items wholesale. 409 stale_draft when row_version no longer matches."""
    rx = own_rx(doctor_id, rx_id)
    if rx.status != 'draft':
        raise ServiceError('not_draft', 409)
    fields = _fields(payload)
    items = _items(payload['items']) if 'items' in payload else None
    if not cas(Prescription, (Prescription.id == rx_id, Prescription.provider_id == doctor_id,
                              Prescription.status == 'draft', Prescription.row_version == row_version),
               row_version=Prescription.row_version + 1):
        db.session.refresh(rx)
        raise ServiceError('not_draft' if rx.status != 'draft' else 'stale_draft', 409)
    db.session.refresh(rx)
    for key, value in fields.items():
        setattr(rx, key, value)
    if items is not None:
        PrescriptionItem.query.filter_by(prescription_id=rx_id).delete()
        db.session.expire(rx, ['items'])
        db.session.flush()
        rx.items = [PrescriptionItem(**it) for it in items]
    db.session.flush()
    return rx


def delete_draft(doctor_id, rx_id):
    rx = own_rx(doctor_id, rx_id)
    if rx.status != 'draft':
        raise ServiceError('not_draft', 409)
    patient_id = rx.patient_id
    db.session.delete(rx)
    db.session.flush()
    audit(doctor_id, 'rx_draft_delete', 'prescription', rx_id, patient_id=patient_id)
