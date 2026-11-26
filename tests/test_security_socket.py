"""Security regression tests (agent A): SocketIO room auth, Google OAuth, headers/cookies/limits.
Split out of test_security.py (300-line rule); JSON API auth, role escalation and SECRET_KEY checks are
in test_security_api.py."""
import os
from datetime import date
from types import SimpleNamespace

import app as app_module
from conftest import ROOT
from core.extensions import db
from models import Appointment, User


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
