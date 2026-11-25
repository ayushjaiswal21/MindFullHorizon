"""AI generators. Every model call goes through utils/llm_guard.py (sanitise, wrap as data, guard output) and
ai/gemini_impl.py (breaker, retries). The deterministic crisis floor (ai/severity.py) runs first and alone decides
the emergency path: no model output, injection verdict, budget or outage can suppress it. See docs/LLM_SECURITY.md."""
import json
import logging
import os
from functools import lru_cache

from ai import gemini_impl
from ai.gemini_impl import ask_gemini_system_user, GeminiBlocked
from ai.severity import classify  # re-exported for callers/tests; ask_with_severity itself uses classify_and_score
from ai.fuzzy_crisis import classify_and_score, classify_with_fuzzy
from ai.replies import off_reply
from utils import ai_policy, llm_guard
from utils.helplines import get_helplines, helplines_lines, helplines_text

logger = logging.getLogger(__name__)

DATA_NOTE = llm_guard.DATA_NOTE
ACTIONS = ('none', 'recommend_appointment', 'emergency_hotline')
_PROMPT_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'ai_prompts', 'psychologist_system.txt')

CRISIS_REPLY = ("I'm really sorry you are in this much pain. You matter, and you do not have to carry this alone. "
                "Are you safe right now? Please call Tele-MANAS 14416 or KIRAN 1800-599-0019 (free, 24x7), "
                "or 112 if you are in immediate danger, and reach out to someone you trust nearby. "
                "Counsellors at your college who use this app can see that an alert was raised, without your words, "
                "so that someone can reach out to you.")
FRIEND_REPLY = ("I'm sorry, that sounds really worrying. Staying with your friend and listening without judging helps a lot. "
                "You can call Tele-MANAS 14416 together, and call 112 if they are in immediate danger. "
                "Is your friend safe right now?")
SOFT_REPLY = ("That sounds really heavy. Are you having thoughts of ending your life, or is it more that you feel "
              "exhausted and stuck? I'm here either way.")
DEFAULT_REPLY = "I hear you, that sounds really hard. Can you tell me what happened before this?"
UNAVAILABLE_NOTICE = ("AI is temporarily unavailable, so you are getting a standard supportive reply. "
                      "Crisis detection is still active.")
LIMIT_NOTICE = ("You have reached the AI message limit for now. Please try again later. If you feel unsafe, call "
                "Tele-MANAS 14416, KIRAN 1800-599-0019 or 112. Messages about harming yourself are still answered right away.")
_FALLBACK_PROMPT = ("You are Anya, an AI wellness companion, not a therapist. Respond concisely. Output ONLY JSON: "
                    '{"reply": "string", "severity": int(0-10), "reason": "string<=12words", '
                    '"recommended_action": "none"|"recommend_appointment"|"emergency_hotline"}.')

GENERIC_PROMPT = ("You are Anya, an AI wellness companion for college students in India, not a therapist. Be brief, plain "
                  "and kind. No emoji, no em dashes, no links, no medicine names or doses, no diagnosis.")


@lru_cache(maxsize=4)
def _persona(cap):
    try:
        with open(_PROMPT_FILE, 'r', encoding='utf-8') as f:
            return f.read().replace('{max_reply_chars}', str(cap))
    except OSError:
        return _FALLBACK_PROMPT


def build_system_prompt(hardened=False):
    """Persona and rules + canary + data-handling note (+ alert when the input looked like an injection)."""
    return (_persona(llm_guard.max_reply_chars()) + llm_guard.canary_line() + llm_guard.DATA_NOTE
            + (llm_guard.HARDENED_NOTE if hardened else ''))


def ask(prompt: str, system_prompt: str = GENERIC_PROMPT, max_tokens: int = 1024, temperature: float = 0.7, *,
        personal: bool, **kwargs) -> str:
    """Call the configured AI client. `personal` is required (utils/ai_policy.py); kwargs (e.g. timeout) go to Gemini."""
    return ask_gemini_system_user(system_prompt, prompt, max_tokens=max_tokens, temperature=temperature,
                                  personal=personal, **kwargs)


def _personal_call(system, payload, field, route, tag='data', **kw):
    """Model call for stored/user content (always personal=True, so blocked unless AI_SEND_PERSONAL_TEXT is on):
    sanitised, wrapped as data, system prompt hardened when the content looks like an injection attempt."""
    block, verdict = llm_guard.data_block(payload, field, tag)
    llm_guard.log_event(route, verdict, chars=len(block))
    return ask(block, system_prompt=system + DATA_NOTE + (llm_guard.HARDENED_NOTE if verdict.hardened else ''),
               personal=True, **kw)


