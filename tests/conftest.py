"""Shared pytest fixtures. Run from the project root: `pytest tests -q`.

The app is configured at import time from env vars, so they are set before `import app`.
Each test starts with empty tables; AI calls fall back (no GEMINI_API_KEY).
"""
import os
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_tmpdir = tempfile.mkdtemp(prefix="mfh_test_")
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(_tmpdir, "test.db").replace("\\", "/")
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["FLASK_ENV"] = "testing"
# Set to "" (not popped): load_dotenv() never overrides an existing variable, so a real key in .env cannot leak into tests.
os.environ["GEMINI_API_KEY"] = ""
os.environ["GOOGLE_OAUTH_CLIENT_ID"] = ""
os.environ["GOOGLE_OAUTH_CLIENT_SECRET"] = ""
os.chdir(ROOT)

import app as app_module  # noqa: E402  (must come after the env setup above)
from extensions import db  # noqa: E402
from models import User  # noqa: E402

PASSWORD = "Str0ng!Passw0rd"


@pytest.fixture(scope="session")
def app():
    flask_app = app_module.app
    flask_app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, SESSION_COOKIE_SECURE=False)
    app_module.limiter.enabled = False
    return flask_app


@pytest.fixture(autouse=True)
def clean_db(app):
    """Empty every table before each test (keeps the schema)."""
    with app.app_context():
        db.session.remove()
        for table in reversed(db.metadata.sorted_tables):
            db.session.execute(table.delete())
        db.session.commit()
    yield
    with app.app_context():
        db.session.remove()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def make_user(app):
    """make_user(role='patient', email=None, institution='Test University') -> user id."""
    counter = {"n": 0}

    def _make(role="patient", email=None, institution="Test University", name=None):
        counter["n"] += 1
        email = email or f"{role}{counter['n']}@test.local"
        with app.app_context():
            user = User(email=email, name=name or f"{role.title()} {counter['n']}", role=role, institution=institution)
            user.set_password(PASSWORD)
            db.session.add(user)
            db.session.commit()
            return user.id

    return _make


def _login_as(client, app, user_id):
    with app.app_context():
        user = db.session.get(User, user_id)
        data = dict(email=user.email, role=user.role, name=user.name, institution=user.institution)
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["user_email"] = data["email"]
        sess["user_role"] = data["role"]
        sess["user_name"] = data["name"]
        sess["user_institution"] = data["institution"]


@pytest.fixture
def login(client, app):
    """login(user_id) puts that user into the test client's session (skips the form)."""
    return lambda user_id: _login_as(client, app, user_id)


@pytest.fixture
def patient_client(app, make_user):
    """A (client, user_id) pair already logged in as a patient."""
    c = app.test_client()
    uid = make_user("patient")
    _login_as(c, app, uid)
    return c, uid


@pytest.fixture
def provider_client(app, make_user):
    c = app.test_client()
    uid = make_user("provider")
    _login_as(c, app, uid)
    return c, uid
