"""Patient prescription screens (docs/CLINICAL_DESIGN.md 5.2): list, detail, send to desk, consent, public check."""
import os

import pytest

from extensions import db
from models import AuditLog, Prescription
from rx_helpers import KEY, ROOT, make_doctor, make_medicine, make_rx, page
from utils.rx_numbers import new_number
from utils.timeutil import utcnow


@pytest.fixture(autouse=True)
def flag_on(monkeypatch):
    monkeypatch.setenv("ENABLE_PRESCRIPTIONS", "1")


# ---------- list ----------

def test_list_buckets_and_empty_states(app, make_user, patient_client):
    c, uid = patient_client
    doc, med = make_doctor(app, make_user), make_medicine(app)
    assert "No prescriptions yet" in page(c, "/patient/my-prescriptions")
    active = make_rx(app, doc, uid, med, number="RX2611-ACTIVEAAAAA")
    make_rx(app, doc, uid, med, status="cancelled", number="RX2611-CANCELBBBBB")
    make_rx(app, doc, uid, med, status="dispensed", dispensed=7, number="RX2611-DONECCCCCC")
    html = page(c, "/patient/my-prescriptions")
    assert "RX2611-ACTIVEAAAAA" in html and "RX2611-CANCELBBBBB" not in html and "Send to pharmacy desk" in html
    past = page(c, "/patient/my-prescriptions?tab=past")
    assert "RX2611-CANCELBBBBB" in past and "RX2611-DONECCCCCC" in past and "RX2611-ACTIVEAAAAA" not in past
    assert "Cancelled" in past and "Collected" in past
    assert f"/patient/prescriptions/{active}" in html


def test_empty_active_tab_when_only_past_exists(app, make_user, patient_client):
    c, uid = patient_client
    make_rx(app, make_user("provider"), uid, make_medicine(app), status="expired")
    assert "No active prescriptions." in page(c, "/patient/my-prescriptions")
    assert "Expired" in page(c, "/patient/my-prescriptions?tab=past")


def test_drafts_are_invisible_to_the_patient(app, make_user, patient_client):
    c, uid = patient_client
    doc, med = make_doctor(app, make_user), make_medicine(app)
    draft = make_rx(app, doc, uid, med, draft=True)
    html = page(c, "/patient/my-prescriptions")
    assert "No prescriptions yet" in html and f"/patient/prescriptions/{draft}" not in html
    assert c.get(f"/patient/prescriptions/{draft}").status_code == 404
    assert c.get("/patient/api/prescriptions").get_json()["items"] == []


def test_legacy_row_warns_and_has_no_actions(app, make_user, patient_client):
    c, uid = patient_client
    make_rx(app, make_user("provider"), uid, make_medicine(app), status="legacy")
    html = page(c, "/patient/my-prescriptions?tab=past")
    assert "Issued before doctor verification existed" in html
    assert "Send to pharmacy desk" not in html and "Print" not in html


def test_collection_status_words(app, make_user, patient_client):
    c, uid = patient_client
    doc, med = make_doctor(app, make_user), make_medicine(app)
    make_rx(app, doc, uid, med, number="RX2611-NONEAAAAAAA")
    make_rx(app, doc, uid, med, status="partially_dispensed", dispensed=3, number="RX2611-PARTBBBBBBB")
    html = page(c, "/patient/my-prescriptions")
    assert "Not collected" in html and "Partly collected" in html


def test_flag_off_hides_everything(app, make_user, patient_client, monkeypatch):
    c, uid = patient_client
    rx = make_rx(app, make_user("provider"), uid, make_medicine(app))
    monkeypatch.setenv("ENABLE_PRESCRIPTIONS", "0")
    for url in ("/patient/my-prescriptions", f"/patient/prescriptions/{rx}", "/patient/api/prescriptions", "/rx/RX2611-AAAAAAAAAAA"):
        assert c.get(url).status_code == 404


def test_only_patients_reach_patient_routes(app, make_user, provider_client, client):
    c, _ = provider_client
    assert c.get("/patient/my-prescriptions").status_code == 302
    assert c.get("/patient/api/prescriptions", headers={"X-Requested-With": "XMLHttpRequest"}).status_code == 403
    assert client.get("/patient/my-prescriptions").status_code == 302


# ---------- detail ----------

def test_detail_shows_own_prescription_and_hides_others(app, make_user, patient_client):
    c, uid = patient_client
    doc, med = make_doctor(app, make_user), make_medicine(app)
    other = make_user("patient")
    mine = make_rx(app, doc, uid, med, dispensed=2, number="RX2611-MINEAAAAAAA")
    theirs = make_rx(app, doc, other, med, number="RX2611-THEIRSBBBBB")
    html = page(c, f"/patient/prescriptions/{mine}")
    for text in ("RX2611-MINEAAAAAAA", "TESTAMOL 10 mg tablet", "2 of 7", "F41.1", "Dr Asha Rao", "never prescribes medicine by itself"):
        assert text in html
    assert c.get(f"/patient/prescriptions/{theirs}").status_code == 404
    assert c.get(f"/patient/prescriptions/{theirs}/print").status_code == 404


