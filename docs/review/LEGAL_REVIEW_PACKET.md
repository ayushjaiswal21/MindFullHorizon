# Legal review packet: for Indian counsel

For: a lawyer (or team) with data-protection, health-law and technology-contract experience in India, asked to advise on a college pilot of MindFull Horizon.
Written: 2026-11-24, by the engineering side, from the code and docs in this repository.

> **Status: no legal review has been performed.** This document is a fact sheet and a list of questions. It contains no legal conclusions. Every statute, rule, section number, date and judgment named below was taken from secondary sources or memory unless a primary text is explicitly said to have been read; none was read in primary form while preparing this packet. Items are marked **UNVERIFIED** where we could not read the primary text. The public Privacy Policy and Terms pages are drafts written from the app's behaviour and are marked "Draft pending legal review" in the app. Nothing here is advice and nothing here may be shown to a college or a student as legal approval.

Related documents: `docs/PRIVACY_AND_CONSENT.md` (what the code does about personal data, with the data map), `docs/research/product-market.md` section 6 and section 8, `docs/research/llm-security.md` section 4, `docs/CLINICAL_DESIGN.md` and `docs/research/prescribing-inventory.md` (prescribing and inventory design), `docs/PRD.md` section 9 (compliance matrix) and section 13 (open questions), `docs/SAFETY_RESEARCH.md`. The generated files in `docs/review/generated/` (safety flow, prompt snapshot, helplines) state the live behaviour of the crisis flow; copy the git commit from `generated/MANIFEST.md` into any advice so it refers to a known version.

## 1. Facts of the product

### 1.1 What it is

A web app (Flask, a database, a background job worker) for college students in India and the counsellors of their institution. Students (18 and older only, by self-declared checkbox) log mood, complete PHQ-9 and GAD-7 screening questionnaires, keep a journal, make voice logs, chat with an AI companion ("Anya", powered by Google Gemini through an API), use wellness exercises, set goals, record medication reminders, and book appointments (including video sessions) with a counsellor at their institution. Counsellors see assigned students and open crisis alerts. A public site has a landing page, blog, contact form, privacy and terms pages.

It is described in the product's own copy as a screening and support tool, not a diagnosis, treatment or emergency service. The operator is not yet named in the product (`DATA_FIDUCIARY_NAME` is unset).

### 1.2 Roles of the parties (current facts, not conclusions)

| Party | Facts |
|---|---|
| Operator (the entity running the app) | Not yet incorporated or named in the product. An early-stage project; source code is public on GitHub. Decides purposes and means of processing in practice. Holds the database and can read stored data technically |
| Student (user, 18+) | Creates an account by self-signup (email and password, or Google sign-in). Self-declares age and accepts the privacy notice at signup |
| Counsellor (provider role) | Creates an account with an invite code from the institution (`PROVIDER_INVITE_CODE`). Sees only assigned students, plus open crisis alerts of the institution |
| Institution (college) | Not a user type in the software. Counsellors and (in future) an admin act on its behalf. Provides the invite code, the counsellors and the out-of-hours arrangement |
| Doctor (provider with `provider_type = doctor`) | Designed, not built (section 1.8) |
| Admin | Designed, not built (section 1.8) |

Who is the data fiduciary (the operator, the college, or both) and who is a processor is an open question for counsel (question L1).

### 1.3 Data categories and where they go

| Category | Examples | Stored? | Who can read it in the app |
|---|---|---|---|
| Account | name, email, institution (free text), role, hashed password or Google account id, consent timestamps | yes | the user; assigned counsellors see name and email |
| Screening | PHQ-9 and GAD-7 answers, totals, bands, AI explanation text | yes | the user; assigned counsellors |
| Mood and check-ins | mood ratings and notes, daily check-in series | yes | the user; assigned counsellors |
| Journal | title, text, sentiment label, AI suggestion | yes | the user only (counsellor pages show no journal text) |
| Voice logs | audio file, transcript, emotion label, audio measurements, AI analysis | yes | the user only |
| AI chat | messages and replies | **not stored** by the code (no chat table; `routes/auth.py` states chat has no stored messages); text is sent to Gemini to produce a reply | transient. See discrepancy 1 in section 9 |
| Crisis records | time, source (chat, phq9, journal), severity number, short reason code. No message text | yes | counsellors of the institution while unacknowledged, assigned counsellors afterwards |
| Appointments | time, counsellor, status, patient note, modality | yes | patient; the booked counsellor |
| Clinical notes | counsellor session notes, optional pasted transcript | yes | the writing counsellor (and assigned counsellors) |
| Medication reminders | names the student types, adherence log | yes | the user; assigned counsellors (adherence) |
| Prescriptions | behind a feature flag (section 1.8) | yes when enabled | patient; prescribing provider |
| Wellness activity | breathing, yoga, music logs, goals, gamification points | yes | the user; aggregates |
| Contact form | name, email, subject, message | yes | operator |
| Audit log | actor id, action, target type and id, ids and codes | yes | operator |
| Consent records | kind (privacy, age18), version, time | yes | the user (export); operator |
| First-party analytics | event name, page path, UTM labels; no user id, no IP; consent-gated | yes | operator |
| Technical | IP address (rate limiting, server logs), session cookie (login), theme and preference items in the browser | logs on the server | operator |
| Background jobs | ids only, status, error codes | yes | operator |

