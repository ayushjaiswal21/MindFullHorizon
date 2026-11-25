"""Counsellor and doctor read-only Medications panel (docs/CLINICAL_DESIGN.md 5.3)."""
import pytest

from core.extensions import db
from models import AuditLog, Medication, Prescription, ProviderPatient
from rx_helpers import make_doctor, make_medicine, make_rx, page


@pytest.fixture(autouse=True)
def flag_on(monkeypatch):
    monkeypatch.setenv("ENABLE_PRESCRIPTIONS", "1")


def assign(app, provider, patient):
    with app.app_context():
        db.session.add(ProviderPatient(provider_id=provider, patient_id=patient, source="manual"))
        db.session.commit()


def log_medicine(app, patient, name="Own Vitamin", dosage="1 daily"):
    with app.app_context():
        db.session.add(Medication(user_id=patient, name=name, dosage=dosage, frequency="daily", is_active=True))
        db.session.commit()


def test_panel_lists_item_lines_and_self_logged_medicines(app, make_user, provider_client):
    c, pid = provider_client
    patient, med = make_user("patient"), make_medicine(app)
    assign(app, pid, patient)
    make_rx(app, make_doctor(app, make_user), patient, med)
    log_medicine(app, patient)
    html = page(c, f"/provider/wellness-report/{patient}")
    assert 'id="meds-panel"' in html
    for text in ("TESTAMOL 10 mg tablet", "1 tablet", "once daily", "7 days", "Dr Asha Rao", "Own Vitamin", "Logged by patient"):
        assert text in html
    assert "Only a verified doctor can change a prescription." in html


def test_panel_hides_diagnosis_allergies_and_number(app, make_user, provider_client):
    c, pid = provider_client
    patient, med = make_user("patient"), make_medicine(app)
    assign(app, pid, patient)
    make_rx(app, make_doctor(app, make_user), patient, med, number="RX2611-HIDDENAAAAA")
    with app.app_context():
        rx = Prescription.query.one()
        rx.diagnosis, rx.allergies, rx.allergies_status = "SECRET-DIAGNOSIS", "SECRET-ALLERGY", "listed"
        db.session.commit()
    html = page(c, f"/provider/wellness-report/{patient}")
    body = c.get(f"/provider/api/patients/{patient}/medications").get_data(as_text=True)
    for text in ("SECRET-DIAGNOSIS", "SECRET-ALLERGY", "RX2611-HIDDENAAAAA"):
        assert text not in html and text not in body
    assert "TESTAMOL" in body


def test_panel_shows_only_active_prescriptions(app, make_user, provider_client):
    c, pid = provider_client
    patient, med, doc = make_user("patient"), make_medicine(app), make_doctor(app, make_user)
    assign(app, pid, patient)
    make_rx(app, doc, patient, med, status="cancelled")
    make_rx(app, doc, patient, med, draft=True)
    body = c.get(f"/provider/api/patients/{patient}/medications").get_json()
    assert body["success"] is True and body["prescriptions"] == []
    assert "No medicines recorded for this patient." in page(c, f"/provider/wellness-report/{patient}")


def test_panel_empty_state(app, make_user, provider_client):
    c, pid = provider_client
    patient = make_user("patient")
    assign(app, pid, patient)
    assert "No medicines recorded for this patient." in page(c, f"/provider/wellness-report/{patient}")


def test_panel_is_assigned_only(app, make_user, provider_client):
    c, pid = provider_client
    mine, other = make_user("patient"), make_user("patient")
    assign(app, pid, mine)
    make_rx(app, make_doctor(app, make_user), other, make_medicine(app))
    assert c.get(f"/provider/api/patients/{mine}/medications").status_code == 200
    assert c.get(f"/provider/api/patients/{other}/medications").status_code == 404
    assert c.get(f"/provider/wellness-report/{other}").status_code == 404


def test_panel_other_institution_is_404(app, make_user, provider_client):
    c, pid = provider_client
    foreign = make_user("patient", institution="Other University")
    assign(app, pid, foreign)  # even a stray link does not cross institutions
    assert c.get(f"/provider/api/patients/{foreign}/medications").status_code == 404


def test_panel_read_is_audited_with_counts_only(app, make_user, provider_client):
    c, pid = provider_client
    patient, med = make_user("patient"), make_medicine(app)
    assign(app, pid, patient)
    make_rx(app, make_doctor(app, make_user), patient, med)
    log_medicine(app, patient, name="Marker-Vitamin")
    c.get(f"/provider/api/patients/{patient}/medications")
    with app.app_context():
        rows = AuditLog.query.filter_by(action="view_patient_meds").all()
        assert len(rows) == 1 and rows[0].actor_id == pid and rows[0].target_id == patient
        assert rows[0].meta == {"n": 2}
        assert "Marker-Vitamin" not in str(rows[0].meta) and "TESTAMOL" not in str(rows[0].meta)


def test_flag_off_drops_prescription_lines_but_keeps_self_logged(app, make_user, provider_client, monkeypatch):
    c, pid = provider_client
    patient = make_user("patient")
    assign(app, pid, patient)
    make_rx(app, make_doctor(app, make_user), patient, make_medicine(app))
    log_medicine(app, patient)
    monkeypatch.setenv("ENABLE_PRESCRIPTIONS", "0")
    html = page(c, f"/provider/wellness-report/{patient}")
    assert "Own Vitamin" in html and "TESTAMOL" not in html and "send_prescription" not in html


def test_old_send_prescription_route_is_gone_for_everyone(app, make_user, provider_client, patient_client):
    c, pid = provider_client
    pc, uid = patient_client
    assign(app, pid, uid)
    for client in (c, pc):
        assert client.post(f"/provider/send_prescription/{uid}", data={"medication_name": "X", "dosage": "1"}).status_code == 404
    with app.app_context():
        assert Prescription.query.count() == 0


def test_medications_api_is_for_providers_only(app, make_user, patient_client, client):
    pc, uid = patient_client
    ajax = {"X-Requested-With": "XMLHttpRequest"}
    assert pc.get(f"/provider/api/patients/{uid}/medications", headers=ajax).status_code == 403
    assert client.get(f"/provider/api/patients/{uid}/medications", headers=ajax).status_code == 401


def test_caseload_shows_rx_badge_only_for_patients_with_active_prescription(app, make_user, provider_client):
    c, pid = provider_client
    with_rx, without = make_user("patient", name="Has Rx Person"), make_user("patient", name="No Rx Person")
    for p in (with_rx, without):
        assign(app, pid, p)
    make_rx(app, make_doctor(app, make_user), with_rx, make_medicine(app))
    html = page(c, "/provider/dashboard")
    assert html.count('title="Has an active prescription"') == 1
    assert html.index("Has Rx Person") < html.index('title="Has an active prescription"') < html.index("No Rx Person")


def test_appointment_list_carries_modality(app, make_user, provider_client):
    from datetime import date
    from models import Appointment
    c, pid = provider_client
    patient = make_user("patient")
    assign(app, pid, patient)
    with app.app_context():
        db.session.add(Appointment(user_id=patient, provider_id=pid, date=date.today(), time="09:00",
                                   appointment_type="consultation", status="accepted", modality="video"))
        db.session.commit()
    rows = c.get("/provider/appointments", headers={"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"}).get_json()
    rows = rows.get("appointments", rows) if isinstance(rows, dict) else rows
    assert rows[0]["modality"] == "video"
