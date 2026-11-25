"""The issue transaction: the only place a prescription becomes real (design 3.7).

Runs in the caller's transaction and flushes; the route commits. Any failure rolls the session back, so the draft
stays a draft, and writes one `rx_issue_blocked` audit row (a code only) in its own short transaction.
"""
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.exc import IntegrityError

from core.extensions import db
from models import AuditLog, Prescription, User
from services import config, prescriber
from services.db_util import cas
from services.errors import MESSAGES, ServiceError
from services.prescriptions._common import own_rx
from services.prescriptions.validate import collect, warning_dict
from utils.audit import audit
from utils.rx_numbers import new_number
from utils.timeutil import ist_day_bounds, to_ist_date, utcnow


@dataclass
class IssueResult:
    prescription: Prescription
    replayed: bool = False


class _Collision(Exception):
    """The random prescription number already exists (unique index); retry the whole transaction."""


def _audit_blocked(doctor_id, rx_id, code):
    try:
        with db.engine.begin() as conn:
            conn.execute(AuditLog.__table__.insert().values(
                actor_id=doctor_id, action='rx_issue_blocked', target_type='prescription', target_id=rx_id,
                meta={'code': code}, created_at=utcnow()))
    except Exception:  # an audit failure must not hide the real error
        pass


def issue(doctor_id, rx_id, issue_key, acknowledged):
    """Issue a draft. Returns IssueResult; a replay of the same key returns the first result with replayed=True."""
    for _ in range(3):  # no SAVEPOINT (utils/jobs.py explains why): a number collision retries the whole transaction
        try:
            return _issue_once(doctor_id, rx_id, issue_key, set(acknowledged or ()))
        except ServiceError as err:
            db.session.rollback()
            if err.code != 'not_found':
                _audit_blocked(doctor_id, rx_id, err.code)
            raise
        except (_Collision, IntegrityError):
            db.session.rollback()
    raise ServiceError('conflict', 409)


def _first_error(errors):
    code = errors[0]['code']
    return ServiceError(code if code in MESSAGES else 'validation', 404 if code == 'patient_not_assigned' else 422,
                        errors=errors)


def _issue_once(doctor_id, rx_id, key, acknowledged):
    now = utcnow()
    replay = Prescription.query.filter_by(provider_id=doctor_id, issue_request_id=key).first()
    if replay:
        if replay.id != rx_id:
            raise ServiceError('conflict', 409)
        return IssueResult(replay, True)
    rx = own_rx(doctor_id, rx_id)
    if rx.status != 'draft':
        raise ServiceError('already_issued' if rx.number else 'not_draft', 409)
    version = rx.row_version
    if not cas(Prescription, (Prescription.id == rx_id, Prescription.provider_id == doctor_id,
                              Prescription.status == 'draft', Prescription.row_version == version),
               status='issued', issue_request_id=key, row_version=version + 1):
        db.session.refresh(rx)
        if rx.issue_request_id == key and rx.status != 'draft':
            return IssueResult(rx, True)
        raise ServiceError('not_draft' if rx.status != 'draft' else 'stale_draft', 409)
    db.session.refresh(rx)
    profile = prescriber.require_verified(doctor_id, lock=True)
    doctor = db.session.get(User, doctor_id)
    errors, warns, el = collect(rx, doctor)
    if errors:
        raise _first_error(errors)
    unacknowledged = [w for w in warns if w.code not in acknowledged]
    if unacknowledged:
        raise ServiceError('warnings_unacknowledged', 409, warnings=[warning_dict(w) for w in unacknowledged])
    if rx.amends_id:
        if not cas(Prescription, (Prescription.id == rx.amends_id, Prescription.provider_id == doctor_id,
                                  Prescription.status == 'issued'),
                   status='cancelled', cancel_reason='amended', cancelled_at=now, cancelled_by=doctor_id):
            raise ServiceError('amended_rx_changed', 409)
        audit(doctor_id, 'rx_cancel', 'prescription', rx.amends_id, reason_code='amended', by='doctor')
    _snapshot(rx, doctor, profile, el, warns, acknowledged, now)
    try:
        db.session.flush()
    except IntegrityError:
        raise _Collision()
    audit(doctor_id, 'rx_issue', 'prescription', rx.id, patient_id=rx.patient_id, items=len(rx.items),
          lists=''.join(sorted({i.tpg_list for i in rx.items})), warnings=sorted({w.code for w in warns}))
    return IssueResult(rx, False)


def _snapshot(rx, doctor, profile, el, warns, acknowledged, now):
    """Copy everything the printout shows, so later changes to profiles or medicines never alter it."""
    days = min(max(rx.expiry_days or config.rx_expiry_days(), 1), config.rx_expiry_days())
    last_day = to_ist_date(now) + timedelta(days=days)
    rx.issue_date, rx.expiry_date = now, ist_day_bounds(last_day)[1] - timedelta(seconds=1)  # end of the IST day
    rx.doctor_name, rx.doctor_reg_no = doctor.name, profile.registration_number
    rx.doctor_council, rx.doctor_specialisation = profile.council, profile.specialisation
    rx.patient_name = db.session.get(User, rx.patient_id).name
    rx.consult_appointment_id, rx.tpg_context = el.consult_appointment_id, el.tpg_context
    rx.consent_version = config.erx_consent_version()
    rx.warnings_ack = sorted({w.code for w in warns} & acknowledged) or None
    rx.number = new_number()
    for it in rx.items:
        it.medicine_label, it.tpg_list = it.medicine.label, it.medicine.tpg_list
