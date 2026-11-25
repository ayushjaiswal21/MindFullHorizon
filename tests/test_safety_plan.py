"""Safety plan: private, one per student, shared read-only with assigned providers only on request, never logged."""
import json
import logging

from core.extensions import db
from models import AuditLog, ProviderPatient, SafetyPlan

SECRET = "my-very-private-warning-sign-xyz"
FORM = {"warning_signs": SECRET, "coping_alone": "walk", "places_people": "library", "professionals": "Dr A",
        "safer_surroundings": "ask warden", "person_name_0": "Asha", "person_phone_0": "+91 98765 43210"}


def plan_row(app, uid):
    with app.app_context():
        return SafetyPlan.query.filter_by(user_id=uid).first()


def test_pages_need_login_and_patient_role(client, provider_client):
    for path in ("/patient/safety-plan", "/patient/safety-plan/edit"):
        assert client.get(path).status_code == 302
    c, _ = provider_client
    assert c.get("/patient/safety-plan").status_code == 302
    assert c.post("/patient/safety-plan", data=FORM).status_code == 302


def test_empty_state_then_create_view_edit_delete(app, patient_client):
    c, uid = patient_client
    html = c.get("/patient/safety-plan").get_data(as_text=True)
    assert "Make my safety plan" in html and "not a diagnosis" in html
    assert "14416" in html and "1800-599-0019" in html  # helplines come from the config
    r = c.post("/patient/safety-plan", data=FORM)
    assert r.status_code == 302
    html = c.get("/patient/safety-plan").get_data(as_text=True)
    assert SECRET in html and "Asha" in html and "tel:+919876543210" in html and "Print" in html
    c.post("/patient/safety-plan", data=dict(FORM, warning_signs="changed"))
    with app.app_context():
        assert SafetyPlan.query.count() == 1 and SafetyPlan.query.one().warning_signs == "changed"
    c.post("/patient/safety-plan/delete")
    assert plan_row(app, uid) is None


def test_validation_and_limits(app, patient_client):
    c, uid = patient_client
    assert c.post("/patient/safety-plan", data={}).status_code == 400
    assert c.post("/patient/safety-plan", data=dict(FORM, warning_signs="x" * 1001)).status_code == 400
    assert c.post("/patient/safety-plan", data=dict(FORM, person_phone_0="call me <b>")).status_code == 400
    assert plan_row(app, uid) is None
    many = {f"person_name_{i}": f"P{i}" for i in range(5)}
    c.post("/patient/safety-plan", data=many)
    assert len(plan_row(app, uid).help_people) == 5


def test_create_is_idempotent_with_request_id(app, patient_client):
    c, uid = patient_client
    key = {"client_request_id": "abcdef12345678"}
    for _ in range(2):
        assert c.post("/patient/safety-plan", data=dict(FORM, **key)).status_code == 302
    with app.app_context():
        assert SafetyPlan.query.count() == 1
    assert c.post("/patient/safety-plan", data=dict(FORM, client_request_id="bad key!")).status_code == 302  # handler redirect


def test_each_student_sees_only_own_plan(app, patient_client, make_user, login):
    c, uid = patient_client
    c.post("/patient/safety-plan", data=FORM)
    other = make_user("patient")
    c2 = app.test_client()
    with c2.session_transaction() as s:
        s.update(user_id=other, user_email="o@t.l", user_role="patient", user_name="O")
    assert SECRET not in c2.get("/patient/safety-plan").get_data(as_text=True)


def test_content_never_in_logs(app, patient_client, caplog):
    c, uid = patient_client
    with caplog.at_level(logging.DEBUG):
        c.post("/patient/safety-plan", data=FORM)
        c.get("/patient/safety-plan")
        c.post("/patient/safety-plan/sharing", data={"share": "on"})
        c.post("/patient/safety-plan", data=dict(FORM, warning_signs="x" * 2000))  # error path
    assert SECRET not in caplog.text and "Asha" not in caplog.text and "98765" not in caplog.text


