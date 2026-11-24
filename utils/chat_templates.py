"""Starter questions for the chat page: a fixed server-side allowlist, never user text.

Each template has a plain static answer (used when the AI is off or down) and may have one AI answer cached for
24 hours, keyed by template id and the AI configuration version. Only these ids are ever cached; a message a
student types is never stored here. A cached answer passed `llm_guard.guard_output` before it was stored.
"""
import threading
import time
from typing import NamedTuple

from ai import gemini_impl
from utils import llm_guard
from utils.helplines import get_helplines

TTL_SECONDS = 24 * 3600
PROMPT_VERSION = '1'  # bump when SYSTEM changes, so old cached answers are not served
MAX_ENTRIES = 32      # the allowlist is far smaller; this only bounds a bug


class Template(NamedTuple):
    id: str
    label: str
    text: str
    answer: str  # static fallback; {help} becomes the first helpline from utils/helplines.py


TEMPLATES = (
    Template('exam-stress', 'Stress before exams', 'How can I manage stress before my exams?',
             "Exam stress is common and it can be eased with small steps. Break your syllabus into short blocks of "
             "25 to 40 minutes with a 5 minute break between them. Keep a fixed time for sleep, meals and water, "
             "because a tired mind remembers less. Try slow breathing for two minutes: breathe in for four counts, "
             "out for six. If the worry stays heavy for weeks or stops you from studying, talk to your college "
             "counsellor."),
    Template('sleep', 'Racing mind at night', 'What can I try when my mind is racing and I cannot sleep?',
             "A racing mind at night is common. Put screens away about 30 minutes before bed and keep the room dark "
             "and cool. Write your worries on paper so they do not have to stay in your head. Then try slow breathing "
             "or relaxing your muscles from your feet upwards. If you are still awake after 20 minutes, get up, sit "
             "somewhere dim and do something quiet until you feel sleepy. If sleep stays poor for weeks, mention it "
             "to your counsellor or a doctor."),
    Template('overwhelmed', 'Feeling overwhelmed', 'What is a quick way to calm down when I feel overwhelmed?',
             "When everything feels like too much, slow down your body first. Breathe in through the nose for four "
             "counts and out slowly for six, five times. Then name five things you can see and four you can touch. "
             "This brings your attention back to the present. Afterwards pick one small task and do only that. "
             "If the feeling keeps coming back, please talk to someone you trust or to your counsellor. "
             "You can also call {help} any time."),
    Template('counsellor', 'When to see a counsellor', 'How do I know when it is time to talk to a counsellor?',
             "You do not need to wait for a crisis. It is a good time to talk to a counsellor when low mood, worry or "
             "stress lasts more than two weeks, when it affects your sleep, studies or friendships, or when you "
             "feel stuck and cannot work it out alone. Talking early usually makes things easier. You can book a "
             "session from the appointments page. If you ever feel unsafe, call {help} right away."),
    Template('lonely', 'Feeling lonely or homesick', 'How can I cope with feeling lonely or homesick at college?',
             "Feeling lonely or homesick when you move away is very common, and it usually eases with time. Keep a "
             "regular call with someone from home, but also join one small group, such as a club, a sports hour or "
             "a study circle, so that faces become familiar. Say yes to one small invitation a week. Be patient with "
             "yourself. If the loneliness feels heavy or does not lift, your college counsellor is a good person to "
             "talk to, and {help} is there at any hour."),
    Template('habits', 'Daily habits for mood', 'What small daily habits help my mood?',
             "Small steady habits help more than big changes. Get some daylight and a short walk each day, keep "
             "regular meal and sleep times, and drink enough water. Spend a few minutes with a person you like, "
             "and do one thing each day only because you enjoy it. Notice how you feel in the mood tracker so you "
             "can see what helps you. If low mood continues despite this, please talk to your counsellor."),
)
_BY_ID = {t.id: t for t in TEMPLATES}

SYSTEM = ("You are Anya, an AI wellness companion for college students in India, not a therapist. Answer the "
          "student's general question in 4 to 6 short, plain, kind sentences with practical steps. No emoji, no "
          "em dashes, no links, no medicine names or doses, no diagnosis. Where it fits, suggest talking to the "
          "college counsellor. Reply with plain text only." + llm_guard.DATA_NOTE)


def get(template_id):
    """The template for an allowlisted id, else None (also for non-strings)."""
    return _BY_ID.get(template_id) if isinstance(template_id, str) else None


def public_list():
    """What the page needs to draw the buttons: id, label, text."""
    return [{'id': t.id, 'label': t.label, 'text': t.text} for t in TEMPLATES]


def fallback_answer(tpl):
    helps = get_helplines()
    first = f"{helps[0]['name'].split(' (')[0]} {helps[0]['number']}" if helps else 'a helpline'
    return tpl.answer.replace('{help}', first)


def config_version():
    return f"{gemini_impl.GEMINI_MODEL_NAME}|{llm_guard.max_reply_chars()}|{PROMPT_VERSION}"


_CACHE = {}  # (id, config version) -> (expires_at, text)
_LOCKS = {t.id: threading.Lock() for t in TEMPLATES}  # one AI call per template at a time
_clock = time.time  # patched in tests


def _cached(key):
    hit = _CACHE.get(key)
    if hit and hit[0] > _clock():
        return hit[1]
    _CACHE.pop(key, None)
    return None


def clear_cache():
    _CACHE.clear()


def _generate(tpl):
    """One guarded AI answer for the template text, or None (no key, outage, block, unsafe or empty output)."""
    if not getattr(gemini_impl.PROVIDER, 'configured', lambda: True)():
        return None
    system = SYSTEM + llm_guard.canary_line()
    try:
        raw = gemini_impl.ask_gemini_system_user(system, llm_guard.wrap('user_message', tpl.text),
                                                 max_tokens=400, temperature=0.4, interactive=True)
    except Exception:  # outage, block, breaker open: the static answer is used; the class is logged by the caller
        return None
    guarded = llm_guard.guard_output(raw, system_prompt=system)
    return None if (guarded.blocked or not guarded.text) else guarded.text


def answer(template_id):
    """Answer for an allowlisted template id: {id, text, reply, source, saved}. None for an unknown id.

    source is 'cache' (stored AI answer), 'ai' (fresh, now stored) or 'fallback' (static). `saved` is true for
    cache and fallback, which the page labels "Saved answer"."""
    tpl = get(template_id)
    if tpl is None:
        return None
    key = (tpl.id, config_version())
    reply = _cached(key)
    if reply:
        return {'id': tpl.id, 'text': tpl.text, 'reply': reply, 'source': 'cache', 'saved': True}
    with _LOCKS[tpl.id]:
        reply = _cached(key)  # another request may have filled it while this one waited
        if reply:
            return {'id': tpl.id, 'text': tpl.text, 'reply': reply, 'source': 'cache', 'saved': True}
        reply = _generate(tpl)
        if reply:
            if len(_CACHE) >= MAX_ENTRIES:
                _CACHE.pop(next(iter(_CACHE)))
            _CACHE[key] = (_clock() + TTL_SECONDS, reply)
            return {'id': tpl.id, 'text': tpl.text, 'reply': reply, 'source': 'ai', 'saved': False}
    return {'id': tpl.id, 'text': tpl.text, 'reply': fallback_answer(tpl), 'source': 'fallback', 'saved': True}
