# Evidence, safety and evaluation: will an AI-centric MindFull Horizon really help?

Agent: EVIDENCE-SAFETY-EVAL (the skeptic). Written 2026-11-25. All web sources accessed 2026-11-25. Not clinical or legal advice.
Marking: VERIFIED = I read the page or abstract. UNVERIFIED = seen only in a search snippet, a secondary article or a vendor claim. Numbers marked "computed" are mine (scripts run on 2026-11-25, assumptions stated).

## 0. Bottom line

1. **No evidence exists that making this product "AI-centric" improves student outcomes.** The best evidence is for narrow, scripted, CBT-style chatbots: small short-term effects (g about 0.3) against waitlist or information controls, low to very low certainty, many vendor-affiliated trials. The one generative-AI trial (Therabot, n=210, 8 weeks, no-treatment control, humans reading messages) is promising and unreplicated. Nothing studied matches our features (Hinglish crisis floor, voice logs, counsellor alerts).
2. **For counsellors the realistic gain is attention and time, not diagnosis.** The only regulator-endorsed AI pattern I found is administrative front-door triage with clinician review (NICE HTE30, Wysa DRA, a UK Class I device). Risk ranking of people from text or voice is not supported (Spittal 2025: PPV 0.1 to 17 percent at realistic prevalence).
3. **Our own safety test set cannot show a model is better.** `crisis_test_cases.csv` has 169 rows and the detector matches all 169 (`detector_matches_test = yes`), because the cases were written alongside the regexes. It is a regression suite, not an accuracy estimate. Clinician columns are blank. Until an independently authored, clinician-labelled held-out set exists, any claim "the model catches more" is unfounded.
4. **A 30 to 100 student pilot cannot show clinical benefit.** It can show feasibility, safety behaviour, alert burden, accuracy of components, and acceptability (section 4.6).
5. **Recommendation: "AI-assisted, not AI-centric".** Spend most effort on deterministic floor quality, vetted content, human workflow and measurement. Add at most three small models, each in shadow mode first, each able only to raise concern. Remove two things that exist today and fail the evidence bar (voice emotion label, LLM adherence score). Do less AI where the evidence is absent.

## 1. Evidence by use case

Strength scale: STRONG (several independent RCTs or meta-analyses with low risk of bias), MODERATE (several RCTs, effects small or certainty low), WEAK (one trial, non-randomised, vendor-run, or lab data only), ABSENT (no outcome evidence found).

### 1.1 Summary table

| Use case | Best evidence | Effect, quality | Strength for our context |
|---|---|---|---|
| Scripted or CBT chatbots, depression | Meta-analysis, 39 RCTs, Sohn 2026 [S3]; CBT-oriented, 29 RCTs [S4]; Karger review, 52 studies, 22 RCTs, 13 commercial bots [S5] | Depression g about 0.31 (CI 0.17 to 0.46) [S3]; CBT-oriented g -0.55 at end, -0.32 at follow-up [S4]. Karger: certainty low to very low; modest benefit mainly for depression [S5]. All UNVERIFIED (snippets) | MODERATE, small short-term effect, mostly vs waitlist, COI common |
| Same, anxiety | Same [S3][S4] | g about 0.28 (CI 0.05 to 0.51) [S3]; CBT-oriented g -0.26, not significant at follow-up [S4]. UNVERIFIED | WEAK |
| Persistence of effect | [S4] | Depression effect shrinks at follow-up; anxiety effect not significant. UNVERIFIED | WEAK |
| Generative AI therapy bot | Therabot RCT, Heinz 2025, NEJM AI [S1][S2] | n=210 (106 bot, 104 no access), 4 and 8 weeks. Depression symptoms -51%, anxiety -31%, eating-disorder concern -19% (VERIFIED via press page). Cohen's d 0.845 to 0.903 depression, 0.794 to 0.840 anxiety (UNVERIFIED, abstract via search; computed from log-odds, check paper). Researchers monitored conversations and stood ready to intervene [S1] | WEAK to MODERATE: one trial, no active control, humans in the loop, authors say "no generative AI agent is ready to operate fully autonomously" [S1] |
| Commercial Wysa (RCT) | Real-world RCT, NHS waitlist, 2026 [S6] | 76 randomised, 39 percent lost to follow-up, depression change identical (2.62 vs 2.59): "no evidence that Wysa treats depression" (VERIFIED) | A null result for a well-known app: reminds us that effects often vanish in real settings |
| Wysa observational | 2018 study [S7] | d 0.63 high vs low engagers, self-selected, not causal. UNVERIFIED | ABSENT as causal evidence |
| Woebot RCT in students | Fitzpatrick 2017, n=70, 2 weeks, info-ebook control [S8] | Depression fell in bot arm only (P=.01), 17 percent attrition, unblinded, authors employed by vendor. Partly VERIFIED | WEAK (tiny, short, COI). Woebot (rule-based) closed its app 2025-06-30 citing cost of FDA path [S9] |
| Journaling with AI feedback or reflection | Flourish RCT, 486 US undergraduates, 6 weeks, waitlist control [S30] | Higher positive affect, resilience, social wellbeing. Waitlist only, authors own the company. UNVERIFIED | WEAK; nothing on depression or risk outcomes in India |
| AI-generated psychoeducation | No RCT found for student outcomes | n/a | ABSENT. Static vetted text has the same plausible benefit with no model risk |
| Retrieval of vetted content | No mental-health outcome study found | n/a | ABSENT (benefit is plausible and measurable offline) |
| Suicide risk detection from text | Spittal 2025, 53 studies [S23] (VERIFIED) | Sensitivity 45 to 82 percent, specificity 91 to 95 percent, AUC 0.69 to 0.93, LR+ 6.5 to 9.9. PPV 6 to 17 percent in-sample; at LR+ 10 out-of-sample: 0.1 percent (low prevalence), 17 percent (medium), 66 percent (high). Authors: "too low to be useful for screening" | Discrimination fair; use as case-finding in a general student population: not supported |
| Same, LLM on chatbot conversations | Sonia preprint, 200 segments, 5 clinicians [S24] (VERIFIED) | Setting "High": recall 98.9 percent but false-positive rate 40.7 percent; "Extreme High": recall 100 percent, FPR 49.1 percent; clinician agreement only Fleiss kappa 0.34; single vendor-run site, not peer reviewed, high-risk oversampled (2.55 percent of all exchanges) | Shows the trade-off directly: catching nearly everything means flagging about 40 percent of benign segments. Labelling itself is unreliable |
| Crisis Text Line ML triage | Vendor blog [S25] | Claims 86 percent of severe imminent-risk texters found in first messages; 90.2 percent accuracy. UNVERIFIED, self-reported, no independent audit seen | WEAK. Note the context: every user already contacted a crisis line, so base rate is high and PPV much better than ours |
| Facebook proactive detection | STAT 2019 [S26] | Critics: opaque, proxy labels, no evidence on race or language fairness, not held to research ethics. UNVERIFIED (secondary) | ABSENT (no published outcome evaluation found) |
| Hinglish or code-mixed suicide-text models | ICON 2021 [S27] | Reported 98.54 percent accuracy on an own-built corpus. UNVERIFIED | Such in-corpus numbers do not transfer; they show why we need our own held-out set. No fairness evidence across dialects found |
| Voice markers of depression | Donaghy 2024 review, 19 ML studies [S28]; cross-lingual studies [S28] | Reported efficacy below PHQ-9; accuracy drops across corpora, languages and recording setups; tonal languages a confounder. Snippets only, PDF unreadable. UNVERIFIED | WEAK. Kintsugi, the best-funded attempt, closed Feb 2026 after FDA De Novo trouble (sources conflict on how far it got) [S28] |
| Emotion recognition from text or voice | EU AI Act recital 44 [S29] | EU bans emotion inference in workplaces and education (medical or safety exceptions) citing weak scientific basis and cultural variation. UNVERIFIED (snippet) | WEAK validity; our `classify_emotion` is a pitch/energy threshold rule with no validation |
| Voice interfaces, accessibility | OpenAI/MIT 4-week RCT, n=981 [S14] | Voice mode helped loneliness only at low use, heavy use linked to more dependence; no no-chatbot control. UNVERIFIED | ABSENT for mental-health outcomes in India. Accessibility value (low literacy, typing burden) is plausible, not measured |

