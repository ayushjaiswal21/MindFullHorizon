"""Circuit breaker, bounded retries, per-user budgets and graceful degradation. No network, no Gemini: fakes only."""
import asyncio
import json

import pytest

import ai.gemini_impl as g
import ai.service as svc
from ai.interface import AIProvider
from utils import llm_guard
from utils.circuit_breaker import CLOSED, HALF_OPEN, OPEN, CircuitBreaker

SECRET = "sk-LEAK-me-not-12345 patient said i want to die"


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


class CodedError(Exception):
    def __init__(self, code):
        super().__init__(f"http {code} {SECRET}")
        self.code = code


class FakeProvider(AIProvider):
    """Scripted outcomes: an exception instance/class is raised, anything else is returned."""

    def __init__(self, *script):
        self.script, self.calls = list(script), 0

    def ask(self, prompt, **kw):
        self.calls += 1
        step = self.script.pop(0) if len(self.script) > 1 else self.script[0]
        if isinstance(step, BaseException) or (isinstance(step, type) and issubclass(step, BaseException)):
            raise step
        return step


@pytest.fixture
def provider(monkeypatch):
    def install(*script, breaker=None):
        p = FakeProvider(*script)
        monkeypatch.setattr(g, "PROVIDER", p)
        monkeypatch.setattr(g, "BREAKER", breaker or CircuitBreaker(5, 60, Clock()))
        monkeypatch.setattr(g, "_sleep", lambda s: sleeps.append(s))
        monkeypatch.setattr(g, "_uniform", lambda a, b: b)
        return p
    sleeps = []
    install.sleeps = sleeps
    return install


def ask():
    return g.ask_gemini_system_user("sys", "user")


def run(text, user_id=None):
    return asyncio.run(svc.ask_with_severity(text, user_id=user_id))


GOOD = json.dumps({"reply": "I hear you.", "severity": 0, "reason": "ok", "recommended_action": "none"})


# ---------------------------------------------------------------- breaker state machine
def test_breaker_closed_open_half_open_closed():
    clk = Clock()
    b = CircuitBreaker(failures=3, reset_seconds=60, clock=clk)
    assert b.state == CLOSED and b.allow()
    b.record_failure(); b.record_failure()
    assert b.state == CLOSED
    b.record_failure()
    assert b.state == OPEN and not b.allow()
    clk.t += 59
    assert b.state == OPEN and not b.allow()
    clk.t += 1
    assert b.state == HALF_OPEN
    assert b.allow() is True and b.allow() is False  # only one trial call
    b.record_success()
    assert b.state == CLOSED and b.allow()


def test_breaker_failed_trial_reopens_with_fresh_cooldown():
    clk = Clock()
    b = CircuitBreaker(failures=1, reset_seconds=10, clock=clk)
    b.record_failure()
    clk.t += 10
    assert b.allow()
    b.record_failure()
    assert b.state == OPEN
    clk.t += 9
    assert b.state == OPEN
    clk.t += 1
    assert b.state == HALF_OPEN


def test_breaker_success_resets_consecutive_failures():
    b = CircuitBreaker(failures=3, reset_seconds=60, clock=Clock())
    for _ in range(2):
        b.record_failure()
    b.record_success()
    for _ in range(2):
        b.record_failure()
    assert b.state == CLOSED


def test_breaker_env_defaults_and_bad_values(monkeypatch):
    monkeypatch.delenv("AI_BREAKER_FAILURES", raising=False)
    monkeypatch.delenv("AI_BREAKER_RESET_SECONDS", raising=False)
    b = CircuitBreaker.from_env()
    assert (b.failures, b.reset_seconds) == (2, 60.0)
    monkeypatch.setenv("AI_BREAKER_FAILURES", "2")
    monkeypatch.setenv("AI_BREAKER_RESET_SECONDS", "7")
    b = CircuitBreaker.from_env()
    assert (b.failures, b.reset_seconds) == (2, 7.0)
    monkeypatch.setenv("AI_BREAKER_FAILURES", "junk")
    monkeypatch.setenv("AI_BREAKER_RESET_SECONDS", "-3")
    b = CircuitBreaker.from_env()
    assert (b.failures, b.reset_seconds) == (2, 60.0)


