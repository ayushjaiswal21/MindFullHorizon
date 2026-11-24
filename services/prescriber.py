"""Prescriber verification (design 2). A person at the institution checks the registration; the app cannot query the NMC.

Functions flush and write their AuditLog rows in the caller's transaction; the route (or CLI) commits.
Every admin-side function treats a profile of another institution as not found (404), so existence does not leak.
"""
import re
from datetime import timedelta

from extensions import db
from models import PrescriberProfile, User
from services import config
from services.db_util import cas, for_update, inst_match
from services.errors import ServiceError
from services.roles import norm_inst, same_inst
from utils.audit import audit
from utils.pagination import page_meta
from utils.timeutil import ist_today, utcnow

CHECK_KEYS = ('register_found', 'details_match', 'not_removed', 'modern_medicine', 'works_here')
_REG_RE = re.compile(r'[A-Za-z0-9/\-]{4,20}')
LIVE = ('pending', 'verified', 'suspended')


def _clean(value, limit):
    return re.sub(r'[\x00-\x1f\x7f]', '', ' '.join((value or '').split()))[:limit + 1]


def _validate(registration_number, council, registered_since, specialisation):
    reg = ''.join((registration_number or '').split()).upper()
    council, spec = _clean(council, 100), _clean(specialisation, 100)
    errors = {}
    if not _REG_RE.fullmatch(reg):
        errors['registration_number'] = 'Use 4 to 20 letters, digits, / or -.'
    if not 3 <= len(council) <= 100:
        errors['council'] = 'Enter the council as the register shows it (3 to 100 characters).'
    try:
        year = int(registered_since)
        if not 1950 <= year <= ist_today().year:
            raise ValueError
    except (TypeError, ValueError):
        year = None
        errors['registered_since'] = f'Enter a year from 1950 to {ist_today().year}.'
    if len(spec) > 100:
        errors['specialisation'] = 'At most 100 characters.'
    if errors:
        raise ServiceError('validation', 422, fields=errors)
    return reg, council, year, spec or None


def _duplicate(reg, council_key, user_id):
    return PrescriberProfile.query.filter(
        PrescriberProfile.registration_number == reg, PrescriberProfile.council_key == council_key,
        PrescriberProfile.status.in_(LIVE), PrescriberProfile.user_id != user_id).first() is not None


def submit_profile(user_id, registration_number, council, registered_since, specialisation=None):
    """Create the profile (pending) or let the doctor edit it. Identity edits send pending/verified back to pending."""
    reg, council, year, spec = _validate(registration_number, council, registered_since, specialisation)
    key = norm_inst(council)
    if _duplicate(reg, key, user_id):
        raise ServiceError('registration_in_use', 409, fields={'registration_number': 'Already in use.'})
    now = utcnow()
    p = PrescriberProfile.query.filter_by(user_id=user_id).first()
    if p is None:
        p = PrescriberProfile(user_id=user_id, registration_number=reg, council=council, council_key=key,
                              registered_since=year, specialisation=spec, status='pending', submitted_at=now,
                              status_changed_at=now)
        db.session.add(p)
        db.session.flush()
        audit(user_id, 'prescriber_submit', 'prescriber_profile', p.id, to='pending')
        return p
    changed = (p.registration_number, p.council_key, p.registered_since) != (reg, key, year)
    old = p.status
    p.registration_number, p.council, p.council_key, p.registered_since, p.specialisation = reg, council, key, year, spec
    if old == 'rejected':
        _to_pending(p, now)
        audit(user_id, 'prescriber_submit', 'prescriber_profile', p.id, **{'from': old, 'to': 'pending'})
    elif changed and old in ('pending', 'verified'):
        _to_pending(p, now)
        audit(user_id, 'prescriber_edit_reset', 'prescriber_profile', p.id, **{'from': old, 'to': 'pending'})
    db.session.flush()
    return p


def _to_pending(p, now):
    p.status, p.submitted_at, p.status_changed_at = 'pending', now, now
    p.verified_at = p.review_due_at = p.verified_by = None


def get_profile(user_id):
    return PrescriberProfile.query.filter_by(user_id=user_id).first()


def is_verified(profile, now=None):
    return bool(profile and profile.status == 'verified' and profile.review_due_at
                and profile.review_due_at > (now or utcnow()))


def state_of(profile, now=None):
    """'pending' | 'verified' | 'rejected' | 'suspended' | 'lapsed' (verified but past its review date)."""
    if profile is None:
        return 'pending'
    if profile.status == 'verified' and not is_verified(profile, now):
        return 'lapsed'
    return profile.status


def require_verified(user_id, lock=False):
    """The doctor's profile if verified and in date, else ServiceError('prescriber_not_verified', 403)."""
    q = PrescriberProfile.query.filter_by(user_id=user_id)
    p = (for_update(q) if lock else q).first()
    user = db.session.get(User, user_id)
    if not (is_verified(p) and user and user.role == 'provider' and user.provider_type == 'doctor'
            and user.deactivated_at is None):
        raise ServiceError('prescriber_not_verified', 403)
    return p


# ---------- admin decisions ----------

def _admin_and_profile(profile_id, admin_id):
    admin = db.session.get(User, admin_id)
    p = db.session.get(PrescriberProfile, profile_id)
    doctor = db.session.get(User, p.user_id) if p else None
    if not (admin and admin.role == 'admin' and admin.deactivated_at is None and doctor
            and same_inst(admin.institution, doctor.institution)):
        raise ServiceError('not_found', 404)
    return p