def test_print_uses_shared_template(app, make_user, patient_client):
    if not os.path.exists(os.path.join(ROOT, "templates", "provider_rx", "print.html")):
        pytest.skip("provider_rx/print.html is package B's and has not landed")
    c, uid = patient_client
    rx = make_rx(app, make_doctor(app, make_user), uid, make_medicine(app), number="RX2611-PRINTAAAAAA")
    r = c.get(f"/patient/prescriptions/{rx}/print")
    assert r.status_code == 200 and "RX2611-PRINTAAAAAA" in r.get_data(as_text=True)


# ---------- send to pharmacy desk ----------

def post_send(c, rx, key=KEY):
    headers = {"Idempotency-Key": key} if key else {}
    return c.post(f"/patient/api/prescriptions/{rx}/request-pharmacy", json={}, headers=headers)


def test_request_pharmacy_is_idempotent_and_audited_once(app, make_user, patient_client):
    c, uid = patient_client
    rx = make_rx(app, make_doctor(app, make_user), uid, make_medicine(app))
    first, again = post_send(c, rx), post_send(c, rx)
    assert first.status_code == 200 and again.status_code == 200
    with app.app_context():
        assert db.session.get(Prescription, rx).dispense_requested_at is not None
        rows = AuditLog.query.filter_by(action="rx_send_to_desk").all()
        assert len(rows) == 1 and rows[0].actor_id == uid and not rows[0].meta
    assert "Sent to the pharmacy desk on" in page(c, f"/patient/prescriptions/{rx}")


def test_request_pharmacy_needs_a_valid_key(app, make_user, patient_client):
    c, uid = patient_client
    rx = make_rx(app, make_doctor(app, make_user), uid, make_medicine(app))
    assert post_send(c, rx, key=None).status_code == 400
    assert post_send(c, rx, key="short").status_code == 400
    with app.app_context():
        assert db.session.get(Prescription, rx).dispense_requested_at is None


@pytest.mark.parametrize("status", ["cancelled", "expired", "dispensed"])
def test_request_pharmacy_refused_for_closed_prescriptions(app, make_user, patient_client, status):
    c, uid = patient_client
    rx = make_rx(app, make_doctor(app, make_user), uid, make_medicine(app), status=status)
    r = post_send(c, rx)
    assert r.status_code == 409 and r.get_json()["error"] == "not_sendable"
    with app.app_context():
        assert db.session.get(Prescription, rx).dispense_requested_at is None


def test_request_pharmacy_for_someone_elses_prescription_is_404(app, make_user, patient_client):
    c, uid = patient_client
    rx = make_rx(app, make_doctor(app, make_user), make_user("patient"), make_medicine(app))
    assert post_send(c, rx).status_code == 404
    with app.app_context():
        assert db.session.get(Prescription, rx).dispense_requested_at is None


# ---------- consent ----------

def test_consent_give_withdraw_give_again(app, patient_client):
    c, uid = patient_client
    assert "Allow e-prescriptions" in page(c, "/patient/my-prescriptions")
    for value in (True, False, True):
        r = c.post("/patient/api/prescriptions/consent", json={"consent": value})
        assert r.status_code == 200 and r.get_json()["consent"]["active"] is value
    from services.consent import erx_status
    with app.app_context():
        assert erx_status(uid)["active"] is True
        actions = [a.action for a in AuditLog.query.filter(AuditLog.action.like("erx_consent%")).order_by(AuditLog.id)]
    assert actions == ["erx_consent_give", "erx_consent_withdraw", "erx_consent_give"]


def test_consent_rejects_non_boolean(patient_client):
    c, _ = patient_client
    for body in ({}, {"consent": "yes"}, {"consent": 1}):
        r = c.post("/patient/api/prescriptions/consent", json=body)
        assert r.status_code == 422 and r.get_json()["error"] == "field_invalid"


def test_withdraw_keeps_issued_prescriptions(app, make_user, patient_client):
    c, uid = patient_client
    rx = make_rx(app, make_doctor(app, make_user), uid, make_medicine(app), number="RX2611-KEEPAAAAAAA")
    c.post("/patient/api/prescriptions/consent", json={"consent": True})
    c.post("/patient/api/prescriptions/consent", json={"consent": False})
    from services.consent import erx_status
    with app.app_context():
        assert erx_status(uid)["active"] is False
    assert "RX2611-KEEPAAAAAAA" in page(c, "/patient/my-prescriptions") and c.get(f"/patient/prescriptions/{rx}").status_code == 200


# ---------- public status check ----------

def test_public_status_shows_minimal_fields(app, make_user, client):
    patient = make_user("patient", name="Secret Student")
    med = make_medicine(app)
    number = new_number(utcnow())
    make_rx(app, make_doctor(app, make_user), patient, med, number=number)
    r = client.get(f"/rx/{number}")  # no login
    html = r.get_data(as_text=True)
    assert r.status_code == 200 and number in html and "Dr Asha Rao" in html and "Test University" in html
    assert "Secret Student" not in html and "TESTAMOL" not in html and "F41.1" not in html
    assert client.get(f"/rx/{number}", headers={"Accept": "application/json"}).get_json()["status"] == "valid"


def test_public_status_bad_check_character_and_unknown_are_the_same_404(client):
    good = new_number(utcnow())
    bad = good[:-1] + ("0" if good[-1] != "0" else "1")
    codes = {client.get(f"/rx/{n}").status_code for n in (bad, good, "nonsense", "RX2611-")}
    assert codes == {404}
