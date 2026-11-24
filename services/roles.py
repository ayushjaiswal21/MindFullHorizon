"""Roles, provider types and institution keys (design 1.1, 1.4)."""
import re

ROLES = ('patient', 'provider', 'admin')
_HOME = {'patient': 'patient.patient_dashboard', 'admin': 'admin.dashboard'}


def home_endpoint(role):
    return _HOME.get(role, 'provider.provider_dashboard')


def norm_inst(name):
    """lower, strip, collapse whitespace; '' for empty."""
    return re.sub(r'\s+', ' ', (name or '').strip().lower())


def same_inst(a, b):
    return bool(norm_inst(a)) and norm_inst(a) == norm_inst(b)


def provider_type_of(user):
    if user is None or user.role != 'provider':
        return None
    return user.provider_type or 'counsellor'


def is_doctor(user):
    return provider_type_of(user) == 'doctor'


def bookable_staff(institution):
    """Providers a patient may book: counsellors, and doctors only while verified. Same institution only."""
    from sqlalchemy import func
    from models import PrescriberProfile, User
    from services.prescriber import is_verified
    key = norm_inst(institution)
    if not key:
        return []
    rows = (User.query.filter(User.role == 'provider', User.deactivated_at.is_(None),
                              func.lower(func.trim(User.institution)) == key).order_by(User.name).all())
    doctor_ids = [u.id for u in rows if u.provider_type == 'doctor']
    profiles = {p.user_id: p for p in PrescriberProfile.query.filter(PrescriberProfile.user_id.in_(doctor_ids or [0]))}
    return [u for u in rows if u.provider_type != 'doctor' or is_verified(profiles.get(u.id))]
