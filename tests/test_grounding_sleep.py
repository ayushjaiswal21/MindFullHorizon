"""Grounding exercise (points through the shared ledger) and the private sleep log."""
import json
from datetime import timedelta

from models import Gamification, PointsLedger, SleepLog
from utils.timeutil import ist_today

XHR = {"X-Requested-With": "XMLHttpRequest"}


def points(app, uid):
    with app.app_context():
        g = Gamification.query.filter_by(user_id=uid).first()
        return g.points if g else 0


# ---- grounding ----

def test_grounding_page_has_five_steps_and_a_way_out(patient_client):
    c, _ = patient_client
    html = c.get("/patient/grounding").get_data(as_text=True)
    for n in ("5 things you can see", "4 things you can feel", "3 things you can hear", "2 things you can smell", "1 thing you can taste"):
        assert n in html
    assert 'href="#helplines"' in html and 'id="gr-next"' in html and 'id="gr-back"' in html
    assert "not treatment" in html


def test_grounding_pages_need_patient(client, provider_client):
    assert client.get("/patient/grounding").status_code == 302
    assert client.post("/patient/grounding/complete").status_code == 302
    c, _ = provider_client
    assert c.get("/patient/grounding").status_code == 302


def test_grounding_awards_once_per_key_and_caps_daily(app, patient_client):
    c, uid = patient_client
    base = points(app, uid)
    r = c.post("/patient/grounding/complete", headers={**XHR, "Idempotency-Key": "ground-key-0001"})
    assert r.status_code == 200 and r.get_json()["success"] is True
    assert points(app, uid) == base + 20
    c.post("/patient/grounding/complete", headers={**XHR, "Idempotency-Key": "ground-key-0001"})  # replay
    assert points(app, uid) == base + 20
    for i in range(2, 6):
        c.post("/patient/grounding/complete", headers={**XHR, "Idempotency-Key": f"ground-key-000{i}"})
    assert points(app, uid) == base + 60  # three paid awards a day, as breathing
    with app.app_context():
        assert PointsLedger.query.filter_by(user_id=uid, activity_type="grounding_exercise").count() == 5


def test_grounding_requires_a_valid_key(patient_client):
    c, _ = patient_client
    assert c.post("/patient/grounding/complete", headers=XHR).status_code == 400
    assert c.post("/patient/grounding/complete", headers={**XHR, "Idempotency-Key": "no"}).status_code == 400


# ---- sleep log ----

def entry(**kw):
    base = {"night_date": ist_today().isoformat(), "bedtime": "23:30", "wake_time": "07:00", "quality": "4", "note": "ok"}
    return {**base, **kw}


def test_sleep_save_duration_across_midnight_and_page(app, patient_client):
    c, uid = patient_client
    assert c.post("/patient/sleep", data=entry()).status_code == 302
    with app.app_context():
        row = SleepLog.query.one()
        assert row.duration_minutes == 450 and row.user_id == uid and row.quality == 4
    html = c.get("/patient/sleep").get_data(as_text=True)
    assert "7 h 30 min" in html and "<svg" in html and 'class="sc-bar"' in html and "<table" in html
    assert "not a sleep score" in html and "Average: 7 h 30 min" in html


def test_sleep_one_entry_per_night_and_replay(app, patient_client):
    c, _ = patient_client
    c.post("/patient/sleep", data=entry(client_request_id="sleep-key-0001"))
    c.post("/patient/sleep", data=entry(client_request_id="sleep-key-0001"))  # replay: same row
    r = c.post("/patient/sleep", data=entry(client_request_id="sleep-key-0002"))  # same night, new key
    assert r.status_code == 400 and "already logged" in r.get_data(as_text=True)
    with app.app_context():
        assert SleepLog.query.count() == 1


def test_sleep_validation(app, patient_client):
    c, _ = patient_client
    tomorrow = (ist_today() + timedelta(days=1)).isoformat()
    old = (ist_today() - timedelta(days=45)).isoformat()
    for bad in (entry(bedtime="25:00"), entry(wake_time=""), entry(quality="6"), entry(quality="x"), entry(night_date=tomorrow),
                entry(night_date=old), entry(night_date="nope"), entry(bedtime="07:00", wake_time="07:00"),
                entry(bedtime="02:00", wake_time="23:00"), entry(note="n" * 201)):
        assert c.post("/patient/sleep", data=bad).status_code == 400, bad
    with app.app_context():
        assert SleepLog.query.count() == 0


def test_sleep_chart_window_and_average(app, patient_client):
    c, uid = patient_client
    today = ist_today()
    c.post("/patient/sleep", data=entry(night_date=today.isoformat(), bedtime="23:00", wake_time="07:00"))  # 8 h
    c.post("/patient/sleep", data=entry(night_date=(today - timedelta(days=1)).isoformat(), bedtime="00:00", wake_time="06:00"))  # 6 h
    c.post("/patient/sleep", data=entry(night_date=(today - timedelta(days=20)).isoformat()))  # outside 14 days
    html = c.get("/patient/sleep").get_data(as_text=True)
    assert "Average: 7 h 00 min" in html and "over 2 logged nights" in html
    assert html.count('class="sc-bar"') == 2


def test_sleep_is_private_delete_own_only(app, patient_client, make_user):
    c, uid = patient_client
    c.post("/patient/sleep", data=entry(note="private-sleep-note"))
    other = make_user("patient")
    c2 = app.test_client()
    with c2.session_transaction() as s:
        s.update(user_id=other, user_email="o@t.l", user_role="patient", user_name="O")
    assert "private-sleep-note" not in c2.get("/patient/sleep").get_data(as_text=True)
    with app.app_context():
        rid = SleepLog.query.one().id
    assert c2.post(f"/patient/sleep/{rid}/delete").status_code == 404
    with app.app_context():
        assert SleepLog.query.count() == 1
    assert c.post(f"/patient/sleep/{rid}/delete").status_code == 302
    with app.app_context():
        assert SleepLog.query.count() == 0


def test_sleep_gives_no_points_and_is_not_shown_to_counsellors(app, patient_client, make_user):
    c, uid = patient_client
    base = points(app, uid)
    c.post("/patient/sleep", data=entry(note="counsellor-must-not-see"))
    assert points(app, uid) == base
    prov = make_user("provider")
    from core.extensions import db
    from models import ProviderPatient
    with app.app_context():
        db.session.add(ProviderPatient(provider_id=prov, patient_id=uid, source="manual"))
        db.session.commit()
    pc = app.test_client()
    with pc.session_transaction() as s:
        s.update(user_id=prov, user_email="p@t.l", user_role="provider", user_name="P", user_institution="Test University")
    assert "counsellor-must-not-see" not in pc.get(f"/provider/wellness-report/{uid}").get_data(as_text=True)


def test_sleep_in_export_and_deleted_with_account(app, patient_client):
    c, uid = patient_client
    c.post("/patient/sleep", data=entry(note="exported-note"))
    data = json.loads(c.post("/account/export").get_data(as_text=True))
    assert data["sleep_logs"][0]["note"] == "exported-note" and "client_request_id" not in data["sleep_logs"][0]
    from tests.conftest import PASSWORD
    c.post("/account/delete", data={"password": PASSWORD})
    with app.app_context():
        assert SleepLog.query.count() == 0