### 1.2 Harms and incidents (these are the reasons for caution)

| Item | Finding | Source |
|---|---|---|
| Stanford, FAccT 2025 | Chatbots gave bridge heights to a user hinting at suicide, showed stigma, therapy bots answered appropriately under 60 percent vs 93 percent for licensed therapists; bigger models were no better. Authors see lower-stakes roles (journaling, coaching) | [S10] UNVERIFIED (news and snippets) |
| Brown, AAAI/AIES 2025 | 15 ethical risks in 5 categories, including poor crisis handling and "deceptive empathy", even when prompted with therapy techniques | [S11] UNVERIFIED |
| OpenAI own figures | About 0.15 percent of weekly users show explicit suicidal planning indicators (about 1.2 million of 800 million); new model reduced undesired self-harm answers 52 percent on its own test | [S12] UNVERIFIED (news coverage of OpenAI post) |
| Lawsuits | Character.AI and Google settled several teen-suicide suits (Jan 2026); suits against OpenAI pending as of my sources | [S13] UNVERIFIED |
| Karger review | Only 3 of 22 RCTs actively monitored and reported serious adverse events; so "no harm reported" is not "no harm" | [S5] UNVERIFIED |
| Ecological audit (2026) | Test-set failure rates for suicide and self-harm were far higher than in real deployment; argues for continuous monitoring over one-time certification | arXiv 2602.05088, UNVERIFIED (PDF unreadable, from search summary) |

Reading across: harms cluster in open-ended generative chat (stigma, method information, sycophancy, dependence). Our current design (fixed crisis replies, fixed starter answers, output guard, `AI_SEND_PERSONAL_TEXT=0`) already avoids most of them.

### 1.3 Regulators and professional bodies

