"""Redesigned patient pages: render, copy rules, safety hooks, and the small routes they need."""
import json
import os
import re
from datetime import date, datetime, timedelta

import pytest

from core.extensions import db
from models import Appointment, Assessment, Goal, Medication, MoodLog

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PAGES = ["/patient/dashboard", "/patient/assessment", "/patient/progress", "/patient/goals",
         "/patient/schedule", "/profile", "/patient/medication"]

EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿⭐⬆️⏱⏰]")
FORBIDDEN_PHRASES = ["Transform your", "Unlock your", "Revolutionize", "Powered by AI", "Made with AI",
                     "AI-powered", "Oops", "rounded-full", "bg-gradient", "Total Points", "Badges Earned"]
MY_JS = ["assessment-fixes.js", "mood.js", "medication.js", "patient-common.js",
         "inline_extracted/patient_dashboard_inline_1.js", "inline_extracted/progress_inline_1.js",
         "inline_extracted/goals_inline_1.js", "inline_extracted/schedule_inline_1.js"]
MY_TEMPLATES = ["patient_dashboard.html", "assessment.html", "progress.html", "goals.html", "schedule.html",
                "profile.html", "medication.html", "my_prescriptions.html", "patient_mood_entry.html",
                "patient_macros.html"]


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def _seed(app, uid, provider_id):
    with app.app_context():
        db.session.add(MoodLog(user_id=uid, mood_score=6, notes="ok"))
        db.session.add(MoodLog(user_id=uid, mood_score=8))
        db.session.add(Assessment(user_id=uid, assessment_type="PHQ-9", score=11, responses=[1] * 9,
                                  ai_insights=json.dumps({"summary": "A summary.", "recommendations": ["Walk"],
                                                          "resources": ["Tele-MANAS: 14416"]})))
        db.session.add(Assessment(user_id=uid, assessment_type="GAD-7", score=4, responses=[0] * 7,
                                  created_at=datetime.utcnow() - timedelta(days=2)))
        db.session.add(Assessment(user_id=uid, assessment_type="Daily Mood", score=7, responses={"mood": 7},
                                  created_at=datetime.utcnow() - timedelta(days=3)))
        db.session.add(Goal(user_id=uid, title="Walk daily", category="physical_health", target_value=30,
                            current_value=10, unit="minutes", start_date=date.today()))
        db.session.add(Medication(user_id=uid, name="Vitamin D", dosage="1 tablet", frequency="Daily"))
        db.session.add(Appointment(user_id=uid, provider_id=provider_id, date=date.today() + timedelta(days=3),
                                   time="10:00", appointment_type="therapy", status="pending"))
        db.session.commit()


def _clean(html, url):
    assert "—" not in html, f"em dash on {url}"
    assert "–" not in html, f"en dash on {url}"
    assert not EMOJI.search(html), f"emoji on {url}"
    for phrase in FORBIDDEN_PHRASES:
        assert phrase not in html, f"{phrase!r} on {url}"
    assert not re.search(r"\son(click|change|submit|load|input)=", html), f"inline handler on {url}"


@pytest.mark.parametrize("url", PAGES)
def test_pages_render_empty_and_clean(patient_client, url):
    c, _ = patient_client
    r = c.get(url)
    assert r.status_code == 200, url
    _clean(r.get_data(as_text=True), url)


@pytest.mark.parametrize("url", PAGES)
def test_pages_render_with_data_and_clean(app, patient_client, make_user, url):
    c, uid = patient_client
    _seed(app, uid, make_user("provider"))
    r = c.get(url)
    assert r.status_code == 200, url
    _clean(r.get_data(as_text=True), url)


def test_pages_need_login(client):
    for url in PAGES:
        assert client.get(url).status_code in (302, 401), url


def test_dashboard_empty_states_and_helplines(patient_client):
    c, _ = patient_client
    html = c.get("/patient/dashboard").get_data(as_text=True)
    assert "No data yet" in html
    assert "No screenings yet" in html
    assert "No upcoming appointments" in html
    assert 'id="mood-trend"' in html and "skeleton" in html
    assert 'id="save-mood-btn"' in html and 'id="mood-notes"' in html
    assert "14416" in html and "1800-599-0019" in html and "112" in html


