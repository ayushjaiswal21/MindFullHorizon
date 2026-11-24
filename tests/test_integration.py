"""Cross-area checks: signup consent, empty-data provider pages, secrets and Docker hygiene."""
import os
import re

from models import User

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASSWORD = "Str0ng!Passw0rd"


def _signup(client, **extra):
    data = dict(name="New", email="new@test.local", password=PASSWORD, confirm_password=PASSWORD,
                role="patient", institution="Test University", age_confirm="yes")
    data.update(extra)
    return client.post("/signup", data=data)


def test_signup_requires_server_side_consent(client, app):
    r = _signup(client)  # no consent field at all
    assert r.status_code == 200  # form re-rendered, not redirected
    with app.app_context():
        assert User.query.filter_by(email="new@test.local").first() is None


def test_signup_with_consent_creates_patient(client, app):
    r = _signup(client, consent="yes")
    assert r.status_code in (200, 302)
    with app.app_context():
        user = User.query.filter_by(email="new@test.local").first()
        assert user is not None and user.role == "patient"


def test_provider_pages_render_with_no_data(provider_client):
    c, _ = provider_client
    for url in ("/provider/dashboard", "/provider/analytics"):
        r = c.get(url)
        assert r.status_code == 200, url
        assert b"Traceback" not in r.data


def test_dashboard_shows_na_not_none(provider_client):
    c, _ = provider_client
    body = c.get("/provider/dashboard").get_data(as_text=True)
    assert "Nonemin" not in body and "None%" not in body and "None/5" not in body


def test_no_demo_persona_or_us_helplines_left_in_code():
    bad = re.compile(r"Dr\. Anya|\b988\b|\b741741\b")
    hits = []
    for folder in ("ai", "routes", "templates", "utils"):
        for root, _, files in os.walk(os.path.join(ROOT, folder)):
            for f in files:
                if f.endswith((".py", ".html", ".js")):
                    text = open(os.path.join(root, f), encoding="utf-8", errors="ignore").read()
                    if bad.search(text):
                        hits.append(os.path.join(root, f))
    assert not hits, hits


def test_env_and_database_files_are_gitignored():
    ignore = open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read().splitlines()
    for pattern in (".env", "*.db", "instance/", "static/uploads/*"):
        assert pattern in ignore, pattern


def test_dockerfile_migrates_before_starting():
    text = open(os.path.join(ROOT, "Dockerfile"), encoding="utf-8").read()
    assert "flask db upgrade" in text and "FLASK_APP=app.py" in text
