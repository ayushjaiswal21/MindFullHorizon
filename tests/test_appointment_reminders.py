"""Appointment reminders: one job per accepted appointment, 24 h before in IST, no-op when state changed, never after
the slot, SMTP-unset path, honest "Reminder scheduled" (docs/FOLLOWUPS.md)."""
from datetime import date, datetime, timedelta

import pytest

from conftest import _login_as
from core.extensions import db
from models import Appointment, Job, Notification, ProviderPatient
from utils import appt_reminders as ar
from utils import jobs
from utils.state import transition
from utils.timeutil import ist_now, utcnow


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)


@pytest.fixture
def setup(app, make_user):
    prov, pat = make_user("provider", name="Dr Rao"), make_user("patient", name="Meena")
    with app.app_context():
        db.session.add(ProviderPatient(provider_id=prov, patient_id=pat, source="manual"))
        db.session.commit()
    c = app.test_client()
    _login_as(c, app, prov)
    return dict(c=c, prov=prov, pat=pat)


def book(app, s, when, status="pending"):
    """An appointment at IST wall-clock `when`."""
    with app.app_context():
        a = Appointment(user_id=s["pat"], provider_id=s["prov"], date=when.date(), time=when.strftime("%H:%M"),
                        appointment_type="counselling", status=status)
        db.session.add(a)
        db.session.commit()
        return a.id


def accept(s, aid):
    return s["c"].post(f"/provider/appointments/accept/{aid}", json={})


def run_due():
    db.session.execute(db.update(Job).where(Job.status.in_(("queued", "failed"))).values(run_at=utcnow() - timedelta(seconds=1)))
    db.session.commit()
    return jobs.run_once("t")


def test_accept_schedules_one_job_24h_before_in_ist(app, setup):
    when = (ist_now() + timedelta(days=3)).replace(hour=10, minute=0, second=0, microsecond=0)
    aid = book(app, setup, when)
    with app.app_context():
        assert Job.query.filter_by(kind="appointment_reminder").count() == 0  # pending: nothing scheduled
    assert accept(setup, aid).status_code == 200
    with app.app_context():
        job = Job.query.filter_by(idempotency_key=f"appt-reminder:{aid}:24h").one()
        expected = (when - timedelta(hours=24) - timedelta(hours=5, minutes=30))  # IST wall clock -> naive UTC
        assert job.run_at == expected and job.payload["slot"] == when.isoformat()
        assert ar.states([aid]) == {aid: "scheduled"}
        ar.schedule(db.session.get(Appointment, aid))  # a second call changes nothing
        db.session.commit()
        assert Job.query.filter_by(kind="appointment_reminder").count() == 1


def test_run_at_at_ist_midnight_slot(app, setup):
    when = (ist_now() + timedelta(days=3)).replace(hour=0, minute=30, second=0, microsecond=0)  # 00:30 IST
    aid = book(app, setup, when)
    accept(setup, aid)
    with app.app_context():
        job = Job.query.filter_by(idempotency_key=f"appt-reminder:{aid}:24h").one()
        assert job.run_at == datetime.combine(when.date() - timedelta(days=2), datetime.min.time()).replace(hour=19)  # 19:00 UTC two days before


def test_reminder_sends_in_app_to_both_without_smtp_and_once(app, setup):
    when = (ist_now() + timedelta(days=1, hours=1)).replace(second=0, microsecond=0)
    aid = book(app, setup, when)
    accept(setup, aid)
    with app.app_context():
        run_due()
        job = Job.query.filter_by(kind="appointment_reminder").one()
        assert job.status == "done" and job.last_error == "sent:in_app"
        to_patient = Notification.query.filter_by(recipient_id=setup["pat"], type="appointment_reminder").one()
        to_provider = Notification.query.filter_by(recipient_id=setup["prov"], type="appointment_reminder").one()
        assert to_patient.message.startswith("Reminder: appointment tomorrow at ") and "with Dr Rao" in to_patient.message
        assert "Meena" in to_provider.message
        assert ar.states([aid]) == {aid: "sent"}
        job.status, job.run_at = "queued", utcnow()
        db.session.commit()
        jobs.run_once("again")
        assert Notification.query.filter_by(type="appointment_reminder").count() == 2  # replay adds nothing


