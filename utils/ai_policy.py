"""Policy for what may be sent to an external AI model (Google Gemini).

Zero-cost deployment decision (2026-11-24): Gemini's free tier may use submitted content to improve Google products, and
billing is not acceptable, so student-authored or health-related text is NOT sent unless the operator switches it on
with AI_SEND_PERSONAL_TEXT=1 (and records the college's written approval in AI_PERSONAL_TEXT_APPROVED_BY).

Every call into the model layer must say `personal=True` (carries anything a student wrote or anything tied to a
user: chat, journal, voice, screening, mood, goals, medication, detox, progress, session transcripts) or
`personal=False` (fixed prompts with no user data: the daily tip, the starter-question answers). The low-level
`ask_gemini_system_user` requires the argument and calls `check()`; tests/test_ai_policy.py fails on any call that
does not state it. The deterministic crisis floor and canned replies never touch the model and are not affected.
"""
import os

TRUTHY = ('1', 'true', 'yes', 'on')


class PersonalTextBlocked(RuntimeError):
    """A personal-content model call was skipped because AI_SEND_PERSONAL_TEXT is off. Callers use their fallback."""


def personal_text_allowed():
    """True only for 1/true/yes/on. Read on every call, so the safe mode is the default and tests can flip it."""
    return os.environ.get('AI_SEND_PERSONAL_TEXT', '').strip().lower() in TRUTHY


def check(personal):
    """Gate for one model call. Raises TypeError when the call is unclassified, PersonalTextBlocked when blocked."""
    if not isinstance(personal, bool):
        raise TypeError('model calls must say personal=True or personal=False')
    if personal and not personal_text_allowed():
        raise PersonalTextBlocked('personal text is not sent to the model in this deployment')


def assistant_kind():
    """How the chat companion is described to students, matching what actually happens."""
    return 'an AI assistant' if personal_text_allowed() else 'an automated assistant'


def approval_recorded():
    """True when the operator wrote down who approved sending personal text (free text, never shown in the UI)."""
    return bool(os.environ.get('AI_PERSONAL_TEXT_APPROVED_BY', '').strip())
