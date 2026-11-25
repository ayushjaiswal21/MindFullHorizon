"""Event-driven job worker: an idle worker must not poll the database (keeps Neon asleep), yet crisis jobs run promptly."""
import threading
import time
from datetime import datetime, timedelta

import pytest
from sqlalchemy import event

from core.extensions import db
from models import Job
from utils import jobs, worker_wake


@pytest.fixture
def worker(app):
    """start(handler_fn, idle_max=30) -> (kind name, stop). Runs jobs.run_worker in a thread; cleans up afterwards."""
    started = []

    def start(fn, idle_max=30.0):
        name = f"wake_{len(started)}"
        jobs.register(name)(fn)
        stop = threading.Event()
        t = threading.Thread(target=jobs.run_worker, args=(app, stop, 0.05, idle_max), daemon=True)
        t.start()
        started.append((name, stop, t))
        time.sleep(0.6)  # first pass finishes, the worker goes idle
        return name

    yield start
    for name, stop, t in started:
        stop.set()
        worker_wake.WAKE.set()
        t.join(timeout=5)
        jobs._HANDLERS.pop(name, None)


def _wait_done(app, count, timeout):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        with app.app_context():
            if Job.query.filter_by(status="done").count() >= count:
                return True
        time.sleep(0.02)
    return False


def test_idle_worker_makes_no_database_query(app, worker):
    worker(lambda job: None)
    statements = []
    with app.app_context():
        engine = db.engine
    listener = lambda conn, cursor, statement, *a: statements.append(statement)  # noqa: E731
    event.listen(engine, "before_cursor_execute", listener)
    try:
        time.sleep(1.5)  # the old loop (poll 0.05 s here, 2 s in production) would query many times
    finally:
        event.remove(engine, "before_cursor_execute", listener)
    assert statements == []


def test_enqueue_and_commit_wakes_the_worker_promptly(app, worker):
    ran = []
    name = worker(lambda job: ran.append(time.monotonic()))  # idle_max is 30 s: only WAKE can explain a fast run
    with app.app_context():
        jobs.enqueue(name)
        db.session.commit()
    t0 = time.monotonic()
    assert _wait_done(app, 1, 3.0) and ran and ran[0] - t0 < 2.0


def test_scheduled_job_fires_at_its_run_at(app, worker):
    ran = []
    name = worker(lambda job: ran.append(datetime.utcnow()))
    run_at = datetime.utcnow() + timedelta(seconds=1.2)
    with app.app_context():
        jobs.enqueue(name, run_at=run_at)
        db.session.commit()
    time.sleep(0.5)
    assert ran == []  # not before it is due
    assert _wait_done(app, 1, 4.0)
    assert timedelta(0) <= ran[0] - run_at < timedelta(seconds=2)


def test_rollback_does_not_wake_or_run(app, worker):
    ran = []
    name = worker(lambda job: ran.append(1))
    worker_wake.WAKE.clear()
    with app.app_context():
        jobs.enqueue(name)
        assert not worker_wake.WAKE.is_set()  # nothing wakes before the commit
        db.session.rollback()
        assert "wake_jobs" not in db.session.info
        db.session.commit()  # a later, unrelated commit
    time.sleep(0.3)
    assert not worker_wake.WAKE.is_set() and ran == []
    with app.app_context():
        assert Job.query.count() == 0


def test_commit_without_enqueue_does_not_wake(app):
    worker_wake.WAKE.clear()
    with app.app_context():
        db.session.commit()
    assert not worker_wake.WAKE.is_set()


def test_next_wait_follows_earliest_run_at_within_bounds(app):
    now = datetime.utcnow()
    with app.app_context():
        assert worker_wake.next_wait(2.0, 900.0) == 900.0  # nothing scheduled: the idle cap
        jobs.enqueue("x", run_at=now + timedelta(seconds=100))
        jobs.enqueue("x", run_at=now + timedelta(minutes=45))
        db.session.commit()
        assert 98 < worker_wake.next_wait(2.0, 900.0) <= 100
        assert worker_wake.next_wait(2.0, 10.0) == 10.0  # capped
        jobs.enqueue("x", run_at=now - timedelta(seconds=5))
        db.session.commit()
        assert worker_wake.next_wait(2.0, 900.0) == 2.0  # already due: the minimum (poll_interval)


def test_idle_cap_defaults(app, monkeypatch):
    monkeypatch.delenv("JOB_IDLE_MAX_SECONDS", raising=False)
    with app.app_context():
        assert jobs._cfg("JOB_IDLE_MAX_SECONDS", 900.0) == 900.0
        monkeypatch.setenv("JOB_IDLE_MAX_SECONDS", "120")
        assert jobs._cfg("JOB_IDLE_MAX_SECONDS", 900.0) == 120.0
