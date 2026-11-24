"""/health, /ready, request ids, access log and log redaction (Q1a)."""
import logging

import pytest
from sqlalchemy import text

import routes.ops as ops
from extensions import db
from utils import jobs
from utils.logging_setup import RedactionFilter, redact


def test_health_is_constant_and_needs_no_db(client, monkeypatch):
    def broken(*a, **k):
        raise RuntimeError("db password is hunter2")
    monkeypatch.setattr(ops, "text", broken)  # /ready would fail; /health must not care
    monkeypatch.setattr(jobs, "stats", broken)
    r = client.get("/health")
    assert r.status_code == 200 and r.get_json() == {"status": "ok"}


def test_ready_ok(client):
    r = client.get("/ready")
    body = r.get_json()
    assert r.status_code == 200 and body["status"] == "ready"
    assert body["checks"]["database"] == "ok" and body["checks"]["jobs"]["dead"] == 0


def test_ready_reports_job_counts_and_stale_warning(client, app):
    from datetime import datetime, timedelta
    with app.app_context():
        j = jobs.enqueue("x", run_at=datetime.utcnow() - timedelta(hours=1))
        jobs.enqueue("y", max_attempts=1)
        db.session.commit()
    body = client.get("/ready").get_json()
    assert body["checks"]["jobs"]["queued"] == 2 and body["checks"]["jobs_warning"] == "stale_jobs"
    assert j is not None


def test_ready_503_when_db_broken_and_no_exception_text(client, monkeypatch):
    def broken(*a, **k):
        raise RuntimeError("secret connection string postgres://u:pw@host/db")
    monkeypatch.setattr(ops, "text", broken)
    r = client.get("/ready")
    assert r.status_code == 503 and r.get_json() == {"status": "not_ready"}
    assert "secret" not in r.get_data(as_text=True) and "postgres" not in r.get_data(as_text=True)


def test_ready_503_when_jobs_check_fails(client, monkeypatch):
    def broken():
        raise ValueError("boom detail")
    monkeypatch.setattr(jobs, "stats", broken)
    r = client.get("/ready")
    assert r.status_code == 503 and "boom" not in r.get_data(as_text=True)


def test_ready_503_on_migration_mismatch(client, app, monkeypatch):
    monkeypatch.setattr(ops, "_alembic_head", lambda: "head_rev")
    with app.app_context():
        db.session.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        db.session.execute(text("INSERT INTO alembic_version VALUES ('old_rev')"))
        db.session.commit()
    try:
        r = client.get("/ready")
        assert r.status_code == 503 and r.get_json() == {"status": "not_ready"}
        with app.app_context():
            db.session.execute(text("UPDATE alembic_version SET version_num='head_rev'"))
            db.session.commit()
        assert client.get("/ready").status_code == 200
    finally:
        with app.app_context():
            db.session.execute(text("DROP TABLE alembic_version"))
            db.session.commit()


def test_alembic_head_matches_migrations_folder():
    assert ops._alembic_head()  # a real revision id is found in migrations/versions


def test_ops_endpoints_exempt_from_rate_limit(client):
    from extensions import limiter
    limiter.enabled = True
    try:
        assert all(client.get(p).status_code == 200 for p in ("/health", "/ready") for _ in range(70))  # default is 60/min
        assert client.get("/about").status_code in (200, 404)  # sanity: a normal route is still served
    finally:
        limiter.enabled = False


# ---------- request id and access log ----------
def test_request_id_generated_and_echoed(client):
    rid = client.get("/health").headers["X-Request-ID"]
    assert len(rid) == 32 and rid.isalnum()


@pytest.mark.parametrize("inbound", ["abc-123_XYZ", "a" * 64])
def test_sane_inbound_request_id_is_echoed(client, inbound):
    assert client.get("/health", headers={"X-Request-ID": inbound}).headers["X-Request-ID"] == inbound


@pytest.mark.parametrize("inbound", ["a" * 65, "has space", "semi;colon", "<script>", "café"])
def test_bad_inbound_request_id_is_replaced(client, inbound):
    got = client.get("/health", headers={"X-Request-ID": inbound}).headers["X-Request-ID"]
    assert got != inbound and len(got) == 32


def test_access_log_line_has_no_query_string_and_integer_user(patient_client, caplog):
    c, uid = patient_client
    with caplog.at_level(logging.INFO, logger="access"):
        c.get("/health?token=abc123&email=a@b.com", headers={"X-Request-ID": "rid-1"})
    lines = [r.getMessage() for r in caplog.records if r.name == "access"]
    assert len(lines) == 1
    line = lines[0]
    assert "method=GET" in line and "path=/health " in line and "status=200" in line and "duration_ms=" in line
    assert f"user_id={uid}" in line and "request_id=rid-1" in line
    assert "abc123" not in line and "a@b.com" not in line and "?" not in line


def test_access_log_anonymous_user(client, caplog):
    with caplog.at_level(logging.INFO, logger="access"):
        client.get("/health")
    assert "user_id=-" in [r.getMessage() for r in caplog.records if r.name == "access"][0]


def test_request_body_is_never_logged(patient_client, caplog):
    c, uid = patient_client
    with caplog.at_level(logging.DEBUG):
        c.post("/api/mood", json={"value": 5, "note": "my secret diary sentence"})
    assert not any("secret diary" in r.getMessage() for r in caplog.records)


# ---------- redaction ----------
def test_redact_masks_emails_tokens_passwords_and_long_text():
    out = redact("user a.b+c@example.co.in password=hunter2 Authorization: Bearer abcDEF123456xyz api_key=XYZ123 token: t0k3n")
    assert "example.co.in" not in out and "hunter2" not in out and "abcDEF123456xyz" not in out
    assert "XYZ123" not in out and "t0k3n" not in out
    long = "diary " + "word " * 40
    assert "word word" not in redact(f'saved entry "{long}" ok') and "[text omitted]" in redact(f'x "{long}" y')
    assert redact("job dead id=5 kind=send_email") == "job dead id=5 kind=send_email"


def test_all_log_records_are_redacted_via_record_factory(caplog):
    with caplog.at_level(logging.INFO):
        logging.getLogger("anything").info("login failed for %s with password=%s", "x@y.com", "pw123")
    msg = caplog.records[-1].getMessage()
    assert "x@y.com" not in msg and "pw123" not in msg


def test_redaction_filter_class():
    rec = logging.LogRecord("n", logging.INFO, "f", 1, "mail %s", ("q@r.com",), None)
    assert RedactionFilter().filter(rec) and "q@r.com" not in rec.getMessage()
