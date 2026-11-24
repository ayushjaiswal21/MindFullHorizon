"""Lists and single reads for doctors, patients and staff, and the public status check (design 3.9, 5.2, 5.3)."""
from sqlalchemy import and_, or_
from sqlalchemy.orm import selectinload

from extensions import db
from models import Medication, Prescription, User
from services.errors import ServiceError
from services.http import iso
from services.prescriptions._common import ACTIVE, CLOSED
from services.prescriptions.lifecycle import effective_status
from services.prescriptions.serialize import collection, serialize
from utils.pagination import page_meta
from utils.rx_numbers import is_valid_number, normalise
from utils.timeutil import utcnow


def _live(now):
    return and_(Prescription.status.in_(ACTIVE), Prescription.expiry_date > now)


def _ended(now):
    return or_(Prescription.status.in_(CLOSED + ('legacy',)),
               and_(Prescription.status.in_(ACTIVE), Prescription.expiry_date <= now))


def _page(query, page, per_page):
    total = query.count()
    rows = query.options(selectinload(Prescription.items)).limit(per_page).offset((page - 1) * per_page).all()
    return rows, page_meta(page, per_page, total)


def list_for_doctor(doctor_id, bucket, q=None, page=1, per_page=20):
    """RxListItem dicts (design 5.5). bucket: 'draft' | 'issued' | 'closed'. q: a prescription number."""
    now = utcnow()
    query = Prescription.query.filter(Prescription.provider_id == doctor_id)
    if bucket == 'draft':
        query = query.filter(Prescription.status == 'draft')
    elif bucket == 'issued':
        query = query.filter(_live(now))
    else:
        query = query.filter(_ended(now), Prescription.status != 'legacy')
    if q:
        query = query.filter(Prescription.number == normalise(q))
    rows, meta = _page(query.order_by(Prescription.updated_at.desc(), Prescription.id.desc()), page, per_page)
    names = dict(db.session.query(User.id, User.name).filter(User.id.in_({r.patient_id for r in rows} or {0})))
    return [{'id': r.id, 'number': r.number, 'status': effective_status(r, now),
             'patient_name': r.patient_name or names.get(r.patient_id), 'issued_at': iso(r.issue_date),
             'valid_until': iso(r.expiry_date), 'items': len(r.items), 'collection': collection(r),
             'updated_at': iso(r.updated_at)} for r in rows], meta


def list_for_patient(patient_id, bucket, page=1, per_page=10):
    """PatientRx dicts, never drafts. bucket 'active' (live) or 'past' (dispensed, cancelled, expired, legacy)."""
    now = utcnow()
    query = Prescription.query.filter(Prescription.patient_id == patient_id, Prescription.status != 'draft')
    query = query.filter(_live(now) if bucket == 'active' else _ended(now))
    rows, meta = _page(query.order_by(Prescription.issue_date.desc(), Prescription.id.desc()), page, per_page)
    cache = {}
    return [serialize(r, 'patient', cache) for r in rows], meta


def get_for_patient(patient_id, rx_id):
    rx = Prescription.query.filter_by(id=rx_id, patient_id=patient_id).first()
    if rx is None or rx.status == 'draft':
        raise ServiceError('not_found', 404)
    return serialize(rx, 'patient')


def request_pharmacy(patient_id, rx_id, now=None):
    """Mark the prescription as sent to the pharmacy desk (first request wins; a repeat changes nothing)."""
    now = now or utcnow()
    rx = Prescription.query.filter_by(id=rx_id, patient_id=patient_id).first()
    if rx is None or rx.status == 'draft':
        raise ServiceError('not_found', 404)
    if rx.status not in ACTIVE or effective_status(rx, now) != rx.status:
        raise ServiceError('not_sendable', 409)
    if rx.dispense_requested_at is None:
        rx.dispense_requested_at = now
        db.session.flush()
    return rx


def active_rx_patient_ids(patient_ids):
    ids = list(patient_ids or ())
    if not ids:
        return set()
    rows = db.session.query(Prescription.patient_id).filter(
        Prescription.patient_id.in_(ids), _live(utcnow())).distinct().all()
    return {r[0] for r in rows}


def medication_lines_for_staff(patient_id):
    """Item lines only (no diagnosis, allergies or number) for the counsellor and doctor medicines panel."""
    meds = [{'name': m.name, 'dosage': m.dosage, 'frequency': m.frequency}
            for m in Medication.query.filter_by(user_id=patient_id, is_active=True).order_by(Medication.name)]
    rxs = (Prescription.query.filter(Prescription.patient_id == patient_id, _live(utcnow()))
           .options(selectinload(Prescription.items)).order_by(Prescription.issue_date.desc()).all())
    return {'self_logged': meds, 'prescriptions': [line for r in rxs for line in serialize(r, 'staff_lines')]}


def public_status(number):
    """Minimal public check: status, issue date, doctor and institution only. None for unknown or malformed numbers."""
    if not is_valid_number(number):
        return None
    rx = Prescription.query.filter_by(number=normalise(number)).first()
    if rx is None or rx.status in ('draft', 'legacy'):
        return None
    eff = effective_status(rx)
    return {'status': 'valid' if eff == 'issued' else eff, 'issued_at': iso(rx.issue_date),
            'doctor_name': rx.doctor_name, 'doctor_reg_no': rx.doctor_reg_no, 'institution': rx.institution_name}
