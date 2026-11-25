"""Reminder emails: settings, double opt-in, signed tokens and unsubscribe."""
import json
import re
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from core.extensions import db
from models import Job, ReminderPref, User
from services import reminders as rem
from utils.jobs import run_once
from utils.timeutil import ist_today, utcnow
from tests.reminder_support import *  # noqa: F401,F403  (autouse `mail` fixture and helpers)
from tests.reminder_support import SENT, pref_of, turn_on, job, queued, token_from, activate  # noqa: F401


# ---- settings page ----

def test_pages_need_patient_login(client, provider_client):
    assert client.get("/patient/reminders").status_code == 302
    assert client.post("/patient/reminders", data={"frequency": "daily", "hour": "8"}).status_code == 302
    assert provider_client[0].get("/patient/reminders").status_code == 302


def test_smtp_unset_shows_honest_note_and_saves_nothing(app, patient_client, monkeypatch):
    monkeypatch.delenv("SMTP_HOST")
    c, uid = patient_client
    html = c.get("/patient/reminders").get_data(as_text=True)
    assert "Email is not set up on this server" in html and "disabled" in html
    assert turn_on(c).status_code == 400
    assert pref_of(app, uid) is None


def test_off_by_default_and_validation(app, patient_client):
    c, uid = patient_client
    assert "Off" in c.get("/patient/reminders").get_data(as_text=True)
    for bad in ({"frequency": "hourly", "hour": "8"}, {"frequency": "daily", "hour": "24"}, {"frequency": "daily", "hour": "x"},
                {"frequency": "weekly", "hour": "8", "weekday": "9"}):
        assert c.post("/patient/reminders", data=bad).status_code == 400
    assert pref_of(app, uid) is None


# ---- double opt-in ----

def test_nothing_is_sent_until_confirmed(app, patient_client):
    c, uid = patient_client
    assert turn_on(c).status_code == 302
    pref = pref_of(app, uid)
    assert pref.status == "pending" and pref.confirmed_at is None
    assert "Waiting for your confirmation" in c.get("/patient/reminders").get_data(as_text=True)
    with app.app_context():
        run_once("t")
        assert Job.query.filter_by(kind="reminder_send").count() == 1  # the confirmation mail only
    assert len(SENT) == 1 and "confirm" in SENT[0].body
    with app.app_context():
        email = db.session.get(User, uid).email
    assert SENT[0].to == email  # only the account address, never one typed by the user


def test_get_of_confirm_link_does_not_activate_post_does(app, patient_client, client):
    c, uid = patient_client
    turn_on(c)
    with app.app_context():
        run_once("t")
    token = token_from(SENT[0].body, "confirm")
    anon = app.test_client()  # opened in another browser, not signed in
    r = anon.get(f"/patient/reminders/confirm/{token}")
    assert r.status_code == 200 and "Yes, turn on reminders" in r.get_data(as_text=True)
    assert pref_of(app, uid).status == "pending"  # a mail scanner opening the link changes nothing
    assert anon.post(f"/patient/reminders/confirm/{token}").status_code == 200
    pref = pref_of(app, uid)
    assert pref.status == "active" and pref.confirmed_at
    with app.app_context():
        assert Job.query.filter_by(kind="reminder_send").count() == 2  # confirmation plus the first reminder


@pytest.mark.parametrize("mutate", ["tamper", "garbage", "truncate"])
def test_tampered_confirm_tokens_are_refused(app, patient_client, mutate):
    c, uid = patient_client
    turn_on(c)
    with app.app_context():
        run_once("t")
    token = token_from(SENT[0].body, "confirm")
    bad = {"tamper": token[:-3] + ("AAA" if not token.endswith("AAA") else "BBB"), "garbage": "not-a-token", "truncate": token[:20]}[mutate]
    anon = app.test_client()
    assert anon.get(f"/patient/reminders/confirm/{bad}").status_code == 400
    assert anon.post(f"/patient/reminders/confirm/{bad}").status_code == 400
    assert pref_of(app, uid).status == "pending"


def test_expired_token_is_refused(app, patient_client, monkeypatch):
    c, uid = patient_client
    turn_on(c)
    with app.app_context():
        run_once("t")
    token = token_from(SENT[0].body, "confirm")
    monkeypatch.setattr(rem, "CONFIRM_MAX_AGE", -1)
    r = app.test_client().post(f"/patient/reminders/confirm/{token}")
    assert r.status_code == 400 and "expired" in r.get_data(as_text=True)
    assert pref_of(app, uid).status == "pending"


def test_old_link_dies_when_settings_are_saved_again_or_email_changes(app, patient_client):
    c, uid = patient_client
    turn_on(c)
    with app.app_context():
        run_once("t")
    old = token_from(SENT[0].body, "confirm")
    turn_on(c, hour="9")  # new nonce
    anon = app.test_client()
    assert anon.post(f"/patient/reminders/confirm/{old}").status_code == 400
    with app.app_context():
        run_once("t")
    new = token_from(SENT[1].body, "confirm")
    with app.app_context():
        db.session.get(User, uid).email = "changed@test.local"
        db.session.commit()
    assert anon.post(f"/patient/reminders/confirm/{new}").status_code == 400  # address no longer the one asked about


def test_confirm_token_cannot_confirm_another_user(app, patient_client, make_user):
    c, uid = patient_client
    other = make_user("patient")
    with app.app_context():
        db.session.add(ReminderPref(user_id=other, nonce="n" * 8))
        db.session.commit()
    turn_on(c)
    with app.app_context():
        token = rem.confirm_token(SimpleNamespace(id=uid, email="x@y.z"), SimpleNamespace(nonce="whatever"))
    assert app.test_client().post(f"/patient/reminders/confirm/{token}").status_code == 400
    assert pref_of(app, other).status == "pending"


# ---- unsubscribe ----

def test_unsubscribe_one_click_get_and_post_and_bad_token(app, patient_client):
    c, uid = patient_client
    activate(app, c, uid)
    with app.app_context():
        rem.reminder_send(queued(app))
        db.session.commit()
    token = token_from(SENT[-1].body, "unsubscribe")
    anon = app.test_client()
    assert anon.get("/patient/reminders/unsubscribe/forged").status_code == 400
    assert pref_of(app, uid) is not None
    assert anon.get(f"/patient/reminders/unsubscribe/{token}").status_code == 200
    assert pref_of(app, uid) is None
    activate(app, c, uid)
    with app.app_context():
        tok = rem.unsubscribe_token(uid)
    assert anon.post(f"/patient/reminders/unsubscribe/{tok}").status_code == 200  # mail client one-click
    assert pref_of(app, uid) is None


def test_unsubscribe_token_never_expires_but_is_user_bound(app, patient_client, make_user):
    c, uid = patient_client
    other = make_user("patient")
    activate(app, c, uid)
    with app.app_context():
        db.session.add(ReminderPref(user_id=other, nonce="n" * 8, status="active"))
        db.session.commit()
    with app.app_context():
        tok = rem.unsubscribe_token(uid)
    app.test_client().get(f"/patient/reminders/unsubscribe/{tok}")
    assert pref_of(app, uid) is None and pref_of(app, other) is not None


def test_turn_off_from_settings(app, patient_client):
    c, uid = patient_client
    turn_on(c)
    assert c.post("/patient/reminders/off").status_code == 302
    assert pref_of(app, uid) is None
