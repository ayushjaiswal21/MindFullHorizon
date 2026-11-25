"""Security regression tests (agent A): auth on JSON APIs, roles, sockets, headers, OAuth."""
import os
import subprocess
import sys
from datetime import date
from types import SimpleNamespace

import pytest

import app as app_module
from conftest import PASSWORD, ROOT
from extensions import db
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


# ---------- SocketIO ----------

def _appt(app, patient, provider, status="accepted"):
    with app.app_context():
        db.session.add(Appointment(user_id=patient, provider_id=provider, date=date.today(), time="10:00",
                                   appointment_type="video", status=status))
        db.session.commit()


def _sio(app, client):
    return app_module.socketio.test_client(app, flask_test_client=client)


def _joined(sio, room):
    sio.get_received()
    sio.emit("join", {"room": room})
    return "message" in [m["name"] for m in sio.get_received()]


def test_socket_join_requires_login(app, client, make_user):
    pid = make_user("patient")
    sio = _sio(app, client)
    assert not _joined(sio, f"telehealth_room_{pid}")


def test_socket_patient_only_own_room(app, patient_client, make_user):
    c, uid = patient_client
    other = make_user("patient")
    sio = _sio(app, c)
    assert _joined(sio, f"telehealth_room_{uid}")
    assert not _joined(sio, f"telehealth_room_{other}")
    assert not _joined(sio, "user_%d" % other)
    assert not _joined(sio, "telehealth_room_abc")


def test_socket_provider_needs_appointment_and_same_institution(app, make_user, login, client):
    pid = make_user("patient")
    same = make_user("provider")
    other_inst = make_user("provider", institution="Elsewhere U")
    nobody = make_user("provider")
    _appt(app, pid, same)
    _appt(app, pid, other_inst)
    room = f"telehealth_room_{pid}"
    for prov, ok in ((same, True), (other_inst, False), (nobody, False)):
        c = app.test_client()
        from conftest import _login_as
        _login_as(c, app, prov)
        assert _joined(_sio(app, c), room) is ok


def test_socket_signalling_requires_joined_room(app, patient_client, make_user):
    c, uid = patient_client
    other = make_user("patient")
    peer_client = app.test_client()
    from conftest import _login_as
    _login_as(peer_client, app, other)
    peer = _sio(app, peer_client)
    peer.emit("join", {"room": f"telehealth_room_{other}"})
    peer.get_received()
    sio = _sio(app, c)
    sio.emit("offer", {"room": f"telehealth_room_{other}", "sdp": "x"})
    assert "offer" not in [m["name"] for m in peer.get_received()]


def test_socket_signalling_anonymous_ignored(app, client):
    sio = _sio(app, client)
    sio.emit("offer", {"room": "telehealth_room_1"})
    sio.emit("leave", {"room": "telehealth_room_1"})
    sio.emit("join", "not a dict")  # must not raise


def test_socketio_cors_not_wildcard():
    assert app_module.socketio.server.eio.cors_allowed_origins != "*"


def test_telehealth_session_access(app, client, make_user):
    pid = make_user("patient")
    prov = make_user("provider")
    stranger = make_user("provider")
    _appt(app, pid, prov)
    from conftest import _login_as
    assert client.get(f"/telehealth_session/{pid}").status_code == 302
    for uid, code in ((pid, 403), (stranger, 403), (prov, 200)):
        c = app.test_client()
        _login_as(c, app, uid)
        assert c.get(f"/telehealth_session/{pid}").status_code == code


# ---------- duplicates removed ----------

def test_duplicate_routes_gone(app):
    rules = {r.rule for r in app.url_map.iter_rules()}
    for dup in ("/api/digital-detox-data", "/api/log-digital-detox",
                "/send_prescription/<int:patient_id>", "/wellness-report/<int:user_id>"):
        assert dup not in rules, dup
    assert "/provider/send_prescription/<int:patient_id>" not in rules  # removed: prescribing moved behind a verified doctor
    assert "/patient/api/log-digital-detox" in rules


# ---------- Google OAuth ----------

def _google(app, info):
    resp = SimpleNamespace(ok=True, json=lambda: info, text="")
    bp = SimpleNamespace(session=SimpleNamespace(get=lambda url: resp))
    with app.test_request_context("/"):
        out = app_module.google_logged_in(bp, {"access_token": "t"})
        return out


