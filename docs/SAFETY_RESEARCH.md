# Safety research notes (Nov 2026)

Source: research pass with web sources. **Not clinical or legal advice.** Phrase lists below are constructed test fixtures, not a validated corpus: have a clinician and Hindi speakers review them before launch.

## Screening scores (screening tools, not diagnosis)

**PHQ-9**: 9 items, each 0-3, total 0-27. Bands: 0-4 minimal, 5-9 mild, 10-14 moderate, 15-19 moderately severe, 20-27 severe. Score >= 10 is the usual "needs follow-up" cut-off. Sources: https://pmc.ncbi.nlm.nih.gov/articles/PMC1495268/ , https://hiv.uw.edu/page/mental-health-screening/phq-9

- Item 9 (thoughts of being better off dead / self-harm) counts "if present at all". **Project rule (our inference, not an official rule):** item 9 >= 1 is positive regardless of total: show crisis resources and flag for provider immediately. A skipped item 9 is "unanswered", never 0.
- The functional-difficulty question is separate and not part of the total. Copy its exact wording from the official form before shipping.

**GAD-7**: 7 items, each 0-3, total 0-21. Bands: 0-4 minimal, 5-9 mild, 10-14 moderate, 15-21 severe. Cut-off >= 10 for further evaluation (>= 8 is a more sensitive option). Source: https://www.hiv.uw.edu/page/mental-health-screening/gad-7

## Crisis-text handling

A safe response: empathic acknowledgement, helplines shown prominently (112 for immediate danger), prompt to reach a trusted person, no promise of confidentiality that cannot be kept, no method/means details, no debate of reasons. After a crisis flag stop gamification and cheerful prompts and keep a human-escalation path. Guidance: https://who.int/publications/i/item/9789240076846 , https://afsp.org/how-to-talk-safely-about-suicide/

Keyword-only detection fails on negation and on code-mixed Hinglish (https://pmc.ncbi.nlm.nih.gov/articles/PMC5732584 , https://aclanthology.org/2021.icon-main.14).

**Chosen design**
1. Normalize: lowercase, collapse repeated characters, map spelling variants (hu/hun/hoon, nahi/nahin/nhi), normalize apostrophes.
2. Word-boundary regex over the high-risk list.
3. Negation window of ~4 tokens before the hit ("don't", "never", "not", "nahi", "mat"). A negated hit is **downgraded to a soft check-in, not dropped**.
4. LLM classifier on any hit or ambiguity.
5. **Fail conservative:** if the classifier errors or times out, a regex hit still shows the crisis card.

### Fixtures: must trigger (English)
i want to die · i wanna die · i want to kill myself · i'm going to kill myself · i am going to end my life · i want to end it all · i'm ending it tonight · i can't go on anymore · i don't want to be alive · i don't want to live anymore · i wish i were dead · i wish i would not wake up · everyone would be better off without me · i'm a burden and should disappear · i have a plan to kill myself · i've been thinking about suicide · suicidal thoughts every day · i'm going to hurt myself · i keep cutting myself · i took too many pills · thinking of overdosing · i want to jump off the roof · i'm going to hang myself · i don't see any reason to live · life is not worth living · i'm done with everything, goodbye forever · this is my last message · i can't take it anymore, i want out permanently · i'd be better off dead · i'm planning to kill myself after exams

### Fixtures: must trigger (Hinglish / romanized Hindi)
mar jana chahta hu · mar jana chahti hu · mujhe marna hai · jeena nahi chahta · jeene ka mann nahi hai · ab jee nahi sakta · khud ko khatam kar lunga · khud ko khatam karna hai · apni jaan dena chahta hu · main suicide karunga · sab khatam kar dena hai · mere jaane se sab theek ho jayega · zindagi se thak gaya hu, marna chahta hu · main kisi ko dikhai nahi dena chahta, hamesha ke liye · khudkushi karne ka mann hai

### Fixtures: must NOT trigger the crisis card
i'm killing it at the gym · dying of laughter · i could die for pizza · i'd kill for a coffee · my phone died · main to hans hans ke mar gaya · mera phone mar gaya / battery mar gayi
Ambiguous, route to a soft check-in (not the crisis card): "this exam is killing me" · "i don't want to die" (negated).
Third-party ("she told me she wants to die, how can I help her?") goes to a "helping a friend" response, not the self-crisis flow.

## India helplines (keep in ONE config with a "last verified" date; re-check quarterly)

| Service | Number | Status |
|---|---|---|
| Tele-MANAS (Govt. of India) | 14416 or 1-800-891-4416, 24x7, ~20 languages | verified via PIB release (official site not fetchable) |
| KIRAN (Min. of Social Justice) | 1800-599-0019, 24x7 | verified via PIB (some pages print 1800-500-0019: likely typo) |
| Emergency | 112 | verified (MHA/ERSS) |
| iCall (TISS) | 9152987821 | number verified; hours conflict, show "Mon-Sat, check site for hours" |
| Vandrevala Foundation | +91 9999 666 555 | secondary sources only: UNVERIFIED on official site |
| AASRA | 022 2754 6669 | verified on https://aasra.info/helpline.html. Do NOT use 9820466726 (unverified) |

Default in-app list: Tele-MANAS 14416, KIRAN 1800-599-0019, 112.

## Privacy / regulation (secondary sources, get counsel before launch)

- DPDP Act 2023 and Rules 2025 (notified Nov 2025; most duties apply from ~mid-2027): free, specific, informed consent with notice; purpose limitation; withdrawal of consent; breach notification to the Board and users.
- Under-18 users need verifiable parental consent and no behavioural tracking (s.9). Many first-year students are 17 or younger, so plan an **age gate**.
- Mental Healthcare Act 2017 s.23-24: confidentiality of mental-health information; disclosure allowed for care, to prevent harm or threat to life, or under legal order. Whether it binds a wellness app is unverified; treat it as the standard to meet.

## Gamification rules for this product

- No loss-framed streak messages; allow pauses and rest days.
- Never attach points, badges or leaderboards to PHQ-9/GAD-7 or mood scores, or to disclosing distress.
- Suspend celebratory UI after a crisis flag or a high score; keep notifications neutral and optional.