Health data is stored in plain text in the database; there is no field-level or at-rest encryption yet (tracker item O-04). The product must not and does not claim encryption.

### 1.4 Processors and recipients (named from the code and docs)

| Recipient | What it receives | Notes for counsel |
|---|---|---|
| Google (Gemini API) | The text of each AI feature: chat message (cleaned, up to a length cap), journal title, text and sentiment, screening type, score and answers, goal, medication-log and mood summaries, voice transcript and audio measurements, counsellor-pasted transcripts for note drafting. The app does not send name, email or user id. Crisis-flagged journals and flagged assessments do not go to the model (fixed text instead); flagged chat messages do go to the model | Gemini terms for unpaid versus paid use differ: unpaid services may use content to improve products and humans may read it; paid services do not use it for training (https://aistudio.google.com/docs/terms , fetched 2026-11-24 per `docs/research/llm-security.md`; retention length UNVERIFIED). The deployment must use a paid, billing-enabled key: unconfirmed. Processing location and cross-border transfer: UNVERIFIED |
| Hosting provider | The whole database and files. Docs mention Render and Docker; region and provider are not fixed | Operator task: name provider and region |
| SMTP provider (optional) | Contact-form messages; crisis escalation emails (institution name, event id, time) | Operator task: name the provider, or state that none is used |
| Google sign-in (optional) | Name, email, Google account id | |
| Content delivery networks | Browsers fetch libraries from cdnjs (Cloudflare), cdn.socket.io and jsDelivr, so those hosts see visitor IP addresses | Disclosed in the draft policy |
| Object storage for audio (optional, `AUDIO_BASE_URL`) | Public wellness audio tracks, not student data | Licence of the audio content has not been checked (question L22) |

### 1.5 Flows relevant to law

- **Consent and age gate:** signup needs two ticked boxes verified on the server: privacy notice accepted, and 18 or older. Both are stored in `ConsentRecord` (kind, version from `CONSENT_VERSION`, UTC time). A version bump forces re-consent for users who already have records. Under-18 users are not supported; there is no parental-consent flow and no age verification beyond the box (`routes/auth.py`, `docs/PRIVACY_AND_CONSENT.md` section 5).
- **AI disclosure:** the chat and the `/ai` page state that Anya is an AI and not a therapist, what is sent to the model and the limits of the crisis check. The system prompt tells the model it is an AI, not a human, doctor or therapist, to avoid diagnosis, medicine names and doses, and not to promise confidentiality or outcomes.
- **Crisis alerts to institution counsellors:** when a rule-based check, a model severity or a PHQ-9 rule flags risk, an alert (no message text) is shown to every counsellor account of the same institution text, re-notified at 15, 30 and 45 minutes (default) and optionally emailed to one address. Every view of the open-alerts panel and every acknowledgement is audited. The student is told in the privacy draft that counsellors see alerts; the crisis text itself does not say so. Full step list: `generated/safety_flow.md`.
- **No 24x7 service:** nobody is paged. The Terms draft says "nobody watches the app around the clock".
- **Access control:** a counsellor sees an individual student's data only if an assignment exists (created when the student books that counsellor). Institution-level figures are aggregates with small groups suppressed (default group minimum 5). Not-assigned lookups return 404.
- **Audit log:** counsellor views of a patient report, the alert panel, acknowledgements, clinical notes, exports, deletions, prescriptions and assignments are recorded with ids and codes only. Retention of the audit log is not set.
- **Export and deletion:** a logged-in user can download a JSON export (`POST /account/export`, audited, rate-limited) and delete the account (`POST /account/delete`, password or typed phrase, cascade delete, files removed, one audit row remains). Deletion does not reach database backups or the log file. Counsellor-written clinical notes about a student are deleted with the student (cascade), and are not included in the student's export.
- **Retention:** "until deletion" for almost everything; no automatic deletion job exists; periods are not set (`PRIVACY_AND_CONSENT.md` section 8).
- **Contact form:** every message is stored first; sending email is a background job; if SMTP is not configured the page says the message was saved and will be read by the team.
- **First-party analytics:** consent-gated page events with no user id or IP; no third-party analytics scripts.
- **Security measures present:** TLS and secure cookies in production configuration (depends on hosting), password hashing, CSRF protection, rate limiting, a content security policy with nonces, role and ownership checks on routes with tests, no patient text in logs, a log filter that masks emails and tokens. Not present: encryption at rest, external penetration test, formal backup and restore drill, breach-notification runbook (see the pilot plan gates).

### 1.6 Minors

18+ only, by self-declaration. A first-year student may be 17. The DPDP rules on children (verifiable parental consent, no behavioural tracking) are the strictest reading we designed against; the product avoids the problem by excluding under-18s. Counsel to confirm whether a self-declared age gate is adequate and what the college must do for 17-year-old first-years (question L6).

### 1.7 Advertising and public claims

The landing page and the product copy are written under rules in `docs/research/product-market.md` section 8: no "diagnoses", "clinically proven", "24x7 monitoring", "100 percent confidential", "DPDP compliant", "endorsed by" claims, no fake statistics or testimonials. The landing page was found to contain placeholder statistics and testimonials in the earlier audit (`docs/STATUS.md`); whether they have all been removed in the current build must be checked on the live page before any outreach. Comparative claims about competitors: none intended.

### 1.8 Prescriptions and pharmacy inventory (designed, not built)

`docs/CLINICAL_DESIGN.md` is a design contract for a doctor role (verified prescriber), prescriptions, a medicine catalogue with Telemedicine Practice Guidelines list membership as verified data, an inventory ledger and a pharmacy desk that dispenses. At the time of writing `models.py` contains only a basic `Prescription` table; there are no `Medicine`, `PrescriberProfile` or inventory tables and no admin role, so the module is not built. Prescription routes are behind `ENABLE_PRESCRIPTIONS` (decision P-01: default off, return 404). The design document says the flag should flip to on (decision C-11); that conflicts with P-01 and the owner has not resolved it (discrepancy 4, section 9). The design blocks Telemedicine List C, Schedule H1, Schedule X and NDPS medicines and states that no drug-interaction check is built or claimed. Prescriber verification is a manual lookup with an evidence note, because no official NMC API was found (`docs/research/prescribing-inventory.md` section 2). Counsel is asked whether the module should be built at all for the pilot, and if so under what licences (questions L10 to L12). Recommendation from engineering: leave it off for the pilot.

### 1.9 Telehealth

A video session room exists (WebRTC signalling over Socket.IO). We have not verified whether any session is recorded: the code read for this packet does not record, but the reviewer of the code should confirm before the telemedicine question (L9) is answered.

## 2. Questions for counsel

Each question names the instrument. "UNVERIFIED" means we have not read the primary text. Please answer in writing, say what you relied on, and mark anything you could not confirm.

### A. Data protection (DPDP Act 2023 and DPDP Rules 2025)

Primary sources: Act text https://www.indiacode.nic.in/bitstream/123456789/22037/2/a2023-22.pdf (listed in `docs/research/llm-security.md`, not read); Rules notified mid-November 2025 (secondary summaries: https://www.scconline.com/blog/post/2025/12/26/digital-personal-data-protection-rules-2025-key-highlights/ , https://www.legal500.com/firms/237811-saga-legal/c-india/news-and-developments/the-privacy-timer-starts-now-analysing-the-dpdp-rules-and-its-18-month-countdown). The phased start dates differ between sources; we assumed most duties apply from about mid-May 2027 and designed to the stricter reading. Which duties apply today: UNVERIFIED.

- **L1. Fiduciary and processor.** Who is the Data Fiduciary for a student's data in the pilot: the operator, the college, or joint fiduciaries? Is the operator a processor for the college? Does the answer differ for data the student gives directly (journal, mood) versus data the college's counsellors enter (notes)? What contract terms follow?
- **L2. Notice and consent.** Is the signup checkbox plus the privacy page an adequate notice and consent, or is a separate, itemised notice required per purpose (screening, AI processing, sharing with counsellors, analytics)? Is the notice required in languages other than English (Eighth Schedule languages)? What must a consent record contain? Is our `ConsentRecord` (user, kind, version, time) enough? Is consent withdrawable "as easily as it was given", and does withdrawal require deleting the whole account as the draft says?
- **L3. Legitimate uses and the crisis alert.** The crisis alert shares the existence of a risk flag (not the student's words) with the institution's counsellors without a fresh consent at the moment of the alert. Does the DPDP Act provide a lawful ground for that (consent at signup, or a "legitimate use" for responding to a medical emergency or threat to life)? The Act's section on legitimate uses and the exact wording of the medical emergency ground: UNVERIFIED, recalled from memory. How should the signup notice describe it?
- **L4. Sensitive data.** The Act reportedly has no separate "sensitive" category (UNVERIFIED), but mental-health data is high risk. Are there additional duties or best practices counsel recommends, and does this make the operator a Significant Data Fiduciary (section on SDF designation and Rule on annual DPIA, audit and data localisation: UNVERIFIED)?
- **L5. Rights and grievance.** Are the export and delete flows enough for the rights of access, correction and erasure, and nomination? What turnaround must we promise? Who must be the grievance officer and what must be published? Our draft asks for a response period; none is set. Do the rules require retaining logs for a minimum period (secondary sources say one year, Rule 8(3) UNVERIFIED) and does that conflict with erasure?
- **L6. Children.** Is a self-declared 18+ gate adequate for the pilot? What must the college do for students aged 17? Is there an exemption for educational or healthcare establishments from verifiable parental consent (conflicting secondary reports, `docs/research/product-market.md` section 6.1, UNVERIFIED)? Does the ban on behavioural monitoring of children matter if we exclude them?
- **L7. Breach notification.** What are the duties and timelines to the Board and to individuals (72 hours to the Board in secondary sources, UNVERIFIED)? What must a breach runbook contain? Does a crisis-alert or consent-record failure count?
- **L8. Cross-border transfer and Gemini.** Text is sent to Google's Gemini API, with processing location unspecified. Is that a restricted transfer (section on transfers to notified countries: UNVERIFIED)? What clauses do we need from Google (data processing terms, paid-tier terms, no training, retention)? Should the product warn students not to type third-party personal data (the privacy copy already does)? Should the chat be switched off until a paid-tier agreement is confirmed?

### B. Health law and professional regulation

- **L9. Telemedicine Practice Guidelines 2020 (MoHFW and NMC).** The guidelines are reported to bar AI and machine-learning platforms from counselling patients or prescribing, allowing them only to support a registered medical practitioner (clause 5.4 per secondary sources; the official PDF could not be opened on 2026-11-24, UNVERIFIED). Does the AI companion, which gives supportive conversation but not counselling or diagnosis by design, fall inside this restriction? What wording must the product and the college avoid ("counsellor", "therapist", "AI counsellor")? Does the counsellor-facing note-drafting feature (an AI draft that a clinician edits) raise any issue? Do psychologists and social workers using the app need to follow the guidelines at all (they apply to registered medical practitioners)?
- **L10. Mental Healthcare Act 2017.** Section 23 gives a right to confidentiality for mental-health information, with exceptions; the exceptions as they apply to crisis alerts, and whether the Act binds a wellness app or an institution's counsellors, are UNVERIFIED (`docs/research/product-market.md` section 6.2; Act PDF https://qps.nhsrcindia.org/sites/default/files/2022-01/THE%20MENTAL%20HEALTHCARE%20ACT%2C%202017.pdf not read). Questions: Is sending an alert (not content) to counsellors of the same institution within the exceptions? May a counsellor or the college inform parents, a warden or police, and under what conditions (the UGC draft proposes informing parents in crisis)? Does section 115 (a person attempting suicide presumed under severe stress and not punished) require anything of crisis messaging beyond not implying punishment? Are mental-health establishment registration or other duties triggered by providing the software to counsellors? Is a counsellor's session note a "mental health record" with access and retention rules?
- **L11. Medical device rules (CDSCO, Medical Devices Rules 2017).** Is a PHQ-9 and GAD-7 screening and triage tool with a risk flag a medical device or software as a medical device under these rules? What intended-use statements keep it outside, if it can stay outside (README says "not a medical device"; CDSCO position UNVERIFIED, `docs/research/product-market.md` section 6.4)? Does the counsellor dashboard's risk ranking ("clinical decision support") change the answer?
- **L12. Drugs and Cosmetics Act 1940 and Rules 1945, NDPS Act 1985, Pharmacy Practice Regulations 2015.** Only relevant if the inventory and dispensing module is built or enabled. Questions: If a college runs a pharmacy counter on this software, what licences, registers (for example Schedule H1 records) and pharmacist supervision apply? Is it lawful for software to hold stock and dispensing records and to let a "pharmacy desk" user dispense? Does listing medicines in a catalogue or issuing digital prescriptions make the operator an e-pharmacy under any rule or draft rule (UNVERIFIED)? Our design blocks List C, H1, X and NDPS medicines and states "no interaction check"; is that sufficient? Prescribing: what must a prescription contain, how must the prescriber be verified, and what is the operator's liability for a wrongly verified prescriber (manual check of the NMC register with an evidence note)?
- **L13. Professional titles.** The UI says "counsellor" for staff; the Supreme Court in Amit Kumar asks that the term not be used indiscriminately (as reported). What credential verification must we display or keep? Who verifies counsellors: the college?

### C. Information technology law and incident reporting

- **L14. IT Act 2000 and the SPDI Rules 2011.** Do section 43A and the Sensitive Personal Data or Information Rules (which list mental health condition and medical records as sensitive, recalled, UNVERIFIED) apply in parallel with, or until replaced by, the DPDP regime? What "reasonable security practices" must be documented (the Rules mention ISO 27001 or an approved code)? What does a written privacy policy under those Rules require beyond the draft?
- **L15. CERT-In directions of 28 April 2022 under section 70B.** They reportedly require reporting specified cyber incidents within six hours and keeping logs for 180 days within India (we tried to read https://www.cert-in.org.in/PDF/CERT-In_Directions_70B_28.04.2022.pdf on 2026-11-24 but the PDF text could not be extracted; the figures are from general knowledge and must be treated as UNVERIFIED). Does the operator fall within the directions? Where must logs be stored? Our application log excludes patient text, but is the 180-day retention compatible with deletion duties?

### D. Advertising and consumer law

- **L16. Consumer Protection Act 2019, CCPA guidelines on misleading advertisements and endorsements, and the ASCI code.** Review the public copy: landing page, blog, how-it-works, any claims about outcomes, confidentiality, "safe", "private", "AI support 24x7", Hindi and Hinglish support, comparisons with other services. Which of our "claims we must not make" (product-market section 8) are legally required and which are only prudence? Are there dark-pattern issues under the 2023 guidelines on dark patterns (UNVERIFIED) in the consent or cookie banner? Does the gamification (points, streaks on non-assessment activities) raise any issue?

### E. Institution duties and our role as a vendor

- **L17. Supreme Court directions and UGC draft.** Sukdeb Saha v. State of Andhra Pradesh (25 July 2025, bench of Vikram Nath and Sandeep Mehta, JJ.; interim guidelines on institutional mental-health policy, counsellors, referral protocol, helplines, training, anonymised records and annual reports) and Amit Kumar v. Union of India (15 January 2026, 2026 INSC 62, Pardiwala and Mahadevan, JJ.; directions on reporting student deaths, round-the-clock medical help for residential institutions, and a request to the National Task Force for model protocols). The UGC draft guidelines circulated 13 January 2026 are a draft; final status UNVERIFIED. Our sources are secondary summaries (`docs/research/product-market.md` section 1.6), and the judgment texts were not read in full. Questions: Which of these obligations fall on the institution and which, if any, can lawfully be delegated to a vendor? What must we avoid saying ("supports your compliance workflow" versus "compliant")? Does the vendor owe anything if a student dies while using the product (duty of care, negligence, reporting)? Is the product's out-of-hours position (students told to call Tele-MANAS 14416 and 112; no 24x7 monitoring) legally adequate for the college's duty, and what must the college provide itself?
- **L18. Ethics committee and research.** A pilot that measures outcomes (PHQ-9 and GAD-7 change, retention) and may be published: is Institutional Ethics Committee approval required under the ICMR National Ethical Guidelines for Biomedical and Health Research Involving Human Participants (2017) and the ICMR guidelines for AI in biomedical research and healthcare (2023, https://www.icmr.gov.in/ethical-guidelines-for-application-of-artificial-intelligence-in-biomedical-research-and-healthcare , PDF not read)? Does it differ if data are used only for service evaluation and never published? Is registration in the Clinical Trials Registry required (UNVERIFIED)? What consent text is needed for research use beyond the product consent?

### F. Contracts and operations

- **L19. Contract with the college.** Draft or review: a data processing agreement (roles, purposes, sub-processors Google and hosting, security measures, breach notice, audit rights, deletion and return on exit), a pilot MoU (scope, duration, who is the responsible clinician, out-of-hours arrangement, students' information sheet, communication, publicity), limitation of liability and a cap, indemnities in both directions, service levels (what uptime is promised, and an explicit statement that alerts are not a monitored emergency service), force majeure, termination and exit (data return in an agreed format, deletion certificate), governing law and jurisdiction (the Terms draft leaves the operator's city blank). See the MoU outline in `PILOT_PLAN.md`.
- **L20. Terms of service and privacy policy.** Review the drafts at `/privacy` and `/terms` (source: `templates/privacy.html`, `templates/terms.html`) for accuracy against the actual behaviour (section 9 lists known mismatches), enforceability, limitation of liability, and DPDP content. Both pages carry "Draft pending legal review" banners that must stay until counsel signs.
- **L21. Grievance officer, retention and insurance.** Who must be appointed grievance officer and what must be published? Recommend retention periods per data class: assessments, journal, voice, crisis events, audit log, clinical notes, contact messages, backups, application logs (CERT-In and DPDP interplay). Recommend insurance (professional indemnity, cyber, general liability) and any cover the college requires.
- **L22. Content and open source.** The repository is public. Check licences for the audio tracks and datasets (the binaural dataset import script and tracks) and for the fonts and libraries loaded from CDNs; confirm the project licence (LICENSE file) allows the intended commercial pilot. A history-rewrite to remove audio from git is deferred (decision P-03).

## 3. What we already implemented for each legal ask

"Implemented" means present in code and tested where stated; it does not mean sufficient in law.

| Ask (from section 2) | What exists | Where in the code | What does not exist |
|---|---|---|---|
| Notice (L2, L20) | Privacy and Terms pages, draft banner, data table, rights, services list | `templates/privacy.html`, `templates/terms.html`, `routes/pages.py`, `docs/PRIVACY_AND_CONSENT.md` | Legal review; operator name, hosting and SMTP provider, retention periods, grievance details are placeholders |
| Consent record (L2) | Two server-checked boxes, `ConsentRecord` rows with version and time, re-consent on version bump, consent guard for Google sign-up | `routes/auth.py`, `models.ConsentRecord`, env `CONSENT_VERSION` | Per-purpose consent, withdrawal without account deletion, consent for users created before the feature |
| 18+ gate (L6) | `age_confirm` box checked on the server and stored as a record | `routes/auth.py` | Age verification, parental consent, any under-18 path |
| Access scoping (L10) | Assigned-only rule, 404 for others, aggregates with small groups suppressed, crisis override for institution counsellors | `utils/assignments.py`, `routes/provider.py` (`institution_summary`), `docs/PRIVACY_AND_CONSENT.md` sections 2 to 4; tests `tests/test_provider_scope.py` | Admin or dean role; formal anonymisation guarantee |
| Audit trail (L10, L21) | Audit log of counsellor views, alert views and acknowledgements, notes, exports, deletes, assignments | `utils/audit.py`, `models.AuditLog` | Audit retention period; audit of every read of every table |
| Export and delete (L5) | JSON export and cascade delete with typed confirmation, audit rows, files removed | `routes/auth.py` (`account_export`, `account_delete`) | Deletion from backups and logs; counsellor notes in the export; a timeline promise |
| Minimal crisis data (L3, L10) | Alert record holds a code only, never the message; escalation email holds institution, event id and time only | `utils/crisis.py`, `models.CrisisEvent` | Student told at the moment of alert that counsellors are notified; confidentiality-break policy |
| AI disclosure and limits (L9, L16) | AI named as AI in chat and on `/ai`; prompt forbids diagnosis, medicines, doses, methods and promises; output filter blocks those patterns; no real names sent to the model | `ai_prompts/psychologist_system.txt`, `utils/llm_guard.py`, `templates/how_ai_works.html`; generated `ai_prompt_snapshot.md` | Counsel's view on the AI-restriction clause; paid-tier and data terms with Google; model version pinning |
| Data minimisation to the AI provider (L8) | No name, email or user id sent; text cleaned and length-capped; crisis journals and assessments never sent | `ai/service.py`, `utils/llm_guard.py` | Redaction of names or phone numbers typed by the student |
| Security safeguards (L7, L14) | Hashing, CSRF, rate limits, CSP nonces, secure cookies in production, no patient text in logs, log masking, jobs without text | `app.py`, `utils/logging_setup.py`, `tests/test_security.py` | Encryption at rest, penetration test, key rotation record, backup and restore drill, breach runbook |
| Breach notification (L7, L15) | Nothing beyond logging and the job system | `docs/OPERATIONS.md` | Breach runbook, contact list, CERT-In and Board notification procedure |
| Advertising claims (L16) | Rules for what may be claimed; helpline and AI copy written to those rules; no fake counts in current copy per tests | `docs/research/product-market.md` section 8, `tests/test_redesign_public.py` | Legal review of the landing page; check of live copy |
| Counsellor titles and credentials (L13) | Provider accounts need an invite code | `routes/auth.py` | Credential verification, display of verification status (designed for doctors only) |
| Prescribing controls (L9, L12) | Feature flag default off, assigned-patient check, audit row on issue | `routes/provider.py`, `decorators.py` | Verified-prescriber check, List blocking, inventory, dispensing (all design only) |
| Contact form handling | Stored first, email as a job, honest message when email is off | `routes/pages.py`, `utils/mailer.py` | Retention period; processor named |
| Research and IEC (L18) | Product avoids publishing outcome claims; metrics are marked targets | `PILOT_PLAN.md` | Ethics approval, research consent text |
| Contracts (L19) | Outline only | `PILOT_PLAN.md` | Any draft or signed contract |

## 4. Operator tasks the owner must complete

Engineering cannot supply these. Counsel can advise on several.

| Task | Where it is used | Status |
|---|---|---|
| Name the data fiduciary (legal entity, registered address): `DATA_FIDUCIARY_NAME` | Privacy and Terms pages, DPA | open |
| Appoint a grievance officer, mailbox and promised response time: `GRIEVANCE_EMAIL` | Privacy and Terms pages | open |
| Decide retention periods per data class and the deletion mechanism (no automatic job exists) | privacy page, code change needed | open |
| Provide or approve a DPA template and a pilot MoU | college contract | open |
| Choose jurisdiction city for disputes (the Terms placeholder) | Terms page | open |
| Name the hosting provider and region; confirm database backup retention and who can read backups and logs | privacy page, DPA | open |
| Name the SMTP provider or state none; set `CRISIS_ESCALATION_EMAIL` to a monitored address | privacy page, alerting | open |
| Confirm the Gemini key is on a paid, billing-enabled plan and record the terms accepted | privacy page, L8 | open |
| Decide whether a Data Protection Officer or an SDF assessment applies | counsel | open |
| Decide under-18 handling before the age gate is ever lowered | counsel | open |
| Decide whether users created before consent records existed must be re-consented | `PRIVACY_AND_CONSENT.md` section 5 | open |
| Decide whether the prescription flag stays off for the pilot (recommended) and resolve P-01 versus C-11 | `docs/CLINICAL_DESIGN.md` | open |
| Insurance quotes (professional indemnity, cyber) | pilot gates | open |
| Name the clinical advisor and the college's responsible clinician (needed for L10 and L17 answers) | pilot plan | open |

## 5. Deliverables requested from counsel

1. Written answers to L1 to L22, with confidence level and sources.
2. A marked-up Privacy Policy and Terms (replace the draft banners only after your sign-off).
3. A DPA template and MoU for the college, a signed-off notice text for signup and the crisis alert, and research consent text if outcome data will be published.
4. A short list of changes you require before any real student uses the product.
5. A sign-off page (below). No review is complete without it.

## 6. Counsel sign-off page

| Field | Entry |
|---|---|
| Reviewer name and firm | |
| Bar council enrolment number | |
| Date | |
| Scope reviewed (tick) | [ ] DPDP   [ ] Mental Healthcare Act   [ ] Telemedicine and prescribing   [ ] Drugs and pharmacy   [ ] IT Act and SPDI   [ ] CERT-In   [ ] Medical devices   [ ] Consumer and advertising   [ ] Institution duties   [ ] Ethics committee   [ ] Contracts   [ ] Policies |
| Scope NOT reviewed | |
| Code version reviewed: git commit hash (from `generated/MANIFEST.md`) | |
| Documents reviewed (names and versions) | |
| Primary texts consulted (list) | |
| Conditions | |
| Changes required | |
| Outcome | [ ] no objection for the pilot as scoped   [ ] with conditions   [ ] objection |
| Signature | |

## 7. Dated list of sources used in this packet

All fetched or cited on or before 2026-11-24. "Secondary" means a law-firm note, news article or journal commentary.

- DPDP Rules 2025 summaries (secondary): https://www.scconline.com/blog/post/2025/12/26/digital-personal-data-protection-rules-2025-key-highlights/ ; https://www.legal500.com/firms/237811-saga-legal/c-india/news-and-developments/the-privacy-timer-starts-now-analysing-the-dpdp-rules-and-its-18-month-countdown ; https://www.tribuneindia.com/news/business/govt-notifies-digital-personal-data-protection-rules-rollout-in-phases-specified-obligations-for-data-fiduciaries . UNVERIFIED against the gazette.
- Mental Healthcare Act 2017: https://qps.nhsrcindia.org/sites/default/files/2022-01/THE%20MENTAL%20HEALTHCARE%20ACT%2C%202017.pdf (not read); commentary https://pmc.ncbi.nlm.nih.gov/articles/PMC7736728 and https://blog.ipleaders.in/all-need-know-about-mental-healthcare-act/ .
- Telemedicine Practice Guidelines 2020 (secondary): https://www.lexology.com/library/detail.aspx?g=9055584c-829c-4742-aa80-3353bdbb5d14 ; https://khaitanco.com/thought-leaderships/Telemedicine-Practice-Guidelines . Official PDF not opened.
- Prescribing and inventory research: `docs/research/prescribing-inventory.md` (all items marked verified, secondary or UNVERIFIED there).
- Sukdeb Saha and Amit Kumar (secondary): https://www.livelaw.in/amp/supreme-court/in-neet-aspirants-death-case-supreme-court-issues-guidelines-to-protect-mental-health-of-students-in-colleges-coaching-centres-298795 ; https://www.scobserver.in/supreme-court-observer-law-reports-scolr/amit-kumar-v-union-of-india-guidelines-on-student-suicide-prevention/ . Judgment PDFs not read in full.
- UGC draft (secondary, draft): https://theprint.in/india/education/ugcs-draft-mental-health-norms-call-for-standardised-student-counselor-ratio-well-being-centres/2827423 .
- ICMR AI guidelines 2023: https://www.icmr.gov.in/ethical-guidelines-for-application-of-artificial-intelligence-in-biomedical-research-and-healthcare (PDF not read).
- CERT-In directions: https://www.cert-in.org.in/PDF/CERT-In_Directions_70B_28.04.2022.pdf , fetched 2026-11-24, text not extractable; six-hour and 180-day figures from general knowledge, UNVERIFIED.
- Gemini API terms: https://aistudio.google.com/docs/terms (via `docs/research/llm-security.md`, fetched 2026-11-24).
- Not researched at all, named only because counsel will ask: SPDI Rules 2011 text, CDSCO software classification, CCPA misleading-advertisement and dark-pattern guidelines, Pharmacy Practice Regulations 2015, ICMR 2017 national guidelines. All UNVERIFIED.

## 8. Notes on liability and claims engineering will not make

The product will not claim to be compliant with any law, certified, endorsed by a government body, clinically proven, or monitored 24x7. If counsel advises that any statement in the product copy is unsafe, engineering will change it; the list of claims already barred is in `docs/research/product-market.md` section 8.

## 9. Discrepancies found between our own documents and the code (for the owner and counsel)

These were found while preparing the packet. Each needs a fix in code or text before a lawyer relies on the document concerned.

1. **Chat storage.** `templates/privacy.html` lists "Chat: Messages you send to the AI companion and its replies" among data we collect and store. The code stores no chat messages (`routes/auth.py` comment: "Chat has no stored messages"; no chat table). The text is still sent to Gemini. Either the policy overstates what is stored, or storage exists that we did not find. Confirm and correct.
2. **Session length.** The privacy draft says the session cookie lasts up to 7 days. `app.py` sets the permanent session lifetime from `SESSION_LIFETIME_HOURS` (default 24 hours) and a cookie max age of 7 days; which one governs should be confirmed and the policy aligned.
3. **Crisis reply wording.** `templates/how_ai_works.html` says that in a crisis the student sees a fixed caring reply "whatever the model wrote". The code shows the model's reply if the model returns a usable one that passes the output filter, and uses the fixed text only otherwise (`generated/safety_flow.md` section 2). Either the page or the code must change before the claim is made.
4. **Prescription flag default.** Decision P-01 says `ENABLE_PRESCRIPTIONS` defaults to off. `docs/CLINICAL_DESIGN.md` decision C-11 says it flips to on. The owner has not reconciled them, and the design is unbuilt.
5. **Alert disclosure to the student.** The privacy draft tells students that counsellors see crisis alerts, but the crisis text shown at the moment of the alert does not say that an alert was sent. Counsel and the clinician should decide whether it must.
