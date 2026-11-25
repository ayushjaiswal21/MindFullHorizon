"""Job queue, mailer and send_email handler tests (Q1a). No network; SMTP is faked."""
import logging
import threading
import types
from datetime import datetime, timedelta

import pytest

from core.extensions import db
from models import ContactMessage, Job
from utils import jobs, mailer

FUTURE = lambda: datetime.utcnow() + timedelta(days=1)  # noqa: E731


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    for k in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM", "CONTACT_RECIPIENT"):
        monkeypatch.delenv(k, raising=False)


@pytest.fixture
def kind(request):
    """Register a throwaway handler kind and remove it afterwards."""
    registered = []

    def _register(name, fn, **kw):
        jobs.register(name, **kw)(fn)
        registered.append(name)
        return name
    yield _register
    for n in registered:
        jobs._HANDLERS.pop(n, None)
        jobs._ON_DEAD.pop(n, None)


# ---------- enqueue ----------
def test_enqueue_idempotent(app):
    with app.app_context():
        a = jobs.enqueue("x", {"id": 1}, idempotency_key="k1")
        db.session.commit()
        b = jobs.enqueue("x", {"id": 2}, idempotency_key="k1")
        db.session.commit()
        assert a.id == b.id and Job.query.count() == 1
        jobs.enqueue("x")
        jobs.enqueue("x")  # no key: always inserts
        db.session.commit()
        assert Job.query.count() == 3


def test_enqueue_does_not_commit(app):
    with app.app_context():
        jobs.enqueue("x", idempotency_key="k")
        db.session.rollback()
        assert Job.query.count() == 0


def test_enqueue_race_falls_back_to_winner(app, monkeypatch):
    """The pre-check misses (another worker inserted in between): the unique constraint decides."""
    with app.app_context():
        winner = jobs.enqueue("x", idempotency_key="race")
        db.session.commit()
        real = Job.query
        calls = []

        class Q:
            def filter_by(self, **kw):
                calls.append(kw)
                return types.SimpleNamespace(first=lambda: None) if len(calls) == 1 else real.filter_by(**kw)
        monkeypatch.setattr(Job, "query", Q())
        loser = jobs.enqueue("x", idempotency_key="race")
        db.session.commit()
        assert loser.id == winner.id and len(calls) == 2
        assert db.session.query(Job).count() == 1


# ---------- claim / exclusivity ----------
def test_claim_exclusive_between_two_workers(app):
    with app.app_context():
        for i in range(6):
            jobs.enqueue("x", {"i": i})
        db.session.commit()
    got, barrier = {"a": [], "b": []}, threading.Barrier(2)

    def work(name):
        with app.app_context():
            barrier.wait()
            while True:
                j = jobs.claim_next(name)
                if j is None:
                    break
                got[name].append(j.id)
            db.session.remove()
    ts = [threading.Thread(target=work, args=(n,)) for n in got]
    [t.start() for t in ts]
    [t.join() for t in ts]
    both = got["a"] + got["b"]
    assert len(both) == 6 and len(set(both)) == 6


def test_claim_skips_future_jobs(app):
    with app.app_context():
        jobs.enqueue("x", run_at=FUTURE())
        db.session.commit()
        assert jobs.claim_next("w") is None


# ---------- backoff ----------
def test_backoff_bounds():
    for attempt in range(1, 15):
        hi = min(jobs.BACKOFF_CAP, jobs.BACKOFF_BASE * 2 ** attempt)
        vals = [jobs.backoff_seconds(attempt) for _ in range(200)]
        assert all(0 <= v <= hi for v in vals)
    assert max(jobs.backoff_seconds(30) for _ in range(200)) <= 900
    assert max(jobs.backoff_seconds(1) for _ in range(200)) <= 10


