"""Patient feature tests: gamification, mood, dashboard empty state, medication, goals, appointments,
digital detox. Split out of test_patient.py (300-line rule); journal/voice logs, the progress API and
landing-page honesty checks are in test_patient_records.py."""
from datetime import date, datetime, timedelta, timezone

import pytest

from core.extensions import db
from utils.timeutil import ist_today
from models import (BreathingExerciseLog, Gamification, Goal, MedicationLog, Medication,
                    MoodLog, Appointment, User)

XHR = {"X-Requested-With": "XMLHttpRequest"}


def _gam(app, uid):
    with app.app_context():
        g = Gamification.query.filter_by(user_id=uid).first()
        return (g.points, g.streak) if g else (0, 0)


def _med(app, uid, name="Sertraline"):
    with app.app_context():
        m = Medication(user_id=uid, name=name, dosage="50mg", frequency="Daily")
        db.session.add(m)
        db.session.commit()
        return m.id


# ---- 1. gamification -------------------------------------------------------

def test_breathing_points_persist(app, patient_client):
    c, uid = patient_client
    c.post("/patient/breathing", data={"exercise_name": "Box", "duration_minutes": "5"})
    assert _gam(app, uid) == (20, 1)


def test_points_have_daily_cap(app, patient_client):
    c, uid = patient_client
    for _ in range(6):
        c.post("/patient/breathing", data={"exercise_name": "Box", "duration_minutes": "5"})
    assert _gam(app, uid)[0] == 60  # cap 3 awards/day


def test_assessment_and_mood_give_no_points(app, patient_client):
    c, uid = patient_client
    c.post("/patient/api/save-mood", json={"mood": 4}, headers=XHR)
    assert _gam(app, uid) == (0, 0)
    from utils.gamification import award_points
    with app.app_context():
        award_points(uid, 20, "assessment")
    assert _gam(app, uid) == (0, 0)


def test_streak_same_day_and_gap(app, patient_client):
    c, uid = patient_client
    c.post("/patient/yoga", data={"session_name": "Sun", "duration_minutes": "10"})
    c.post("/patient/yoga", data={"session_name": "Sun", "duration_minutes": "10"})
    assert _gam(app, uid)[1] == 1
    with app.app_context():
        g = Gamification.query.filter_by(user_id=uid).first()
        g.last_activity = ist_today() - timedelta(days=1)
        g.streak = 4
        db.session.commit()
    c.post("/patient/yoga", data={"session_name": "Sun", "duration_minutes": "10"})
    assert _gam(app, uid)[1] == 5
    with app.app_context():
        g = Gamification.query.filter_by(user_id=uid).first()
        g.last_activity = ist_today() - timedelta(days=5)
        db.session.commit()
    c.post("/patient/yoga", data={"session_name": "Sun", "duration_minutes": "10"})
    assert _gam(app, uid)[1] == 1


def test_page_streak_ignores_duplicate_days(app, patient_client):
    c, uid = patient_client
    now = datetime.now(timezone.utc)
    with app.app_context():
        for d in (0, 0, 1):
            db.session.add(BreathingExerciseLog(user_id=uid, exercise_name="x", duration_minutes=1,
                                                created_at=now - timedelta(days=d)))
        db.session.commit()
    html = c.get("/patient/breathing").get_data(as_text=True)
    assert 'mb-2">2</div>' in html  # two distinct days -> streak 2


# ---- 2. mood ---------------------------------------------------------------

@pytest.mark.parametrize("bad", [0, 11, "abc", None, 2.5, True])
def test_save_mood_rejects_invalid(patient_client, bad):
    c, _ = patient_client
    r = c.post("/patient/api/save-mood", json={"mood": bad}, headers=XHR)
    assert r.status_code == 400


def test_save_mood_stores_note_for_session_user(app, patient_client, make_user):
    c, uid = patient_client
    other = make_user("patient")
    r = c.post("/patient/api/save-mood", json={"mood": 7, "notes": "tired", "user_id": other}, headers=XHR)
    assert r.status_code == 200
    with app.app_context():
        logs = MoodLog.query.all()
        assert [(l.user_id, l.mood_score, l.notes) for l in logs] == [(uid, 7, "tired")]


def test_mood_js_sends_note():
    src = open("static/js/mood.js", encoding="utf-8").read()
    assert "notes" in src


# ---- 3. dashboard empty state ---------------------------------------------

def test_dashboard_no_fake_vitals(patient_client):
    c, _ = patient_client
    html = c.get("/patient/dashboard").get_data(as_text=True)
    for fake in ("72 bpm", "8500", "7.5h", "7/10"):
        assert fake not in html
    assert "No data yet" in html


# ---- 4. medication ---------------------------------------------------------

