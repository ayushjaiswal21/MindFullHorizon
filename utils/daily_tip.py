"""Tip of the day: one short, general wellbeing tip for everyone, with no user data in the request.

The only model call here is `personal=False`: a fixed prompt plus a topic from a fixed list. At most one attempt per IST
day per process, started by GET /api/tip (never by a page render) and run in the background; until it lands (or if it fails, is blocked by the
output guard, or no key is set) the static list in utils/tip_data.py is shown. Per-process memory, no database: a restart
can cost one more call, never a repeat storm. See docs/LLM_SECURITY.md."""
import logging
import threading

from ai import gemini_impl
from utils import llm_guard
from utils.timeutil import ist_today
from utils.tip_data import TIPS, TOPICS

logger = logging.getLogger(__name__)

SYSTEM = ("You write one short, general wellbeing tip for college students in India. One or two plain sentences, at "
          "most 30 words. No emoji, no em dashes, no links, no medicine names or doses, no diagnosis, no promises. "
          "It is general information, not advice for any one person. Reply with the tip only.")
MAX_CHARS = 220

_STATE = {'day': None, 'text': None, 'started': False}
_LOCK = threading.Lock()


def _run(fn):  # patched in tests to run inline
    threading.Thread(target=fn, name='daily-tip', daemon=True).start()


def _static(day):
    return TIPS[day.toordinal() % len(TIPS)]


def _generate(day):
    """The model's tip for `day`, or None (no key, outage, breaker open, blocked or empty output)."""
    system = SYSTEM + llm_guard.canary_line()
    try:
        raw = gemini_impl.ask_gemini_system_user(system, 'Topic: ' + TOPICS[day.toordinal() % len(TOPICS)],
                                                 max_tokens=80, temperature=0.8, interactive=True, personal=False)
    except Exception as exc:  # class only: SDK messages can echo the payload
        logger.warning('daily tip not generated (%s)', type(exc).__name__)
        return None
    guarded = llm_guard.guard_output(raw, max_chars=MAX_CHARS, system_prompt=system)
    return None if (guarded.blocked or not guarded.text) else guarded.text


def _refresh(day):
    text = _generate(day)
    if text:
        with _LOCK:
            if _STATE['day'] == day:
                _STATE['text'] = text


def get_tip(refresh=False):
    """{'text', 'source'} for today (IST). source is 'model' or 'static'. Never raises, never blocks.

    Page renders call it with refresh=False and never start a model call; only GET /api/tip (refresh=True) may."""
    day = ist_today()
    with _LOCK:
        if _STATE['day'] != day:
            _STATE.update(day=day, text=None, started=False)
        if _STATE['text']:
            return {'text': _STATE['text'], 'source': 'model'}
        start = refresh and not _STATE['started'] and getattr(gemini_impl.PROVIDER, 'configured', lambda: True)()
        _STATE['started'] = _STATE['started'] or refresh  # one attempt a day, whatever the outcome
    if start:
        _run(lambda: _refresh(day))
    return {'text': _static(day), 'source': 'static'}


def reset():
    with _LOCK:
        _STATE.update(day=None, text=None, started=False)
