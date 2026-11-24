"""Staff list and (de)activation for institution admins (design 5.4). Providers only; never a patient."""
from sqlalchemy import or_

from extensions import db
from models import PrescriberProfile, User
from services.db_util import inst_match
from services.errors import ServiceError
from services.http import iso
from services.prescriber import state_of
from utils.audit import audit
from utils.pagination import page_meta
from utils.timeutil import utcnow


def staff_page(institution_key, ptype=None, status=None, page=1, per_page=20):
    q = User.query.filter(User.role == 'provider', inst_match(User.institution, institution_key))
    if ptype == 'doctor':
        q = q.filter(User.provider_type == 'doctor')
    elif ptype == 'counsellor':
        q = q.filter(or_(User.provider_type == 'counsellor', User.provider_type.is_(None)))
    if status == 'active':
        q = q.filter(User.deactivated_at.is_(None))
    elif status == 'deactivated':
        q = q.filter(User.deactivated_at.isnot(None))
    total = q.count()
    users = q.order_by(User.name, User.id).limit(per_page).offset((page - 1) * per_page).all()
    profiles = {p.user_id: p for p in PrescriberProfile.query.filter(PrescriberProfile.user_id.in_([u.id for u in users] or [0]))}
    rows = [{'id': u.id, 'name': u.name, 'email': u.email, 'provider_type': u.provider_type or 'counsellor',
             'institution_typed': u.institution, 'created_at': iso(u.created_at), 'deactivated': u.deactivated_at is not None,
             'verification_state': state_of(profiles[u.id]) if u.id in profiles else None} for u in users]
    return rows, page_meta(page, per_page, total)


def set_active(admin_id, user_id, active):
    """Deactivate or reactivate a provider of the admin's institution. Flushes and audits; the route commits."""
    admin, user = db.session.get(User, admin_id), db.session.get(User, user_id)
    if not (admin and user and user.role == 'provider'
            and (admin.institution or '').strip().lower() == (user.institution or '').strip().lower()):
        raise ServiceError('not_found', 404)
    if (user.deactivated_at is None) == bool(active):
        return user  # already in that state
    user.deactivated_at = None if active else utcnow()
    db.session.flush()
    audit(admin_id, 'staff_reactivate' if active else 'staff_deactivate', 'user', user.id)
    return user
