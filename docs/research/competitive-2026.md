# MindFull Horizon: competitive research 2026

Research date and access date for every URL below: **2026-11-24**. Method: web search plus page fetches. Several vendor sites returned 403, empty or truncated pages to the fetch tool, so many facts come from search summaries of third-party pages.

**Source tags used in tables**
- **P** = primary page or document read in full or in the relevant part this session (vendor page, statute, government PDF).
- **S** = secondary source, search snippet, store listing or news report. Everything tagged S is **UNVERIFIED** until someone opens the primary source.
- A dash in a matrix cell means "not seen on the pages I read". It is NOT proof of absence. A question mark means "not checked".

Our own column in the matrix reflects the repo on 2026-11-24 (code, `docs/STATUS.md`, `docs/TRACKER.md`, tests). Other agents were editing the repo while I read it, and I did not run the test suite, so "built and tested" means "code and a test file exist", not "I saw it pass".

---

## 0. Summary

1. **Youper has shut down.** Its own page says it "discontinued its services on September 30, 2026" (P, single source, no news corroboration found). Woebot's consumer app closed 30 June 2025. Two well-known AI-chat apps are gone; the lesson is dependence on one regulatory or business model, not that the category is dead.
2. **Headspace's AI companion Ebb is not offered in India.** Per Headspace, it is English only, for paid members in the US, UK, Canada and Australia, 18+, and "not monitored in real time by a human" (P). This is the cleanest verified, neutral contrast available for the landing page.
3. **UGC mental-health guidelines are still, as far as I can find, a draft.** I read the circulated text (a college's copy of the UGC document). It asks institutions for a well-being centre, a 24x7 helpline linked to Tele-MANAS, at least three post-crisis follow-up sessions, and an anonymised report on a UGC portal called MANAS-SETU. I found no notification of a final version and no evidence the portal is live (UNVERIFIED either way).
4. **The Telemedicine Practice Guidelines clause on AI is now verified from the primary PDF** (clause 5.4): AI/ML platforms may not counsel or prescribe; only a registered medical practitioner may.
5. **Biggest honest gaps in our product** (all "not built"): safety plan, post-crisis three-session tracker, appointment reminders, institution annual-report export, Hindi UI, anonymous or pseudonymous mode, sleep log, thought record, grounding. Our strongest built assets are the deterministic crisis path with counsellor alert and timed escalation, server-side PHQ-9/GAD-7, assigned-only counsellor scope with aggregate-only institution data, and data export and deletion.
6. **Evidence is modest everywhere.** Most digital-tool effects are small to moderate, heterogeneous, short-lived, and strongest when a human is involved. No India-college RCT of any comparable product was found.

---

## 1. Current status of products (as of 2026-11-24)

### 1.1 AI chat and CBT-style apps

| Product | Status 2026 | Facts | Source (tag) |
|---|---|---|---|
| Woebot | Consumer app retired 30 June 2025. Company now lists provider, payer and health-system offerings. A return of the consumer app is not indicated. | Founder said FDA marketing-authorisation cost and difficulty drove the closure. Woebot Health's homepage today shows partner programmes and a "behavioral health copilot"; it does not say whether the consumer app exists. 2026 "no FDA approval" claims came from review sites only (UNVERIFIED). | https://www.statnews.com/2025/07/02/woebot-mental-health-chatbot-shuts-down-founder-says-ai-moving-faster-than-regulators/ (S) ; https://www.mobihealthnews.com/news/woebot-health-shutting-down-its-app (S) ; https://woebothealth.com (P, partial) |
| Youper | **Discontinued 30 September 2026.** | Page: "Youper discontinued its services on September 30, 2026". Prior description: adult-only (18+) AI chatbot for mood tracking, reflection and journaling; "not an emergency service"; referred users to US numbers (988, Crisis Text Line 741741, 911); not FDA-cleared; no clinical studies cited. Pricing before closure conflicted across third-party sites (UNVERIFIED). | https://www.youper.ai (P, fetched twice) |
| Wysa (Touchkin) | Active. India-linked. | Hindi version launched April 2024 (company press release, with early-adopter NGOs; "90% returned for more than one session" is company-reported). Wellcome Trust grant of GBP 5.3m for adolescent girls in rural India (S). "Top 10 at India AI Impact Summit 2026" (snippet, UNVERIFIED). FDA Breakthrough Device designation May 2022 is a designation, not approval (carried from earlier research, not re-fetched). Wysa's own site and evidence page returned no readable body to the fetch tool. | https://blogs.wysa.io/blog/company-news/wysa-launches-hindi-version-of-globally-successful-ai-therapy-app-smart-staff-azad-foundation-and-royal-rajasthan-foundation-first-to-adopt (S) ; https://yourstory.com/socialstory/2024/04/wysa-launches-hindi-version-of-ai-therapy-app (S) ; https://blogs.wysa.io/blog/wysa-news/wellcome-awards-5-3m-grant-to-wysa-3 (S) |
| Headspace (with Ebb) | Active. Ebb AI companion limited to four countries. | Ebb: English, paid members in US, UK, Canada, Australia; 18+; "not a substitute for human care"; "does not provide clinical mental health services"; "not monitored in real time by a human"; entered information not shared with a care team unless the member chooses. Crisis: directs US/Canada users to 988. Headspace says it will widen country and language access in 2026 (snippet). Also sells therapy (insurance-backed in the US, per search snippet). | https://www.headspace.com/ebb (P) ; https://www.headspace.com/articles/introducing-therapy-by-headspace (S) |
| Talkspace (reference, not India) | Being acquired or acquired by Universal Health Services for USD 835m (one source says closed 17 Aug 2026, another says expected Q3 2026). | AI agent "Tee": free first week then USD 19.99 per month per one summary; CEO said monetisation was undecided. Acquired Wisdo Health (peer support) Oct 2025. | https://www.statnews.com/2026/03/09/talkspace-to-be-acquired-for-835-million-by-mental-health-services-giant/ (S) ; https://www.uschamber.com/co/good-company/the-leap/talkspace-ai-therapy-strategy (S) |
| BetterHelp (reference) | Not checked for India availability. | One third-party comparison quotes about USD 70-100 per week. UNVERIFIED. | search summary only (S) |

### 1.2 Mood, habit and tracker apps

| Product | Status 2026 | Facts | Source (tag) |
|---|---|---|---|
| Daylio | Active, free plus premium. | Premium prices seen: USD 4.99 per month or 35.99 per year (a July 2026 third-party review); store listings show other regional prices. Premium-only items reported by users: passcode lock, monthly overview, "year in pixels"; reviewer says data export is the main reason to pay. | https://www.choosingtherapy.com/daylio-app-review/ (S) ; https://apps.apple.com/us/app/daylio-journal-mood-tracker/id1194023242 (S) |
| Finch | Active, free base app plus "Finch Plus". | Plus plans vary by country (users reported GBP 9.99 per month or 59.99 per year; US listing shows many SKUs). No 2026 user count or funding found. | https://apps.apple.com/app/id1528595748 (S) |
| Bearable | Active. | Review updated 29 July 2026 gives USD 6.99 per month or 34.99 per year with a 7-day trial; sleep tracking not confirmed in what I saw. | https://www.choosingtherapy.com/bearable-app-review/ (S) ; https://apps.apple.com/app/symptom-mood-tracker/id1482581097 (S) |
| MindDoc (Germany) | Active. | German store listing: more than 70 CBT-based courses and exercises; IAPs around EUR 7.99 per month. A 2022 German pharmacy-journal article calls it a class I medical product; a third-party review says it screens with questions "adapted from validated screeners" (UNVERIFIED). Whether it is a reimbursed DiGA is stated inconsistently. | https://apps.apple.com/DE/app/id1052216403 (S) ; https://www.pharmazeutische-zeitung.de/depressionen-digital-angehen-131420/seite/3/ (S) |
| Sanvello | Existence in 2026 not confirmed. | Older pages: free tier plus premium (USD 8.99 per month or 53.99 per year, possibly stale); premium bundled into some US health plans. One NZ app library lists it as no longer available. No shutdown or acquisition news found. UNVERIFIED. | https://choosingtherapy.com/sanvello-app-review (S) ; https://www.cbinsights.com/company/pacifica-labs (S) |
| Calm | Active. | Help centre says price varies by country in local currency; USD 69.99 per year and 14.99 per month appear on aggregators; a student discount via Student Beans appears on a coupon site (UNVERIFIED). No India price confirmed. | https://support.calm.com/hc/en-us/articles/360008240934 (S) |

### 1.3 Peer, community and campus self-help

| Product | Status 2026 | Facts | Source (tag) |
|---|---|---|---|
| 7 Cups | Active. | Volunteer "listeners" (not clinicians), paid licensed-therapist messaging reported at about USD 150-200 per month, AI tool "Noni". Listener counts conflict across sources (320,000 to 600,000). Recent Trustpilot reviews negative (anecdotal). | https://weforum.org/organizations/7-cups (S) ; https://www.choosingtherapy.com/7-cups-review/ (S) |
| Togetherall | Active. Access depends on a funding organisation (university, employer, health authority). Regional sites: UK, US, Canada, NZ, Ireland, Australia; no India site seen. | Anonymous usernames; moderated by staff with clinicians (company claim); "not a crisis service"; members 16+. Access can end if the funder stops. | https://togetherall.com (P, navigation only) ; https://togetherall.com/en-us/faqs/using-the-togetherall-community-platform/ (S) |
| TAO Connect | Active at many US campuses; at least two schools ended access in 2026 (Delmar College 24 April; Weber State mid-August). | Self-guided self-help library, logged in with a campus email, positioned as a supplement to counselling, "not therapy". | https://delmar.edu/offices/counseling/tao.html (S) ; https://www.weber.edu/counselingcenter/tao.html (S) |

### 1.4 India: tele-mental-health and clinics

| Product | Status 2026 | Facts | Source (tag) |
|---|---|---|---|
| Tele-MANAS (MoHFW, 14416) | Active. | Cumulative 29.82 lakh calls reported in a Lok Sabha reply of Dec 2025; 53 cells in 36 states and UTs; 20 languages. A Tele-MANAS mobile app (Oct 2024) with video consultation is reported (UNVERIFIED). Note the per-year figures quoted in the earlier research (121,151 for 2025) do not add up to the cumulative figure; the discrepancy is unresolved. | https://www.freepressjournal.in/tech/new-delhi-over-298-lakh-calls-handled-by-tele-manas-cells-govt-strengthens-womens-mental-health-support (S) ; https://www.tribuneindia.com/news/delhi/natl-mental-health-helpline-got-2-calls-every-minute-govt (S) |
| MANODARPAN (MoE) | Active as a helpline and web pages. | Launched July 2020. A secondary report citing Lok Sabha replies says 69 tele-counsellors and 3,32,877 calls by 10 March 2026, about 70% from classes 6-8, and no summative impact evaluation (UNVERIFIED). Not a college triage tool. | https://manodarpan.education.gov.in (S) ; https://www.newkerala.com/news/a/govt-taking-multi-pronged-measures-providing-psychological-support-students-325.htm (S) |
| UGC MANAS-SETU | **Planned in draft guidelines. No evidence of a live portal or registration process.** | See section 8 (UGC row). UNVERIFIED. | draft text read: https://mmcc.edu.in/wp-content/uploads/2026/01/UGC-mental-health-well-being-feedback-Noticeand-policy.pdf (P) |
| Amaha (ex-InnerHour) | Active; raising about Rs 100 crore (Oct 2026 reports). | College wellness page (P): self-care app with 600+ tools; therapy and psychiatry on campus, online or in clinics; "Amaha Round the Clock" expert access said to be under 10 minutes; anonymous expert-moderated peer space; email-bot check-ins to spot trends; ISO, HIPAA and GDPR icons shown. The page does not describe formal screening or an administrator dashboard. Company-reported scale: 450,000+ sessions, 100,000+ clients, 270+ professionals (secondary). | https://amahahealth.com/services/college-wellness-programme/main (P) ; https://biospectrumindia.com/news/86/28709/amaha-set-to-close-rs-100-cr-fundraise-to-strengthen-mental-healthcare-capabilities.html (S) |
| YourDOST | Active (not re-verified). | Earlier research: institution-funded counselling and helplines (IIT Kanpur page, Haryana). The vendor page returned only a heading to the fetch tool. | https://iitk.ac.in/counsel/cmhw/pages/external-counselling.php (S, from earlier research) |
| Lissun | Active. | Press-reported: 1 lakh students reached, 500+ B2B clients, 2026 focus on child-development centres. "Prevents 1,000+ self-harm incidents" is a company headline, not a verified outcome. | https://www.theweek.in/health/more/2025/07/26/lissun-mental-health-india-tech-empathy-distribution-healthcare.html (S) |
| MindPeers | Active. | NLIU Bhopal partnership Jan 2026: free unlimited counselling for all its students. Corporate clients in Southeast Asia, LATAM and Japan (LiveLaw report). | https://www.livelaw.in/lawschool/news/nliu-bhopal-ties-up-with-mindpeers-provide-free-mental-health-support-students-519201 (S) |
| Evolve | Active, LGBTQ+-focused CBT app. Not a campus tool. | User-count claims conflict (over 1 million downloads in 2024 vs 600,000 users in a 2026 profile). | https://yourstory.com/2022/07/mental-wellness-app-evolve-lgbtq-community-healthtech-startup (S) |
| Practo (consults) | Active. | Online psychiatrist consults listed; no verified price. A guide quotes Rs 1,500-4,600 per initial psychiatrist consult across providers (2025, UNVERIFIED). | https://www.practo.com/consult/ask-a-psychiatrist-online (S) |
| Mpower (Aditya Birla Education Trust) | Active campus programme. | 62 colleges and 1.12 lakh students in a one-year initiative; peer first-aider programme (COPE). Outcome percentages are self-reported by Mpower-linked releases: do not reuse. "Gaia" was not identified as a product. | https://www.theweek.in/wire-updates/business/2026/02/23/institutional-mental-health-strengthens-across-62-colleges-as-women-emerge-as-key-peer-support-leaders.html (S) |
| Here for You (research app) | Peer-reviewed pilot, not a commercial product found. | JMIR Formative Research 2026;10:e75616: screening app co-designed with Indian university students; 30 students with diagnosed depression, anxiety or stress; DASS-21 scores correlated with clinician ratings (r 0.82 to 0.97); usability 4.4/5; authors call it preliminary feasibility. A "Quick Exit" button and crisis links came from co-design. | https://formative.jmir.org/2026/1/e75616 (S) |

### 1.5 Campus platforms and counselling-centre software

| Product | Status 2026 | Facts | Source (tag) |
|---|---|---|---|
| TimelyCare (TimelyMD) | Active, US. | Says 400+ campuses and 1 million+ students; counselling, on-demand emotional support, medical, psychiatric care, coaching. No India deployment found. | https://timelycare.com/for-schools/ (S) |
| Mantra Health (the US company; not MantraCare India) | Active, US. | A 2021 report describes a student telehealth app plus a collaboration portal for campus counsellors to monitor and refer, and an EHR. Closest analogue to our counsellor loop. India deployment not found. | https://www.mobihealthnews.com/news/mantra-health-tackles-college-mental-healthcare-closed-loop-virtual-care (S) |
| Titanium Schedule | Active, US counselling-centre EHR. | Scheduling, custom forms and notes, e-signatures, reminders, reporting, data export, role-based access, e-prescribing, API; GetApp lists USD 1,750 first year (possibly stale). | https://www.capterra.com/p/84048/Titanium-Schedule/ (S) |
| Point and Click Solutions | Not verified. | My search returned nothing on it. | none |

### 1.6 Hospital information systems with pharmacy modules

| Product | Facts | Source (tag) |
|---|---|---|
| Bahmni (on OpenMRS) | Pharmacy and stock run on Odoo: warehouses and stocking points, products and suppliers, batch-level stock, first-expiry-first-out dispensing, stock movements between locations, a "Prescription" widget showing a patient queue, drug orders syncing as billing quotations. Some pages describe old versions (Bahmni 0.91/0.92). | https://bahmni.atlassian.net/wiki/spaces/BAH/pages/32604205/Pharmacy+Management (S, search summary; the page body did not load) |
| OpenHMIS pharmacy (OpenMRS community) | Entry of prescriptions, a queue of orders to fill, dispensing, and a stock check with a warning when a prescription cannot be filled, if the inventory module is installed. | https://openmrs.atlassian.net/wiki/x/siCcAQ (S) |
| Practo Ray | Clinic management; listings say e-prescribing and inventory features; I could not tie a pharmacy module to Ray from Practo's own pages. A directory says no API (unreliable). | https://www.capterra.com/p/167778/Ray/ (S) |

---

## 2. What a prescription plus inventory flow normally contains

Sources: the Telemedicine Practice Guidelines (primary, below) and the Bahmni and OpenHMIS summaries above. Items marked "proposal" are my synthesis, not facts.

**Required by Indian rules (primary: Telemedicine Practice Guidelines, 25 March 2020, official PDF copy at https://esanjeevani.mohfw.gov.in/assets/guidelines/Telemedicine_Practice_Guidelines.pdf , P)**
- Only a registered medical practitioner (RMP) may counsel or prescribe; platforms must show each RMP's name, qualification and registration number (clauses 5.1, 5.2).
- Drug lists by consult type: List O (safe in any mode), List A (first consult by video; refills at follow-up), List B (follow-up), and a Prohibited list (Schedule X and narcotic or psychotropic substances under the NDPS Act). The "List C" label used in the earlier research comes from the telepsychiatry guidelines and is not in the TPG text I read.
- A prescription follows the Indian Medical Council ethics regulations; the RMP gives a signed copy or e-prescription; if sent to a pharmacy, the patient's explicit consent is needed and the patient may choose any pharmacy (clause 3.6.4.2).
- Prescription records are kept as for in-person visits (clause 3.7.2.3). The RMP must ask the patient's age before prescribing (clause 3.2.3).

**What an inventory-linked flow adds (secondary, UNVERIFIED in detail)**
- Drug master with generic name, strength, form and schedule; stock by location and batch with expiry; first-expiry-first-out issue; reorder level; stock adjustments with reason; a prescription queue for the pharmacist; a dispense record linked to the prescription; billing link (Bahmni, OpenHMIS summaries).
- Proposal for us: because campus counsellors cannot prescribe and our feature flag is off, we do not need inventory. If a campus health centre later wants it, the minimum is prescriber verification, schedule-aware blocking, dispense record and a stock-out warning; do not build a pharmacy ledger.

---

## 3. Feature matrix

Legend: **Y** seen on a vendor or primary page; **Ys** seen only in a secondary source (UNVERIFIED); **-** not seen; **?** not checked. Our column: **Built** (code and test file exist), **Partial**, **Not built**, with the reason.

| Feature | Wysa | Headspace | Daylio | MindDoc | Togetherall | Amaha campus | TimelyCare / Mantra | Titanium (EHR) | Tele-MANAS | MindFull Horizon |
|---|---|---|---|---|---|---|---|---|---|---|
| Mood tracking with patterns | ? | ? | Ys | Ys | ? | Y (email check-ins) | ? | - | - | **Partial**: 1-10 log and 30-day chart; no activity or trigger patterns |
| Validated screening (PHQ-9, GAD-7) with scoring | ? | ? | - | Ys (adapted items) | ? | - (not described) | ? | ? | - | **Built**: server scoring, item-9 rule (`tests/test_safety.py`) |
| CBT thought records | ? | ? | - | Ys (CBT courses) | ? | ? | ? | - | - | **Not built** |
| Guided breathing or grounding | ? | Y (mindfulness) | - | ? | ? | Ys (self-care tools) | ? | - | - | **Partial**: breathing page and log built; grounding not built |
| Sleep tracking | ? | ? | ? | Ys | ? | ? | ? | - | - | **Not built**: only a `sleep_duration` field in `RPMData`, no student log |
| Journaling | ? | ? | Ys | ? | ? | ? | ? | - | - | **Built**: journal in DB, crisis scan (`tests/test_crisis_durability.py`) |
| Safety plan builder (Stanley-Brown) | ? | - | - | ? | ? | ? | ? | ? | - | **Not built** |
| Crisis detection and escalation to a human | ? | Resources only; no real-time human (Y) | - | ? | Ys (clinician moderation; "not a crisis service") | Y (claim: expert in under 10 min) | Ys (24x7 support) | - | Y (is the human line) | **Built**: rules, alert job, notifications, timed escalation, acknowledgement (`utils/crisis.py`, `tests/test_crisis_durability.py`). Out of hours the student sees helplines; no staffed 24x7 monitoring |
| Post-crisis follow-up tracking (3 sessions) | - | - | - | - | - | ? | ? | ? | - | **Not built**: acknowledgement only |
| Human counsellor booking | Ys (coach) | Ys (therapy) | - | Ys | - | Y | Ys | Ys | - | **Built**: request, accept or reject, conflict check, telehealth signalling (no TURN, per STATUS) |
| Caseload triage for counsellors | Ys (Copilot, earlier research) | ? | - | ? | ? | - | Ys (Mantra portal) | ? | - | **Partial**: risk from PHQ/GAD and open crisis events; no overdue follow-ups |
| Measurement-based care trends | ? | ? | - | ? | ? | ? | ? | ? | - | **Partial**: per-patient PHQ/GAD chart and CSV for the counsellor; no change flags |
| Anonymised institutional reporting | ? | ? | - | - | ? | - (not described) | ? | Ys (reporting) | - | **Partial**: aggregate summary with groups under 5 hidden; no annual-report export |
| Hindi and regional languages | Y (Hindi, 2024 company release) | Y English only for Ebb | ? | - | ? | ? | - | - | Y (20 languages) | **Not built** (`<html lang="en">`) |
| Anonymous or pseudonymous mode | ? | ? | ? | ? | Y (username) | Y (anonymous peer space) | ? | - | ? | **Not built**: name and email accounts |
| Reminders and notifications | ? | ? | ? | ? | ? | ? | ? | Ys | - | **Not built** for reminders; in-app notices only for crisis alerts |
| Offline use | ? | ? | ? | ? | ? | ? | ? | - | - | **Not built** |
| Peer support | - | - | - | - | Y | Y | ? | - | - | **Not built** (blog comments only) |
| Psychiatrist e-prescription | ? | ? | - | - | - | Y (psychiatry with medication support) | Ys | Ys | - | **Partial**: code exists, flag `ENABLE_PRESCRIPTIONS` off by default, no prescriber verification |
| Pharmacy inventory integration | - | - | - | - | - | - | - | ? | - | **Not built** (patient medication log only) |
| Data export and deletion | ? | ? | Ys (premium export) | ? | ? | ? | ? | Ys (export) | - | **Built**: `/account/export`, `/account/delete` (`tests/test_privacy.py`) |
| Accessibility | ? | ? | ? | ? | ? | ? | ? | ? | ? | **Partial**: ARIA attributes in templates; no audit |
| Price and model | Freemium and enterprise (earlier research) | Paid membership (Y) | Free and premium (Ys) | Free and IAP (Ys) | Funded by institutions, employers, health systems (Y) | Per-session plus institution programmes (Ys) | Institution-funded (Ys) | Licence (Ys) | Free, government (Y) | **Not defined in the repo** |

Reading the matrix: no product I could check combines student check-in, validated scoring, counsellor alerting with acknowledgement, and anonymised institutional reporting in one loop. Mantra Health (US) is the closest in concept. That is a limited-scan observation, not a verified market gap.

---

## 4. Evidence per feature class

Effect-size wording: g or d near 0.2 is small, near 0.5 moderate. Most figures below come from abstracts or search summaries (S, UNVERIFIED against full text).

| Feature class | What studies show | Strength and caveats | Source (tag) |
|---|---|---|---|
| Mood tracking | A 2026 systematic review and meta-analysis found it unclear whether mood monitoring alone reduces symptoms or relapse (small non-significant effect on mania; none on bipolar depression). A 2025 review of 77 studies notes self-monitoring harms are little studied and may be higher in self-guided apps. App trials pooled dropout 26.2%, lower with human feedback and in-app mood monitoring. No trial of rumination harm found. | Weak as a stand-alone intervention. Useful as data for a counsellor. | https://mental.jmir.org/2026/1/e84020 (S) ; https://pubmed.ncbi.nlm.nih.gov/31969272/ (S) |
| Screening and measurement-based care | Small average gains (g about 0.15 to 0.28) and only when a clinician sees and acts. PHQ-9 item 9 alone misses many people who later attempt. | Small. Our design (counsellor sees scores) matches where the effect exists. | see `product-market.md` section 3.2 |
| Digital programmes for students | A 2025 meta-analysis reports d=0.55 depression and d=0.46 anxiety for digital interventions in university students (fully automated 0.55 vs guided 0.35 for anxiety); a 2022 wellbeing meta-analysis g=0.32; another 2025 paper reports g 0.80-0.88, which I would not trust without reading methods. | Moderate pooled values, heterogeneous, mostly non-Indian samples, and larger than chatbot-specific estimates (g about 0.3). | https://pmc.ncbi.nlm.nih.gov/articles/PMC11876723/ (S) ; https://pmc.ncbi.nlm.nih.gov/articles/PMC9557766/ (S) |
| Human guidance | Individual-patient-data network meta-analysis of 39 trials (9,751 people): guided internet CBT beat unguided, with a small gap for subthreshold symptoms and a larger gap at PHQ-9 above 9. A 2021 meta-analysis of 22 studies says guidance increases adherence. | Supports our counsellor-in-the-loop design. | https://jamanetwork.com/journals/jamapsychiatry/fullarticle/2774861 (S) ; https://pubmed.ncbi.nlm.nih.gov/33471111/ (S) |
| CBT thought records | A network meta-analysis of 45 trials (3,382 people) found cognitive restructuring, behavioural activation and full CBT equal to each other and better than care as usual or waitlist. The separate contribution of the thought record is not established. | Moderate for CBT packages; unknown for a stand-alone unguided thought record. | https://pmc.ncbi.nlm.nih.gov/articles/PMC10440210/ (S) |
| Breathing and grounding | Breathwork meta-analysis: stress g=-0.35, anxiety -0.32, depression -0.40, most studies at moderate risk of bias, authors urge caution. Slow-paced breathing in non-clinical people: SMD -0.51 but confidence interval -1.06 to 0.03, "marginal". No grounding-specific meta-analysis verified. | Small to moderate, low certainty. | https://www.nature.com/articles/s41598-023-49279-8 (S) ; https://link.springer.com/article/10.1007/s12671-023-02294-2 (S) |
| Sleep tools | A 2025 meta-analysis of digital sleep interventions in college and young adults reports large changes in subjective sleep quality (g=-1.25, I2=97%) with certainty rated moderate to very low; insomnia-severity figures differ between abstract and PDF summaries. A 2022 young-people review found medium-to-large subjective gains but limited objective gains. | Large but unreliable pooled numbers. A diary alone is not CBT for insomnia. | https://pmc.ncbi.nlm.nih.gov/articles/PMC12107209/ (S) ; https://pmc.ncbi.nlm.nih.gov/articles/PMC8949345/ (S) |
| Journaling | Expressive writing: overall effect small (g about -0.12 for depression, anxiety and stress in healthy and subclinical samples; earlier r=0.075). Larger only in some clinical subgroups. | Small. | https://pmc.ncbi.nlm.nih.gov/articles/PMC3830620 (S) ; https://www.simplypsychology.org/expressive-writing-for-anxiety.html (S) |
| Safety planning | Stanley-Brown Safety Planning Intervention with phone follow-up in US veterans' emergency departments: about half the odds of later suicidal behaviour, but a non-randomised cohort comparison. The "45%" figure I was given could not be confirmed. A high-quality individual randomised trial is registered; smartphone safety-plan apps are at feasibility stage. | Promising, not definitive; app evidence early. | https://www.npr.org/sections/health-shots/2018/07/11/628029412/a-simple-emergency-room-intervention-can-help-cut-future-suicide-risk (S) ; https://pubmed.ncbi.nlm.nih.gov/33515785/ (S) |
| Post-crisis follow-up contact | Caring-contacts review: six randomised trials, about 6,200 people; fewer attempts at 1 year; effect on deaths and re-presentations inconclusive. A separate brief-contact review of 14 studies could not recommend wide rollout. | Moderate for attempts, uncertain for deaths. | https://www.suicideinfo.ca/?p=175142 (S) ; https://pubmed.ncbi.nlm.nih.gov/22846445/ (S) |
| Appointment reminders | SMS reminders raise attendance (summary effect 1.48 in a 2012 meta-analysis); digital notifications cut no-shows by 25% (RR 0.75, 2016). I found no mental-health-specific estimate and none for email specifically. | Moderate for SMS in general medicine. Email effect UNVERIFIED. | https://pubmed.ncbi.nlm.nih.gov/22091980/ (S) ; https://pubmed.ncbi.nlm.nih.gov/27798006/ (S) |
| Peer support | Peer-support apps had the best 30-day retention in open-market apps (8.9%) in the earlier research. Efficacy and safety of unmoderated peer support not checked here. | Retention only. | `product-market.md` section 3.3 |
| Language access | No evidence found on translated screening in Indian college students. Hindi PHQ-9 validation found in cancer patients (2024) and rural older adults (2021); none in students. | Gap in evidence, so use official translations, not machine translation. | https://pmc.ncbi.nlm.nih.gov/articles/PMC8327872 (S) |
| Campus screening apps in India | One pilot (n=30), feasibility only. | Anecdotal. | https://formative.jmir.org/2026/1/e75616 (S) |

---

## 5. Gap analysis and prioritised build list

Scoring: each criterion 1-5 (5 best); total out of 20. **Safety** = reduces harm to a student in distress. **Evidence** = strength of evidence the feature helps (see section 4). **India** = fit with Indian rules and campus reality. **Feasibility** = small team, a few weeks, using the existing job queue, mailer and models. Scores are my judgement, not data.

| Rank | Feature | Safety | Evidence | India | Feasibility | Total | Clinician sign-off needed? |
|---|---|---|---|---|---|---|---|
| 1 | Post-crisis three-session follow-up tracker | 5 | 3 | 5 | 3 | 16 | **Yes** |
| 1 | Safety plan builder | 5 | 3 | 4 | 4 | 16 | **Yes** |
| 3 | Per-student PHQ/GAD trend with change flags for the counsellor | 3 | 3 | 4 | 5 | 15 | Yes for thresholds |
| 4 | Appointment reminders by email | 2 | 4 | 3 | 5 | 14 | No (wording review only) |
| 5 | Hindi UI for the most important pages | 4 | 2 | 5 | 2 | 13 | **Yes, plus native speakers** |
| 5 | Sleep log | 2 | 3 | 3 | 5 | 13 | No |
| 7 | Anonymised annual report export (CSV and print) | 1 | 2 | 5 | 4 | 12 | No, but legal review of what is reported |
| 7 | Grounding exercises | 2 | 2 | 3 | 5 | 12 | Light review |
| 7 | Anonymous-first onboarding | 3 | 2 | 5 | 2 | 12 | **Owner and legal decision** |
| 10 | CBT thought record | 1 | 2 | 3 | 4 | 10 | **Yes** |

Report export scores low on the four criteria but is the regulator-driven institutional wedge (draft UGC Chapter 5, Supreme Court guideline 10). Build it anyway; treat the rank as a floor.

**Top 8 to build, in order:** post-crisis follow-up tracker, safety plan builder, per-student trend flags, appointment email reminders, Hindi crisis and consent pages, sleep log, annual report export, grounding exercises. Anonymous-first onboarding and the thought record wait for a decision and clinician input.

### Specs (one paragraph each)

**1. Post-crisis follow-up tracker (risky without clinician sign-off).** When a provider acknowledges a `CrisisEvent`, create a follow-up record for that student with three due dates (suggested 24-48 hours, 1 week, 2 weeks: dates need clinician approval). Counsellor dashboard gets a "follow-ups due" list sorted by overdue, and marking a session done links to an `Appointment` or a short outcome code (no free text about the crisis). Overdue items raise a neutral in-app notice to the counsellor and a counsellor-only email via the job queue. Students are never sent crisis-labelled messages. Maps to draft UGC 3.4 ("minimum three sessions") and 3.5 (monthly review of crisis cases): add a count of crisis events and follow-ups completed to the institution aggregates. Needs a new table, so the schema owner must add the migration.

**2. Safety plan builder (clinician sign-off required for template wording).** A student-owned form following the six Stanley-Brown steps: warning signs, own coping strategies, people and places for distraction, people to ask for help, professionals and helplines (pre-filled from `utils/helplines.py`: 14416, 1800-599-0019, 112), and making the environment safer. Stored encrypted-at-rest if the platform adds that; visible to the student on a lock-screen-friendly page and printable; visible to a counsellor only if the student shares it (a per-plan flag, audited). Never auto-fill from chat or journal. Copy must say it is a planning aid, not treatment, and that the evidence is promising but not conclusive. Do not claim it "reduces suicide".

**3. Per-student PHQ/GAD trend with change flags.** The wellness report already charts PHQ-9 and GAD-7. Add a baseline-versus-latest delta, a "5 points or more" change marker for PHQ-9 (the commonly cited minimal important difference, see `product-market.md`), and a "no re-screen in 14 days" marker for students with a moderate or higher score. Keep it descriptive: no predictions, no risk scores. Thresholds need a clinician's review. Low build cost because the data and chart exist.

**4. Appointment reminders by email.** A `send_email` job already exists (`utils/mailer.py`). Enqueue a reminder 24 hours and 2 hours before an accepted `Appointment`, with the date, time and counsellor name only: no mention of mental health, scores or crisis. Include a cancel link. Evidence is for SMS and general medicine; email effect is UNVERIFIED, and students may check WhatsApp or SMS more, so treat email as a first step. Medication reminders by email are riskier (they disclose drug use if forwarded): leave out until prescriptions are decided.

**5. Hindi UI for the most important pages (high risk without review).** Scope: crisis card, helpline list, consent and age gate, signup and login, PHQ-9 and GAD-7 forms. Use the official published Hindi PHQ-9 and GAD-7 translations, not machine translation. Native speakers and a clinician must review everything, and the crisis phrase list in Hindi and Hinglish (`ai/severity.py`, O-20) must be tested before saying Hindi is supported. A language switch must set `<html lang>`. Do not call it "Hindi support" for chat until crisis detection is reviewed.

**6. Sleep log.** One row per night: bedtime, wake time, quality 1-5, optional note. Show a 14-day chart and average, and let the counsellor view it when linked. Make clear it is a diary, not treatment. The pooled digital-sleep evidence (section 4) refers to CBT-for-insomnia programmes, which we are not building.

**7. Anonymised annual report export.** One page and a CSV for the institution role: counts of students screened (by instrument), counselling sessions held, crisis events and follow-ups (no identifiers), counts by month, helpline and policy fields the institution types in. Reuse the existing small-cell rule (`MIN_AGGREGATE_GROUP`, default 5) and add the minimum figure to the footer. Known blockers: appointment `completed` is never set (O-14), there is no referral record, and the draft asks for "number diagnosed" which a screening tool must not report: report "screened positive" instead. Print view via a print stylesheet. Reports stay descriptive; do not claim they satisfy a Supreme Court or UGC duty.

**8. Grounding exercises.** A short 5-4-3-2-1 sensory exercise and a "name the feeling" screen beside the existing breathing page, with a visible stop option and the helpline link. Reduced-motion by default. No points or streaks. Low evidence, low risk; useful mainly as an acute self-help step.

**Deferred: anonymous-first onboarding (owner and legal decision).** A pseudonymous display name with the email hidden from counsellors until the student chooses to share would lower the entry barrier (only 56% of NTF respondents trusted administrations, per earlier research). But crisis follow-up needs a way to reach the student, DPDP consent and the 18+ gate still need identity, and "anonymous" is a claim we must not make. Needs a design that states exactly who can see what.

**Deferred: CBT thought record (clinician sign-off).** Cognitive restructuring works inside CBT packages; a stand-alone unguided thought record has no verified evidence and can feed rumination in a depressed student. If built: guided steps, a crisis scan of the text as for the journal, and optional sharing with the counsellor.

---

## 6. Claims we can honestly make on the landing page

Every row is a statement about our own product that the code or docs support. The "contrast" column uses only facts I read on primary pages (P), phrased about categories, not as attacks. Re-verify every contrast before each release, because vendors change.

| # | Exact wording | Why it is true (repo) | Contrast it supports | Verifying source (access 2026-11-24) |
|---|---|---|---|---|
| 1 | "If a check-in, journal entry or chat message shows signs of self-harm, your campus counsellor is alerted, and the alert escalates if nobody acknowledges it." | `utils/crisis.py` (alert job, escalation levels, stop on acknowledgement), `tests/test_crisis_durability.py`. Escalation email only when `CRISIS_ESCALATION_EMAIL` is set; say "can escalate" if not configured. Needs a counsellor on the institution. | Headspace says its AI companion Ebb is "not monitored in real time by a human" and entered information is "not shared with a care team unless the member chooses" (P). | https://www.headspace.com/ebb (P) |
| 2 | "Crisis help works even if the AI is down. It shows Tele-MANAS 14416, KIRAN 1800-599-0019 and 112." | `ai/severity.py` rule-based classifier, `utils/helplines.py`, `tests/test_safety.py` (128 tests). Numbers verified 2026-11 in `docs/SAFETY_RESEARCH.md`; re-verify quarterly. | Headspace's Ebb points US and Canadian users to 988 and is offered only in the US, UK, Canada and Australia (P). Youper, now closed, referred to US numbers (P). | https://www.headspace.com/ebb (P) ; https://www.youper.ai (P) |
| 3 | "PHQ-9 and GAD-7 are scored on our server with the standard score bands. Any answer above zero on PHQ-9 question 9 shows help numbers straight away." | `routes/patient.py` save-assessment, `tests/test_safety.py`, `docs/SAFETY_RESEARCH.md`. Item-9 rule is our design choice, stated as such. | None needed. | Score bands: https://hiv.uw.edu/page/mental-health-screening/phq-9 (S) |
| 4 | "Counsellors see only students linked to them. Institution figures are totals only, and any group smaller than 5 is hidden." | `routes/provider.py` (`assigned_patients`, `min_group`, default 5), `tests/test_provider_scope.py`. Exception: open crisis events of the same institution stay visible to its counsellors, and every such view is audited, so say this in the privacy page, not hide it. | None needed. | repo |
| 5 | "You can download or delete your data from your account." | `routes/auth.py` `/account/export`, `/account/delete`, `tests/test_privacy.py`. | None needed. | repo |
| 6 | "Our AI companion says it is an AI, is instructed not to diagnose or name medicines, and does not replace a counsellor. Counselling and prescribing are done by people." | `templates/chat.html`, `ai_prompts/psychologist_system.txt`, `ai/service.py`. Contrast source: clause 5.4 of the Telemedicine Practice Guidelines bars AI/ML platforms from counselling or prescribing. Caveat: `analyze_medication_adherence` calls a model on medication logs, so keep the word "advice" out of the claim and review that function. | AI "therapist" positioning is not allowed for Indian telemedicine platforms. | https://esanjeevani.mohfw.gov.in/assets/guidelines/Telemedicine_Practice_Guidelines.pdf (P, clause 5.4) |
| 7 | "Built for Indian colleges: Indian helplines, an 18+ sign-up with recorded consent, and a counsellor view." | `utils/helplines.py`, signup `age_confirm` and `consent` stored in `ConsentRecord`, provider dashboard. | Open-market AI companions often work in English and in US-centric ways: Headspace's Ebb is English only in four countries (P). | https://www.headspace.com/ebb (P) |
| 8 | "We never attach points, streaks or badges to your mood or screening scores." | `tests/test_idempotency.py::test_award_points_daily_cap_and_never_for_mood`, `docs/SAFETY_RESEARCH.md`. | Evidence that gamification did not improve adherence in depression apps (beta -1.93, P=.40) supports the choice, not a claim about others. | https://mental.jmir.org/2021/11/e32199 (S) |
| 9 | "Helplines like Tele-MANAS are free for everyone and are not run by your college. We show them next to your college counsellor, not instead of them." | Helpline list plus counsellor booking. | National helplines are open to all and are not tied to a campus; the draft UGC guideline asks colleges to link their own 24x7 helpline to Tele-MANAS (draft text, section 4g). | https://mmcc.edu.in/wp-content/uploads/2026/01/UGC-mental-health-well-being-feedback-Noticeand-policy.pdf (P) |
| 10 | "This is a wellness and screening tool, not a medical device. It does not diagnose." | README, `docs/RULES.md`, results copy. | None needed. | repo |

**Claims we may make only after the build:** "Counsellors can export an anonymised annual report" (after item 7 of section 5); "Three-session follow-up tracking after a crisis" (after item 1); "Hindi crisis help" (after review).

**Six strongest claims, in order:** 1, 2, 3, 4, 5, 6. Claims 1, 2 and 6 carry a named, neutral, primary-source contrast.

### Claims we must NOT make

| Do not say | Why |
|---|---|
| "Best", "number one", "first", "only", "most trusted", "unlike every other app" | Unprovable superlatives; I found no verified market-gap evidence. |
| "Clinically proven", "reduces depression", "prevents suicide", "predicts crisis", "detects every crisis" | No trial of this product; chatbots and item 9 both miss cases; digital tools show small to moderate effects. |
| Any outcome number (retention, "80% early detection", hours saved) | None measured. |
| "100% confidential", "completely anonymous", "end-to-end encrypted", "encrypted at rest" | Crisis exceptions, counsellor access and audit logs exist; encryption at rest is not done (O-04). |
| "DPDP compliant", "Supreme Court or UGC compliant", "NABH, ISO, HIPAA certified", "meets MANAS-SETU requirements" | No audit or certification; the UGC text is a draft and the portal is unconfirmed. |
| "Endorsed by" or "approved by" MoHFW, UGC, NIMHANS, Tele-MANAS, NTF, Supreme Court | No agreement. |
| "24x7 monitored", "a counsellor is always watching" | Out-of-hours safety is helplines shown to the student. |
| "AI counsellor", "AI therapist", "AI gives medicine advice" | TPG clause 5.4. |
| "Hindi supported" | Not built. |
| "Safe for under 18s" | 18+ only. |
| Named competitor weaknesses ("Wysa has no counsellor view", "Amaha has no dashboard", "Headspace does not screen") | Absence on pages I read is not proof; vendors change; not verified. |
| Using Mpower, Lissun or Amaha self-reported outcome numbers | Company-reported, unaudited. |

---

## 7. Indian rules on comparative and health advertising (for legal review)

**All of this is UNVERIFIED legal commentary unless marked P. Get a lawyer to review the landing page before launch.**

| Rule | What I read | Tag |
|---|---|---|
| Consumer Protection Act 2019, section 2(28) "misleading advertisement" | Secondary sources describe it as an ad that falsely describes a product or service, gives a false guarantee, is likely to mislead, or deliberately conceals important information; section 89 penalties are cited. I could not download the Act text. | S UNVERIFIED |
| CCPA Guidelines for Prevention of Misleading Advertisements and Endorsements, 2022 (notified 9 June 2022) | Cover bait ads, free claims, surrogate ads and endorsements, and apply to advertisers, agencies and endorsers. Penalty up to Rs 10 lakh, Rs 50 lakh for repeats, per summaries. The official PDF was unreachable (connection refused). Valid-ad conditions and due-diligence wording not read. | S UNVERIFIED |
| ASCI Code | A report quotes ASCI saying comparative ads are allowed if factual and capable of objective substantiation, and must not denigrate, attack or discredit other brands (Chapter IV.1(e) in one decision report). Healthcare ads are often upheld against for unsubstantiated claims. I did not read the Code. | S UNVERIFIED |
| Drugs and Magic Remedies (Objectionable Advertisements) Act, 1954 (text as on 15 April 2026) | The schedule lists "diseases and disorders of the brain", epilepsy, hysteria and "insanity" among conditions for which advertising a drug that suggests it can treat them is barred (sections 3, 4, 5). "Drug" is defined to include substances and articles for diagnosis, cure, treatment or prevention. Whether a software app is a "drug" or "article" is a legal question I cannot answer; the safe practice is to avoid cure and treatment language. | P for the text; applicability UNVERIFIED |
| Telemedicine Practice Guidelines 2020, clause on advertising | RMPs may not solicit patients through advertisements (clause near line 774 of the PDF). Relevant if the landing page ever advertises named doctors. | P |

Practical rules that follow whatever the law says (proposal): keep claims about our own features and test-backed; avoid naming rivals except for dated, primary-sourced, neutral facts; avoid treatment and cure words; show the date and source of any comparative fact; keep a file of evidence for each claim.

---

## 8. What is stale in our old research

### In `docs/research/product-market.md`

| Section | Old text | Correction | Source |
|---|---|---|---|
| 2 (Youper row), PRD section 3.2 | "Youper: US-centric AI emotional-health assistant ... status UNVERIFIED" | "Youper discontinued its services on 30 September 2026. Remove it from the active competitor list." | https://www.youper.ai (P, 2026-11-24; single source, no news corroboration) |
| 2 (Woebot row) | "App retired 30 June 2025" | Still correct. Add: Woebot Health's homepage lists only enterprise, provider and payer offerings and does not state that a consumer app exists. | https://woebothealth.com (P, partial) |
| 2 (Headspace, Calm row) | "No screening, no human handoff, USD pricing, English-first" | Too strong. Headspace now sells therapy and has an AI companion Ebb (English, US/UK/Canada/Australia, 18+, not human-monitored). I could not verify "no screening" for either app. Replace with: "Ebb is not available in India and is not monitored by a human in real time (Headspace)." | https://www.headspace.com/ebb (P) |
| 2 (Wysa row) | "6 new languages Dec 2025" | Not re-verified. Add: Hindi version launched April 2024 (company release); GBP 5.3m Wellcome grant for rural India girls (S). | links in section 1.1 |
| 2 (Amaha row) | "claims 700,000+ individuals covered (UNVERIFIED)" | Press now says 450,000+ sessions, 100,000+ clients, 270+ professionals (company-reported); Rs 100 crore raise reported Oct 2026. Its college page does not describe formal screening or a dashboard. | https://amahahealth.com/services/college-wellness-programme/main (P) ; BioSpectrum (S) |
| 2 (Tele-MANAS row) | "cumulative 23.8 to 29.8 lakh (inconsistent)" | Not inconsistent in time: 23.82 lakh was reported in July 2025 (to mid-March 2025) and 29.82 lakh in Dec 2025. The per-year numbers (2,848; 47,067; 66,045; 121,151) still cannot be reconciled with the cumulative figure. | https://www.freepressjournal.in/tech/new-delhi-over-298-lakh-calls-handled-by-tele-manas-cells-govt-strengthens-womens-mental-health-support (S) |
| 2 (MANODARPAN) | "Directory and policy, UNVERIFIED depth" | Has a tele-counselling helpline: 69 counsellors and 3,32,877 calls by 10 March 2026 per a secondary report; no impact evaluation (UNVERIFIED). | newkerala link in section 1.4 (S) |
| 1.6C UGC draft | "one counsellor per 500 students at larger institutions ... at least three follow-up sessions ... tracking on a MANASSETU portal" | Primary text now read. Wording is hedged: "1 qualified clinical psychologist/psychologist/mental health professional for any institution where 100 or more students are enrolled **may be considered**. Currently, a ratio of 1 per 500 students ... **may be considered**." Faculty mentors "for example 1:500", peer supporters "for example 1:100". Parents informed in a crisis (3.3). "Structured follow-up counselling (minimum three sessions)" (3.4). Monthly review of all crisis cases (3.5). HEIs "shall run a 24x7 helpline" and "interlink the Tele MANAS and other established helplines" (4f, 4g). Reports to UGC on MANAS-SETU "containing only anonymized data"; personal identifiers stored encrypted with access limited to the centre (Chapter 5). The report list includes number "diagnosed". Clinical records "coded/anonymized for storage" and may be destroyed one year after graduation. Feedback was invited to 29 January 2026. CMHLP's public comments (Feb 2026) criticise unclear crisis definitions, parent notification, reporting of suicidal ideation without safeguards, and the "may" wording on the portal. No final notified version found; MANAS-SETU live status UNVERIFIED. Some press says "one per 100", which is the small-institution reading and not the text. | draft text: https://mmcc.edu.in/wp-content/uploads/2026/01/UGC-mental-health-well-being-feedback-Noticeand-policy.pdf (P) ; https://cmhlp.org/wp-content/uploads/2026/02/CMHLP-comments-on-UGC-mental-health-in-HEIs-draft-guidelines.pdf (P) |
| 1.6B / open items (NTF) | "final report due 31 October; year unconfirmed; UNVERIFIED whether published" | A Supreme Court order of 27 May 2026 extended the NTF's final report to 31 October 2026. The NTF site hosts an **interim report uploaded 8 June 2026** (page read; PDF body not read). Secondary summary: 65% of 2,119 institutions surveyed have no access to any mental health service provider, student suicides 7.6% of the total in NCRB 2022, and recommendations on central data, uniform reporting and accessibility (UNVERIFIED). Final report: I found no evidence it has been filed or published as of 2026-11-24. | https://ntf.education.gov.in/document/interim-report-of-the-national-task-force/ (P, metadata only) ; https://visionias.in/current-affairs/news-today/2026-06-13/society/interim-report-of-national-task-forcentf-concerning-students-mental-health-released (S) ; https://news.careers360.com/student-suicide-ntf-report-field-visits-30-heis-10-states-task-force-iit-delhi-mental-health-gender-equality-supreme-court-order/amp (S) |
| 6.1 DPDP | "Rules notified 13 or 14 Nov; consent managers later; Rules 3, 5-16, 22-23 after 18 months" | Consistent sources: Rules 1, 2, 17-21 effective on notification (13 Nov 2025); Rule 4 (consent managers) one year later (mid-Nov 2026, now passed); the rest about 13 May 2027. New: a DPDP (Removal of Difficulties) Order, October 2026 (one source says 5 October, S.O. 5458(E); another snippet says 12 October), adds the word "of" in section 9 and changes "periodic audit" to "periodic data audit" in section 10; the reporting source says it changes no dates and creates no healthcare or education exemption. Keep designing to the stricter reading. All UNVERIFIED against the Gazette. | https://ssrana.in/articles/dpdp-removal-of-difficulties-order-2026-what-has-been-changed-for-childrens-data-and-sdf-audits/ (S) ; https://www.legal500.com/firms/237811-saga-legal/c-india/news-and-developments/the-privacy-timer-starts-now-analysing-the-dpdp-rules-and-its-18-month-countdown (S) |
| 6.3 Telemedicine | "AI cannot counsel or prescribe ... clause 5.4 ... UNVERIFIED against primary; List C" | **Verified from the primary PDF.** Clause 5.4: "Technology platforms based on Artificial Intelligence/Machine Learning are not allowed to counsel the patients or prescribe any medicines to a patient. Only a RMP is entitled to counsel or prescribe ..." Drug lists in the TPG text are O, A, B and a "Prohibited List" (Schedule X and NDPS substances); "List C" is a telepsychiatry-guideline label. This is the March 2020 text; later amendments not checked. | https://esanjeevani.mohfw.gov.in/assets/guidelines/Telemedicine_Practice_Guidelines.pdf (P) |
| 9 Open items | Competitor status for Youper, Amaha, YourDOST; UGC finalisation; NTF final report; TPG clause | Youper, Amaha, UGC, NTF and TPG are updated above. YourDOST remains unverified. | this document |

### In `docs/STATUS.md` and `docs/TRACKER.md` (owned by the lead; suggestions only)

| Statement | Issue | Evidence |
|---|---|---|
| STATUS: "Crisis detection and escalation: Partial ... alert durability and timed escalation are open (O-01, O-02)" | Code and tests now exist for durable alert plus timed escalation and for journal and socket-chat crisis events. I did not run them. Re-check after the full suite passes, then update the row and close O-01 and O-02. | `utils/crisis.py`, `routes/patient.py` lines using `record_crisis`, `tests/test_crisis_durability.py` |
| STATUS: "Prescriptions ... needs a decision (O-06)" and "assigned-only scoping is a product decision (O-07)" | Decisions P-01 and P-02 are made and (per the code) implemented: feature flag and `ProviderPatient` scope. | `routes/provider.py` (`assigned_patients`), brief |
| STATUS: "Remote patient monitoring, predictive analytics, peer support: Missing" | Still true. Also missing and worth listing: safety plan, follow-up tracker, reminders, annual report export, Hindi, sleep log (section 3). | section 3 |

---

## 9. What I could not verify

- Whether UGC has issued a final version of the mental-health guidelines, and whether MANAS-SETU is live (searches found neither; absence is not proof).
- The full text of the Supreme Court orders (July 2025, January 2026) and the NTF interim report PDF.
- CCPA 2022 guideline text, the Consumer Protection Act 2019 text, and the ASCI Code text (all UNVERIFIED in section 7).
- Official pages for Wysa, YourDOST, MindDoc, Calm, Daylio, Bearable, Finch, Sanvello, 7 Cups and TimelyCare returned errors, empty or truncated content; their entries rest on search summaries and store listings (S).
- Whether Sanvello still operates; whether BetterHelp serves India; Practo's psychiatry pricing; Point and Click Solutions; what "Gaia" refers to.
- Any competitor's PHQ-9 use, safety-plan feature, reminders or accessibility conformance: left as "?" in the matrix.
- The "45%" safety-planning figure; the Stanley-Brown 2018 paper itself (PMC page blocked).
- Bahmni and OpenHMIS page bodies did not load; those features come from a search summary.
- Whether the full test suite passes today; "Built" in our column means code and a test file exist.
