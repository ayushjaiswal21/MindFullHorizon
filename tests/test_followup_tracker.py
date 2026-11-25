"""Post-crisis follow-up tracker: creation on acknowledge, IST due dates, assigned-only access, state machine, audit,
no free text in steps, the `followup_due` reminder job, plan completion (docs/FOLLOWUPS.md)."""
from datetime import date, datetime, timedelta

import pytest

from conftest import _login_as
from extensions import db
from models import (Appointment, AuditLog, ClinicalNote, CrisisEvent, FollowUpPlan, FollowUpStep, Job, Notification,
                    ProviderPatient)
from utils import followups, jobs
from utils.timeutil import ist_today, utcnow

XHR = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    for k in ("SMTP_HOST", "FOLLOWUP_SESSIONS", "FOLLOWUP_DAYS", "SITE_URL"):
        monkeypatch.delenv(k, raising=False)


@pytest.fixture
def case(app, make_user):
    """provider (assigned), patient, open crisis event, and a logged-in client for the provider."""
    pid, uid = make_user("provider"), make_user("patient", name="Asha Patient")
    with app.app_context():
        db.session.add(ProviderPatient(provider_id=pid, patient_id=uid, source="manual"))
        ev = CrisisEvent(user_id=uid, source="phq9", severity=9, reason="phq9_item9_positive")
        db.session.add(ev)
        db.session.commit()
        eid = ev.id
    c = app.test_client()
    _login_as(c, app, pid)
    return dict(c=c, provider=pid, patient=uid, event=eid)


def ack(case):
    return case["c"].post(f"/provider/crisis/{case['event']}/acknowledge", headers=XHR)


def plan_steps(app, event_id):
    with app.app_context():
        plan = FollowUpPlan.query.filter_by(crisis_event_id=event_id).one()
        return plan, list(plan.steps)


def step_post(client, step_id, **body):
    return client.post(f"/provider/api/followups/steps/{step_id}", json=body)


def run_due():
    db.session.execute(db.update(Job).where(Job.status.in_(("queued", "failed"))).values(run_at=utcnow() - timedelta(seconds=1)))
    db.session.commit()
    return jobs.run_once("test-worker")


# ---------- creation ----------

def test_acknowledge_creates_plan_with_default_steps_and_jobs(app, case):
    assert ack(case).get_json()["success"] is True
    plan, steps = plan_steps(app, case["event"])
    assert (plan.status, plan.owner_provider_id, plan.patient_id) == ("open", case["provider"], case["patient"])
    base = ist_today()
    assert [s.due_date for s in steps] == [base + timedelta(days=d) for d in (2, 7, 14)]
    assert all(s.status == "pending" and s.outcome is None for s in steps)
    with app.app_context():
        assert Job.query.filter_by(kind="followup_due").count() == 3
        actions = [a.action for a in AuditLog.query.order_by(AuditLog.id)]
        assert "ack_crisis" in actions and "followup_plan_create" in actions


def test_second_acknowledge_does_not_duplicate(app, case):
    ack(case), ack(case)
    with app.app_context():
        assert FollowUpPlan.query.count() == 1 and FollowUpStep.query.count() == 3 and Job.query.filter_by(kind="followup_due").count() == 3


def test_config_sessions_and_days(app, case, monkeypatch):
    monkeypatch.setenv("FOLLOWUP_SESSIONS", "2")
    monkeypatch.setenv("FOLLOWUP_DAYS", "3,10,30")
    ack(case)
    _, steps = plan_steps(app, case["event"])
    assert [(s.due_date - ist_today()).days for s in steps] == [3, 10]
    monkeypatch.setenv("FOLLOWUP_SESSIONS", "5")
    monkeypatch.setenv("FOLLOWUP_DAYS", "2,x")  # invalid list falls back to the default, then pads weekly
    assert followups.config() == (5, [2, 7, 14, 21, 28])


def test_due_dates_use_the_ist_day_at_midnight(app, case):
    with app.app_context():
        ev = db.session.get(CrisisEvent, case["event"])
        ev.acknowledged_at = datetime(2026, 11, 24, 19, 0)  # 00:30 IST on 25 Nov
        plan = followups.create_plan(ev, case["provider"])
        db.session.commit()
        assert [s.due_date for s in plan.steps][0] == date(2026, 11, 27)
        job = Job.query.filter_by(idempotency_key=f"followup-due:{plan.steps[0].id}:2026-11-27").one()
        assert job.run_at == datetime(2026, 11, 27, 3, 30)  # 09:00 IST


