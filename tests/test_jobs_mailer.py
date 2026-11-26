"""Mailer and send_email job-handler tests (Q1a): header injection, SMTP/SSL dispatch, retry to
email_failed. Split out of test_jobs.py (300-line rule); queue/retry/worker tests are in
test_jobs_queue.py."""
from datetime import datetime, timedelta

import pytest

from core.extensions import db
from models import ContactMessage, Job
from utils import jobs, mailer

FUTURE = lambda: datetime.utcnow() + timedelta(days=1)  # noqa: E731


class FakeSMTP:
    instances = []

    def __init__(self, host, port, timeout=None, context=None):
        self.host, self.port, self.timeout, self.ssl = host, port, timeout, context is not None and type(self).__name__ == "FakeSMTPSSL"
        self.log, self.sent = [], []
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self, context=None):
        self.log.append("starttls")

    def login(self, u, p):
        self.log.append("login")

    def send_message(self, msg):
        self.sent.append(msg)


class FakeSMTPSSL(FakeSMTP):
    pass


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    for k in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM", "CONTACT_RECIPIENT"):
        monkeypatch.delenv(k, raising=False)


@pytest.fixture
def fake_smtp(monkeypatch):
    FakeSMTP.instances = []
    monkeypatch.setattr(mailer.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(mailer.smtplib, "SMTP_SSL", FakeSMTPSSL)
    return FakeSMTP


def _contact(app, **kw):
    with app.app_context():
        cm = ContactMessage(name=kw.get("name", "Asha"), email=kw.get("email", "asha@example.com"),
                            subject=kw.get("subject", "Hello"), message="Need info")
        db.session.add(cm)
        db.session.commit()
        return cm.id


def test_clean_header_strips_crlf():
    assert "\n" not in mailer.clean_header("a\r\nBcc: evil@x.com") and "\r" not in mailer.clean_header("a\rb\x00c")


def test_header_injection_is_neutralised(monkeypatch, fake_smtp):
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    mailer.send_mail("to@x.com\r\nBcc: evil@x.com", "Subj\r\nBcc: evil@x.com", "body", reply_to="a@b.com\r\nBcc: evil@x.com")
    msg = fake_smtp.instances[0].sent[0]
    assert "Bcc" not in msg.keys()
    assert all("\n" not in str(v) and "\r" not in str(v) for v in msg.values())


def test_send_email_smtp_unset_is_success_and_message_stays_new(app):
    cid = _contact(app)
    with app.app_context():
        jobs.enqueue("send_email", {"contact_message_id": cid}, idempotency_key=f"contact-email:{cid}")
        db.session.commit()
        jobs.run_once("w")
        row = Job.query.one()
        assert row.status == "done" and row.last_error == "skipped:smtp_unset"
        assert db.session.get(ContactMessage, cid).status == "new"


def test_send_email_with_fake_smtp_and_twice_is_idempotent(app, monkeypatch, fake_smtp):
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "u")
    monkeypatch.setenv("SMTP_PASSWORD", "p")
    monkeypatch.setenv("SMTP_FROM", "noreply@mfh.test")
    monkeypatch.setenv("CONTACT_RECIPIENT", "team@mfh.test")
    cid = _contact(app, subject="Hi\r\nBcc: evil@x.com")
    with app.app_context():
        job = jobs.enqueue("send_email", {"contact_message_id": cid})
        db.session.commit()
        assert mailer.send_email(job) == "sent"
        db.session.commit()
        assert mailer.send_email(job) == "skipped:already_handled"  # second delivery: no second email
        assert db.session.get(ContactMessage, cid).status == "emailed"
    assert len(fake_smtp.instances) == 1
    smtp = fake_smtp.instances[0]
    assert smtp.log == ["starttls", "login"] and smtp.port == 587 and smtp.timeout
    msg = smtp.sent[0]
    assert msg["Reply-To"] == "asha@example.com" and msg["To"] == "team@mfh.test" and "Bcc" not in msg.keys()
    assert "Need info" in msg.get_content()


def test_send_email_port_465_uses_ssl(app, monkeypatch, fake_smtp):
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setenv("SMTP_PORT", "465")
    monkeypatch.setenv("CONTACT_RECIPIENT", "team@mfh.test")
    cid = _contact(app)
    with app.app_context():
        job = jobs.enqueue("send_email", {"contact_message_id": cid})
        db.session.commit()
        mailer.send_email(job)
    assert type(fake_smtp.instances[0]).__name__ == "FakeSMTPSSL" and "starttls" not in fake_smtp.instances[0].log


def test_send_email_retries_then_marks_email_failed(app, monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setenv("CONTACT_RECIPIENT", "team@mfh.test")

    def down(*a, **k):
        raise OSError("connection refused for asha@example.com")
    monkeypatch.setattr(mailer.smtplib, "SMTP", down)
    cid = _contact(app)
    with app.app_context():
        jobs.enqueue("send_email", {"contact_message_id": cid}, max_attempts=2)
        db.session.commit()
        for _ in range(2):
            jobs.process_job(jobs.claim_next("w", now=FUTURE()))
        row = Job.query.one()
        assert row.status == "dead" and row.last_error == "OSError" and "asha" not in row.last_error
        assert db.session.get(ContactMessage, cid).status == "email_failed"


def test_send_email_missing_contact_is_permanent(app):
    with app.app_context():
        jobs.enqueue("send_email", {"contact_message_id": 99999})
        db.session.commit()
        jobs.process_job(jobs.claim_next("w"))
        assert Job.query.one().status == "dead"
