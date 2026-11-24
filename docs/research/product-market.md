# MindFull Horizon: product and market research

Research date: 2026-11-24. Method: web search plus page fetches. Every fact carries a source URL. **UNVERIFIED** = only seen in a secondary source, a search snippet, or not confirmed at all. Where a primary PDF could not be read (NMHS summary returned HTTP 403; the SC Jan-2026 PDF is image/compressed) the figure is taken from a secondary page and flagged. "Proposal" = my suggestion, not a fact.

Product context read from the repo: README.md, docs/requirements.md, docs/STATUS.md. Relevant status facts: PHQ-9/GAD-7 scoring is client-supplied with no item-9 handling; socket chat has no crisis check; crisis escalation is a stub with no provider alert or audit log; endpoints are unauthenticated in places; PHI is stored in plaintext; the landing page still has placeholder stats and testimonials (docs/STATUS.md).

---

## 0. Decision-relevant summary

1. Institutions now have legal pressure (Supreme Court July 2025 and Jan 2026, UGC draft Jan 2026) to run a mental-health policy, staff counsellors, publish helplines, keep anonymised records and report annually. A tool that makes this reporting and referral workflow easy is a sellable wedge. A generic "wellness app" is not.
2. Open-market mental-health apps retain about 3% of users at day 30 (median). The requirements doc's "70% daily active users" target is not credible; replace it.
3. Chatbot evidence is small (g about 0.3 on depression/anxiety), shrinks at follow-up, and the best-known CBT chatbot (Woebot) shut its app in June 2025. Position the AI as a supportive companion plus triage to humans, never as therapy.
4. In India, AI cannot legally counsel or prescribe under the Telemedicine Practice Guidelines 2020 (secondary sources; verify against the official PDF). Only a registered medical practitioner may prescribe, and never from the controlled list over tele-consult.
5. PHQ-9 item 9 alone misses many at-risk people (about 36-39% of attempts/deaths within 30 days came from people answering "not at all" in one US study). Crisis safety needs several signals and a human loop, not one score.
6. Before any public deploy, the Critical items in docs/STATUS.md (auth, role escalation, crisis logic, PHI plaintext) are prerequisites, not features.

---

## 1. The problem in India

### 1.1 Prevalence and treatment gap

| Fact | Source |
|---|---|
| NMHS 2015-16 (NIMHANS, MoHFW): overall weighted prevalence of any mental morbidity 13.7% lifetime and 10.6% current (adults 18+). Summary reports are the official source. | Official PDF (403 on fetch): https://mohfw.gov.in/sites/default/files/National%20Mental%20Health%20Survey%2C%202015-16%20-%20Summary%20Report_0.pdf ; figures seen via search results listing https://pmc.ncbi.nlm.nih.gov/articles/PMC6201882 and https://www.pubmed.gov/32126902/ (UNVERIFIED against primary) |
| Treatment gap: 84.5% for overall mental morbidity; 79.1% depression; 80.4% common mental disorders; 82.9% anxiety disorders. Range quoted elsewhere 70-90%. | https://www.pubmed.gov/32126902/ ; https://pmc.ncbi.nlm.nih.gov/articles/PMC6201882 (via search snippets, UNVERIFIED against primary) |
| NMHS summary via PARI: about 150 million Indians need mental-health care; treatment gap 28-83% depending on disorder, above 60% for all except epilepsy. | https://ruralindiaonline.org/en/library/resource/national-mental-health-survey-of-india-2015-16-summary/ |
| NMHS sample: 34,802 adults interviewed, 34% aged 18-29. No student-specific or age-18-29 prevalence or stigma figure was found. | https://pmc.ncbi.nlm.nih.gov/articles/PMC8992756 (snippet) , UNVERIFIED |
| NMHS is general-population, 2015-16, pre-COVID. It is not a student prevalence figure. Do not quote it as one. | (analytic note) |

### 1.2 College-student prevalence (no single national figure exists)

- Kashmir cross-sectional study, fieldwork Jan-Apr 2024, n=1,471, age 18-26, PHQ-9/GAD-7: severe depression 12.52%, anxiety 24.26%, high stress 19.17%, higher in females. Single region, convenience-type sample. https://pmc.ncbi.nlm.nih.gov/articles/PMC12457365/
- Indian undergraduate medical students (meta-analysis, Natl J Community Med, Oct 2024): pooled depression 48%, anxiety 54%, suicidal ideation 21%, I-squared about 98%. Medical students are a high-stress subgroup and heterogeneity is extreme; do not generalise. https://doaj.org/article/129a1622e72f4faa9e934634835230be
- International context: WHO World Mental Health International College Student initiative, 13,984 first-year students in 8 mostly high-income countries (India not included): 12-month MDD 18.5%, GAD 16.7%; over a third screened positive for at least one of six disorders. https://www.apa.org/news/press/releases/2018/09/freshmen-mental-health ; paper: Auerbach et al., J Abnormal Psychology 127(7):623-638, DOI 10.1037/abn0000362 (exact "31%" figure not confirmed).
- National Task Force (NTF) survey, more than 2.43 lakh HE students: 9% had suicidal thoughts "often or very often" in the past year; 15% recalled weeks of severe distress/low mood/anxiety; 32% said their institution offered no counselling; 56% trusted the administration to handle serious issues fairly. NTF itself says the sample is not representative and findings are preliminary. https://www.deccanchronicle.com/amp/southern-states/telangana/survey-flags-student-mental-health-concerns-1991766 (secondary news; NTF primary not read)

### 1.3 Student suicide (NCRB ADSI)