# ---------- access ----------

def test_unassigned_provider_gets_404_and_owner_cannot_act(app, case, make_user):
    ack(case)
    _, steps = plan_steps(app, case["event"])
    other = app.test_client()
    _login_as(other, app, make_user("provider"))
    assert step_post(other, steps[0].id, action="done", outcome="no_answer").status_code == 404
    assert other.post(f"/provider/api/followups/plans/1/close", json={"reason": "other"}).status_code == 404
    with app.app_context():  # the owner loses the assignment: still sees the plan in the panel, still cannot act
        ProviderPatient.query.delete()
        db.session.commit()
    assert step_post(case["c"], steps[0].id, action="done", outcome="no_answer").status_code == 404
    page = case["c"].get("/provider/dashboard").get_data(as_text=True)
    assert "not on your caseload" in page and "data-fu-done" not in page


def test_patient_and_anonymous_cannot_use_the_routes(app, case):
    ack(case)
    _, steps = plan_steps(app, case["event"])
    anon = app.test_client()
    assert step_post(anon, steps[0].id, action="done", outcome="no_answer").status_code in (302, 401, 403)
    pc = app.test_client()
    _login_as(pc, app, case["patient"])
    assert step_post(pc, steps[0].id, action="done", outcome="no_answer").status_code in (302, 401, 403)
    with app.app_context():
        assert db.session.get(FollowUpStep, steps[0].id).status == "pending"


# ---------- state machine ----------

def test_done_needs_a_valid_outcome_and_is_final(app, case):
    ack(case)
    _, steps = plan_steps(app, case["event"])
    c, sid = case["c"], steps[0].id
    assert step_post(c, sid, action="done").status_code == 400
    assert step_post(c, sid, action="done", outcome="free text").status_code == 400
    assert step_post(c, sid, action="bogus").status_code == 400
    ok = step_post(c, sid, action="done", outcome="contacted_by_phone")
    assert ok.status_code == 200 and ok.get_json()["plan_status"] == "open"
    assert step_post(c, sid, action="done", outcome="contacted_by_phone").status_code == 200  # replay: quiet no-op
    assert step_post(c, sid, action="missed").status_code == 409  # terminal
    with app.app_context():
        assert AuditLog.query.filter_by(action="followup_step_done").count() == 1
        step = db.session.get(FollowUpStep, sid)
        assert step.status == "done" and step.outcome == "contacted_by_phone" and step.completed_at is not None


def test_steps_store_codes_only_and_notes_become_clinical_notes(app, case):
    ack(case)
    _, steps = plan_steps(app, case["event"])
    assert {c.name for c in FollowUpStep.__table__.columns} == {"id", "plan_id", "seq", "due_date", "status", "completed_at", "outcome"}
    assert all("Text" not in type(c.type).__name__ for t in (FollowUpStep, FollowUpPlan) for c in t.__table__.columns)
    step_post(case["c"], steps[0].id, action="done", outcome="contacted_in_person", note="Met on campus, plans to see me Friday.")
    with app.app_context():
        note = ClinicalNote.query.filter_by(patient_id=case["patient"]).one()
        assert note.provider_id == case["provider"] and "Met on campus" in note.provider_notes
        assert not any("Met on campus" in str(a.meta) for a in AuditLog.query.all())


def test_plan_completes_when_every_step_is_resolved(app, case):
    ack(case)
    _, steps = plan_steps(app, case["event"])
    for s, (action, outcome) in zip(steps, [("done", "contacted_in_person"), ("done", "no_answer"), ("done", "referred")]):
        r = step_post(case["c"], s.id, action=action, outcome=outcome)
    assert r.get_json()["plan_status"] == "completed"
    with app.app_context():
        plan = FollowUpPlan.query.one()
        assert plan.status == "completed" and plan.closed_at is not None
        assert AuditLog.query.filter_by(action="followup_plan_complete").count() == 1


