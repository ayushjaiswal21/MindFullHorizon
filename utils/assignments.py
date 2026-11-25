"""Provider-patient assignment (decision P-02): a provider sees an individual patient only through a ProviderPatient row."""
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import Appointment, ProviderPatient, User


def same_institution(a, b):
    """Case-insensitive exact match of two institution names; an empty name matches nothing."""
    norm = lambda s: (s or '').strip().lower()
    return bool(norm(a)) and norm(a) == norm(b)


def link_provider_patient(provider_id, patient_id, source='appointment'):
    """Idempotently link a provider and a patient of the SAME institution in the caller's transaction.

    Returns True when the link exists afterwards, False when the pair is invalid (wrong roles or different
    institutions). The caller commits.
    """
    provider, patient = db.session.get(User, provider_id), db.session.get(User, patient_id)
    if not (provider and patient and provider.role == 'provider' and patient.role == 'patient'
            and same_institution(provider.institution, patient.institution)):
        return False
    if ProviderPatient.query.filter_by(provider_id=provider_id, patient_id=patient_id).first():
        return True
    try:
        with db.session.begin_nested():  # a concurrent insert hits the unique constraint; the savepoint keeps the outer transaction
            db.session.add(ProviderPatient(provider_id=provider_id, patient_id=patient_id, source=source))
    except IntegrityError:
        pass
    return True


def unlink_if_unrequested(provider_id, patient_id):
    """Drop an 'appointment'-sourced link once no appointment still backs it (O-14: rejecting or cancelling a
    pending request must not leave the provider assigned to a patient they never actually treated). A 'manual'
    link, or one still backed by a pending/accepted/completed appointment, is left alone. The caller commits.
    """
    if provider_id is None:
        return
    link = ProviderPatient.query.filter_by(provider_id=provider_id, patient_id=patient_id, source='appointment').first()
    if not link:
        return
    still_backed = Appointment.query.filter(
        Appointment.provider_id == provider_id, Appointment.user_id == patient_id,
        Appointment.status.in_(('pending', 'accepted', 'booked', 'completed'))).first()
    if not still_backed:
        db.session.delete(link)
