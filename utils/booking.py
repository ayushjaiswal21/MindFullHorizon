"""Helpers for the patient appointment form: who can be booked, modality, e-prescription consent (design 1.6, 3.6).

Kept out of routes/patient.py so that file does not grow. Counsellor bookings are unchanged: no modality and no
consent. A doctor booking needs video or in person plus an active e-prescription consent (ticked on the form or
given earlier on the prescriptions page).
"""
from core.extensions import db
from utils import rx_text

MODALITIES = ('video', 'in_person')
NEEDS_MODALITY = 'Please choose video or in person for a doctor appointment.'
NEEDS_CONSENT = 'Please agree to receive e-prescriptions, or choose a counsellor instead.'


def staff_options(institution):
    """Counsellors, and verified doctors only, of the patient's institution."""
    from services.roles import bookable_staff
    return bookable_staff(institution)


def erx_active(patient_id):
    from services.consent import erx_status
    return bool(erx_status(patient_id)['active'])


def schedule_context(patient_id, institution):
    """Template context for schedule.html: the bookable staff and the consent state."""
    return {'providers': staff_options(institution), 'erx_active': erx_active(patient_id),
            'erx_text': rx_text.ERX_CONSENT_TEXT}


def booking_extras(provider, form, patient_id):
    """(modality, error) for the chosen staff member. Counsellors give (None, None)."""
    from services.roles import is_doctor
    if provider is None or not is_doctor(provider):
        return None, None
    modality = (form.get('modality') or '').strip()
    if modality not in MODALITIES:
        return None, NEEDS_MODALITY
    if form.get('erx_consent') != 'on' and not erx_active(patient_id):
        return None, NEEDS_CONSENT
    return modality, None


def record_erx_consent(provider, form, patient_id):
    """After a doctor booking was saved: store the consent the patient ticked. Returns True when it was recorded."""
    from services.consent import set_erx_consent
    from services.roles import is_doctor
    if provider is None or not is_doctor(provider) or form.get('erx_consent') != 'on' or erx_active(patient_id):
        return False
    set_erx_consent(patient_id, True)
    db.session.commit()
    return True
