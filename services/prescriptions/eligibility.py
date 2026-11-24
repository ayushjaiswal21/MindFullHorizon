"""Consult eligibility and TPG context (design 3.3)."""
from dataclasses import dataclass, field
from datetime import timedelta

from models import Appointment
from services import config, consent
from services.rx_rules import allowed_lists, max_days
from utils.timeutil import utcnow

QUALIFYING_MODALITIES = ('video', 'in_person')
FOLLOW_UP_DAYS = 183  # six months, UNVERIFIED rounding (design 3.3)


@dataclass
class Eligibility:
    consult_appointment_id: int | None = None
    modality: str | None = None
    started_at: object = None
    tpg_context: str = 'first'
    allowed_lists: set = field(default_factory=lambda: {'O', 'A'})
    max_days: int = 14
    blockers: list = field(default_factory=list)
    erx_consent: bool = False
    follow_up_possible: bool = False


def consult_eligibility(doctor_id, patient_id, same_condition_attested=False, now=None):
    now = now or utcnow()
    base = Appointment.query.filter(Appointment.user_id == patient_id, Appointment.provider_id == doctor_id,
                                    Appointment.modality.in_(QUALIFYING_MODALITIES),
                                    Appointment.consult_started_at.isnot(None))
    a = (base.filter(Appointment.status.in_(('accepted', 'booked', 'completed')),
                     Appointment.consult_started_at >= now - timedelta(hours=config.rx_consult_window_hours()))
         .order_by(Appointment.consult_started_at.desc(), Appointment.id.desc()).first())
    el = Eligibility(erx_consent=consent.erx_status(patient_id)['active'])
    if a is None:
        el.blockers.append('no_consult')
    else:
        el.consult_appointment_id, el.modality, el.started_at = a.id, a.modality, a.consult_started_at
        prior = base.filter(Appointment.modality == 'in_person', Appointment.status == 'completed',
                            Appointment.id != a.id,
                            Appointment.consult_started_at >= now - timedelta(days=FOLLOW_UP_DAYS)).first()
        el.follow_up_possible = a.modality == 'video' and prior is not None
        if a.modality == 'in_person':
            el.tpg_context = 'in_person'
        elif el.follow_up_possible and same_condition_attested:
            el.tpg_context = 'follow_up'
    if not el.erx_consent:
        el.blockers.append('no_consent')
    el.allowed_lists = allowed_lists(el.tpg_context)
    el.max_days = max_days(el.tpg_context)
    return el