def test_breaker_is_thread_safe_enough():
    import threading
    b = CircuitBreaker(failures=1000, reset_seconds=60, clock=Clock())
    ts = [threading.Thread(target=lambda: [b.record_failure() for _ in range(100)]) for _ in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert b._fails == 800 and b.state == CLOSED


# ---------------------------------------------------------------- retries
def test_retries_transient_errors_with_backoff_then_succeeds(provider):
    p = provider(TimeoutError("t"), CodedError(503), "fine")
    assert ask() == "fine"
    assert p.calls == 3 and len(provider.sleeps) == 2
    assert provider.sleeps[0] <= 0.5 and provider.sleeps[1] <= 1.0  # jittered, bounded


@pytest.mark.parametrize("exc", [TimeoutError("t"), CodedError(429), CodedError(500), CodedError(408), ConnectionError("c")])
def test_transient_errors_retry_at_most_twice(provider, exc):
    p = provider(exc)
    with pytest.raises(type(exc)):
        ask()
    assert p.calls == 3 and len(provider.sleeps) == 2  # 1 try + max 2 retries


@pytest.mark.parametrize("exc", [ValueError("bad"), CodedError(400), CodedError(403), CodedError(404), RuntimeError("x")])
def test_non_transient_errors_are_not_retried(provider, exc):
    p = provider(exc)
    with pytest.raises(type(exc)):
        ask()
    assert p.calls == 1 and not provider.sleeps


def test_safety_block_is_never_retried_and_is_not_an_outage(provider):
    br = CircuitBreaker(1, 60, Clock())
    p = provider(g.GeminiBlocked("blocked"), breaker=br)
    for _ in range(3):
        with pytest.raises(g.GeminiBlocked):
            ask()
    assert p.calls == 3 and not provider.sleeps and br.state == CLOSED


def test_is_transient_classification():
    assert g.is_transient(TimeoutError()) and g.is_transient(CodedError(503)) and g.is_transient(CodedError(429))
    assert not g.is_transient(CodedError(400)) and not g.is_transient(g.GeminiBlocked()) and not g.is_transient(ValueError())

    class ServiceUnavailable(Exception):
        pass
    assert g.is_transient(ServiceUnavailable())


def test_client_errors_do_not_open_the_circuit(provider):
    br = CircuitBreaker(2, 60, Clock())
    provider(CodedError(400), breaker=br)
    for _ in range(5):
        with pytest.raises(CodedError):
            ask()
    assert br.state == CLOSED


def test_one_failed_request_is_one_breaker_failure(provider):
    br = CircuitBreaker(2, 60, Clock())
    p = provider(TimeoutError("t"), breaker=br)
    with pytest.raises(TimeoutError):
        ask()
    assert p.calls == 3 and br.state == CLOSED  # 3 attempts, 1 failure (threshold 2)
    with pytest.raises(TimeoutError):
        ask()
    assert br.state == OPEN


def test_open_breaker_fails_fast_then_recovers(provider):
    clk = Clock()
    br = CircuitBreaker(1, 30, clk)
    p = provider(RuntimeError("x"), "back", breaker=br)
    with pytest.raises(RuntimeError):
        ask()
    calls = p.calls
    with pytest.raises(g.AIUnavailable):
        ask()
    assert p.calls == calls  # no call made while open
    clk.t += 30
    assert ask() == "back" and br.state == CLOSED


def test_missing_key_does_not_touch_breaker(monkeypatch):
    br = CircuitBreaker(1, 60, Clock())
    monkeypatch.setattr(g, "BREAKER", br)
    monkeypatch.setattr(g, "GEMINI_API_KEY", "")
    monkeypatch.setattr(g, "PROVIDER", g.GeminiProvider())
    for _ in range(3):
        with pytest.raises(RuntimeError):
            ask()
    assert br.state == CLOSED


def test_gemini_provider_is_behind_the_seam():
    assert isinstance(g.PROVIDER, AIProvider)
    old = g.set_provider(FakeProvider("x"))
    try:
        g.BREAKER.reset()
        assert ask() == "x"
    finally:
        g.set_provider(old)


def test_default_model_is_configurable_constant():
    assert g.GEMINI_MODEL_NAME and isinstance(g.GEMINI_MODEL_NAME, str)
    assert svc.check_api_status()["model"] == g.GEMINI_MODEL_NAME


# ---------------------------------------------------------------- budgets
def test_burst_limit_per_user_and_window_slides():
    clk = Clock(86400 * 10 + 5)
    b = llm_guard.UserBudget(daily=100, burst=3, window=60, clock=clk)
    assert [b.consume(1)[0] for _ in range(3)] == [True] * 3
    ok, reason, retry = b.consume(1)
    assert not ok and reason == "burst" and 1 <= retry <= 60
    assert b.consume(2)[0]  # another user is unaffected
    clk.t += 61
    assert b.consume(1)[0]


def test_daily_limit_resets_next_day_and_rejections_are_not_counted():
    clk = Clock(86400 * 10 + 100)
    b = llm_guard.UserBudget(daily=4, burst=100, window=60, clock=clk)
    assert all(b.consume(1)[0] for _ in range(4))
    for _ in range(10):
        ok, reason, retry = b.consume(1)
        assert not ok and reason == "daily" and retry > 0
    assert b.consume(2)[0]
    clk.t += 86400
    assert b.consume(1)[0]


def test_budget_memory_is_bounded():
    b = llm_guard.UserBudget(daily=5, burst=5, max_users=50, clock=Clock())
    for uid in range(5000):
        b.consume(uid)
    assert len(b._users) <= 50


def test_budget_defaults_from_env(monkeypatch):
    monkeypatch.delenv("AI_DAILY_LIMIT", raising=False)
    monkeypatch.delenv("AI_BURST_LIMIT", raising=False)
    b = llm_guard.UserBudget()
    assert (b.daily, b.burst) == (200, 8)
    monkeypatch.setenv("AI_DAILY_LIMIT", "3")
    monkeypatch.setenv("AI_BURST_LIMIT", "2")
    b = llm_guard.UserBudget()
    assert (b.daily, b.burst) == (3, 2)


@pytest.fixture
def small_budget(monkeypatch):
    b = llm_guard.UserBudget(daily=2, burst=2, clock=Clock(86400 * 20))
    monkeypatch.setattr(llm_guard, "BUDGET", b)
    return b


def test_chat_budget_is_per_session_user_and_skips_the_model_when_spent(monkeypatch, small_budget):
    calls = []
    monkeypatch.setattr(svc, "ask_gemini_system_user", lambda *a, **k: calls.append(1) or GOOD)
    assert not run("hello", 1)["rate_limited"] and not run("hello again", 1)["rate_limited"]
    out = run("third message", 1)
    assert out["rate_limited"] is True and out["retry_after"] > 0 and out["notice"] == svc.LIMIT_NOTICE
    assert out["helplines"] and len(calls) == 2  # no model call, helplines mentioned
    assert not run("hello", 2)["rate_limited"] and len(calls) == 3  # user 2 has own budget


def test_crisis_floor_answers_with_budget_exhausted(monkeypatch, small_budget):
    calls = []
    monkeypatch.setattr(svc, "ask_gemini_system_user", lambda *a, **k: calls.append(1) or GOOD)
    for _ in range(2):
        run("hello", 1)
    for text in ("i want to kill myself", "mujhe marna hai", "मैं मरना चाहता हूँ", "my friend wants to die", "this exam is killing me"):
        out = run(text, 1)
        assert out["rate_limited"] is False and out["reply"] and out["helplines"], text
        assert out["ai_unavailable"] is True
    out = run("i want to kill myself", 1)
    assert out["escalate"] and out["recommended_action"] == "emergency_hotline" and out["severity"] >= 9
    assert "14416" in out["reply"] and len(calls) == 2  # templates only, no model cost


def test_crisis_floor_answers_with_breaker_open_and_no_exception_text(monkeypatch, provider):
    br = CircuitBreaker(1, 60, Clock())
    provider(RuntimeError(SECRET), breaker=br)
    out = run("hello there", 1)
    assert out["ai_unavailable"] is True and out["notice"] == svc.UNAVAILABLE_NOTICE and br.state == OPEN
    assert "sk-LEAK" not in json.dumps(out) and out["reply"] == svc.DEFAULT_REPLY
    out = run("i want to die", 1)  # breaker is open now
    assert out["escalate"] and out["recommended_action"] == "emergency_hotline" and out["helplines"]
    assert "sk-LEAK" not in json.dumps(out)  # the floor answered without calling the model, so no outage flag


def test_outage_degrades_to_rule_based_replies_with_same_shape(provider):
    provider(RuntimeError(SECRET))
    keys = set(run("hello", 1))
    for text, needle in (("this exam is killing me", "thoughts of ending"), ("my friend wants to die", "friend"), ("hello", "hear you")):
        out = run(text, 2)
        assert set(out) == keys and needle in out["reply"] and out["ai_unavailable"]
    g.set_provider(FakeProvider(GOOD))  # provider fixture restores the original afterwards
    g.BREAKER.reset()
    out = run("hello", 3)
    assert out["ai_unavailable"] is False and out["notice"] is None and set(out) == keys


def test_generators_degrade_without_exception_text(provider):
    provider(RuntimeError(SECRET))
    assert "LEAK" not in svc.generate_journal_insights("t", "c", "sad")
    assert "LEAK" not in svc.analyze_voice_emotion("hi", {})
    assert "LEAK" not in svc.generate_clinical_note("hi")
    assert svc.generate_goal_suggestions({}) == []
    assert "LEAK" not in json.dumps(svc.generate_progress_recommendations({}))
    assert "LEAK" not in svc.generate_chat_response("hello")


# ---------------------------------------------------------------- routes
def test_chat_route_429_has_helplines_and_crisis_still_200(patient_client, monkeypatch, small_budget):
    c, uid = patient_client
    monkeypatch.setattr(svc, "ask_gemini_system_user", lambda *a, **k: GOOD)
    assert c.post("/api/chat", json={"message": "hello"}).status_code == 200
    assert c.post("/api/chat", json={"message": "hello again"}).status_code == 200
    r = c.post("/api/chat", json={"message": "one more", "user_id": 999})
    body = r.get_json()
    assert r.status_code == 429 and body["rate_limited"] is True and body["retry_after"] > 0
    assert any(h["number"] == "14416" for h in body["helplines"]) and "still answered" in body["error"]
    r = c.post("/api/chat", json={"message": "i want to kill myself"})
    body = r.get_json()
    assert r.status_code == 200 and body["escalate"] is True and body["recommended_action"] == "emergency_hotline"
    assert body["helplines"] and "14416" in body["reply"]


def test_chat_route_outage_adds_notice_and_hides_error_text(patient_client, provider):
    c, _ = patient_client
    provider(RuntimeError(SECRET))
    r = c.post("/api/chat", json={"message": "hello"})
    text = r.get_data(as_text=True)
    assert r.status_code == 200 and r.get_json()["ai_unavailable"] is True and r.get_json()["notice"]
    assert "sk-LEAK" not in text and "Traceback" not in text
    for key in ("reply", "severity", "reason", "recommended_action", "escalate", "helplines"):
        assert key in r.get_json()


def test_ask_route_budget_and_floor(patient_client, monkeypatch, small_budget):
    c, _ = patient_client
    monkeypatch.setattr("ai.service.ask", lambda p, **kw: "ok")
    assert c.post("/api/ask", json={"prompt": "hi"}).get_json()["response"] == "ok"
    assert c.post("/api/ask", json={"prompt": "hi"}).status_code == 200
    r = c.post("/api/ask", json={"prompt": "hi"})
    assert r.status_code == 429 and r.get_json()["helplines"]
    r = c.post("/api/ask", json={"prompt": "i want to die"})
    assert r.status_code == 200 and "14416" in r.get_json()["response"]