def test_dashboard_with_data_shows_real_numbers(app, patient_client, make_user):
    c, uid = patient_client
    _seed(app, uid, make_user("provider"))
    html = c.get("/patient/dashboard").get_data(as_text=True)
    assert "Moderate" in html and "11" in html  # newest screening is the PHQ-9 with 11
    assert "Pending" in html


def test_dashboard_hides_prescriptions_when_flag_off(patient_client, monkeypatch):
    monkeypatch.setenv("ENABLE_PRESCRIPTIONS", "0")  # default is ON since the clinical build
    c, _ = patient_client
    assert "/patient/my-prescriptions" not in c.get("/patient/dashboard").get_data(as_text=True)


def test_dashboard_shows_prescriptions_when_enabled(patient_client, monkeypatch):
    monkeypatch.setenv("ENABLE_PRESCRIPTIONS", "1")
    c, _ = patient_client
    assert "/patient/my-prescriptions" in c.get("/patient/dashboard").get_data(as_text=True)


def test_assessment_page_structure(patient_client):
    c, _ = patient_client
    html = c.get("/patient/assessment").get_data(as_text=True)
    assert 'data-assessment-type="PHQ-9"' in html and 'data-assessment-type="GAD-7"' in html
    assert "<fieldset" in html and "<legend" in html
    assert 'id="assessment-progress"' in html
    assert "not a diagnosis" in html
    assert "14416" in html
    assert 'id="item9-note"' in html and 'id="crisis-slot"' in html


def test_assessment_page_has_no_exclamation_in_copy(patient_client):
    c, _ = patient_client
    html = c.get("/patient/assessment").get_data(as_text=True)
    body = html.split('<div class="container section">', 1)[1].split("</main>")[0]
    text = re.sub(r"<[^>]+>", " ", re.sub(r"<script.*?</script>", "", body, flags=re.S))
    assert "!" not in text


def test_phq9_has_nine_items_and_item9_is_scale():
    q = json.loads(_read("static", "questions.json"))["PHQ-9"]["questions"]
    assert len(q) == 9 and q[8]["id"] == "phq9_9" and q[8]["type"] == "scale"
    assert len(json.loads(_read("static", "questions.json"))["GAD-7"]["questions"]) == 7


def test_assessment_js_keeps_crisis_flow():
    src = _read("static", "js", "assessment-fixes.js")
    assert "d.crisis" in src and "crisis-banner" in src and "d.helplines" in src
    assert "assessment_type: state.key" in src and "contextual_responses" in src
    assert "Question ' + (state.i + 1) + ' of '" in src


def test_assessment_js_shows_crisis_payload_whatever_the_status():
    src = _read("static", "js", "assessment-fixes.js")
    crisis_at = src.index("if (d && d.crisis)")
    assert crisis_at < src.index("if (r.ok && d && d.success)")  # crisis is checked before success
    branch = src[crisis_at:src.index("failSave((d && d.message)")]
    assert "crisisBanner(d.helplines)" in branch and "could not be saved" in branch
    assert "helplines-fallback" in src  # empty payload helplines fall back to the server-rendered list
    assert "state.standard[8] > 0" in src  # item 9 positive keeps the banner even if the response is unreadable


def test_assessment_page_has_helplines_fallback(patient_client):
    c, _ = patient_client
    html = c.get("/patient/assessment").get_data(as_text=True)
    assert 'id="helplines-fallback"' in html
    assert html.split('id="helplines-fallback"', 1)[1].split("</div>", 1)[0].count("tel:") == 3


def test_item9_still_returns_crisis_payload(patient_client):
    c, _ = patient_client
    r = c.post("/patient/api/save-assessment",
               json={"assessment_type": "PHQ-9", "responses": [0, 0, 0, 0, 0, 0, 0, 0, 1]})
    d = r.get_json()
    assert r.status_code == 200 and d["crisis"] is True and d["helplines"]


@pytest.mark.parametrize("name", MY_JS)
def test_my_js_is_clean(name):
    src = _read("static", "js", *name.split("/"))
    assert "{{" not in src and "{%" not in src, name
    assert not re.search(r"(?<![.\w])(alert|confirm)\(", src), name
    assert not EMOJI.search(src) and "—" not in src, name
    assert not re.search(r"\.on[a-z]+\s*=", src.replace(".onclick = null", "")), name


@pytest.mark.parametrize("name", MY_TEMPLATES)
def test_my_templates_are_clean(name):
    src = _read("templates", name)
    assert not EMOJI.search(src) and "—" not in src and "–" not in src, name
    assert not re.search(r"\son(click|change|submit|load|input)=", src), name
    assert "bg-gradient" not in src and "rounded-full" not in src, name
    assert "style=" not in src, name


