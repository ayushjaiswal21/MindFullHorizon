"""Tests for ai/fuzzy_crisis.py (SYNTHESIS.md section 3(a) item a3).

Reproduces, as closely as practical, the measurement method in docs/research/ai/encoders-nlp.md section 3.2:
respell one word (4+ letters) of a Hinglish must-trigger crisis phrase at a time, using the same six habits
that report names (drop an interior vowel, double "a", "i"->"ee", add "h" after t/d/k/g, drop the final
vowel, swap two letters), then compare floor-only recall to floor+fuzzy recall on the resulting variants.

IMPORTANT: the phrase set below is OUR OWN constructed fixture list (the same Hinglish phrases used in
tests/test_safety.py), not the original research corpus from encoders-nlp.md - that script lives in the
session scratchpad, not this repo. Numbers here will not exactly match encoders-nlp.md's 39%/58%; this test
exists to show the same *direction* of effect (fuzzy raises recall, with no benign false positives) on a
set we can rerun and check into the repo.
"""
import csv
import os

import pytest

from ai.fuzzy_crisis import classify_with_fuzzy, fuzzy_correct
from ai.severity import classify

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(ROOT, "docs", "review", "generated", "crisis_test_cases.csv")

# Must-trigger Hinglish crisis phrases (same fixtures as tests/test_safety.py::CRISIS_HI).
HINGLISH_CRISIS = [
    "mar jana chahta hu", "mar jana chahti hu", "mujhe marna hai", "jeena nahi chahta",
    "jeene ka mann nahi hai", "ab jee nahi sakta", "khud ko khatam kar lunga", "khud ko khatam karna hai",
    "apni jaan dena chahta hu", "main suicide karunga", "sab khatam kar dena hai",
    "mere jaane se sab theek ho jayega", "zindagi se thak gaya hu, marna chahta hu",
    "khudkushi karne ka mann hai", "mar jana chahta hoon", "mujhe marna hai yaar",
]


def _respellings(word):
    """The six habits from encoders-nlp.md 3.2, applied to one word of 4+ letters. Yields (habit, variant)."""
    if len(word) < 4:
        return
    vowels = "aeiou"
    for i in range(1, len(word) - 1):  # interior position only
        if word[i] in vowels:
            yield "drop_interior_vowel", word[:i] + word[i + 1:]
            break
    for i, ch in enumerate(word):
        if ch == "a":
            yield "double_a", word[:i] + "aa" + word[i + 1:]
            break
    for i, ch in enumerate(word):
        if ch == "i":
            yield "i_to_ee", word[:i] + "ee" + word[i + 1:]
            break
    for i, ch in enumerate(word[:-1]):
        if ch in "tdkg":
            yield "add_h", word[:i + 1] + "h" + word[i + 1:]
            break
    if word[-1] in vowels:
        yield "drop_final_vowel", word[:-1]
    if len(word) >= 5:
        yield "swap_letters", word[:2] + word[3] + word[2] + word[4:]


def _variants(phrase):
    """One variant per (word, habit) combination, respelling a single word of 4+ letters at a time."""
    words = phrase.split()
    for idx, w in enumerate(words):
        if len(w) < 4:
            continue
        for habit, respelled in _respellings(w):
            if respelled != w:
                out = words[:]
                out[idx] = respelled
                yield habit, " ".join(out)


def _all_variants():
    return [(habit, text) for phrase in HINGLISH_CRISIS for habit, text in _variants(phrase)]


VARIANTS = _all_variants()


def test_variant_set_is_nonempty_and_sized_like_the_research_experiment():
    # encoders-nlp.md used 326 variants from 27 phrases; our smaller fixture list gives fewer, but should
    # produce multiple variants per habit, not a degenerate set.
    assert len(VARIANTS) > 50
    habits = {h for h, _ in VARIANTS}
    assert len(habits) == 6


