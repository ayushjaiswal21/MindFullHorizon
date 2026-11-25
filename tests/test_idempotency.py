"""Idempotency: replays and concurrent double submits create one row; points award once; invalid keys are rejected."""
import threading
from datetime import timedelta

import pytest

from conftest import _login_as
from core.extensions import db
from models import (Appointment, Assessment, BreathingExerciseLog, Gamification, Goal, JournalEntry, Medication,
                    MedicationLog, MoodLog, PointsLedger, YogaLog)
from utils.gamification import award_points
from utils.timeutil import ist_today

KEY = "req-0123456789"
XHR = {"X-Requested-With": "XMLHttpRequest"}


def count(app, model, **filters):
    with app.app_context():
        return model.query.filter_by(**filters).count()


def gam(app, uid):
    with app.app_context():
        g = Gamification.query.filter_by(user_id=uid).first()
        return (g.points, g.streak) if g else (0, 0)


def test_mood_api_replay_returns_same_row_200(app, patient_client):
    c, uid = patient_client
    first = c.post("/api/mood", json={"value": 6, "client_request_id": KEY})
    again = c.post("/api/mood", json={"value": 6}, headers={"Idempotency-Key": KEY})
    assert first.status_code == 201 and again.status_code == 200
    assert first.get_json()["id"] == again.get_json()["id"]
    assert count(app, MoodLog, user_id=uid) == 1


def test_save_mood_replay_one_mood_one_assessment(app, patient_client):
    c, uid = patient_client
    for _ in range(3):
        r = c.post("/patient/api/save-mood", json={"mood": 7, "client_request_id": KEY}, headers=XHR)
        assert r.status_code == 200 and r.get_json()["success"] is True
    assert count(app, MoodLog, user_id=uid) == 1
    assert count(app, Assessment, user_id=uid, assessment_type="Daily Mood") == 1


def test_keys_are_per_user(app, make_user):
    a, b = make_user("patient"), make_user("patient")
    for uid in (a, b):
        c = app.test_client()
        _login_as(c, app, uid)
        assert c.post("/api/mood", json={"value": 5, "client_request_id": KEY}).status_code == 201
    assert count(app, MoodLog) == 2


@pytest.mark.parametrize("bad", ["short", "has space in it", "x" * 65, "semi;colon-0123", "ünïcode-key-123"])
def test_invalid_keys_rejected_everywhere(app, patient_client, bad):
    c, uid = patient_client
    r = c.post("/api/mood", json={"value": 5}, headers={"Idempotency-Key": bad})
    assert r.status_code == 400 and r.get_json()["error"] == "Invalid request id."
    r = c.post("/patient/api/save-mood", json={"mood": 5, "client_request_id": bad}, headers=XHR)
    assert r.status_code == 400 and r.get_json()["success"] is False
    r = c.post("/patient/api/save-assessment", json={"assessment_type": "PHQ-9", "responses": [0] * 9,
                                                      "client_request_id": bad})
    assert r.status_code == 400
    assert count(app, MoodLog) == 0 and count(app, Assessment) == 0


def test_assessment_replay_same_body_one_row(app, patient_client):
    c, uid = patient_client
    body = {"assessment_type": "PHQ-9", "responses": [1] * 8 + [0], "client_request_id": KEY}
    first = c.post("/patient/api/save-assessment", json=body)
    again = c.post("/patient/api/save-assessment", json=body)
    assert first.status_code == 200 and again.status_code == 200
    a, b = first.get_json(), again.get_json()
    assert a["assessment_id"] == b["assessment_id"] and a["score"] == b["score"] == 8 and a["band"] == b["band"]
    assert a["ai_insights"] == b["ai_insights"] and a["crisis"] is False and b["crisis"] is False
    assert count(app, Assessment, user_id=uid) == 1


def test_assessment_without_key_still_works(app, patient_client):
    c, uid = patient_client
    for _ in range(2):
        assert c.post("/patient/api/save-assessment", json={"assessment_type": "GAD-7", "responses": [0] * 7}).status_code == 200
    assert count(app, Assessment, user_id=uid) == 2


def test_medication_one_log_per_day_and_points_once(app, patient_client):
    c, uid = patient_client
    with app.app_context():
        m = Medication(user_id=uid, name="m", dosage="1", frequency="daily")
        db.session.add(m)
        db.session.commit()
        mid = m.id
    first = c.post("/patient/log-medication", data={"medication_id": mid}).get_json()
    again = c.post("/patient/log-medication", data={"medication_id": mid}).get_json()
    assert first["success"] is True and again["success"] is False and again["already_logged"] is True
    assert count(app, MedicationLog, user_id=uid) == 1
    assert gam(app, uid)[0] == 10


def test_medication_log_dates_are_ist_days(app, patient_client):
    c, uid = patient_client
    with app.app_context():
        m = Medication(user_id=uid, name="m", dosage="1", frequency="daily")
        db.session.add(m)
        db.session.commit()
        mid = m.id
        db.session.add(MedicationLog(user_id=uid, medication_id=mid, log_date=ist_today() - timedelta(days=1)))
        db.session.commit()
    assert c.post("/patient/log-medication", data={"medication_id": mid}).get_json()["success"] is True


def test_appointment_booking_replay_and_double_booking(app, patient_client, make_user):
    c, uid = patient_client
    prov = make_user("provider")
    day = (ist_today() + timedelta(days=3)).isoformat()
    form = {"date": day, "time": "10:30", "appointment_type": "video", "provider_id": str(prov), "client_request_id": KEY}
    assert c.post("/patient/schedule", data=form).status_code == 302
    assert c.post("/patient/schedule", data=form).status_code == 302  # replay: redirect again, no second row
    assert count(app, Appointment, user_id=uid) == 1
    # another patient, same provider slot: slot taken, 409, nothing created
    c2 = app.test_client()
    _login_as(c2, app, make_user("patient"))
    r = c2.post("/patient/schedule", data=dict(form, client_request_id="other-key-12345"))
    assert r.status_code == 409
    assert count(app, Appointment) == 1


