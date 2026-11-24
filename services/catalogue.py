"""Medicine catalogue (design 4.1, 4.12). List and schedule are DATA that a second administrator confirms.

Functions flush and audit in the caller's transaction; the route commits. Audit meta holds field names only.
"""
import re

from sqlalchemy import or_

from extensions import db
from models import Medicine
from services import config
from services.errors import ServiceError
from utils.audit import audit
from utils.pagination import page_meta
from utils.timeutil import utcnow

LISTS = ('O', 'A', 'B', 'C')
SCHEDULES = ('none', 'H', 'H1', 'X', 'NDPS')
CLASS_FIELDS = ('tpg_list', 'schedule', 'is_controlled')  # a change here clears the second-admin confirmation
TEXT_LIMITS = {'generic_name': 120, 'brand_name': 120, 'strength': 40, 'form': 30, 'route': 20, 'therapeutic_class': 60}


def clean(value, limit):
    """Strip, collapse whitespace, drop control characters. Cut at limit + 1 so a caller can detect 'too long'."""
    return re.sub(r'[\x00-\x1f\x7f]', '', ' '.join(str(value if value is not None else '').split()))[:limit + 1]


def to_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if value in (None, ''):
        return default
    return str(value).strip().lower() in ('1', 'true', 'yes', 'on')


def normalise(data, partial_of=None):
    """Validated field dict from a client dict. `partial_of` is a Medicine whose values fill what the client left out."""
    out, errors = {}, {}
    for name, limit in TEXT_LIMITS.items():
        if name not in data and partial_of is not None:
            out[name] = getattr(partial_of, name)
            continue
        out[name] = clean(data.get(name), limit)
        if len(out[name]) > limit:
            errors[name] = 'Too long.'
    for name in ('generic_name', 'strength', 'form'):
        if not out.get(name):
            errors.setdefault(name, 'Required.')
    out['route'] = out.get('route') or 'oral'
    out['brand_name'] = out.get('brand_name') or ''
    out['therapeutic_class'] = out.get('therapeutic_class') or None
    base = partial_of
    out['tpg_list'] = (str(data['tpg_list']).strip().upper() if data.get('tpg_list') not in (None, '')
                       else (base.tpg_list if base else 'C'))  # unknown means C: blocked
    out['schedule'] = (str(data['schedule']).strip() if data.get('schedule') not in (None, '')
                       else (base.schedule if base else 'none'))
    if out['tpg_list'] not in LISTS:
        errors['tpg_list'] = 'Choose O, A, B or C.'
    if out['schedule'].upper() in ('X', 'NDPS', 'H', 'H1'):
        out['schedule'] = out['schedule'].upper()
    if out['schedule'] not in SCHEDULES:
        errors['schedule'] = 'Choose none, H, H1, X or NDPS.'
    out['is_controlled'] = (out['schedule'] in ('X', 'NDPS')) or to_bool(
        data.get('is_controlled'), base.is_controlled if base else False)
    out['active'] = to_bool(data.get('active'), base.active if base else True)
    if errors:
        raise ServiceError('validation', 422, fields=errors)
    out['generic_key'] = clean(out['generic_name'], 120).lower()
    return out


def _duplicate(fields, ignore_id=None):
    q = Medicine.query.filter_by(generic_key=fields['generic_key'], brand_name=fields['brand_name'],
                                 strength=fields['strength'], form=fields['form'])
    if ignore_id:
        q = q.filter(Medicine.id != ignore_id)
    if q.first():
        raise ServiceError('conflict', 409, fields={'generic_name': 'This medicine already exists.'})


def get(medicine_id):
    m = db.session.get(Medicine, medicine_id)
    if m is None:
        raise ServiceError('not_found', 404)
    return m


def create(admin_id, data):
    f = normalise(data)
    _duplicate(f)
    now = utcnow()
    m = Medicine(**f, is_demo=False, list_verified_at=None, list_verified_by=None, created_by=admin_id,
                 updated_by=admin_id, created_at=now)
    db.session.add(m)
    db.session.flush()
    audit(admin_id, 'medicine_create', 'medicine', m.id)
    return m


def update(admin_id, medicine_id, data):
    m = get(medicine_id)
    f = normalise(data, partial_of=m)
    _duplicate(f, ignore_id=m.id)
    changed = [k for k in f if k != 'generic_key' and getattr(m, k) != f[k]]
    for k, v in f.items():
        setattr(m, k, v)
    if any(k in CLASS_FIELDS for k in changed):
        m.list_verified_at = m.list_verified_by = None
        m.updated_by = admin_id
    db.session.flush()
    audit(admin_id, 'medicine_edit', 'medicine', m.id, fields=changed)
    return m


def set_active(admin_id, medicine_id, on):
    m = get(medicine_id)
    if m.active != bool(on):
        m.active = bool(on)
        db.session.flush()
        audit(admin_id, 'medicine_activate' if on else 'medicine_deactivate', 'medicine', m.id)
    return m


def can_verify(m, admin_id):
    return m.list_verified_at is None and (not config.four_eyes() or m.updated_by != admin_id)


def verify_list(admin_id, medicine_id):
    """Confirm tpg_list, schedule and is_controlled. With four-eyes on, the last editor cannot confirm their own edit."""
    m = get(medicine_id)
    if config.four_eyes() and m.updated_by == admin_id:
        raise ServiceError('second_admin_required', 409)
    m.list_verified_at, m.list_verified_by = utcnow(), admin_id
    db.session.flush()
    audit(admin_id, 'medicine_list_verify', 'medicine', m.id)
    return m


def serialize(m, me_id=None):
    return {'id': m.id, 'label': m.label, 'generic_name': m.generic_name, 'brand_name': m.brand_name,
            'strength': m.strength, 'form': m.form, 'route': m.route, 'tpg_list': m.tpg_list, 'schedule': m.schedule,
            'is_controlled': m.is_controlled, 'therapeutic_class': m.therapeutic_class, 'active': m.active,
            'is_demo': m.is_demo, 'verified': m.list_verified_at is not None,
            'needs_second_check': m.list_verified_at is None,
            'can_verify': can_verify(m, me_id) if me_id else False}


def search(q=None, tpg_list=None, verified=None, active=None, page=1, per_page=20, me_id=None):
    """(rows, meta) of serialised medicines. `verified` and `active` are 'yes'/'no'/None."""
    query = Medicine.query
    if q:
        like = clean(q, 60).lower()
        query = query.filter(or_(Medicine.generic_key.contains(like, autoescape=True),
                                 db.func.lower(Medicine.brand_name).contains(like, autoescape=True)))
    if tpg_list in LISTS:
        query = query.filter(Medicine.tpg_list == tpg_list)
    if verified in ('yes', 'no'):
        query = query.filter(Medicine.list_verified_at.isnot(None) if verified == 'yes' else Medicine.list_verified_at.is_(None))
    if active in ('yes', 'no'):
        query = query.filter(Medicine.active.is_(active == 'yes'))
    total = query.count()
    rows = query.order_by(Medicine.generic_key, Medicine.strength, Medicine.id).limit(per_page).offset((page - 1) * per_page).all()
    return [serialize(m, me_id) for m in rows], page_meta(page, per_page, total)