| Body | Position | Source |
|---|---|---|
| APA health advisory, 2025-11-13 | Do not use chatbots or wellness apps as a substitute for a qualified professional; even tools built with good psychological science "do not have enough evidence" of effectiveness and safety; calls for RCTs and longitudinal studies, safeguards for young and vulnerable users, transparency, no impersonating licensed professionals, safe-by-default privacy | [S15] VERIFIED (press page) |
| FDA Digital Health Advisory Committee, 2025-11-06 | Over 1,200 AI-enabled devices authorised, none with generative AI for mental health; discussion stressed human oversight, reliable detection of high-acuity situations, and model drift | [S16] UNVERIFIED (law-firm summaries; FDA PDF 404) |
| WHO LMM guidance, Jan 2024 | 40+ recommendations; independent post-release audits at scale; warns outputs look authoritative but may be wrong. No mental-health-chatbot-specific WHO position found | [S17] UNVERIFIED |
| NICE HTE30, 2025-07-24 | Wysa Digital Referral Assistant (UK Class I) and Limbic Access allowed conditionally during a 3-year evidence-generation period; clinician reviews the report | [S18] UNVERIFIED |
| US states 2025 | Illinois bans AI-delivered therapy unless a licensed professional conducts it (fines reported up to USD 10,000 per violation); Nevada similar; Utah requires disclosure | [S19] UNVERIFIED |
| India: Telemedicine Practice Guidelines 2020, clause 5.4 | AI must not counsel or prescribe (owner-verified in the brief) | brief |
| India: ICMR AI ethics guidelines 2023; MeitY AI Governance Guidelines 2025-11-05 | Principle-based: transparency, accountability, bias, ethics review, informed consent; sector regulators lead enforcement | [S20] UNVERIFIED (snippets) |
| India: MHCA 2017, CDSCO, NMC, MoHFW | I found no official guidance on mental-health chatbots; commentary says MHCA does not cover AI and standalone apps are unregulated. Treat as "unregulated but liable" (Consumer Protection Act product liability, DPDP) | [S21] commentary, UNVERIFIED |
| DPDP Rules 2025 | Notified Nov 2025; most duties from about 2027-05-13; verifiable parental consent under 18; consent, purpose limitation, breach notice | [S22] UNVERIFIED (law-firm snippets). Our 18+ rule avoids the child-data duties |

**Pattern:** every credible body says "adjunct, human in the loop, evidence required". None approves an AI that screens, diagnoses or counsels alone.

## 2. Do not build, and build only as assistive

### 2.1 Do not build (or remove)

| Item | Why | Maps to |
|---|---|---|
| AI diagnosis or condition labels | TPG 5.4; APA; no validated accuracy; PHQ-9 and GAD-7 are the screening tools | Never add to `ai/scoring.py` outputs |
| AI-only crisis detection (model replaces or lowers the floor) | PPV and drift evidence; "the crisis path never waits on the model" | Keep `ai/severity.py` authoritative |
| Ranking students by predicted suicide risk | Spittal 2025: too low for prioritising; creates a hidden watch-list | Not on `provider_dashboard` |
| Voice biometrics, speaker ID, voice-based depression or risk scoring | Weak, non-replicating, accent and language sensitive; biometric data raises DPDP and trust issues; the audio is discarded today, keep it so | `utils/voice_features.py` |
| **Voice "emotion" label (`classify_emotion`, `analyze_voice_emotion`)** | Pitch/energy/ZCR thresholds are not valid emotion measures; phone mics and accents break them; the label can reach counsellors as fact. Remove from any counsellor view now | `utils/voice_features.py`, `ai/service.py:384`, `models.py` voice log |
| Emotion scores shown to counsellors as fact | Contested science; EU treats as banned in education; anchors clinical judgement | all dashboards |
| **LLM "adherence score" 0 to 100** | The model invents a number from a few logs; no validation; clinical risk | `ai/service.py:345`; replace with a plain count of logged vs missed doses |
| Open-ended generative therapy chat, personas ("Dr. Anya"), "counselling" claims | Harms in 1.2; TPG 5.4; no safe free tier route (privacy rule forbids hosted inference) | `routes/chat.py` stays scripted plus fixed templates |
| Training or tuning on real student text, or scraped social-media distress posts | Owner rule 7; consent and re-identification problems | datasets agent |
| Any model output shown to institution administrators about individuals | Chilling effect; discrimination; breach of trust | Agreement clause (4.7) |

### 2.2 Build only as assistive (human decides, model proposes)

| Feature | Constraint |
|---|---|
| Second-opinion crisis classifier | Raise-only; non-paging; counsellor queue with reason; shadow first |
| Semantic search over clinician-vetted content | Returns only pre-approved text; no generation |
| Speech-to-text for typing convenience | Transcript goes through the same floor as typed text; student can edit; no audio kept; no acoustic inference |
| Text-to-speech of fixed content | No personal data involved |
| Counsellor session-note drafting | Only if inference stays on our own server or counsellor device; counsellor edits and owns the note; labelled draft. Build later |
| Translation of static content | Human-reviewed before publish |
| Trend flags for counsellors | Deterministic rules on PHQ-9, missed check-ins, sleep (not ML), shown with the raw numbers |

## 3. Safety engineering for the proposed AI features

### 3.1 Layered design

| Layer | Rule | Today |
|---|---|---|
| L0 deterministic floor | Regex plus normalisation plus negation and third-party logic; synchronous; authoritative; no kill switch; fixed replies | `ai/severity.py`, `ai/service.py` |
| L1 model signal | Runs after L0. Output is a score and a coarse tier. May only RAISE: none to soft check-in, soft to counsellor review queue. Never lowers, never cancels an L0 alert, never edits a fixed reply | new, shadow only at first |
| L2 human review | Counsellor sees the item, the L0/L1 reason category, and decides. Nothing that pages a human is created by L1 alone. Only L0 pages | `provider_dashboard`, `crisis_alerts` |
| L3 audit | Every L1 raise and every human decision logged as codes, never text | `utils/audit.py` |

Why L1 does not page: with LR+ 10 and low prevalence the page would be a false alarm about 99 percent of the time (Spittal). A student seeing a gentle check-in plus helplines after a false raise is cheap and reversible; a 3 a.m. phone call to a counsellor is not. Exception that the clinician may approve later: L1 high-tier plus a recent PHQ-9 item 9 or L0 soft hit combine to page.

Computed PPV for a 80 percent sensitive detector (my arithmetic, standard formula): prevalence of crisis-level messages 0.1 percent: PPV 1.6 percent at 95 percent specificity, 7.4 percent at 99 percent. Prevalence 1 percent: 13.9 percent and 44.7 percent. A model that is "99 percent accurate" still produces mostly false alerts.

