"""Small thread-safe circuit breaker (closed -> open -> half-open) for the Gemini wrapper.

closed:    calls flow; `failures` consecutive failures open the circuit.
open:      calls are refused (callers use their rule-based fallback) until `reset_seconds` have passed.
half-open: exactly one trial call is let through; success closes the circuit, failure re-opens it.
State is three numbers, so memory is bounded. One breaker per process (not shared between workers).
"""
import os
import threading
import time

CLOSED, OPEN, HALF_OPEN = 'closed', 'open', 'half_open'


def _env_num(name, default, cast):
    try:
        value = cast(os.environ.get(name, default))
        return value if value > 0 else default
    except (TypeError, ValueError):
        return default


class CircuitBreaker:
    def __init__(self, failures=2, reset_seconds=60.0, clock=time.monotonic):
        self.failures = max(1, int(failures))
        self.reset_seconds = float(reset_seconds)
        self._clock = clock
        self._lock = threading.Lock()
        self.reset()

    @classmethod
    def from_env(cls, clock=time.monotonic):
        return cls(_env_num('AI_BREAKER_FAILURES', 2, int), _env_num('AI_BREAKER_RESET_SECONDS', 60.0, float), clock)

    def reset(self):
        with self._lock:
            self._fails = 0
            self._opened_at = None
            self._trial_out = False

    @property
    def state(self):
        with self._lock:
            return self._state()

    def _state(self):
        if self._opened_at is None:
            return CLOSED
        if self._clock() - self._opened_at >= self.reset_seconds:
            return HALF_OPEN
        return OPEN

    def allow(self):
        """True if a call may go out now. In half-open state only one caller gets True until it reports back."""
        with self._lock:
            state = self._state()
            if state == CLOSED:
                return True
            if state == HALF_OPEN and not self._trial_out:
                self._trial_out = True
                return True
            return False

    def record_success(self):
        with self._lock:
            self._fails, self._opened_at, self._trial_out = 0, None, False

    def record_failure(self):
        with self._lock:
            self._trial_out = False
            if self._opened_at is not None:  # failed trial (or a straggler): restart the cool-down
                self._opened_at = self._clock()
                return
            self._fails += 1
            if self._fails >= self.failures:
                self._opened_at = self._clock()

    def snapshot(self):
        return {'state': self.state, 'failure_threshold': self.failures, 'reset_seconds': self.reset_seconds}
