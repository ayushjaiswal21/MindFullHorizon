"""Provider pages: scoping by institution, risk bands, crisis panel, JS free of Jinja."""
import os
import re
from datetime import date, datetime, timedelta

import pytest

from extensions import db
from models import Appointment, Assessment, ClinicalNote, CrisisEvent, DigitalDetoxLog, Prescription, ProviderPatient

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_DIR = os.path.join(ROOT, "static", "js")
OWNED_JS = [
    "provider_dashboard.js", "scripts.js", "modal-utils.js",
    "inline_extracted/telehealth_inline_1.js", "inline_extracted/analytics_inline_1.js",
    "inline_extracted/wellness_report_inline_1.js", "inline_extracted/signup_inline_1.js",
    "inline_extracted/blog_create_inline_1.js", "inline_extracted/blog_edit_inline_1.js",
    "inline_extracted/blog_list_inline_1.js", "inline_extracted/base_inline_1.js",
    "inline_extracted/base_inline_2.js", "inline_extracted/base_inline_3.js",
    "inline_extracted/base_inline_4.js",
]


@pytest.mark.parametrize("name", OWNED_JS)
def test_static_js_has_no_jinja(name):
    path = os.path.join(JS_DIR, name)
    if not os.path.exists(path):
        pytest.skip("missing")
    text = open(path, encoding="utf-8").read()
    assert "{{" not in text and "{%" not in text, name


def add(app, obj):
    with app.app_context():
        db.session.add(obj)
        db.session.commit()
        return obj.id


def assign(app, provider, *patients):
    """P-02: a provider only sees patients linked by a ProviderPatient row."""
    for p in patients:
        add(app, ProviderPatient(provider_id=provider, patient_id=p, source="manual"))


def test_dashboard_exposes_urls_for_js(app, provider_client):
    c, _ = provider_client
    html = c.get("/provider/dashboard").get_data(as_text=True)
    assert 'id="provider-config"' in html
    assert 'data-appointments-url="/provider/appointments"' in html
    assert 'data-accept-url="/provider/appointments/accept/0"' in html
    assert 'data-reject-url="/provider/appointments/reject/0"' in html
    assert 'data-report-url="/provider/wellness-report/0"' in html
    assert 'data-message-url="/api/message"' in html


def test_institution_match_is_exact_not_keyword(app, make_user, provider_client):
    c, pid = provider_client  # Test University
    ids = [make_user("patient", email="same@t.l", institution="  test UNIVERSITY ", name="Same Student"),
           make_user("patient", email="other@t.l", institution="Other University", name="Other Student"),
           make_user("patient", email="kw@t.l", institution="Test College", name="Keyword Student")]
    assign(app, pid, *ids)  # even stray links cannot cross institutions
    html = c.get("/provider/dashboard").get_data(as_text=True)
    assert "Same Student" in html
    assert "Other Student" not in html and "Keyword Student" not in html


def test_risk_comes_from_phq_gad_not_screen_time(app, make_user, provider_client):
    c, pid = provider_client
    hi = make_user("patient", name="Screen Only")
    sev = make_user("patient", name="Severe Phq")
    mod = make_user("patient", name="Moderate Gad")
    assign(app, pid, hi, sev, mod)
    add(app, DigitalDetoxLog(user_id=hi, date=date.today(), screen_time_hours=11, ai_score="Good"))
    add(app, Assessment(user_id=sev, assessment_type="PHQ-9", score=17))
    add(app, Assessment(user_id=mod, assessment_type="GAD-7", score=12))
    html = c.get("/provider/dashboard").get_data(as_text=True)
    risks = dict(re.findall(r"data-risk-name=\"([^\"]+)\" data-risk=\"(\w+)\"", html))
    assert risks == {"Screen Only": "Low", "Severe Phq": "High", "Moderate Gad": "Medium"}


def test_latest_detox_and_note_use_newest(app, make_user, provider_client):
    c, pid = provider_client
    p = make_user("patient", name="Dated")
    assign(app, pid, p)
    add(app, DigitalDetoxLog(user_id=p, date=date.today() - timedelta(days=5), screen_time_hours=2, ai_score="OldScore"))
    add(app, DigitalDetoxLog(user_id=p, date=date.today(), screen_time_hours=2, ai_score="NewScore"))
    add(app, ClinicalNote(provider_id=pid, patient_id=p, session_date=datetime(2020, 1, 1)))
    add(app, ClinicalNote(provider_id=pid, patient_id=p, session_date=datetime(2024, 2, 3)))
    html = c.get("/provider/dashboard").get_data(as_text=True)
    assert "2024-02-03" in html and "2020-01-01" not in html


