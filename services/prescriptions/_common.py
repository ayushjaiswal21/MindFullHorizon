"""Shared helpers for the prescription services: text cleaning, ownership lookups, status groups."""
import re

from core.extensions import db
from models import Prescription, ProviderPatient, User
from services.errors import ServiceError
from services.roles import same_inst

ACTIVE = ('issued', 'partially_dispensed')
CLOSED = ('dispensed', 'cancelled', 'expired')
_CTRL = re.compile(r'[\x00-\x1f\x7f]')


def clean(value, limit, field):
    """Free text: strip, collapse whitespace and control characters, enforce length (422 field_too_long). '' becomes None."""
    if value is None:
        return None
    text = ' '.join(_CTRL.sub(' ', str(value)).split())
    if len(text) > limit:
        raise ServiceError('field_too_long', 422, fields={field: f'At most {limit} characters.'})
    return text or None


def own_rx(doctor_id, rx_id):
    """The prescription if it belongs to this doctor, else 404 (never reveals other doctors' rows)."""
    rx = Prescription.query.filter_by(id=rx_id, provider_id=doctor_id).first()
    if rx is None:
        raise ServiceError('not_found', 404)
    return rx


def assigned_patient(doctor, patient_id):
    """The patient User if this doctor may prescribe for them (role, same institution, ProviderPatient), else None."""
    patient = db.session.get(User, patient_id)
    if not (patient and patient.role == 'patient' and doctor and same_inst(doctor.institution, patient.institution)
            and ProviderPatient.query.filter_by(provider_id=doctor.id, patient_id=patient_id).first()):
        return None
    return patient
