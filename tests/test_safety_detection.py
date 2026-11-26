"""Safety tests: crisis phrase detection, helplines config, PHQ-9/GAD-7 scoring.

Phrase lists are the constructed fixtures from docs/SAFETY_RESEARCH.md (clinician/Hindi review pending).
Split out of test_safety.py (300-line rule); ask_with_severity/gemini_impl integration and the
save-assessment route/chat UI checks are in test_safety_integration.py.
"""
import os
import re

import pytest

from ai.severity import classify, heuristic_severity

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CRISIS_EN = [
    "i want to die", "I wanna die", "i want to kill myself", "i'm going to kill myself",
    "i am going to end my life", "i want to end it all", "i'm ending it tonight",
    "i can't go on anymore", "i don't want to be alive", "i don't want to live anymore",
    "i wish i were dead", "i wish i would not wake up", "everyone would be better off without me",
    "i'm a burden and should disappear", "i have a plan to kill myself",
    "i've been thinking about suicide", "suicidal thoughts every day", "i'm going to hurt myself",
    "i keep cutting myself", "i took too many pills", "thinking of overdosing",
    "i want to jump off the roof", "i'm going to hang myself", "i don't see any reason to live",
    "life is not worth living", "i'm done with everything, goodbye forever", "this is my last message",
    "i can't take it anymore, i want out permanently", "i'd be better off dead",
    "i'm planning to kill myself after exams", "I WANT TO DIEEEE", "i want to die!!!",
]
CRISIS_HI = [
    "mar jana chahta hu", "mar jana chahti hu", "mujhe marna hai", "jeena nahi chahta",
    "jeene ka mann nahi hai", "ab jee nahi sakta", "khud ko khatam kar lunga", "khud ko khatam karna hai",
    "apni jaan dena chahta hu", "main suicide karunga", "sab khatam kar dena hai",
    "mere jaane se sab theek ho jayega", "zindagi se thak gaya hu, marna chahta hu",
    "main kisi ko dikhai nahi dena chahta, hamesha ke liye", "khudkushi karne ka mann hai",
    "mar jana chahta hoon", "mujhe marna hai yaar", "jeena nhi chahta",
]
BENIGN = [
    "i'm killing it at the gym", "dying of laughter", "i could die for pizza", "i'd kill for a coffee",
    "my phone died", "main to hans hans ke mar gaya", "mera phone mar gaya", "battery mar gayi",
    "I booked a plane ticket, it means a lot to me", "I have a plan for the weekend",
    "the planet needs more trees", "we discussed the means of production in class",
    "I have access to the library", "the exam intent was unclear", "", "hello how are you",
]


@pytest.mark.parametrize("text", CRISIS_EN + CRISIS_HI)
def test_crisis_phrases_trigger(text):
    assert classify(text) == "crisis", text
    assert heuristic_severity(text) >= 9


@pytest.mark.parametrize("text", BENIGN)
def test_benign_phrases_do_not_trigger(text):
    assert classify(text) in ("none",), text
    assert heuristic_severity(text) <= 3


@pytest.mark.parametrize("text", [
    "this exam is killing me", "i don't want to die", "i do not want to die", "i would never kill myself",
    "i'm not suicidal", "mujhe marna nahi hai", "i can't take it anymore",
])
def test_ambiguous_or_negated_is_soft_checkin(text):
    assert classify(text) == "soft", text
    assert 4 <= heuristic_severity(text) <= 6


def test_negation_in_other_clause_does_not_hide_crisis():
    assert classify("i don't know, i want to die") == "crisis"
    assert classify("i don't want to die but i want to kill myself") == "crisis"
    assert classify("i can't stop thinking i want to die") == "crisis"


@pytest.mark.parametrize("text", [
    "she told me she wants to die, how can I help her?", "my friend wants to die", "my friend is suicidal",
    "my roommate said he wants to kill himself", "mera dost marna chahta hai", "meri dost suicide ki baat karti hai",
])
def test_third_party_is_friend_path(text):
    assert classify(text) == "friend", text
    assert heuristic_severity(text) < 7