def test_close_early_skips_pending_steps_and_blocks_changes(app, case):
    ack(case)
    plan, steps = plan_steps(app, case["event"])
    c = case["c"]
    assert c.post(f"/provider/api/followups/plans/{plan.id}/close", json={"reason": "nope"}).status_code == 400
    assert c.post(f"/provider/api/followups/plans/{plan.id}/close", json={"reason": "referred"}).status_code == 200
    assert c.post(f"/provider/api/followups/plans/{plan.id}/close", json={"reason": "referred"}).status_code == 200
    assert c.post(f"/provider/api/followups/plans/{plan.id}/close", json={"reason": "other"}).status_code == 409
    with app.app_context():
        assert {s.status for s in FollowUpPlan.query.one().steps} == {"skipped"}
        assert FollowUpPlan.query.one().closed_reason == "referred"
    assert step_post(c, steps[0].id, action="done", outcome="no_answer").status_code == 409


# ---------- reminder job ----------

def test_followup_due_job_notifies_owner_once_without_patient_name(app, case, monkeypatch):
    ack(case)
    sent = []
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    import utils.mailer as mailer
    monkeypatch.setattr(mailer, "send_mail", lambda to, subject, body, reply_to=None: sent.append((to, subject, body)))
    with app.app_context():
        run_due()
        notes = Notification.query.filter_by(type="followup_due").all()
        # the three steps fall on three different days: one in-app reminder per owner and due date
        assert len(notes) == 3 and {n.recipient_id for n in notes} == {case["provider"]}
        assert len({n.payload["date"] for n in notes}) == 3
        assert all("Asha" not in (n.message or "") for n in Notification.query.all())
        assert sent and all("Asha" not in b and "Patient" not in b for _, _, b in sent)
        assert "You have follow-ups" in sent[0][2]
        before = Notification.query.count()
        db.session.execute(db.update(Job).where(Job.kind == "followup_due").values(status="queued", run_at=utcnow() - timedelta(seconds=1)))
        db.session.commit()
        jobs.run_once("again")
        assert Notification.query.count() == before  # replayed jobs add nothing


def test_followup_due_job_skips_resolved_steps_and_works_without_smtp(app, case):
    ack(case)
    _, steps = plan_steps(app, case["event"])
    step_post(case["c"], steps[0].id, action="done", outcome="no_answer")
    with app.app_context():
        run_due()
        jobs_by_step = {j.idempotency_key.split(":")[1]: j for j in Job.query.filter_by(kind="followup_due")}
        assert jobs_by_step[str(steps[0].id)].last_error == "skipped:resolved"
        assert jobs_by_step[str(steps[1].id)].last_error == "sent:in_app"  # SMTP unset: in-app only, job still done
        assert all(j.status == "done" for j in jobs_by_step.values())


# ---------- appointment offer and views ----------

def test_completed_appointment_offers_next_step_but_never_auto_completes(app, case):
    ack(case)
    with app.app_context():
        db.session.add(Appointment(user_id=case["patient"], provider_id=case["provider"], date=ist_today(), time="10:00",
                                   appointment_type="counselling", status="completed", updated_at=utcnow()))
        db.session.commit()
    _, steps = plan_steps(app, case["event"])
    with app.app_context():
        FollowUpStep.query.filter_by(id=steps[0].id).update({"due_date": ist_today()})
        db.session.commit()
        from utils.followup_views import panel
        today = panel(case["provider"])["today"]
        assert len(today) == 1 and today[0]["offer"] is True
        assert db.session.get(FollowUpStep, steps[0].id).status == "pending"
    step_post(case["c"], steps[0].id, action="done", outcome="contacted_in_person")
    with app.app_context():
        from utils.followup_views import panel
        assert not any(r["offer"] for k in panel(case["provider"]).values() for r in k)


def test_dashboard_panel_and_report_timeline_render(app, case):
    ack(case)
    _, steps = plan_steps(app, case["event"])
    with app.app_context():
        FollowUpStep.query.filter_by(id=steps[0].id).update({"due_date": ist_today() - timedelta(days=2)})
        db.session.commit()
    page = case["c"].get("/provider/dashboard").get_data(as_text=True)
    assert "Overdue" in page and "Asha Patient" in page and "Follow-up 1 of 3" in page and "2 days ago" in page
    report = case["c"].get(f"/provider/wellness-report/{case['patient']}").get_data(as_text=True)
    assert "Follow-up 1" in report and "Close plan early" in report and "Overdue" in report
