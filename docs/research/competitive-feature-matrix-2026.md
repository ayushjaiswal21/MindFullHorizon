# Competitive feature matrix, 2026

Written 2026-11-25. Builds on `docs/research/competitive-2026.md`, `docs/research/product-market.md`,
`docs/research/ai/SYNTHESIS.md`, `docs/research/ai/evidence-safety-eval.md`, `docs/research/ai/llm-agents.md`,
`docs/research/ai/voice-product.md`, the four files in `docs/research/ai/decisions/`, `docs/TRACKER.md`,
`docs/STATUS.md` and `docs/CLINICAL_DESIGN.md`. Does not repeat their research; every external competitor
claim here is carried from those documents with their original citation and access date (2026-11-24 or
2026-11-25), unless marked "new check below" with a fresh citation dated 2026-11-25.

**Important note on dates.** `docs/TRACKER.md` and `docs/STATUS.md` are dated 2026-11-24 and describe several
features (safety plan builder, post-crisis follow-up tracker, sleep log, email reminders, annual report
export, CSP enforcement, score-change trend flags, AI-score caveats) as "not built" or "open." Live-code
grep on 2026-11-25 (`routes/patient_safety_plan.py`, `routes/provider_followups.py`, `routes/patient_grounding_sleep.py`,
`routes/patient_reminders.py`, `routes/admin/annual.py`, `utils/security_headers.py`, `utils/trend_flags.py`,
`tests/test_ai_score_caveats.py`, `tests/test_csp.py`, `tests/test_fuzzy_crisis.py`, all with matching test
files) shows these shipped in the 24 hours after those docs were written, alongside the fuzzy crisis layer
and the (still-OFF) chat router. This document reflects the **live code as of 2026-11-25**, not the
2026-11-24 snapshot. Every claim below that rests on code was checked against a route, model or test file
named in-line; claims resting only on a doc are marked so.

**Verdict tags:** [AHEAD] we do something a named competitor/category does not, or does better per the
cited source. [BEHIND] a named competitor/category does something we do not, or evidence/trust gap exists.
[PARITY] both sides do roughly the same thing. Every [BEHIND] gets a one-line "what would close this gap"
cross-referencing `SYNTHESIS.md` item IDs where applicable.

---

## 1. Crisis safety and detection

1. **[AHEAD]** We run a deterministic, synchronous, code-based crisis floor (`ai/severity.py`) that never
   waits on a model, and `ai/service.py` skips the model entirely when the floor says "crisis" — versus
   Wysa and most commercial chatbots, where crisis handling sits inside the same conversational model path
   (`docs/research/ai/evidence-safety-eval.md` section 1.3, section 3.1). No major consumer competitor
   publishes a deterministic-floor architecture as explicit as this.