def test_appointments_api_bands_and_none(app, make_user, provider_client):
    c, pid = provider_client
    a = make_user("patient", name="PhqPatient")
    b = make_user("patient", name="GadPatient")
    n = make_user("patient", name="NoData")
    assign(app, pid, a, b, n)
    add(app, Assessment(user_id=a, assessment_type="PHQ-9", score=20))
    add(app, Assessment(user_id=b, assessment_type="GAD-7", score=12))
    for i, uid in enumerate((a, b, n)):  # one slot per appointment: a provider cannot hold two live ones at the same time
        add(app, Appointment(user_id=uid, provider_id=pid, date=date.today(), time=f"1{i}:00", appointment_type="video"))
    data = c.get("/provider/appointments").get_json()
    by = {x["patient_name"]: x for x in data["appointments"]}
    assert by["PhqPatient"]["urgency_level"] == "high"
    assert by["PhqPatient"]["patient_health_data"]["latest_assessment"]["severity"] == "Severe"
    assert by["GadPatient"]["urgency_level"] == "normal"
    assert by["GadPatient"]["patient_health_data"]["latest_assessment"]["severity"] == "Moderate"
    assert by["NoData"]["urgency_level"] == "normal"


def test_accept_does_not_claim_other_institution(app, make_user, provider_client):
    c, pid = provider_client
    foreign = make_user("patient", institution="Other University")
    local = make_user("patient")
    fa = add(app, Appointment(user_id=foreign, date=date.today(), time="10:00", appointment_type="video"))
    la = add(app, Appointment(user_id=local, date=date.today(), time="11:00", appointment_type="video"))
    assert c.post(f"/provider/appointments/accept/{fa}").status_code == 403
    assert c.post(f"/provider/appointments/reject/{fa}", json={"reason": "x"}).status_code == 403
    r = c.post(f"/provider/appointments/accept/{la}")
    assert r.status_code == 200
    with app.app_context():
        assert db.session.get(Appointment, la).provider_id == pid
        assert db.session.get(Appointment, fa).provider_id is None


def test_patient_scoped_pages_blocked_for_other_institution(app, make_user, provider_client, monkeypatch):
    c, pid = provider_client
    foreign = make_user("patient", institution="Other University")
    local = make_user("patient")
    assign(app, pid, local, foreign)
    assert c.get(f"/provider/wellness-report/{foreign}").status_code == 404
    assert c.get(f"/provider/wellness-report/{local}").status_code == 200
    # The old open prescription form is gone (design 5.3): 404 for every patient, flag on or off, nothing written.
    for pid_ in (foreign, local):
        assert c.post(f"/provider/send_prescription/{pid_}", data={"medication_name": "X", "dosage": "1"}).status_code == 404
    with app.app_context():
        assert Prescription.query.count() == 0
    assert c.get(f"/provider/telehealth/{foreign}").status_code == 404


def test_appointment_row_alone_does_not_make_patient_reachable(app, make_user, provider_client):
    # P-02: reach comes from a ProviderPatient row (created when the patient books), not from an appointment row.
    c, pid = provider_client
    foreign = make_user("patient", institution="Other University")
    add(app, Appointment(user_id=foreign, provider_id=pid, date=date.today(), time="9:00", appointment_type="video"))
    assert c.get(f"/provider/wellness-report/{foreign}").status_code == 404


def test_wellness_report_page_wiring(app, make_user, provider_client):
    c, pid = provider_client
    p = make_user("patient", name="Report Person")
    assign(app, pid, p)
    html = c.get(f"/provider/wellness-report/{p}").get_data(as_text=True)
    assert "send_prescription" not in html and "Send prescription" not in html  # old form removed
    assert 'id="meds-panel"' in html  # read-only medications panel
    assert 'id="report-data"' in html and "Report Person" in html
    assert 'nonce="{ g' not in html


