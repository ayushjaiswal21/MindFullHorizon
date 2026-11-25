"""The ops_daily job: scheduling, prescription expiry, stock and review alerts (design 4.10)."""
from datetime import timedelta

import pytest

from core.extensions import db
from models import Job, Notification, PrescriberProfile, Prescription
from services import ops_jobs
from tests import inv_helpers as h
from utils import jobs
from utils.timeutil import ist_today, utcnow


def run_job(app):
    with app.app_context():
        assert ops_jobs.ops_daily(None) == 'ok'
        db.session.commit()


@pytest.fixture
def desk(make_user):
    return make_user('admin', is_pharmacy_desk=True)


def test_ops_daily_registers_and_reschedules(app):
    assert jobs._HANDLERS['ops_daily'] is ops_jobs.ops_daily
    with app.app_context():
        ops_jobs.ensure_ops_daily_scheduled()
        ops_jobs.ensure_ops_daily_scheduled()  # idempotent: one job per IST day
        assert [j.idempotency_key for j in Job.query] == [f'ops_daily:{ist_today()}']
        assert jobs.run_once('test-worker') == 1
        done, nxt = Job.query.order_by(Job.id).all()
        assert done.status == 'done' and done.last_error == 'ok'
        assert nxt.idempotency_key == f'ops_daily:{ist_today() + timedelta(days=1)}' and nxt.status == 'queued'
        assert nxt.run_at > utcnow()  # 06:00 IST tomorrow, as naive UTC (00:30 UTC)
        assert (nxt.run_at.hour, nxt.run_at.minute) == (0, 30)


def test_ops_daily_idempotent_key_when_rerun(app):
    run_job(app)
    run_job(app)
    with app.app_context():
        assert Job.query.filter_by(kind='ops_daily').count() == 1  # tomorrow's job is not duplicated


def test_expires_prescriptions(app, make_user, make_doctor):
    med = h.med(app)
    patient, doctor = make_user('patient'), make_doctor()
    old = h.rx(app, patient, doctor, [(med, 1)], days_valid=-1)
    partly = h.rx(app, patient, doctor, [(med, 1)], status='partially_dispensed', days_valid=-2)
    live = h.rx(app, patient, doctor, [(med, 1)], days_valid=5)
    done = h.rx(app, patient, doctor, [(med, 1)], status='dispensed', days_valid=-3)
    run_job(app)
    with app.app_context():
        got = {i: db.session.get(Prescription, i).status for i in (old, partly, live, done)}
    assert got == {old: 'expired', partly: 'expired', live: 'issued', done: 'dispensed'}


def test_alerts_once_per_day_counts_only(app, desk, make_user):
    base = make_user('admin')  # no desk flag: gets no stock alert
    other = make_user('admin', is_pharmacy_desk=True, institution='Other College')
    med = h.med(app, name='Secretol')
    h.batch(app, med, 5, 'NEAR', days=10)
    h.batch(app, med, 3, 'DEAD', days=-2)
    run_job(app)
    with app.app_context():
        jobs.enqueue('ops_daily')  # a second run on the same IST day
        db.session.commit()
    run_job(app)
    with app.app_context():
        rows = Notification.query.filter_by(type='inventory_alert').all()
        assert [r.recipient_id for r in rows] == [desk]
        n = rows[0]
        assert n.payload['near_expiry'] == 1 and n.payload['awaiting_writeoff'] == 1 and n.payload['date'] == ist_today().isoformat()
        assert 'Secretol' not in (n.message or '') and 'Secretol' not in str(n.payload)
        assert Notification.query.filter(Notification.recipient_id.in_([base, other])).count() == 0


def test_no_alert_when_nothing_to_report(app, desk):
    med = h.med(app)
    h.batch(app, med, 50, days=300)
    run_job(app)
    with app.app_context():
        assert Notification.query.count() == 0


def test_reconcile_mismatch_and_review_due_notify_admins(app, desk, make_user, make_doctor):
    admin = make_user('admin')
    med = h.med(app)
    bid = h.batch(app, med, 10, days=300)
    doctor = make_doctor()
    with app.app_context():
        db.session.execute(db.text(f'UPDATE inventory_batches SET quantity_on_hand = 11 WHERE id = {bid}'))
        PrescriberProfile.query.filter_by(user_id=doctor).one().review_due_at = utcnow() + timedelta(days=10)
        db.session.commit()
    run_job(app)
    with app.app_context():
        mismatch = Notification.query.filter_by(type='inventory_mismatch').all()
        assert [n.recipient_id for n in mismatch] == [desk] and mismatch[0].payload['batches'] == 1
        review = {n.recipient_id for n in Notification.query.filter_by(type='prescriber_review_due')}
        assert review == {desk, admin}  # any admin of the institution, not only the desk