def test_log_medication_ownership_and_double(app, patient_client, make_user):
    c, uid = patient_client
    other = make_user("patient")
    foreign = _med(app, other)
    assert c.post("/patient/log-medication", data={"medication_id": foreign}, headers=XHR).status_code == 404
    mine = _med(app, uid)
    r = c.post("/patient/log-medication", data={"medication_id": mine}, headers=XHR)
    assert r.status_code == 200 and r.get_json()["success"]
    r = c.post("/patient/log-medication", data={"medication_id": mine}, headers=XHR)
    assert r.get_json()["success"] is False and "already" in r.get_json()["message"].lower()
    with app.app_context():
        assert MedicationLog.query.count() == 1
    assert _gam(app, uid)[0] == 10


def test_log_medication_bad_id(patient_client):
    c, _ = patient_client
    assert c.post("/patient/log-medication", data={"medication_id": "abc"}, headers=XHR).status_code in (400, 404)


def test_medication_page_uses_fetch(app, patient_client):
    c, uid = patient_client
    _med(app, uid)
    html = c.get("/patient/medication").get_data(as_text=True)
    assert "data-med-id" in html


# ---- 5. goals --------------------------------------------------------------

def _goal(app, uid, **kw):
    with app.app_context():
        g = Goal(user_id=uid, title="Walk", category="physical_health", start_date=date.today(), **kw)
        db.session.add(g)
        db.session.commit()
        return g.id


def test_goal_create_bad_target_is_400(patient_client):
    c, _ = patient_client
    r = c.post("/patient/api/goals", json={"title": "x", "target_value": "abc"}, headers=XHR)
    assert r.status_code == 400


def test_goal_put_semantics(app, patient_client, make_user):
    c, uid = patient_client
    gid = _goal(app, uid)
    url = f"/patient/api/goals/{gid}"

    def status():
        with app.app_context():
            return db.session.get(Goal, gid).status

    assert c.put(url, json={"current_value": 2}, headers=XHR).status_code == 200
    assert status() == "active"
    c.put(url, json={"completed": True}, headers=XHR)
    assert status() == "completed"
    c.put(url, json={"current_value": 3}, headers=XHR)  # untouched status
    assert status() == "completed"
    c.put(url, json={"completed": False}, headers=XHR)
    assert status() == "active"
    c.put(url, json={"status": "paused"}, headers=XHR)
    assert status() == "paused"
    assert c.put(url, json={"current_value": "abc"}, headers=XHR).status_code == 400
    assert c.put(url, json={"status": "bogus"}, headers=XHR).status_code == 400


def test_goal_other_user_404(app, patient_client, make_user):
    c, _ = patient_client
    gid = _goal(app, make_user("patient"))
    assert c.put(f"/patient/api/goals/{gid}", json={"completed": True}, headers=XHR).status_code == 404
    assert c.delete(f"/patient/api/goals/{gid}", headers=XHR).status_code == 404


def test_goals_template_no_unsafe_attr(patient_client):
    html = open("templates/goals.html", encoding="utf-8").read()
    assert "| safe" not in html and "|safe" not in html


# ---- 6. appointments -------------------------------------------------------

def _slot(days=3):
    return (date.today() + timedelta(days=days)).isoformat()


def test_schedule_validation(app, patient_client, make_user):
    c, uid = patient_client
    prov = make_user("provider")
    not_prov = make_user("patient")
    ok = {"date": _slot(), "time": "10:30", "appointment_type": "Counselling", "provider_id": str(prov)}
    assert c.post("/patient/schedule", data={"date": _slot()}).status_code == 400
    for patch in ({"date": "2000-01-01"}, {"date": "garbage"}, {"time": "25:99"}, {"time": "x"},
                  {"provider_id": "9999"}, {"provider_id": str(not_prov)}, {"provider_id": "abc"}):
        assert c.post("/patient/schedule", data={**ok, **patch}).status_code == 400, patch
    r = c.post("/patient/schedule", data=ok)
    assert r.status_code == 302
    r = c.post("/patient/schedule", data=ok)  # same slot again
    assert r.status_code == 409
    with app.app_context():
        assert Appointment.query.count() == 1


# ---- 7. digital detox ------------------------------------------------------

def test_detox_validation_and_daily_upsert(app, patient_client):
    from models import DigitalDetoxLog
    c, uid = patient_client
    url = "/patient/api/log-digital-detox"
    good = {"screen_time": 5, "academic_score": 80, "social_interactions": "high"}
    for patch in ({"screen_time": 30}, {"screen_time": "abc"}, {"academic_score": 101},
                  {"social_interactions": "huge"}, {"social_interactions": ""}):
        assert c.post(url, json={**good, **patch}, headers=XHR).status_code == 400, patch
    assert c.post(url, json=good, headers=XHR).status_code == 200
    assert c.post(url, json={**good, "screen_time": 6}, headers=XHR).status_code == 200
    with app.app_context():
        logs = DigitalDetoxLog.query.all()
        assert len(logs) == 1 and logs[0].screen_time_hours == 6
    assert _gam(app, uid)[0] == 15  # second submission the same day earns nothing


def test_detox_js_uses_patient_url():
    src = open("static/js/inline_extracted/digital_detox_inline_1.js", encoding="utf-8").read()
    assert "'/patient/api/log-digital-detox'" in src and "'/api/log-digital-detox'" not in src
