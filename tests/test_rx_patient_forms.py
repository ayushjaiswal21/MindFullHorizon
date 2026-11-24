"""Patient dashboard widget, care team, schedule form (doctor booking) and consent wording."""
import os
from datetime import date, timedelta

import pytest

from extensions import db
from models import Appointment, ConsentRecord, ProviderPatient
from rx_helpers import ROOT, consent_row, make_doctor, make_medicine, make_rx, page
from utils.rx_text import ERX_CONSENT_TEXT


@pytest.fixture(autouse=True)
def flag_on(monkeypatch):
    monkeypatch.setenv("ENABLE_PRESCRIPTIONS", "1")


# ---------- dashboard ----------

def test_dashboard_widget_and_care_team(app, make_user, patient_client):
    c, uid = patient_client
    html = page(c, "/patient/dashboard")
    assert "No prescriptions yet" in html and "You have not booked with anyone yet." in html
    doc, counsellor, med = make_doctor(app, make_user), make_user("provider", name="Cara Counsel"), make_medicine(app)
    with app.app_context():
        for staff in (doc, counsellor):
            db.session.add(ProviderPatient(provider_id=staff, patient_id=uid, source="manual"))
        db.session.commit()
    make_rx(app, doc, uid, med)
    html = page(c, "/patient/dashboard")
    assert "Active prescriptions" in html and "Next expires" in html
    assert "Dr Asha Rao" in html and "Doctor" in html and "Cara Counsel" in html and "Counsellor" in html
    assert "can see the information you share" in html


def test_dashboard_has_no_widget_when_flag_off(patient_client, monkeypatch):
    c, _ = patient_client
    monkeypatch.setenv("ENABLE_PRESCRIPTIONS", "0")
    html = page(c, "/patient/dashboard")
    assert "Active prescriptions" not in html and "/patient/my-prescriptions" not in html and "Your care team" in html


# ---------- schedule form ----------

def booking(uid_provider, **extra):
    data = {"date": (date.today() + timedelta(days=2)).isoformat(), "time": "10:00", "appointment_type": "consultation",
            "provider_id": str(uid_provider), "client_request_id": "sched-key-0001"}
    data.update(extra)
    return data


def test_schedule_lists_verified_doctors_and_counsellors_only(app, make_user, patient_client):
    c, _ = patient_client
    verified = make_doctor(app, make_user, name="Dr Verified")
    make_doctor(app, make_user, verified=False, name="Dr Pending")
    make_doctor(app, make_user, institution="Other University", name="Dr Elsewhere")
    make_user("provider", name="Cara Counsel")
    html = page(c, "/patient/schedule")
    assert "Dr Verified (Doctor)" in html and "Cara Counsel (Counsellor)" in html
    assert "Dr Pending" not in html and "Dr Elsewhere" not in html
    assert f'data-doctor-ids="{verified}"' in html and "How will you meet the doctor?" in html


def test_booking_an_unverified_doctor_is_refused(app, make_user, patient_client):
    c, uid = patient_client
    pending = make_doctor(app, make_user, verified=False)
    r = c.post("/patient/schedule", data=booking(pending, modality="video", erx_consent="on"))
    assert r.status_code == 400
    with app.app_context():
        assert Appointment.query.count() == 0


def test_doctor_booking_needs_modality_and_consent(app, make_user, patient_client):
    c, uid = patient_client
    doc = make_doctor(app, make_user)
    assert c.post("/patient/schedule", data=booking(doc, erx_consent="on")).status_code == 400
    assert "video or in person" in c.post("/patient/schedule", data=booking(doc, erx_consent="on")).get_data(as_text=True)
    r = c.post("/patient/schedule", data=booking(doc, modality="video"))
    assert r.status_code == 400 and "e-prescriptions" in r.get_data(as_text=True)
    with app.app_context():
        assert Appointment.query.count() == 0 and ConsentRecord.query.filter_by(kind="eprescription").count() == 0


def test_doctor_booking_stores_modality_and_consent(app, make_user, patient_client):
    c, uid = patient_client
    doc = make_doctor(app, make_user)
    r = c.post("/patient/schedule", data=booking(doc, modality="in_person", erx_consent="on"))
    assert r.status_code == 302
    from services.consent import erx_status
    with app.app_context():
        appt = Appointment.query.one()
        assert appt.modality == "in_person" and appt.provider_id == doc
        assert ProviderPatient.query.filter_by(provider_id=doc, patient_id=uid).count() == 1
        assert erx_status(uid)["active"] is True
    assert "In person" in page(c, "/patient/schedule")


def test_counsellor_booking_needs_neither_modality_nor_consent(app, make_user, patient_client):
    c, uid = patient_client
    cons = make_user("provider")
    assert c.post("/patient/schedule", data=booking(cons)).status_code == 302
    with app.app_context():
        assert Appointment.query.one().modality is None
        assert ConsentRecord.query.filter_by(kind="eprescription").count() == 0


def test_booking_skips_the_tickbox_when_consent_exists(app, make_user, patient_client):
    c, uid = patient_client
    consent_row(app, uid)
    doc = make_doctor(app, make_user)
    assert "You have already allowed e-prescriptions" in page(c, "/patient/schedule")
    assert c.post("/patient/schedule", data=booking(doc, modality="video")).status_code == 302


# ---------- wording ----------

def test_consent_text_is_verbatim_from_the_design(app, make_user, patient_client):
    with open(os.path.join(ROOT, "docs", "CLINICAL_DESIGN.md"), encoding="utf-8") as fh:
        assert ERX_CONSENT_TEXT in fh.read()
    c, _ = patient_client
    make_doctor(app, make_user)
    assert ERX_CONSENT_TEXT in page(c, "/patient/schedule")  # shown next to the tick box
    assert ERX_CONSENT_TEXT in page(c, "/patient/my-prescriptions")  # shown with the Allow button


def test_export_includes_prescription_items(app, make_user, patient_client):
    c, uid = patient_client
    make_rx(app, make_doctor(app, make_user), uid, make_medicine(app))
    r = c.post("/account/export")
    assert r.status_code == 200 and "TESTAMOL 10 mg tablet" in r.get_data(as_text=True)
