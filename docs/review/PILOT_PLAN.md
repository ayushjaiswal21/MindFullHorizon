# Pilot plan: one college, 8 to 12 weeks

Written: 2026-11-24, by the engineering side. A proposal for the owner, a college and its clinician to adapt.

> **Nothing in this plan has been approved by anyone.** No clinician, lawyer, ethics committee or college has reviewed it. Every target below is a proposal, not a fact (the numbers come from `docs/research/product-market.md` section 5, which marks them as proposals). Real students must not use the product until the gates in section 5 are signed by the named humans. The review states are tracked in `README.md` in this folder.

## 1. Objectives

1. **Safety first:** show that the crisis flow (detection, student-facing help, counsellor alert, escalation, follow-up) works end to end in a real campus setting without a missed alert and without harming a student.
2. **Usability and trust:** learn whether students will complete a check-in, return, and trust the app (and which words and flows put them off).
3. **Counsellor fit:** learn whether the dashboard saves counsellor time, whether alert volume is workable, and what is missing.
4. **Measurement:** collect the first real baseline for retention, completion, time-to-acknowledge and false-positive load. Institution-embedded retention is unknown today; the market median for open apps is 3.3 percent at day 30 (Baumel 2019, https://pmc.ncbi.nlm.nih.gov/articles/PMC6785720 ; cited in `product-market.md`). Do not promise numbers before the pilot.

## 2. What is and is not being tested

| Being tested | Not being tested |
|---|---|
| Screening (PHQ-9, GAD-7) flow, alert on item 9 or severe scores | Clinical effectiveness or "reduces depression" (a pilot of this size cannot show it) |
| Rule-based crisis detection in English, Hinglish, Devanagari on real traffic (reviewed after the fact, see section 9) | Detection of implicit risk (known not to work, see the clinician packet section 6) |
| The alert, escalation and acknowledgement chain, and the human SOP around it | A 24x7 monitored service (does not exist) |
| AI companion as a brief supportive adjunct | AI as therapy, counselling or prescribing (never) |
| Appointment booking with the college's own counsellors | Prescriptions, pharmacy or inventory (leave the flag off, see `LEGAL_REVIEW_PACKET.md` section 1.8) |
| Student and counsellor experience, wording, accessibility | Under-18 students (excluded), parent notification, paid tiers |
| Operations: backups, alert drill, incident runbook | Scale beyond the pilot cohort |

## 3. Site criteria

The pilot proceeds only at a site that meets all of these:

- One institution with an in-house counsellor (at least one, ideally two so that leave and shifts are covered) and a **named responsible clinician** (psychiatrist or clinical psychologist) who accepts clinical oversight in writing.
- A college contact (single point of contact, SPOC) with authority to agree the MoU, the on-call arrangement and the student briefing.
- Willingness to provide an out-of-hours arrangement for alerts (an on-call counsellor, warden or medical room) and to state it to students, or to agree that students are told there is none.
- Duration 8 to 12 weeks. A **staged cohort**: start with 20 to 30 volunteers in weeks 1 to 4, extend to a larger volunteer group only if the stop rules (section 6) have not fired and the clinical lead agrees at the week-4 review.
- **18 and older only** (self-declared at signup; no under-18 path exists). The college confirms it will not recruit 17-year-olds.
- Counsellors can attend a training session before launch and agree to log in at the check times in the SOP.
- Mobile web access for students; the institution does not block the app domain.
- No use of the pilot for student discipline, grading or any decision about a student's standing. State this in the MoU.

## 4. Roles

| Role | Person (to fill) | Responsibilities |
|---|---|---|
| Clinical lead (college's responsible clinician) | | Owns clinical decisions and the SOP; reviews every alert outcome weekly; can pause the pilot; signs the clinician review page |
| College SPOC | | Recruitment, room and poster logistics, MoU, on-call roster, student briefing, escalation to college management |
| Counsellor(s) | | Respond to alerts, follow-up per protocol, log outcomes, attend weekly review |
| Engineering on-call | | Keeps the app and job worker running, handles the incident runbook, re-runs the exporter and tests after any change, never changes detector, thresholds or wording during the pilot without the clinical lead's written approval |
| Data protection contact | | Receives student requests (export, deletion, grievance), breach triage, keeps the DPA and the data map current |
| Owner (operator) | | Named as data fiduciary or processor per counsel's advice; accountable for the legal gates |
| Evaluation lead (may be the owner) | | Runs the metrics, the weekly pack and the final report |

## 5. Pre-launch gates (all must be ticked and evidenced before the first student account is made)

Each gate names who signs. An unsigned gate is closed.

- [ ] **Clinician sign-off** on the crisis phrases, severity mapping, wording, escalation and assessment rules, as the signed page in `CLINICIAN_REVIEW_PACKET.md` section 10, with the code version (git commit and fingerprints). (Clinical lead or the reviewing clinician)
- [ ] **Legal sign-off** on the privacy notice, terms, DPA and MoU, the crisis-alert notice, the cross-border position on Gemini, and the under-18 exclusion, as the signed page in `LEGAL_REVIEW_PACKET.md` section 6. (Counsel)
- [ ] **Ethics approval** from the college's Institutional Ethics Committee if outcome data will be published or shared beyond service evaluation; or a written decision from the committee that none is needed. (IEC chair)
- [ ] **Security review**: an external penetration test, or at minimum a documented internal security review of authentication, access control, injection, secrets and the AI pipeline, with findings fixed or accepted in writing. (Engineering plus an independent reviewer)
- [ ] **Key rotation**: every secret that has ever been committed or shared (the Gemini key found in a local `.env` earlier, session secret, OAuth secrets, invite codes, SMTP password) is rotated and the old ones revoked. Evidence: dated record. (Owner)
- [ ] **Paid Gemini plan confirmed** and the terms recorded, or the chat feature switched off. (Owner)
- [ ] **Backups and restore drill**: automated database backups configured; one full restore into a clean environment completed and timed; backup retention and access stated in the privacy notice. (Engineering)
- [ ] **Uptime monitoring and alert drill**: an uptime monitor on `/health` and `/ready` with notifications to engineering on-call (`docs/OPERATIONS.md`); a drill in which a fake crisis event is created on staging and a counsellor acknowledges it, with the escalation interval set low, and the timestamps recorded. (Engineering and counsellor)
- [ ] **Out-of-hours alert path tested**: `CRISIS_ESCALATION_EMAIL` points to a monitored shared mailbox, SMTP verified by a real test email, and the on-call phone number or forwarding rule confirmed by a test. (SPOC and engineering)
- [ ] **Incident runbook** written and rehearsed: privacy incident, missed alert, dead job (`flask jobs-stats`, `/ready`), outage, wrong helpline number, harmful AI reply. Includes who tells whom within what time, and the breach-notification steps counsel provides. (Engineering and data protection contact)
- [ ] **Crisis tabletop done** with the clinician and counsellors using the 15 scenarios in `CLINICIAN_REVIEW_PACKET.md` section 8; every scenario rated; every C rating fixed or accepted in writing. (Clinical lead)
- [ ] **Counsellor training session** held (how the dashboard works, the alert SOP, what the app cannot do, documentation, who to call). Attendance list kept. (Clinical lead and engineering)
- [ ] **Student briefing and consent script** delivered and approved (section 10); information sheet printed and posted online. (SPOC and counsel)
- [ ] **Helpline posters** displayed (Tele-MANAS 14416, KIRAN 1800-599-0019, 112, plus the campus counsellor and medical room), in hostels and common areas, matching `utils/helplines.py`. Numbers re-verified on the launch date. (SPOC)
- [ ] **Engineering gap list reviewed**: the owner has decided, for each of the items in section 7.3, whether to build before launch or to accept the gap and say so in the MoU. (Owner and clinical lead)
- [ ] **Public copy check**: the landing page and in-app text contain no fake statistics, no 24x7 claim, no compliance or endorsement claim, and the draft banners on privacy and terms are still in place until counsel signs. (Owner)

## 6. Stop rules

The pilot is **paused immediately** (new sign-ups stopped; existing users keep access to helplines and counsellor booking; the college is informed the same day) if any of these happens. Resuming needs a written decision by the clinical lead and the owner, after a documented root cause.

1. **Any missed crisis alert**: a crisis event that no counsellor was told about, or that stayed unacknowledged past the final escalation level without a documented reason, or a student who disclosed risk to the app and for whom no alert exists because of a software fault.
2. **Any privacy incident**: unauthorised access, a counsellor seeing a student they are not assigned to (outside the crisis panel), exposure of student text, a lost or leaked backup, a leaked secret that was live.
3. **Any serious complaint**: a student or counsellor complaint about harm, distress caused by the app, a wrongful escalation, or a harmful AI reply.
4. A death or attempt involving a pilot participant (also report to the college and clinical lead at once, and follow the college's protocol).
5. A wrong or dead helpline number shown to a student.
6. The clinical lead or the ethics committee withdraws approval.
7. Loss of the on-call arrangement (no named person available for alerts).

Also review (not an automatic stop): alerts per counsellor per week above what the counsellors say is workable; false-positive share above the level the clinical lead set.

## 7. Crisis alert handling SOP

### 7.1 What the software does (read from the code, see `generated/safety_flow.md`)

An alert reaches every counsellor account of the institution as an in-app notification within seconds, again at 15, 30 and 45 minutes (default) while unacknowledged, and from the 30-minute step as an email to one configured address. Nobody is paged by SMS or call. There is no out-of-hours logic. The student sees the crisis card with Tele-MANAS 14416, KIRAN 1800-599-0019 and 112 immediately; the student is not told whether anyone saw the alert. No promise of 24x7 monitoring is made anywhere.

### 7.2 Proposed human SOP (to be agreed and signed by the clinical lead)

| Item | Proposal (targets, not facts) |
|---|---|
| Who is on call | A named counsellor each day (roster kept by the SPOC) with a backup; the clinical lead is the escalation. The roster is posted internally and sent to engineering |
| Working hours | Counsellor logs into the dashboard at fixed times (suggest at least at start of day, midday and end of day) and keeps the notification tab open during duty. Target from `product-market.md`: median time to acknowledge under 15 minutes and p95 under 60 minutes in working hours |
| First action | Open the alert panel, acknowledge, then contact the student by the agreed route (phone, in person via the college), using a risk screen chosen by the clinical lead (for example the Columbia protocol screener, free and askable without clinical training, https://cssrs.columbia.edu/the-columbia-scale-c-ssrs/about-the-scale/ , read 2026-11-24) |
| Out of hours | The app tells students to call Tele-MANAS 14416 and 112 and gives no assurance of monitoring. Escalation emails go to a shared mailbox that forwards to the on-call phone. If the college cannot staff nights, say so in the information sheet and the MoU; do not imply otherwise. Unacknowledged alerts are the first item the next morning |
| Documentation | Counsellor records outcome in the clinical-notes feature and in a simple log (date, time received, time acknowledged, contact made, outcome, follow-up plan). The software has no follow-up field, so this log is the record |
| Follow-up | Per the protocol the clinical lead sets. The UGC draft proposes at least three follow-up sessions after a crisis (secondary sources, draft, wording UNVERIFIED: `product-market.md` section 1.6); adopt a rule the clinician agrees |
| Repeat alerts | Each flagged message makes a new alert; counsellors acknowledge duplicates and note them as repeats |
| False positives | Counsellor marks each alert in the log as "risk confirmed", "no current risk", or "unclear"; this feeds the metric in section 9 |
| Confidentiality | Disclosure beyond the college counselling team (parents, police, warden) only as the clinical lead and counsel's advice allow; the student is told first where safe to do so |
| Failure | If the dashboard or email path is down, engineering tells the clinical lead at once and counsellors fall back to manual check-in; the pilot may be paused (stop rule 1 if an alert was missed) |

### 7.3 Engineering gaps the SOP depends on (owner to decide before launch)

1. No SMS or phone paging; email goes to one address only.
2. No merging of repeated alerts from one student.
3. No follow-up or outcome field on an alert (the manual log substitutes).
4. The crisis text does not tell the student that a counsellor was alerted.
5. No out-of-hours routing.
6. Institution matching is exact free text: confirm every counsellor and student account uses identical institution text (check before launch).
7. Encryption at rest is not implemented; backups and restore are not yet drilled.
8. Detection coverage in Hinglish and Devanagari is unvalidated.

## 8. Timeline (Gantt-style week table)

Week numbers: P1 to P8 are preparation weeks before launch; W1 to W12 are pilot weeks. Shorten to 8 pilot weeks if the college prefers: drop W9 to W12 and keep the close-out.

`X` = work happens in that week.

| Workstream | P1 | P2 | P3 | P4 | P5 | P6 | P7 | P8 | W1 | W2 | W3 | W4 | W5 | W6 | W7 | W8 | W9 | W10 | W11 | W12 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Agree site, roles, MoU outline | X | X | X | | | | | | | | | | | | | | | | | |
| Clinician review (phrases, wording, flow) | X | X | X | X | | | | | | | | | | | | | | | | |
| Legal review and DPA, notice text | X | X | X | X | X | | | | | | | | | | | | | | | |
| Ethics approval (if needed) | | X | X | X | X | X | | | | | | | | | | | | | | |
| Security review or pen test, fixes | | | X | X | X | X | | | | | | | | | | | | | | |
| Key rotation, backups, restore drill | | | | X | X | | | | | | | | | | | | | | | |
| Alert drill, runbook, tabletop | | | | | X | X | X | | | | | | | | | | | | | |
| Counsellor training, student materials, posters | | | | | | X | X | X | | | | | | | | | | | | |
| Gate review and go or no-go | | | | | | | | X | | | | | | | | | | | | |
| Cohort 1 (20 to 30 volunteers) | | | | | | | | | X | X | X | X | | | | | | | | |
| Week-4 review: continue, extend, or stop | | | | | | | | | | | | X | | | | | | | | |
| Cohort 2 (extended volunteers, if approved) | | | | | | | | | | | | | X | X | X | X | X | X | X | |
| Weekly safety and metrics review | | | | | | | | | X | X | X | X | X | X | X | X | X | X | X | X |
| Student and counsellor feedback rounds | | | | | | | | | | X | | X | | X | | X | | X | | X |
| Close-out, final report, data deletion or return | | | | | | | | | | | | | | | | | | | X | X |

## 9. Metrics, data collection and analysis

### 9.1 Metrics (all numbers are PROPOSED TARGETS from `docs/research/product-market.md` section 5, not facts or promises)

| Type | Metric | Definition | Proposed target |
|---|---|---|---|
| Safety (guardrail) | Missed alerts | Crisis events not delivered or not acknowledged without a reason | 0; any case triggers stop rule 1 |
| Safety | False-negative rate on the reviewed test set | Explicit self-harm statements in the clinician-reviewed English, Hindi and Hinglish test set not flagged | 0 missed on explicit statements; at least 95 percent on the implicit set (proposal) |
| Safety | False-positive load | Alerts per counsellor per week judged "no current risk" | Track; tune so counsellors act on over 70 percent |
| Safety | Alert follow-up completeness | Alerts with documented follow-up | 100 percent |
| Safety | Time to acknowledge | Alert created to acknowledged | Median under 15 min, p95 under 60 min in working hours |
| Safety | Complaint and harm rate | Complaints about AI replies, privacy or wrongful escalation per 1,000 active users | Under 1 per 1,000; each serious one reviewed within 24 hours |
| Privacy | Incidents | Unauthorised access, breach | 0 |
| Privacy | Data-rights turnaround | Export and deletion requests fulfilled | Within 30 days (proposal; DPDP timing to confirm with counsel) |
| Engagement | Assessment completion | Completed PHQ-9 or GAD-7 divided by started | At least 80 percent |
| Engagement | Weekly active check-ins | Onboarded students with at least one completed check-in per week | 20 to 30 percent of onboarded (market daily-active median is about 4 percent) |
| Engagement | 30-day retention | Onboarded students active in days 25 to 35 | 10 to 15 percent, to be confirmed by the pilot |
| Engagement | Time to first value | Minutes from signup to first completed screen plus a visible next step and helpline | Median under 3 minutes |
| Care loop (north star) | Closed-loop rate | Of students with a moderate-or-above score (10 or more) or a risk flag, those with a documented counsellor contact or accepted plan within 72 hours | 60 percent at pilot end |
| Counsellor | Time saved | Time-and-motion study of triage and documentation per week against baseline | 20 to 30 percent (proposal; earlier "50 percent" has no evidence) |
| Monitor | Behaviour after missed days | Change in check-ins or mood entries after a gap | Monitor; remove streak features if negative |

Do not report points or streaks as success, and never attach points or streaks to assessment or mood scores.

### 9.2 Baseline

Before launch, record with the college (no student data): number of enrolled students, counsellor headcount and hours, current number of counselling appointments per week and waiting time, how a student in crisis is currently handled, and the current out-of-hours arrangement. During weeks 1 to 2, record the app's own first-week figures as the baseline for retention and completion. Compare the pilot with the Baumel 2019 open-app figures only as context, not as a control.

### 9.3 Data collection

- **From the app (aggregate counts only, small cells suppressed at 5):** sign-ups, check-ins per week, assessment starts and completions, alerts, acknowledgement times, escalation levels reached, appointment bookings. Pulled by a query or script run by engineering, stored in a spreadsheet without student ids.
- **From counsellors (the alert log, section 7.2):** outcome category and follow-up completeness per alert, with no student identifiers in the shared copy.
- **Surveys:** a 5-question anonymous survey at weeks 2, 6 and 12 (usefulness, safety feeling, wording, trust, what to change) on a separate form, with no link to accounts.
- **Interviews:** 6 to 8 voluntary 20-minute interviews with students and every counsellor at the end.
- **Review of flagged messages:** the app does not store chat text; journal text is private to the student. To check detector performance, the clinical lead reviews only text that students voluntarily share (for example through the survey or contact form, with consent), and engineering never reads student text. If a larger audit is wanted, design it with counsel and ethics approval first.
- **Never collect:** names, emails or ids in any analysis file; message text in logs or spreadsheets.

### 9.4 Analysis plan

Descriptive only: counts, medians, ranges, with the denominator in every table. Weekly pack (section 11). A paired before-and-after PHQ-9 or GAD-7 comparison is allowed only for students with at least two completed assessments, reported as descriptive, never as an effect. No claim of clinical benefit, causation or generalisation. Publish only after ethics approval, with the limits stated.

## 10. Communication templates

### 10.1 Student information sheet (outline; counsel and the clinical lead to finalise)

1. **What this is:** a pilot of MindFull Horizon, a web app from [operator name] offering mood check-ins, PHQ-9 and GAD-7 screening, a journal, wellness exercises, an AI companion and booking with the college's counsellors. It runs from [date] to [date].
2. **What it is not:** not a diagnosis, treatment or emergency service. The AI companion is an AI, not a person or therapist and can be wrong. **Nobody watches the app around the clock.** If you or someone else is in danger call 112. Free support: Tele-MANAS 14416, KIRAN 1800-599-0019 (24x7). Campus counsellor: [contact]. Medical room: [contact].
3. **Who can join:** students aged 18 or older who volunteer. Joining or not joining has no effect on your studies or standing.
4. **What we collect:** list from the privacy page. Say clearly what is sent to Google's Gemini service for AI features, that your name and email are not sent, and that the crisis check is a fixed set of rules.
5. **Who can see what:** you see everything in your account. Your assigned counsellor sees your screening, mood and check-in data. Journal text and voice logs are not shown to counsellors. **If the safety check finds language about harming yourself, or a screening answer or score shows possible risk, an alert is sent to the counsellors at your college so someone can reach out.** The alert does not contain your words. [Wording to be settled with the clinician and counsel.]
6. **Your choices:** download your data and delete your account at any time (account data page); withdraw consent; contact the data protection contact [name, email]; complaints to [grievance officer].
7. **Risks and benefits:** possible benefit is an early nudge to talk to someone; possible risks are distress when answering questions, a false alarm or a missed alarm, and privacy risks. We will stop the pilot if serious problems occur.
8. **Contact for questions:** SPOC, clinical lead, engineering contact.

### 10.2 Consent text (outline)

- I am 18 or older and I volunteer.
- I have read the information sheet and the privacy notice (version [x]).
- I understand the app is not an emergency service and nobody monitors it around the clock.
- I understand that an alert may be sent to the counsellors at my college if the app finds possible risk, and what the alert contains.
- I understand my text may be processed by Google's Gemini service for AI features.
- (Only if outcome data will be used for research and ethics approval exists) I agree that anonymised, aggregate results may be used in a report. Optional, separate box.
- I know I can withdraw and delete my account at any time.

The consent screen in the app already stores version and time (`ConsentRecord`); the information sheet above is given in addition, in person or by link.

### 10.3 Counsellor briefing (one page)

How alerts appear and when; the escalation timeline and that nobody is paged; how to acknowledge; the SOP and documentation log; what the app cannot detect (implicit risk, some Hinglish); what false positives look like; what you may and may not do with student data (assigned students only; the open-alerts panel shows name, source, severity and time); how to record an outcome; who to call (clinical lead, engineering on-call, data protection contact); how to report a problem; that you are the clinician, the app only triages.

### 10.4 College MoU outline (counsel to draft)

1. Parties and purpose; pilot period and cohort; non-clinical status of the software.
2. **Data roles:** who is data fiduciary and who is processor (as counsel advises), purposes, the data map, sub-processors (Google Gemini, hosting, SMTP), cross-border statement, security measures, breach notice and contacts, deletion and return on exit.
3. Responsibilities: clinical lead named; counsellor roster; on-call and out-of-hours arrangement stated honestly; the college owns clinical decisions and any reporting duties; the vendor owns the software and its operation.
4. Student protections: 18 and over only; voluntary; no academic consequences; information sheet and consent as above.
5. Service levels: target availability, support hours, response times for incidents, an explicit statement that alerts are a triage aid and not a monitored emergency service.
6. Stop rules and the right of either party to pause (section 6).
7. Research and publication: ethics approval, who may publish, anonymity, review before publication.
8. Intellectual property, confidentiality, publicity (no use of the college's name without written consent).
9. Liability cap and indemnities (counsel), insurance.
10. Term, termination and exit plan (section 12), governing law and jurisdiction city.

## 11. Weekly review cadence and feedback

- **Weekly safety review** (30 minutes; clinical lead, counsellors, engineering, SPOC as needed): every alert of the week with its acknowledgement time, outcome and false-positive category; any complaints; any stop-rule trigger; app incidents; helpline check; open actions. Written minutes, no student identifiers.
- **Weekly metrics pack** (engineering): the section 9.1 table with denominators, drawn from aggregate counts.
- **Monthly decision point** (weeks 4, 8, 12): continue, extend, adjust or stop, signed by the clinical lead and owner.
- **Feedback channels:** anonymous survey link in the app footer and on posters; the contact form (stored and read by the team, answered within an agreed time); counsellor feedback in the weekly review; two short interview rounds; a simple "report a problem" email monitored by engineering. Changes to detector, thresholds or wording only through the change-request log in the clinician packet.

## 12. Exit and data deletion plan

1. At pilot end or on a stop: close new sign-ups; show a notice with the helplines and the date the service ends.
2. Offer every student a data export and a reminder that they can delete their account; delete accounts on request within the agreed time.
3. Aggregate results are kept only in anonymised form (counts, no ids).
4. The college receives its data in an agreed format (counsellor notes it wrote are the college's records under the MoU as counsel decides); the operator confirms deletion of the rest in writing, including the system backups after the stated retention period, and removes the college's counsellor accounts and invite code.
5. Rotate secrets used for the pilot. Keep only what counsel says must be kept (for example the audit log and consent records) for the stated period.
6. Written close-out report to the college, clinical lead and ethics committee (if any).

## 13. Risk register (top 15)

Likelihood (L) and impact (I): Low, Medium, High. Mitigations are proposals. Owner roles are from section 4.

| No. | Risk | L | I | Mitigation | Owner |
|---|---|---|---|---|---|
| 1 | A real crisis is missed because the detector does not recognise the wording (implicit, Hinglish, Devanagari, sarcasm) | High | High | Clinician and native-speaker review; honest information sheet; helplines on every page; counsellor outreach, not only the app; review of detector performance; do not claim detection | Clinical lead |
| 2 | An alert is created but no counsellor sees it in time (in-app only, nobody paged, out of hours) | High | High | SOP with fixed check times, shared mailbox with phone forwarding, alert drill, decision on SMS or paging before launch, stop rule 1 | SPOC and engineering |
| 3 | False positives overload counsellors; alert fatigue | Medium | Medium | Track false-positive share; clinician tuning; merge repeats (engineering gap 2); weekly review | Clinical lead |
| 4 | Privacy incident: counsellor sees an unassigned student, a leak, plaintext health data exposed | Low | High | Assignment rule tests, audit log review, security review, secret rotation, encryption at rest decision, runbook, stop rule 2 | Engineering and data protection contact |
| 5 | The AI companion gives a harmful, wrong or over-confident reply | Medium | High | Prompt rules, output filter, fixed text on risk paths, tabletop, complaint channel, pause rule, option to run with chat switched off | Engineering and clinical lead |
| 6 | Misleading claims in marketing or consent (24x7, confidentiality, compliance) | Medium | High | Public copy check, counsel review, claims list in `product-market.md` section 8 | Owner |
| 7 | Legal gap: fiduciary role, consent, cross-border transfer to Gemini, MHCA confidentiality unresolved | Medium | High | Legal sign-off gate, DPA, paid-tier terms, chat off until resolved | Owner and counsel |
| 8 | Under-18 student gets in (self-declared gate only) | Medium | High | College confirms eligibility; counsellor-issued access; clear information sheet; rapid account closure | SPOC |
| 9 | Helpline numbers wrong or out of date | Low | High | Verify on launch date and quarterly; one config file; posters match the app | Engineering |
| 10 | Outage or job worker stopped: alerts not created or not escalated | Medium | High | Uptime monitor on `/health` and `/ready`, stale-jobs alarm, restart procedure, backup drill, manual fallback | Engineering |
| 11 | Data loss with no restore | Low | High | Automated backups and a timed restore drill before launch | Engineering |
| 12 | Counsellor capacity or leave leaves no one on call | Medium | High | Roster with backup, clinical lead as escalation, pause rule when no on-call | SPOC |
| 13 | Low engagement makes the pilot uninformative | High | Low | Realistic targets, onboarding with counsellor introduction, feedback rounds; low engagement is a finding, not a failure | Evaluation lead |
| 14 | Students or staff over-rely on the app and its scores (screening mistaken for diagnosis) | Medium | Medium | Briefing, wording, counsellor training, "screening not diagnosis" everywhere | Clinical lead |
| 15 | Ethics or regulatory objection mid-pilot (research use, medical-device classification, telemedicine rules) | Low | High | Ethics gate, counsel answers to L9 to L11, keep prescriptions off, no outcome claims | Owner |

## 14. Budget outline (template: no amounts are invented here)

Fill with real quotes. Leave a line blank if it does not apply. Currency and period to be set by the owner.

| Item | Basis (to fill) | Amount | Who pays | Notes |
|---|---|---|---|---|
| Clinical review (psychiatrist or clinical psychologist) | hours or fixed fee | | | Includes Hindi and Hinglish phrase review |
| Native-speaker reviewers (Hindi, Hinglish) | | | | |
| Legal review and drafting (policies, DPA, MoU, research consent) | | | | |
| Ethics committee fee, if any | | | | |
| Security review or penetration test | | | | |
| Hosting, database, backups, monitoring | per month | | | Paid tier needed for backups and reliability |
| Gemini API (paid plan) | per usage | | | Required, see legal gate |
| SMTP or SMS provider (alert email, optional paging) | | | | |
| Domain and TLS | | | | |
| Insurance (professional indemnity, cyber) | | | | |
| Engineering time (build gaps, on-call, support) | hours | | | |
| Counsellor time (training, alerts, follow-up, weekly review) | hours | | | Usually the college's cost |
| Student materials (posters, printing, briefing session) | | | | |
| Incentives for survey and interview participants, if any | | | | Ethics committee to approve |
| Evaluation and reporting | | | | |
| Contingency | | | | |
| **Total** | | | | |
