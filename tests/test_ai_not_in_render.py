"""No patient or provider page waits on the model: with every AI entry point sleeping or raising, pages still answer fast
and do not call the AI at all while rendering. The progress suggestions endpoint is the one place that may call it, and it is capped."""
import time

import pytest

import ai.service as ai_service
from ai import gemini_impl
from extensions import db
from models import Assessment, ProviderPatient
from routes import patient_progress
from utils.timeutil import utcnow

LIMIT = 1.5
SLOW = 3.0

PATIENT_PAGES = ["/patient/dashboard", "/patient/assessment", "/patient/progress", "/patient/goals", "/patient/journal",
                 "/patient/digital-detox", "/patient/voice-logs", "/patient/breathing", "/patient/yoga", "/patient/yoga/videos",
                 "/patient/medication", "/patient/schedule", "/music", "/profile", "/chat"]
PROVIDER_PAGES = ["/provider/dashboard", "/provider/analytics", "/provider/wellness-report/{pid}", "/provider/ai-documentation"]


@pytest.fixture
def ai_calls(monkeypatch):
    """Make every model entry point slow (or failing) and count the calls. The key counts as configured."""
    calls = []

    def make(name, behaviour):
        def fake(*a, **k):
            calls.append(name)
            if behaviour == "raise":
                raise RuntimeError("model down")
            time.sleep(SLOW)
            return ""
        return fake

    def arm(behaviour):
        for name in dir(ai_service):
            if name.startswith(("generate_", "analyze_", "ask", "_simple_chat")) and callable(getattr(ai_service, name)):
                monkeypatch.setattr(ai_service, name, make(name, behaviour))
        monkeypatch.setattr(gemini_impl, "ask_gemini_system_user", make("gemini", behaviour))
        monkeypatch.setattr(gemini_impl.GeminiProvider, "configured", lambda self: True)
        return calls

    return arm


def _seed(app, uid):
    with app.app_context():
        db.session.add(Assessment(user_id=uid, assessment_type="PHQ-9", score=8, responses=[1] * 9, created_at=utcnow()))
        db.session.commit()


def _timed(client, url):
    t0 = time.perf_counter()
    r = client.get(url)
    return r, time.perf_counter() - t0


@pytest.mark.parametrize("behaviour", ["sleep", "raise"])
def test_patient_pages_answer_fast_without_calling_ai(app, patient_client, ai_calls, behaviour):
    c, uid = patient_client
    _seed(app, uid)
    calls = ai_calls(behaviour)
    for url in PATIENT_PAGES:
        r, took = _timed(c, url)
        assert r.status_code == 200, url
        assert took < LIMIT, f"{url} took {took:.2f}s"
    assert calls == [], f"AI called while rendering: {calls}"


@pytest.mark.parametrize("behaviour", ["sleep", "raise"])
def test_provider_pages_answer_fast_without_calling_ai(app, provider_client, make_user, ai_calls, behaviour):
    c, prov = provider_client
    pat = make_user("patient")
    with app.app_context():
        db.session.add(ProviderPatient(provider_id=prov, patient_id=pat, source="manual"))
        db.session.commit()
    _seed(app, pat)
    calls = ai_calls(behaviour)
    for url in PROVIDER_PAGES:
        r, took = _timed(c, url.format(pid=pat))
        assert r.status_code == 200, url
        assert took < LIMIT, f"{url} took {took:.2f}s"
    assert calls == [], f"AI called while rendering: {calls}"


def test_progress_suggestions_are_capped_and_failure_is_remembered(app, patient_client, ai_calls, monkeypatch):
    c, uid = patient_client
    _seed(app, uid)
    patient_progress.FAILED.clear()
    monkeypatch.setattr(patient_progress, "AI_CAP_SECONDS", 0.5)
    calls = ai_calls("sleep")
    t0 = time.perf_counter()
    body = c.get("/patient/api/progress/suggestions").get_json()
    assert time.perf_counter() - t0 < LIMIT
    assert body["status"] == "unavailable" and body["message"]
    assert calls == ["generate_progress_recommendations"]
    t0 = time.perf_counter()
    again = c.get("/patient/api/progress/suggestions").get_json()  # remembered failure: no second model call
    assert time.perf_counter() - t0 < 0.5 and again["status"] == "unavailable"
    assert calls == ["generate_progress_recommendations"]


def test_progress_suggestions_success_is_stored_and_reused(app, patient_client, monkeypatch):
    c, uid = patient_client
    _seed(app, uid)
    patient_progress.FAILED.clear()
    monkeypatch.setattr(gemini_impl.GeminiProvider, "configured", lambda self: True)
    seen = []
    rec = {"insights": [{"title": "I", "desc": "d"}], "actions": [{"title": "A", "desc": "d"}]}
    monkeypatch.setattr(ai_service, "generate_progress_recommendations", lambda data: seen.append(data) or rec)
    first = c.get("/patient/api/progress/suggestions").get_json()
    second = c.get("/patient/api/progress/suggestions").get_json()
    assert first["status"] == second["status"] == "ok" and first["actions"] == rec["actions"]
    assert len(seen) == 1  # the second answer came from the stored recommendation


def test_progress_suggestions_empty_account_and_auth(app, patient_client, client, make_user, login):
    c, _ = patient_client
    assert c.get("/patient/api/progress/suggestions").get_json()["status"] == "empty"
    assert client.get("/patient/api/progress/suggestions").status_code in (302, 401)
    login(make_user("provider"))
    assert client.get("/patient/api/progress/suggestions").status_code in (302, 401, 403)


def test_negative_cache_is_bounded_and_expires(monkeypatch):
    from utils import ai_cap
    nc = ai_cap.NegativeCache(ttl=600, limit=3)
    for k in range(5):
        nc.add(k)
    assert not nc.blocked(0) and nc.blocked(4) and len(nc._items) == 3
    t = [ai_cap.time.monotonic()]
    monkeypatch.setattr(ai_cap.time, "monotonic", lambda: t[0] + 601)
    assert not nc.blocked(4)


def test_stock_fallback_text_is_not_stored_or_shown_as_a_suggestion(app, patient_client, monkeypatch):
    from models import ProgressRecommendation
    c, uid = patient_client
    _seed(app, uid)
    patient_progress.FAILED.clear()
    monkeypatch.setattr(gemini_impl.GeminiProvider, "configured", lambda self: True)
    stock = {"insights": [{"title": "Keep Going", "desc": "x"}], "actions": [{"title": "Daily Check-ins", "desc": "y"}]}
    monkeypatch.setattr(ai_service, "generate_progress_recommendations", lambda data: stock)
    assert c.get("/patient/api/progress/suggestions").get_json()["status"] == "unavailable"
    with app.app_context():
        assert ProgressRecommendation.query.count() == 0
