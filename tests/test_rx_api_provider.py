"""Provider prescribing JSON API and pages (design 5.3, 5.5): access rules, lookups, drafts, issue, consults, profile."""
import os

import pytest

from conftest import _login_as
from core.extensions import db
from models import Appointment, AuditLog, Prescription, PrescriberProfile
from tests.rx_support import give_consent, item, link, make_consult, make_med, ready_draft, setup

API = "/provider/api/rx"
HAS_PRINT = os.path.exists(os.path.join(os.path.dirname(__file__), "..", "templates", "provider_rx", "print.html"))


@pytest.fixture
def d(app, make_user, make_doctor):
    """Doctor logged in, with an assigned patient, consent, a started video consult and medicines O, A, B, C."""
    s = setup(app, make_user, make_doctor, meds=("O", "A", "B", "C"))
    c = app.test_client()
    _login_as(c, app, s["doctor"])
    return c, s


def headers(key="api-issue-key-01"):
    return {"Idempotency-Key": key}


def draft_via_api(c, s, **extra):
    r = c.post(f"{API}/prescriptions", json={"patient_id": s["patient"]}, headers=headers("crid-key-0001"))
    assert r.status_code == 201, r.get_data(as_text=True)
    rx = r.get_json()["prescription"]
    body = {"row_version": rx["row_version"], "diagnosis": "F41.1", "allergies_status": "none_reported",
            "current_meds_status": "unknown", "items": [item(s["meds"][1])]} | extra
    r = c.put(f"{API}/prescriptions/{rx['id']}", json=body)
    assert r.status_code == 200, r.get_data(as_text=True)
    return r.get_json()["prescription"]


# ---- access ----

def test_counsellor_gets_404_on_prescribing_routes(app, provider_client):
    c, _ = provider_client
    for url in (f"{API}/dashboard", f"{API}/patients", "/provider/prescriptions", "/provider/prescribing-profile"):
        assert c.get(url).status_code == 404, url
    assert c.post(f"{API}/prescriptions", json={"patient_id": 1}).status_code == 404


def test_patient_and_admin_cannot_reach_prescribing(app, patient_client, admin_client):
    for c, _ in (patient_client, admin_client):
        assert c.get(f"{API}/patients", headers={"X-Requested-With": "XMLHttpRequest"}).status_code == 403


def test_unverified_doctor_gets_403_json(app, make_doctor):
    c, doc = app.test_client(), make_doctor(status="pending")
    _login_as(c, app, doc)
    r = c.get(f"{API}/patients")
    assert r.status_code == 403 and r.get_json()["error"] == "prescriber_not_verified"
    assert c.get("/provider/prescribe").status_code == 302  # HTML goes to the profile page
    assert c.get(f"{API}/dashboard").get_json()["state"] == "pending"  # the banner still loads
    with app.app_context():
        assert AuditLog.query.filter_by(action="denied").count() >= 1


def test_suspension_blocks_next_request(app, d):
    c, s = d
    assert c.get(f"{API}/patients").status_code == 200
    with app.app_context():
        PrescriberProfile.query.filter_by(user_id=s["doctor"]).one().status = "suspended"
        db.session.commit()
    assert c.get(f"{API}/patients").status_code == 403


def test_flag_off_returns_404(app, d, monkeypatch):
    monkeypatch.setenv("ENABLE_PRESCRIPTIONS", "0")
    assert d[0].get(f"{API}/patients").status_code == 404


# ---- lookups ----

def test_patients_list_assigned_only(app, d, make_user):
    c, s = d
    make_user("patient", name="Unassigned Person")
    other = make_user("patient", institution="Elsewhere College", name="Far Person")
    link(app, s["doctor"], other)  # assigned but a different institution: never listed
    items = c.get(f"{API}/patients").get_json()["items"]
    assert [i["id"] for i in items] == [s["patient"]]
    assert c.get(f"{API}/patients?q=zzz").get_json()["items"] == []


def test_eligibility_shape_and_foreign_patient_404(app, d, make_user):
    c, s = d
    body = c.get(f"{API}/eligibility?patient_id={s['patient']}").get_json()
    assert body["blockers"] == [] and body["tpg_context"] == "first" and body["allowed_lists"] == ["A", "O"]
    assert body["consult"]["modality"] == "video" and body["limits"]["max_items"] == 6 and body["erx_consent"] is True
    assert c.get(f"{API}/eligibility?patient_id={make_user('patient')}").status_code == 404


def test_medicines_search_min_length_and_limit(app, d):
    c, s = d
    assert c.get(f"{API}/medicines?q=d").get_json()["items"] == []
    for i in range(25):
        make_med(app, name=f"Bulkdrug{i:02d}", tpg="O")
    assert len(c.get(f"{API}/medicines?q=bulkdrug").get_json()["items"]) == 20


