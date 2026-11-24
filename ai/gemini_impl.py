"""Gemini access behind the AIProvider seam, plus resilience (breaker, bounded retries).

The SDK call lives only in GeminiProvider. `google.generativeai` is end-of-life: a future `google-genai`
adapter is another AIProvider subclass passed to set_provider(); breaker, retries and callers do not change.
The default model was never exercised against the live API in CI (tests use fakes). See docs/LLM_SECURITY.md.
"""
import logging
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout

from dotenv import load_dotenv

from ai.interface import AIProvider
from utils.circuit_breaker import CircuitBreaker


class _LazyGenai:
    """Imports google.generativeai on first use (about 1.4 s and 40 MB at startup otherwise).
    Attributes set on this object (tests monkeypatch `configure` / `GenerativeModel`) win over the real module."""

    def __getattr__(self, name):
        import google.generativeai as real
        return getattr(real, name)


genai = _LazyGenai()

# Load environment variables (safe to call multiple times)
load_dotenv()

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
# Model ids are retired often: set GEMINI_MODEL_NAME to pin one; the "-latest" alias is the default.
GEMINI_MODEL_NAME = os.environ.get("GEMINI_MODEL_NAME", "gemini-flash-latest")
FALLBACK_MODEL = "gemini-flash-latest"
try:
    GEMINI_TIMEOUT = float(os.environ.get("GEMINI_TIMEOUT", "20"))
except ValueError:
    GEMINI_TIMEOUT = 20.0
try:
    MAX_RETRIES = max(0, min(2, int(os.environ.get("AI_MAX_RETRIES", "2"))))  # hard ceiling of 2
except ValueError:
    MAX_RETRIES = 2

INTERACTIVE_TIMEOUT = 10.0    # hard cap (seconds, all attempts together) for chat and ask, whatever GEMINI_TIMEOUT says
INTERACTIVE_RETRIES = 1       # at most one retry, transient errors only
BREAKER = CircuitBreaker.from_env()
_sleep = time.sleep           # patched in tests
_uniform = random.uniform     # patched in tests

if not GEMINI_API_KEY:
    logger.warning("GEMINI_API_KEY is not set: AI features use fallbacks")


class GeminiBlocked(Exception):
    """The model refused or its safety filter blocked the reply (callers must keep crisis resources)."""


class AIUnavailable(RuntimeError):
    """The circuit breaker is open: no call was made. Callers use their rule-based fallback."""


_TRANSIENT_STATUS = {408, 429, 500, 502, 503, 504}
_TRANSIENT_NAMES = ('timeout', 'deadlineexceeded', 'serviceunavailable', 'resourceexhausted', 'toomanyrequests',
                    'internalservererror', 'gatewaytimeout', 'connectionerror', 'badgateway')


def _status(exc):
    for attr in ('code', 'status_code'):
        v = getattr(exc, attr, None)
        v = v() if callable(v) else v
        if isinstance(v, int) and 100 <= v <= 599:
            return v
    return None


def is_transient(exc):
    """Timeouts, 408/429/5xx and connection errors may be retried. Safety blocks and 4xx never are."""
    if isinstance(exc, (GeminiBlocked, AIUnavailable)):
        return False
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return True
    status = _status(exc)
    if status is not None:
        return status in _TRANSIENT_STATUS
    return any(n in type(exc).__name__.lower() for n in _TRANSIENT_NAMES)


def _counts_against_breaker(exc):
    """Client errors (400-499 except 408/429) are about the request, not the service: they must not open the circuit."""
    status = _status(exc)
    return not (status is not None and 400 <= status < 500 and status not in (408, 429))


