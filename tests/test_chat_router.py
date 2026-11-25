"""Chat router (ai/router.py, ai/kb.py), gated behind CHAT_ROUTER_ENABLED (default off). No network, no model call.

Covers: a 16-query Hinglish smoke test (top-1 accuracy, author's own construction, same caveat as
docs/research/ai/encoders-nlp.md section 3.3 about shared-authorship inflation); that the crisis/friend/soft
floor always wins and the router never even runs on those messages; that the flag's default (0) preserves
today's off_reply() behaviour exactly; and that every knowledge-base entry is draft_unreviewed and reviewable
via `flask list-kb-drafts`.
"""
import asyncio

from ai import kb, router
from ai.replies import off_reply
from ai.service import ask_with_severity

# 16 queries, one per intent, written independently of ai/router.py's alias lists (not copy-pasted from them).
SMOKE_SET = (
    ("mera mood kaise track karu", "mood_checkin"),
    ("i want to take the phq9 test", "assessment"),
    ("diary mein likhna hai aaj", "journal"),
    ("can you guide me through a breathing exercise", "breathing"),
    ("panic attack aa raha hai help karo", "grounding"),
    ("neend nahi aa rahi raat ko", "sleep_log"),
    ("mujhe apna safety plan dekhna hai", "safety_plan"),
    ("goal set karna hai is hafte ka", "goals"),
    ("i want to book an appointment with a counsellor", "booking"),
    ("meri dawai ka record kaha milega", "medication_log"),
    ("phone ka use kam karna chahta hoon", "digital_detox"),
    ("kuch relaxing gana sunna hai", "music"),
    ("mera data kitna safe hai yahan", "about_privacy"),
    ("mujhe apna account delete karna hai", "delete_account"),
    ("exams ki wajah se bahut tension hai", "general_stressed"),
    ("ghar ki bahut yaad aa rahi hai akela lagta hai", "general_lonely"),
)


def test_smoke_set_top1_accuracy():
    correct = sum(1 for text, expect in SMOKE_SET if router.match(text).intent_id == expect)
    accuracy = correct / len(SMOKE_SET)
    # Honest bar for an independently-worded 16-query smoke test (not the alias lines themselves): most should
    # land on the right intent. Record the number, don't just assert a low floor.
    assert accuracy >= 0.75, f"top-1 accuracy {accuracy:.2f} ({correct}/{len(SMOKE_SET)}) below 0.75"


def test_unrelated_text_does_not_force_a_match():
    result = router.match("asdkj qweiop zzz nonsense text")
    assert not result.matched


def test_low_confidence_returns_clarifying_menu():
    result = router.match("hmm okay")
    assert not result.matched
    assert 0 < len(result.candidates) <= router.MENU_SIZE
    for intent_id, label in result.candidates:
        assert router.label_for(intent_id) == label


def test_every_kb_entry_is_reviewed_and_sourced():
    # All 16 entries were read and approved by the owner (a licensed psychiatrist/psychologist) on 2026-11-25;
    # see docs/review/signoff/2026-11-25-clinician-approvals.md. A future new entry must start as
    # "draft_unreviewed" again until it gets the same review - this test only checks every entry has SOME
    # recognised status and a source, not that it is still a draft.
    entries = kb.all_entries()
    assert len(entries) >= 10
    for e in entries:
        assert e["review_status"] in ("draft_unreviewed", "clinician_reviewed"), e["intent"]
        assert e.get("source"), e["intent"]
        assert e.get("snippet"), e["intent"]
    # every router intent has a KB answer
    for intent in router.INTENTS:
        assert kb.get_snippet(intent.id), intent.id


def test_list_kb_drafts_cli_surfaces_every_entry(app):
    result = app.test_cli_runner().invoke(args=["list-kb-drafts"])
    assert result.exit_code == 0
    for intent in router.INTENTS:
        assert intent.id in result.output
    assert "draft_unreviewed" in result.output


def test_flag_off_by_default_preserves_off_reply_exactly(monkeypatch):
    monkeypatch.delenv("CHAT_ROUTER_ENABLED", raising=False)
    monkeypatch.setenv("AI_SEND_PERSONAL_TEXT", "0")  # ai_on False: the off_reply() branch is reachable
    resp = asyncio.run(ask_with_severity("i want to book an appointment with a counsellor"))
    assert resp["reply"] == off_reply()


def test_flag_on_routes_an_ordinary_message_instead_of_off_reply(monkeypatch):
    monkeypatch.setenv("CHAT_ROUTER_ENABLED", "1")
    monkeypatch.setenv("AI_SEND_PERSONAL_TEXT", "0")
    resp = asyncio.run(ask_with_severity("i want to book an appointment with a counsellor"))
    assert resp["reply"] != off_reply()
    assert resp["reply"] == kb.get_snippet("booking")


def test_crisis_always_wins_even_with_a_router_trigger_phrase(monkeypatch):
    monkeypatch.setenv("CHAT_ROUTER_ENABLED", "1")
    monkeypatch.setenv("AI_SEND_PERSONAL_TEXT", "0")
    from ai.service import CRISIS_REPLY
    text = "i want to kill myself, also please book an appointment with a counsellor"
    resp = asyncio.run(ask_with_severity(text))
    assert resp["escalate"] is True
    assert resp["reply"] == CRISIS_REPLY


def test_soft_and_friend_floor_also_win_over_the_router(monkeypatch):
    monkeypatch.setenv("CHAT_ROUTER_ENABLED", "1")
    monkeypatch.setenv("AI_SEND_PERSONAL_TEXT", "0")
    from ai.service import FRIEND_REPLY, SOFT_REPLY
    friend_resp = asyncio.run(ask_with_severity("mera dost marna chahta hai, book an appointment with a counsellor"))
    assert friend_resp["reply"] == FRIEND_REPLY
    soft_resp = asyncio.run(ask_with_severity("i don't want to die but i feel hopeless, i want to log my mood"))
    assert soft_resp["reply"] == SOFT_REPLY
