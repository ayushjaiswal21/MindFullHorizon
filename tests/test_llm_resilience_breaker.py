"""Circuit breaker state machine and bounded retries. No network, no Gemini: fakes only. Split out of
test_llm_resilience.py (300-line rule); budget/route degradation tests are in
test_llm_resilience_budget.py."""
import ai.gemini_impl as g
import ai.service as svc
import pytest
from ai.interface import AIProvider
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
    return g.ask_gemini_system_user("sys", "user", personal=False)


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
