"""Deploy-readiness code changes: cookie sessions with a stamp, no uploads on disk, ProxyFix, logging, Neon engine options.

See docs/DEPLOY.md section 13. No network; SQLite temp DB from conftest.
"""
import io
import logging
import os
import sys
import types
from logging.handlers import RotatingFileHandler

import pytest
from flask import Flask, request, url_for
from flask_limiter.util import get_remote_address
from sqlalchemy import event
from sqlalchemy.exc import OperationalError

import app as app_module
from extensions import db
from models import User, VoiceLog
from utils import database_utils, log_config, proxy
from utils.database_utils import engine_options, normalize_db_url, wait_for_database
from utils.session_stamp import make_stamp

PW = "Str0ng!Passw0rd"
XHR = {"X-Requested-With": "XMLHttpRequest"}
UPLOADS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "uploads")


def _form_login(client, email, role="patient"):
    return client.post("/login", data={"email": email, "password": PW, "role": role})


def _email(app, uid):
    with app.app_context():
        return db.session.get(User, uid).email


# ---------- 1. sessions: signed cookies plus a stamp ----------
def test_no_server_side_session_storage(app):
    import extensions
    assert not hasattr(extensions, "flask_session") and "SESSION_TYPE" not in app.config
    assert "SESSION_FILE_DIR" not in app.config and not hasattr(extensions, "prune_session_files")
    assert app.config["SESSION_COOKIE_NAME"] == "mindfullhorizon_session"


def test_login_sets_stamp_and_cookie_flags(app, client, make_user):
    uid = make_user("patient")
    app.config["SESSION_COOKIE_SECURE"] = True  # production value
    try:
        r = _form_login(client, _email(app, uid))
    finally:
        app.config["SESSION_COOKIE_SECURE"] = False
    cookie = next(h for h in r.headers.getlist("Set-Cookie") if h.startswith("mindfullhorizon_session="))
    assert "HttpOnly" in cookie and "SameSite=Lax" in cookie and "Secure" in cookie
    with client.session_transaction() as s:
        assert s["user_id"] == uid and len(s["stamp"]) == 16 and s.permanent


def test_session_cookie_stays_well_under_4kb(app, client, make_user):
    uid = make_user("patient", name="N" * 100, institution="I" * 150)
    r = _form_login(client, _email(app, uid))
    cookie = next(h for h in r.headers.getlist("Set-Cookie") if h.startswith("mindfullhorizon_session="))
    assert len(cookie) < 1500  # browsers drop cookies over about 4096 bytes


def test_valid_stamp_keeps_session_and_costs_one_query(app, client, make_user):
    uid = make_user("patient")
    _form_login(client, _email(app, uid))
    seen = []

    def count(conn, cursor, statement, *a):
        seen.append(statement)
    with app.app_context():
        event.listen(db.engine, "before_cursor_execute", count)
        try:
            assert client.get("/profile").status_code == 200
            n_profile = sum("FROM users" in q and "password_hash" in q and "users.name" not in q for q in seen)
            seen.clear()
            client.get("/health")
            client.get("/static/css/styles.css")
        finally:
            event.remove(db.engine, "before_cursor_execute", count)
    assert n_profile >= 1 and seen == []  # health and static paths skip the stamp query entirely


@pytest.mark.parametrize("change", ["password", "role", "delete"])
def test_stale_stamp_invalidates_cookie(app, client, make_user, change):
    uid = make_user("patient")
    _form_login(client, _email(app, uid))
    assert client.get("/profile").status_code == 200
    with app.app_context():
        user = db.session.get(User, uid)
        if change == "password":
            user.set_password("An0ther!Passw0rd")
        elif change == "role":
            user.role = "provider"
        else:
            db.session.delete(user)
        db.session.commit()
    r = client.get("/profile")
    assert r.status_code == 302 and "/login" in r.headers["Location"]
    with client.session_transaction() as s:
        assert "user_id" not in s


def test_profile_password_change_keeps_own_session(app, client, make_user):
    uid = make_user("patient")
    _form_login(client, _email(app, uid))
    client.post("/profile", data={"name": "New Name", "email": _email(app, uid), "password": "An0ther!Passw0rd"})
    assert client.get("/profile").status_code == 200  # the stamp was refreshed in the same request


