"""Reminder emails: the send job, one a day, no health data, mailer headers, export and deletion."""
import json
import re
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from extensions import db
from models import Job, ReminderPref, User
from services import reminders as rem
from utils.jobs import run_once
from utils.timeutil import ist_today, utcnow
from tests.reminder_support import *  # noqa: F401,F403  (autouse `mail` fixture and helpers)
from tests.reminder_support import SENT, pref_of, turn_on, job, queued, token_from, activate  # noqa: F401


# ---- sending ----

def test_reminder_email_has_no_health_information(app, patient_client):
    c, uid = patient_client
    pref = activate(app, c, uid)
    with app.app_context():
        rem.reminder_send(job(pref, "reminder"))
    mail = SENT[-1]
    body = (mail.subject + mail.body).lower()
    for word in ("mood", "phq", "gad", "score", "journal", "safety plan", "sleep", "anxiety", "depress", "crisis", "assessment"):
        assert word not in body, word
    assert "https://app.test/" in mail.body and "unsubscribe" in mail.body and "because you turned on reminders" in mail.body
    assert mail.headers["List-Unsubscribe"].startswith("<https://app.test/patient/reminders/unsubscribe/")
    assert mail.headers["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    with app.app_context():
        assert db.session.get(User, uid).name not in mail.body


def test_one_reminder_per_user_per_day_and_chain_continues(app, patient_client):
    c, uid = patient_client
    activate(app, c, uid)
    before = len(SENT)
    real = queued(app)
    with app.app_context():
        assert rem.reminder_send(real) == "sent"
        db.session.commit()
        assert rem.reminder_send(real) == "skipped:rate_limit"  # a second job, same IST day
        db.session.commit()
        assert ReminderPref.query.one().last_sent_on == ist_today()
        # one job for the next date, whichever job asked for it (idempotency key user + nonce + date)
        keys = [j.idempotency_key for j in Job.query.filter(Job.kind == "reminder_send")]
        assert len(keys) == len(set(keys)) == 3  # confirm, first reminder, the next one
    assert len(SENT) == before + 1


def test_job_replay_does_not_double_schedule(app, patient_client):
    c, uid = patient_client
    pref = activate(app, c, uid)
    with app.app_context():
        j = queued(app)
        rem.reminder_send(j)
        db.session.commit()
        n = Job.query.filter_by(kind="reminder_send").count()
        rem.reminder_send(j)
        db.session.commit()
        assert Job.query.filter_by(kind="reminder_send").count() == n


def test_smtp_unset_skips_silently_but_keeps_the_chain(app, patient_client, monkeypatch):
    c, uid = patient_client
    pref = activate(app, c, uid)
    monkeypatch.delenv("SMTP_HOST")
    real = queued(app)
    with app.app_context():
        assert rem.reminder_send(real) == "skipped:smtp_unset"
        db.session.commit()
        assert Job.query.filter_by(kind="reminder_send").count() == 3
        assert ReminderPref.query.one().last_sent_on is None


def test_late_run_skips_but_schedules_next(app, patient_client):
    c, uid = patient_client
    pref = activate(app, c, uid)
    n = len(SENT)
    with app.app_context():
        assert rem.reminder_send(job(pref, "reminder", due=utcnow() - timedelta(hours=9))) == "skipped:late"
    assert len(SENT) == n


def test_stale_inactive_and_deleted_jobs_do_nothing(app, patient_client):
    c, uid = patient_client
    turn_on(c)
    pref = pref_of(app, uid)
    with app.app_context():
        assert rem.reminder_send(job(pref, "reminder")) == "skipped:not_active"  # pending is not active
        assert rem.reminder_send(job(pref, "confirm", nonce="old")) == "skipped:stale"
    c.post("/patient/reminders/off")
    with app.app_context():
        assert rem.reminder_send(job(pref, "reminder")) == "skipped:stale"  # preference gone
    assert SENT == []


def test_failed_send_rolls_back_rate_limit_so_the_retry_can_send(app, patient_client, monkeypatch):
    c, uid = patient_client
    pref = activate(app, c, uid)
    monkeypatch.setattr(rem, "send_mail", lambda *a, **k: (_ for _ in ()).throw(OSError("smtp down")))
    with app.app_context():
        with pytest.raises(OSError):
            rem.reminder_send(job(pref, "reminder"))
        db.session.rollback()  # what jobs._fail does
        assert ReminderPref.query.one().last_sent_on is None


def test_next_due_daily_and_weekly():
    mk = lambda **kw: SimpleNamespace(frequency=kw.get("f", "daily"), hour_ist=kw.get("h", 20), weekday=kw.get("w", 0))
    after = datetime(2026, 11, 24, 10, 0)  # 15:30 IST, a Tuesday
    due, day = rem.next_due(mk(), after)
    assert (day.isoformat(), due) == ("2026-11-24", datetime(2026, 11, 24, 14, 30))
    assert rem.next_due(mk(h=9), after)[1].isoformat() == "2026-11-25"
    day = rem.next_due(mk(f="weekly", w=0), after)[1]
    assert day.isoformat() == "2026-11-30" and day.weekday() == 0


def test_mailer_headers_are_one_line(monkeypatch):
    from utils import mailer
    captured = {}

    class FakeSMTP:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self, **k): pass
        def login(self, *a): pass
        def send_message(self, msg): captured["msg"] = msg
    monkeypatch.setattr(mailer.smtplib, "SMTP", FakeSMTP)
    mailer.send_mail("a@b.c\r\nBcc: evil@x.y", "Subject\r\nBcc: evil@x.y", "body", headers={"X-Test": "v\r\nBcc: evil@x.y"})
    msg = captured["msg"]
    assert msg["Bcc"] is None and "\n" not in msg["X-Test"] and "\n" not in msg["To"]


# ---- account data ----

def test_export_and_delete_cover_preferences_only_of_this_user(app, patient_client, make_user):
    c, uid = patient_client
    other = make_user("patient")
    with app.app_context():
        db.session.add(ReminderPref(user_id=other, nonce="nonce-other", status="active"))
        db.session.commit()
    activate(app, c, uid)
    data = json.loads(c.post("/account/export").get_data(as_text=True))
    assert len(data["reminder_prefs"]) == 1 and data["reminder_prefs"][0]["user_id"] == uid
    assert "nonce" not in data["reminder_prefs"][0] and "nonce-other" not in json.dumps(data)
    from tests.conftest import PASSWORD
    c.post("/account/delete", data={"password": PASSWORD})
    assert pref_of(app, uid) is None and pref_of(app, other) is not None
    with app.app_context():  # a chain job that outlives the account does nothing
        assert rem.reminder_send(SimpleNamespace(payload={"user_id": uid, "nonce": "x", "kind": "reminder",
                                                          "due": utcnow().isoformat()})) == "skipped:stale"


def test_handler_is_registered_with_the_queue(app):
    from utils import jobs
    jobs._load_handlers()
    assert "reminder_send" in jobs._HANDLERS
