"""Provider scope (P-02), small-cell suppression, crisis safety override, prescriptions gate (P-01)."""
from datetime import date, datetime, timedelta

import pytest

from extensions import db
from models import (Appointment, Assessment, AuditLog, ClinicalNote, CrisisEvent, DigitalDetoxLog, Prescription,
                    ProviderPatient, User)


def add(app, obj):
    with app.app_context():
        db.session.add(obj)
        db.session.commit()
        return obj.id


def assign(app, provider, patient):
    return add(app, ProviderPatient(provider_id=provider, patient_id=patient, source="manual"))


def audit_rows(app, action):
    with app.app_context():
        return AuditLog.query.filter_by(action=action).all()


# ---------- assigned-only access ----------

def test_unassigned_patient_is_404_everywhere(app, make_user, provider_client, monkeypatch):
    c, pid = provider_client
    mine, other = make_user("patient", email="mine@t.l"), make_user("patient", email="other@t.l")
    assign(app, pid, mine)
    assert c.get(f"/provider/wellness-report/{mine}").status_code == 200
    assert c.get(f"/provider/telehealth/{mine}").status_code == 200
    for url in (f"/provider/wellness-report/{other}", f"/provider/telehealth/{other}"):
        assert c.get(url).status_code == 404
    r = c.post("/provider/api/rx/prescriptions", json={"patient_id": other})  # prescribing is not reachable for an unassigned patient
    assert r.status_code == 404
    r = c.post("/provider/ai-documentation", data={"transcript": "t", "patient_email": "other@t.l"})
    assert r.status_code == 200 and b"No assigned patient" in r.data
    with app.app_context():
        assert Prescription.query.count() == 0 and ClinicalNote.query.count() == 0


def test_dashboard_lists_only_assigned(app, make_user, provider_client):
    c, pid = provider_client
    mine = make_user("patient", name="Assigned Anna")
    make_user("patient", name="Unassigned Uma")
    assert b"Unassigned Uma" not in c.get("/provider/dashboard").data  # zero assignments must not error either
    assign(app, pid, mine)
    html = c.get("/provider/dashboard").get_data(as_text=True)
    assert "Assigned Anna" in html and "Unassigned Uma" not in html


def test_cross_institution_provider_sees_nothing(app, make_user):
    prov = make_user("provider", institution="Other University")
    pat = make_user("patient")
    c = app.test_client()
    from tests.conftest import _login_as
    _login_as(c, app, prov)
    assign(app, prov, pat)  # even a stray row cannot cross institutions
    assert c.get(f"/provider/wellness-report/{pat}").status_code == 404
    ev = add(app, CrisisEvent(user_id=pat, source="chat", severity=3, reason="self_harm"))
    assert b"Patient" not in c.get("/provider/dashboard").data.replace(b"Patients", b"")
    assert c.post(f"/provider/crisis/{ev}/acknowledge").status_code == 404


# ---------- auto assignment ----------

def _book(c, provider_id, time="10:00"):
    return c.post("/patient/schedule", data={
        "date": (date.today() + timedelta(days=3)).isoformat(), "time": time, "appointment_type": "video",
        "provider_id": str(provider_id)})


def test_booking_assigns_provider_once(app, make_user, patient_client):
    c, uid = patient_client
    prov = make_user("provider")
    assert _book(c, prov).status_code == 302
    assert _book(c, prov, "11:00").status_code == 302
    with app.app_context():
        rows = ProviderPatient.query.filter_by(provider_id=prov, patient_id=uid).all()
        assert len(rows) == 1 and rows[0].source == "appointment"
    pc = app.test_client()
    from tests.conftest import _login_as
    _login_as(pc, app, prov)
    assert pc.get(f"/provider/wellness-report/{uid}").status_code == 200


def test_booking_other_institution_provider_refused(app, make_user, patient_client):
    c, _ = patient_client
    prov = make_user("provider", institution="Other University")
    assert _book(c, prov).status_code == 400
    with app.app_context():
        assert ProviderPatient.query.count() == 0 and Appointment.query.count() == 0


