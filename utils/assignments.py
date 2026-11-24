"""Provider-patient assignment (decision P-02): a provider sees an individual patient only through a ProviderPatient row."""
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import ProviderPatient, User


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