def test_fuzzy_layer_raises_recall_on_respelled_variants():
    """Floor-only recall vs floor+fuzzy recall on the respelled variants. Reports both; asserts fuzzy is
    never worse and meaningfully better, matching the DIRECTION (not the exact magnitude) of encoders-nlp.md
    section 3.2's measured +19 points (39% -> 58%)."""
    floor_hits = sum(classify(text) == "crisis" for _, text in VARIANTS)
    fuzzy_hits = sum(classify_with_fuzzy(text)[0] == "crisis" for _, text in VARIANTS)
    n = len(VARIANTS)
    floor_recall, fuzzy_recall = floor_hits / n, fuzzy_hits / n
    print(f"\n[fuzzy_crisis] floor recall={floor_recall:.2f} ({floor_hits}/{n}), "
          f"floor+fuzzy recall={fuzzy_recall:.2f} ({fuzzy_hits}/{n})")
    assert fuzzy_hits >= floor_hits  # raise-only: never worse
    assert fuzzy_recall - floor_recall >= 0.05  # meaningfully better on this constructed set


def test_fuzzy_matched_variants_are_tagged_fuzzy_not_exact():
    tagged_fuzzy = [text for _, text in VARIANTS
                    if classify(text) != "crisis" and classify_with_fuzzy(text) == ("crisis", "fuzzy")]
    assert tagged_fuzzy  # the layer does add some fuzzy-only hits on this set
    for text in tagged_fuzzy:
        assert classify_with_fuzzy(text)[1] == "fuzzy"


# ---------- false positives on the existing negative test cases ----------
def _csv_rows():
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def test_no_new_false_positives_on_existing_negative_cases():
    """Every non-crisis row in crisis_test_cases.csv must stay non-crisis with the fuzzy layer added
    (raise-only is only safe if it does not turn a benign/soft/friend case into 'crisis')."""
    rows = [r for r in _csv_rows() if r["test_expects"] != "crisis"]
    assert len(rows) == 57
    floor_fp = sum(classify(r["text"]) == "crisis" for r in rows)
    fuzzy_fp = sum(classify_with_fuzzy(r["text"])[0] == "crisis" for r in rows)
    print(f"\n[fuzzy_crisis] false positives on {len(rows)} negative cases: floor={floor_fp}, floor+fuzzy={fuzzy_fp}")
    assert floor_fp == 0  # the existing floor already has none on this fixture set
    assert fuzzy_fp == 0  # the fuzzy layer must add none


# ---------- negation / third-party safety (must survive a fuzzy near-miss exactly like the exact floor) ----------
@pytest.mark.parametrize("text", [
    "mujhe mrna nahi hai",         # negated respelling of "mujhe marna hai"
    "mujhe maarna nahi hai",
])
def test_negated_respelling_does_not_escalate_to_crisis(text):
    level, matched_via = classify_with_fuzzy(text)
    assert level != "crisis", (text, level, matched_via)
    assert matched_via == "fuzzy"  # confirms the fuzzy layer DID fire here, and the floor's negation rule still won


@pytest.mark.parametrize("text", [
    "mera dost mrna chahta hai",        # third-party respelling of "mera dost marna chahta hai"
    "meri saheli khud ko khtam karna chahti hai",  # third-party respelling of "...khud ko khatam karna..."
])
def test_third_party_respelling_stays_friend_not_crisis(text):
    level, matched_via = classify_with_fuzzy(text)
    assert level == "friend", (text, level, matched_via)
    assert matched_via == "fuzzy"  # confirms the fuzzy layer DID fire here, and the floor's own friend rule still won


def test_fuzzy_correct_is_a_pure_raise_only_helper():
    """fuzzy_correct never shortens/garbles ordinary benign text it has no vocabulary match for."""
    benign = "i booked a plane ticket, it means a lot to me"
    corrected, hit = fuzzy_correct(benign)
    assert hit is False
    assert classify_with_fuzzy(benign) == ("none", "none")


def test_classify_and_score_never_lowers_the_floors_own_severity():
    from ai.fuzzy_crisis import classify_and_score
    from ai.severity import heuristic_severity
    for text in ["i want to kill myself", "mrna chahta hu", "hello how are you"]:
        _, score, _ = classify_and_score(text)
        assert score >= heuristic_severity(text)
