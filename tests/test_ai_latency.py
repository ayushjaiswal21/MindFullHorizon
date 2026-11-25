"""Latency guarantees for interactive AI calls (chat, ask): instant without a key, hard timeout, short retry,
fast breaker, and the crisis floor never waiting on the model. Fakes only, no network."""
import asyncio
import threading
import time

import pytest

import ai.gemini_impl as g
import ai.service as svc
from ai.interface import AIProvider
from utils.circuit_breaker import CLOSED, OPEN, CircuitBreaker


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


class Coded(Exception):
    def __init__(self, code):
        super().__init__(str(code))
        self.code = code


class Slow(AIProvider):
    """Sleeps longer than any deadline and ignores the timeout it is given (like a stuck SDK call)."""

    def __init__(self, seconds=2.0):
        self.seconds, self.calls, self.timeouts = seconds, 0, []

    def ask(self, prompt, **kw):
        self.calls += 1
        self.timeouts.append(kw.get("timeout"))
        time.sleep(self.seconds)
        return "late"


class Scripted(AIProvider):
    def __init__(self, *script):
        self.script, self.calls = list(script), 0

    def ask(self, prompt, **kw):
        self.calls += 1
        step = self.script.pop(0) if len(self.script) > 1 else self.script[0]
        if isinstance(step, BaseException):
            raise step
        return step


@pytest.fixture
def fast(monkeypatch):
    """Short interactive deadline, recorded sleeps, a fresh breaker with the production default (2 failures)."""
    sleeps = []
    monkeypatch.setattr(g, "INTERACTIVE_TIMEOUT", 0.2)
    monkeypatch.setattr(g, "_sleep", lambda s: sleeps.append(s))
    monkeypatch.setattr(g, "_uniform", lambda a, b: b)
    monkeypatch.setattr(g, "BREAKER", CircuitBreaker(clock=Clock()))
    return sleeps


def chat(text):
    return asyncio.run(svc.ask_with_severity(text, user_id=1))


def test_default_breaker_opens_after_two_failures_for_sixty_seconds(monkeypatch):
    monkeypatch.delenv("AI_BREAKER_FAILURES", raising=False)
    monkeypatch.delenv("AI_BREAKER_RESET_SECONDS", raising=False)
    b = CircuitBreaker.from_env()
    assert (b.failures, b.reset_seconds) == (2, 60.0)


def test_no_key_is_an_instant_fallback_with_no_sleep_or_retry(monkeypatch):
    sleeps = []
    monkeypatch.setattr(g, "GEMINI_API_KEY", "")
    monkeypatch.setattr(g, "PROVIDER", g.GeminiProvider())
    monkeypatch.setattr(g, "_sleep", lambda s: sleeps.append(s))
    monkeypatch.setattr(g, "BREAKER", CircuitBreaker(clock=Clock()))
    t0 = time.perf_counter()
    out = chat("I feel a bit low today")
    dt = time.perf_counter() - t0
    assert dt < 0.2, dt
    assert out["ai_unavailable"] is True and out["notice"] and out["reply"] and not sleeps
    assert g.BREAKER.state == CLOSED  # a missing key is configuration, not an outage
    t0 = time.perf_counter()
    res = svc.ask_guarded("hello there", user_id=2)
    assert time.perf_counter() - t0 < 0.2 and res["ai_unavailable"] is True and not sleeps


def test_provider_that_hangs_is_cut_off_by_the_interactive_timeout(monkeypatch, fast):
    p = Slow(2.0)
    monkeypatch.setattr(g, "PROVIDER", p)
    t0 = time.perf_counter()
    with pytest.raises(TimeoutError):
        g.ask_gemini_system_user("sys", "user", interactive=True, personal=False)
    assert time.perf_counter() - t0 < 1.0
    assert p.calls == 1 and not fast  # the deadline is used up, so there is no second try and no jitter sleep