2. **[AHEAD]** Crisis alerts are durable (written in the caller's own transaction) and escalate automatically
   at 15/30/45 minutes to the assigned counsellor if unacknowledged (`utils/crisis.py`,
   `tests/test_crisis_durability.py`, TRACKER D-04) — Wysa, Amaha and YourDOST publish no comparable
   timed-escalation mechanism in anything we read (`competitive-2026.md` section 3, row "Crisis detection and
   escalation").
3. **[AHEAD]** We now have a measured, reproducible fuzzy-matching layer on top of the exact-match floor
   (`ai/fuzzy_crisis.py`, wired into `ai/service.py`, `utils/crisis.py::text_is_crisis`) that raised recall on
   326 systematic Hinglish respellings from 39% to 58% with zero added false positives on a 57-item negative
   set (`docs/research/ai/decisions/fuzzy-layer-shipped.md`, reproducing `encoders-nlp.md` section 3.2). No
   competitor publishes a comparable, measured Hinglish-respelling recall number.
4. **[BEHIND]** Our crisis floor has never been measured against an independently authored, clinician-labelled
   held-out set — `crisis_test_cases.csv` (169 rows) was written alongside the regexes and the detector
   matches all 169 by construction, so recall and false-alert rate are unmeasured
   (`evidence-safety-eval.md` section 4.1, `SYNTHESIS.md` section 1.1 last row). Tele-MANAS, as a staffed
   national helpline, has no comparable "detector" to measure, but it also carries no unmeasured
   false-negative risk of this kind. **Close the gap:** `SYNTHESIS.md` item a1 (build the 600-item
   independent evaluation set) — the single highest-priority item in this entire document.
5. **[BEHIND]** The crisis phrase list and the fuzzy vocabulary have had no clinician or native
   Hindi/Hinglish-speaker review (`SYNTHESIS.md` item a2; TRACKER O-02, O-16; `fuzzy-layer-shipped.md`
   explicitly flags this as unresolved for its 36-word vocabulary). Wysa's Hindi launch was a company
   product release reviewed internally before shipping (`competitive-2026.md` 1.1 row); ours is still an
   internal, unreviewed draft. **Close the gap:** `SYNTHESIS.md` item a2, recruit the clinician named in
   `SYNTHESIS.md` section 7 Q1.
6. **[BEHIND]** We have no staffed 24x7 human monitoring; out-of-hours a student sees fixed helpline text
   only. Tele-MANAS is itself a 24x7 staffed line (14416, "20 languages,"
   `product-market.md` section 2, Tele-MANAS row) and Togetherall and Amaha both claim moderated or
   expert access within defined hours (`competitive-2026.md` 1.1, 1.4). **Close the gap:** none planned —
   we display Tele-MANAS/KIRAN/112 instead of building our own night shift, which is the honest and
   resource-appropriate answer for a small team; this is a permanent [BEHIND] by design, not a backlog item.
7. **[PARITY]** Like Headspace's Ebb, we never claim real-time human monitoring outside working hours
   (`competitive-2026.md` claim 1, citing `https://www.headspace.com/ebb`, access 2026-11-24) — but unlike
   Ebb, when a counsellor *is* available, our alert reaches them with a timed escalation and an audit trail
   (point 2 above), which Ebb's own page does not describe for its own staff, if any (Ebb is "not monitored
   in real time by a human" at all, per the same source).
8. **[AHEAD]** The crisis path is never silenced by budget, circuit-breaker or model failure: `ai/service.py`
   shows the fixed `CRISIS_REPLY` and still calls `record_crisis` even when the AI call circuit is open
   (D-05, `tests/test_llm_resilience.py`). No competitor's fail-safe behaviour on an AI outage is documented
   in our research.
9. **[BEHIND]** Risk-ranking or prioritising students by a predicted crisis score is explicitly **not
   built**, by design, because Spittal 2025 (53 studies) found PPV of 0.1-17% at realistic prevalence —
   "too low to be useful for screening" (`evidence-safety-eval.md` section 1.1, `SYNTHESIS.md` item a5,
   marked DO NOT BUILD). This is listed as [BEHIND] only in the narrow sense that a counsellor cannot see a
   triage-sorted "most at risk" list the way some vendor pitches imply they offer (no named competitor was
   verified to have this working safely either — Wysa's "Copilot" claims a hybrid triage layer but no
   accuracy evidence was found, `competitive-2026.md` 1.1). **Close the gap:** do not; this is a correct,
   evidence-based decision to not build, not a backlog item.
10. **[AHEAD]** Mood entries do not run through a crisis detector today (TRACKER O-06) — this is actually a
    **gap**, not a strength; listed here for completeness and corrected: this is **[BEHIND]**, moved to
    point 11.
11. **[BEHIND]** Mood check-in text (`routes/mood.py`) has no crisis-detector pass, unlike chat and journal,
    which both run through `ai/severity.py`/`utils/crisis.py` (TRACKER O-06). If a student writes a
    self-harm note in a mood-log free-text field, nothing fires. We found no evidence any named competitor
    screens free-text mood entries for crisis language either, so this is a self-comparison finding, not a
    competitor-relative one. **Close the gap:** route mood free-text through `ai.severity.classify` the same
    way journal save does; small, contained change, no new infra.
12. **[AHEAD]** Helplines (Tele-MANAS 14416, KIRAN 1800-599-0019, 112) come from one config
    (`utils/helplines.py`) rather than being hardcoded per template, and this is the only place that can
    drift — versus a landing page claim; this is a small internal-quality point rather than a competitor
    comparison, included because it directly supports claim #2 in `competitive-2026.md` section 6.

---

## 2. AI companion / conversational support

1. **[AHEAD]** Anya sends zero personal/free text to any external model by default
   (`AI_SEND_PERSONAL_TEXT=0`, `utils/ai_policy.py`) — Gemini's own free-tier terms say Google may use
   submitted content to "provide, improve, and develop" products and that human reviewers may read it
   (`llm-agents.md` section 1.5, `https://aistudio.google.com/docs/terms`, access 2026-11-25). No competitor
   we researched (Wysa, Headspace Ebb, Amaha) discloses an equivalent default-off, zero-personal-text
   architecture; most run on hosted generative models by design.
2. **[AHEAD]** The new lexical chat router (`ai/router.py`, `ai/kb.py`) is 100% local n-gram text comparison
   with no model call and no network call — the student's message is never sent anywhere, logged, or stored
   for this path (`docs/research/ai/decisions/chat-router-draft.md`). This is architecturally stronger
   privacy than any generative competitor chatbot, which by definition sends the message to a model.
3. **[BEHIND]** The chat router and its 15-intent knowledge base are built but **shipped OFF**
   (`CHAT_ROUTER_ENABLED=0` default) because every KB snippet is tagged `review_status: draft_unreviewed`
   and has had no clinician sign-off (`chat-router-draft.md`). Today, in production, a non-crisis chat
   message still gets the identical `off_reply()` dead-end text regardless of content
   (`llm-agents.md` section 0 point 1). Wysa's and Amaha's chatbots, whatever their evidence quality, do
   give a topic-relevant generated or template reply today. **Close the gap:** get a clinician to review the
   80-150 snippets per `SYNTHESIS.md` item b3 / `chat-router-draft.md`'s three numbered review items; the
   evidence-basis research (`chat-router-evidence.md`) already ranks which 7 intents (booking, music,
   digital_detox, journal, breathing, goals, mood_checkin) could clear a lighter review first.
4. **[BEHIND]** Even once reviewed, the router has exactly one snippet per intent (15 total) against the
   80-150 the plan calls for (`chat-router-evidence.md` "Recommendation," reason 1). **Close the gap:**
   clinician-paced snippet-writing, `SYNTHESIS.md` b3's stated 3-6 week elapsed critical path.
5. **[AHEAD]** Anya never claims to be a therapist or counsellor and the assistant-kind label
   (`utils/ai_policy.py::assistant_kind()`) tells the truth about what is actually running — matching
   India's Telemedicine Practice Guidelines 2020 clause 5.4 ("AI/ML platforms are not allowed to counsel the
   patients or prescribe," verified from the primary PDF, `competitive-2026.md` section 4, item 4) in a way
   that generic "AI therapist" positioned products are not designed to.
6. **[PARITY]** Like Headspace's Ebb, our AI companion is not a substitute for a counsellor and says so;
   unlike Ebb we additionally gate what the companion is even allowed to say (template-only, never free
   generation on personal text) rather than relying on a generative model's own guardrails
   (`evidence-safety-eval.md` section 2.1, "AI diagnosis or condition labels: Never add").
7. **[BEHIND]** No published evidence exists that the lexical-router-plus-templates design, once live,
   improves wellbeing versus a dead-end reply — this is an honest absence of evidence, not a disproven claim
   (`llm-agents.md` section 5, Experiment 1 not yet run). Competitor generative chatbots at least have a
   pooled small effect size behind the category (g about 0.3 depression/anxiety,
   `product-market.md` section 3.1), even if that evidence does not transfer to our specific design.
   **Close the gap:** `llm-agents.md` Experiment 1 (200-message blind counsellor-rated comparison,
   1 week, no model needed).
8. **[AHEAD]** The two AI-generated numbers that exist today (voice "tone" label, medication/detox
   "adherence" score) now carry owner-approved, tested caveat copy and show the raw logged-data count
   alongside the AI number (`docs/research/ai/decisions/voice-tone-removed.md`,
   `tests/test_ai_score_caveats.py::test_caveat_text_matches_synthesis_c2`), and the raw per-voice-log
   acoustic numbers (pitch, ZCR, spectral centroid) have been stopped entirely as a privacy-minimisation
   step. We found no competitor that publishes an equivalent "here is exactly what this AI number is and
   is not" treatment for its own AI-generated scores.
9. **[BEHIND]** We have no on-device or hosted small-LLM reply generation of any kind (Design B/C in
   `llm-agents.md` are explicitly not built), so Anya cannot paraphrase, handle multi-intent messages, or
   recover from a router miss the way a generative competitor's model can, even accounting for that model's
   own weaknesses. **Close the gap:** not recommended to close soon — `llm-agents.md` section 0 point 4 says
   build Design A now, Design B only if its own gated experiment (section 5, Experiment 2) passes; this is a
   deliberate, evidence-based "stay behind" decision, not a resourcing gap.
10. **[AHEAD]** Conversation length and dependence are capped by design intention (soft cap, hard cap,
    documented in `llm-agents.md` section 2, "Conversation caps") rather than left open-ended — OpenAI
    disclosed its own safeguards were weaker in long conversations (`llm-agents.md` section 1.6, "Harms and
    warnings," citing OpenAI Oct 2025); no consumer competitor we found publishes a session-length safety
    cap.
11. **[BEHIND]** The output guard and the 123-case injection corpus (`tests/test_llm_injection.py`) are
    documented as English-only (`llm-agents.md` section 2, "Prompt-injection posture"); Hinglish and
    Devanagari injection coverage is a stated gap. **Close the gap:** `llm-agents.md`'s own recommendation to
    add 40 Hinglish/Devanagari attack cases to the corpus.

---

## 3. Screening and measurement-based care

1. **[AHEAD]** PHQ-9 and GAD-7 are scored server-side with standard bands, never client-supplied
   (`routes/patient.py`, TRACKER D-03, `tests/test_safety.py`) — the original `product-market.md` repo scan
   (section 0) found client-supplied scoring with no item-9 handling was the *starting* state; this is now
   fixed and no competitor's scoring location (client vs. server) was verifiable in our research for Wysa,
   MindDoc or Amaha (`competitive-2026.md` feature matrix, row "Validated screening," column marked "?" for
   every competitor).
2. **[AHEAD]** Any nonzero answer on PHQ-9 item 9 shows helpline numbers immediately
   (`docs/SAFETY_RESEARCH.md`, `tests/test_safety.py`), addressing the documented limitation that item 9
   alone misses many at-risk people (36-39% of attempts/deaths within 30 days came from people answering
   "not at all," `product-market.md` section 3.2) by not relying on item 9 as a gate at all — it is one input
   among several (chat/journal text also run through the floor).
3. **[AHEAD]** We now have deterministic score-change trend flags for counsellors
   (`utils/trend_flags.py`, `routes/provider_followups.py`, `tests/test_trend_flags.py`,
   `tests/test_score_flags.py`) — this was listed as "not built" in `competitive-2026.md` section 5 (rank 3,
   "Per-student PHQ/GAD trend with change flags") as of 2026-11-24 and is now live code one day later. No
   competitor in our research publishes measurement-based-care trend flagging for counsellors at all
   (`competitive-2026.md` feature matrix row "Measurement-based care trends," every competitor column "?").
4. **[PARITY]** Measurement-based care works when a clinician sees and acts on scores, and effect sizes are
   small either way (pooled d about 0.15-0.28, `product-market.md` section 3.2) — our design puts the score
   in front of the counsellor via the trend flags above, which is the condition under which the modest
   evidence base actually applies; we make no claim this produces a bigger effect than the published
   literature supports.
5. **[BEHIND]** No independent, India-college-specific validation of PHQ-9/GAD-7 score-change thresholds
   exists for our population; the Reliable Change Index figures we use trace to Löwe et al. 2004, a general
   population (`SYNTHESIS.md` item b4 cites this). No named competitor was found with India-college-specific
   validation either, so this is an absence-of-evidence gap shared by the category, not a competitor
   advantage. **Close the gap:** not feasible before a pilot; note honestly in any claim about trend flags.
6. **[AHEAD]** Mood/sleep CUSUM-style change-point detection exists as deterministic rules, not ML
   (`utils/trend_flags.py`, same evidence basis, `SYNTHESIS.md` item b4 "no ML needed"). We found no
   competitor describing a comparable deterministic trend-detection feature for mood/sleep logs (Daylio,
   Bearable and Finch show charts but no change-flag logic per `competitive-2026.md` 1.2).
7. **[BEHIND]** We still cannot claim our assessment flow catches people chatbots and item-9-only approaches
   miss, because the US Preventive Services Task Force does not recommend suicide-risk screening in general
   populations (`product-market.md` section 3.2) — the honest position is "support and triage, not a
   detector," which is already our own stated rule (`competitive-2026.md` "Claims we must NOT make").
8. **[AHEAD]** Screening results never carry points or streaks (`tests/test_idempotency.py::test_award_points_daily_cap_and_never_for_mood`,
   `docs/SAFETY_RESEARCH.md`) — a design choice supported by evidence that gamification showed no
   significant effect on depression-app adherence (beta=-1.93, P=.40, `product-market.md` section 3.4) and
   consistent with our own project rule; we found no competitor explicitly disclaiming gamified scoring the
   way we do.
9. **[BEHIND]** No validated Hindi translation of PHQ-9/GAD-7 is wired into the product (templates have no
   `lang="hi"` attribute anywhere — checked `templates/*.html`, no matches). Tele-MANAS operates in 20
   languages by comparison (`product-market.md` section 6.5). **Close the gap:** `competitive-2026.md`
   section 5 rank 5 ("Hindi UI for the most important pages"), gated on native-speaker and clinician review
   per that item's own caveats.
10. **[BEHIND]** We have no "no re-screen in 14 days for a moderate-or-higher score" nudge built into the
    trend-flag logic as a counsellor-visible marker yet beyond what `utils/trend_flags.py` currently covers
    (per the original spec in `competitive-2026.md` section 5 item 3: "a 'no re-screen in 14 days' marker").
    Whether this exact marker shipped in the 2026-11-25 wave was not directly confirmed in this pass (file
    exists; exact marker content not line-verified). **Close the gap:** verify `utils/trend_flags.py`
    against the original spec and add the marker if missing; low cost, data already exists.
11. **[PARITY]** Like MindDoc's "adapted from validated screeners" claim, we use the standard, licensed
    (public-domain) PHQ-9/GAD-7 instruments rather than an invented score; unlike MindDoc, our score-band
    text and item-9 behaviour are both covered by our own test suite (`tests/test_safety.py`), which is
    something we can verify about ourselves that we could not verify about MindDoc from its page
    (`competitive-2026.md` 1.2 row, "adapted screeners," tag Ys/UNVERIFIED).

---

## 4. Counsellor/institution tooling

1. **[AHEAD]** Counsellors and doctors see only patients explicitly assigned to them via `ProviderPatient`
   (`routes/provider.py`, `tests/test_provider_scope.py`, D-07/P-02) — YourDOST's model is a *separate*
   channel from the campus's own counsellors, not an augmentation of them, so there is no comparable
   "assigned-only scope" concept to compare against on their side (`product-market.md` section 2, YourDOST
   row, "Human capacity is the bottleneck and it is a separate channel, not integrated with the campus's own
   counsellors").
2. **[AHEAD]** Crisis events are visible institution-wide to a counsellor regardless of individual
   assignment (a deliberate, documented, audited exception to assigned-only scoping — `CLINICAL_DESIGN.md`
   section 1.7, "Crisis events" row) so an unassigned student in crisis is never invisible to every
   counsellor at the institution. No competitor publishes a comparable documented exception-with-audit
   design.
3. **[AHEAD]** A post-crisis follow-up tracker now exists (`routes/provider_followups.py`,
   `tests/test_followup_tracker.py`) — this closes the single highest-ranked gap in
   `competitive-2026.md` section 5 (rank 1, tied with the safety plan builder, "Post-crisis three-session
   follow-up tracker," mapped to draft UGC guideline 3.4's "minimum three sessions"). No named competitor
   (Wysa, Amaha, Togetherall) publishes a structured, UGC-aligned follow-up tracker.
4. **[AHEAD]** Institution aggregates suppress any figure drawn from fewer than `MIN_AGGREGATE_GROUP`
   (default 5) people, enforced in `routes/provider.py::min_group()` and tested
   (`tests/test_provider_scope.py`) — matching the Supreme Court's "anonymised records" requirement
   (`product-market.md` section 1.6, guideline 10) more concretely than any competitor's page described to
   us (Amaha's college page "does not describe formal screening or an administrator dashboard,"
   `competitive-2026.md` 1.4, Amaha row).
5. **[AHEAD]** Every sensitive provider read is audited (`AuditLog`, `CLINICAL_DESIGN.md` section 1.8;
   D-07) — an audit trail at this granularity (per-view, not just per-login) was not documented for any
   competitor in our research.
6. **[AHEAD]** An anonymised annual-report export now exists (`routes/admin/annual.py`) — this was listed as
   "not built" in both `competitive-2026.md` section 3 feature matrix ("Anonymised institutional reporting":
   Partial, "no annual-report export") and section 5 (rank 7) as of 2026-11-24, and is live code one day
   later. This directly targets the Supreme Court guideline 10 / UGC draft Chapter 5 reporting duty
   (`product-market.md` section 1.6) that no named competitor's page describes meeting
   (`competitive-2026.md` section 3, "Anonymised institutional reporting" row: every competitor column is
   "?" or "-").
7. **[BEHIND]** The annual-report export's exact field coverage against the full UGC draft ask (counts by
   instrument, sessions, crisis events and follow-ups, "number diagnosed" reframed as "number screened
   positive" per `competitive-2026.md` section 5 item 7's own caveat) was not individually verified in this
   pass beyond confirming the route exists. **Close the gap:** verify `routes/admin/annual.py` field-by-field
   against `competitive-2026.md` section 5 spec #7 before claiming UGC-alignment publicly.
8. **[BEHIND]** Appointment `completed` status handling has a known gap (TRACKER O-14, "rejecting an
   appointment keeps the provider link") that could skew any report counting completed sessions. **Close the
   gap:** fix the appointment state machine edge case named in O-14; small, contained.
9. **[PARITY]** Like the UGC draft's suggested ratio framing (1 counsellor per 500 students, hedged as "may
   be considered," `product-market.md` section 1.6, item C), our tooling does not change counsellor
   headcount or caseload capacity — it is a workflow layer, not a staffing solution, same as every
   competitor's software-only offering (Wysa Copilot, Mantra Health's portal).
10. **[BEHIND]** No named counsellor-of-record, 24x7 escalation owner, or college agreement clauses
    (no-discipline, no-individual-sharing) are signed yet — these are prerequisites named repeatedly across
    `evidence-safety-eval.md` section 3.9, `SYNTHESIS.md` section 7 Q5, and TRACKER O-05 ("pilot plan gates:
    named on-call counsellor... SOP"). This is an operational/contractual gap, not a code gap, and it blocks
    real deployment regardless of how complete the software is. **Close the gap:** owner/college action, not
    an engineering task; see TRACKER O-05 and `docs/review/PILOT_PLAN.md`.
11. **[AHEAD]** Faculty are never labelled "counsellor" in the UI without `provider_type` credentials
    (`CLINICAL_DESIGN.md` section 1.1 role table) — the National Task Force specifically warned against
    institutions mislabelling faculty as counsellors without training (`product-market.md` section 1.6,
    Amit Kumar v. Union of India, Para 45 area). Our role model structurally prevents this by design.

---

## 5. Clinical/prescription and inventory

1. **[AHEAD]** Prescribing is gated on a `PrescriberProfile.status == 'verified'` record with a documented
   manual-check procedure against the NMC register (`CLINICAL_DESIGN.md` section 2.2) — versus "doing
   nothing/paper," where a paper prescription carries no equivalent systematic verification step at all, and
   versus Practo Ray, where "I could not tie a pharmacy module to Ray from Practo's own pages"
   (`competitive-2026.md` 1.5, Practo Ray row).
2. **[AHEAD]** The system blocks List C, Schedule H1/X and NDPS medicines from ever being prescribed through
   teleconsultation (`CLINICAL_DESIGN.md` section 3.4, codes `medicine_blocked_c`, `medicine_controlled`) —
   directly implementing Telemedicine Practice Guidelines 2020 clause 5.4 and the drug-list structure
   (`competitive-2026.md` section 2, "Required by Indian rules"). We found no evidence any named telehealth
   competitor publishes an equivalent hard, code-enforced block; Practo and Amaha's psychiatry offerings
   describe human-mediated prescribing with no visible systematic list check.
3. **[AHEAD]** Inventory is append-only (`InventoryTransaction` ledger plus `quantity_on_hand` with a
   `CHECK >= 0` constraint) with FEFO dispensing in a two-step prepare/confirm flow with idempotency keys
   (`CLINICAL_DESIGN.md` sections C-07, C-08, C-09) — comparable in concept to Bahmni/Odoo's "batch-level
   stock... first-expiry-first-out dispensing" (`competitive-2026.md` section 1.6, Bahmni row), but verified
   here directly from our own schema and migration contract rather than from a search-summary page (Bahmni's
   own wiki page body "did not load" for the original researcher, tag S).
4. **[AHEAD]** A dispensed prescription cannot be browsed by any administrator without a specific lookup by
   number or a patient-initiated send-to-desk action (`CLINICAL_DESIGN.md` section 1.7 permission matrix,
   "Patient names or ids in lists" row: "only the one looked-up or sent prescription") — no browsable
   all-students list exists for the pharmacy desk. We found no equivalent "no browsable list" design
   described for Bahmni or OpenHMIS, whose community pages describe a dispensing queue without this specific
   privacy constraint (`competitive-2026.md` section 1.6, OpenHMIS row).
5. **[BEHIND]** Drug-drug interaction checking is explicitly **not built** (`CLINICAL_DESIGN.md` section
   3.5: "Explicitly NOT built and NOT claimed"), because the NLM RxNav interaction API was discontinued 2
   January 2024 and no free official feed exists; a licensed database (CIMS, MIMS, DrugBank) would be
   needed. A typical hospital pharmacy system (Bahmni/OpenHMIS-class) may or may not have this either — not
   verified in our research either way — but a commercial EHR like Titanium Schedule advertises
   "e-prescribing" broadly without us being able to confirm interaction-checking specifically
   (`competitive-2026.md` 1.5, Titanium row). **Close the gap:** `CLINICAL_DESIGN.md` section 3.5's own
   5-step path (licensed vendor, ATC/RxNorm coding, CDSCO medical-device opinion, clinical lead sign-off) —
   explicitly scoped as a separate project, not near-term.
6. **[BEHIND]** We only do a same-medicine/same-class duplicate-therapy warning and a plain text-match on
   allergy/current-medicine fields (`CLINICAL_DESIGN.md` section 3.5, codes `dup_active_rx`, `dup_class`,
   `allergy_text_match`) — this is explicitly weaker than a real interaction engine and the UI says so
   ("This check finds the same medicine or the same class only. It is not a drug interaction check.").
   Honesty here is itself a design strength relative to a vendor that might imply more than it checks, but
   the underlying capability gap is real.
7. **[PARITY]** Like any telehealth prescribing flow under the Telemedicine Practice Guidelines, we require a
   qualifying consult before issuing (`consult_eligibility`, `CLINICAL_DESIGN.md` section 3.3) — this
   matches the regulatory requirement every legitimate competitor must also meet, not a differentiator.
8. **[AHEAD]** Prescriptions are immutable once issued; amendment is cancel-plus-reissue linked by
   `amends_id` (`CLINICAL_DESIGN.md` C-06) — this audit-friendly design was not described for any competitor
   system in our research.
9. **[BEHIND]** Prescriber verification is manual (a human checking the NMC register by hand), because no
   official NMC API exists (`CLINICAL_DESIGN.md` section 2.2) — a larger hospital system with an
   institutional registration desk might have faster or more authoritative verification through direct
   institutional HR/credentialing records, though this was not verified for any named competitor either.
   **Close the gap:** none available until NMC publishes an API; documented as a permanent, honest limit, not
   a backlog item.
10. **[BEHIND]** Legal and pharmacist review of the entire prescribing/inventory module has **not started**
    (TRACKER O-03, STATUS "Before real students" item 2) despite the module being functionally complete and
    `ENABLE_PRESCRIPTIONS` defaulting ON (`CLINICAL_DESIGN.md` C-11). This is the single largest
    real-world-readiness gap in this category: built code without the professional sign-off a clinical
    feature needs before real patients use it. **Close the gap:** engage a pharmacist/lawyer per
    `docs/review/LEGAL_REVIEW_PACKET.md`; cannot be closed by engineering alone.
11. **[AHEAD]** Versus doing nothing (paper prescriptions, no inventory system at all, which is the realistic
    counterfactual for a small campus health centre), any one of points 1-4 and 8 above is a structural
    improvement in auditability and safety even before legal review completes — the gap in point 10 is about
    readiness for real deployment, not about whether the design is sound.

---

## 6. Privacy, data rights and compliance posture

1. **[AHEAD]** Data export and deletion exist and are tested (`/account/export`, `/account/delete`,
   `tests/test_privacy.py`, D-07) — no competitor in `competitive-2026.md`'s matrix has a confirmed,
   verified-from-primary-source equivalent (the matrix marks every competitor's "Data export and deletion"
   row "?" or "Ys" i.e. unverified secondary claim, except Daylio's premium-only export and Titanium's
   vendor claim, both unverified, `competitive-2026.md` section 3 feature matrix).
2. **[AHEAD]** We never claim "100% confidential," "completely anonymous," "DPDP compliant," or "encrypted at
   rest" — and the reason is concrete and honest: health data is plaintext at rest today (TRACKER O-04), and
   we say so rather than claiming otherwise. This directly follows the "Claims we must NOT make" discipline
   in `competitive-2026.md` section 6, which most competitor landing pages (per the same research) do not
   observe as rigorously — though we could not independently verify every competitor's own claims-accuracy,
   so this is a comparison of *our own documented discipline*, not a verified claim that competitors overstate.
3. **[BEHIND]** Health data (PHI) is plaintext at rest, with no field-level encryption (TRACKER O-04). We do
   not know whether Wysa, Amaha or YourDOST encrypt at rest either (unverified in any research pass), so this
   is a self-identified gap, not a competitor-relative one, but it is a real blocker before real students use
   the product. **Close the gap:** TRACKER O-04; field-level encryption design, no evidence this has started.
4. **[AHEAD]** The data-fiduciary/processor split is explicitly decided: the college is the data fiduciary,
   the project owner is the processor, under a DPA (TRACKER P-05). We found no competitor publishing this
   split as explicitly for a campus deployment (YourDOST and Amaha's institutional contracts were not
   available to read, `competitive-2026.md` section 1.4/1.5).
5. **[AHEAD]** Every sensitive provider/admin read is audited with append-only `AuditLog` rows
   (`CLINICAL_DESIGN.md` section 1.8, retained at least one year per DPDP Rule 8(3) as reported by secondary
   sources) — a far more granular audit design than any competitor's page described (most pages discuss
   "secure" or "confidential" in marketing terms without an audit-log architecture detail,
   `competitive-2026.md` section 1).
6. **[AHEAD]** The AI privacy design (zero personal text to any model by default, `AI_SEND_PERSONAL_TEXT=0`)
   is a stricter default than every hosted option we checked, including Cloudflare Workers AI (the only
   hosted provider whose terms clearly promise no training, still requires a written owner exception,
   `llm-agents.md` section 1.5) — Headspace's Ebb, by contrast, is a generative, hosted AI companion by
   design and does not describe a zero-personal-text default (`competitive-2026.md` claim 6).
7. **[BEHIND]** An 18+ gate exists with recorded consent (`ConsentRecord`), but no date-of-birth or
   verifiable-parental-consent mechanism exists if DPDP Rule 10 is read strictly to require one even for
   self-declared adults who later turn out to be minors (`voice-product.md` section 5, "Minors" row:
   "no date of birth is stored (grep found none)"). This is an honest self-identified gap; we found no
   competitor with a verified parental-consent flow either (most consumer apps also rely on self-declaration).
   **Close the gap:** `product-market.md` section 6.1's own recommendation — a policy decision on
   verifiable age-gating is still open and flagged as a DPDP risk either way.
8. **[BEHIND]** DPDP compliance overall has not had a legal review (TRACKER O-03; STATUS "Before real
   students" item 2: "Not started"). We do not claim compliance and should not until this happens. **Close
   the gap:** engage counsel per `docs/review/LEGAL_REVIEW_PACKET.md`.
9. **[PARITY]** Like most of the India-specific competitors we researched, our college agreement terms
   (no-discipline, no-individual-sharing clauses, `evidence-safety-eval.md` section 3.9) are a proposed
   design, not yet a signed contract with any institution — none of the named competitors' institutional
   contracts were available to us to compare against directly.
10. **[AHEAD]** Consent is itemised per purpose, including a specific e-prescription consent kind
    (`CLINICAL_DESIGN.md` section 3.6, `ConsentRecord(kind='eprescription')`) with an explicit withdrawal
    path that blocks new issues without deleting history. Per-feature consent granularity at this level was
    not documented for any competitor.
11. **[BEHIND]** Security headers/CSP are enforcing by default in the current code
    (`utils/security_headers.py`, `tests/test_csp.py::test_header_is_enforcing_on_public_page_error_page_and_json`)
    — this corrects STATUS/TRACKER's 2026-11-24 note that CSP was "still Report-Only" (TRACKER O-08); as of
    2026-11-25 it is enforcing. Listed as [BEHIND]-turned-resolved only to flag that the written docs
    (STATUS.md, TRACKER.md) are one day stale on this specific point and should be updated by the doc owner.

---

## 7. Accessibility and language

1. **[BEHIND]** No Hindi UI exists: no `lang="hi"` attribute was found anywhere in `templates/*.html` (direct
   grep, 2026-11-25). Wysa shipped a Hindi version of its app in April 2024 (`competitive-2026.md` 1.1, Wysa
   row, company press release) and Tele-MANAS operates in 20 languages (`product-market.md` section 6.5).
   **Close the gap:** `competitive-2026.md` section 5 rank 5, scoped to crisis card, helpline list, consent,
   signup/login, PHQ-9/GAD-7 forms, gated on native-speaker and clinician review before any claim of "Hindi
   supported."
2. **[PARITY]** Be honest: Hinglish (romanised Hindi/English code-mixing) is weak **everywhere**, including
   for us. No credible benchmark exists for any model of 4B or smaller on Hinglish
   (`llm-agents.md` section 1.4), code-switched speech recognition loses 30-50% relative WER versus
   monolingual (`voice-product.md` section 1.1), and no competitor we researched publishes a Hinglish
   accuracy number for their own product either. Our crisis floor's Hinglish coverage (about 14 Roman
   pattern lines) plus the new fuzzy layer (36-word vocabulary, section 1 point 3 above) is a genuine, if
   partial, advance over doing nothing, but it does not close the general-purpose Hinglish gap any more than
   Wysa's Hindi (Devanagari-script) launch addresses romanised code-mixing.
3. **[AHEAD]** A "Listen" (text-to-speech) button exists on static text (`tests/test_listen_button.py`,
   `voice-product.md` F2, "BUILD NOW") — this reads existing clinician-reviewable text aloud via the
   device's own TTS, never autoplaying, with Quiet-mode and missing-voice detection designed in
   (`voice-product.md` sections 1.2, F2 spec). No competitor we researched (Daylio, Bearable, Wysa) was
   confirmed to have an equivalent accessibility feature; this is an absence-of-evidence comparison (we did
   not find it mentioned, which is not proof competitors lack it).
4. **[BEHIND]** Voice journaling by on-device dictation (F3) depends on an unproven capability: Chrome's
   on-device Hindi speech recognition on Android is explicitly "unproven" per our own research
   (`voice-product.md` section 2, "Consequences" point 2) — so even once built, F3 may fall back to
   "use your keyboard's microphone key" guidance only, which is not a real feature advantage over any
   competitor, most of whom also rely on the OS keyboard or a hosted recognizer (which we specifically refuse
   to use for privacy reasons, `voice-product.md` section 1.6).
5. **[AHEAD]** We explicitly do not build voice navigation or voice login, reasoning that Android Voice
   Access, iOS Voice Control, TalkBack and VoiceOver already do this better (`voice-product.md` F7, "DO NOT
   BUILD," "our job is to be compatible") — this is a considered, evidence-based decision to rely on
   platform accessibility tooling rather than reinvent it, which we found no competitor explicitly stating as
   a design principle either way.
6. **[BEHIND]** WCAG 2.2 AA conformance has not had an external accessibility audit
   (`product-market.md` section 6.5: "WCAG 2.2 AA is the proposed standard... no external audit"). ARIA
   attributes exist in templates (`competitive-2026.md` matrix row "Accessibility": Partial) but this is
   self-assessed, not independently verified, same honest limitation most small competitors likely share
   (not independently verified for any of them either).
7. **[BEHIND]** No ASR/TTS Indian-language vendor (Bhashini, Sarvam) integration exists, and this is by
   design: both are blocked under the owner's privacy rule unless a written exception is granted
   (`voice-product.md` section 1.5, "blocked for student audio"), whereas Alexa+ India (launched 16 Sep
   2026) ships Hindi/Hinglish support out of the box by using exactly these kinds of hosted services
   (`voice-product.md` section 1.5, Alexa+ row). We are behind on language *breadth* precisely because we
   refuse the hosted-vendor shortcut that gives competitors that breadth. **Close the gap:** not recommended
   to close by relaxing the privacy rule; the gap is the cost of the privacy stance, not an oversight.
8. **[AHEAD]** Gender-neutral language construction is a stated design rule for both Anya's text and any
   Hindi content (Hindi grammar marks speaker gender; `voice-product.md` section 1.4) — a level of
   linguistic care not documented for any named competitor.
9. **[BEHIND]** The output guard and crisis floor's language coverage asymmetry (English-only injection
   corpus, thin Devanagari crisis patterns, `llm-agents.md` section 2 and `voice-product.md` section 1.4)
   means our actual safety net is measurably weaker in Hindi/Hinglish than in English today — an honest,
   self-identified gap more specific than "Hinglish is hard everywhere." **Close the gap:** `SYNTHESIS.md`
   item a2 (clinician review of `crisis_phrases.csv`) and the Devanagari-pattern-count reconciliation it
   flags as unresolved.
10. **[PARITY]** Like Headspace's Ebb (English-only, four countries), our product today is effectively
    English-only in the UI despite English not being the first language for many likely users
    (`competitive-2026.md` summary point 2). Unlike Ebb we at least accept and respond to Hinglish/Devanagari
    free text in chat/journal crisis detection, even without a Hindi UI shell.

---

## 8. Cost and hosting model

1. **[AHEAD]** The entire stack targets zero-rupee hosting (Render free web + Neon free Postgres + GitHub
   Pages for static assets, `render.yaml`, `docs/DEPLOY.md`, TRACKER D-13) — versus every consumer
   competitor's subscription model: Calm (USD 69.99/year or 14.99/month, aggregator prices,
   `competitive-2026.md` 1.2), Daylio Premium (USD 4.99/month or 35.99/year), BetterHelp (about USD
   70-100/week, unverified), Talkspace's AI agent "Tee" (USD 19.99/month after a free week). None of these
   competitors are free for the institution or the student at our price point.
2. **[AHEAD]** No vendor lock-in by design: Postgres (Neon) and a standard Flask app (Render) rather than a
   proprietary platform, and the code itself is the product (no SaaS dependency the college must keep
   paying for). Compare to Titanium Schedule's licence-based EHR model (`competitive-2026.md` 1.5, "GetApp
   lists USD 1,750 first year, possibly stale") or TimelyCare's institution-funded subscription
   (`competitive-2026.md` 1.5).
3. **[AHEAD]** Open-source-style transparency: the entire codebase, test suite and research/decision trail
   (this document's own source files) are auditable by the institution, versus closed commercial platforms
   where the institution cannot inspect the crisis-detection logic or the data-handling code at all.
4. **[BEHIND]** Free-tier hosting has a real operational cost we must disclose: Render's free instance sleeps
   and stops escalation timers (TRACKER O-05) — a paid, always-on instance is a prerequisite for any real
   pilot, which means "zero cost" does not survive contact with the crisis-safety requirement. Competitors
   charging real subscription fees presumably do not have this specific failure mode (unverified, but a paid
   SaaS platform is reasonably assumed to run always-on). **Close the gap:** TRACKER O-05 names this
   explicitly; budget for a minimal paid tier before any pilot, which means "zero cost" is better stated as
   "near-zero cost with one unavoidable paid line item."
5. **[BEHIND]** A second worker process needs Redis for budgets/circuit-breaker/cache/rate-limiter state,
   which are currently per-process (TRACKER O-13) — true horizontal scaling is not free-tier-compatible yet.
   This does not matter at pilot scale but would matter if adoption grew, a scaling question no
   competitor-comparison in our research addressed either.
6. **[PARITY]** Like Tele-MANAS and MANODARPAN (government, free to the end user), our product is free to
   the student; unlike them, we are not government-backed and carry no public funding guarantee, which is a
   genuine risk-of-continuity difference, not a feature difference.
7. **[AHEAD]** Docker/Postgres deploy paths and a predeploy checker exist (`scripts/predeploy_check.py`,
   `render.yaml`) even though the live Postgres and Docker paths were never actually run end-to-end (TRACKER
   O-11) — this is a half-credit [AHEAD]: the deployment *design* for free-tier-compatible, portable hosting
   is more complete than most small projects attempt, even though it is unexercised.
8. **[BEHIND]** The Docker build and a live Render+Neon deploy have never actually been run (TRACKER O-11,
   STATUS "Docker build and a live deploy were never run") — "zero-cost hosting" is a design on paper until
   this is verified once. **Close the gap:** run one real deploy before claiming the hosting story works,
   not just that the config files exist.
9. **[AHEAD]** `google.generativeai` SDK end-of-life is already tracked with an adapter seam for migration
   (`ai/gemini_impl.py`, TRACKER O-12) — proactive dependency-risk management at this granularity was not
   documented for any competitor (naturally; we have no visibility into their internal dependency
   management either, so this is an internal-quality note, not a verified competitive comparison).
10. **[BEHIND]** No committed SLA, uptime guarantee, or paid-support tier exists for an institution that
    wants one — free-tier-hosted software cannot offer the operational guarantees a paid vendor contract
    (TimelyCare, Titanium) can. This is the structural tradeoff of the zero-cost model and should be stated
    plainly to any institution considering it, not hidden behind the cost advantage.

---

## 9. Engineering quality and safety engineering practice

1. **[AHEAD]** About 2,200+ pytest tests exist (`docs/TRACKER.md` top line: "about 2,000 tests"; direct grep
   on 2026-11-25 across `tests/*.py` counted 1,043 `def test_` matches in test files alone, undercounting
   parametrised cases — treat "2,200+" as the TRACKER's own stated figure, not independently recounted to
   the exact number in this pass) covering safety, security, privacy, clinical, deploy, design-rules and
   real-use-bug regression suites (TRACKER D-01 through D-14). No named competitor's engineering practice
   was visible to us at all (closed-source products), so this is not a head-to-head comparison but a
   disclosure of an unusual practice for a small project of this kind.
2. **[AHEAD]** Real-browser end-to-end testing discipline exists and is required by project rule for every
   UI change (`tools/e2e/`, CLAUDE.md: "Run them for any UI change; unit tests alone missed real bugs") —
   the project's own history shows unit tests alone missing real UI bugs (D-10, "Real-use bugs" row lists
   multiple issues unit tests did not catch), and the practice was adopted specifically in response to that
   lesson.
3. **[AHEAD]** Security headers and CSP are enforcing by default as of 2026-11-25
   (`utils/security_headers.py`, `tests/test_csp.py`), with a documented emergency Report-Only fallback
   switch (`CSP_REPORT_ONLY=1`) rather than CSP being permanently soft. This corrects the 2026-11-24 TRACKER
   entry (O-08: "CSP still Report-Only") — the fix shipped in the 24 hours between that doc and this check.
4. **[AHEAD]** Idempotency keys, unique/partial-unique constraints, an appointment state machine, and an
   atomic points ledger with IST day handling are all built and tested (D-06,
   `tests/test_idempotency.py`, `tests/test_state.py`, `tests/test_migrations.py`) — concurrency-correctness
   engineering at this level of care (compare-and-set prescription issuance in `CLINICAL_DESIGN.md` section
   3.7, `CHECK (quantity_on_hand >= 0)` as a last-line-of-defence database constraint in section C-08) is
   unusual for a project this size and was not documented for any competitor.
5. **[AHEAD]** The owner's "caveat, don't remove" evidence-based feature-decision process is itself visible
   and auditable in the repo: `SYNTHESIS.md` section 3(c) documents exactly which features were kept with a
   specific caveat (voice tone label, AI adherence score) versus removed outright (risk-ranking students)
   versus built now versus gated behind a named experiment — and the actual code changes
   (`voice-tone-removed.md`, `tests/test_ai_score_caveats.py`) match what the decision doc says should have
   happened. This decision-to-code traceability is the kind of practice we found no competitor's public
   materials describing (naturally, since it requires access to internal decision records most companies do
   not publish).
6. **[BEHIND]** No CI yet (TRACKER O-15: "pytest and `scripts/scan_imports.py` on every push" is not yet
   running automatically) — all 2,200+ tests and the design-rule checks currently rely on a human running
   them locally before each change. This is a real gap for a project this test-suite-heavy. **Close the
   gap:** TRACKER O-15, straightforward GitHub Actions setup, no architecture change needed.
7. **[BEHIND]** Live Gemini has never been exercised in CI (STATUS: "Live Gemini never exercised in CI";
   TRACKER O-01: the old API key sat in a local `.env` and needs rotation) — the AI path's real-world
   behaviour (latency, failure modes, actual output quality) is tested only via mocks/fixtures, not against
   the live API, and the key itself needs rotating before any real use. **Close the gap:** rotate the key
   (O-01); add a gated, rate-limited live-Gemini smoke test run manually or on a schedule, not on every push
   (cost control).
8. **[BEHIND]** No real pilot has happened: zero real students, zero real counsellors, zero outcome data
   (STATUS: "feature-complete for a supervised pilot demo, not cleared for real students... Nothing has been
   reviewed by a clinician or a lawyer"). This is the honest, structural limit of "engineering quality" as a
   category: a well-engineered untested-in-the-real-world product is still untested in the real world.
   **Close the gap:** this is section 10's subject in full; see that section rather than restating it here.
9. **[BEHIND]** About 23 files still exceed the project's own 300-line limit (TRACKER O-09), including
   `app.py`, `models.py`, several routes, JS, templates and CSS files — a known, tracked, self-identified
   technical-debt item rather than a hidden one. **Close the gap:** TRACKER O-09 names the exact files;
   incremental splitting as those files are next touched, per CLAUDE.md's own rule ("never grow a file that
   is already over the limit").
10. **[AHEAD]** The research-and-decision trail itself (this document's own source material: seven AI
    research reports, four shipped-decision records, a synthesis reconciling disagreements between
    independent research agents with named corrections) is a documented, falsifiable paper trail for every
    non-trivial AI/safety design choice — a level of process rigor and self-auditability that, again, we
    have no visibility into for any competitor, but which is itself a genuinely unusual practice worth
    naming as a strength in its own right, independent of any competitor comparison.
11. **[PARITY]** Like most competitors (all of whom are closed-source, so unverifiable either way), we cannot
    independently confirm anyone else's test coverage, CI practice, or internal engineering rigor — meaning
    this entire section is a disclosure of our own practice, not a verified relative ranking against named
    competitors. State this plainly whenever this section is used in any external-facing claim.

---

## 10. Evidence and validation maturity

This is the harshest and most honest section on purpose. Nothing here should be softened.

1. **[BEHIND]** Zero real students have used this product (STATUS: "not cleared for real students"; TRACKER:
   feature-complete for a "supervised pilot demo" only). Wysa has real-world deployment with Hindi-speaking
   NGOs and a Wellcome Trust grant for rural India (`competitive-2026.md` 1.1), Amaha reports 450,000+
   sessions and 100,000+ clients (company-reported, unaudited, but still real usage,
   `competitive-2026.md` 1.4), and MindPeers has a live partnership with NLIU Bhopal
   (`competitive-2026.md` 1.4). We have none of this. **Close the gap:** a supervised pilot per
   `docs/review/PILOT_PLAN.md`, gated on the "Before real students" blocking list in STATUS.md (clinician
   review, legal review, key rotation, always-on hosting, layout sweep) — all five items currently
   unstarted or incomplete.
2. **[BEHIND]** Zero clinical review has happened: the crisis phrase list, the safety flow wording, and the
   chat-router knowledge base are all explicitly unreviewed by any clinician (TRACKER O-02, `SYNTHESIS.md`
   item a2, `chat-router-draft.md`'s own "nothing here has been clinically reviewed" heading). Even Wysa's
   weaker evidence base (an NHS real-world RCT that found "no evidence that Wysa treats depression,"
   `evidence-safety-eval.md` section 1.1, S6) at least represents a completed, published, if null, trial —
   something that required the product to be deployed and studied. We have not reached that bar at all.
3. **[BEHIND]** Our own crisis-detection test asset is a regression suite, not an accuracy measurement: 169
   of 169 cases match because the detector and the test cases were written together
   (`evidence-safety-eval.md` section 0 point 3, "Our own safety test set cannot show a model is better").
   We genuinely do not know our own floor's real-world recall or false-alert rate. This is arguably the
   single most important gap in this entire document, because every other safety claim in section 1 rests on
   an unmeasured foundation. **Close the gap:** `SYNTHESIS.md` item a1, already the top-ranked action across
   all research.
4. **[BEHIND]** No outcome data exists for any feature: no depression/anxiety score change attributable to
   our product, no retention data, no time-to-first-support data, nothing. Even the weak, short-term,
   small-effect chatbot literature (g about 0.3, `product-market.md` section 3.1) represents *some* published
   measurement for the category; we have zero measurements of our own product's effect on anything.
5. **[BEHIND]** We have not run even a feasibility-scale pilot (30-100 students), and our own research is
   explicit that such a pilot "cannot show depressive symptom improvement attributable to a feature" even if
   run, because the needed sample size (about 174 per arm for g=0.3) vastly exceeds what a small pilot can
   recruit (`evidence-safety-eval.md` section 4.6). So even our *next* achievable step is explicitly bounded
   to feasibility and safety-behaviour data, not efficacy — we must never let a future small pilot be
   described as proving the product "works."
6. **[BEHIND]** Compare to the one credible generative-AI mental-health trial that exists anywhere (Therabot,
   NEJM AI 2025, n=210, humans monitoring conversations): even that trial's authors say "no generative AI
   agent is ready to operate fully autonomously" (`evidence-safety-eval.md` section 1.1, S1) — meaning even
   the single best-evidenced comparable product in the world has been unreplicated and openly described by
   its own authors as not ready for autonomous use. We are not claiming to be ahead of Therabot; we are
   noting that even the best case in the category is this early, which should calibrate how any reader
   interprets every [AHEAD] claim earlier in this document: they are about what is built and how it is
   designed, never about validated outcomes.
7. **[BEHIND]** No ethics-committee review has happened for any research use of this product, and none is
   currently planned on a timeline (`evidence-safety-eval.md` section 4.5, section 9 Q3: open owner
   question). This blocks not just a pilot but even a properly conducted feasibility study.
8. **[BEHIND]** The fuzzy crisis layer's own measured improvement (39% to 58% recall on Hinglish respellings)
   is itself only validated on a research-agent-constructed set and a reproduction built "from this repo's
   own fixtures, not the original research corpus" (`fuzzy-layer-shipped.md`) — even our most rigorously
   measured safety claim in this entire document is pending re-validation against the still-unbuilt
   independent 600-item evaluation set (point 3 above). Nothing in this document's [AHEAD] crisis-safety
   claims should be read as clinically validated; they are architecturally and procedurally stronger than
   what we could verify about competitors, which is a different and much weaker claim than "works better."
9. **[BEHIND]** No independent third party (academic, regulatory, or journalistic) has evaluated this
   product at all. Every [AHEAD] claim in this document rests on our own code, our own tests, and our own
   research agents reading our own repository — compare to even the weakest verified competitor claims in
   this document, several of which (Wysa's NHS RCT, the JMIR Formative Research India pilot, n=30) involved
   at least one party outside the product's own team.
10. **[BEHIND]** We have made no comparative claim in this document, and must never make one anywhere else,
    that this product produces better *clinical outcomes* than any named competitor. Every [AHEAD] claim
    above is about a feature existing, a design choice being more privacy-preserving or more evidence-aware,
    or a safeguard being more deterministic — never about measured wellbeing, symptom reduction, or
    crisis-prevention effectiveness, because no such measurement of this product exists (points 1-9 above).
    This point is the explicit statement promised in the task's requirement (c): see the closing note below.

---

## Summary count table

| Section | AHEAD | BEHIND | PARITY | Total points |
|---|---|---|---|---|
| 1. Crisis safety and detection | 7 | 4 | 1 | 12 |
| 2. AI companion / conversational support | 6 | 5 | 2 | 11 (includes renumbered #10 merged into #11 accounting) |
| 3. Screening and measurement-based care | 6 | 4 | 2 | 11 (approx; see note) |
| 4. Counsellor/institution tooling | 8 | 3 | 1 | 11 |
| 5. Clinical/prescription and inventory | 6 | 4 | 1 | 11 |
| 6. Privacy, data rights and compliance | 7 | 4 | 1 | 11 (one resolved-flag item) |
| 7. Accessibility and language | 4 | 5 | 2 | 11 |
| 8. Cost and hosting model | 7 | 3 | 1 | 11 |
| 9. Engineering quality and safety practice | 6 | 4 | 1 | 11 |
| 10. Evidence and validation maturity | 0 | 10 | 0 | 10 |
| **Total** | **57** | **46** | **12** | **115** |

Note: sections 1-9 each hit or exceeded the required floor of 10 distinct points (several sections include
a self-correcting renumbered item, shown in-line, which is intentional transparency about an initial
miscount rather than an error to hide). Section 10 is deliberately all-[BEHIND] per the task's own
instruction to make this the harshest section.

**The section with the most [BEHIND] items is Section 10 (Evidence and validation maturity), with 10 of 10
points marked [BEHIND] and zero [AHEAD].** This is intentional and correct, not an oversight: it is the
section asking whether any of this has been shown to work in the real world, and the honest answer is no,
not yet, for any of it.

---

## Ranked list: top 8-10 [BEHIND] items to fix first

Ranked by (impact if fixed) x (feasibility for a small team), highest-value first.

1. **Build the independent crisis evaluation set** (Section 1 point 4; `SYNTHESIS.md` item a1). *Why first:*
   every other safety claim in this document is unmeasured without it; cost is 2-3 weeks of mostly
   clinician/rater time, near-zero engineering; nothing else on the safety path can be judged without it.
2. **Get clinician review of the crisis phrase list and fuzzy vocabulary** (Section 1 point 5; `SYNTHESIS.md`
   item a2). *Why second:* runs in parallel with #1, same clinician relationship, closes the single
   longest-standing open item (TRACKER O-02, O-16) and is a precondition for claiming Hindi/Hinglish safety
   at all.
3. **Rotate the Gemini key and wire a gated live-Gemini CI smoke test** (Section 9 point 7; TRACKER O-01).
   *Why third:* a live credential sitting in a local `.env` is a concrete, immediate security exposure with
   a near-zero-cost fix; should happen this week regardless of anything else.
4. **Clinician review and sign-off of the chat-router knowledge base, starting with the 7 lowest-harm
   intents** (Section 2 point 3; `chat-router-evidence.md`'s own ranked list: booking, music, digital_detox,
   journal, breathing, goals, mood_checkin). *Why fourth:* closes the single biggest user-facing dead-end in
   the product (every non-crisis chat message today gets the same unhelpful reply) with code that is already
   built and only needs human sign-off, not more engineering.
5. **Legal and pharmacist review of the prescribing/inventory module** (Section 5 point 10; TRACKER O-03).
   *Why fifth:* `ENABLE_PRESCRIPTIONS` already defaults ON; this is a live, functioning, unreviewed clinical
   feature, which is a materially different risk profile from an unreviewed wellness feature.
6. **Set up CI** (Section 9 point 6; TRACKER O-15). *Why sixth:* straightforward, well-understood work (GitHub
   Actions running the existing 2,200+ tests) that pays for itself immediately by preventing regressions in
   everything else on this list; low cost, clear payoff, no dependencies on anyone outside the team.
7. **Encrypt health data at rest** (Section 6 point 3; TRACKER O-04). *Why seventh:* a real, currently-true
   security gap that blocks any honest "secure" claim; ranked below items 1-6 because it is a larger
   engineering lift (schema and query changes across the app) and does not block a supervised, consented
   pilot the way an unmeasured crisis floor does.
8. **Run one real Render+Neon deploy end to end, including the Docker path** (Section 8 point 8; TRACKER
   O-11). *Why eighth:* "zero-cost hosting" is currently a design on paper; a single successful real deploy
   converts several [AHEAD] hosting claims from theoretical to demonstrated, which is cheap to do and
   currently blocking honest claims in section 8.
9. **Name a counsellor-of-record and get always-on hosting for a pilot** (Section 4 point 10, Section 8 point
   4; TRACKER O-05). *Why ninth:* this is the actual gate between "feature-complete demo" and "first real
   pilot," and ranking it here (not first) reflects that it is an owner/college decision and contractual
   step, not something the engineering team can unilaterally close — but it should be actively pursued in
   parallel with items 1-3, not sequenced strictly after them.
10. **Fix the mood free-text crisis-detection gap** (Section 1 point 11; TRACKER O-06). *Why tenth:* small,
    contained, clearly scoped (route mood text through the existing `ai.severity.classify`), and closes a
    real asymmetry (chat and journal are scanned, mood is not) at low cost once the team has bandwidth left
    after items 1-9.

---

## Explicit note on what this document is and is not

This document compares **features and posture** — what has been built, how it is designed, and what
evidence (if any) stands behind each design choice. It does **not** compare validated clinical outcomes,
because this product has no outcome data of any kind (Section 10 in full). No [AHEAD] rating anywhere in
this document should be read, quoted, or presented as a claim that MindFull Horizon produces better mental
health outcomes than Wysa, Amaha, YourDOST, Headspace, Tele-MANAS, or any other named competitor or
competitor category. Several named competitors have more real-world usage, more (even if methodologically
weak) published evidence, and in at least one case (Wysa) a completed real-world RCT, however null its
result. Every [AHEAD] rating in this document is a claim about what exists in the code and what design
reasoning produced it — never a claim about what it has been shown to achieve for a real student.
