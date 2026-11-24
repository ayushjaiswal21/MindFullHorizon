"""Durable job queue (transactional outbox, no Redis). Owned by Q1a. See docs/OPERATIONS.md.
Producers call `enqueue()` inside their own transaction and commit with their data.
Status machine: queued -> running -> done | failed (retry, run_at = now + jittered backoff) -> dead.
`attempts` counts failed attempts (and lock-timeout recoveries). Handlers must be idempotent: delivery is at-least-once.
`last_error` holds an exception class name or short code, NEVER message text or patient text.
"""
import atexit
import logging
import os
import random
import socket
import sys
import threading
from datetime import datetime, timedelta

import click
from sqlalchemy import func, update
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import Job
from utils.worker_wake import WAKE, mark_session, next_wait, sleep_until_woken

logger = logging.getLogger(__name__)

CLAIMABLE = ('queued', 'failed')
BACKOFF_BASE = 5.0
BACKOFF_CAP = 15 * 60.0
_HANDLERS = {}
_ON_DEAD = {}


class PermanentJobError(Exception):
    """Raise from a handler for an error that retrying cannot fix: the job goes straight to 'dead'."""


def register(kind, on_dead=None):
    """Decorator: register `fn(job)` as the handler for `kind`. `on_dead(job)` runs once when the job is dead-lettered."""
    def deco(fn):
        _HANDLERS[kind] = fn
        if on_dead:
            _ON_DEAD[kind] = on_dead
        return fn
    return deco


def _cfg(name, default):
    from flask import current_app
    value = current_app.config.get(name) if current_app else None
    if value in (None, ''):
        value = os.getenv(name)
    try:
        return type(default)(value) if value not in (None, '') else default
    except (TypeError, ValueError):
        return default


def _insert_ignore(values):
    """INSERT ... ON CONFLICT DO NOTHING on the idempotency key (no savepoint: pysqlite's SAVEPOINT can commit the
    caller's transaction, and a failed PostgreSQL insert would poison it). False if unsupported."""
    dialect = db.engine.dialect.name
    if dialect == 'postgresql':
        from sqlalchemy.dialects.postgresql import insert
    elif dialect == 'sqlite':
        from sqlalchemy.dialects.sqlite import insert
    else:
        return False
    db.session.execute(insert(Job.__table__).values(**values).on_conflict_do_nothing(index_elements=['idempotency_key']))
    return True


def enqueue(kind, payload=None, idempotency_key=None, run_at=None, max_attempts=5):
    """Add a Job to the CURRENT session without committing; the caller commits.

    If `idempotency_key` already exists the existing Job is returned. Race-safe: the insert is conflict-ignoring on the
    unique key, so a concurrent producer that wins the race simply makes us return its row.
    """
    run_at = run_at or datetime.utcnow()
    mark_session(db.session)  # after_commit sets WAKE so an idle worker looks at the queue (utils/worker_wake.py)
    if not idempotency_key:
        job = Job(kind=kind, payload=payload, run_at=run_at, max_attempts=max_attempts)
        db.session.add(job)
        return job
    existing = Job.query.filter_by(idempotency_key=idempotency_key).first()
    if existing:
        return existing
    db.session.flush()  # the caller's pending rows first, so the insert below joins their transaction
    values = dict(kind=kind, payload=payload, idempotency_key=idempotency_key, run_at=run_at, max_attempts=max_attempts)
    if _insert_ignore(values):
        return Job.query.filter_by(idempotency_key=idempotency_key).one()
    job = Job(**values)  # other dialects: savepoint + unique constraint
    try:
        with db.session.begin_nested():
            db.session.add(job)
            db.session.flush()
    except IntegrityError:
        return Job.query.filter_by(idempotency_key=idempotency_key).one()
    return job


def backoff_seconds(attempt, base=BACKOFF_BASE, cap=BACKOFF_CAP):
    """Full jitter: U(0, min(cap, base * 2^attempt)). `attempt` is the number of failures so far (>= 1)."""
    return random.uniform(0, min(cap, base * (2 ** max(attempt, 0))))


