"""Shared fixtures and helpers for tests/test_reminders*.py (SMTP faked, outbox recorded)."""
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

SENT = []


@pytest.fixture(autouse=True)
def mail(monkeypatch):
    """SMTP 'configured' and send_mail recorded; each test starts with an empty outbox."""
    SENT.clear()
    monkeypatch.setenv("SMTP_HOST", "smtp.test.invalid")
    monkeypatch.setenv("SITE_URL", "https://app.test")
    monkeypatch.setattr(rem, "send_mail", lambda to, subject, body, **kw: SENT.append(
        SimpleNamespace(to=to, subject=subject, body=body, headers=kw.get("headers") or {})))


def pref_of(app, uid):
    with app.app_context():
        return ReminderPref.query.filter_by(user_id=uid).first()


def turn_on(c, **kw):
    return c.post("/patient/reminders", data={"frequency": "daily", "hour": "20", **kw})


def job(pref, kind, due=None, nonce=None):
    return SimpleNamespace(payload={"user_id": pref.user_id, "nonce": nonce or pref.nonce, "kind": kind,
                                    "site": "https://app.test", "due": (due or utcnow()).isoformat()})


def queued(app, kind="reminder"):
    """The job the queue really holds (its due time is the scheduled time, as in production)."""
    with app.app_context():
        j = [j for j in Job.query.filter_by(kind="reminder_send") if j.payload["kind"] == kind][0]
        return SimpleNamespace(payload=dict(j.payload))


def token_from(body, name):
    return re.search(rf"/patient/reminders/{name}/(\S+)", body).group(1)


def activate(app, c, uid):
    """Full opt-in: save, run the confirmation job, open the link, press confirm. Returns the pref."""
    turn_on(c)
    with app.app_context():
        run_once("t")
    token = token_from(SENT[-1].body, "confirm")
    assert c.post(f"/patient/reminders/confirm/{token}").status_code == 200
    return pref_of(app, uid)