class GeminiProvider(AIProvider):
    """google.generativeai adapter. Reads module settings at call time so tests and env changes apply."""

    def configured(self):
        return bool(GEMINI_API_KEY)

    def _generate(self, model_name, system_prompt, user_text, max_tokens, temperature, timeout):
        # system rules go in system_instruction, so user text is never concatenated into the instructions
        model = genai.GenerativeModel(model_name, system_instruction=system_prompt)
        response = model.generate_content(
            user_text,
            generation_config=genai.types.GenerationConfig(max_output_tokens=max_tokens, temperature=temperature),
            request_options={"timeout": timeout},
        )
        try:
            return response.text
        except ValueError as e:  # no candidates / finish_reason SAFETY
            raise GeminiBlocked("response blocked or empty") from e

    def ask(self, prompt, system_prompt="", max_tokens=1024, temperature=0.2, timeout=None, **_):
        genai.configure(api_key=GEMINI_API_KEY)
        timeout = timeout or GEMINI_TIMEOUT
        try:
            return self._generate(GEMINI_MODEL_NAME, system_prompt, prompt, max_tokens, temperature, timeout)
        except Exception as e:
            # A retired or unknown model id falls back to the alias; transient errors are retried by the caller.
            if isinstance(e, GeminiBlocked) or is_transient(e) or GEMINI_MODEL_NAME == FALLBACK_MODEL:
                raise
            logger.warning("Gemini model %s failed (%s), retrying with %s", GEMINI_MODEL_NAME, type(e).__name__, FALLBACK_MODEL)
            return self._generate(FALLBACK_MODEL, system_prompt, prompt, max_tokens, temperature, timeout)


PROVIDER: AIProvider = GeminiProvider()


def set_provider(provider: AIProvider):
    """Swap the model adapter (e.g. a google-genai one). Returns the previous provider."""
    global PROVIDER
    old, PROVIDER = PROVIDER, provider
    return old


_POOL = ThreadPoolExecutor(max_workers=8, thread_name_prefix='gemini')


def _call_with_retries(fn, max_retries=None, deadline=None):
    retries = MAX_RETRIES if max_retries is None else max_retries
    for attempt in range(retries + 1):
        try:
            return fn()
        except Exception as e:
            if attempt >= retries or not is_transient(e) or (deadline and time.monotonic() >= deadline):
                raise
            _sleep(_uniform(0, min(4.0, 0.5 * 2 ** attempt)))  # full jitter


def _interactive_attempt(ask, deadline):
    """One attempt that cannot outlive the shared deadline: the SDK timeout is a request option, not a promise,
    so the wait itself is bounded here. An abandoned thread ends on its own when the SDK gives up."""
    left = deadline - time.monotonic()
    if left <= 0:
        raise TimeoutError("interactive deadline")
    future = _POOL.submit(ask, left)
    try:
        return future.result(timeout=left)
    except FutureTimeout:
        raise TimeoutError("interactive deadline") from None


def ask_gemini_system_user(system_prompt: str, user_text: str, max_tokens: int = 1024,
                           temperature: float = 0.2, timeout: float = None, interactive: bool = False):
    """Call the model with a system instruction and the user's text.

    Raises GeminiBlocked on safety blocks, AIUnavailable while the breaker is open, RuntimeError without a key
    (before any retry, sleep or breaker use). Retries (max 2, jittered) only transient errors; one request counts
    as one breaker outcome. `interactive=True` (a student is waiting): all attempts share one deadline of at most
    INTERACTIVE_TIMEOUT seconds and there is at most one retry, so a dead provider costs one wait, then the breaker opens."""
    if not getattr(PROVIDER, "configured", lambda: True)():
        raise RuntimeError("GEMINI_API_KEY not set")
    if not BREAKER.allow():
        raise AIUnavailable("circuit open")

    def one(t=None):
        return PROVIDER.ask(user_text, system_prompt=system_prompt, max_tokens=max_tokens,
                            temperature=temperature, timeout=t or timeout)
    try:
        if interactive:
            deadline = time.monotonic() + min(timeout or INTERACTIVE_TIMEOUT, INTERACTIVE_TIMEOUT)
            out = _call_with_retries(lambda: _interactive_attempt(one, deadline), INTERACTIVE_RETRIES, deadline)
        else:
            out = _call_with_retries(one)
    except GeminiBlocked:
        BREAKER.record_success()  # the service answered; a block is not an outage
        raise
    except Exception as e:
        if _counts_against_breaker(e):
            BREAKER.record_failure()
        else:
            BREAKER.record_success()
        logger.warning("Gemini call failed: %s", type(e).__name__)  # class only: SDK messages can echo the payload
        raise
    BREAKER.record_success()
    return out