def claim_next(worker_id, now=None):
    """Atomically claim one due job (status -> running) or return None. Safe with several workers."""
    now = now or datetime.utcnow()
    postgres = db.engine.dialect.name == 'postgresql'
    for _ in range(5):  # a lost compare-and-set race just means another worker got that row
        q = (db.session.query(Job.id).filter(Job.status.in_(CLAIMABLE), Job.run_at <= now)
             .order_by(Job.run_at, Job.id))
        if postgres:
            q = q.with_for_update(skip_locked=True)
        row = q.first()
        if not row:
            db.session.rollback()
            return None
        res = db.session.execute(update(Job).where(Job.id == row.id, Job.status.in_(CLAIMABLE))
                                 .values(status='running', locked_at=now, locked_by=worker_id))
        db.session.commit()
        if res.rowcount == 1:
            return db.session.get(Job, row.id)
    return None


def _dead_letter(job):
    logger.error("job dead id=%s kind=%s", job.id, job.kind)
    hook = _ON_DEAD.get(job.kind)
    if hook:
        try:
            hook(job)
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            logger.error("job on_dead hook failed id=%s kind=%s err=%s", job.id, job.kind, type(exc).__name__)


def _fail(job_id, error_code, permanent=False):
    """Record a failed attempt: retry with backoff, or dead-letter."""
    db.session.rollback()
    job = db.session.get(Job, job_id)
    if job is None:
        return
    now = datetime.utcnow()
    job.attempts += 1
    job.last_error = str(error_code)[:200]
    job.locked_at = job.locked_by = None
    if permanent or job.attempts >= job.max_attempts:
        job.status, job.finished_at = 'dead', now
        db.session.commit()
        _dead_letter(job)
        return
    job.status = 'failed'
    job.run_at = now + timedelta(seconds=backoff_seconds(job.attempts))
    db.session.commit()


def process_job(job):
    """Run the handler for a claimed job. The handler's DB writes and the 'done' mark commit together."""
    job_id, kind = job.id, job.kind
    handler = _HANDLERS.get(kind)
    if handler is None:
        _fail(job_id, 'unknown_kind', permanent=True)
        return 'dead'
    try:
        note = handler(job)
        job.status, job.finished_at = 'done', datetime.utcnow()
        job.locked_at = job.locked_by = None
        job.last_error = note[:200] if isinstance(note, str) else None  # short code such as 'skipped:smtp_unset'
        db.session.commit()
        return 'done'
    except PermanentJobError as exc:
        _fail(job_id, type(exc).__name__, permanent=True)
        return 'dead'
    except Exception as exc:  # class name only: exception text may carry user data
        _fail(job_id, type(exc).__name__)
        return 'failed'


def recover_stale(now=None):
    """Visibility timeout: running jobs locked longer than JOB_LOCK_TIMEOUT seconds go back to the queue (attempts+1)."""
    now = now or datetime.utcnow()
    cutoff = now - timedelta(seconds=_cfg('JOB_LOCK_TIMEOUT', 300))
    stuck = Job.query.filter(Job.status == 'running', Job.locked_at < cutoff).all()
    recovered = 0
    for job in stuck:
        dead = job.attempts + 1 >= job.max_attempts
        values = dict(attempts=Job.attempts + 1, last_error='lock_timeout', locked_at=None, locked_by=None)
        values.update(status='dead', finished_at=now) if dead else values.update(status='queued', run_at=now)
        res = db.session.execute(update(Job).where(Job.id == job.id, Job.status == 'running',
                                                   Job.locked_at < cutoff).values(**values))
        db.session.commit()
        if res.rowcount == 1:
            recovered += 1
            if dead:
                _dead_letter(db.session.get(Job, job.id))
    return recovered


def run_once(worker_id, max_jobs=20):
    """Recover stale jobs, then process due jobs. Returns the number processed."""
    recover_stale()
    n = 0
    while n < max_jobs:
        job = claim_next(worker_id)
        if job is None:
            break
        process_job(job)
        n += 1
    return n