def check_api_status() -> dict:
    """Cheap config check (no network call, no secrets) for /health and /api/ai-status."""
    ok = bool(gemini_impl.GEMINI_API_KEY)
    return {'api_key_configured': ok, 'model_available': ok, 'model': gemini_impl.GEMINI_MODEL_NAME,
            'breaker': gemini_impl.BREAKER.state}


def _to_int(value, default):
    try:
        return int(float(value))
    except (TypeError, ValueError, OverflowError):
        return default


def _parse_llm_json(raw):
    """First JSON object in the model output as a dict (strings filtered like any model output), or None."""
    clean = (raw or '').strip().replace('```json', '').replace('```', '')
    start = clean.find('{')
    candidates = []
    if start >= 0:
        try:
            parsed, _ = json.JSONDecoder().raw_decode(clean[start:])
            candidates.append(parsed)
        except ValueError:
            if clean.startswith('{'):  # truncated output: try closing it
                try:
                    candidates.append(json.loads(clean + ('"' if clean.count('"') % 2 else '') + '}'))
                except ValueError:
                    pass
    for parsed in candidates:
        if isinstance(parsed, dict):
            return llm_guard.clean_json(parsed)
    logger.warning("Could not parse LLM JSON reply")
    return None


def _loads_clean(raw, expect):
    """json.loads of model output with a shape check; raises json.JSONDecodeError like the old bare json.loads."""
    clean = (raw or '').strip().replace('```json', '').replace('```', '')
    obj = json.loads(clean)
    if not isinstance(obj, expect):
        raise json.JSONDecodeError("unexpected shape", clean, 0)
    return llm_guard.clean_json(obj)


def routed_reply(raw_text):
    """Replaces off_reply() for an ordinary (level == 'none') message when CHAT_ROUTER_ENABLED=1: a local lexical
    match (ai/router.py) against a fixed intent list, answered from a draft knowledge-base snippet (ai/kb.py).
    Pure text matching, no model call, nothing leaves this process. Falls back to off_reply() on no confident
    match, on an unreviewed/missing snippet, or when the flag is off (today's unchanged behaviour)."""
    if os.environ.get('CHAT_ROUTER_ENABLED', '').strip().lower() in ('1', 'true', 'yes', 'on'):
        from ai import kb, router
        result = router.match(raw_text)
        if result.matched:
            snippet = kb.get_snippet(result.intent_id)
            if snippet:
                guarded = llm_guard.guard_output(snippet)
                if guarded.text:
                    return guarded.text
        elif result.candidates:
            menu = ', '.join(label for _, label in result.candidates)
            return f"I'm not sure what you mean yet. Did you want help with: {menu}? You can also pick a saved question above."
    return off_reply()


