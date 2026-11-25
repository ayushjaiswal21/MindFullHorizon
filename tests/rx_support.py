"""Builders for the prescribing tests (services and API): patient, consult, consent, medicines, ready drafts."""
from datetime import timedelta

import pytest

from core.extensions import db
from models import Appointment, Medicine, ProviderPatient
from services import consent, prescriptions
from services.errors import ServiceError
from utils.timeutil import ist_today, utcnow

KEY = "issue-key-0001"


def link(app, doctor, patient):
    with app.app_context():
        db.session.add(ProviderPatient(provider_id=doctor, patient_id=patient, source="manual"))
        db.session.commit()


def give_consent(app, patient):
    with app.app_context():
        consent.set_erx_consent(patient, True)
        db.session.commit()


def make_consult(app, doctor, patient, modality="video", status="accepted", hours_ago=0, time="10:00", day=None):
    """An appointment whose consult the doctor has started `hours_ago` hours ago."""
    with app.app_context():
        a = Appointment(user_id=patient, provider_id=doctor, date=day or ist_today(), time=time, appointment_type="consultation",
                        status=status, modality=modality, consult_started_at=utcnow() - timedelta(hours=hours_ago))
        db.session.add(a)
        db.session.commit()
        return a.id


def make_med(app, name="Alphamol", tpg="A", schedule="none", verified=True, **kw):
    with app.app_context():
        m = Medicine(generic_name=name, generic_key=name.lower(), brand_name=kw.pop("brand", ""), strength=kw.pop("strength", "10 mg"),
                     form="tablet", tpg_list=tpg, schedule=schedule, is_controlled=schedule in ("X", "NDPS", "H1"),
                     list_verified_at=utcnow() if verified else None, **kw)
        db.session.add(m)
        db.session.commit()
        return m.id


def item(med, **kw):
    return {"medicine_id": med, "dose_text": "1 tablet", "frequency": "once daily", "duration_days": 7, "quantity": 7,
            "instructions": None} | kw


def ready_draft(app, doctor, patient, meds, **fields):
    """A draft that passes validation: clinical fields filled in and one item per medicine id."""
    with app.app_context():
        rx = prescriptions.create_draft(doctor, patient)
        payload = {"diagnosis": "F41.1", "allergies_status": "none_reported", "current_meds_status": "unknown",
                   "items": [item(m) for m in meds]} | fields
        rx = prescriptions.save_draft(doctor, rx.id, payload, rx.row_version)
        db.session.commit()
        return rx.id


def setup(app, make_user, make_doctor, meds=("A",), **consult_kw):
    """Doctor, assigned patient with consent and a started video consult, plus one medicine per TPG list letter."""
    doctor, patient = make_doctor(), make_user("patient")
    link(app, doctor, patient)
    give_consent(app, patient)
    appt = make_consult(app, doctor, patient, **consult_kw)
    return {"doctor": doctor, "patient": patient, "appt": appt,
            "meds": [make_med(app, name=f"Drug{letter.lower()}", tpg=letter) for letter in meds]}


def issue(app, s, rx_id, key=KEY, ack=()):
    """Issue a draft through the service and commit. Returns (id, replayed)."""
    with app.app_context():
        res = prescriptions.issue(s["doctor"], rx_id, key, ack)
        db.session.commit()
        return res.prescription.id, res.replayed


def code_of(app, fn):
    """The ServiceError code `fn` raises (the session is rolled back)."""
    with app.app_context():
        with pytest.raises(ServiceError) as e:
            fn()
        db.session.rollback()
        return e.value.code


def issued(app, s, meds=None, **fields):
    rx = ready_draft(app, s["doctor"], s["patient"], meds or s["meds"][:1], **fields)
    issue(app, s, rx)
    return rx