def _worker_id():
    return f"{socket.gethostname()}:{os.getpid()}"[:60]


def run_worker(app, stop_event, poll_interval=2.0, idle_max=None):
    """Event-driven loop (thread, green thread or separate process): after each pass sleep until WAKE (same process
    only), the next scheduled run_at or `idle_max` (JOB_IDLE_MAX_SECONDS, default 900 s; 60 s for `flask jobs-worker`).
    No database query on a short timer. `poll_interval` is the minimum sleep."""
    worker_id = _worker_id()
    logger.info("job worker started id=%s", worker_id)
    while not stop_event.is_set():
        with app.app_context():
            cap = _cfg('JOB_IDLE_MAX_SECONDS', 900.0) if idle_max is None else idle_max
            WAKE.clear()  # before the pass, so a commit that lands during it is not lost
            did, wait = 0, min(cap, max(poll_interval, 30.0))  # error backoff
            try:
                did = run_once(worker_id)
                wait = 0 if did else next_wait(poll_interval, cap)
            except Exception as exc:
                db.session.rollback()
                logger.error("job worker loop error type=%s", type(exc).__name__)
        sleep_until_woken(stop_event, wait)  # wait is 0 right after a pass that did work
    logger.info("job worker stopped id=%s", worker_id)


def stats():
    """Counts per status plus oldest due job age in seconds (for /ready and `flask jobs-stats`)."""
    counts = dict(db.session.query(Job.status, func.count(Job.id)).group_by(Job.status).all())
    oldest = db.session.query(func.min(Job.run_at)).filter(Job.status.in_(CLAIMABLE)).scalar()
    lag = max(0, int((datetime.utcnow() - oldest).total_seconds())) if oldest else 0
    return {s: counts.get(s, 0) for s in ('queued', 'running', 'done', 'failed', 'dead')} | {'oldest_due_age_s': lag}


def _load_handlers():
    import utils.crisis, utils.mailer, services.ops_jobs  # noqa: F401,E401  (register crisis_*, send_email, ops_daily)


def _truthy(v):
    return str(v or '').strip().lower() in ('1', 'true', 'yes', 'on')


def init_jobs(app):
    """Register handlers and CLI commands; start the in-process worker when JOBS_INPROCESS is truthy."""
    _load_handlers()

    @app.cli.command('jobs-worker')
    @click.option('--poll', default=2.0, show_default=True, help='Minimum seconds between database checks.')
    def jobs_worker(poll):
        """Run a job worker in this process until interrupted (checks the queue at least every 60 s: no wake signal)."""
        try:
            run_worker(app, threading.Event(), poll, idle_max=_cfg('JOB_IDLE_MAX_SECONDS', 60.0))
        except KeyboardInterrupt:
            pass

    @app.cli.command('jobs-run-once')
    def jobs_run_once():
        """Process all currently due jobs, then exit."""
        click.echo(f"processed={run_once(_worker_id(), max_jobs=1000)}")

    @app.cli.command('jobs-stats')
    def jobs_stats():
        """Print job counts per status."""
        for k, v in stats().items():
            click.echo(f"{k}={v}")

    default = '1' if os.getenv('FLASK_ENV') == 'production' else '0'
    if not _truthy(os.getenv('JOBS_INPROCESS', default)):
        return None
    argv = [os.path.basename(a).lower() for a in sys.argv[:3]]
    if ('flask' in argv[0] or argv[0] == '__main__.py') and 'run' not in argv[1:]:
        return None  # flask CLI commands (db upgrade, jobs-*) must not spawn a second worker
    if os.getenv('FLASK_DEBUG') == '1' and os.name != 'nt' and os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        return None  # reloader parent process
    if app.extensions.get('jobs_thread'):
        return app.extensions['jobs_thread']
    stop = threading.Event()
    thread = threading.Thread(target=run_worker, args=(app, stop), name='jobs-worker', daemon=True)
    app.extensions['jobs_thread'] = thread
    thread.start()

    def _shutdown():
        stop.set()
        WAKE.set()
        thread.join(timeout=5)
    atexit.register(_shutdown)
    return thread