async def ask_with_severity(user_text: str, user_id=None, prefer_llm=True, history=None):
    """Chat turn. Returns {reply, severity, reason, recommended_action, escalate, helplines,
    ai_unavailable, notice, rate_limited, retry_after}.

    A heuristic crisis hit always wins: emergency action + helplines, whatever the LLM says, whether it fails,
    and whether the user's budget is spent. `history` (optional list of {role, text}) is untrusted data.
    """
    raw = llm_guard.bound(user_text) if isinstance(user_text, str) else ''
    # 1. deterministic floor + raise-only fuzzy layer (ai/fuzzy_crisis.py); matched_via tags a fuzzy-only hit for audit
    level, score, matched_via = classify_and_score(raw)
    # 2. detection is informational only (hardens the prompt); it never changes the floor
    clean = llm_guard.sanitize(raw, 'chat')
    verdict = llm_guard.detect(raw)
    llm_guard.log_event('chat', verdict, level, chars=len(raw), sent=len(clean))
    # 3. per-user budget (session id); over budget or personal text off: no model call, the floor still answers
    ai_on = ai_policy.personal_text_allowed()
    allowed, retry_after = True, 0
    if user_id is not None and ai_on:
        allowed, _, retry_after = llm_guard.BUDGET.consume(user_id)

    parsed, blocked, unavailable, system_prompt = None, False, not allowed, ''
    if ai_on and allowed and prefer_llm and clean and level != 'crisis':  # the floor answers a crisis alone: never wait on the model
        system_prompt = build_system_prompt(verdict.hardened)
        payload = (llm_guard.format_history(history) + '\n' if history else '') + llm_guard.wrap('user_message', clean)
        try:
            parsed = _parse_llm_json(ask_gemini_system_user(system_prompt, payload, max_tokens=512, temperature=0.2,
                                                            interactive=True, personal=True))
        except GeminiBlocked:
            blocked = True
        except Exception as e:
            unavailable = True
            logger.warning("Gemini call failed inside ask_with_severity: %s", type(e).__name__)

    reply, reason, action = None, '', 'none'
    if parsed:
        score = max(score, min(10, max(0, _to_int(parsed.get('severity'), 0))))  # the model can only raise severity
        action = parsed.get('recommended_action') if parsed.get('recommended_action') in ACTIONS else 'none'
        reason = llm_guard.clean_text(str(parsed.get('reason') or ''))[0][:100]
        guarded = llm_guard.guard_output(parsed.get('reply'), high_severity=score >= 7 or level == 'crisis',
                                         system_prompt=system_prompt)
        # blocked content on a risk path is replaced by the fixed template below, never by model words
        reply = guarded.text if guarded.text and not (guarded.blocked and level != 'none') else None
    if level == 'friend':
        score = min(score, 6)  # someone else is at risk: support path, not the self-crisis card
        if action == 'emergency_hotline':
            action = 'none'

    crisis = level == 'crisis' or score >= 7
    if crisis:
        score, action, reason = max(score, 9 if level == 'crisis' else 7), 'emergency_hotline', reason or 'possible self-harm risk'
    elif score >= 5 and action == 'none' and level != 'soft':
        action = 'recommend_appointment'
    if crisis:
        reply = None  # on the emergency path the student always sees the fixed, clinician-reviewable text
    reply = reply or (CRISIS_REPLY if crisis else FRIEND_REPLY if level == 'friend'
                      else SOFT_REPLY if level == 'soft' or blocked else DEFAULT_REPLY if ai_on else routed_reply(raw))
    if crisis and not parsed:
        reason = 'explicit self-harm language' if level == 'crisis' else 'high distress signals'
    fuzzy = crisis and matched_via == 'fuzzy'

    rate_limited = (not allowed) and not crisis and level == 'none'
    notice = None
    if not allowed:
        notice = LIMIT_NOTICE
    elif unavailable:
        notice = UNAVAILABLE_NOTICE
    show_helplines = crisis or level in ('friend', 'soft') or blocked or rate_limited
    return {
        'reply': reply,
        'severity': int(score),
        'reason': reason,
        'recommended_action': action,
        'escalate': bool(crisis),
        'helplines': get_helplines() if show_helplines else [],
        'ai_unavailable': bool(unavailable),
        'notice': notice,
        'fuzzy': fuzzy,  # audit-only: this crisis hit came from the fuzzy layer, not an exact regex match
        'rate_limited': bool(rate_limited),
        'retry_after': int(retry_after) if rate_limited else 0,
    }


def _simple_chat(prompt, user_id=None):
    """Single-turn supportive reply used by /api/ask and the socket chat. Same floor, budget and guards as chat."""
    raw = llm_guard.bound(prompt) if isinstance(prompt, str) else ''
    level, _matched_via = classify_with_fuzzy(raw)
    if level == 'crisis':
        return {'reply': CRISIS_REPLY, 'rate_limited': False, 'retry_after': 0, 'ai_unavailable': False, 'notice': None}
    ai_on = ai_policy.personal_text_allowed()
    if not ai_on:  # personal text is not sent to a model: fixed replies only, no budget used, nothing to report as down
        return {'reply': FRIEND_REPLY if level == 'friend' else SOFT_REPLY if level == 'soft' else off_reply(),
                'rate_limited': False, 'retry_after': 0, 'ai_unavailable': False, 'notice': None}
    if user_id is not None:
        allowed, _, retry_after = llm_guard.BUDGET.consume(user_id)
        if not allowed:
            return {'reply': LIMIT_NOTICE, 'rate_limited': True, 'retry_after': int(retry_after),
                    'ai_unavailable': True, 'notice': LIMIT_NOTICE}
    clean = llm_guard.sanitize(raw, 'chat')
    verdict = llm_guard.detect(raw)
    llm_guard.log_event('ask', verdict, chars=len(raw), sent=len(clean))
    system = ("You are Anya, a supportive wellness companion, an AI and not a therapist. Reply in 2 or 3 short, plain, "
              "empathetic sentences in the user's language (English or Hinglish). No emoji, no em dashes, no links, no "
              "medicine names or doses, no diagnosis." + DATA_NOTE + (llm_guard.HARDENED_NOTE if verdict.hardened else ''))
    try:
        out = ask(llm_guard.wrap('user_message', clean), system_prompt=system, max_tokens=150, interactive=True, personal=True)
    except Exception as e:
        logger.warning("Chat reply failed: %s", type(e).__name__)
        return {'reply': "I'm here to support you. How can I help you today?", 'rate_limited': False, 'retry_after': 0,
                'ai_unavailable': True, 'notice': UNAVAILABLE_NOTICE}
    text = llm_guard.guard_output(out, system_prompt=system).text
    return {'reply': text or "I'm here to support you. How can I help you today?", 'rate_limited': False,
            'retry_after': 0, 'ai_unavailable': False, 'notice': None}