def _note(note):
    note = _clean(note, 500)
    if not 10 <= len(note) <= 500:
        raise ServiceError('note_required', 422, fields={'note': 'Write 10 to 500 characters.'})
    return note


def _checks(checks):
    if not isinstance(checks, dict) or not all(checks.get(k) is True for k in CHECK_KEYS):
        raise ServiceError('checks_incomplete', 422)


def _move(profile_id, admin_id, allowed_from, to, note, audit_action, checks=None, need_checks=False):
    p = _admin_and_profile(profile_id, admin_id)
    if need_checks:
        _checks(checks)
    note = _note(note)
    if p.status not in allowed_from:
        raise ServiceError('bad_transition', 409)
    now, old = utcnow(), p.status
    values = dict(status=to, notes=note, verified_by=admin_id, status_changed_at=now)
    if to == 'verified':
        values.update(verified_at=now, review_due_at=now + timedelta(days=config.review_days()))
    else:
        values.update(verified_at=None, review_due_at=None)
    if not cas(PrescriberProfile, (PrescriberProfile.id == profile_id, PrescriberProfile.status == old), **values):
        raise ServiceError('bad_transition', 409)
    db.session.refresh(p)
    audit(admin_id, audit_action, 'prescriber_profile', p.id, **{'from': old, 'to': to})
    return p


def get_for_admin(profile_id, admin_id):
    """(profile, doctor User) if the admin may see it (same institution), else ServiceError 404."""
    p = _admin_and_profile(profile_id, admin_id)
    return p, db.session.get(User, p.user_id)


def verify(profile_id, admin_id, checks, note):
    """pending -> verified. A verified profile that is lapsed or due within 30 days can be re-checked the same way."""
    p = _admin_and_profile(profile_id, admin_id)
    recheck = p.status == 'verified' and p.review_due_at and p.review_due_at <= utcnow() + timedelta(days=30)
    return _move(profile_id, admin_id, ('pending', 'verified') if recheck else ('pending',), 'verified', note,
                 'prescriber_verify', checks, True)


def allowed_actions(p):
    """Action names the verification screen offers for this profile."""
    if p.status == 'pending':
        return ['verify', 'reject']
    if p.status == 'suspended':
        return ['reinstate']
    if p.status == 'verified':
        due = p.review_due_at and p.review_due_at <= utcnow() + timedelta(days=30)
        return (['verify'] if due else []) + ['suspend']
    return []


def reject(profile_id, admin_id, note):
    return _move(profile_id, admin_id, ('pending',), 'rejected', note, 'prescriber_reject')


def suspend(profile_id, admin_id, note):
    return _move(profile_id, admin_id, ('verified',), 'suspended', note, 'prescriber_suspend')


def reinstate(profile_id, admin_id, checks, note):
    return _move(profile_id, admin_id, ('suspended',), 'verified', note, 'prescriber_reinstate', checks, True)


def item(p, user, include_notes=False):
    """VerificationItem (design 5.5)."""
    iso = lambda v: v.isoformat() + 'Z' if v else None
    out = {'id': p.id, 'user_name': user.name, 'email': user.email, 'registration_number': p.registration_number,
           'council': p.council, 'registered_since': p.registered_since, 'specialisation': p.specialisation,
           'status': p.status, 'state': state_of(p), 'submitted_at': iso(p.submitted_at),
           'review_due_at': iso(p.review_due_at)}
    if include_notes:
        verifier = db.session.get(User, p.verified_by) if p.verified_by else None
        out.update(notes=p.notes, verified_by_name=verifier.name if verifier else None, verified_at=iso(p.verified_at))
    return out


def counts(institution_key):
    """{'pending': n, ...} for the verification tabs."""
    rows = (db.session.query(PrescriberProfile.status, db.func.count(PrescriberProfile.id))
            .join(User, User.id == PrescriberProfile.user_id).filter(inst_match(User.institution, institution_key))
            .group_by(PrescriberProfile.status).all())
    return {s: 0 for s in ('pending', 'verified', 'suspended', 'rejected')} | dict(rows)


def queue(institution_key, status=None, page=1, per_page=20):
    """(rows, meta) of VerificationItems for one institution, oldest submission first."""
    q = (db.session.query(PrescriberProfile, User).join(User, User.id == PrescriberProfile.user_id)
         .filter(inst_match(User.institution, institution_key)))
    if status:
        q = q.filter(PrescriberProfile.status == status)
    total = q.count()
    rows = q.order_by(PrescriberProfile.submitted_at, PrescriberProfile.id).limit(per_page).offset((page - 1) * per_page).all()
    return [item(p, u) for p, u in rows], page_meta(page, per_page, total)


def review_due_count(institution_key, within_days=30, now=None):
    """Verified profiles whose review date is within `within_days` or already past."""
    now = now or utcnow()
    return (db.session.query(db.func.count(PrescriberProfile.id)).join(User, User.id == PrescriberProfile.user_id)
            .filter(inst_match(User.institution, institution_key), PrescriberProfile.status == 'verified',
                    PrescriberProfile.review_due_at <= now + timedelta(days=within_days)).scalar() or 0)