### 3.2 Fail-safe behaviour

| Failure | Behaviour |
|---|---|
| Model file missing, hash mismatch, load error, out of memory | Feature flag forced off at boot; log a code; L0 only (identical to today) |
| Model timeout (budget about 150 ms inline, else asynchronous job) | Discard result; never delay the reply; L0 answers |
| Model returns NaN, out-of-range, wrong schema | Treated as no signal |
| Model disagrees with L0 downward | Ignored (raise-only) |
| Render free instance sleeps or restarts | Model lazy-loads after the first response; first message after cold start is L0 only |
| Model version changes without sign-off | Startup check compares model hash to the signed manifest; mismatch disables L1 |
| Adversarial text (injection, obfuscation) | L0 normalisation already folds confusables and leetspeak; L1 input is the same normalised text; L1 output cannot change replies, so injection has nothing to steer |

### 3.3 Drift monitoring without storing text

Log only aggregates, per day, per model version, with cells under 5 suppressed:

- counts of the L0 class by L1 tier (the 4 by 4 agreement matrix);
- score histogram in 10 buckets (population stability index against the pilot baseline);
- script mix (Latin, Devanagari, mixed), length bucket, latency percentiles, timeout rate;
- counsellor verdicts on L1 items: "concerning", "not concerning", "unsure" (a label tied to an alert id, no text);
- alert-per-counsellor-per-week.

Nightly canary in GitHub Actions: run the frozen synthetic set (no student data) through the model and fail the build if any case flips relative to the signed expected output. Alarms: agreement-matrix shift above a set PSI, "not concerning" rate above 80 percent for two weeks (alert fatigue), recall on canary below the frozen floor.

### 3.4 Red-team plan

Run before first shadow, before every model or threshold change, and quarterly with native speakers (volunteer clinicians, counsellors, final-year psychology students; free). Findings go into the frozen set tagged by slice.

| Attack class | Examples to cover |
|---|---|
| Evasion | Euphemisms ("sleep forever", "pack my bags permanently"), method-only statements, romanised Hindi spelling variants, Devanagari-Latin mixing, emoji only, song or film quotes, very long messages, slang by region |
| False-positive traps | Idioms ("hasi se mar gaya", "exam is killing me"), exam jokes, third-party concern, quoted news, negation, past tense recovery stories |
| Abuse | Prank or harassment: a student writing alarm text to trigger a roommate's counsellor flow; mass-alert flooding |
| Model attacks | Prompt injection in journal or STT transcript, gradient or token tricks on the small encoder, input in unseen scripts |
| Fairness slices | English-medium vs vernacular, gender-coded language, caste, religion and region words, disability, dyslexic spelling, STT errors on accents |
| Privacy | Memorisation or leakage tests, log inspection for text, error pages |

### 3.5 Harm taxonomy and severity

| Rank | Harm | Example | Primary control |
|---|---|---|---|
| S1 Critical | Missed crisis with false reassurance | L1 or a reply downplays a real disclosure | L0 authoritative; raise-only; fixed replies; incident SLA |
| S1 | Personal text sent to a third party | Gemini call with `personal=True` slips through | `utils/ai_policy.py` gate, tests, egress allowlist |
| S1 | Model advice contains method or encouragement | Generative reply | No free generation in crisis or personal paths; output guard |
| S2 High | Counsellor misled by model label | "Depressed 87 percent" treated as diagnosis | No scores shown, only categories and reasons; training |
| S2 | Confidential flag reaches administrators or disciplinary process | College uses alerts for fitness-to-study | Agreement clause; role scoping; audit |
| S2 | Substitution for care or dependence | Student relies on bot for weeks | Escalation prompts, usage nudges to human, APA-style disclosure |
| S3 Medium | Alert fatigue (leads to S1 later) | 30 false items per counsellor per week | Alert budget, tiers, digest, kill switch |
| S3 | Chilling effect or distrust | Students stop writing honestly | Transparency copy, opt-outs for L1, no hidden scoring |
| S3 | Language or group bias | Lower recall on Devanagari or Hinglish | Slice metrics, gating criteria |
| S4 Low | Irrelevant tip, slow page, wrong helpline | Retrieval miss | Static fallback, monitoring |

### 3.6 Human-in-the-loop for flagged items

L1 items enter a "model-suggested review" queue, separate from crisis alerts, ordered by time not by score, with: category, which tier, last PHQ-9 date, and one-click actions (reach out, mark not concerning, escalate). Each item has an owner and a next-business-day review target. Counsellors can switch the queue off. Nothing in it is shown to the student as "flagged"; the student only sees a gentle check-in card.

### 3.7 Kill switches, model cards and change control

| Control | Design |
|---|---|
| Env flags (default off) | `AI_L1_SHADOW`, `AI_L1_RAISE`, `AI_RETRIEVAL`, `AI_STT`, `AI_TTS`, `AI_KILL_ALL`. Read per request. Render env change needs a restart: slow |
| Admin toggle | Settings row, cached for 30 seconds, admin-only, audited. Flips a feature off in under a minute. The floor has no toggle |
| Model card per model | Intended use, out-of-scope use, data sources and licences, size and latency, metrics by language slice with confidence intervals, thresholds, known failures, hash, owner, date, clinician reviewer |
| Threshold changes | Config file in git with fields `clinician`, `date`, `eval_report_sha`, `previous_value`. A test fails if the threshold file changes without a matching signed record. No threshold change on the same data used to tune it |
| Frozen sets | A tuning set and a never-tuned sealed set. The sealed set is used once per release candidate |
| Release gate | CI blocks if recall on the sealed set drops, or false-alert rate rises above budget, or any slice recall falls under its floor |