def test_google_new_user_has_unusable_password_and_patient_dashboard(app):
    out = _google(app, {"id": "g1", "email": "g@test.local", "name": "G", "verified_email": True})
    assert out.status_code == 302 and "/consent" in out.headers["Location"]  # new Google users accept the notice first (P-05)
    with app.app_context():
        u = User.query.filter_by(email="g@test.local").one()
        assert u.password_hash and not u.check_password("")


def test_google_existing_provider_redirects_to_provider_dashboard(app, make_user):
    make_user("provider", email="pv@test.local")
    out = _google(app, {"id": "g2", "email": "pv@test.local", "name": "P", "verified_email": True})
    assert out.status_code == 302 and "/provider/" in out.headers["Location"]


def test_google_unverified_email_does_not_take_over_account(app, make_user):
    make_user("patient", email="victim@test.local")
    out = _google(app, {"id": "g3", "email": "victim@test.local", "name": "X", "verified_email": False})
    assert out.status_code == 302 and "/login" in out.headers["Location"]
    with app.app_context():
        assert User.query.filter_by(email="victim@test.local").one().google_id is None


def test_google_failure_redirects_to_login(app):
    with app.test_request_context("/"):
        out = app_module.google_logged_in(SimpleNamespace(), None)
    assert out.status_code == 302 and "/login" in out.headers["Location"]


def test_google_login_does_not_log_profile(app, caplog):
    import logging
    with caplog.at_level(logging.DEBUG):
        _google(app, {"id": "g4", "email": "secret-mail@test.local", "name": "Q", "verified_email": True})
    assert "picture" not in caplog.text and "{'id'" not in caplog.text


# ---------- headers, cookies, limits ----------

def test_security_headers(client):
    r = client.get("/login")
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["Referrer-Policy"]
    assert r.headers["Permissions-Policy"]
    assert "Content-Security-Policy" in r.headers  # enforcing; details in tests/test_csp.py
    assert "Content-Security-Policy-Report-Only" not in r.headers
    assert "Strict-Transport-Security" not in r.headers  # only in production


def test_cookies_are_lax(app):
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
    assert app.config["REMEMBER_COOKIE_SAMESITE"] == "Lax"


def test_default_limit_allows_normal_browsing_but_login_is_strict(client):
    lim = app_module.limiter
    lim.enabled = True
    lim.reset()
    try:
        codes = [client.get("/api/status").status_code for _ in range(40)]
        assert 429 not in codes
        codes = [client.post("/login", data={"email": "a@b.c", "password": "x", "role": "patient"}).status_code
                 for _ in range(12)]
        assert codes[-1] == 429 and codes[0] != 429
    finally:
        lim.reset()
        lim.enabled = False


def test_error_handler_matches_blueprint_endpoint():
    src = open(os.path.join(ROOT, "app.py"), encoding="utf-8").read()
    assert "request.endpoint == 'patient_journal'" not in src


def test_profile_weak_password_change_is_rejected_not_500(patient_client):
    c, _ = patient_client
    r = c.post("/profile", data={"name": "N", "email": "p1@test.local", "password": "weak"})
    assert r.status_code == 302


def test_chat_passes_helplines_and_records_crisis_for_session_user(patient_client, monkeypatch, app):
    c, uid = patient_client
    calls = []

    async def fake(text, user_id=None, **kw):
        return {"reply": "r", "severity": 3, "reason": "x", "recommended_action": "emergency_hotline",
                "escalate": True, "helplines": [{"name": "Tele-MANAS", "number": "14416"}]}

    monkeypatch.setattr("routes.chat.ask_with_severity", fake)
    monkeypatch.setattr("routes.chat.record_crisis", lambda *a: calls.append(a))
    body = c.post("/api/chat", json={"message": "hi", "user_id": 999}).get_json()
    assert body["escalate"] is True and body["helplines"][0]["number"] == "14416"
    assert calls == [(uid, "chat", 3, "chat_self_harm")]


def test_severity_info_uses_shared_bands(app):
    with app.test_request_context("/"):
        ctx = {}
        app.update_template_context(ctx)
        f = ctx["get_severity_info"]
        assert f("PHQ-9", 15)["severity"] == "Moderately Severe"
        assert f("PHQ-9 Depression Screening", 20)["severity"] == "Severe"
        assert f("GAD-7", 4)["severity"] == "Minimal"