def test_accepting_unassigned_request_assigns_and_hides_data_before(app, make_user, provider_client):
    c, pid = provider_client
    p = make_user("patient", name="Requester")
    add(app, Assessment(user_id=p, assessment_type="PHQ-9", score=20))
    appt = add(app, Appointment(user_id=p, date=date.today(), time="TBD", appointment_type="chat_referral",
                                notes="private note text"))
    row = next(a for a in c.get("/provider/appointments").get_json()["appointments"] if a["id"] == appt)
    assert row["patient_name"] == "Requester"
    assert row["patient_health_data"] is None and row["notes"] is None and row["patient_email"] is None
    assert row["patient_id"] is None
    assert c.post(f"/provider/appointments/accept/{appt}").status_code == 200
    with app.app_context():
        assert ProviderPatient.query.filter_by(provider_id=pid, patient_id=p).count() == 1
    row = next(a for a in c.get("/provider/appointments").get_json()["appointments"] if a["id"] == appt)
    assert row["patient_health_data"]["latest_assessment"]["score"] == 20 and row["notes"] == "private note text"


def test_assign_patient_cli(app, make_user):
    prov, pat = make_user("provider", email="pv@t.l"), make_user("patient", email="pt@t.l")
    foreign = make_user("patient", email="fp@t.l", institution="Other University")
    runner = app.test_cli_runner()
    assert runner.invoke(args=["assign-patient", "pv@t.l", "pt@t.l"]).exit_code == 0
    assert runner.invoke(args=["assign-patient", "pv@t.l", "pt@t.l"]).exit_code == 0  # idempotent
    assert runner.invoke(args=["assign-patient", "pv@t.l", "fp@t.l"]).exit_code != 0
    with app.app_context():
        rows = ProviderPatient.query.all()
        assert len(rows) == 1 and rows[0].source == "manual"


# ---------- aggregates and K ----------

def _institution_summary(app, institution="Test University"):
    from flask import session
    from routes.provider import institution_summary
    with app.test_request_context("/"):
        session["user_institution"] = institution
        return institution_summary(institution)


def _patients_with_logs(app, make_user, n, logs):
    for _ in range(n):
        uid = make_user("patient")
        if logs:
            add(app, DigitalDetoxLog(user_id=uid, date=date.today(), screen_time_hours=9, ai_score="Good"))


def test_aggregates_hidden_below_k_and_shown_at_k(app, make_user):
    _patients_with_logs(app, make_user, 4, logs=True)
    out = _institution_summary(app)
    assert all(v is None for v in out.values())
    make_user("patient")  # fifth person, no logs
    out = _institution_summary(app)
    assert out["total_users"] == 5
    assert out["avg_screen_time"] is None and out["high_risk_users"] is None  # only 4 people behind it


def test_aggregates_shown_when_k_people_contribute(app, make_user):
    _patients_with_logs(app, make_user, 5, logs=True)
    out = _institution_summary(app)
    assert out["total_users"] == 5 and out["avg_screen_time"] == 9.0
    assert out["high_risk_users"] == 5 and out["active_users"] == 5


def test_min_group_env(app, make_user, monkeypatch):
    monkeypatch.setenv("MIN_AGGREGATE_GROUP", "2")
    _patients_with_logs(app, make_user, 2, logs=True)
    assert _institution_summary(app)["total_users"] == 2


def test_analytics_page_ok_below_k(app, make_user, provider_client):
    c, _ = provider_client
    _patients_with_logs(app, make_user, 2, logs=True)
    r = c.get("/provider/analytics")
    assert r.status_code == 200 and b"Traceback" not in r.data


# ---------- crisis safety override ----------