def test_email_goes_to_patient_only_when_smtp_is_set(app, setup, monkeypatch):
    sent = []
    import utils.mailer as mailer
    monkeypatch.setattr(mailer, "send_mail", lambda to, subject, body, reply_to=None: sent.append((to, body)))
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    aid = book(app, setup, (ist_now() + timedelta(days=1, hours=2)).replace(second=0, microsecond=0))
    accept(setup, aid)
    with app.app_context():
        run_due()
        assert len(sent) == 1 and sent[0][0].startswith("patient") and "Reminder: appointment" in sent[0][1]
        assert Job.query.filter_by(kind="appointment_reminder").one().last_error == "sent"


def test_cancelled_rescheduled_or_past_appointments_send_nothing(app, setup):
    ids = [book(app, setup, (ist_now() + timedelta(days=1, hours=h)).replace(second=0, microsecond=0)) for h in (2, 3, 4)]
    for aid in ids:
        accept(setup, aid)
    with app.app_context():
        transition(db.session.get(Appointment, ids[0]), "cancelled", "provider")  # cancelled before the job runs
        moved = db.session.get(Appointment, ids[1])
        moved.time = "23:59" if moved.time != "23:59" else "23:58"  # slot changed: the old job must not fire
        db.session.commit()
        past = db.session.get(Appointment, ids[2])
        past.date = date.today() - timedelta(days=2)  # already over by the time the job runs
        db.session.commit()
        run_due()
        notes = {j.payload["appointment_id"]: j.last_error for j in Job.query.filter_by(kind="appointment_reminder")}
        assert notes == {ids[0]: "skipped:not_accepted", ids[1]: "skipped:rescheduled", ids[2]: "skipped:rescheduled"}
        assert Notification.query.filter_by(type="appointment_reminder").count() == 0


def test_no_reminder_after_the_slot_and_none_scheduled_for_past_slots(app, setup):
    when = (ist_now() + timedelta(hours=2)).replace(second=0, microsecond=0)
    aid = book(app, setup, when)
    accept(setup, aid)
    with app.app_context():
        job = Job.query.filter_by(kind="appointment_reminder").one()
        assert job.run_at <= utcnow() + timedelta(seconds=5)  # booked under 24 h ahead: due at once
        a = db.session.get(Appointment, aid)
        a.time = (ist_now() - timedelta(minutes=5)).strftime("%H:%M")  # the slot has now passed
        job.payload = dict(job.payload, slot=ar.slot_of(a).isoformat())
        db.session.commit()
        assert ar.appointment_reminder(job) == "skipped:past"
        past = Appointment(user_id=setup["pat"], provider_id=setup["prov"], date=date.today() - timedelta(days=1), time="09:00",
                           appointment_type="x", status="accepted")
        db.session.add(past)
        db.session.flush()
        assert ar.schedule(past) is None
        assert ar.slot_of(Appointment(date=date.today(), time="soon")) is None


def test_dashboard_reports_reminder_only_when_a_job_exists(app, setup):
    s = setup
    with_job = book(app, s, (ist_now() + timedelta(days=2)).replace(hour=11, minute=0, second=0, microsecond=0))
    without = book(app, s, (ist_now() + timedelta(days=3)).replace(hour=11, minute=0, second=0, microsecond=0), status="accepted")  # accepted outside the state machine
    accept(s, with_job)
    got = s["c"].get("/provider/api/appointment-reminders").get_json()["reminders"]
    assert list(got) == [str(with_job)] and got[str(with_job)]["state"] == "scheduled" and str(without) not in got
