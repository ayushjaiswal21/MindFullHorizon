"""Crisis durability (O-01, O-02): event + alert job commit with the data, escalation timeline, no patient text (Q1a)."""
import logging
from datetime import datetime, timedelta

import pytest

import app as app_module
from extensions import db
from models import Assessment, CrisisEvent, Job, JournalEntry, Notification
from utils import crisis, jobs

CRISIS_TEXT = "I want to kill myself tonight"


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    for k in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM", "CONTACT_RECIPIENT",
              "CRISIS_ESCALATION_EMAIL", "CRISIS_ESCALATE_MINUTES"):
        monkeypatch.delenv(k, raising=False)
    import ai.service as svc

    def no_llm(*a, **k):
        raise RuntimeError("no ai")
    monkeypatch.setattr(svc, "ask_gemini_system_user", no_llm)


@pytest.fixture
def enqueue_fails(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("queue down")
    monkeypatch.setattr(crisis, "enqueue", boom)


def _phq9_item9(client):
    return client.post("/patient/api/save-assessment", json={"assessment_type": "PHQ-9", "responses": [0] * 8 + [2]})


def _run_due():
    """Make every queued/failed job due, then run the worker once."""
    db.session.execute(db.update(Job).where(Job.status.in_(("queued", "failed")))
                       .values(run_at=datetime.utcnow() - timedelta(seconds=1)))
    db.session.commit()
    return jobs.run_once("test-worker")


def _crisis_event(app, uid):
    with app.app_context():
        ev = crisis.record_crisis(uid, "phq9", 9, "phq9_item9_positive")
        db.session.commit()
        return ev


# ---------- assessment ----------
def test_assessment_item9_creates_event_and_job_in_same_commit(patient_client, app):
    c, uid = patient_client
    body = _phq9_item9(c).get_json()
    assert body["crisis"] is True
    with app.app_context():
        ev = CrisisEvent.query.filter_by(user_id=uid).one()
        job = Job.query.filter_by(idempotency_key=f"crisis-alert:{ev.id}").one()
        assert job.kind == "crisis_alert" and job.payload == {"event_id": ev.id} and job.status == "queued"
        assert Assessment.query.filter_by(user_id=uid).count() == 1


def test_assessment_persistence_failure_still_returns_emergency_payload(patient_client, app, enqueue_fails, caplog):
    c, uid = patient_client
    with caplog.at_level(logging.ERROR):
        r = _phq9_item9(c)
    body = r.get_json()
    assert r.status_code == 500 and body["success"] is False and "queue down" not in r.get_data(as_text=True)
    assert body["crisis"] is True and any("14416" in h["number"] for h in body["helplines"])
    assert body["ai_insights"]["resources"]
    with app.app_context():  # all or nothing: no orphan assessment without its alert
        assert Assessment.query.count() == 0 and CrisisEvent.query.count() == 0 and Job.query.count() == 0
    assert any(f"user={uid}" in r.getMessage() and r.levelno == logging.ERROR for r in caplog.records)


# ---------- chat (HTTP) ----------
def _fake_escalating_chat(monkeypatch):
    async def fake(text, user_id=None, **kw):
        return {"reply": "please call 14416", "severity": 9, "reason": "x", "recommended_action": "emergency_hotline",
                "escalate": True, "helplines": [{"name": "Tele-MANAS", "number": "14416"}]}
    monkeypatch.setattr("routes.chat.ask_with_severity", fake)


def test_chat_crisis_commits_event_and_job(patient_client, app, monkeypatch):
    _fake_escalating_chat(monkeypatch)
    c, uid = patient_client
    body = c.post("/api/chat", json={"message": CRISIS_TEXT}).get_json()
    assert body["escalate"] is True and "alert_recorded" not in body
    with app.app_context():
        ev = CrisisEvent.query.filter_by(user_id=uid).one()
        assert ev.source == "chat" and Job.query.filter_by(idempotency_key=f"crisis-alert:{ev.id}").count() == 1


def test_chat_persistence_failure_still_returns_reply_and_helplines(patient_client, app, monkeypatch, enqueue_fails, caplog):
    _fake_escalating_chat(monkeypatch)
    c, uid = patient_client
    with caplog.at_level(logging.ERROR):
        r = c.post("/api/chat", json={"message": CRISIS_TEXT})
    body = r.get_json()
    assert r.status_code == 200 and body["escalate"] is True and body["reply"] and body["helplines"][0]["number"] == "14416"
    assert body["alert_recorded"] is False
    assert any("crisis record FAILED" in r.getMessage() and f"user={uid}" in r.getMessage() for r in caplog.records)
    assert not any("kill" in r.getMessage() for r in caplog.records)
    with app.app_context():
        assert CrisisEvent.query.count() == 0


# ---------- journal (O-02) ----------
def _journal(client, content):
    return client.post("/patient/journal", data={"title": "Tonight", "content": content}, follow_redirects=True)


def test_journal_crisis_creates_event_without_text(patient_client, app):
    c, uid = patient_client
    r = _journal(c, CRISIS_TEXT)
    assert r.status_code == 200 and "14416" in r.get_data(as_text=True)  # helplines shown to the writer
    with app.app_context():
        ev = CrisisEvent.query.filter_by(user_id=uid).one()
        assert ev.source == "journal" and ev.severity >= 7 and ev.reason == "journal_self_harm"
        job = Job.query.filter_by(idempotency_key=f"crisis-alert:{ev.id}").one()
        stored = f"{ev.reason} {ev.source} {job.payload}"
        assert "kill" not in stored and "myself" not in stored
        assert JournalEntry.query.filter_by(user_id=uid).count() == 1


def test_journal_without_crisis_creates_nothing(patient_client, app):
    c, uid = patient_client
    _journal(c, "Had a good day, studied for exams.")
    with app.app_context():
        assert CrisisEvent.query.count() == 0 and Job.query.count() == 0 and JournalEntry.query.count() == 1


def test_journal_persistence_failure_fails_visibly_and_shows_helplines(patient_client, app, enqueue_fails):
    c, uid = patient_client
    html = _journal(c, CRISIS_TEXT).get_data(as_text=True)
    assert "Could not save your journal entry" in html and "14416" in html and "queue down" not in html
    with app.app_context():
        assert JournalEntry.query.count() == 0 and CrisisEvent.query.count() == 0


# ---------- legacy socket chat (O-02) ----------
def _sio(app, client):
    return app_module.socketio.test_client(app, flask_test_client=client)


def test_socket_chat_crisis_creates_event_and_flags_reply(app, patient_client):
    c, uid = patient_client
    sio = _sio(app, c)
    sio.get_received()
    sio.emit("chat_message", {"message": CRISIS_TEXT})
    got = [m for m in sio.get_received() if m["name"] == "chat_response"]
    assert got and got[0]["args"][0]["is_crisis"] is True
    with app.app_context():
        ev = CrisisEvent.query.filter_by(user_id=uid).one()
        assert ev.source == "chat" and Job.query.filter_by(idempotency_key=f"crisis-alert:{ev.id}").count() == 1


def test_socket_chat_still_replies_when_persistence_fails(app, patient_client, enqueue_fails):
    c, uid = patient_client
    sio = _sio(app, c)
    sio.get_received()
    sio.emit("chat_message", {"message": CRISIS_TEXT})
    got = [m for m in sio.get_received() if m["name"] == "chat_response"]
    assert got and got[0]["args"][0]["is_crisis"] is True and "14416" in got[0]["args"][0]["reply"]
    with app.app_context():
        assert CrisisEvent.query.count() == 0


def test_socket_chat_benign_message_creates_no_event(app, patient_client):
    c, uid = patient_client
    sio = _sio(app, c)
    sio.get_received()
    sio.emit("chat_message", {"message": "my phone died"})
    with app.app_context():
        assert CrisisEvent.query.count() == 0


# ---------- alert delivery and escalation ----------
def test_alert_notifies_institution_providers_only_and_schedules_escalation(app, make_user):
    patient = make_user("patient")
    mine = make_user("provider")
    other = make_user("provider", institution="Elsewhere College")
    ev = _crisis_event(app, patient)
    with app.app_context():
        assert _run_due() == 1
        notes = Notification.query.filter_by(type="crisis_alert").all()
        assert [n.recipient_id for n in notes] == [mine] and other not in [n.recipient_id for n in notes]
        assert "kill" not in (notes[0].message or "") and notes[0].payload == {"event_id": ev, "level": 0}
        esc = Job.query.filter_by(kind="crisis_escalate").one()
        assert esc.payload == {"event_id": ev, "level": 1} and esc.status == "queued"
        assert esc.run_at > datetime.utcnow() + timedelta(minutes=14)  # default window is 15 minutes


def test_escalation_after_window_then_capped_at_level_3(app, make_user, monkeypatch, caplog):
    import utils.mailer as mailer_mod
    sent = []
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setenv("CRISIS_ESCALATION_EMAIL", "oncall@mfh.test")
    monkeypatch.setattr(mailer_mod, "send_mail", lambda to, subject, body, reply_to=None: sent.append((to, subject, body)))
    patient = make_user("patient", institution="Test University")
    provider = make_user("provider")
    ev = _crisis_event(app, patient)
    with app.app_context():
        _run_due()  # crisis_alert
        for level in (1, 2, 3):
            assert _run_due() == 1
            e = db.session.get(CrisisEvent, ev)
            assert e.escalation_level == level and e.escalated_at is not None
            assert Notification.query.filter_by(recipient_id=provider).count() == level + 1
        assert _run_due() == 0  # capped: nothing scheduled after level 3
        assert Job.query.filter(Job.status.in_(("queued", "failed"))).count() == 0
        assert [s[1] for s in sent] == ["[MindFull Horizon] Unacknowledged crisis alert (level 2)",
                                        "[MindFull Horizon] Unacknowledged crisis alert (level 3)"]
        assert all(s[0] == "oncall@mfh.test" and f"Event id: {ev}" in s[2] and "Test University" in s[2] for s in sent)
        assert not any("kill" in s[2] for s in sent)
    assert any(r.levelno == logging.ERROR and f"event={ev}" in r.getMessage() for r in caplog.records)


def test_acknowledged_event_is_not_escalated(app, make_user):
    patient = make_user("patient")
    provider = make_user("provider")
    ev = _crisis_event(app, patient)
    with app.app_context():
        _run_due()
        e = db.session.get(CrisisEvent, ev)
        e.acknowledged_at, e.acknowledged_by = datetime.utcnow(), provider
        db.session.commit()
        before = Notification.query.count()
        assert _run_due() == 1
        e = db.session.get(CrisisEvent, ev)
        assert e.escalation_level == 0 and e.escalated_at is None and Notification.query.count() == before
        assert Job.query.filter_by(kind="crisis_escalate").one().last_error == "skipped:acknowledged"
        assert Job.query.filter(Job.status.in_(("queued", "failed"))).count() == 0


def test_duplicate_delivery_does_not_duplicate_notifications(app, make_user):
    patient = make_user("patient")
    make_user("provider")
    make_user("provider")
    _crisis_event(app, patient)
    with app.app_context():
        alert = Job.query.filter_by(kind="crisis_alert").one()
        assert crisis.crisis_alert(alert) == "notified"
        db.session.commit()
        assert crisis.crisis_alert(alert) == "notified"  # the same job delivered twice
        db.session.commit()
        assert Notification.query.filter_by(type="crisis_alert").count() == 2
        esc = Job.query.filter_by(kind="crisis_escalate").one()
        assert crisis.crisis_escalate(esc) == "escalated:1"
        db.session.commit()
        assert crisis.crisis_escalate(esc) == "skipped:already_escalated"
        db.session.commit()
        assert Notification.query.filter_by(type="crisis_alert").count() == 4
        assert Job.query.filter_by(kind="crisis_escalate").count() == 2  # level 2 scheduled exactly once


def test_record_crisis_does_not_commit(app, make_user):
    patient = make_user("patient")
    with app.app_context():
        assert crisis.record_crisis(patient, "chat", 9, "chat_self_harm") is not None
        db.session.rollback()  # caller never committed: neither the event nor the job survives
        assert CrisisEvent.query.count() == 0 and Job.query.count() == 0
        assert crisis.record_crisis(None, "chat", 9, "x") is None


def test_dead_crisis_job_logs_critical_with_ids_only(app, make_user, monkeypatch, caplog):
    patient = make_user("patient")
    ev = _crisis_event(app, patient)
    monkeypatch.setitem(jobs._HANDLERS, "crisis_alert", lambda j: 1 / 0)
    with app.app_context():
        db.session.execute(db.update(Job).values(max_attempts=1))
        db.session.commit()
        with caplog.at_level(logging.ERROR):
            jobs.process_job(jobs.claim_next("w"))
        assert Job.query.one().status == "dead"
    assert any(r.levelno == logging.CRITICAL and f"event={ev}" in r.getMessage() for r in caplog.records)