- ADSI 2023: 13,892 student suicides, the highest in a decade, 8.1% of 171,418 total. https://news.careers360.com/ncrb-report-2023-over-13800-student-suicide-deaths-highest-in-10-years-national-crime-records-bureau-maharashtra-up-tn/amp ; https://cmhlp.org/imho/blog/takeaways-from-the-ncrb-data-on-suicide-for-2023-what-has-changed/
- ADSI 2024 (released May 2026 per Careers360): 14,488 student suicides, 8.5% of total, +4.3% on 2023, about 80% above 2014 (8,068). 7,669 male and 6,819 female. 2,032 attributed to exam failure (about 14%). Maharashtra highest (1,909). https://news.careers360.com/student-suicide-ncrb-report-2026-rise-80-pc-10-years-1000-under-18-jobs-unemployment-exam-mental-health-school-higher-education/amp ; https://www.outlookindia.com/education/career-stress-mental-disorders-govt-lists-causes-of-student-suicides-experts-push-back (secondary; primary NCRB PDF not read, UNVERIFIED)
- Caveats: NCRB "student" includes school pupils, not only college students (the Supreme Court in Jan 2026 asked NCRB to separate the two: https://www.scobserver.in/supreme-court-observer-law-reports-scolr/amit-kumar-v-union-of-india-guidelines-on-student-suicide-prevention/). The data are police-recorded and widely considered under-reported (https://www.tribuneindia.com/news/india/indias-student-suicide-rate-has-surpassed-overall-trend-population-growth-rate-report). Cause attribution is police-assigned. A Sabrang article gives 13,044 for 2023; that matches 2022, so it is likely a mix-up.

### 1.4 Counsellor capacity

- No national count or sector-wide counsellor:student ratio was found. https://news.careers360.com/ugc-mental-health-centre-must-university-psychologist-psychiatrist-helpline-draft-guideline-higher-ed-student-faculty-nrf-icmr-who/amp (draft norm only)
- Reported RTI-based IIT figures: IIT (BHU) 1:4,750, IIT-Kharagpur 1:1,136, IIT-Roorkee 1:1,317, from a secondary exam-prep site. UNVERIFIED. https://www.civilsdaily.com/news/several-iits-have-far-fewer-counsellors-than-recommended-by-ugc-rti-data/
- The "1:2000 caseload" persona in the brief is an illustrative assumption, not a sourced national number.
- NTF/Supreme Court: faculty must not be labelled "counsellors" without training. https://www.scobserver.in/supreme-court-observer-law-reports-scolr/amit-kumar-v-union-of-india-guidelines-on-student-suicide-prevention/

### 1.5 Stigma and help-seeking

No India-specific student stigma statistic was verified in this pass. The NTF finding that only 56% trust administrations to handle serious issues fairly (link above) is the closest primary-adjacent datapoint and supports building an anonymous, low-exposure entry point. Medical-student study of why depressed students do not seek treatment: https://doi.org/10.1177/0253717620982326 (abstract not read, UNVERIFIED content).

### 1.6 Supreme Court and regulator directives (institution requirements)

**A. Sukdeb Saha v. State of Andhra Pradesh** (NEET-aspirant death case). Bench: Vikram Nath and Sandeep Mehta, JJ. Date: 25 July 2025. Citation reported variously as 2025 INSC 893 / 2025 LiveLaw (SC) 740. Fifteen interim guidelines under Articles 32 and 141, binding on schools, colleges, universities, coaching centres until legislation/regulation exists; grounded in the right to mental health under Art. 21. Order PDF: https://api.sci.gov.in/supremecourt/2024/18489/18489_2024_3_1502_62660_Order_25-Jul-2025.pdf (not read in full). Summary used: https://www.livelaw.in/amp/supreme-court/in-neet-aspirants-death-case-supreme-court-issues-guidelines-to-protect-mental-health-of-students-in-colleges-coaching-centres-298795 ; also https://www.verdictum.in/court-updates/supreme-court/sukdeb-saha-v-the-state-of-andhra-pradesh-2025-insc-893-mental-health-policy-educational-institutions-1586163

Requirements that matter for the product (LiveLaw summary, verify wording in the judgment):
1. Uniform mental-health policy based on UMMEED draft guidelines, MANODARPAN and the National Suicide Prevention Strategy; reviewed annually; published.
2. At least one qualified counsellor/psychologist/social worker for institutions with 100 or more students; smaller ones need formal referral links.
3. Optimal student:counsellor ratio (no number given); mentors for small batches, especially at exam time.
5. Written referral protocol; Tele-MANAS and other helplines shown prominently in hostels, classrooms, common areas and websites.
6-7. Staff trained at least twice a year in psychological first aid, warning signs, self-harm response and referral, including for SC/ST/OBC/EWS, LGBTQ+, disabled and bereaved students.
8. Confidential complaint mechanisms for harassment, ragging and bias; neglect leading to self-harm treated as institutional culpability.
10. **Anonymised records and an annual report** on wellness interventions, referrals, training and activities to a regulator (State Education Dept, UGC, AICTE, CBSE).
Other: career counselling, hostel safety, exam-pressure review. Union to file a compliance affidavit within 90 days.

**B. Amit Kumar v. Union of India**, 15 January 2026, 2026 INSC 62, Pardiwala and Mahadevan, JJ. Follows the 24 March 2025 order that created the National Task Force. Source: https://www.scobserver.in/supreme-court-observer-law-reports-scolr/amit-kumar-v-union-of-india-guidelines-on-student-suicide-prevention/ ; https://www.verdictum.in/court-updates/supreme-court/amit-kumar-ors-v-union-of-india-2026-insc-62-student-suicides-higher-educational-institutions-ntf-model-suicide-prevention-postvention-protocol-1604597 (the SC PDF https://api.sci.gov.in/supremecourt/2024/40105/40105_2024_7_301_67552_Judgement_15-Jan-2026.pdf could not be text-extracted, so I did not confirm it is this judgment).
Directions to HEIs (Para 45): report any student suicide or unnatural death to police immediately (campus, hostel, PG, off-site; in-person, distance and online students); annual report of such deaths to UGC/professional regulators or Ministry of Education; round-the-clock qualified medical help for residential HEIs (on campus or within 1 km); fill faculty/leadership vacancies within four months; clear scholarship backlogs; strictly follow UGC anti-ragging 2009, equity 2012, sexual-harassment 2016 and grievance 2023 regulations. NCRB to separate school from HE students; SRS to hold central suicide data for ages 15-29.
Asks the NTF (non-binding) to produce model SOPs on well-being audits (possibly feeding NAAC), faculty training, counselling services (confidentiality rules, online services, follow-up, feedback), a single "Suicide Prevention and Postvention Protocol", mandatory accessibility audits, anonymised feedback and avoiding indiscriminate use of "counsellor".
Not specified: counsellor ratios, helpline numbers, penalties ("serious consequences"), NTF final report deadline (one article says the final report is due 31 October; year unconfirmed, UNVERIFIED whether it has been published).

**C. UGC "Guidelines on Uniform Policy on Mental Health & Well-Being for HEIs"**, circulated 13 January 2026 as a DRAFT for public consultation. Proposals: Mental Health & Well-being Centre; one counsellor per 500 students at larger institutions (and at least one professional for institutions with 100+ students); 24x7 helpline recommended; tracking on a "MANASSETU" portal with annual reports; parents informed in crises; at least three follow-up counselling sessions post-crisis. I found no confirmation of a final notified version. Sources: https://theprint.in/india/education/ugcs-draft-mental-health-norms-call-for-standardised-student-counselor-ratio-well-being-centres/2827423 ; https://www.scconline.com/blog/post/2026/01/17/ugc-guidelines-for-mental-health-in-higher-educational-institutions/ ; ratio wording differs between sources, UNVERIFIED.

**Product implications:** (a) anonymised annual-report export is a core institutional feature; (b) helpline display and referral protocol must be built into the product; (c) post-crisis follow-up tracking (3 sessions) is a workflow to support; (d) confidentiality SOP and audit trail are buyer requirements; (e) "counsellor" labels in the UI should map to verified credentials; (f) accessibility is an NTF recommendation (see section 6).

---

## 2. Competitors and adjacent products

Evidence column: "RCT" means randomised trial found; I did not read most primary papers.

| Product | Target user | Core features | Business model | Evidence base | Weaknesses / our differentiation |
|---|---|---|---|---|---|
| Wysa (Touchkin; India/UK origin) | Consumers, employers, health systems, some public-health partners | AI CBT-style chatbot, self-help tools, human coach tier, "Wysa Copilot" hybrid AI+clinician platform, intake assistant; multilingual (6 new languages Dec 2025) | Freemium; paid premium; enterprise/payer contracts. "B2B2C" is my inference. | FDA Breakthrough Device designation May 2022 (a designation, not approval); published trials mostly UK/US/chronic-pain populations; no India-college RCT found. | Little campus workflow (no caseload/risk queue, no institutional compliance reporting found). Differentiate on counsellor workflow, anonymised institutional reporting, India context. Sources: https://www.businesswire.com/news/home/20220512005084/en ; https://www.wysa.com/clinical-evidence ; https://blogs.wysa.io/blog/company-news/wysa-launches-multilingual-capabilities-to-broaden-access-to-mental-health-support-globally |
| Youper | Consumers (US-centric) | AI emotional-health assistant, mood tracking | Subscription (UNVERIFIED) | No RCT found in this pass; 2025 status not found | UNVERIFIED across the board. Not an India-campus player. |
| Woebot | Was consumer and payer-facing | Scripted CBT chatbot (rules-based, not generative); about 1.5M users | Pivoted to enterprise/payers | Several published trials (not re-read here) | **App retired 30 June 2025.** Founder cited the cost/difficulty of FDA marketing authorization and unsettled LLM regulation. Lesson: scripted-safety plus regulation cost; do not claim medical-device functions. https://www.statnews.com/2025/07/02/woebot-mental-health-chatbot-shuts-down-founder-says-ai-moving-faster-than-regulators/ ; https://www.mobihealthnews.com/news/woebot-health-shutting-down-its-app |
| Headspace, Calm | General consumers incl. students | Guided meditation, sleep, breathing | Consumer subscription, some university/employer deals | Meta-analysis of 10 mobile-mindfulness studies (958 university students) shows improved stress/wellbeing; an RCT of 561 students/staff found small effects (d=0.16 stress, 0.16 depression). Evidence is for stress and wellbeing, not clinical depression care. | No screening, no human handoff, USD pricing, English-first. https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9856434/ ; https://link.springer.com/article/10.1007/s12144-021-01762-z |
| YourDOST | Colleges, corporates, individuals | Online counselling and helplines with human counsellors; anonymity | Institution-funded (free to students, e.g. IIT Kanpur, Haryana helpline for 1 lakh+ students); corporate programmes | Outcome evidence not found, UNVERIFIED | Human capacity is the bottleneck and it is a separate channel, not integrated with the campus's own counsellors. Differentiate by augmenting in-house counsellors. https://iitk.ac.in/counsel/cmhw/pages/external-counselling.php ; https://indiaeducationdiary.in/?p=85077 ; https://www.indianstartuptimes.com/startup-deep-dive/yourdost-deep-dive/ |
| Amaha (ex-InnerHour) | Individuals, colleges, corporates | Therapy and psychiatry (online and clinics), college wellness programme, self-help app | Per-session fees (about Rs 1,000 in one comparison, UNVERIFIED) plus institutional programmes; claims 700,000+ individuals covered (UNVERIFIED) | Not found | Clinic-style paid care; not a campus triage layer. https://amahahealth.com/services/college-wellness-programme/main |
| Tele-MANAS (MoHFW, 14416) | Everyone, free | 24x7 tele-mental-health, 20 languages | Government | Utilisation: Lok Sabha Q2228 (12 Dec 2025) call counts 2,848 (2022), 47,067 (2023), 66,045 (2024), 121,151 (2025 to 4 Dec); other 2025 replies cite cumulative 23.8 lakh to 29.8 lakh calls (inconsistent, UNVERIFIED) | A phone line, no campus context. We must integrate and display it, not compete with it. https://eparlib.sansad.in/bitstream/123456789/3017708/2/AU2228_0CSctD_hindi.pdf ; https://www.tribuneindia.com/news/india/16-lakh-calls-on-mental-health-helpline-in-2-years |
| Campus portals: MANODARPAN (MoE), UGC MANASSETU (draft), UMMEED guidelines, IIT counselling cells | Students on specific campuses | Information, helplines, referral | Government/institutional | Not found | Often directories and policy, not a working triage/caseload tool. UNVERIFIED depth; these are named in the SC and UGC texts above. |

Honest gaps: I did not verify pricing, user numbers or current status for Youper, Amaha, YourDOST or Headspace/Calm in India. Wysa's India-specific traction and any government partnership were not found.

Positioning: none of the above, as found, offers the full loop of student check-in, validated scoring, risk triage to a campus counsellor with a time-stamped acknowledgement trail, and anonymised institutional reporting aligned to the Supreme Court guidelines. That claim is my inference from a limited scan, not a verified market gap.

---

## 3. Evidence on what works

### 3.1 Chatbots and digital CBT
- Conversational-agent RCT meta-analysis (JMIR 2023): short-term depression g=0.29 (CI 0.20-0.38) and anxiety g=0.29 (0.21-0.36); long-term effects mostly not significant. https://www.jmir.org/2023/1/e43862
- An earlier npj Digital Medicine meta-analysis reported g=0.64 for depression from 15 RCTs but with a very wide CI (0.17-1.12); treat as an outlier. https://www.nature.com/articles/s41746-023-00979-5 (page needed login; figure from search snippet)
- 2026 reviews reported by search (primary pages not opened, UNVERIFIED): npj Digital Medicine review to Oct 2025, depression g=0.31 and anxiety g=0.28; commercial-chatbot review with depression g=-0.35 (about 1.6 PHQ-9 points, below the 5-point minimal clinically important difference) and uncertain anxiety; JMIR 2026 CBT-chatbot follow-up g=-0.32 depression and non-significant anxiety. https://www.jmir.org/2026/1/e104186/PDF ; https://karger.com/pps/article/doi/10.1159/000552072/948904/Commercial-AI-Based-Mental-Health-Chatbots-as-Low
- Reading: small, short-lived benefit on symptoms, strongest in people with mild-to-moderate symptoms; not a substitute for care. APA advises not relying on generative-AI chatbots for psychotherapy because evidence on safety and efficacy is insufficient (Nov 2025). https://www.apa.org/topics/artificial-intelligence-machine-learning/health-advisory-chatbots-wellness-apps ; https://www.apa.org/news/press/releases/2025/11/ai-wellness-apps-mental-health
- No India-specific college-student chatbot RCT was found.

### 3.2 Measurement-based care (PHQ-9/GAD-7)
- Routine outcome feedback gives small average gains: Hedges g=0.28 (Shimokawa 2010, OQ feedback added to usual treatment); a 2021 depression-specific meta-analysis found MBC reduces severity and raises remission but response-rate difference was not significant (OR 1.66, CI 0.66-4.17). One review put the pooled effect at d=0.15. https://www.psychiatrist.com/jcp/measurement-based-care-depression ; https://link.springer.com/article/10.1007/s10488-022-01236-9
- MBC works when a clinician sees and acts on scores. A self-scoring app with no follow-up gets little of this benefit. That is why the provider loop is the core product.
- PHQ-9 item 9: one-year attempt risk rose from 0.4% (answering "not at all") to 4% ("nearly every day"), death from 0.03% to 0.3%; but 39% of attempts and 36% of deaths within 30 days occurred among those answering "not at all". Persistent positive responses carry the most risk. US health-system data; generalisation to Indian students UNVERIFIED. https://ps.psychiatryonline.org/doi/10.1176/appi.ps.201200587 ; https://pmc.ncbi.nlm.nih.gov/articles/PMC4993156 ; https://www.psychiatrist.com/jcp/suicide-risk-and-phq-responses/
- US Preventive Services Task Force does not recommend suicide-risk screening in general populations, per a review cited at the above links. Implication: market the tool as support and triage, not as a suicide detector.

### 3.3 Engagement and retention
- Baumel et al., JMIR 2019 (93 Android mental-health apps with 10,000+ installs): median 15-day retention 3.9% and 30-day retention 3.3%; median daily active rate 4.0%. 30-day retention by type: peer support 8.9%, trackers 6.1%, mindfulness 4.7%, breathing exercises 0.0%. Open-market apps, not institution-embedded. https://pmc.ncbi.nlm.nih.gov/articles/PMC6785720
- Implication: breathing/yoga/music content alone will not retain users. Retention must come from a reason to return: counsellor follow-up, appointments, reminders tied to the student's own goals.
- Drivers of drop-off: the Baumel paper shows the pattern but not the causes. Commonly cited causes (low perceived value after first use, notification fatigue, effort of logging, privacy worry) are practitioner knowledge, UNVERIFIED in this pass.

### 3.4 Gamification and streaks
- Meta-regression of depression apps: apps with and without gamification were equally effective; gamification had no significant effect on adherence (beta=-1.93, P=.40). https://mental.jmir.org/2021/11/e32199
- A 2019 systematic review found little research on gamification for mental health and that current practice often fails to reflect positive-reinforcement principles. https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6617915/
- Evidence that streaks cause guilt or anxiety in mental-health apps was NOT found (UNVERIFIED either way). It is a plausible harm and a design risk: a broken streak for a depressed student is a negative signal. Requirements REQ-018/019/021 (streaks, badges, leaderboards, social comparison) should be treated as unproven, with leaderboards dropped.

### 3.5 Ethics of AI companions
- RAND/Psychiatric Services (Aug 2025): ChatGPT, Claude and Gemini handled very-high-risk and very-low-risk suicide questions consistently but were inconsistent on intermediate-risk ones; single-turn only. https://www.rand.org/pubs/external_publications/EP71040.html ; https://www.psypost.org/ai-chatbots-give-inconsistent-responses-to-suicide-related-questions-study-finds/
- Common Sense Media (advocacy org, its own rubric): social AI companions rated "unacceptable risk" for under-18s; 3 in 4 US teens have used AI companions. https://www.commonsensemedia.org/research/why-teens-use-ai-companions
- APA advisory: AI companions too risky for minors (as summarised by search; wording not confirmed). https://www.apa.org/news/press/releases/2025/11/ai-wellness-apps-mental-health
- Illinois WOPR Act (Aug 2025) prohibits AI providing therapy or therapeutic decision-making, fines up to USD 10,000 per violation. Not applicable in India, but shows the regulatory direction. https://idfpr.illinois.gov/content/soi/idfpr/en/news/2025/gov-pritzker-signs-state-leg-prohibiting-ai-therapy-in-il.html
- Design principles drawn from the above (proposals): disclose that it is AI every session; no diagnosing, no medication advice, no role-play as a person or therapist; no engagement-maximising persuasion; deterministic crisis path that does not depend on the LLM; log and review safety-relevant chats under a stated retention policy; avoid under-18 AI-chat use until parental-consent flow exists.

---

## 4. Personas (evidence-informed; these are hypotheses to validate with interviews)

### P1. Ananya, first-year hostel student (18)
- Context: leaves home, new language/food/peer group, first marks. Evidence: first-year students show high prevalence of common disorders internationally (WHO WMH-ICS, above); 34% of NTF respondents felt like outsiders on campus.
- Jobs to be done: know if what I feel is normal; get a low-effort way to talk to someone; not be reported to parents.
- Pains: homesickness, sleep, ragging fear, academic shock, nowhere private to call.
- Trust: privacy that is credible (who sees what, in plain Hindi/English), a human reachable fast, no judgement.
- Leave: forced logging, push notifications from the college, any sign that the hostel warden can see her data.

### P2. Rohit, final-year placement-stress student (21-22)
- Context: placements, CGPA pressure, family expectations; exam-failure-linked deaths are about 14% of NCRB 2024 student suicides.
- JTBD: manage acute stress before interviews/results, sleep, keep a record to show a counsellor, get career counselling (SC guideline 12).
- Pains: comparison, fear that "mental health history" harms placement, little time.
- Trust: assurance the institution/placement cell cannot see individual data; quick (under 5 min) sessions.
- Leave: generic breathing content, leaderboards, feeling surveilled.

### P3. Meera, the student who will never talk to a counsellor
- Context: stigma, fear of being labelled, distrust of the administration (only 56% trust, NTF). Prefers anonymous text, may self-medicate with content.
- JTBD: private self-check, a next step she controls, a path to a human only on her terms.
- Pains: being "caught" by a risk flag; being pushed to a person.
- Trust: transparent rules on when confidentiality is broken (imminent risk only), anonymous or pseudonymous mode, easy data deletion.
- Leave: surprise escalation, parent contact, dishonest "100% anonymous" claims. Design tension: for this persona the crisis protocol must be disclosed upfront.

### P4. Dr. Sharma, campus counsellor, caseload far above ratio
- Context: UGC draft suggests 1:500; real ratios reported far higher at some IITs (UNVERIFIED). One counsellor, many roles (the NTF warns about faculty being called counsellors).
- JTBD: see who needs me first; document quickly; follow up three times after a crisis; produce the annual report without spreadsheets.
- Pains: no triage, paper notes, late alerts, liability if a student she did not see dies.
- Trust: alerts she can act on and acknowledge, false-alarm rate she can live with, notes she controls, no data sold or shared with management.
- Leave: alert flood, AI-written notes she must rewrite, any feature that makes her accountable without giving her control.

### P5. Wellness-cell admin / dean of students
- Context: now personally exposed to SC directions (policy, annual report, anonymised records, referral protocol, training twice a year, police reporting of suicides).
- JTBD: show compliance, see aggregate trends (no individual identities), allocate counsellor time, justify budget.
- Pains: audit exposure, vendor risk (DPDP penalties), reputational risk from a data breach.
- Trust: DPDP-ready data processing agreement, clear role-based access, exportable anonymised reports, uptime and a named safety process.
- Leave: any individual-level leak to management, claims they cannot defend in an audit, vendor lock-in.

---

## 5. Proposed success metrics (all targets are PROPOSALS, not facts)

Baseline reference: median 30-day retention for open-market mental-health apps is 3.3% (Baumel 2019, above). Institution-embedded retention is unknown; measure it in a pilot before committing to numbers.

| Role | Metric | Definition | Proposed target |
|---|---|---|---|
| North star | Closed-loop rate | Of students whose check-in is moderate or above (PHQ-9 or GAD-7 of 10 or more) or who triggered a risk flag, % with a documented counsellor contact or accepted self-help plan within 72 h | 60% at pilot end |
| Leading | Weekly active check-ins | % of onboarded students with at least one completed check-in per week | 20-30% of onboarded (vs about 4% daily active market median) |
| Leading | 30-day retention | % of onboarded students active in days 25-35 | 10-15% (3x market median), pilot to confirm |
| Leading | Time-to-first-value | Minutes from signup to first completed screen plus a visible next step and helpline | Median under 3 min |
| Leading | Assessment completion | Completed PHQ-9/GAD-7 / started | At least 80% |
| Provider | Crisis alert time-to-acknowledge | Alert created to counsellor acknowledgement (in hours) | Median under 15 min, p95 under 60 min in working hours; out-of-hours alerts show Tele-MANAS/112 to the student automatically |
| Provider | Counsellor hours saved | Time-motion study of documentation and triage per week versus baseline | 20-30% (the requirements doc's 50% has no evidence) |
| Institution | Report generation time | Time to produce the SC-style anonymised annual report | Under 1 hour, one click |
| Guardrail | False-negative crisis rate | On a curated, clinician-reviewed test set (English, Hindi, Hinglish): % explicit self-harm statements NOT flagged | 0 missed on explicit statements; at least 95% recall on implicit/ambiguous set, reviewed monthly |
| Guardrail | False-positive load | Alerts per counsellor per week that were judged non-risk | Track; tune so counsellors act on over 70% |
| Guardrail | Alert follow-up completeness | % of crisis alerts with documented follow-up | 100% |
| Guardrail | Complaint and harm rate | Student/counsellor complaints about AI replies, privacy or wrongful escalation per 1,000 active users | Under 1 per 1,000; every serious one reviewed within 24 h |
| Guardrail | Privacy incidents | Unauthorised access, breach | 0; breach runbook tested before launch |
| Guardrail | Data-rights SLA | Deletion/export request fulfilment | Within 30 days (proposal; DPDP Rules timing to confirm) |
| Guardrail | Streak-break behaviour | Drop in check-ins or mood scores after a missed day | Monitor; remove streaks if negative signal |
| Replace | Requirements doc targets "70% DAU", "80% early detection", "25% retention gain", "40% fewer emergencies" | No evidence base | Retire from public documents |

---

## 6. Compliance and trust requirements

### 6.1 DPDP Act 2023 and DPDP Rules 2025
- Rules notified mid-November 2025 (13 or 14 Nov; sources differ). Phased: some rules immediate (1, 2, 17-21), consent managers (Rule 4) later, Rules 3 and 5-16 and 22-23 after 18 months, roughly 12-13 May 2027. https://www.scconline.com/blog/post/2025/12/26/digital-personal-data-protection-rules-2025-key-highlights/ ; https://www.legal500.com/firms/237811-saga-legal/c-india/news-and-developments/the-privacy-timer-starts-now-analysing-the-dpdp-rules-and-its-18-month-countdown . One law-firm table shows verifiable parental consent as effective immediately; this conflicts with the SCC Online reading. Treat as UNVERIFIED and design to the stricter reading.
- Children (under 18): Rule 10 requires verifiable parental/guardian consent with identity and age verification before processing; Rule 12 gives narrow exemptions. Some sources say healthcare establishments and educational institutions are exempt from parental consent; SCC Online does not name them. https://www.tribuneindia.com/news/business/govt-notifies-digital-personal-data-protection-rules-rollout-in-phases-specified-obligations-for-data-fiduciaries ; UNVERIFIED. The DPDP Act s.9 also bars tracking, behavioural monitoring and targeted advertising directed at children (from the statute as I know it, not re-checked here; UNVERIFIED).
- Practical impact: many first-year students are 17. Build an age gate, a parental-consent path, and a policy decision on whether under-18s may use the AI chat or only the counsellor channel.
- Rule 6 security safeguards (encryption, access control, logging, backups); Rule 7 breach notification to individuals and the Board; Rule 8 deletion when purpose ends (48 h notice, one-year log retention); Rule 13 (significant data fiduciaries: annual DPIA, audit, local storage of data) applies only if designated, UNVERIFIED whether a student mental-health platform would be. Source: scconline link above.
- Product impact: consent screen separate for each purpose (screening, AI chat, sharing with counsellor, institutional analytics); withdrawal and deletion; no plaintext PHI (an existing Critical issue in docs/STATUS.md).

### 6.2 Mental Healthcare Act 2017
- Section 23: right to confidentiality for mental-health information (and s.24 on restriction of release; s.25 access to records). https://qps.nhsrcindia.org/sites/default/files/2022-01/THE%20MENTAL%20HEALTHCARE%20ACT%2C%202017.pdf ; summary https://pmc.ncbi.nlm.nih.gov/articles/PMC7736728. Section 23 exceptions and how they apply to institutions: UNVERIFIED, take legal advice.
- Section 115: a person who attempts suicide is presumed to be under severe stress and is not punished. https://blog.ipleaders.in/all-need-know-about-mental-healthcare-act/ . Implication: crisis messaging must never imply punishment or police action for disclosing ideation.
- The Telepsychiatry article notes the tension between mandatory diagnosis on a prescription and s.23; suggested workaround is an ICD/DSM code. https://pmc.ncbi.nlm.nih.gov/articles/PMC7736728
- Product impact: institutional users (deans) must not see individual records; counsellor access limited to assigned students; every access logged.

### 6.3 Telemedicine Practice Guidelines 2020 (MoHFW/NMC) and prescribing
- Applies to registered medical practitioners (RMPs) enrolled in the State/Indian Medical Register. https://www.nrces.in/standards/telemedicine-practice-guidelines ; https://khaitanco.com/thought-leaderships/Telemedicine-Practice-Guidelines
- Prescribing lists: first consult List O and List A; follow-up also List B; List C (including Schedule X/controlled drugs) can never be prescribed after teleconsultation. https://pmc.ncbi.nlm.nih.gov/articles/PMC7736728 (Telepsychiatry Operational Guidelines 2020 by IPS, TSI, NIMHANS, which add that benzodiazepines such as diazepam and lorazepam sit in List C).
- **AI cannot counsel or prescribe.** Multiple secondary sources quote the guideline (reproduced as clause 5.4): technology platforms based on AI/ML are not allowed to counsel patients or prescribe medicines; they may only support the RMP, who makes the final decision. https://www.lexology.com/library/detail.aspx?g=9055584c-829c-4742-aa80-3353bdbb5d14 ; https://psalegal.com/telemedicine-guidelines-2020-faq/ ; https://deemagclinic.com/2020/03/25/telemedicine-practice-guidelines/ . I could not open the official PDF (https://covid19dashboard.mohfw.gov.in/pdf/Telemedicine.pdf timed out), so confirm clause text before legal reliance. UNVERIFIED against primary.
- Answer to "is prescribing by an app allowed, and by whom": an app may host a prescription only if written by a verified RMP (a psychiatrist or doctor), within the list limits, after adequate information and, for first-time psychotropics, ideally video consult. It cannot be generated by the AI, and campus counsellors who are psychologists or social workers cannot prescribe. Prescribing without adequate diagnosis can be professional misconduct. Source: Lexology/PSA above.
- Product impact: the prescription module must (a) gate on RMP registration number verification, (b) block List C drugs for tele-prescription, (c) show a hard separation between AI drafts (notes) and clinician-signed prescriptions, (d) store consent and records as in-person standards. Digital prescription signature requirements: https://pmc.ncbi.nlm.nih.gov/articles/PMC7736728 .

### 6.4 ICMR / NHA digital-health considerations
- ICMR Ethical Guidelines for AI in Biomedical Research and Healthcare (2023): ten patient-centric principles including autonomy (informed consent), data privacy, accountability and liability, risk minimisation, safety, accessibility, non-discrimination, validity and trustworthiness. https://www.icmr.gov.in/ethical-guidelines-for-application-of-artificial-intelligence-in-biomedical-research-and-healthcare ; PDF https://www.icmr.gov.in/icmrobject/custom_data/pdf/Ethical-guidelines/Ethical_Guidelines_AI_Healthcare_2023.pdf (principles from search summary; PDF not read).
- NHA/ABDM data-management policy and consent-manager obligations: not verified. UNVERIFIED. If we later integrate with ABDM (ABHA IDs), a separate review is needed.
- CDSCO / Medical Device Rules 2017 classification of screening/diagnostic software: not checked here. UNVERIFIED. README already says "not a medical device"; keep marketing consistent with that.
- Any research use of student data (for example evaluating effectiveness) needs ethics-committee review under ICMR guidance. UNVERIFIED specifics.

### 6.5 Accessibility and language
- WCAG 2.2 AA is the proposed standard. No Indian legal mandate for private HEI web apps was verified here. The Supreme Court cited the UGC Accessibility Guidelines and Standards for HEIs 2022 and the NTF recommends mandatory accessibility audits (https://www.scobserver.in/supreme-court-observer-law-reports-scolr/amit-kumar-v-union-of-india-guidelines-on-student-suicide-prevention/). RPwD Act 2016 and GIGW applicability: UNVERIFIED.
- Mental-health-specific accessibility: low-motion option on breathing exercises, captions for yoga video, high-contrast, screen-reader labels for PHQ-9 radio groups, no time-limited questions, 44px touch targets.
- Language: Tele-MANAS operates in 20 languages (https://www.deccanherald.com/amp/story/india%2Fnational-mental-health-helpline-got-nearly-2-calls-per-minute-govt-tells-parliament-3826372, via search snippet), signalling that language access matters for mental-health care. No peer-reviewed evidence on Hinglish chatbot performance was found, UNVERIFIED. Proposal: Hindi and English UI, Hinglish tolerance in crisis-phrase detection, validated Hindi PHQ-9/GAD-7 (validated Hindi translations exist; I did not verify citations). Test crisis detection explicitly on Hinglish/Hindi phrases before claiming support.

---

## 7. What to build next (MoSCoW, 2-3 people, about 3 months)

Capacity assumption: about 500-600 engineer-days total. Order matters: Must items gate any pilot.

### Must
1. **Close Critical/High issues in docs/STATUS.md**: authenticate all API/socket endpoints, fix role escalation (no self-assigned "provider"), restore CSP, SECRET_KEY handling, encrypt PHI at rest, fix broken pages. Reason: a pilot with unauthenticated mood/chat endpoints would breach confidentiality (MHCA s.23, DPDP Rule 6).
2. **Server-side PHQ-9/GAD-7 scoring** with official bands, item-9 handling, and repeat-response tracking (item 9 alone misses many; see 3.2). Show helpline and next step on every moderate+ result.
3. **Crisis pipeline**: deterministic word-boundary and multilingual (English/Hindi/Hinglish) detection plus the LLM as a secondary signal; creates an alert to the assigned counsellor (and a fallback pool), with states (new, acknowledged, contacted, closed), an audit log, time-to-acknowledge timer, and out-of-hours display of Tele-MANAS 14416 and 112. Test set and recall measurement before launch.
4. **Consent, age gate and privacy by design**: DPDP-style notice and per-purpose consent, under-18 handling, deletion/export, role-based access (counsellor sees assigned students only, admin sees aggregates only, small-cell suppression), full access logging, breach runbook.
5. **AI chat guardrails**: persistent "I'm an AI, not a counsellor" notice, no diagnosis/medication advice, crisis handoff, safe fallback when Gemini is down, no streak/engagement pressure in the chat; log review policy.
6. **Remove unsubstantiated claims** (placeholder stats/testimonials; see section 8).
7. **Prescription module restricted** to verified RMP accounts, list-aware (no List C), or hide it for the pilot.

### Should
8. **Counsellor triage view**: risk-sorted caseload, overdue follow-ups, three-session post-crisis tracker (UGC draft), appointment accept/reject with reminders.
9. **Anonymised institutional report export** (counts of screenings, referrals, wait times, training logs) mapped to SC guideline 10 and the Jan-2026 annual-report duty. Likely the strongest sales feature.
10. **Hindi UI and Hinglish crisis phrases**; plain-language privacy page.
11. **Onboarding to first value in under 3 minutes**, mood check-in first, assessments optional until the student chooses.
12. **WCAG 2.2 AA pass** on the core student flows (sign-up, check-in, assessment, chat, appointments) with an external audit later.
13. **Outcome instrumentation**: PHQ-9/GAD-7 trend per student visible to the counsellor (MBC), plus pilot metrics in section 5.

### Could
14. Telehealth hardening (TURN, session consent, no recording by default) if a campus will actually use video.
15. AI note drafting for counsellors, only on-device or with a data-processing agreement; counsellor edits and signs. Check Gemini terms for health data (UNVERIFIED).
16. Journal sentiment, goals, yoga/music (already built; keep, do not expand).
17. Peer-support circles only with moderation, since peer-support apps showed the best 30-day retention (8.9%) in Baumel, but moderation is costly.

### Won't (this quarter)
Wearables remote monitoring, predictive suicide-risk ML, leaderboards and social comparison, streak pressure, "AI therapist" positioning, any AI prescribing/counselling, parent dashboards, claims of regulatory approval, ABDM integration.

Justification summary: the Must list fixes the product's two existential risks (data breach, missed crisis) and the Should list builds the loop that institutions are now legally pushed to run (policy, referral, training, annual report). Engagement content is intentionally de-prioritised because content-only retention is poor.

---

## 8. Claims the product must NOT make

1. "Diagnoses", "treats" or "cures"; "clinically proven"/"clinically validated" for the app itself (no trial of this product exists).
2. "Prevents suicide", "predicts suicide", "detects every crisis", "24x7 monitoring" unless a staffed human service exists. Item 9 and chatbots both miss cases (section 3).
3. "AI therapist", "AI counsellor", "replaces your counsellor"; any statement that AI prescribes or advises on medicines (Telemedicine Practice Guidelines, secondary sources).
4. "100% confidential" or "completely anonymous". There are crisis-escalation exceptions, counsellor access, and logs. Say exactly who can see what.
5. "DPDP compliant", "Supreme Court / UGC compliant", "NABH/ISO/HIPAA certified" without evidence or certification. Use "supports your compliance workflow" if true.
6. "Endorsed/approved by MoHFW, UGC, NIMHANS, Tele-MANAS" without a signed agreement.
7. Outcomes from the requirements doc: "70% daily active", "80% early detection", "25% better retention", "40% fewer emergencies", "50% less documentation time".
8. Placeholder statistics and testimonials currently in index.html (docs/STATUS.md lists this as an open item). Fake testimonials are also a trust and legal risk.
9. "Hindi/Hinglish supported" before crisis detection is tested in those languages.
10. "Safe for under-18s" before the parental-consent and AI-companion policy exists.
11. "Proven to reduce depression" based on chatbot literature; cite effect sizes honestly (small, short-lived) if at all.
12. Medical-device language ("remote patient monitoring", "clinical decision support") unless CDSCO position has been checked.

---

## 9. Open items to verify next (not done in this pass)
- Official TPG PDF clause numbers (AI restriction, record retention).
- NMHS summary PDF numbers (403) and NMHS age-group tables.
- NCRB ADSI 2024 primary tables (student definition, age split).
- Whether UGC finalised the mental-health guidelines and the MANASSETU portal after Jan 2026; whether the NTF published its final report.
- DPDP: exact effective date of Rules 10-12 and any exemption for educational/healthcare institutions in the gazette text.
- Competitor status 2025-26 for Youper, Amaha, YourDOST (pricing, users, trials).
- India-specific primary studies on student help-seeking and digital-tool acceptance.
