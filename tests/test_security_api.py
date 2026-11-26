"""Security regression tests (agent A): auth on JSON APIs, role escalation, SECRET_KEY startup checks.
Split out of test_security.py (300-line rule); SocketIO, Google OAuth and header/cookie/limit tests are
in test_security_socket.py."""
import os
import subprocess
import sys

import pytest

import app as app_module
from conftest import PASSWORD, ROOT
from core.extensions import db
from models import Appointment, MoodLog, User


# ---------- open JSON endpoints ----------

@pytest.mark.parametrize("method,url", [
    ("get", "/api/chats/1/messages"),
    ("post", "/api/chat"),
    ("get", "/api/mood"),
    ("post", "/api/mood"),
    ("post", "/api/ask"),
    ("post", "/api/play-mood"),
    ("post", "/api/chat/book-appointment"),
])
def test_anonymous_json_api_gets_401(client, method, url):
    assert getattr(client, method)(url, json={"message": "x", "value": 3, "prompt": "x", "mood": "calm"}).status_code == 401


def test_chat_messages_only_own_id(patient_client, make_user):
    c, uid = patient_client
    other = make_user("patient")
    assert c.get(f"/api/chats/{other}/messages").status_code == 403
    assert c.get(f"/api/chats/{uid}/messages").status_code == 200


def test_chat_ignores_client_user_id(patient_client, monkeypatch):
    c, uid = patient_client
    seen = {}

    async def fake(text, user_id=None, **kw):
        seen["uid"] = user_id
        return {"reply": "hi", "severity": 0, "reason": "", "recommended_action": None}

    monkeypatch.setattr("routes.chat.ask_with_severity", fake)
    r = c.post("/api/chat", json={"message": "hello", "user_id": 999})
    assert r.status_code == 200 and seen["uid"] == uid


def test_chat_bad_payload_is_400_without_details(patient_client):
    c, _ = patient_client
    r = c.post("/api/chat", data="not json", content_type="text/plain")
    assert r.status_code == 400


def test_mood_writes_and_reads_session_user_only(patient_client, make_user, app):
    c, uid = patient_client
    other = make_user("patient")
    with app.app_context():
        db.session.add(MoodLog(user_id=other, mood_score=2))
        db.session.commit()
    r = c.post("/api/mood", json={"value": 4})
    assert r.status_code == 201
    with app.app_context():
        assert MoodLog.query.filter_by(user_id=uid, mood_score=4).count() == 1
    moods = c.get("/api/mood").get_json()["moods"]
    assert [m["mood"] for m in moods] == [4]


@pytest.mark.parametrize("value", ["abc", None, 99, 0, [1]])
def test_mood_rejects_bad_values(patient_client, value):
    c, _ = patient_client
    r = c.post("/api/mood", json={"value": value})
    assert r.status_code == 400
    assert "Traceback" not in r.get_data(as_text=True)


def test_ask_validates_json_and_requires_prompt(patient_client, monkeypatch):
    c, _ = patient_client
    assert c.post("/api/ask", data="x", content_type="text/plain").status_code == 400
    assert c.post("/api/ask", json={"prompt": ""}).status_code == 400
    monkeypatch.setattr("ai.service.ask", lambda p, **kw: "ok")
    r = c.post("/api/ask", json={"prompt": "hello"})
    assert r.status_code == 200 and r.get_json()["response"] == "ok"


def test_play_mood_never_launches_server_side(patient_client, monkeypatch):
    c, _ = patient_client
    audio_dir = os.path.join(ROOT, "data", "binaural-beats-dataset", "audio")
    os.makedirs(audio_dir, exist_ok=True)
    fn = os.path.join(audio_dir, "zzsectest.mp3")
    open(fn, "wb").close()
    calls = []
    monkeypatch.setattr(os, "startfile", lambda p: calls.append(p), raising=False)
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: calls.append(a))
    try:
        r = c.post("/api/play-mood", json={"mood": "zzsectest"})
    finally:
        os.remove(fn)
    assert not calls
    body = r.get_json()
    assert r.status_code == 200 and body["action"] == "local" and body["url"].endswith("zzsectest.mp3")
    assert "path" not in body