### 3.8 Incident response

1. Detect: counsellor report, drift alarm, canary failure, student complaint. 2. Contain within 1 hour: flip `AI_KILL_ALL` or the single flag; L0 continues. 3. Triage by the S1 to S4 table; S1 or S2 call the clinical lead and the college contact. 4. Preserve evidence as codes and counts (never raw text). 5. If personal data left our system: breach process under DPDP Rules (check timelines in the rule text) and notify the college. 6. Blameless review within 7 days, update red-team set, record in `docs/MEMORY.md`. 7. No re-enable until the sealed set passes again and the clinician signs.

### 3.9 Consent, transparency, DPDP and the college agreement

| Requirement | Practice |
|---|---|
| Honest labelling | Every AI-produced sentence marked as automated; no "Dr." persona; `assistant_kind()` already tells the truth about what runs |
| Purpose limitation | Separate consent line per feature (floor safety checks; model second opinion; STT; counsellor visibility of signals). Withdrawal switches the feature off for that student |
| What counsellors see | Plain statement shown to students before use: which signals, who sees them, retention |
| Data | No audio retained, no text in logs, no training on student data, no external inference of personal text (owner constraint) |
| College agreement clauses | No use of signals for discipline, academics, hostel or admission decisions; no individual-level sharing with administrators; k-anonymised aggregates only; named clinical lead and 24x7 escalation owner; incident notification duty; right to audit; termination deletes data |
| Under 18 | Keep the 18+ gate; DPDP Rule 10 child duties then do not arise (UNVERIFIED rule text) |
| Ethics approval | Any research use (pilot, publishing results) needs an institutional ethics committee; see 4.5 |

## 4. Evaluation framework: is the feature better than the baseline?

### 4.1 Baseline and what the current test sets can and cannot do

| Asset | Count | Use | Limit |
|---|---|---|---|
| `crisis_test_cases.csv` | 169 (112 crisis, 35 none-or-soft, 11 none, 6 friend, 5 soft; 117 English, 36 Hinglish, 16 Devanagari) | Regression: keeps floor behaviour stable; includes injection cases | Written with the detector; 169 of 169 match, so recall and false-positive rate are unmeasured. Few Devanagari cases |
| `crisis_phrases.csv` | 1,416 rows (1,243 crisis patterns) | Review packet for the clinician | Clinician columns blank; patterns, not an evaluation set |
| New: held-out set A | target 300 items, at least 150 positives, at least 50 in Hinglish or Devanagari, authored by 3 or more people who have not seen the regexes, labelled independently by 2 clinicians plus adjudication | Real recall and false-alert estimate of the floor and of any model | Needs clinician time. The labelling is hard anyway (kappa 0.34 in [S24]); report agreement |
| New: hard-negative set B | 300 benign items (idioms, exams, jokes, third-party, quoted news) | Specificity | Same |
| New: sealed set C | 100 positives plus 100 negatives | One-shot release gate | Never used for tuning |

Sample size for recall (computed): if all n positives are caught, the 95 percent one-sided lower bound is 0.74 at n=10, 0.90 at n=30, 0.94 at n=50, 0.95 at n=59, 0.97 at n=100. At observed recall 0.90 the 95 percent interval is 0.70 to 0.97 at n=20 and 0.85 to 0.93 at n=200. So 150 positives are needed to speak of recall at the 0.85 to 0.95 level; 30 is a smoke test.

### 4.2 Metrics per feature

| Feature | Primary metric | Secondary | Baseline |
|---|---|---|---|
| L1 crisis second opinion | Incremental recall: share of clinician-positive items missed by L0 that L1 raises, at a fixed false-alert rate of at most 1 percent of benign messages | Incremental PPV of L1-only raises; counsellor minutes per week; per-slice recall | L0 alone on set A, B, C |
| Counsellor review queue | Precision burden: false items per counsellor per week (budget: 5 for non-paging items, set by owner) | Time to action, share marked "not concerning" | No queue |
| STT (browser or server) | WER and, for safety words, a "crisis-term miss rate"; per accent, language, phone model | Latency on 2G or 3G; failure rate | Typing |
| Vetted-content retrieval | Hit rate at 3 on 100 clinician-written student queries (does a clinician-approved item appear in the top 3?) | Click-through, "was this helpful" 3-point rating, zero-result rate | Current static starter list and keyword search |
| TTS read-aloud | Completion rate of guides, accessibility feedback | Load time | No audio |
| Journaling or reflection prompt | User-rated helpfulness; return rate at 2 weeks | Harm reports | Fixed prompt list |
| Whole product | Time to first support (minutes from distress disclosure to a human or a helpline click), drop-off at week 2 and 4, helpline click rate, appointments booked | Counsellor workload | Pre-pilot cohort or parallel non-AI feature |

Rule: never use mood or PHQ-9 scores as engagement metrics; no points or streaks on them (project rule).

### 4.3 Shadow mode (first step, zero user impact)

Run the candidate model next to the floor, record only the agreement matrix and score buckets (section 3.3), show nothing to anyone. Two sources of ground truth: (a) sets A, B, C offline; (b) an optional, consent-gated, opt-in "help us improve safety" review where a student's flagged-but-disagreeing message is read by a clinician and labelled; stored as a code and not used for training (owner decision needed, Q4). Run at least 4 weeks and at least 59 clinician-labelled positives before any raise is switched on.

### 4.4 Pre-registered pass bars (proposal for clinician and owner sign-off)

Write these in a dated file before looking at results. Suggested defaults:

| Gate | Bar |
|---|---|
| Floor baseline (do this first) | Recall on set A at least 0.90 with lower CI bound at least 0.85; each language slice at least 0.80; false-alert rate on set B at most 2 percent |
| L1 may run in shadow | Passes licence and RAM checks (other agents), canary stable |
| L1 may raise (non-paging) | Incremental recall at least 15 percentage points of the floor's misses with at most 1 percent benign flagged; incremental PPV at least 20 percent on clinician labels; no slice recall below the floor's; counsellor budget not exceeded |
| L1 may combine toward paging | Clinician sign-off plus a separate prospective evaluation |
| Retrieval on | Hit rate at 3 of at least 85 percent and no unreviewed content served |
| STT on | WER at most 20 percent on our accent set (owner to set), crisis-term miss rate no worse than typed baseline in a paired test |
| Any feature | Zero S1 incidents; no S2 unresolved; kill switch drill passed |

### 4.5 Ethical A/B in a pilot

- **Never randomise safety.** The floor, fixed crisis replies and helplines are identical in every arm. Randomise only low-risk features (retrieval vs static list; reflective prompt vs fixed prompt).
- Ethics committee approval (institutional ethics committee under the ICMR 2017 National Ethical Guidelines) before any data collection for research; check whether CTRI registration applies to a behavioural trial (CTRI says prospective registration for interventions; draft ICMR guidance on non-regulatory trials covers mental-health support) [S31]. UNVERIFIED; the committee will say.
- Informed consent that separates research from service; students can decline research and keep the service; no academic consequences.
- Stopping rules written in advance: stop an arm or the pilot on any S1 incident, on counsellor workload above budget for 2 consecutive weeks, on a clinician request, or if an interim look (at 50 percent of exposure, no efficacy testing) shows a safety imbalance.
- Counsellor of record with 24x7 escalation plan; helplines unchanged; debrief and data deletion.
- Pre-register primary outcome, analysis plan and sample size on OSF or CTRI before enrolling.

### 4.6 What a 30 to 100 student pilot can and cannot show

Computed (normal approximation, 80 percent power, alpha 0.05, two-sided; assumed SD of PHQ-9 change about 5 points):

| Quantity | Result |
|---|---|
| Per-arm n to detect d = 0.2 / 0.3 / 0.5 / 0.8 | 392 / 174 / 63 / 25 |
| Smallest detectable effect with 15 / 25 / 50 per arm | d = 1.02 / 0.79 / 0.56 |
| Single-arm pre/post PHQ-9, 95 percent CI half-width | plus or minus 1.8 points (n=30), 1.4 (n=50), 1.0 (n=100) |
| Expected crisis-level events | If 0.5 percent of students per week write crisis-level text, 100 students give about 0.5 events a week, roughly 6 in 12 weeks: far too few to estimate recall from live traffic |

Therefore the pilot **cannot** show: depressive symptom improvement attributable to a feature (regression to the mean, selection, and engagement bias swamp it; published meta-analytic effects of g about 0.3 need about 174 per arm); crisis-detection recall; suicide prevention; or long-term outcomes.

It **can** show: that the product runs on free tier under real load; usage and retention (Wysa lost 39 percent [S6]); false-alert load per counsellor; whether counsellors act on queue items; STT WER on real devices; retrieval hit rates; helpfulness ratings; time to first support; zero-incident safety behaviour; and acceptability. Frame results with confidence intervals and as feasibility, never as efficacy.

## 5. Cost-benefit of candidate AI features

Benefit = evidence plus expected value to students or counsellors. Risk = harm potential. Cost = engineering weeks plus run cost on free tier (details from other agents). Scores 1 (low) to 5 (high). Order is my recommendation.

| # | Feature | Benefit | Risk | Cost | Evidence | Verdict |
|---|---|---|---|---|---|---|
| 1 | Measure the existing floor: independent held-out sets A, B, C, clinician and Hindi review of the 1,416-row packet | 5 | 1 | 2 | n/a (it is the measurement) | Build now. Prerequisite for everything |
| 2 | Better deterministic floor and normalisation (Hinglish spellings, Devanagari, idiom lists, negation) driven by set A errors | 4 | 1 | 2 | Keyword-only fails on code-mixing (SAFETY_RESEARCH) | Build now |
| 3 | Remove voice emotion label and LLM adherence score; replace adherence with counted logs | 3 | 1 | 0.5 | Negative: no validity | Do now (less AI) |
| 4 | Deterministic change flags for counsellors (PHQ-9 rise, item 9, missed check-ins, sleep) | 4 | 1 | 1.5 | Measurement-based care is standard practice; no ML needed | Build now |
| 5 | TTS read-aloud for fixed guides (breathing, grounding) via browser speech API or pre-rendered audio | 3 | 1 | 1 | Accessibility plausible, unmeasured | Build now if cheap |
| 6 | Semantic or lexical retrieval over clinician-vetted content (starter questions, guides, FAQ) | 3 | 1 | 2 | ABSENT for outcomes; measurable offline | Build after #1, hit rate gated |
| 7 | L1 crisis second-opinion encoder, raise-only, shadow first | 3 | 3 | 3 | PPV low at low base rate [S23][S24]; Hinglish evidence thin | Build later, gated by #1 |
| 8 | STT for voice-to-text journal or chat input (on-device or own server) | 3 | 2 | 3 | Accessibility; WER on Hinglish unknown (speech agent) | Build later, same floor on transcript |
| 9 | Counsellor session-note drafting (own-server or on-device model) | 3 | 3 | 4 | General scribe evidence not verified here; none in mental health | Research only |
| 10 | Journal reflection prompts or AI feedback (on-device only) | 2 | 2 | 3 | WEAK, waitlist-controlled, COI [S30] | Research only; fixed prompts first |
| 11 | Machine translation of static vetted content into more Indian languages with human check | 3 | 2 | 2 | n/a; reach benefit | Build later |
| 12 | Open-ended generative companion (any host) | 2 | 5 | 5 | Harms documented; benefit only under human monitoring (Therabot) | Do not build |
| 13 | Voice-based depression or risk detection, speaker or emotion models | 1 | 5 | 4 | WEAK, non-replicating [S28] | Do not build |
| 14 | Risk ranking of students for counsellors | 1 | 5 | 3 | Spittal: too low [S23] | Do not build |
| 15 | AI diagnosis or treatment suggestion | 1 | 5 | 3 | TPG 5.4, APA | Do not build |