def test_schedule_empty_state_and_form(patient_client):
    c, _ = patient_client
    html = c.get("/patient/schedule").get_data(as_text=True)
    assert 'class="empty-state"' in html and "No appointments yet" in html
    assert 'name="date"' in html and 'name="time"' in html and 'name="provider_id"' in html
    assert "14416" in html


def test_schedule_conflict_error_is_inline(app, patient_client, make_user):
    c, uid = patient_client
    prov = make_user("provider")
    slot = {"date": (date.today() + timedelta(days=4)).isoformat(), "time": "10:00",
            "appointment_type": "therapy", "provider_id": str(prov)}
    assert c.post("/patient/schedule", data=slot).status_code == 302
    other = make_user("patient")
    c2 = app.test_client()
    from conftest import _login_as
    _login_as(c2, app, other)
    r = c2.post("/patient/schedule", data=slot)
    html = r.get_data(as_text=True)
    assert r.status_code in (400, 409)
    assert 'id="schedule-error"' in html and "already booked" in html
    assert 'aria-invalid="true"' in html
    assert slot["date"] in html  # the form keeps what was typed


def test_schedule_lists_and_cancels_own_appointment(app, patient_client, make_user):
    c, uid = patient_client
    prov = make_user("provider")
    _seed(app, uid, prov)
    with app.app_context():
        appt_id = Appointment.query.filter_by(user_id=uid).first().id
    html = c.get("/patient/schedule").get_data(as_text=True)
    assert "badge-warning" in html and "data-confirm" in html and f"/patient/appointments/{appt_id}/cancel" in html
    assert c.post(f"/patient/appointments/{appt_id}/cancel").status_code == 302
    with app.app_context():
        assert db.session.get(Appointment, appt_id).status == "cancelled"


def test_cannot_cancel_someone_elses_appointment(app, patient_client, make_user):
    c, uid = patient_client
    other = make_user("patient")
    with app.app_context():
        a = Appointment(user_id=other, date=date.today() + timedelta(days=2), time="09:00",
                        appointment_type="therapy", status="pending")
        db.session.add(a)
        db.session.commit()
        aid = a.id
    c.post(f"/patient/appointments/{aid}/cancel")
    with app.app_context():
        assert db.session.get(Appointment, aid).status == "pending"


def test_prescriptions_page_follows_flag(patient_client, monkeypatch):
    c, _ = patient_client
    monkeypatch.setenv("ENABLE_PRESCRIPTIONS", "0")
    r = c.get("/patient/my-prescriptions")
    if r.status_code == 200:  # the route may also 404 when the flag is off
        html = r.get_data(as_text=True)
        assert "This feature is not available" in html and "/patient/dashboard" in html
    else:
        assert r.status_code == 404
    monkeypatch.setenv("ENABLE_PRESCRIPTIONS", "1")
    r = c.get("/patient/my-prescriptions")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "My prescriptions" in html and "No prescriptions yet" in html
    _clean(html, "/patient/my-prescriptions")


def test_profile_has_data_card(patient_client):
    c, _ = patient_client
    html = c.get("/profile").get_data(as_text=True)
    assert "Your data" in html and "/account/data" in html
    assert 'name="name"' in html and 'name="email"' in html and 'name="institution"' in html
    assert "never earn points" in html


def test_progress_empty_and_with_data(app, patient_client, make_user):
    c, uid = patient_client
    html = c.get("/patient/progress").get_data(as_text=True)
    assert "n/a" in html and 'id="progress-data"' in html and "No goals yet" in html
    _seed(app, uid, make_user("provider"))
    html = c.get("/patient/progress").get_data(as_text=True)
    assert "Walk daily" in html and "Moderate" in html and 'id="moodChart"' in html


def test_medication_page_keeps_ids(app, patient_client):
    c, uid = patient_client
    with app.app_context():
        db.session.add(Medication(user_id=uid, name="Vitamin D", dosage="1", frequency="Daily"))
        db.session.commit()
    html = c.get("/patient/medication").get_data(as_text=True)
    assert "log-med-form" in html and "data-med-id" in html and 'id="med-feedback"' in html
    assert 'name="name"' in html and 'name="dosage"' in html and 'name="frequency"' in html
