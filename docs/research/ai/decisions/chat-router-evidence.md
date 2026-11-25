# Chat-router knowledge-base: evidence basis per intent

Author: ROUTER-EVIDENCE agent, 2026-11-25. Research only (web search and fetch); no code or `ai/kb_data/*.json`
files were edited. I am not a clinician. Citing real published guidance is meant to raise confidence honestly,
not to replace the clinician review `ai/kb.py` already requires (every entry's `review_status` must stay
`draft_unreviewed` until a clinician signs off; see that file's own docstring). Nothing below changes that gate.

Context read before this research: `BRIEF.md` (UPDATES 4), `docs/research/ai/SYNTHESIS.md` section 3(b) item b3
and its surrounding gate, `docs/SAFETY_RESEARCH.md`, `ai_prompts/psychologist_system.txt`,
`docs/research/ai/llm-agents.md` (Design A, section on retrieval/scope rules), `docs/research/ai/evidence-safety-eval.md`
(regulatory table, section 2). The ROUTER agent (a3bec55515768a9be) had already built `ai/kb.py`, `ai/router.py`
and all 15 `ai/kb_data/*.json` files when I started; I read all of them and the snippets quoted below are the
exact current draft text.

## Architecture check: does the crisis floor always run before the router, with no path to override it?

Read `ai/service.py::ask_with_severity` end to end. Yes, in design: step 1 is
`level = classify(raw)` on the bounded raw text, before sanitising, injection detection, budget
accounting, or any model call (`ai/service.py` lines ~128-131). The model call itself is skipped entirely
when `level == 'crisis'` (`... and level != 'crisis'`, line 143), and `router.py`'s own docstring states it
is "only ever called for a message the crisis floor ... already classified 'none'" and "has no way to
downgrade or override a floor decision because it never runs on one."

**Flag for the lead:** `ai/router.py` and `ai/kb.py` exist and are complete, but I could not find any call
site wiring them in yet. `grep` across the repo for `CHAT_ROUTER_ENABLED`, `ai.router`, or `kb.get_snippet`
found matches only inside `ai/kb.py`'s and `ai/router.py`'s own docstrings — no import or call from
`ai/service.py`, `routes/`, or `tests/`. So the "floor always wins" invariant is correct in the code that
exists today (the router/KB modules are inert, never invoked), and it is correctly *designed* to hold once
wired in (router.py is built to be called only from inside the `level == 'none'` branch), but it has not
actually been exercised in an end-to-end call path yet. **When the router is wired into `ai/service.py`, the
call to `router.match()` / `kb.get_snippet()` must sit strictly after the `level = classify(raw)` line and
strictly inside a branch that already excludes `level in ('crisis', 'friend', 'soft')` — verify this at
integration time, do not assume it from the module docstrings alone.**

## Summary table

| Intent | Best source org | Confidence | Harm-if-wrong |
|---|---|---|---|
| assessment (PHQ-9/GAD-7) | Kroenke 2001 (PHQ-9), UW HIV/AIDS Program clinical page (GAD-7) | MEDIUM-HIGH | **HIGH** |
| safety_plan | SPRC (Stanley-Brown Safety Planning Intervention) | MEDIUM | **HIGH** |
| general_stressed | WHO Psychological First Aid guide (adapted, not student-specific) | MEDIUM-HIGH | MEDIUM |
| general_lonely | WHO Psychological First Aid guide (adapted, not student-specific) | MEDIUM-HIGH | MEDIUM |
| medication_log | WHO "Adherence to Long-term Therapies" (2003) | MEDIUM-HIGH | MEDIUM |
| sleep_log | NHS "Insomnia" page (referral half only) | MEDIUM | LOW-MEDIUM |
| grounding | Cleveland Clinic 5-4-3-2-1 page (no live WHO/VA/SAMHSA primary found) | **LOW** | LOW-MEDIUM |
| booking | Tele-MANAS (PIB), MANODARPAN (Ministry of Education) | MEDIUM-HIGH | LOW |
| delete_account | DPDP Act 2023 s.12(3), DPDP Rules 2025 | MEDIUM-HIGH | MEDIUM (legal-accuracy risk, not clinical) |
| journal | APA Monitor coverage of Pennebaker expressive-writing research | MEDIUM-HIGH | LOW |
| breathing | Peer-reviewed vagal-tone/breathing studies (not a lay WHO/NHS page) | MEDIUM | LOW |
| digital_detox | WHO Europe 2025 policy brief (evidence explicitly mixed) | MEDIUM | LOW |
| music | NIH NCCIH "Music and Health" page | HIGH | LOW |
| goals | APA depression guideline, behavioral-activation section (imperfect fit) | LOW-MEDIUM | LOW |
| mood_checkin | PMC review of mood-monitoring RCTs (mixed/unclear benefit) | LOW-MEDIUM | LOW |
| about_privacy | No direct match; closest analog is California SB 243's AI-disclosure duty | N/A (verify against code, not a citation) | LOW |

Two axes are separate on purpose: `about_privacy` and `delete_account` are procedural claims about this app's
own real behaviour, not clinical psychoeducation — their correctness is verified against the code and the
actual route behaviour, not against a published source, and I say so plainly below rather than forcing a
weak external citation to look like evidence it isn't.

## Per-intent detail

### assessment — PHQ-9 / GAD-7 screening
Current snippet: *"You can take the PHQ-9 and GAD-7 screening questionnaires from the assessment page
whenever you want a check on how you have been feeling. They are screening tools, not a diagnosis. If an
answer there is about thoughts of self-harm, the app shows helpline numbers right away."*

(a) Source: Kroenke, Spitzer & Williams, "The PHQ-9: Validity of a Brief Depression Severity Measure,"
*J Gen Intern Med* 2001, https://pmc.ncbi.nlm.nih.gov/articles/PMC1495268/ (live, access 2026-11-25) — the
PHQ-9 validation paper already cited in `docs/SAFETY_RESEARCH.md`. For GAD-7: University of Washington
HIV/AIDS Program clinical education page, "GAD-7,"
https://www.hiv.uw.edu/page/mental-health-screening/gad-7 (live, access 2026-11-25).
(b) Direct quote (GAD-7 page): calls the GAD-7 "an initial screening tool for generalized anxiety disorder"
and states "further diagnostic assessment is warranted to determine the presence and type of anxiety
disorder" — directly backs "screening tool, not a diagnosis."
(c) Confidence: MEDIUM-HIGH. The instruments are properly validated (that part is solid and already in this
repo's own safety research), but the PHQ-9 paper itself frames the instrument as dual-purpose
(severity grading as well as case-finding), so it only partly backs a clean "screen-only" framing on its own
— the GAD-7 page covers that framing better. The self-harm-triggers-helplines half of the snippet is an
app-design/safety-protocol claim (matches this repo's own item-9 rule in `docs/SAFETY_RESEARCH.md`), not an
external psychoeducation fact, so it needs no outside citation, only an internal check that the assessment
route actually does this (not verified by me in this pass).

### safety_plan
Current snippet: *"A safety plan is a private page in the app where you can write down what helps you stay
safe and who to contact. You can open or edit yours from the menu, and you choose whether to share it with
your counsellor."*

(a) Source: Suicide Prevention Resource Center (SPRC, SAMHSA/HRSA-funded), "Stanley-Brown Safety Plan,"
https://sprc.org/online-library/stanley-brown-safety-plan/ (live, access 2026-11-25).
(b) Paraphrase: a safety plan is "a brief intervention to help those experiencing self-harm and suicidal
thoughts ... to mitigate risk and increase safety," built from sections on warning signs, coping strategies,
people and places for distraction, support contacts, professional contacts, and means restriction.
(c) Confidence: MEDIUM. SPRC is authoritative and this is the correct underlying clinical concept most
in-app safety-plan features are modelled on, but I could not get a live fetch of a SAMHSA.gov or VA page
with matching casual wording, and the app's own language ("private page," "you choose whether to share it")
is a feature description, not a quote from the clinical literature. **Harm-if-wrong is HIGH regardless of
citation quality**: this is the one intent directly adjacent to self-harm risk management, and getting the
description of what a safety plan is or does even slightly wrong could give a student false confidence or
the wrong idea of what the feature protects against. Recommend this intent gets a named clinician's eyes
before enabling, full stop, independent of the sourcing above.

### general_stressed / general_lonely
Current snippets point to the breathing guide, journal, and counsellor booking, framed as supportive and
non-pressuring ("That sounds really hard. I hear you. ... I am here either way" / "... your college
counsellor is a good person to talk to").

(a) Source: WHO, "Psychological First Aid: Guide for Field Workers" (2011),
https://www.who.int/publications/i/item/9789241548205 (live listing confirmed, access 2026-11-25).
(b) The guide's "Look, Listen, Link" framework: under "Listen" — approach people who may need support, ask
about their needs and concerns, listen without pressing them to talk, help them feel calm, and respect their
right to decide what help they want; under "Link" — help connect people to services and informal supports.
(c) Confidence: MEDIUM-HIGH. This is a WHO document written specifically for this kind of supportive,
non-clinical psychoeducation, so the underlying principle (listen without pressuring, then point to help) is
well grounded. It is written for humanitarian/crisis field workers, not Indian college students specifically,
so it needs adapting rather than quoting verbatim — I would not call this HIGH on its own for a
student-specific claim. Harm-if-wrong: MEDIUM. These are the two intents that catch real (if sub-crisis)
distress language before the router would ever see it, so tone matters more here than for a pure
feature-navigation intent, even though the crisis floor still runs first and would have already caught
anything scoring as crisis, friend, or soft.

### medication_log
Current snippet: *"You can log your medication and see your prescriptions from the menu. I cannot give
medical advice about medicines; please ask your doctor or counsellor about that."*

(a) Source: WHO, "Adherence to Long-term Therapies: Evidence for Action" (2003),
https://iris.who.int/items/bf8058c0-03b2-4b47-838f-5534849927fb, press release
https://www.who.int/news/item/01-07-2003-failure-to-take-prescribed-medicine-for-chronic-diseases-is-a-massive-world-wide-problem
(both live, access 2026-11-25).
(b) The report states average adherence to long-term therapy is around 50% in developed countries and calls
for better support systems around adherence generally, with no drug-specific content.
(c) Confidence: MEDIUM-HIGH for the general "adherence support matters" framing; the report is from 2003 but
is still the standard WHO reference on this topic and is currently live. The snippet itself correctly names
no medicine or dose and explicitly defers to a doctor/counsellor, matching `ai_prompts/psychologist_system.txt`'s
rule. Harm-if-wrong: MEDIUM, not because this exact wording is risky (it deliberately says nothing
medical), but because this is a medication-adjacent category on the task's own harm axis — any future
edit to this snippet that drifts toward naming a medicine, dose, or adherence percentage would move it to
HIGH immediately. Flag this as a line that needs its wording frozen, not just its sourcing checked.

### sleep_log
Current snippet: *"You can keep a sleep log in the app from the menu. If poor sleep keeps happening, it is
worth mentioning to your counsellor or a doctor."*

(a) Source: NHS, "Insomnia," https://www.nhs.uk/conditions/insomnia/ (live, access 2026-11-25), section
"See a GP if: changing your sleeping habits has not helped ... you've had trouble sleeping for months ...
your insomnia is affecting your daily life."
(b) Directly backs the "mention persistent poor sleep to a doctor" half of the snippet.
(c) Confidence: MEDIUM. The referral half is well grounded; the "keeping a sleep log is a useful practice"
half has no WHO/NHS/NIMHANS primary source I could find endorsing sleep-tracking specifically (secondary UK
sources such as The Sleep Charity describe sleep diaries, but not NHS.uk itself) — flagging that as a gap
rather than forcing a citation onto it. Harm-if-wrong: LOW-MEDIUM; the referral framing is correct and safe
to state as-is.

### grounding
Current snippet: *"The app has a grounding exercise you can open from the menu that walks you through it
step by step. If things feel very heavy right now, I am also here to listen."*

(a) No live WHO, VA, or SAMHSA primary source was found for the 5-4-3-2-1 grounding technique specifically.
`ptsd.va.gov/gethelp/grounding.asp` returns 404; the VA's current self-help/coping page does not mention
grounding at all. The technique online today is carried mainly by secondary/commercial sources, the closest
being Cleveland Clinic, "5-4-3-2-1 Grounding Technique,"
https://health.clevelandclinic.org/54321-grounding-technique (access 2026-11-25).
(b) Cleveland Clinic describes it as a sensory technique (name 5 things you see, 4 you can touch, etc.) used
to interrupt anxiety/panic by anchoring attention to the present.
(c) Confidence: **LOW**. I could not find a government or WHO primary source currently live for this
specific technique, despite real effort (the VA page that likely once covered it has moved or been
removed). Cleveland Clinic is a reputable health system but not a public-health authority on the WHO/gov
tier this task asks to prioritise. Honest options: cite Cleveland Clinic as MEDIUM-confidence
professional-adjacent material, or soften the snippet to lean on the supportive-listening half (backed by
WHO PFA, see general_stressed/lonely above) rather than implying a validated clinical technique. Harm-if-wrong
is only LOW-MEDIUM because the current snippet makes no specific instructional claim (it just points to the
in-app guide), but the weak sourcing here means this is one of the intents where I'd recommend a clinician's
eyes regardless of how low-stakes the wording looks.

### booking
Current snippet: *"You can book a session with a counsellor from the appointments page in the menu. You do
not need to wait for a crisis to talk to someone."*

(a) Sources: Tele-MANAS (Ministry of Health and Family Welfare), PIB release,
https://pib.gov.in/PressReleasePage.aspx?PRID=1640208; MANODARPAN (Ministry of Education),
https://dsel.education.gov.in/sites/default/files/update/Manodarpan-merged_0.pdf (both live, access
2026-11-25).
(b) Both describe proactive, non-crisis psychosocial support as their stated purpose (24/7 free helpline;
national student psychosocial-support initiative), supporting the idea that these channels exist for more
than crises.
(c) Confidence: MEDIUM-HIGH. Neither source has an exact "don't wait for a crisis" sentence verbatim — that
framing is a reasonable inference from their stated scope, not a direct quote, so I would not call this
HIGH. Harm-if-wrong: LOW. Encouraging booking is safe to encourage regardless of the exact source wording.

### delete_account
Current snippet: *"You can delete your account from your data page: sign in, open it from the menu, and
choose delete. That removes your account and the records tied to it from the service database."*

(a) Source: Digital Personal Data Protection Act 2023, s.12(3) (right to erasure),
https://www.indiacode.nic.in/bitstream/123456789/22037/2/a2023-22.pdf; DPDP Rules 2025 notified 2025-11-13,
https://static.pib.gov.in/WriteReadData/specificdocs/documents/2025/nov/doc20251117695301.pdf (both live,
access 2026-11-25).
(b) The erasure right under s.12(3) is tied to withdrawal of consent or the processing purpose ending, and
can be overridden by another law's retention mandate — it is not an unconditional, automatic promise.
(c) Confidence: MEDIUM-HIGH that the legal concept exists and the app's framing is broadly in the right
direction; but this is a legal-accuracy question, not a clinical one, so the right check is engineering plus
legal, not a clinician. **Flag for the lead:** before this snippet goes live, verify the actual
delete-account route truly removes "the records tied to it" with no exceptions — if any table is retained
for audit, legal, or safety reasons (for example `AuditLog`, or a safety-plan record a counsellor has already
acted on), the current wording overstates what happens and should say so plainly instead. Harm-if-wrong:
MEDIUM — not clinical harm, but a broken promise about data handling is a real trust and possibly a legal
problem.

### journal
Current snippet: *"You can write in your private journal from the menu. It is tied to your account and is
not shown to other students or displayed on a counsellor's page."*

(a) Source: APA Monitor, coverage of James Pennebaker's expressive-writing research,
https://www.apa.org/monitor/jun02/writing and https://www.apa.org/monitor/sep01/keepdiary (access
2026-11-25).
(b) Describes expressive writing as associated with reduced intrusive/avoidant thoughts and modest
cognitive benefits across multiple studies, with effects described as modest and inconsistent across
individuals.
(c) Confidence: MEDIUM-HIGH. These are APA magazine pieces summarising peer-reviewed research, not a primary
study or a dedicated public psychoeducation handout, and the research itself shows modest, inconsistent
effects — worth keeping any benefit claim soft, which this snippet already does (it describes privacy, not
a therapeutic benefit, so it is actually the safer of the two things it could have said). Harm-if-wrong: LOW.

### breathing
Current snippet: *"There is a breathing guide in the app that walks you through it step by step. You can
open it from the menu whenever you want."*

(a) Sources: Moher et al., "Benefits from one session of deep and slow breathing on vagal tone and anxiety
in young and older adults," https://pubmed.ncbi.nlm.nih.gov/34588511/; 2023 scoping review of 16 breathwork
studies, https://pmc.ncbi.nlm.nih.gov/articles/PMC12372116/ (access 2026-11-25).
(b) Slow, deep breathing with a longer exhale is associated with increased vagal tone and a shift toward
parasympathetic (calmer) balance — the physiological mechanism usually cited for breathing exercises
reducing anxious arousal.
(c) Confidence: MEDIUM. These are peer-reviewed physiological studies rather than a WHO/NHS lay
psychoeducation page (I could not confirm a live NHS "breathing exercises" page in this pass). The current
snippet makes no technique claim at all, just points at the in-app guide, so it needs the least
grounding of any intent here. Harm-if-wrong: LOW.

### digital_detox
Current snippet: *"The app has a digital detox page in the menu where you can track your screen time and
set limits."*

(a) Source: WHO Regional Office for Europe, "Addressing the digital determinants of youth mental health and
well-being: policy brief" (2025),
https://www.who.int/europe/publications/i/item/WHO-EURO-2025-12187-51959-79685 (access 2026-11-25).
(b) Describes the screen-use/mental-health relationship as bidirectional and the evidence base as still
unsettled, while recommending healthier digital habits as a reasonable precaution.
(c) Confidence: MEDIUM, and I am deliberately not rounding this up: the WHO brief itself, and the peer-reviewed
reviews behind it, describe the evidence as mixed and sometimes contradictory, not a settled causal claim.
The snippet is safe because it makes no causal claim either, just points to the tracking feature. Harm-if-wrong:
LOW.

### music
Current snippet: *"You can find relaxing audio tracks on the music page in the menu."*

(a) Source: NIH National Center for Complementary and Integrative Health (NCCIH), "Music and Health: What
You Need To Know," https://www.nccih.nih.gov/health/music-and-health-what-you-need-to-know (access
2026-11-25).
(b) Summarises evidence, including a 2013 Cochrane review of roughly 2,000 participants, that music-based
interventions can reduce anxiety, mainly in situational/pre-procedure contexts, while noting risk of bias in
underlying trials.
(c) Confidence: HIGH for the general "music can help with anxiety/stress" claim — this is a US government
health-research-institute public page directly on topic. The app's snippet claims nothing beyond "relaxing,"
so it is comfortably covered. Harm-if-wrong: LOW.

