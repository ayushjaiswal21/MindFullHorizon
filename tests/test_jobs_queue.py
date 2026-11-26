"""Job queue tests: enqueue, claim/exclusivity, backoff, retry/dead-letter, stuck-job recovery,
stats/worker loop (Q1a). Split out of test_jobs.py (300-line rule); mailer/send_email tests are in
test_jobs_mailer.py."""
import logging
import threading
import types
from datetime import datetime, timedelta

import pytest

from core.extensions import db
from models import Job
from utils import jobs

FUTURE = lambda: datetime.utcnow() + timedelta(days=1)  # noqa: E731


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


def test_init_jobs_does_not_start_thread_in_tests(app):
    assert app.extensions.get("jobs_thread") is None