def test_medicines_blocked_reasons_and_no_stock_numbers(app, d):
    c, s = d
    items = {i["tpg_list"]: i for i in c.get(f"{API}/medicines?q=drug&patient_id={s['patient']}").get_json()["items"]}
    assert items["A"]["prescribable"] and items["A"]["blocked_code"] is None
    assert items["B"]["blocked_code"] == "medicine_needs_followup" and items["B"]["blocked_text"]
    assert items["C"]["blocked_code"] == "medicine_blocked_c"
    assert all(i["availability"] in ("in_stock", "low", "out") for i in items.values())
    assert not any("on_hand" in i for i in items.values())


def test_availability_badge_comes_from_inventory(app, d, monkeypatch):
    c, s = d
    monkeypatch.setattr("services.inventory.availability",
                        lambda inst, reqs: {m: {"status": "low", "on_hand": 3} for m, _ in reqs}, raising=False)
    items = c.get(f"{API}/medicines?q=druga").get_json()["items"]
    assert items[0]["availability"] == "low" and "on_hand" not in items[0]


# ---- drafts ----

def test_draft_create_idempotent(app, d):
    c, s = d
    a = c.post(f"{API}/prescriptions", json={"patient_id": s["patient"]}, headers=headers("crid-key-0001"))
    b = c.post(f"{API}/prescriptions", json={"patient_id": s["patient"]}, headers=headers("crid-key-0001"))
    assert (a.status_code, b.status_code) == (201, 200)
    assert a.get_json()["prescription"]["id"] == b.get_json()["prescription"]["id"]
    assert c.post(f"{API}/prescriptions", json={"patient_id": s["patient"]}, headers=headers("x")).status_code == 400


def test_draft_put_row_version_conflict_and_other_doctor_404(app, d, make_doctor):
    c, s = d
    rx = draft_via_api(c, s)
    r = c.put(f"{API}/prescriptions/{rx['id']}", json={"row_version": rx["row_version"] - 1, "diagnosis": "stale"})
    assert r.status_code == 409 and r.get_json()["error"] == "stale_draft"
    other = app.test_client()
    _login_as(other, app, make_doctor())
    assert other.get(f"{API}/prescriptions/{rx['id']}").status_code == 404
    assert other.delete(f"{API}/prescriptions/{rx['id']}").status_code == 404


def test_draft_delete_and_list_tabs(app, d):
    c, s = d
    rx = draft_via_api(c, s)
    assert [i["id"] for i in c.get(f"{API}/prescriptions?status=draft").get_json()["items"]] == [rx["id"]]
    assert c.delete(f"{API}/prescriptions/{rx['id']}").status_code == 200
    assert c.get(f"{API}/prescriptions?status=draft").get_json()["meta"]["total"] == 0


def test_validate_reports_errors_and_warnings(app, d):
    c, s = d
    rx = draft_via_api(c, s, items=[item(s["meds"][3])], diagnosis="")
    body = c.post(f"{API}/prescriptions/{rx['id']}/validate").get_json()
    codes = {(e["code"], e["item"], e["field"]) for e in body["errors"]}
    assert body["ok"] is False and ("medicine_blocked_c", 1, None) in codes and ("field_required", None, "diagnosis") in codes


# ---- issue ----

def test_issue_flow_replay_and_conflict(app, d):
    c, s = d
    rx = draft_via_api(c, s)
    assert c.post(f"{API}/prescriptions/{rx['id']}/issue", json={}).status_code == 400  # key required
    r = c.post(f"{API}/prescriptions/{rx['id']}/issue", json={}, headers=headers())
    body = r.get_json()
    assert r.status_code == 201 and body["replayed"] is False and body["prescription"]["number"].startswith("RX")
    again = c.post(f"{API}/prescriptions/{rx['id']}/issue", json={}, headers=headers())
    assert again.status_code == 200 and again.get_json()["replayed"] is True
    other = c.post(f"{API}/prescriptions/{rx['id']}/issue", json={}, headers=headers("different-key-02"))
    assert other.status_code == 409 and other.get_json()["error"] == "already_issued"
    put = c.put(f"{API}/prescriptions/{rx['id']}", json={"row_version": 99, "diagnosis": "x"})
    assert put.status_code == 409 and put.get_json()["error"] == "not_draft"
    assert c.get(f"{API}/dashboard").get_json()["recent"][0]["number"] == body["prescription"]["number"]


def test_issue_errors_carry_codes(app, d):
    c, s = d
    rx = draft_via_api(c, s, items=[item(s["meds"][3])])
    r = c.post(f"{API}/prescriptions/{rx['id']}/issue", json={}, headers=headers())
    assert r.status_code == 422 and r.get_json()["error"] == "medicine_blocked_c" and r.get_json()["errors"]
    assert "Traceback" not in r.get_data(as_text=True)


def test_issue_warning_unacknowledged_409(app, d):
    c, s = d
    rx = draft_via_api(c, s, allergies_status="listed", allergies="allergic to druga")
    r = c.post(f"{API}/prescriptions/{rx['id']}/issue", json={}, headers=headers())
    assert r.status_code == 409 and r.get_json()["warnings"][0]["code"] == "allergy_text_match"
    ok = c.post(f"{API}/prescriptions/{rx['id']}/issue", json={"acknowledged_warnings": ["allergy_text_match"]}, headers=headers())
    assert ok.status_code == 201