def test_log_error_cannot_inject_log_lines(client, caplog):
    import logging
    with caplog.at_level(logging.DEBUG):
        r = client.post("/api/log-error", json={"message": "boom\nINFO - fake admin login" + "A" * 5000,
                                                "filename": "a\r\nb", "lineno": "1\n2"})
    assert r.status_code == 200
    text = "\n".join(rec.getMessage() for rec in caplog.records)
    assert "\nINFO - fake" not in text and "\r" not in text
    assert max(len(rec.getMessage()) for rec in caplog.records) < 1000


def test_book_appointment_creates_pending_for_session_user(patient_client, provider_client, app):
    c, uid = patient_client
    r = c.post("/api/chat/book-appointment", json={"user_message": "I feel low", "user_id": 999})
    assert r.status_code == 201 and r.get_json()["ok"] is True
    with app.app_context():
        appt = Appointment.query.one()
        assert appt.user_id == uid and appt.status == "pending"
    pc, _ = provider_client
    assert pc.post("/api/chat/book-appointment", json={}).status_code == 403


# ---------- role escalation ----------

def _signup(client, role, **extra):
    data = dict(name="New", email="new@test.local", password=PASSWORD, confirm_password=PASSWORD,
                role=role, institution="Test University", consent="yes", age_confirm="yes")
    data.update(extra)
    return client.post("/signup", data=data)


def _role_of(app, email="new@test.local"):
    with app.app_context():
        u = User.query.filter_by(email=email).first()
        return u.role if u else None


def test_signup_patient_ok_provider_blocked_by_default(client, app, monkeypatch):
    monkeypatch.delenv("PROVIDER_INVITE_CODE", raising=False)
    _signup(client, "provider", invite_code="anything")
    assert _role_of(app) is None
    _signup(client, "patient")
    assert _role_of(app) == "patient"


def test_signup_provider_needs_matching_invite_code(client, app, monkeypatch):
    monkeypatch.setenv("PROVIDER_INVITE_CODE", "s3cret-code")
    _signup(client, "provider", invite_code="wrong")
    assert _role_of(app) is None
    _signup(client, "provider")
    assert _role_of(app) is None
    _signup(client, "provider", invite_code="s3cret-code")
    assert _role_of(app) == "provider"


def test_signup_unknown_role_rejected(client, app):
    _signup(client, "admin")
    assert _role_of(app) is None


def test_save_role_requires_login(client):
    r = client.post("/save_role", data={"role": "patient"})
    assert r.status_code == 302 and "/login" in r.headers["Location"]


def test_save_role_cannot_make_provider(patient_client, app):
    c, uid = patient_client
    c.post("/save_role", data={"role": "provider"})
    with app.app_context():
        assert db.session.get(User, uid).role == "patient"
    with c.session_transaction() as s:
        assert s["user_role"] == "patient"


def test_save_role_cannot_demote_provider(provider_client, app):
    c, uid = provider_client
    c.post("/save_role", data={"role": "patient"})
    with app.app_context():
        assert db.session.get(User, uid).role == "provider"


# ---------- SECRET_KEY ----------

def _import_app_env(**env):
    base = {k: v for k, v in os.environ.items() if k not in ("SECRET_KEY", "FLASK_ENV")}
    base.update(env)
    return subprocess.run([sys.executable, "-c", "import app; print(len(app.app.secret_key))"],
                          cwd=ROOT, env=base, capture_output=True, text=True, timeout=120)


def test_production_without_secret_key_refuses_to_start():
    r = _import_app_env(FLASK_ENV="production", SECRET_KEY="")
    assert r.returncode != 0 and "SECRET_KEY" in r.stderr


def test_dev_without_secret_key_gets_random_key_not_default():
    r = _import_app_env(FLASK_ENV="development", SECRET_KEY="")
    assert r.returncode == 0, r.stderr
    assert app_module.app.secret_key != "supersecretkey"
    assert int(r.stdout.strip().splitlines()[-1]) >= 32
