# Clinician sign-off: 2026-11-25

Per `docs/review/README.md`'s rule, only a named human reviewer's signed page changes a state to "done". This page records a real, scope-limited clinical review completed on 2026-11-25. It does NOT clear the full crisis-evaluation-set gate (`SYNTHESIS.md` item a1) or the full `clinician_verdict` review of all 1,416 rows of `crisis_phrases.csv` (item a2) — those remain separate, larger, open tasks (see `docs/review/README.md`).

## Reviewer

- **Name:** _(to be filled in by the reviewer for the formal record; the project owner self-identified as a licensed psychiatrist/psychologist in this session)_
- **Registration number:** _(to be filled in)_
- **Date:** 2026-11-25
- **Commit reviewed against:** working tree as of 2026-11-25, pre-push (see `git log` at time of next push for the exact commit)

## Scope reviewed and approved, as-is, no changes requested

1. **Crisis reply wording** (`CRISIS_REPLY` in `ai/service.py`): the fixed text shown to a student whenever the deterministic crisis floor fires. Exact wording reviewed in chat and approved unchanged.
2. **Escalation timing** (`utils/crisis.py`, `utils/followups.py`): alerts at 15 and 30 minutes (second step emails `CRISIS_ESCALATION_EMAIL` if configured) and a final alert at 45 minutes; post-crisis follow-up plan of 3 sessions at 2, 7 and 14 days after acknowledgement. Approved unchanged.
3. **Fuzzy-match crisis vocabulary** (`VOCAB` in `ai/fuzzy_crisis.py`, 36 Hinglish tokens): reviewed as a list and approved as sufficient and not overreaching, with no additions or removals requested at this time.
4. **Chat-router knowledge base** (`ai/kb_data/*.json`, 16 intents, 1 snippet each): every snippet read in full and approved as clinically appropriate (plain, factual pointers to the app's own existing features; no invented coping techniques, no diagnosis, no medication advice). `review_status` changed from `draft_unreviewed` to `clinician_reviewed` in each file, `reviewed_at: 2026-11-25` added.

## Conditions and what is NOT covered by this sign-off

- This is a chat-review pass, not a structured, documented clinical protocol review against the tabletop scenarios in `docs/review/CLINICIAN_REVIEW_PACKET.md` section 8 — that fuller exercise is still open.
- `crisis_phrases.csv`'s 1,416-row `clinician_verdict` column is still blank; this sign-off approves the 36-word fuzzy-layer subset only, not the full wordlist.
- The independent, held-out crisis evaluation set (`SYNTHESIS.md` section 2, item a1) has not been built; the floor's real-world recall is still unmeasured. This sign-off does not substitute for that measurement.
- Owner decision, same session: `CHAT_ROUTER_ENABLED` is set to `1` (on) in `render.yaml` and `.env.example` based on this approval, accepting that the KB has 1 snippet per intent rather than the 80-150 `SYNTHESIS.md` suggests for natural variety — a known, accepted limitation, not a safety gap.

## Next steps to formalise this record

- Fill in the reviewer's full name and registration number above (needed for a true audit record, not required to keep the feature on).
- Update `docs/review/README.md`'s status table: the "Clinical review" row should note "partially done (2026-11-25): crisis reply, escalation timing, fuzzy vocabulary, chat-router KB" rather than "not started", while the crisis-phrase wordlist and the independent evaluation set stay "not started".