def test_stamp_required_outside_testing(app, client, make_user, login):
    login(make_user("patient"))  # conftest helper: writes the session directly, no stamp
    assert client.get("/profile").status_code == 200  # TESTING: helper-written sessions are accepted
    app.config["TESTING"] = False
    try:
        r = client.get("/profile")
    finally:
        app.config["TESTING"] = True
    assert r.status_code == 302 and "/login" in r.headers["Location"]


def test_stamp_depends_on_secret_key_and_inputs(app):
    with app.app_context():
        a = make_stamp(1, "h", "patient")
        assert a == make_stamp(1, "h", "patient") and a != make_stamp(1, "h2", "patient") != make_stamp(1, "h", "provider")
        old = app.secret_key
        app.secret_key = "other"
        try:
            assert make_stamp(1, "h", "patient") != a
        finally:
            app.secret_key = old


# ---------- 2. uploads: nothing persistent on local disk ----------
def _uploads():
    return sorted(set(os.listdir(UPLOADS)) - {".gitkeep"}) if os.path.isdir(UPLOADS) else []


def test_voice_upload_stores_measurements_only(app, patient_client):
    c, uid = patient_client
    before = _uploads()
    r = c.post("/api/upload-voice", data={"audio": (io.BytesIO(b"RIFF....WAVEfmt "), "voice_log.wav", "audio/wav")},
               content_type="multipart/form-data", headers=XHR)
    assert r.status_code == 200
    with app.app_context():
        row = VoiceLog.query.one()
        assert row.filename == "not-stored" and row.ai_analysis
    assert _uploads() == before and "UPLOAD_FOLDER" not in app.config
    page = c.get("/patient/voice-logs").get_data(as_text=True)
    assert "static/uploads" not in page and "<audio controls preload=\"none\"" not in page


def test_extract_features_deletes_its_temp_file_on_failure(monkeypatch):
    from utils import voice_features
    seen = []

    def boom(path, **kw):
        seen.append(path)
        raise RuntimeError("bad audio")
    monkeypatch.setitem(sys.modules, "librosa", types.SimpleNamespace(load=boom))
    monkeypatch.setitem(sys.modules, "numpy", types.ModuleType("numpy"))
    monkeypatch.setattr(voice_features, "LIBROSA_AVAILABLE", True)
    upload = types.SimpleNamespace(save=lambda f: f.write(b"audio"))
    assert voice_features.extract_features(upload, "wav") == ({}, "neutral")
    assert len(seen) == 1 and not os.path.exists(seen[0])


def test_profile_picture_upload_is_gone(app, patient_client):
    c, uid = patient_client
    before = _uploads()
    page = c.get("/profile").get_data(as_text=True)
    assert 'type="file"' not in page and "static/uploads" not in page and "avatar" in page
    c.post("/profile", data={"name": "X", "email": _email(app, uid), "profile_pic": (io.BytesIO(b"\x89PNG"), "a.png")},
           content_type="multipart/form-data")
    with app.app_context():
        assert db.session.get(User, uid).profile_pic is None
    assert _uploads() == before


# ---------- 3. ProxyFix ----------
def _proxy_app(env):
    flask_app = Flask("proxy_test")
    flask_app.config["SERVER_NAME"] = None
    proxy.init_proxy(flask_app, env)

    @flask_app.route("/x")
    def x():
        return {"secure": request.is_secure, "ip": get_remote_address(), "host": request.host,
                "url": url_for("x", _external=True)}
    return flask_app


FWD = {"HTTP_X_FORWARDED_PROTO": "https", "HTTP_X_FORWARDED_FOR": "203.0.113.9", "HTTP_X_FORWARDED_HOST": "app.example.com"}


@pytest.mark.parametrize("env", [{"FLASK_ENV": "production"}, {"TRUST_PROXY": "1"}, {"TRUST_PROXY": "true"}])
def test_proxyfix_uses_forwarded_headers(env):
    body = _proxy_app(env).test_client().get("/x", environ_overrides=FWD).get_json()
    assert body == {"secure": True, "ip": "203.0.113.9", "host": "app.example.com", "url": "https://app.example.com/x"}


@pytest.mark.parametrize("env", [{}, {"FLASK_ENV": "development"}, {"TRUST_PROXY": "0"}])
def test_proxyfix_is_off_without_a_proxy(env):
    body = _proxy_app(env).test_client().get("/x", environ_overrides=FWD).get_json()
    assert body["secure"] is False and body["ip"] != "203.0.113.9" and body["url"].startswith("http://")


