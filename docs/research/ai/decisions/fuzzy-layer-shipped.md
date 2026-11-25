# Decision: fuzzy crisis-vocabulary layer shipped (2026-11-25)

## What shipped
`ai/fuzzy_crisis.py` (new, <300 lines): edit-distance-1 (rapidfuzz, MIT) snap of 4+ letter tokens onto a
36-word Hinglish crisis vocabulary, raise-only, OR'd with `ai/severity.py::classify`, tagged `matched_via`
('exact'/'fuzzy') so a fuzzy hit is never silently indistinguishable from a direct regex hit. Wired into
`ai/service.py::ask_with_severity`/`_simple_chat`/`generate_journal_insights` and `utils/crisis.py::text_is_crisis(_detailed)`.
The student-facing crisis reply, helplines and escalation are unchanged for a fuzzy-only hit; the `fuzzy`
tag (result dict key, and a `_fuzzy` suffix on `CrisisEvent.reason` in the chat/journal paths) is audit-only.

## Evidence this followed (SYNTHESIS.md 3(a) a3, encoders-nlp.md 3.2)
Measured on the research agent's own script (not in this repo): floor recall on 326 systematic Hinglish
respellings of 27 crisis phrases rose from 39% to 58% with the same mechanism, 0 added false positives on
57 non-crisis cases. Reproduced here on a constructed set of the same shape (`tests/test_fuzzy_crisis.py`,
built from this repo's own fixtures, not the original research corpus): floor recall 42% -> 58% on 177
variants of 16 Hinglish crisis phrases; 0 false positives, before and after, on all 57 non-crisis rows of
`docs/review/generated/crisis_test_cases.csv`. Negation and third-party fuzzy near-misses stay soft/friend
(tested explicitly), because the fuzzy branch is still run through `classify()`'s own negation-window and
third-party logic, never a bare vocabulary-presence check.

## What this decision is NOT
This is **BUILD NOW**, not **fully validated**. Per SYNTHESIS.md section 2's own gate:
1. The 36-word vocabulary (`ai/fuzzy_crisis.py::VOCAB`) has NOT had clinician or native-Hinglish-speaker
   review (same O-20 status as every other wordlist in this codebase). Do not treat it as safe for real
   student traffic until that review happens.
2. The false-positive rate is measured only on the 57-case fixture set above (same limitation the research
   report names for its own 57-case set: a 95% interval of roughly 1-15 percentage points). It must be
   re-validated once SYNTHESIS.md section 2's independent 600-item evaluation set exists, and the fuzzy
   layer's incremental recall/false-alert numbers on that set should be reported before relying on it for
   anything beyond the current audit-only tagging.
3. The vocabulary is Hinglish-only, drawn from `crisis_pattern`/`detector_class_alone==crisis` CSV rows as
   of 2026-11-25; if that CSV changes materially, this list needs regenerating by hand (it is not read from
   the CSV at runtime, by design, to avoid a file dependency).

## Owner question still open
SYNTHESIS.md section 7, Q2: confirm shipping now, understanding the counsellor-visible `fuzzy` tag and the
pending native-speaker vocabulary review.