def ask_guarded(prompt, user_id=None):
    """Dict form of the single-turn chat (reply, rate_limited, retry_after, ai_unavailable, notice)."""
    return _simple_chat(prompt, user_id)


def generate_chat_response(prompt: str, user_id=None) -> str:
    """Short supportive reply for the simple chat endpoint (crisis text never reaches the model)."""
    return _simple_chat(prompt, user_id)['reply']


def _assessment_fallback(assessment_type, score, summary=None):
    return {
        "summary": summary or f"Your {assessment_type} score is {score}. AI insights are temporarily unavailable.",
        "recommendations": [
            "Practice regular self-care and stress management",
            "Consider talking to a counselor or doctor, especially if symptoms persist",
            "Keep a steady routine for sleep, food and movement",
        ],
        "resources": helplines_lines(),
    }


def generate_assessment_insights(assessment_type: str, score: int, responses: list, timeout: float = 8) -> dict:
    """Insights for a saved assessment. Raises on AI failure (caller keeps saving); resources are always our helplines."""
    system_prompt = ("You are a supportive wellness assistant. This is a screening result, not a diagnosis. "
                     'Return ONLY JSON: {"summary": "<100 words", "recommendations": ["..", "..", ".."]}. '
                     "Do not invent phone numbers or links.")
    data = {"type": assessment_type, "score": score, "responses": responses}
    insights = _parse_llm_json(_personal_call(system_prompt, data, 'data', 'assessment', max_tokens=600, timeout=timeout))
    if not insights:
        return _assessment_fallback(assessment_type, score, f"Your {assessment_type} score is {score}.")
    if not isinstance(insights.get("recommendations"), list):
        insights["recommendations"] = _assessment_fallback(assessment_type, score)["recommendations"]
    insights["resources"] = helplines_lines()  # never trust model-written phone numbers
    return insights


def generate_progress_recommendations(user_data: dict) -> dict:
    """AI-powered progress recommendations based on user data."""
    def plain(i1, d1, i2, d2, a1, ad1, a2, ad2):
        return {"insights": [{"title": i1, "desc": d1}, {"title": i2, "desc": d2}],
                "actions": [{"title": a1, "desc": ad1, "priority": "medium"}, {"title": a2, "desc": ad2, "priority": "high"}]}
    try:
        system_prompt = ("You are a mental health coach. Given the data block, return JSON: "
                         '{"insights": [{"title": "T1", "desc": "D1"}], '
                         '"actions": [{"title": "A1", "desc": "D1", "priority": "high"}]}')
        response = _personal_call(system_prompt, user_data, 'data', 'progress', max_tokens=500)
        try:
            return _loads_clean(response, dict)
        except json.JSONDecodeError:
            logger.error("Failed to parse progress recommendations JSON")
            return plain("Keep Going", "You're making progress on your mental health journey.", "Stay Consistent",
                         "Regular check-ins help maintain mental wellness.", "Continue Daily Monitoring",
                         "Keep tracking your mood and symptoms.", "Practice Self-Care",
                         "Make time for activities that support your wellbeing.")
    except Exception as e:
        logger.warning("Error generating progress recommendations: %s", type(e).__name__)
        return plain("Progress Tracking", "Continue monitoring your mental health journey.", "Wellness Focus",
                     "Prioritize self-care and healthy habits.", "Daily Check-ins",
                     "Monitor your mood and symptoms regularly.", "Healthy Lifestyle",
                     "Maintain sleep, exercise, and nutrition balance.")


def generate_digital_detox_insights(detox_data: dict) -> dict:
    """AI-powered digital detox insights."""
    try:
        system_prompt = ("You are a digital wellness coach. Given the data block, return JSON: "
                         '{"analysis": "Brief analysis", "recommendations": ["Rec 1", "Rec 2"], "score": "Score/100 (string)"}')
        response = _personal_call(system_prompt, detox_data, 'data', 'detox', max_tokens=400)
        try:
            return _loads_clean(response, dict)
        except json.JSONDecodeError:
            logger.error("Failed to parse digital detox insights JSON")
            return {
                "analysis": "Your digital habits show room for improvement in screen time management.",
                "recommendations": [
                    "Set daily screen time limits",
                    "Take regular breaks from digital devices",
                    "Create tech-free zones in your home"
                ],
                "score": "75"
            }
    except Exception as e:
        logger.warning("Error generating digital detox insights: %s", type(e).__name__)
        return {
            "analysis": "Digital wellness analysis temporarily unavailable.",
            "recommendations": [
                "Monitor your screen time regularly",
                "Balance digital and offline activities",
                "Practice digital mindfulness"
            ],
            "score": "70"
        }


