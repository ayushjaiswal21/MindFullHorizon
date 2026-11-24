"""Daily operations job `ops_daily` (design 4.10): expire prescriptions, stock alerts, ledger reconcile, review alerts.

There is no scheduler in the job queue, so the handler enqueues itself for 06:00 IST the next day. Every step is
state-based and idempotent, so a worker that was down simply catches up. Notifications carry counts only.
"""
import logging
from datetime import datetime, timedelta, timezone

import click
from sqlalchemy import update

from extensions import db
from models import InventoryBatch, Notification, Prescription, User
from services.inventory import alert_counts, reconcile
from services.prescriber import review_due_count
from services.roles import norm_inst
from utils.jobs import enqueue, register
from utils.timeutil import IST, ist_day_bounds, ist_today, utcnow

logger = logging.getLogger(__name__)
KIND = 'ops_daily'
OPEN_STATES = ('issued', 'partially_dispensed')


def _run_at(day):
    """06:00 IST of `day` as naive UTC."""
    return datetime(day.year, day.month, day.day, 6, 0, tzinfo=IST).astimezone(timezone.utc).replace(tzinfo=None)


def ensure_ops_daily_scheduled():
    """Idempotent enqueue of today's run. Commits. Safe to call from the CLI, start-up or the admin dashboard."""
    try:
        enqueue(KIND, {}, idempotency_key=f'{KIND}:{ist_today()}')
        db.session.commit()
    except Exception as exc:  # scheduling must never break the caller
        db.session.rollback()
        logger.warning('ops_daily scheduling failed: %s', type(exc).__name__)


def expire_due_prescriptions(now):
    """Persist status 'expired' for issued and partially dispensed prescriptions past their expiry instant."""
    try:
        from services.prescriptions import expire_due
        return expire_due(now)
    except ImportError:
        res = db.session.execute(update(Prescription).where(Prescription.status.in_(OPEN_STATES),
                                                            Prescription.expiry_date <= now).values(status='expired'))
        return res.rowcount


def _institutions():
    keys = {k for (k,) in db.session.query(InventoryBatch.institution_key).distinct()}
    keys |= {norm_inst(i) for (i,) in db.session.query(User.institution).filter(User.role == 'provider',
                                                                                  User.provider_type == 'doctor')}
    return sorted(k for k in keys if k)


def _admins(institution_key, desk_only=False):
    q = User.query.filter(User.role == 'admin', User.deactivated_at.is_(None))
    return [a for a in q if norm_inst(a.institution) == institution_key and (a.is_pharmacy_desk or not desk_only)]


def _notify_once(recipient, kind, payload, message):
    """One Notification per recipient and type per IST day (dedupe by creation time, no JSON query needed)."""
    start = ist_day_bounds()[0]
    if Notification.query.filter(Notification.recipient_id == recipient.id, Notification.type == kind,
                                 Notification.created_at >= start).first():
        return False
    db.session.add(Notification(recipient_id=recipient.id, type=kind, payload=dict(payload, date=ist_today().isoformat()),
                                message=message))
    return True


def inventory_alerts(institution_key):
    counts = alert_counts(institution_key)
    if not any(counts.values()):
        return 0
    msg = ('Stock check: {low} low, {out} out of stock, {near_expiry} batches near expiry, '
           '{awaiting_writeoff} expired batches waiting for write-off.').format(**counts)
    return sum(_notify_once(a, 'inventory_alert', counts, msg) for a in _admins(institution_key, desk_only=True))


def inventory_mismatches(institution_key):
    bad = reconcile(institution_key)
    for row in bad:
        logger.error('inventory mismatch batch_id=%s', row['batch_id'])  # ids only
    if not bad:
        return 0
    msg = f'The stock ledger and the batch quantities disagree for {len(bad)} batches. Count the shelf and check the ledger.'
    return sum(_notify_once(a, 'inventory_mismatch', {'batches': len(bad)}, msg) for a in _admins(institution_key, desk_only=True))


def prescriber_review_alerts(institution_key):
    n = review_due_count(institution_key, 30)
    if not n:
        return 0
    msg = f'{n} prescriber registration checks are due within 30 days or overdue.'
    return sum(_notify_once(a, 'prescriber_review_due', {'count': n}, msg) for a in _admins(institution_key))


@register(KIND)
def ops_daily(job):
    """Handlers raise on database errors: the queue retries with backoff and keeps the exception class name only."""
    now = utcnow()
    expire_due_prescriptions(now)
    for key in _institutions():
        inventory_alerts(key)
        inventory_mismatches(key)
        prescriber_review_alerts(key)
    tomorrow = ist_today() + timedelta(days=1)
    enqueue(KIND, {}, idempotency_key=f'{KIND}:{tomorrow}', run_at=_run_at(tomorrow))
    return 'ok'


def init_ops_cli(app):
    """Register `flask ops-daily-schedule` (called from app.py)."""
    @app.cli.command('ops-daily-schedule')
    def ops_daily_schedule():
        """Queue today's ops_daily run (it then re-queues itself every day)."""
        ensure_ops_daily_scheduled()
        click.echo('ops_daily scheduled')
