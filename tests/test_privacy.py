"""Consent, age gate, OAuth consent guard, account export and deletion (decisions P-05, DPDP rights)."""
import json
from datetime import date, datetime
from types import SimpleNamespace

import app as app_module
from core.extensions import db
from models import (SafetyPlan, SleepLog, ReminderPref, Appointment, Assessment, AuditLog, ConsentRecord, CrisisEvent, Goal, JournalEntry, MoodLog,
                    Notification, User, VoiceLog)

PASSWORD = "Str0ng!Passw0rd"
SECRET = "zq-private-journal-text-9917"


def _signup(client, **extra):
    data = dict(name="New", email="new@test.local", password=PASSWORD, confirm_password=PASSWORD,
                role="patient", institution="Test University", consent="yes", age_confirm="yes")
    data.update(extra)
    data = {k: v for k, v in data.items() if v is not None}
    return client.post("/signup", data=data)


def _user(app, email="new@test.local"):
    with app.app_context():
        return User.query.filter_by(email=email).first()


# ---------- signup ----------

def test_signup_needs_consent_and_age_confirm(client, app):
    for missing in ("consent", "age_confirm"):
        r = _signup(client, **{missing: None})
        assert r.status_code == 200 and _user(app) is None, missing
    with app.app_context():
        assert ConsentRecord.query.count() == 0


def test_signup_writes_two_consent_rows_with_version(client, app, monkeypatch):
    monkeypatch.delenv("CONSENT_VERSION", raising=False)
    assert _signup(client).status_code == 302
    with app.app_context():
        rows = ConsentRecord.query.all()
        assert {(r.kind, r.version) for r in rows} == {("privacy", "2026-11"), ("age18", "2026-11")}
        assert all(r.user_id == _user(app).id and r.accepted_at for r in rows)


def test_signup_uses_consent_version_env(client, app, monkeypatch):
    monkeypatch.setenv("CONSENT_VERSION", "2027-02")
    _signup(client)
    with app.app_context():
        assert {r.version for r in ConsentRecord.query.all()} == {"2027-02"}


def test_signup_rejection_keeps_fields_not_password(client, app):
    r = _signup(client, name="Keep Me", age_confirm=None)
    assert r.status_code == 200
    assert PASSWORD not in r.get_data(as_text=True)


def test_duplicate_email_message_is_generic(client, make_user):
    make_user("patient", email="new@test.local")
    html = _signup(client).get_data(as_text=True)
    assert "already registered" not in html and "could not create an account" in html


def test_provider_signup_still_needs_invite(client, app, monkeypatch):
    monkeypatch.setenv("PROVIDER_INVITE_CODE", "letmein")
    _signup(client, role="provider", invite_code="wrong")
    assert _user(app) is None
    _signup(client, role="provider", invite_code="letmein")
    assert _user(app).role == "provider"


# ---------- login ----------

def test_login_failures_share_one_message(client, make_user):
    make_user("patient", email="p@test.local")
    msgs = set()
    for email, pw, role in (("nobody@test.local", PASSWORD, "patient"), ("p@test.local", "Wrong1!pass", "patient"),
                            ("p@test.local", PASSWORD, "provider")):
        html = client.post("/login", data=dict(email=email, password=pw, role=role)).get_data(as_text=True)
        assert "No account found" not in html and "does not match" not in html
        msgs.add("Invalid email, password or role" in html)
    assert msgs == {True}


def test_login_resets_session_and_works(client, make_user):
    make_user("patient", email="p@test.local")
    with client.session_transaction() as s:
        s["stale"] = "leftover"
    r = client.post("/login", data=dict(email="p@test.local", password=PASSWORD, role="patient"))
    assert r.status_code == 302
    with client.session_transaction() as s:
        assert "stale" not in s and s["user_email"] == "p@test.local" and "consent_pending" not in s


def test_needs_reconsent_and_login_redirect(app, client, make_user, monkeypatch):
    from routes.auth import has_current_consent, needs_reconsent
    uid = make_user("patient", email="p@test.local")
    with app.app_context():
        user = db.session.get(User, uid)
        assert needs_reconsent(user) is False  # legacy account without rows is not interrupted
        db.session.add(ConsentRecord(user_id=uid, kind="privacy", version="2020-01"))
        db.session.commit()
        assert needs_reconsent(user) is True and has_current_consent(uid) is False
    r = client.post("/login", data=dict(email="p@test.local", password=PASSWORD, role="patient"))
    assert r.status_code == 302 and r.headers["Location"].endswith("/consent")


