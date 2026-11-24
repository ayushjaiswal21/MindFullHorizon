# Prescribing and inventory: regulatory inventory

Research notes behind [../CLINICAL_DESIGN.md](../CLINICAL_DESIGN.md). Searched and fetched on 2026-11-24. This is engineering research, not legal advice. Every claim is marked **Verified (primary)**, **Secondary** (law firm, journal, news) or **UNVERIFIED**. The official Telemedicine Practice Guidelines PDF could not be opened in this session (https://covid19dashboard.mohfw.gov.in/pdf/Telemedicine.pdf returned a gateway timeout; https://nmcn.in/oldsite/pdf/Telemedicine%20Practice%20Guidelines.pdf returned 404), so nothing below about the TPG is verified against the primary text.

## 1. Telemedicine Practice Guidelines 2020 (TPG)

| Point | Finding | Status | Source (fetched 2026-11-24) |
|-------|---------|--------|------|
| Who may prescribe | Registered medical practitioners (RMPs) only. AI/ML platforms may not counsel or prescribe (clause 5.4 per secondary sources). | Secondary | https://www.lexology.com/library/detail.aspx?g=9055584c-829c-4742-aa80-3353bdbb5d14 ; https://khaitanco.com/thought-leaderships/Telemedicine-Practice-Guidelines |
| First consult | Patient consults the RMP for the first time, OR more than 6 months since the previous consultation, OR earlier consultation was for a different condition. | Secondary | search-result quotation of the TPG definitions; same Khaitan and PSA Legal pages |
| Follow-up consult | Same RMP, within 6 months of the previous **in-person** consultation, same health condition. | Secondary | same |
| List O | Medicines that can be prescribed in any tele-consult (over-the-counter type: analgesics, antacids, vitamins). Contains no psychotropics. | Secondary | https://pmc.ncbi.nlm.nih.gov/articles/PMC7736728 |
| List A | Can be prescribed at the first consult **if it is a video consult**, and re-prescribed for refills at follow-up. | Secondary | PMC7736728 |
| List B | Can be prescribed only at a follow-up consult (any mode), in addition to what was prescribed in person for the same condition. | Secondary | PMC7736728 |
| List C | Cannot be prescribed through teleconsultation. Schedule X drugs and drugs under the NDPS Act 1985. Examples named in the psychiatry guideline: zolpidem, diazepam, lorazepam, methadone, buprenorphine, ketamine, morphine, tramadol, codeine; methylphenidate is not allowed by tele-consult at all. | Secondary | PMC7736728 |
| Psychotropic membership conflicts | The Telepsychiatry Operational Guidelines article (PMC7736728) puts clonazepam and clobazam in List A "after an MCI amendment"; another secondary source says benzodiazepines are barred "except clonazepam"; a third differs on the exceptions. | Secondary, **conflicting** | PMC7736728 and search summaries |
| Lists change | The lists are revised by notification. | Secondary | PMC7736728 |
| Prescription content | Digital prescriptions: generic name in capitals plus a digital signature; signature accompanied by name, designation, affiliation; a diagnosis (provisional or final, an ICD code is suggested for confidentiality). | Secondary (psychiatry article, not the TPG itself) | PMC7736728 |
| Patient identification | Required at the first consult, not at follow-up. | Secondary | search summary |
| Follow-up refill cap | An official FAQ addresses a cap on refills for chronic conditions; the text was not retrieved. | UNVERIFIED | https://aiims.edu/images/pdf/notice/FAQ_Telemedicine.pdf (not opened) |

Design consequence: list membership is DATA entered and verified by a person per medicine (never hard-coded from this table), unknown membership defaults to "C" (blocked), and the app treats clonazepam and clobazam like any other medicine: they can be in List A only if the pharmacist and legal reviewer say so (they are also Schedule H1 or NDPS-adjacent in some classifications: UNVERIFIED).

## 2. Verifying an Indian doctor

- The official lookup is the Indian Medical Register search on the NMC website: https://www.nmc.org.in/information-desk/indian-medical-register/ . Fields: name, registration number, year of registration, State Medical Council. Match name, year and council, not one field. (Source: https://righttoinformation.wiki/verify-doctor-registration-national-medical-register-india , Secondary.)
- The NMC publishes a separate list of removed or blacklisted doctors: https://www.nmc.org.in/information-desk/indian-medical-register/black-list-doctors/ (same Secondary source).
- Caveats from the same source: older doctors may be only in a State register not yet mirrored nationally; disciplinary orders can lag by months; the register covers modern medicine only (AYUSH has separate councils); registered is not the same as clean record.
- **No official public NMC API was found.** Searches only returned commercial wrappers (Decentro, Surepass, Meon, Apify actors) whose accuracy, terms and legality of scraping are UNVERIFIED: https://surepass.io/nmc-verification-api/ , https://decentro.tech/api-hub/nmc-verification-api , https://apify.com/whoareyouanas/nmc-doctor-lookup . The design therefore uses a manual check by an admin with a recorded evidence note, and treats a paid verification API as a later option the owner must evaluate.

## 3. Schedules and stock records

- Schedule H1 (G.S.R. 588(E), 30 Aug 2013, antibiotics, anti-TB and certain habit-forming drugs): sale only on an RMP prescription; supply recorded in a separate register at the time of supply with prescriber name and address, patient name, drug and quantity; records kept 3 years and open to inspection. Secondary: https://www.nhsrcindia.org/sites/default/files/2021-07/Attachment%20A%2C%20Schedule%20H1%20register%20and%20NDPS%20Forms.pdf and indiankanoon pages found by search. One source (ntep.in) says the opposite; treated as an error, UNVERIFIED either way.
- Draft G.S.R. 791(E), 8 Sep 2026, would add CCTV on prescription-drug sales with 3 months of footage (draft, scope unclear): UNVERIFIED, from https://www.gktoday.in/health-ministry-proposes-amendments-to-drugs-rules-1945-for-schedule-h-h1-and-x-drugs/ and similar. Relevant only if the owner runs a real pharmacy counter.
- Consequence: v1 stocks and prescribes only medicines with schedule `none` or `H` and `is_controlled = false`. H1, X and NDPS medicines are blocked from prescribing, and receiving them into stock is rejected, so no register is needed in v1.
- Pharmacy Practice Regulations 2015 (who may dispense; record keeping): nothing retrieved. UNVERIFIED. Treated as: a registered pharmacist must supervise dispensing, so the dispense screen captures the pharmacist's name and registration number.

## 4. Record retention and data protection

- Indian Medical Council (Professional Conduct, Etiquette and Ethics) Regulations 2002, reg. 1.3.1: records of indoor patients kept 3 years; reg. 1.3.2: records produced within 72 hours on request; reg. 1.3.4: computerise records. A 2023 NMC regulation was notified and then kept in abeyance (secondary, unverified). https://www.nmc.org.in/rules-regulations/code-of-medical-ethics-regulations-2002/ ; commentary at https://lawbhoomi.com/maintenance-of-medical-records-by-hospitals-in-india/ . Outpatient prescription retention period: UNVERIFIED. Design default: keep issued prescriptions and the dispensing ledger at least 3 years, never purge them in code, and make the owner confirm the number.
- DPDP Rules 2025 were notified in November 2025 with phased commencement (12 to 18 months for most duties). Rule 8(3) (per secondary sources) requires keeping personal data, traffic data and processing logs for at least one year, then erasing unless law requires longer. Secondary: https://www.scconline.com/blog/post/2025/12/26/digital-personal-data-protection-rules-2025-key-highlights/ ; https://www.barandbench.com/view-point/meity-notifies-final-digital-personal-data-protection-rules-2025 ; https://www.khaitanco.com/sites/default/files/2025-11/ERGO%20-%20Digital%20Personal%20%20Data%20Protection%20Rules%20-%2015%20November%202025.pdf . Exact commencement dates for each rule: UNVERIFIED. Prescription data is health data; the 18+ only decision (P-05) removes the child-data rules for now.

## 5. Drug interaction checking

- The NLM RxNav drug-drug interaction API was discontinued on 2 January 2024 (NLM FAQ: https://lhncbc.nlm.nih.gov/RxNav/information/FAQs.html , Verified primary). Its underlying sources were a high-priority DDI list for EHRs plus CredibleMeds and DrugBank data.
- India-specific licensed databases (CIMS, MIMS and similar): coverage and licence terms not found, UNVERIFIED. DrugBank has a commercial licence for DDI data: terms not checked, UNVERIFIED.
- Software that gives drug-interaction decision support may attract medical-device rules (CDSCO / Medical Devices Rules 2017): UNVERIFIED, see docs/research/product-market.md section 6.4.
- Consequence: v1 builds a same-medicine and same-class duplicate warning only, and says on screen that it is not an interaction check.
