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
# Set explicitly (not popped): load_dotenv() never overrides an existing variable, so whatever a developer's real
# .env happens to have set (a real key, CHAT_ROUTER_ENABLED=1 for local testing, etc.) can never leak into a test
# run's behaviour. Tests that want a flag on use monkeypatch.setenv, which overrides this baseline per test.
os.environ["GEMINI_API_KEY"] = ""
os.environ["GOOGLE_OAUTH_CLIENT_ID"] = ""
os.environ["GOOGLE_OAUTH_CLIENT_SECRET"] = ""
os.environ["CHAT_ROUTER_ENABLED"] = "0"
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

    def _make(role="patient", email=None, institution="Test University", name=None, **extra):
        """`extra` goes to the User row, for example provider_type='doctor' or is_pharmacy_desk=True."""
        counter["n"] += 1
        email = email or f"{role}{counter['n']}@test.local"
        with app.app_context():
            user = User(email=email, name=name or f"{role.title()} {counter['n']}", role=role, institution=institution, **extra)
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


@pytest.fixture(autouse=True)
def reset_llm_state():
    """Fresh AI budgets and a closed circuit breaker for every test.

    Also clears routes.patient_progress.FAILED: a process-global 10-minute negative cache keyed by user id.
    SQLite reuses row ids after clean_db empties the tables, so a later test's patient can reuse an id another
    test's FAILED entry was keyed on, silently skipping the model call it meant to exercise."""
    from ai import gemini_impl
    from routes.patient_progress import FAILED as progress_failed_cache
    from utils import llm_guard
    llm_guard.reset_state()
    gemini_impl.BREAKER.reset()
    progress_failed_cache.clear()
    yield


# ---- clinical fixtures (docs/CLINICAL_DESIGN.md 12) ----

@pytest.fixture
def make_doctor(app, make_user):
    """make_doctor(status='verified', institution='Test University') -> user id of a doctor with a PrescriberProfile."""
    from datetime import timedelta
    from models import PrescriberProfile
    from utils.timeutil import utcnow
    counter = {"n": 0}

    def _make(status="verified", institution="Test University", **extra):
        counter["n"] += 1
        uid = make_user("provider", institution=institution, provider_type="doctor", **extra)
        with app.app_context():
            now = utcnow()
            db.session.add(PrescriberProfile(
                user_id=uid, registration_number=f"REG{1000 + counter['n']}", council="State Medical Council",
                council_key="state medical council", registered_since=2011, status=status, submitted_at=now,
                status_changed_at=now, verified_at=now if status == "verified" else None,
                review_due_at=now + timedelta(days=365) if status == "verified" else None))
            db.session.commit()
        return uid

    return _make


@pytest.fixture
def doctor_client(app, make_doctor):
    """(client, user_id): a verified doctor, logged in."""
    c = app.test_client()
    uid = make_doctor()
    _login_as(c, app, uid)
    return c, uid


@pytest.fixture
def admin_client(app, make_user):
    """(client, user_id): an administrator without the pharmacy desk flag."""
    c = app.test_client()
    uid = make_user("admin", institution="Test University")
    _login_as(c, app, uid)
    return c, uid


@pytest.fixture
def desk_client(app, make_user):
    """(client, user_id): an administrator with is_pharmacy_desk."""
    c = app.test_client()
    uid = make_user("admin", institution="Test University", is_pharmacy_desk=True)
    _login_as(c, app, uid)
    return c, uid


@pytest.fixture(autouse=True)
def personal_text_on_by_default(monkeypatch):
    """Existing tests exercise the model path (fakes only), so they run with AI_SEND_PERSONAL_TEXT on. The real default
    is OFF: tests/test_ai_policy.py unsets it and checks the safe mode, the copy and the tip."""
    monkeypatch.setenv("AI_SEND_PERSONAL_TEXT", "1")
    from utils import daily_tip
    daily_tip.reset()
    yield