def test_interactive_timeout_is_capped_at_ten_seconds_whatever_the_caller_asks(monkeypatch):
    p = Scripted("ok")
    seen = []
    p.ask = lambda prompt, **kw: seen.append(kw["timeout"]) or "ok"
    monkeypatch.setattr(g, "PROVIDER", p)
    monkeypatch.setattr(g, "BREAKER", CircuitBreaker(clock=Clock()))
    assert g.INTERACTIVE_TIMEOUT <= 10
    g.ask_gemini_system_user("s", "u", timeout=60, interactive=True, personal=False)
    assert seen and 0 < seen[0] <= 10


def test_interactive_retries_once_only_for_transient_errors(monkeypatch, fast):
    monkeypatch.setattr(g, "INTERACTIVE_TIMEOUT", 5.0)
    p = Scripted(Coded(503), "fine")
    monkeypatch.setattr(g, "PROVIDER", p)
    assert g.ask_gemini_system_user("s", "u", interactive=True, personal=False) == "fine"
    assert p.calls == 2 and fast == [0.5]  # one retry, short jitter

    p = Scripted(Coded(503))
    monkeypatch.setattr(g, "PROVIDER", p)
    with pytest.raises(Coded):
        g.ask_gemini_system_user("s", "u", interactive=True, personal=False)
    assert p.calls == 2  # never more than one retry (the old default allowed two)

    p = Scripted(Coded(400))
    monkeypatch.setattr(g, "PROVIDER", p)
    with pytest.raises(Coded):
        g.ask_gemini_system_user("s", "u", interactive=True, personal=False)
    assert p.calls == 1


def test_non_interactive_calls_keep_the_configured_timeout_and_two_retries(monkeypatch, fast):
    p = Scripted(Coded(503))
    monkeypatch.setattr(g, "PROVIDER", p)
    with pytest.raises(Coded):
        g.ask_gemini_system_user("s", "u", personal=False)
    assert p.calls == 3


def test_breaker_opens_after_two_failed_chats_then_fails_fast(monkeypatch, fast):
    p = Slow(2.0)
    monkeypatch.setattr(g, "PROVIDER", p)
    t0 = time.perf_counter()
    first, second = chat("hello"), chat("hello again")
    assert time.perf_counter() - t0 < 2.0  # two deadlines of 0.2 s, not minutes
    assert first["ai_unavailable"] and second["ai_unavailable"] and g.BREAKER.state == OPEN
    calls = p.calls
    t0 = time.perf_counter()
    third = chat("still there?")
    assert time.perf_counter() - t0 < 0.1 and third["ai_unavailable"] and third["reply"]
    assert p.calls == calls  # no call made while the circuit is open


@pytest.mark.parametrize("text", ["i want to kill myself", "mujhe marna hai", "i am going to end my life tonight"])
def test_crisis_text_answers_instantly_even_when_the_provider_hangs(monkeypatch, fast, text):
    monkeypatch.setattr(g, "INTERACTIVE_TIMEOUT", 30.0)  # if the model were awaited this would take 30 s
    p = Slow(30.0)
    monkeypatch.setattr(g, "PROVIDER", p)
    t0 = time.perf_counter()
    out = chat(text)
    assert time.perf_counter() - t0 < 0.5
    assert out["escalate"] is True and out["recommended_action"] == "emergency_hotline"
    assert out["reply"] == svc.CRISIS_REPLY and out["helplines"] and p.calls == 0
    res = svc.ask_guarded(text, user_id=3)
    assert res["reply"] == svc.CRISIS_REPLY and p.calls == 0


def test_chat_route_is_fast_when_the_provider_is_dead(patient_client, monkeypatch, fast):
    p = Slow(2.0)
    monkeypatch.setattr(g, "PROVIDER", p)
    c, _ = patient_client
    t0 = time.perf_counter()
    r = c.post("/api/chat", json={"message": "hello"})
    assert time.perf_counter() - t0 < 1.0
    body = r.get_json()
    assert r.status_code == 200 and body["ai_unavailable"] is True and body["notice"] and body["reply"]
