"""The doctor's dashboard widgets (design 5.3, 5.5 Dashboard)."""
from datetime import timedelta

from sqlalchemy import func

from extensions import db
from models import Appointment, Prescription, User
from services import prescriber
from services.http import iso
from services.prescriptions.eligibility import QUALIFYING_MODALITIES
from services.prescriptions.lifecycle import effective_status
from services.prescriptions.reads import list_for_doctor
from utils.timeutil import ist_today, utcnow

OPEN_STATUSES = ('accepted', 'booked')


def _consults_today(doctor_id):
    rows = (db.session.query(Appointment, User.name).join(User, User.id == Appointment.user_id)
            .filter(Appointment.provider_id == doctor_id, Appointment.date == ist_today(),
                    Appointment.status.in_(OPEN_STATUSES + ('completed',)))
            .order_by(Appointment.time, Appointment.id).all())
    out = []
    for a, name in rows:
        open_ = a.status in OPEN_STATUSES
        out.append({'appointment_id': a.id, 'time': a.time, 'patient_name': name, 'modality': a.modality,
                    'status': a.status, 'started': a.consult_started_at is not None,
                    'can_start': open_ and a.modality in QUALIFYING_MODALITIES and a.consult_started_at is None,
                    'can_complete': open_ and a.consult_started_at is not None})
    return out


def doctor_dashboard(doctor_id):
    """Everything in the Dashboard shape of design 5.5 (own appointments and prescriptions only)."""
    profile = prescriber.get_profile(doctor_id)
    drafts, dmeta = list_for_doctor(doctor_id, 'draft', page=1, per_page=5)
    recent = (Prescription.query.filter(Prescription.provider_id == doctor_id, Prescription.number.isnot(None))
              .order_by(Prescription.issue_date.desc()).limit(5).all())
    names = dict(db.session.query(User.id, User.name).filter(User.id.in_({r.patient_id for r in recent} or {0})))
    now = utcnow()
    waiting = (db.session.query(func.count(Prescription.id)).filter(
        Prescription.provider_id == doctor_id, Prescription.status == 'issued', Prescription.expiry_date > now,
        Prescription.issue_date < now - timedelta(days=7)).scalar() or 0)
    return {'success': True, 'state': prescriber.state_of(profile),
            'review_due_at': iso(profile.review_due_at) if profile else None,
            'can_prescribe': prescriber.is_verified(profile), 'consults_today': _consults_today(doctor_id),
            'drafts': [{'id': d['id'], 'patient_name': d['patient_name'], 'updated_at': d['updated_at'],
                        'items': d['items']} for d in drafts], 'drafts_total': dmeta['total'],
            'recent': [{'id': r.id, 'number': r.number, 'patient_name': r.patient_name or names.get(r.patient_id),
                        'status': effective_status(r, now), 'issued_at': iso(r.issue_date)} for r in recent],
            'awaiting_collection': waiting}