Recommended order: 1, 2, 3, 4 in parallel (weeks 1 to 4), then 5 and 6, then shadow 7 and 8 only if 1 shows the floor leaves a measurable gap. Items 9 to 11 wait for clinician demand. Items 12 to 15 are closed.

**Single smallest first experiment (no model, no student data):** recruit one clinician and two Hindi/Hinglish speakers; have 3 people who never saw the regexes write 300 crisis-and-benign messages across English, Hinglish and Devanagari; have two clinicians label them blind; run `ai/severity.py` and report recall, false-alert rate and per-language slice with confidence intervals. Pass bar: section 4.4 floor baseline. Time: about 2 weeks of part-time effort, cost zero. If the floor already meets the bar, the case for L1 is weak; if recall is poor in Hinglish, fix rules first and re-measure. Only then run shadow L1 on the same sets.

## 6. Fit for MindFull Horizon, per candidate

| Candidate | Plug-in point | Adds over today | Saved Gemini calls | Cost | Verdict and evidence |
|---|---|---|---|---|---|
| L1 second opinion | After `classify()` in `ai/service.py:ask_with_severity` and journal path; results to a review queue in `routes/provider.py` | Catches indirect or novel wording regex misses (unmeasured) | none | Weeks 3 to 4; model size and RAM from encoders and runtime agents | Build later. Evidence it improves outcomes: none; evidence on detection: fair AUC, poor PPV |
| Retrieval | Starter templates (`utils/chat_templates.py`), daily tip (`utils/daily_tip.py`), guide finder | Better matching of a student's words to the right fixed guide | Replaces paid or personal-text calls for tips | Weeks 1 to 2 | Build after #1. No outcome evidence |
| STT | Voice log and chat input (`routes/audio.py`, `static/js/...`) | Lower typing burden | none | Weeks 2 to 3 | Build later. No outcome evidence |
| TTS | Breathing and grounding pages | Accessibility | none | Week 1 | Build now. No outcome evidence |
| Remove emotion and adherence AI | `utils/voice_features.py:classify_emotion`, `ai/service.py` | Removes unvalidated claims | 2 prompts gone | Days | Do now |

## 7. What would convince me (test plan)

| Claim | Smallest experiment | Metric | Pass bar |
|---|---|---|---|
| "Floor is adequate" | Section 5 first experiment | Recall, false-alert rate by language | Section 4.4 |
| "L1 finds what the floor misses" | Shadow on sets A, B, C, then shadow on live traffic with aggregate logging | Incremental recall at at most 1 percent benign flagged; incremental PPV | At least 15 points of floor misses, PPV at least 20 percent, no slice worse |
| "Retrieval helps" | 100 clinician-written queries | Hit rate at 3 | At least 85 percent |
| "STT is usable" | 100 recorded phrases from 20 volunteers on real phones, accents and noise | WER, crisis-term miss rate | WER at most 20 percent; no worse than typed baseline on crisis terms |
| "Students and counsellors want it" | 4-week pilot, 30 to 100 students, 2 counsellors | Helpfulness, retention, counsellor minutes, false items per week | Within budget, no S1 or unresolved S2 |
| "It improves symptoms" | Not testable at pilot size | n/a | Needs about 170 per arm for g 0.3; run only with ethics approval, registered, after safety gates |

## 8. Cross-notes

At time of writing `docs/research/ai/` held no other agent files (`speech.md`, `llm-agents.md`, `encoders-nlp.md`, `datasets-finetuning.md`, `runtime-hosting.md`, `voice-product.md` were absent). Their answers that would change mine:

- `encoders-nlp.md`: any claimed recall or F1 on Hinglish suicide text is in-corpus (e.g. 98.54 percent in [S27]); I would discount it until it is measured on set A. Model size and calibration decide whether L1 fits in 512 MB.
- `runtime-hosting.md`: if the encoder cannot load within the Render free limit alongside Flask, L1 moves to the browser (on-device) or is dropped; shadow evaluation can run offline in GitHub Actions at no cost.
- `speech.md`: WER on Hinglish and accented English decides STT. If WER is high, STT stays a typing aid with student editing, never a safety input on its own.
- `datasets-finetuning.md`: any public self-harm corpus is consent-problematic (owner rule 7); sets A to C should be authored fresh. Licences must permit evaluation use.
- `llm-agents.md`: any on-device LLM companion falls under 2.1 "open-ended generative chat" unless it is a retrieval-and-script agent with fixed crisis replies.
- `voice-product.md`: voice features that infer emotion or condition fall under 2.1; voice as an input and output channel for fixed content is fine.

## 9. Questions for the owner