# ---------- consent page and the guard ----------

def _pending(client, app, make_user):
    uid = make_user("patient", email="g@test.local")
    with client.session_transaction() as s:
        s.update(user_id=uid, user_email="g@test.local", user_role="patient", user_name="G",
                 user_institution="Test University", consent_pending=True)
    return uid


def test_guard_redirects_everything_except_exempt(client, app, make_user):
    _pending(client, app, make_user)
    for path in ("/patient/dashboard", "/profile", "/provider/dashboard"):
        r = client.get(path)
        assert r.status_code == 302 and r.headers["Location"].endswith("/consent"), path
    r = client.get("/api/chats/1/messages")
    assert r.status_code == 403 and r.get_json()["error"] == "consent_required"
    assert client.get("/consent").status_code == 200
    assert not (client.get("/privacy").status_code == 302 and "/consent" in client.get("/privacy").headers.get("Location", ""))
    assert client.get("/logout").status_code == 302
    with client.session_transaction() as s:
        assert "consent_pending" not in s


def test_consent_post_records_and_clears_flag(client, app, make_user):
    uid = _pending(client, app, make_user)
    r = client.post("/consent", data={"consent": "yes"})
    assert r.status_code == 400
    with app.app_context():
        assert ConsentRecord.query.count() == 0
    r = client.post("/consent", data={"consent": "yes", "age_confirm": "yes"})
    assert r.status_code == 302
    with app.app_context():
        assert {c.kind for c in ConsentRecord.query.filter_by(user_id=uid)} == {"privacy", "age18"}
    with client.session_transaction() as s:
        assert "consent_pending" not in s
    assert client.get("/patient/dashboard").status_code == 200


def test_google_new_user_goes_to_consent(app):
    info = {"id": "gx", "email": "gnew@test.local", "name": "G", "verified_email": True}
    resp = SimpleNamespace(ok=True, json=lambda: info, text="")
    bp = SimpleNamespace(session=SimpleNamespace(get=lambda url: resp))
    from flask import session
    with app.test_request_context("/"):
        out = app_module.google_logged_in(bp, {"access_token": "t"})
        assert out.status_code == 302 and out.headers["Location"].endswith("/consent")
        assert session["consent_pending"] is True


# ---------- unauthenticated ----------

def test_account_routes_need_login(client):
    assert client.get("/account/data").status_code == 302
    assert client.post("/account/export").status_code == 302
    assert client.post("/account/delete", data={"password": "x"}).status_code == 302
    ajax = {"X-Requested-With": "XMLHttpRequest"}
    assert client.post("/account/export", headers=ajax).status_code == 401


# ---------- export ----------

def _fill(app, uid, text=SECRET):
    with app.app_context():
        db.session.add_all([
            JournalEntry(user_id=uid, title="t", content=text),
            VoiceLog(user_id=uid, filename="f.wav", transcript=text, ai_analysis=text),
            MoodLog(user_id=uid, mood_score=5, notes=text),
            Assessment(user_id=uid, assessment_type="PHQ-9", score=3, ai_insights=text),
            Goal(user_id=uid, title=text, description=text, category="mental_health", start_date=date.today(), target_date=date.today()),
            Notification(recipient_id=uid, message=text),
            CrisisEvent(user_id=uid, source="chat", severity=3, reason="self_harm"),
            ConsentRecord(user_id=uid, kind="privacy", version="2026-11"),
            SafetyPlan(user_id=uid, warning_signs=text), SleepLog(user_id=uid, night_date=date.today(), bedtime="23:00",
                                                                   wake_time="07:00", duration_minutes=480, quality=3, note=text),
            ReminderPref(user_id=uid, nonce="n0nce-" + str(uid)),
        ])
        db.session.commit()


def test_export_has_only_own_data(app, patient_client, make_user):
    c, uid = patient_client
    other = make_user("patient")
    _fill(app, uid)
    _fill(app, other, text="other-persons-secret-text")
    r = c.post("/account/export")
    assert r.status_code == 200
    assert "attachment" in r.headers["Content-Disposition"] and r.headers["Cache-Control"] == "no-store"
    body = r.get_data(as_text=True)
    data = json.loads(body)
    assert "password_hash" not in body and "pbkdf2" not in body and "scrypt" not in body
    assert "other-persons-secret-text" not in body
    assert data["profile"]["id"] == uid
    assert len(data["journal_entries"]) == 1 and data["journal_entries"][0]["content"] == SECRET
    assert data["voice_logs"][0]["transcript"] == SECRET and len(data["assessments"]) == 1
    assert data["crisis_events"][0]["reason"] == "self_harm" and "acknowledged_by" not in data["crisis_events"][0]
    assert "clinical_notes" not in data
    assert data["safety_plans"][0]["warning_signs"] == SECRET and data["sleep_logs"][0]["note"] == SECRET
    assert len(data["reminder_prefs"]) == 1 and len(data["safety_plans"]) == 1
    with app.app_context():
        row = AuditLog.query.filter_by(action="export_account").one()
        assert row.actor_id == uid and not row.meta