def test_single_statement_reaches_emergency_level():
    assert heuristic_severity("I want to die") >= 9
    assert heuristic_severity("mujhe marna hai") >= 9


# ---------- helplines ----------
def test_helplines_config_is_india_only():
    from utils.helplines import get_helplines, helplines_text
    nums = " ".join(h["number"] for h in get_helplines())
    for expected in ("14416", "1800-599-0019", "112"):
        assert expected in nums
    blob = nums + helplines_text()
    for bad in ("988", "911", "741741", "9820466726", "9999 666 555", "Vandrevala"):
        assert bad not in blob
    assert all(h["last_verified"] == "2026-11" for h in get_helplines())


def test_no_us_numbers_in_ai_service():
    src = open(os.path.join(ROOT, "ai", "service.py"), encoding="utf-8").read()
    assert not re.search(r"\b(988|911|741741)\b", src)


# ---------- scoring ----------
def test_phq9_bands_and_labels():
    from ai.scoring import score_phq9
    cases = {0: "minimal", 4: "minimal", 5: "mild", 9: "mild", 10: "moderate", 14: "moderate",
             15: "moderately severe", 19: "moderately severe", 20: "severe", 27: "severe"}
    for total, band in cases.items():
        resp = [0] * 9
        i = 0
        left = total
        while left and i < 8:  # keep item 9 at 0
            resp[i] = min(3, left)
            left -= resp[i]
            i += 1
        if left:
            resp[8] = left
        assert score_phq9(resp)["total"] == total
        assert score_phq9(resp)["band"] == band, total


def test_gad7_bands():
    from ai.scoring import score_gad7
    for total, band in {0: "minimal", 4: "minimal", 5: "mild", 9: "mild", 10: "moderate", 14: "moderate",
                        15: "severe", 21: "severe"}.items():
        resp = [0] * 7
        for i in range(7):
            resp[i] = min(3, total - sum(resp))
        assert score_gad7(resp) == {"total": total, "band": band, "severe": total >= 15}


def test_phq9_item9_positive_regardless_of_total():
    from ai.scoring import score_phq9
    r = score_phq9([0, 0, 0, 0, 0, 0, 0, 0, 1])
    assert r["total"] == 1 and r["item9_positive"] is True and r["item9_answered"] is True
    r = score_phq9([3, 3, 3, 3, 3, 3, 3, 0, 0])
    assert r["item9_positive"] is False and r["item9_answered"] is True


def test_phq9_skipped_item9_is_unanswered_not_zero():
    from ai.scoring import score_phq9
    r = score_phq9([1, 1, 1, 1, 1, 1, 1, 1, None])
    assert r["item9_answered"] is False and r["item9_positive"] is False and r["total"] == 8


@pytest.mark.parametrize("bad", [None, "abc", [], [0] * 8, [0] * 10, [0, 0, 0, 0, 0, 0, 0, 0, 4],
                                 [0, 0, 0, 0, 0, 0, 0, 0, -1], [None] + [0] * 8, ["1"] * 9, [True] * 9, [1.5] * 9])
def test_phq9_rejects_invalid(bad):
    from ai.scoring import ScoreError, score_phq9
    with pytest.raises(ScoreError):
        score_phq9(bad)


def test_gad7_rejects_invalid():
    from ai.scoring import ScoreError, score_gad7
    for bad in (None, [0] * 6, [0] * 8, [4] * 7, [None] * 7):
        with pytest.raises(ScoreError):
            score_gad7(bad)


def test_canonical_type():
    from ai.scoring import canonical_type
    assert canonical_type("GAD-7 Anxiety Screening") == "GAD-7"
    assert canonical_type("PHQ-9 ANXIETY") == "PHQ-9"
    assert canonical_type("phq9") == "PHQ-9"
    assert canonical_type("Daily Mood") is None
    assert canonical_type(None) is None