def generate_goal_suggestions(patient_data: dict) -> list:
    """AI-powered goal suggestions based on patient data."""
    try:
        system_prompt = ('Wellness coach. Suggest 3 goals from the data block. Return a JSON array: '
                         '[{"title": "T", "description": "D"}]')
        response = _personal_call(system_prompt, patient_data, 'data', 'goals', max_tokens=300)
        try:
            return _loads_clean(response, list)
        except json.JSONDecodeError:
            logger.error("Failed to parse goal suggestions JSON")
            return []
    except Exception as e:
        logger.warning("Error generating goal suggestions: %s", type(e).__name__)
        return []


def analyze_medication_adherence(medication_logs: list, patient_data: dict) -> dict:
    """Analyze medication adherence and provide insights."""
    fallback = {"adherence_score": 0, "insight": "Unable to analyze adherence at this time.",
                "recommendation": "Continue tracking your medication."}
    try:
        system_prompt = ("Medical assistant. Given the data block, return JSON: "
                         '{"adherence_score": 85, "insight": "Brief insight", "recommendation": "Brief rec"}')
        response = _personal_call(system_prompt, {"logs": medication_logs, "data": patient_data}, 'data', 'adherence', max_tokens=300)
        try:
            result = _loads_clean(response, dict)
            result["adherence_score"] = max(0, min(100, _to_int(result.get("adherence_score"), 0)))
            return result
        except json.JSONDecodeError:
            logger.error("Failed to parse medication adherence JSON")
            return fallback
    except Exception as e:
        logger.warning("Error analyzing medication adherence: %s", type(e).__name__)
        return fallback


def generate_journal_insights(title: str, content: str, sentiment: str) -> str:
    """AI insights for a journal entry. Crisis language gets fixed helplines text instead of model output."""
    if classify_with_fuzzy(llm_guard.bound(f"{title} {content}"))[0] == 'crisis':
        return ("It sounds like you are going through something very painful, and I'm glad you wrote it down. "
                "You do not have to carry it alone. Please reach out now: " + helplines_text())
    try:
        system_prompt = ("You are Anya, a compassionate wellness coach (an AI, not a therapist). Given a journal entry "
                         "as JSON, reply with: 1. Insights (2-3 sentences) 2. Suggestions (3 bullets) "
                         "3. Coping strategies (2-3 items) 4. Encouragement (1 sentence). Plain text with headers, "
                         "under 800 chars, no emoji, no em dashes, no links, no medicine names or doses.")
        entry = {"title": title, "content": content, "sentiment": sentiment}
        text = _personal_call(system_prompt, entry, 'journal', 'journal', tag='journal_entry', max_tokens=400)
        return llm_guard.guard_output(text, max_chars=900, system_prompt=system_prompt).text or \
            "Thank you for sharing. Consider discussing these feelings with a professional."
    except Exception as e:
        logger.warning("Error generating journal insights: %s", type(e).__name__)
        return "Thank you for sharing. Consider discussing these feelings with a professional."


# analyze_voice_emotion removed 2026-11-25: the voice tone/emotion label was measured invalid
# (docs/research/ai/SYNTHESIS.md 1.1, 3(c) item c1); see docs/research/ai/decisions/voice-tone-removed.md.


def generate_clinical_note(transcript, patient_context=None) -> str:
    """Draft clinician-review note from a session transcript. Returns a placeholder if the AI is unavailable."""
    try:
        system_prompt = ("You draft concise session notes for a licensed clinician to review and edit. Summarize "
                         "presenting concerns, mood, risk statements quoted neutrally, and follow-ups. Do not diagnose "
                         "or prescribe.")
        text = _personal_call(system_prompt, {"transcript": transcript, "context": patient_context}, 'note', 'clinical_note',
                     tag='transcript', max_tokens=700, temperature=0.3)
        # clinician-facing: medicines and risk quotes may appear, so only the structural filters apply
        return llm_guard.guard_output(text, max_chars=3000, system_prompt=system_prompt, content_checks=False).text or \
            "AI draft note unavailable. Please write the session note manually."
    except Exception as e:
        logger.warning("Error generating clinical note: %s", type(e).__name__)
        return "AI draft note unavailable. Please write the session note manually."