# ---------- retry, dead letter, last_error ----------
def test_retry_then_dead_letter_without_leaking_text(app, kind, caplog):
    def boom(job):
        raise ValueError("patient wrote: I feel hopeless")
    name = kind("t_boom", boom)
    with app.app_context():
        j = jobs.enqueue(name, {"id": 1}, max_attempts=3)
        db.session.commit()
        jid = j.id
        for n in (1, 2, 3):
            claimed = jobs.claim_next("w", now=FUTURE())
            assert claimed.id == jid
            outcome = jobs.process_job(claimed)
            row = db.session.get(Job, jid)
            assert row.attempts == n and row.last_error == "ValueError" and row.locked_at is None
            if n < 3:
                assert outcome == "failed" and row.status == "failed" and row.run_at > datetime.utcnow() - timedelta(seconds=1)
        assert row.status == "dead" and row.finished_at is not None
        assert jobs.claim_next("w", now=FUTURE()) is None
    errors = [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]
    assert any(f"id={jid}" in m and f"kind={name}" in m for m in errors)
    assert not any("hopeless" in r.getMessage() for r in caplog.records)


def test_permanent_error_goes_dead_immediately(app, kind):
    def bad(job):
        raise jobs.PermanentJobError("nope")
    name = kind("t_perm", bad)
    with app.app_context():
        jobs.enqueue(name)
        db.session.commit()
        jobs.process_job(jobs.claim_next("w"))
        row = Job.query.one()
        assert row.status == "dead" and row.attempts == 1 and row.last_error == "PermanentJobError"


def test_unknown_kind_is_dead(app):
    with app.app_context():
        jobs.enqueue("no_such_kind")
        db.session.commit()
        jobs.process_job(jobs.claim_next("w"))
        row = Job.query.one()
        assert row.status == "dead" and row.last_error == "unknown_kind"


def test_success_marks_done_and_note_is_stored(app, kind):
    name = kind("t_ok", lambda job: "skipped:why")
    with app.app_context():
        jobs.enqueue(name)
        db.session.commit()
        assert jobs.run_once("w") == 1
        row = Job.query.one()
        assert row.status == "done" and row.finished_at and row.last_error == "skipped:why"


def test_on_dead_hook_runs(app, kind):
    seen = []
    name = kind("t_dead", lambda job: 1 / 0, on_dead=lambda job: seen.append(job.id))
    with app.app_context():
        jobs.enqueue(name, max_attempts=1)
        db.session.commit()
        jobs.process_job(jobs.claim_next("w"))
        assert seen == [Job.query.one().id]


# ---------- stuck job recovery ----------
def test_stuck_job_returns_to_queue_then_dies(app):
    with app.app_context():
        j = jobs.enqueue("x", max_attempts=2)
        db.session.commit()
        jobs.claim_next("w")
        db.session.execute(db.update(Job).values(locked_at=datetime.utcnow() - timedelta(hours=1)))
        db.session.commit()
        assert jobs.recover_stale() == 1
        row = db.session.get(Job, j.id)
        assert row.status == "queued" and row.attempts == 1 and row.last_error == "lock_timeout" and row.locked_by is None
        jobs.claim_next("w")
        db.session.execute(db.update(Job).values(locked_at=datetime.utcnow() - timedelta(hours=1)))
        db.session.commit()
        assert jobs.recover_stale() == 1
        assert db.session.get(Job, j.id).status == "dead"


def test_fresh_running_job_not_recovered(app):
    with app.app_context():
        jobs.enqueue("x")
        db.session.commit()
        jobs.claim_next("w")
        assert jobs.recover_stale() == 0
        assert Job.query.one().status == "running"


# ---------- stats / worker loop ----------
def test_stats_and_run_worker_stops(app, kind):
    name = kind("t_w", lambda job: None)
    with app.app_context():
        jobs.enqueue(name)
        db.session.commit()
        assert jobs.stats()["queued"] == 1
    stop = threading.Event()
    t = threading.Thread(target=jobs.run_worker, args=(app, stop, 0.05))
    t.start()
    for _ in range(100):
        with app.app_context():
            if Job.query.filter_by(status="done").count() == 1:
                break
        stop.wait(0.05)
    stop.set()
    t.join(timeout=5)
    assert not t.is_alive()
    with app.app_context():
        assert jobs.stats()["done"] == 1


# ---------- mailer ----------
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


def test_init_jobs_does_not_start_thread_in_tests(app):
    assert app.extensions.get("jobs_thread") is None