# ---------- delete ----------

def _all_text(app):
    """Every stored string of every table, joined, to prove a value is gone from the whole database."""
    out = []
    with app.app_context():
        for table in db.metadata.sorted_tables:
            for row in db.session.execute(table.select()).mappings():
                out.append(json.dumps(dict(row), default=str))
    return "\n".join(out)


def test_wrong_password_cannot_delete(app, patient_client):
    c, uid = patient_client
    _fill(app, uid)
    r = c.post("/account/delete", data={"password": "Nope1!nope"})
    assert r.status_code == 302
    with app.app_context():
        assert db.session.get(User, uid) is not None and JournalEntry.query.count() == 1
        assert AuditLog.query.filter_by(action="delete_account").count() == 0
    assert c.post("/account/delete", data={}).status_code == 302
    with app.app_context():
        assert db.session.get(User, uid) is not None


def test_delete_removes_everything_and_logs_only_id(app, patient_client, make_user):
    c, uid = patient_client
    provider = make_user("provider")
    _fill(app, uid)
    with app.app_context():
        db.session.add(Appointment(user_id=uid, provider_id=provider, date=date.today(), time="10:00",
                                   appointment_type="video", notes=SECRET))
        db.session.commit()
    assert SECRET in _all_text(app)
    r = c.post("/account/delete", data={"password": PASSWORD})
    assert r.status_code == 302
    with app.app_context():
        assert db.session.get(User, uid) is None
        for model in (JournalEntry, VoiceLog, MoodLog, Assessment, Goal, Notification, CrisisEvent, ConsentRecord, Appointment,
                      SafetyPlan, SleepLog, ReminderPref):
            assert model.query.count() == 0, model.__name__
        log = AuditLog.query.filter_by(action="delete_account").one()
        assert log.target_id == uid and log.actor_id is None and not log.meta
    assert SECRET not in _all_text(app)
    assert c.get("/patient/dashboard").status_code == 302  # session cleared


def test_delete_provider_keeps_patient_rows_and_nulls_links(app, provider_client, make_user):
    c, pid = provider_client
    patient = make_user("patient")
    with app.app_context():
        appt = Appointment(user_id=patient, provider_id=pid, date=date.today(), time="10:00", appointment_type="video")
        ev = CrisisEvent(user_id=patient, source="chat", severity=3, reason="x", acknowledged_by=pid,
                         acknowledged_at=datetime.utcnow())
        db.session.add_all([appt, ev])
        db.session.add(AuditLog(actor_id=pid, action="view_patient", target_type="user", target_id=patient))
        db.session.commit()
        appt_id, ev_id = appt.id, ev.id
    assert c.post("/account/delete", data={"password": PASSWORD}).status_code == 302
    with app.app_context():
        assert db.session.get(User, pid) is None and db.session.get(User, patient) is not None
        assert db.session.get(Appointment, appt_id).provider_id is None
        assert db.session.get(CrisisEvent, ev_id).acknowledged_by is None
        assert AuditLog.query.filter_by(action="view_patient").one().actor_id is None


def test_google_only_user_deletes_with_email_and_phrase(app, client, make_user, login):
    uid = make_user("patient", email="goog@test.local")
    with app.app_context():
        db.session.get(User, uid).google_id = "g-123"
        db.session.commit()
    login(uid)
    assert client.post("/account/delete", data={"password": PASSWORD}).status_code == 302
    assert client.post("/account/delete", data={"confirm_email": "goog@test.local", "confirm_phrase": "nope"}).status_code == 302
    with app.app_context():
        assert db.session.get(User, uid) is not None
    client.post("/account/delete", data={"confirm_email": "GOOG@test.local", "confirm_phrase": "DELETE MY ACCOUNT"})
    with app.app_context():
        assert db.session.get(User, uid) is None


def test_account_data_page_renders(patient_client):
    c, _ = patient_client
    html = c.get("/account/data").get_data(as_text=True)
    assert "/account/export" in html and "/account/delete" in html
