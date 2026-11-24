"""Dry-run validation and the duplicate-therapy warnings (design 3.5). No state change.

This finds the same medicine or the same class only. It is NOT a drug interaction check and is never described as one.
"""
from collections import namedtuple
from dataclasses import dataclass, field

from extensions import db
from models import Medication, Prescription, PrescriptionItem, User
from services import prescriber
from services.errors import ServiceError
from services.prescriptions._common import ACTIVE, assigned_patient, own_rx
from services.prescriptions.eligibility import consult_eligibility
from services.rx_rules import WARNING_TEXT, check_limits, error, medicine_block_code
from utils.timeutil import utcnow

Warn = namedtuple('Warn', 'code item_id text_key')  # item_id is the 1-based line_no, None when it is about the whole rx


@dataclass
class ValidationResult:
    ok: bool = True
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


def warning_dict(w):
    return {'code': w.code, 'item': w.item_id, 'message': WARNING_TEXT[w.text_key]}


def _active_other_items(rx):
    """Items of the patient's other live prescriptions (excluding the one this draft amends)."""
    q = (db.session.query(PrescriptionItem).join(Prescription, Prescription.id == PrescriptionItem.prescription_id)
         .filter(Prescription.patient_id == rx.patient_id, Prescription.status.in_(ACTIVE),
                 Prescription.expiry_date > utcnow(), Prescription.id != rx.id))
    if rx.amends_id:
        q = q.filter(Prescription.id != rx.amends_id)
    return q.all()


def _mentions(text, med):
    text = (text or '').lower()
    return any(len(n) >= 3 and n in text for n in (med.generic_key, (med.brand_name or '').lower()))


def warnings(rx):
    """Duplicate-therapy and text-match warnings for the draft `rx` (list of Warn)."""
    out, items = [], list(rx.items)
    others = _active_other_items(rx)
    self_logged = [m.name.lower() for m in Medication.query.filter_by(user_id=rx.patient_id, is_active=True)]
    for it in items:
        med = it.medicine
        if any(o.medicine.generic_key == med.generic_key for o in others):
            out.append(Warn('dup_active_rx', it.line_no, 'dup_active_rx'))
        cls = med.therapeutic_class
        if cls and (any(o.medicine.therapeutic_class == cls and o.medicine.generic_key != med.generic_key for o in others)
                    or any(x.line_no < it.line_no and x.medicine.therapeutic_class == cls
                           and x.medicine.generic_key != med.generic_key for x in items)):
            out.append(Warn('dup_class', it.line_no, 'dup_class'))
        if len(med.generic_key) >= 4 and any(med.generic_key in n for n in self_logged):
            out.append(Warn('dup_self_logged', it.line_no, 'dup_self_logged'))
        if rx.allergies_status == 'listed' and _mentions(rx.allergies, med):
            out.append(Warn('allergy_text_match', it.line_no, 'allergy_text_match'))
        if rx.current_meds_status == 'listed' and _mentions(rx.current_meds, med):
            out.append(Warn('current_meds_text_match', it.line_no, 'current_meds_text_match'))
    return out


def collect(rx, doctor):
    """(errors, warnings, eligibility) for a draft; shared by validate() and issue()."""
    errors = []
    if assigned_patient(doctor, rx.patient_id) is None:
        errors.append(error('patient_not_assigned'))
    el = consult_eligibility(doctor.id, rx.patient_id, rx.same_condition_attested)
    errors += [error(code) for code in el.blockers]
    if not rx.diagnosis:
        errors.append(error('field_required', field='diagnosis'))
    for status, text, name in ((rx.allergies_status, rx.allergies, 'allergies'),
                               (rx.current_meds_status, rx.current_meds, 'current_meds')):
        if status is None:
            errors.append(error('field_required', field=name + '_status'))
        elif status == 'listed' and not text:
            errors.append(error('field_required', field=name))
    items = list(rx.items)
    if not items:
        errors.append(error('no_items'))
    for it in items:
        code = medicine_block_code(it.medicine, el.allowed_lists)
        if code:
            errors.append(error(code, item=it.line_no))
        for name in ('dose_text', 'frequency'):
            if not getattr(it, name):
                errors.append(error('field_required', item=it.line_no, field=name))
    errors += check_limits(items, el.tpg_context)
    return errors, warnings(rx), el


def validate(doctor_id, rx_id):
    rx = own_rx(doctor_id, rx_id)
    if rx.status != 'draft':
        raise ServiceError('not_draft', 409)
    prescriber.require_verified(doctor_id)
    errors, warns, _ = collect(rx, db.session.get(User, doctor_id))
    return ValidationResult(ok=not errors, errors=errors, warnings=[warning_dict(w) for w in warns])
