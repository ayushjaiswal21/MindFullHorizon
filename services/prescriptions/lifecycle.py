"""Cancel, amend, expiry (design 3.8). Issued prescriptions are never edited: amending writes a new draft."""
from core.extensions import db
from models import Prescription, PrescriptionItem
from services import prescriber
from services.db_util import cas
from services.errors import ServiceError
from services.prescriptions._common import ACTIVE, own_rx
from utils.audit import audit
from utils.timeutil import utcnow

CANCEL_REASONS = ('error', 'patient_request', 'clinical_change', 'amended', 'system')


def effective_status(rx, now=None):
    """The stored status, except that a live prescription past its expiry instant reads as 'expired'."""
    if rx.status in ACTIVE and rx.expiry_date is not None and rx.expiry_date <= (now or utcnow()):
        return 'expired'
    return rx.status


def expire_due(now=None):
    """Persist 'expired' on live prescriptions past expiry (the nightly job). Returns the row count; caller commits."""
    now = now or utcnow()
    return cas(Prescription, (Prescription.status.in_(ACTIVE), Prescription.expiry_date <= now), status='expired')


def cancel(actor_id, rx_id, reason_code):
    """Cancel an issued or partly dispensed prescription. `actor_id=None` is the system. Dispensed quantities stay."""
    if reason_code not in CANCEL_REASONS:
        raise ServiceError('field_invalid', 422, fields={'reason_code': 'Choose a reason.'})
    where = [Prescription.id == rx_id, Prescription.status.in_(ACTIVE)]
    if actor_id is not None:
        where.append(Prescription.provider_id == actor_id)
    if not cas(Prescription, where, status='cancelled', cancel_reason=reason_code, cancelled_at=utcnow(),
               cancelled_by=actor_id):
        rx = db.session.get(Prescription, rx_id)
        if rx is None or (actor_id is not None and rx.provider_id != actor_id):
            raise ServiceError('not_found', 404)
        raise ServiceError('not_cancellable', 409)
    rx = db.session.get(Prescription, rx_id)
    db.session.refresh(rx)
    audit(actor_id, 'rx_cancel', 'prescription', rx_id, reason_code=reason_code, by='system' if actor_id is None else 'doctor')
    return rx


def amend(doctor_id, rx_id):
    """A new draft copied from an issued prescription (amends_id set). The old one stays issued until the new one issues."""
    prescriber.require_verified(doctor_id)
    old = own_rx(doctor_id, rx_id)
    if old.status != 'issued' or effective_status(old) != 'issued':
        raise ServiceError('not_amendable', 409)
    existing = Prescription.query.filter_by(provider_id=doctor_id, amends_id=old.id, status='draft').first()
    if existing:
        return existing
    new = Prescription(provider_id=doctor_id, patient_id=old.patient_id, status='draft', amends_id=old.id,
                       institution_key=old.institution_key, institution_name=old.institution_name,
                       diagnosis=old.diagnosis, allergies_status=old.allergies_status, allergies=old.allergies,
                       current_meds_status=old.current_meds_status, current_meds=old.current_meds,
                       same_condition_attested=old.same_condition_attested, expiry_days=old.expiry_days)
    db.session.add(new)
    db.session.flush()
    for it in old.items:
        db.session.add(PrescriptionItem(prescription_id=new.id, line_no=it.line_no, medicine_id=it.medicine_id,
                                        dose_text=it.dose_text, frequency=it.frequency, duration_days=it.duration_days,
                                        quantity=it.quantity, instructions=it.instructions))
    db.session.flush()
    db.session.expire(new, ['items'])
    audit(doctor_id, 'rx_amend', 'prescription', new.id, old_id=old.id)
    return new