1. Is there a named clinician (psychologist or psychiatrist) and at least two Hindi/Hinglish speakers who will label sets A to C and sign thresholds? Without them I recommend no L1 at all.
2. Do you accept "AI-assisted, not AI-centric" as the scope, with items 12 to 15 closed?
3. Will a college ethics committee review the pilot, and who is the counsellor of record with 24x7 escalation?
4. May a student opt in to let a clinician read flagged messages for evaluation (not training)? If not, we evaluate only on authored sets.
5. Will the college agreement include the no-discipline, no-individual-sharing clauses in 3.9?

## Sources (all accessed 2026-11-25)

S1 https://tto.dartmouth.edu/news/2025/03/first-therapy-chatbot-trial-yields-mental-health-benefits (read). S2 https://ai.nejm.org/doi/full/10.1056/AIoa2400802 (403, not read; effect sizes via search summary). S3 https://ir.ymlib.yonsei.ac.kr/handle/22282913/212700 (npj Digit Med 2026, DOI 10.1038/s41746-026-02566-w; snippet). S4 https://www.jmir.org/2026/1/e82677 and https://www.jmir.org/2026/1/e104186 and https://www.jmir.org/2025/1/e69639 (snippets; mapping of figures to URLs not confirmed). S5 https://karger.com/pps/article/doi/10.1159/000552072/948904 (snippet). S6 https://pearl.plymouth.ac.uk/pms-research/1982 (read). S7 https://pubmed.ncbi.nlm.nih.gov/30470676/ (snippet). S8 https://pmc.ncbi.nlm.nih.gov/articles/PMC5478797 (snippet). S9 https://www.statnews.com/2025/07/02/woebot-mental-health-chatbot-shuts-down-founder-says-ai-moving-faster-than-regulators/ (snippet). S10 https://spirals.stanford.edu/assets/pdf/moore_expressing_2025.pdf and https://news.stanford.edu/stories/2025/06/ai-mental-health-care-tools-dangers-risks (snippets). S11 https://www.brown.edu/news/2025-10-21/ai-mental-health-ethics (snippet). S12 https://openai.com/index/strengthening-chatgpt-responses-in-sensitive-conversations/ via https://techcrunch.com/2025/10/27/openai-says-over-a-million-people-talk-to-chatgpt-about-suicide-weekly (snippet). S13 https://www.euronews.com/2026/01/08/google-and-chatbot-start-up-characterai-to-settle-lawsuits-over-teen-suicides (snippet). S14 https://arxiv.org/html/2503.17473v2 (snippet). S15 https://www.apa.org/news/press/releases/2025/11/ai-wellness-apps-mental-health (read) and https://apa.org/topics/artificial-intelligence-machine-learning/health-advisory-chatbots-wellness-apps. S16 https://www.fda.gov/medical-devices/digital-health-center-excellence/fda-digital-health-advisory-committee with https://www.orrick.com/en/insights/2025/11/fdas-digital-health-advisory-committee-considers-generative-ai-therapy-chatbots-for-depression and https://www.venable.com/insights/publications/2025/12/the-mind-the-machine-and-the-model-drift-fdas (snippets; FDA summary PDF returned 404). S17 https://www.who.int/publications-detail-redirect/9789240084759 (snippet). S18 https://www.nice.org.uk/guidance/hte30 (snippet). S19 https://www.dlapiper.com/en/insights/publications/2025/08/ai-mental-health-chatbots (snippet). S20 https://www.icmr.gov.in/ethical-guidelines-for-application-of-artificial-intelligence-in-biomedical-research-and-healthcare and https://www.newsonair.gov.in/meity-unveils-india-ai-governance-guidelines-to-promote-safe-and-responsible-ai-adoption (snippets). S21 https://techlawforum.nalsar.ac.in/the-artificial-intelligence-conundrum-balancing-innovation-and-protection-in-mental-healthcare/ (commentary). S22 https://www.barandbench.com/view-point/meity-notifies-final-digital-personal-data-protection-rules-2025 (snippet). S23 https://ideas.repec.org/a/plo/pmed00/1004581.html (read). S24 https://www.medrxiv.org/content/10.64898/2026.01.12.26343914v1.full (read; preprint). S25 https://www.crisistextline.org/product/detecting-crisis-an-ai-solution/ (vendor) and https://www.frontiersin.org/journals/psychiatry/articles/10.3389/fpsyt.2023.1110527/pdf (snippet). S26 https://www.statnews.com/2019/02/11/facebook-suicide-prevention-tools-ethics-privacy/ (snippet). S27 https://aclanthology.org/2021.icon-main.14 (snippet). S28 https://pure.ulster.ac.uk/en/publications/a-review-of-studies-using-machine-learning-to-detect-voice-biomar/ , https://arxiv.org/pdf/2508.18092 , https://bhbusiness.com/2026/02/11/mental-health-voice-biomarker-kintsugi-closes-makes-all-technology-and-research-public/ (snippets). S29 https://ai-act-service-desk.ec.europa.eu/en/ai-act/recital-44 (snippet). S30 https://arxiv.org/abs/2601.11530 (snippet). S31 https://www.ctri.nic.in/ and https://www.icmr.gov.in/icmrobject/uploads/Static/1784177629_draftguidance-non-regulatoryclinicaltrials_latest_v2.pdf (snippets). Also seen only as snippets: VERA-MH https://ai.jmir.org/2026/1/e92817 (clinician-anchored LLM safety benchmark, open source), K-Bench and the ecological audit (arXiv); worth reading before designing set A.

Local files read: `ai/severity.py`, `ai/service.py`, `utils/ai_policy.py`, `utils/voice_features.py`, `utils/chat_templates.py`, `docs/SAFETY_RESEARCH.md`, `docs/LLM_SECURITY.md`, `docs/review/generated/crisis_test_cases.csv`, `crisis_phrases.csv`, `MANIFEST.md`.