def test_cancel_amend_and_pages(app, d):
    c, s = d
    rx = draft_via_api(c, s)
    c.post(f"{API}/prescriptions/{rx['id']}/issue", json={}, headers=headers())
    assert c.post(f"{API}/prescriptions/{rx['id']}/cancel", json={"reason_code": "amended"}).status_code == 422
    new = c.post(f"{API}/prescriptions/{rx['id']}/amend").get_json()["prescription"]
    assert new["amends_id"] == rx["id"] and new["status"] == "draft"
    r = c.post(f"{API}/prescriptions/{rx['id']}/cancel", json={"reason_code": "error"})
    assert r.get_json()["prescription"]["status"] == "cancelled"
    closed = c.get(f"{API}/prescriptions?status=closed").get_json()
    assert closed["meta"]["total"] == 1 and closed["items"][0]["status"] == "cancelled"
    assert c.get(f"{API}/prescriptions?q={closed['items'][0]['number']}&status=closed").get_json()["meta"]["total"] == 1


@pytest.mark.skipif(not HAS_PRINT, reason="provider_rx/print.html (package B) not present yet")
def test_print_audited_and_scoped(app, d, make_doctor):
    c, s = d
    rx = draft_via_api(c, s)
    c.post(f"{API}/prescriptions/{rx['id']}/issue", json={}, headers=headers())
    assert c.get(f"/provider/prescriptions/{rx['id']}/print").status_code == 200
    with app.app_context():
        assert AuditLog.query.filter_by(action="rx_print").count() == 1
    other = app.test_client()
    _login_as(other, app, make_doctor())
    assert other.get(f"/provider/prescriptions/{rx['id']}/print").status_code == 404


# ---- consults, profile, dashboard section ----

def test_consult_start_rules_and_complete(app, d, make_user):
    c, s = d
    with app.app_context():
        a = Appointment(user_id=s["patient"], provider_id=s["doctor"], date=Appointment.query.get(s["appt"]).date,
                        time="15:00", appointment_type="consultation", status="accepted", modality="video")
        chat = Appointment(user_id=s["patient"], provider_id=s["doctor"], date=a.date, time="16:00",
                           appointment_type="consultation", status="accepted", modality="chat")
        db.session.add_all([a, chat])
        db.session.commit()
        aid, chat_id = a.id, chat.id
    url = "/provider/appointments/{}/{}-consult"
    assert c.post(url.format(chat_id, "start"), json={}).status_code == 422
    r = c.post(url.format(aid, "start"), json={})
    first = r.get_json()["started_at"]
    assert r.status_code == 200 and c.post(url.format(aid, "start"), json={}).get_json()["started_at"] == first
    assert c.post(url.format(chat_id, "complete"), json={}).status_code == 409  # never started
    assert c.post(url.format(aid, "complete"), json={}).status_code == 200
    with app.app_context():
        assert Appointment.query.get(aid).status == "completed"
        assert {a.action for a in AuditLog.query.all()} >= {"consult_start", "consult_complete"}


def test_consult_of_another_doctor_404(app, d, make_doctor):
    c, s = d
    other = app.test_client()
    _login_as(other, app, make_doctor())
    assert other.post(f"/provider/appointments/{s['appt']}/start-consult", json={}).status_code == 404


def test_profile_edit_resets_to_pending(app, d):
    c, s = d
    if not os.path.exists(os.path.join(os.path.dirname(__file__), "..", "templates", "provider_rx", "profile.html")):
        pytest.skip("provider_rx/profile.html (package B) not present yet")
    form = {"registration_number": "NEW 12345", "council": "State Medical Council", "registered_since": "2012", "specialisation": ""}
    assert c.post("/provider/prescribing-profile", data=form).status_code == 302
    with app.app_context():
        p = PrescriberProfile.query.filter_by(user_id=s["doctor"]).one()
        assert (p.status, p.registration_number) == ("pending", "NEW12345")
    assert c.get(f"{API}/patients").status_code == 403


def test_dashboard_widgets_and_section_visibility(app, d, provider_client):
    c, s = d
    draft_via_api(c, s)
    body = c.get(f"{API}/dashboard").get_json()
    assert body["state"] == "verified" and body["can_prescribe"] and body["drafts_total"] == 1
    assert body["consults_today"][0]["can_start"] is False and body["consults_today"][0]["started"] is True
    from routes.provider_rx import _rx_section
    with app.test_request_context():
        from flask import session
        session.update(user_role="provider", user_id=s["doctor"])
        assert _rx_section()["show"] is True
    with app.test_request_context():
        session.update(user_role="provider", user_id=provider_client[1])
        assert _rx_section() is None
    with app.test_request_context():
        session.update(user_role="patient", user_id=s["patient"])
        assert _rx_section() is None


def test_empty_states_lists(app, d):
    c, s = d
    for tab in ("draft", "issued", "closed"):
        assert c.get(f"{API}/prescriptions?status={tab}").get_json()["items"] == []
    assert c.get(f"{API}/dashboard").get_json()["recent"] == []