def test_same_origin_check_behind_proxy(app):
    original = app.wsgi_app
    headers = {"Origin": "https://app.example.com", "X-Analytics-Consent": "granted"}
    body = {"name": "page_view", "path": "/"}
    try:
        assert proxy.init_proxy(app, {"TRUST_PROXY": "1"})
        r = app.test_client().post("/api/event", json=body, headers=headers, environ_overrides=FWD)
        assert r.status_code != 403  # Origin matches the forwarded host
        r = app.test_client().post("/api/event", json=body, headers={**headers, "Origin": "https://evil.example"},
                                   environ_overrides=FWD)
        assert r.status_code == 403
    finally:
        app.wsgi_app = original
    assert app.test_client().post("/api/event", json=body, headers=headers).status_code == 403  # no proxy: host differs


# ---------- 4. logging ----------
def test_app_logger_is_not_models_logger():
    assert app_module.logger.name == log_config.APP_LOGGER == "app"
    assert app_module.logger is not sys.modules["models"].logger


def test_production_logs_to_stdout_only(tmp_path):
    lg = log_config.setup_app_logging("deploy_test_prod", {"FLASK_ENV": "production"}, str(tmp_path))
    assert not any(isinstance(h, logging.FileHandler) for h in lg.handlers) and list(tmp_path.iterdir()) == []
    lg = log_config.setup_app_logging("deploy_test_flag", {"LOG_TO_STDOUT": "1"}, str(tmp_path))
    assert not any(isinstance(h, logging.FileHandler) for h in lg.handlers)


def test_development_writes_rotating_file_in_logs_dir(tmp_path):
    lg = log_config.setup_app_logging("deploy_test_dev", {}, str(tmp_path / "logs"))
    handlers = [h for h in lg.handlers if isinstance(h, RotatingFileHandler)]
    assert len(handlers) == 1 and handlers[0].baseFilename == str(tmp_path / "logs" / "mindful_horizon.log")
    handlers[0].close()
    assert "logs/" in open(os.path.join(log_config.ROOT, ".gitignore"), encoding="utf-8").read()


# ---------- 5. Neon engine options and first-connect retry ----------
def test_pooled_host_gets_no_startup_options():
    pooled = engine_options("postgresql://u:p@ep-a-b-pooler.c-2.ap-southeast-1.aws.neon.tech/db", env={})
    direct = engine_options("postgresql://u:p@ep-a-b.c-2.ap-southeast-1.aws.neon.tech/db", env={})
    assert "options" not in pooled["connect_args"] and "statement_timeout" in direct["connect_args"]["options"]
    assert pooled["connect_args"]["connect_timeout"] == direct["connect_args"]["connect_timeout"] == 15
    assert pooled["pool_pre_ping"] is True and pooled["pool_recycle"] == 300 and pooled["pool_size"] <= 5


def test_connect_timeout_and_recycle_are_tunable():
    o = engine_options("postgresql://h/db", env={"DB_CONNECT_TIMEOUT": "7", "DB_POOL_RECYCLE": "120"})
    assert o["connect_args"]["connect_timeout"] == 7 and o["pool_recycle"] == 120
    assert engine_options(normalize_db_url("postgres://u:p@h/db"), env={})["pool_size"] == 5


def test_first_connect_retries_then_succeeds(app, monkeypatch):
    sleeps, calls = [], []
    monkeypatch.setattr(database_utils.time, "sleep", sleeps.append)

    def probe():
        calls.append(1)
        if len(calls) < 3:
            raise OperationalError("SELECT 1", {}, Exception("server closed the connection"))
    with app.app_context():
        assert wait_for_database(3, 1.0, probe) is True
    assert len(calls) == 3 and sleeps == [1.0, 2.0]


def test_first_connect_gives_up_after_three_tries(app, monkeypatch):
    sleeps = []
    monkeypatch.setattr(database_utils.time, "sleep", sleeps.append)

    def probe():
        raise OperationalError("SELECT 1", {}, Exception("down"))
    with app.app_context():
        assert wait_for_database(3, 1.0, probe) is False
    assert len(sleeps) == 2  # no sleep after the last try


def test_non_database_errors_are_not_retried(app):
    def probe():
        raise ValueError("bug")
    with app.app_context(), pytest.raises(ValueError):
        wait_for_database(3, 0, probe)
