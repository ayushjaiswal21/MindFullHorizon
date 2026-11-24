"""Shared builders for the patient prescription tests: doctors, medicines, prescriptions, consent.

Rows are made directly so these tests do not depend on the issue flow.
"""
import os
from datetime import timedelta

from extensions import db
from models import ConsentRecord, Medicine, PrescriberProfile, Prescription, PrescriptionItem, User
from utils.rx_numbers import new_number
from utils.timeutil import utcnow

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY = "test-key-0001"


def make_doctor(app, make_user, verified=True, institution="Test University", name="Dr Asha Rao"):
    uid = make_user("provider", institution=institution, name=name)
    with app.app_context():
        db.session.get(User, uid).provider_type = "doctor"
        now = utcnow()
        db.session.add(PrescriberProfile(
            user_id=uid, registration_number=f"REG{uid:04d}", council="Test Council", council_key="test council",
            registered_since=2010, status="verified" if verified else "pending", submitted_at=now,
            status_changed_at=now, verified_at=now if verified else None,
            review_due_at=now + timedelta(days=300) if verified else None))
        db.session.commit()
    return uid


def make_medicine(app):
    with app.app_context():
        m = Medicine(generic_name="Testamol", generic_key="testamol", brand_name="", strength="10 mg", form="tablet",
                     tpg_list="O", is_demo=True, list_verified_at=utcnow())
        db.session.add(m)
        db.session.commit()
        return m.id


def make_rx(app, doctor, patient, med, status="issued", days=10, dispensed=0, requested=False, number=None, draft=False):
    """One prescription with one item (7 tablets)."""
    now = utcnow()
    with app.app_context():
        rx = Prescription(
            provider_id=doctor, patient_id=patient, status="draft" if draft else status,
            number=None if draft else (number or new_number(now)), doctor_name="Dr Asha Rao", doctor_reg_no="REG0001",
            doctor_council="Test Council", institution_name="Test University", institution_key="test university",
            patient_name="Pat", diagnosis="F41.1", allergies_status="none_reported", current_meds_status="unknown",
            issue_date=None if draft else now, expiry_date=None if draft else now + timedelta(days=days),
            dispense_requested_at=now if requested else None)
        if status == "legacy":
            rx.number, rx.medication_name, rx.dosage = None, "Oldmed", "1 daily"
        db.session.add(rx)
        db.session.flush()
        if status != "legacy":
            db.session.add(PrescriptionItem(prescription_id=rx.id, line_no=1, medicine_id=med, medicine_label="TESTAMOL 10 mg tablet",
                                            dose_text="1 tablet", frequency="once daily", duration_days=7, quantity=7,
                                            quantity_dispensed=dispensed, instructions="After food"))
        db.session.commit()
        return rx.id


def consent_row(app, patient, kind="eprescription"):
    from services.config import erx_consent_version
    with app.app_context():
        db.session.add(ConsentRecord(user_id=patient, kind=kind, version=erx_consent_version(), accepted_at=utcnow()))
        db.session.commit()


def page(c, url):
    return c.get(url).get_data(as_text=True)