def test_plan_text_never_goes_to_the_ai(app, patient_client, monkeypatch):
    c, uid = patient_client
    import ai.gemini_impl as g
    calls = []
    monkeypatch.setattr(g.PROVIDER, "configured", lambda: True)
    for name in ("generate", "generate_content", "chat"):
        if hasattr(g.PROVIDER, name):
            monkeypatch.setattr(g.PROVIDER, name, lambda *a, **k: calls.append(a) or "x")
    c.post("/patient/safety-plan", data=FORM)
    c.get("/patient/safety-plan")
    c.get("/patient/dashboard")
    assert calls == []


def _assign(app, provider, patient):
    with app.app_context():
        db.session.add(ProviderPatient(provider_id=provider, patient_id=patient, source="manual"))
        db.session.commit()


def _provider_client(app, pid):
    c = app.test_client()
    with c.session_transaction() as s:
        s.update(user_id=pid, user_email="p@t.l", user_role="provider", user_name="Prov", user_institution="Test University")
    return c


def test_sharing_defaults_off_and_assigned_provider_reads_read_only_with_audit(app, patient_client, make_user):
    c, uid = patient_client
    prov, stranger = make_user("provider"), make_user("provider")
    _assign(app, prov, uid)
    c.post("/patient/safety-plan", data=FORM)
    assert plan_row(app, uid).share_with_counsellors is False
    pc = _provider_client(app, prov)
    assert SECRET not in pc.get(f"/provider/wellness-report/{uid}").get_data(as_text=True)  # not shared yet
    c.post("/patient/safety-plan/sharing", data={"share": "on"})
    html = pc.get(f"/provider/wellness-report/{uid}").get_data(as_text=True)
    assert SECRET in html and "shared by the student" in html
    with app.app_context():
        rows = AuditLog.query.filter_by(action="view_safety_plan").all()
        assert len(rows) == 1 and rows[0].actor_id == prov and SECRET not in json.dumps(rows[0].meta or {})
        assert AuditLog.query.filter_by(action="safety_plan_share_on").count() == 1
    # read only: no provider route writes the plan, and an unassigned provider cannot open the report at all
    assert pc.post("/patient/safety-plan", data=FORM).status_code == 302
    sc = _provider_client(app, stranger)
    assert sc.get(f"/provider/wellness-report/{uid}").status_code == 404
    c.post("/patient/safety-plan/sharing", data={})  # switch off again
    assert SECRET not in pc.get(f"/provider/wellness-report/{uid}").get_data(as_text=True)


def test_helper_refuses_unassigned_provider_even_when_shared(app, patient_client, make_user):
    from services.safety_plan import shared_plan_for_provider
    c, uid = patient_client
    stranger = make_user("provider")
    c.post("/patient/safety-plan", data=FORM)
    c.post("/patient/safety-plan/sharing", data={"share": "on"})
    with app.app_context():
        assert shared_plan_for_provider(stranger, uid) is None
        assert AuditLog.query.filter_by(action="view_safety_plan").count() == 0


def test_crisis_links_depend_on_plan(app, patient_client):
    c, uid = patient_client
    assert "Make a safety plan" in c.get("/patient/dashboard").get_data(as_text=True)
    assert "Make a safety plan" in c.get("/chat").get_data(as_text=True)
    c.post("/patient/safety-plan", data=FORM)
    for path in ("/patient/dashboard", "/chat", "/patient/assessment"):
        html = c.get(path).get_data(as_text=True)
        assert "Open my safety plan" in html and "Make a safety plan" not in html, path
    assert c.get("/patient/api/safety-plan/link").get_json()["exists"] is True


def test_crisis_reply_is_unchanged_by_the_link(app, patient_client):
    """The fixed crisis reply never depends on the plan: the JS adds the link after the helplines."""
    js = open("static/js/inline_extracted/chat_inline_1.js", encoding="utf-8").read()
    assert js.index("helplineList(lines)") < js.index("safety-plan-line")


def test_export_and_delete_include_plan(app, patient_client):
    c, uid = patient_client
    c.post("/patient/safety-plan", data=FORM)
    data = json.loads(c.post("/account/export").get_data(as_text=True))
    assert data["safety_plans"][0]["warning_signs"] == SECRET and "client_request_id" not in data["safety_plans"][0]
    from tests.conftest import PASSWORD
    c.post("/account/delete", data={"password": PASSWORD})
    with app.app_context():
        assert SafetyPlan.query.count() == 0