### goals
Current snippet: *"You can set and track small goals from the goals page in the menu."*

(a) Source: American Psychological Association, Clinical Practice Guideline for the Treatment of Depression
Across Three Age Cohorts, "Behavioral Therapy" page, https://www.apa.org/depression-guideline/adults (access
2026-11-25).
(b) Describes behavioral activation — engaging in valued or pleasant activities and reducing avoidance,
often via small, achievable goals — as a recommended approach to improving low mood.
(c) Confidence: LOW-MEDIUM. This is a clinician-facing guideline page, not a public self-help handout framed
around "goal-setting," so it is an honest but imperfect fit; I did not find a cleaner APA/WHO/NIMHANS public
page specifically framing goal-setting as a self-help wellbeing practice. The current snippet makes no
clinical claim at all (pure feature pointer), so the weak fit does not translate into real risk.
Harm-if-wrong: LOW.

### mood_checkin
Current snippet: *"You can log how you are feeling right now in the mood tracker from the main menu. If
you would rather talk about it here first, go ahead and tell me more."*

(a) Source: systematic review, "Mood Monitoring, Mood Tracking, and Ambulatory Assessment Interventions in
Depression and Bipolar Disorder," https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12779106/ (access
2026-11-25).
(b) Finds mixed and unclear evidence that mood tracking itself improves outcomes, though some patients
report it helps them notice patterns; a secondary explainer
(https://discovermagazine.com/health/how-helpful-are-self-monitoring-tools-for-mental-health) cautions that
tracking should complement, not replace, professional care and can increase symptom-focused distress in
some people.
(c) Confidence: LOW-MEDIUM. No WHO or NIMHANS page was found making a direct public-education claim
endorsing mood tracking, and the clinical evidence itself is mixed. The current snippet already avoids
overclaiming (it does not say tracking helps, just says the feature exists and invites the student to talk
instead), so it does not need to be softened further, but it should not be strengthened toward "tracking
your mood helps you feel better" without better evidence. Harm-if-wrong: LOW.

### about_privacy
Current snippet: *"I am Anya, an automated assistant, not a human or a therapist. I answer from saved
answers and a fixed safety check; no AI model reads what you write here on this server. Your assigned
counsellor can see the records your assignment allows. The full privacy policy has every detail."*

This is a claim about this app's own real configuration and behaviour, not a psychoeducational claim, so it
is not the kind of thing an external published source can validate — the right check is reading the code
(`utils/ai_policy.py::personal_text_allowed`, `AI_SEND_PERSONAL_TEXT`, and the `ProviderPatient` scoping
rule), not citing a guideline. I did not re-verify that check in this pass (out of this task's scope), so I
am marking this N/A for external sourcing rather than forcing a citation. The closest external analog found:
California SB 243 (effective 2026-01-01, text at https://legiscan.com/CA/text/SB243/2025, summarised at
https://skadden.com/insights/publications/2025/10/new-california-companion-chatbot-law) requires a "clear
and conspicuous" disclosure that a companion chatbot is AI, not human, when a reasonable user could be
misled. It is California law, not binding here, but it is evidence that "disclose you are not human" is now
an emerging regulatory expectation for exactly this kind of chatbot, which supports keeping this snippet's
first sentence rather than softening it. Harm-if-wrong: LOW, provided the claim is actually true of the
running app (an engineering check, not a sourcing one).

## Regulatory question: does anything distinguish "supportive but not therapeutic" from crisis/diagnostic AI chatbot guidance?

Checked `docs/research/ai/evidence-safety-eval.md` section 2 and `docs/research/ai/llm-agents.md` first, so as
not to re-research what they already found (APA Nov 2025 advisory, FDA Nov 2025 Digital Health Advisory
Committee, Telemedicine Practice Guidelines 2020 clause 5.4 "AI must not counsel," California SB 243). New
research this pass found nothing beyond that. Specifically:

- California SB 243 regulates "companion chatbots" broadly by disclosure and required self-harm protocols;
  the disclosure duty applies whenever a reasonable user could be misled, with no separate lighter rule for
  low-stakes navigational or supportive responses as opposed to crisis handling.
- The FTC opened only a Section 6(b) information-gathering study (2025-09-11) into child/teen safety at major
  AI companion platforms; no rule yet, and no supportive/crisis tiering in it.
- The APA's Nov 2025 advisory and its 2026 follow-ups treat "mental health chatbots and wellness apps" as one
  risk category needing safeguards; it does not carve out an exemption for low-stakes supportive or
  navigational use.
- India: MeitY's Nov 2025 AI Governance Guidelines are voluntary and sector-agnostic; no Ministry of
  Education or MeitY statement specific to ed-tech/wellness chatbots was found.

**Honest conclusion:** regulators currently treat "an AI chatbot that touches mental health" as one category,
not two. There is no published basis for treating this KB's purely navigational intents (breathing, music,
goals, journal, mood_checkin, digital_detox, booking) as regulatorily lower-risk than the more
distress-adjacent ones (general_stressed, general_lonely, safety_plan, assessment) — the harm-if-wrong
ranking above is my own content-risk judgement, not a regulatory distinction I can cite.

## Recommendation

My role here is to raise the evidence basis, not to clear the gate `ai/kb.py` already sets (`review_status`
stays `draft_unreviewed`, `CHAT_ROUTER_ENABLED` defaults off in production, "for exactly this reason"). I am
not overriding that; I am informing it.

**Overall: do not enable yet, for any intent, including the best-sourced ones.** Three reasons, independent
of citation quality:

1. The KB today has exactly one snippet per intent (15 total). `SYNTHESIS.md` section 3(b) item b3's own plan
   calls for 80-150 snippets with clinician review as "the real critical path," not 15 single-sentence
   drafts. This is still clearly a first draft in breadth, not a reviewed product.
2. `SYNTHESIS.md` section 2's independent crisis evaluation set (item a1, "BUILD NOW," the prerequisite the
   synthesis says every other safety-path decision depends on) has not been built yet, as far as I can tell
   from this repo. The router only ever sees messages the floor already called `none`, which is the right
   design, but that makes the floor's own unmeasured accuracy the thing standing between a distressed
   message and a feature-navigation reply — I would not enable the downstream feature while the floor it
   depends on is still unmeasured.
3. The router/KB modules are not wired into any call path yet (see architecture check above), so there is
   nothing to "enable" in the literal sense today regardless of the KB's content.

**If forced to rank which intents could move first once the above is resolved:** booking, music,
digital_detox, journal, breathing, goals, and mood_checkin have the combination of LOW harm-if-wrong and at
least MEDIUM sourcing, and are the closest to safe-to-ship-with-a-light-touch-clinician-skim (not full
sign-off) once a1 exists and the router is wired in correctly. sleep_log is close behind but its
tracking-benefit half needs a better source or softer wording. grounding needs either a better citation or
softer wording regardless of its low current harm. **safety_plan, assessment, medication_log,
general_stressed, general_lonely, and about_privacy/delete_account's factual accuracy all need a named
human (clinician for the first five, engineering+legal for the last two) before enabling, regardless of how
the citation picture improves** — these touch self-harm-adjacent content, screening, medication, or a factual
promise about data handling, where a caveat or a citation does not substitute for a person checking the
actual claim against the actual running app.
