"""Desk-side lookups and views of a prescription (design 4.6). No list of all prescriptions exists, only the queue
of prescriptions the patient chose to send and a lookup by number."""
from extensions import db
from models import PrescriberProfile, Prescription
from services.errors import ServiceError
from services.http import iso
from utils.rx_numbers import is_valid_number, normalise
from utils.timeutil import utcnow

DISPENSABLE = ('issued', 'partially_dispensed')


def initials(name):
    """'Asha Sharma' -> 'A. S.' (first letters of the first and last name only)."""
    parts = (name or '').split()
    return ' '.join(f'{p[0].upper()}.' for p in ([parts[0], parts[-1]] if len(parts) > 1 else parts[:1]))


def effective_status(rx, now=None):
    if rx.status in DISPENSABLE and rx.expiry_date and rx.expiry_date <= (now or utcnow()):
        return 'expired'
    return rx.status


def prescriber_blocked(rx):
    """True when the issuing doctor is suspended or rejected (design 3.8): dispensing is blocked."""
    p = PrescriberProfile.query.filter_by(user_id=rx.provider_id).first()
    return bool(p and p.status in ('suspended', 'rejected'))


def get_for_desk(rx_id, institution_key):
    """The prescription if it exists, is not a draft and belongs to the desk's institution; else 404."""
    rx = db.session.get(Prescription, rx_id)
    if rx is None or rx.institution_key != institution_key or rx.status == 'draft':
        raise ServiceError('not_found', 404)
    return rx


def lookup(number, institution_key):
    """Find by prescription number. A bad check character is 422 (helps the desk catch typos); unknown numbers and
    numbers of other institutions are the same 404."""
    if not is_valid_number(number):
        raise ServiceError('bad_number', 422)
    rx = Prescription.query.filter(Prescription.number == normalise(number), Prescription.institution_key == institution_key,
                                   Prescription.status != 'draft').first()
    if rx is None:
        raise ServiceError('not_found', 404)
    return rx


def queue(institution_key, now=None):
    """Prescriptions of this institution that the patient sent to the desk, oldest request first. Initials only."""
    now = now or utcnow()
    rows = (Prescription.query.filter(Prescription.institution_key == institution_key, Prescription.status.in_(DISPENSABLE),
                                      Prescription.dispense_requested_at.isnot(None), Prescription.expiry_date > now)
            .order_by(Prescription.dispense_requested_at, Prescription.id).all())
    return [{'rx_id': r.id, 'number': r.number, 'initials': initials(r.patient_name), 'items': len(r.items),
             'requested_at': iso(r.dispense_requested_at)} for r in rows]


def in_queue(rx):
    return bool(rx.dispense_requested_at and rx.status in DISPENSABLE)


def rx_view(rx, now=None):
    """Full content for the desk (patient name allowed here by design 1.7: the looked-up or sent prescription only)."""
    return {'id': rx.id, 'number': rx.number, 'status': rx.status, 'effective_status': effective_status(rx, now),
            'patient_name': rx.patient_name, 'doctor_name': rx.doctor_name, 'doctor_reg_no': rx.doctor_reg_no,
            'institution': rx.institution_name, 'issued_at': iso(rx.issue_date), 'valid_until': iso(rx.expiry_date),
            'dispense_requested_at': iso(rx.dispense_requested_at), 'prescriber_blocked': prescriber_blocked(rx),
            'items': [{'item_id': i.id, 'medicine_label': i.medicine_label, 'dose_text': i.dose_text,
                       'frequency': i.frequency, 'duration_days': i.duration_days, 'quantity': i.quantity,
                       'quantity_dispensed': i.quantity_dispensed, 'remaining': i.quantity - i.quantity_dispensed,
                       'instructions': i.instructions} for i in rx.items]}