def test_telehealth_room_rendered_server_side(app, make_user, provider_client):
    c, pid = provider_client
    p = make_user("patient", name="Tele Person")
    assign(app, pid, p)
    html = c.get(f"/provider/telehealth/{p}").get_data(as_text=True)
    assert f'data-room="telehealth_room_{p}"' in html
    assert "cdnjs.cloudflare.com/ajax/libs/socket.io" not in html  # base.html is the single socket.io source


def test_analytics_page_renders(app, make_user, provider_client):
    c, _ = provider_client
    p = make_user("patient")
    add(app, DigitalDetoxLog(user_id=p, date=date.today(), screen_time_hours=3, ai_score="Good"))
    r = c.get("/provider/analytics")
    assert r.status_code == 200
    assert 'id="analytics-data"' in r.get_data(as_text=True)


def test_ai_documentation_post(app, make_user, provider_client):
    c, pid = provider_client
    p = make_user("patient", email="doc@t.l")
    assign(app, pid, p)
    r = c.post("/provider/ai-documentation", data={"transcript": "session text", "patient_email": "doc@t.l"})
    assert r.status_code == 200
    with app.app_context():
        assert ClinicalNote.query.filter_by(patient_id=p).count() == 1


def test_crisis_panel_and_acknowledge(app, make_user, provider_client, login):
    c, pid = provider_client
    local = make_user("patient", name="Crisis Local")
    foreign = make_user("patient", institution="Other University", name="Crisis Foreign")
    ev = add(app, CrisisEvent(user_id=local, source="chat", severity=3, reason="self_harm"))
    add(app, CrisisEvent(user_id=foreign, source="chat", severity=3, reason="self_harm"))
    html = c.get("/provider/dashboard").get_data(as_text=True)
    assert "Crisis Local" in html and "Crisis Foreign" not in html
    assert f"/provider/crisis/{ev}/acknowledge" in html
    # a patient may not acknowledge
    pc = app.test_client()
    login_user = make_user("patient", email="x@t.l")
    with pc.session_transaction() as s:
        s.update(user_id=login_user, user_email="x@t.l", user_role="patient", user_name="X", user_institution="Test University")
    assert pc.post(f"/provider/crisis/{ev}/acknowledge").status_code in (302, 403)
    with app.app_context():
        assert db.session.get(CrisisEvent, ev).acknowledged_at is None
    assert c.post(f"/provider/crisis/{ev}/acknowledge").status_code == 302
    with app.app_context():
        e = db.session.get(CrisisEvent, ev)
        assert e.acknowledged_at is not None and e.acknowledged_by == pid
    assert f"/provider/crisis/{ev}/acknowledge" not in c.get("/provider/dashboard").get_data(as_text=True)


def test_crisis_ack_foreign_event_404(app, make_user, provider_client):
    c, _ = provider_client
    foreign = make_user("patient", institution="Other University")
    ev = add(app, CrisisEvent(user_id=foreign, source="chat", severity=3, reason="x"))
    assert c.post(f"/provider/crisis/{ev}/acknowledge").status_code == 404


def test_login_has_no_demo_credentials_and_signup_has_consent(client):
    login = client.get("/login").get_data(as_text=True)
    assert "fillDemo" not in login and "patient@example.com" not in login
    signup = client.get("/signup").get_data(as_text=True)
    assert 'value="provider"' not in signup
    assert 'name="invite_code"' in signup
    assert 'name="consent"' in signup and "required" in signup
    assert "52K" not in signup and "end-to-end" not in signup


def test_base_has_no_dangling_icons_and_single_socketio(client):
    html = client.get("/login").get_data(as_text=True)
    # every static file the page references must exist (the old base pointed at icons that were never shipped)
    for ref in set(re.findall(r'(?:src|href)="(/static/[^"?#]+)', html + client.get("/login").get_data(as_text=True))):
        assert os.path.exists(os.path.join(ROOT, ref.lstrip("/").replace("/", os.sep))), ref
    assert "icon-192x192" not in html  # the legacy manifest icon name
    assert html.count("socket.io.min.js") == 1
    assert html.count("chart.umd.min.js") == 1


def test_long_assessment_titles_count(app, make_user, provider_client):
    c, provider_id = provider_client
    p = make_user("patient", name="Old Title")
    assign(app, provider_id, p)
    add(app, Assessment(user_id=p, assessment_type="PHQ-9 Depression Screening", score=22))
    html = c.get("/provider/dashboard").get_data(as_text=True)
    assert 'data-risk-name="Old Title" data-risk="High"' in html