def test_crisis_panel_is_institution_wide_without_free_text_and_audited(app, make_user, provider_client):
    c, pid = provider_client
    stranger = make_user("patient", name="Stranger Sam")  # NOT assigned
    foreign = make_user("patient", name="Far Away", institution="Other University")
    ev = add(app, CrisisEvent(user_id=stranger, source="chat", severity=3, reason="code_xyz"))
    add(app, CrisisEvent(user_id=foreign, source="chat", severity=3, reason="code_xyz"))
    html = c.get("/provider/dashboard").get_data(as_text=True)
    assert "Stranger Sam" in html and "Far Away" not in html and "code_xyz" not in html
    assert f"/provider/crisis/{ev}/acknowledge" in html
    rows = audit_rows(app, "view_crisis_panel")
    assert len(rows) == 1 and rows[0].actor_id == pid and rows[0].meta == {"event_ids": [ev]}
    assert c.get(f"/provider/wellness-report/{stranger}").status_code == 404  # the override shows the alert, not the file
    assert c.post(f"/provider/crisis/{ev}/acknowledge").status_code == 302
    ack = audit_rows(app, "ack_crisis")
    assert len(ack) == 1 and ack[0].actor_id == pid and ack[0].target_id == ev
    with app.app_context():
        assert db.session.get(CrisisEvent, ev).acknowledged_by == pid


def test_other_providers_of_institution_also_see_the_alert(app, make_user, provider_client):
    p2 = make_user("provider")
    c2 = app.test_client()
    from tests.conftest import _login_as
    _login_as(c2, app, p2)
    pat = make_user("patient", name="Shared Sam")
    add(app, CrisisEvent(user_id=pat, source="phq9", severity=3, reason="item9"))
    c, _ = provider_client
    assert b"Shared Sam" in c.get("/provider/dashboard").data and b"Shared Sam" in c2.get("/provider/dashboard").data


# ---------- audit rows ----------

def test_audit_view_patient_and_clinical_note(app, make_user, provider_client):
    c, pid = provider_client
    p = make_user("patient", email="aud@t.l")
    assign(app, pid, p)
    c.get(f"/provider/wellness-report/{p}")
    rows = audit_rows(app, "view_patient")
    assert len(rows) == 1 and rows[0].actor_id == pid and rows[0].target_id == p
    c.post("/provider/ai-documentation", data={"transcript": "secret session words", "patient_email": "aud@t.l"})
    note = audit_rows(app, "add_clinical_note")
    assert len(note) == 1 and note[0].target_id == p and not note[0].meta
    with app.app_context():
        assert all("secret session words" not in str(r.meta) for r in AuditLog.query.all())


# ---------- prescriptions gate ----------

def test_prescriptions_404_when_flag_off_and_nothing_written(app, make_user, provider_client, patient_client, monkeypatch):
    monkeypatch.setenv("ENABLE_PRESCRIPTIONS", "0")  # the default is ON since the clinical build; off still hides everything
    c, pid = provider_client
    pc, uid = patient_client
    assign(app, pid, uid)
    assert c.post(f"/provider/send_prescription/{uid}", data={"medication_name": "X", "dosage": "1"}).status_code == 404
    assert pc.get("/patient/my-prescriptions").status_code == 404
    with app.app_context():
        assert Prescription.query.count() == 0 and not audit_rows(app, "send_prescription")


def test_prescriptions_pages_work_when_flag_on(app, make_user, provider_client, patient_client, monkeypatch):
    monkeypatch.setenv("ENABLE_PRESCRIPTIONS", "true")
    c, pid = provider_client
    pc, uid = patient_client
    assign(app, pid, uid)
    # the open form is gone; a counsellor cannot reach any prescribing route (404, nothing written)
    assert c.post(f"/provider/send_prescription/{uid}", data={"medication_name": "X", "dosage": "1"}).status_code == 404
    assert c.post("/provider/api/rx/prescriptions", json={"patient_id": uid}).status_code == 404
    with app.app_context():
        assert Prescription.query.count() == 0 and not audit_rows(app, "send_prescription")
    assert pc.get("/patient/my-prescriptions").status_code == 200


def test_prescription_gate_json_for_api_paths(app, monkeypatch):
    from decorators import prescriptions_required
    monkeypatch.setenv("ENABLE_PRESCRIPTIONS", "0")
    with app.test_request_context("/api/prescriptions"):
        resp, status = prescriptions_required(lambda: "ok")()
        assert status == 404 and resp.get_json() == {"error": "not_found"}
    monkeypatch.setenv("ENABLE_PRESCRIPTIONS", "1")
    with app.test_request_context("/api/prescriptions"):
        assert prescriptions_required(lambda: "ok")() == "ok"
