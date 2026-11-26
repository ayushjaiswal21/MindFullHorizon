"""Per-user AI budgets and graceful degradation under an open breaker/outage, plus the routes that sit
on top. No network, no Gemini: fakes only. Split out of test_llm_resilience.py (300-line rule);
circuit-breaker/retry tests are in test_llm_resilience_breaker.py."""
import asyncio
import json

import ai.gemini_impl as g
import ai.service as svc
import pytest
from ai.interface import AIProvider
from utils import llm_guard
from utils.circuit_breaker import OPEN, CircuitBreaker

SECRET = "sk-LEAK-me-not-12345 patient said i want to die"
GOOD = json.dumps({"reply": "I hear you.", "severity": 0, "reason": "ok", "recommended_action": "none"})


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


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


def run(text, user_id=None):
    return asyncio.run(svc.ask_with_severity(text, user_id=user_id))


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