def test_chat_referral_replay_and_same_day_duplicate(app, patient_client):
    c, uid = patient_client
    first = c.post("/api/chat/book-appointment", json={"user_message": "hi"}, headers={"Idempotency-Key": KEY})
    again = c.post("/api/chat/book-appointment", json={"user_message": "hi"}, headers={"Idempotency-Key": KEY})
    other = c.post("/api/chat/book-appointment", json={"user_message": "hi"})  # no key, same day: existing request
    assert (first.status_code, again.status_code, other.status_code) == (201, 200, 200)
    assert first.get_json()["id"] == again.get_json()["id"] == other.get_json()["id"]
    assert count(app, Appointment, user_id=uid) == 1


def test_breathing_yoga_journal_goal_replays(app, patient_client):
    c, uid = patient_client
    for _ in range(2):
        c.post("/patient/breathing", data={"exercise_name": "Box", "duration_minutes": "5", "client_request_id": KEY})
        c.post("/patient/yoga", data={"session_name": "Sun", "duration_minutes": "5", "client_request_id": KEY})
        c.post("/patient/journal", data={"title": "t", "content": "a calm day", "client_request_id": KEY})
        c.post("/patient/goals", data={"title": "g", "client_request_id": KEY})
    assert count(app, BreathingExerciseLog, user_id=uid) == 1
    assert count(app, YogaLog, user_id=uid) == 1
    assert count(app, JournalEntry, user_id=uid) == 1
    assert count(app, Goal, user_id=uid) == 1
    assert gam(app, uid)[0] == 20 + 20 + 15  # one award each


def test_api_goal_replay_200_same_goal(app, patient_client):
    c, uid = patient_client
    a = c.post("/patient/api/goals", json={"title": "x", "client_request_id": KEY}, headers=XHR)
    b = c.post("/patient/api/goals", json={"title": "x", "client_request_id": KEY}, headers=XHR)
    assert (a.status_code, b.status_code) == (201, 200) and a.get_json()["goal"]["id"] == b.get_json()["goal"]["id"]


# ---- points ledger and atomic counters ------------------------------------

def test_award_points_ref_replay_awards_once(app, make_user):
    uid = make_user("patient")
    with app.app_context():
        for _ in range(3):
            award_points(uid, 10, "log_medication", ref="medlog:1")
        assert PointsLedger.query.filter_by(user_id=uid).count() == 1
    assert gam(app, uid) == (10, 1)


def test_award_points_daily_cap_and_never_for_mood(app, make_user):
    uid = make_user("patient")
    with app.app_context():
        for i in range(5):
            award_points(uid, 10, "yoga_session", ref=f"yoga:{i}")
        award_points(uid, 10, "mood", ref="mood:1")
        award_points(uid, 10, "assessment", ref="a:1")
    assert gam(app, uid) == (30, 1)


def _race(app, fn, n=2):
    barrier, errors = threading.Barrier(n), []

    def run(i):
        try:
            with app.app_context():
                barrier.wait(timeout=10)
                fn(i)
        except Exception as exc:  # surfaced below
            errors.append(exc)
        finally:
            with app.app_context():
                db.session.remove()
    threads = [threading.Thread(target=run, args=(i,)) for i in range(n)]
    [t.start() for t in threads]
    [t.join(timeout=60) for t in threads]
    assert not errors, errors


def test_two_sessions_award_points_without_lost_update(app, make_user):
    uid = make_user("patient")
    _race(app, lambda i: award_points(uid, 10, "journal_entry", ref=f"journal:{i}"))
    assert gam(app, uid) == (20, 1)  # both awards counted, streak advanced once


def test_two_sessions_same_ref_award_once(app, make_user):
    uid = make_user("patient")
    _race(app, lambda i: award_points(uid, 10, "journal_entry", ref="journal:7"))
    assert gam(app, uid) == (10, 1)


def test_concurrent_double_submit_creates_one_row(app, patient_client):
    c, uid = patient_client
    results = []

    def post(i):
        client = app.test_client()
        _login_as(client, app, uid)
        results.append(client.post("/api/mood", json={"value": 4, "client_request_id": KEY}).status_code)
    _race(app, post)
    assert sorted(results) in ([200, 201], [201, 201]) and count(app, MoodLog, user_id=uid) == 1


def test_concurrent_medication_log_creates_one_row(app, patient_client):
    c, uid = patient_client
    with app.app_context():
        m = Medication(user_id=uid, name="m", dosage="1", frequency="daily")
        db.session.add(m)
        db.session.commit()
        mid = m.id

    def post(i):
        client = app.test_client()
        _login_as(client, app, uid)
        client.post("/patient/log-medication", data={"medication_id": mid})
    _race(app, post)
    assert count(app, MedicationLog, user_id=uid) == 1
    assert gam(app, uid)[0] == 10


def test_concurrent_assessment_double_submit_one_row(app, patient_client):
    c, uid = patient_client
    codes = []

    def post(i):
        client = app.test_client()
        _login_as(client, app, uid)
        codes.append(client.post("/patient/api/save-assessment", json={
            "assessment_type": "GAD-7", "responses": [1] * 7, "client_request_id": KEY}).status_code)
    _race(app, post)
    assert codes == [200, 200] and count(app, Assessment, user_id=uid) == 1
