"""Safety plan (Stanley-Brown style): form parsing, saving and the read-only view for assigned providers.

The text is sensitive. This module never logs it and never passes it to the AI. Audit rows carry ids only.
"""
import re

from sqlalchemy.exc import IntegrityError

from extensions import db
from models import ProviderPatient, SafetyPlan
from utils import idempotency as idem
from utils.audit import audit

TEXT_FIELDS = (
    ('warning_signs', 'Warning signs',
     'Thoughts, feelings or situations that tell me a crisis may be starting.'),
    ('coping_alone', 'Things I can do on my own',
     'Things that help me calm down or take my mind off it, without needing anyone else.'),
    ('places_people', 'People and places that help me feel better',
     'People I can be around, or places I can go, that lift my mood. I do not have to talk about the problem.'),
    ('professionals', 'Professionals I can contact',
     'My college counsellor or doctor, and any other service I trust. The national helplines are always shown below.'),
    ('safer_surroundings', 'Making my surroundings safer',
     'Steps I can take to put distance between me and anything I could use to hurt myself, or who can help me do that.'),
)
MAX_TEXT, MAX_PEOPLE, MAX_NAME, MAX_PHONE = 1000, 5, 80, 30
PHONE_RE = re.compile(r'[0-9+()\-\s]*')
CTRL_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')


def _clean(value, limit):
    return CTRL_RE.sub('', str(value or '')).replace('\r\n', '\n').strip()[:limit]


def parse_form(form):
    """(values, error). `values` has the five text fields and `help_people`; `error` is a plain message or None."""
    values = {k: _clean(form.get(k), MAX_TEXT) for k, _, _ in TEXT_FIELDS}
    if any(len(str(form.get(k) or '').strip()) > MAX_TEXT for k in values):
        return values, f'Each section can hold up to {MAX_TEXT} characters. Please shorten the longest one.'
    people = []
    for i in range(MAX_PEOPLE):
        name, phone = _clean(form.get(f'person_name_{i}'), MAX_NAME), _clean(form.get(f'person_phone_{i}'), MAX_PHONE)
        if phone and not PHONE_RE.fullmatch(phone):
            return values, 'Phone numbers can contain digits, spaces, + and - only.'
        if name or phone:
            people.append({'name': name, 'phone': phone})
    values['help_people'] = people
    if not people and not any(values[k] for k, _, _ in TEXT_FIELDS):
        return values, 'Write at least one line before saving.'
    return values, None


def get_plan(user_id):
    return SafetyPlan.query.filter_by(user_id=user_id).first()


def save_plan(user_id, values, key=None):
    """Create or update the one plan of this user. Returns (plan, created). Commits."""
    plan = get_plan(user_id)
    if plan is None:
        row = SafetyPlan(user_id=user_id, client_request_id=key, **values)
        try:
            plan, created = idem.add_once(SafetyPlan, row, key)
        except IntegrityError:  # another request created it first: fall through and update it
            db.session.rollback()
            plan, created = get_plan(user_id), False
        if created or plan is None:
            return plan, created
        if key and plan.client_request_id == key:  # a replay of the same create
            return plan, False
    for k, v in values.items():
        setattr(plan, k, v)
    db.session.commit()
    return plan, False


def delete_plan(user_id):
    plan = get_plan(user_id)
    if plan:
        db.session.delete(plan)
        db.session.commit()
    return bool(plan)


def set_sharing(user_id, on):
    plan = get_plan(user_id)
    if plan is None:
        return None
    plan.share_with_counsellors = bool(on)
    audit(user_id, 'safety_plan_share_on' if on else 'safety_plan_share_off', 'safety_plan', plan.id)
    db.session.commit()
    return plan


def link_state(user_id):
    """What the crisis links should say: 'Open my safety plan' when a plan exists, else 'Make a safety plan'."""
    exists = db.session.query(SafetyPlan.id).filter_by(user_id=user_id).first() is not None
    return {'exists': exists, 'label': 'Open my safety plan' if exists else 'Make a safety plan'}


def shared_plan_for_provider(provider_id, patient_id):
    """The patient's plan, read-only, only when the student switched sharing on AND the provider is assigned to the
    student. Audits the read (ids only) and commits. None otherwise."""
    if not db.session.query(ProviderPatient.id).filter_by(provider_id=provider_id, patient_id=patient_id).first():
        return None
    plan = SafetyPlan.query.filter_by(user_id=patient_id, share_with_counsellors=True).first()
    if plan is None:
        return None
    audit(provider_id, 'view_safety_plan', 'safety_plan', plan.id)
    db.session.commit()
    return plan
