"""JSON shapes of a prescription for each viewer (design 5.5, 5.2). Patient shapes never carry warnings or notes."""
from core.extensions import db
from models import PrescriberProfile, User
from services.http import iso
from services.prescriptions._common import ACTIVE
from services.prescriptions.lifecycle import effective_status


def collection(rx):
    """'none' | 'partial' | 'complete' from the dispensed quantities."""
    items = list(rx.items)
    if not items or not any(i.quantity_dispensed for i in items):
        return 'none'
    return 'complete' if all(i.quantity_dispensed >= i.quantity for i in items) else 'partial'


def _prescriber_status(provider_id, cache):
    if cache is None:
        cache = {}
    if provider_id not in cache:
        p = PrescriberProfile.query.filter_by(user_id=provider_id).first()
        cache[provider_id] = p.status if p else None
    return cache[provider_id]


def dispensable(rx, cache=None, now=None):
    """Live, unexpired, and the prescriber is not suspended or rejected (design 3.8)."""
    return (effective_status(rx, now) in ACTIVE and rx.status in ACTIVE
            and _prescriber_status(rx.provider_id, cache) not in ('suspended', 'rejected'))


def _item(it, ids=False):
    out = {'line_no': it.line_no, 'medicine_id': it.medicine_id, 'medicine_label': it.medicine_label or it.medicine.label,
           'tpg_list': it.tpg_list or it.medicine.tpg_list, 'dose_text': it.dose_text, 'frequency': it.frequency,
           'duration_days': it.duration_days, 'quantity': it.quantity, 'quantity_dispensed': it.quantity_dispensed,
           'instructions': it.instructions}
    if ids:
        out['id'] = it.id
    return out


def _patient_name(rx):
    return rx.patient_name or (rx.patient.name if rx.patient else None)


def serialize(rx, viewer, cache=None):
    """viewer: 'doctor' | 'patient' | 'desk' | 'staff_lines' (a list of item lines for counsellors and other doctors)."""
    eff = effective_status(rx)
    if viewer == 'staff_lines':
        by = rx.doctor_name or (rx.provider.name if rx.provider else None)
        return [{'medicine': i.medicine_label or i.medicine.label, 'dose': i.dose_text, 'frequency': i.frequency,
                 'duration_days': i.duration_days, 'status': eff, 'prescribed_by': by} for i in rx.items]
    base = {'id': rx.id, 'number': rx.number, 'status': rx.status, 'effective_status': eff,
            'issued_at': iso(rx.issue_date), 'valid_until': iso(rx.expiry_date),
            'dispense_requested_at': iso(rx.dispense_requested_at), 'collection': collection(rx),
            'items': [_item(i, viewer != 'patient') for i in rx.items]}
    if viewer == 'patient':
        return base | {
            'doctor_name': rx.doctor_name or (rx.provider.name if rx.provider else None),
            'doctor_reg_no': rx.doctor_reg_no, 'institution': rx.institution_name,
            'dispensable': dispensable(rx, cache), 'diagnosis': rx.diagnosis, 'allergies_status': rx.allergies_status,
            'allergies': rx.allergies, 'current_meds_status': rx.current_meds_status, 'current_meds': rx.current_meds}
    full = base | {
        'row_version': rx.row_version, 'patient': {'id': rx.patient_id, 'name': _patient_name(rx)},
        'consult_appointment_id': rx.consult_appointment_id, 'tpg_context': rx.tpg_context,
        'same_condition_attested': rx.same_condition_attested, 'diagnosis': rx.diagnosis,
        'allergies_status': rx.allergies_status, 'allergies': rx.allergies,
        'current_meds_status': rx.current_meds_status, 'current_meds': rx.current_meds,
        'expiry_days': rx.expiry_days, 'amends_id': rx.amends_id, 'cancel_reason': rx.cancel_reason,
        'patient_name': _patient_name(rx), 'doctor_name': rx.doctor_name, 'doctor_reg_no': rx.doctor_reg_no,
        'doctor_council': rx.doctor_council, 'doctor_specialisation': rx.doctor_specialisation,
        'institution': rx.institution_name, 'dispensable': dispensable(rx, cache)}
    if rx.consult_appointment_id:
        from models import Appointment
        a = db.session.get(Appointment, rx.consult_appointment_id)
        full['consult_started_at'] = iso(a.consult_started_at) if a else None
    return full
