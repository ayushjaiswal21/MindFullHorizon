"""Event-driven wake-up for the in-process job worker (docs/OPERATIONS.md, "Idle worker").

The worker used to poll the database every 2 seconds, which keeps a scale-to-zero Neon compute awake for ever.
Now it sleeps on `WAKE` and only queries when (a) a commit that added a job happened in this process, or
(b) the earliest scheduled `run_at` or the idle cap (JOB_IDLE_MAX_SECONDS) arrives.

`threading.Event` is green-thread friendly under eventlet (gunicorn monkey-patches `threading`). It does not cross
processes: a separate `flask jobs-worker` process uses a short idle cap instead (see utils/jobs.py).
"""
import threading
import time
from datetime import datetime

from sqlalchemy import event, func
from sqlalchemy.orm import Session

WAKE = threading.Event()
_FLAG = 'wake_jobs'


def mark_session(session):
    """Call from `enqueue()`: the next successful commit of this session wakes the worker."""
    session.info[_FLAG] = True


@event.listens_for(Session, 'after_commit')  # class-level: registered once, at import
def _wake_after_commit(session):
    if session.info.pop(_FLAG, None):
        WAKE.set()


@event.listens_for(Session, 'after_rollback')  # a real rollback: the job row never existed
def _forget_after_rollback(session):
    session.info.pop(_FLAG, None)


def sleep_until_woken(stop_event, seconds):
    """Wait up to `seconds` for WAKE (or stop_event), polling the stop flag once a second. No database access."""
    end = time.monotonic() + seconds
    while not stop_event.is_set() and not WAKE.is_set():
        left = end - time.monotonic()
        if left <= 0:
            return
        WAKE.wait(min(left, 1.0))


def next_wait(poll_interval, idle_max, now=None):
    """Seconds to sleep: until the earliest claimable job's run_at (one cheap query), never below `poll_interval`
    and never above `idle_max` (nothing scheduled -> idle_max)."""
    from extensions import db
    from models import Job
    from utils.jobs import CLAIMABLE
    now = now or datetime.utcnow()
    earliest = db.session.query(func.min(Job.run_at)).filter(Job.status.in_(CLAIMABLE)).scalar()
    db.session.rollback()  # end the read transaction: no connection is held while the worker sleeps
    wait = (earliest - now).total_seconds() if earliest else idle_max
    return max(poll_interval, min(wait, idle_max))
