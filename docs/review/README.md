# Review kit: index and status

This folder holds the packets that human reviewers need before any real student uses MindFull Horizon: a clinician, a lawyer, a college, and (if outcomes will be published) an ethics committee. Engineering prepared the packets. Engineering cannot perform these reviews and nothing here claims that any has happened.

## The rule

**Only a named human reviewer's signed page changes a state to "done".** A state may not be changed to done by an engineer, an AI agent or the owner on a reviewer's behalf, on the strength of a chat message, a verbal "looks fine" or an unsigned file. The evidence in the last column must exist (the signed page, scanned or electronic, with the reviewer's name, registration number, date and the code version). If the code changes in the reviewed area after the sign-off, the state goes back to "not started" for that part.

## Status table

Update this table by hand when a signed page arrives. Keep the signed pages with the packets (or in the owner's records) and note where in the "Evidence location" column.

| Review | Needed from | State | Evidence required to mark done | Evidence location |
|---|---|---|---|---|
| Clinical review: crisis phrases, severity mapping, response wording, escalation, assessment rules | Psychiatrist or clinical psychologist (named, with registration number) | not started | Signed sign-off page (`CLINICIAN_REVIEW_PACKET.md` section 10) with scope, git commit and conditions; the clinician columns of `generated/crisis_phrases.csv`, `crisis_test_cases.csv` and `assessment_bands.csv` filled | |
| Hindi and Hinglish phrase review (native speakers) | Hindi-speaking clinician or reviewer, preferably more than one | not started | Reviewer names and signed note stating rows reviewed in the Hinglish and Devanagari parts of `generated/crisis_phrases.csv` | |
| Crisis tabletop (15 scenarios) | Clinician with counsellors and engineering | not started | Completed table in `CLINICIAN_REVIEW_PACKET.md` section 8 with Observed and Clinician judgement filled, every C rating resolved in the change-request log | |
| Legal review: data protection, health law, IT law, advertising, contracts | Indian counsel (named, with enrolment number) | not started | Signed page (`LEGAL_REVIEW_PACKET.md` section 6), written answers to L1 to L22, marked-up privacy and terms, the draft banners removed only after sign-off | |
| College DPA and pilot MoU | College authorised signatory and counsel | not started | Signed DPA and MoU | |
| Ethics committee approval (if outcome data will be published or shared) | Institutional Ethics Committee of the pilot college | not started | Approval letter with number and date, or the committee's written statement that none is required | |
| Pilot site approval | College (SPOC, responsible clinician, management) | not started | Written confirmation of the site criteria in `PILOT_PLAN.md` section 3, named clinical lead and on-call roster | |
| Security review or penetration test | Independent security reviewer | not started | Report with findings and a written fix or acceptance decision for each | |
| Key rotation | Owner (with engineering evidence) | not started | Dated record of every rotated secret and revocation of the old ones | |
| Backup and restore drill | Engineering with a witness | not started | Dated record of a full restore and its duration | |
| Alert drill (fake crisis on staging, acknowledged by a counsellor) | Counsellor and engineering | not started | Timestamped record of event, notifications, escalation levels and acknowledgement | |
| Counsellor training session | Clinical lead and engineering | not started | Attendance list and the briefing used | |
| Student briefing and consent script | College SPOC and counsel | not started | Approved information sheet and consent text | |
| Helpline posters and numbers re-verified on launch date | College SPOC | not started | Photo or checklist of locations and a dated check of each number against `utils/helplines.py` | |

## Documents in this folder

| File | For | Contents |
|---|---|---|
| [CLINICIAN_REVIEW_PACKET.md](CLINICIAN_REVIEW_PACKET.md) | Psychiatrist or clinical psychologist | Safety flow explained, exact escalation timeline, the wording students see, known limits, a numbered decision questionnaire (D1 to D16), a 15-scenario tabletop test, sign-off page, change-request log |
| [LEGAL_REVIEW_PACKET.md](LEGAL_REVIEW_PACKET.md) | Indian counsel | Facts of the product, processors, flows, 22 numbered questions with the law named and UNVERIFIED flags, a table of what is implemented per ask, operator tasks, sign-off page, known mismatches between our documents and code |
| [PILOT_PLAN.md](PILOT_PLAN.md) | Owner, college, clinical lead | Objectives, site criteria, roles, pre-launch gates, stop rules, alert SOP, metrics (targets, not facts), communication templates, exit plan, risk register, week table, budget template |
| [generated/](generated/) | All reviewers | Files produced from the live code by `scripts/export_review_packet.py`: `crisis_phrases.csv`, `crisis_test_cases.csv`, `safety_flow.md`, `assessment_bands.csv`, `ai_prompt_snapshot.md`, `helplines.csv`, `tabletop_scenarios.csv`, `MANIFEST.md` |

## Keeping the packets in sync with the code

1. Before any review meeting, run from the project root with the project's Python environment:

   `python scripts/export_review_packet.py`

   It needs no network and no Gemini key, and overwrites `docs/review/generated/`. It prints a NOTE for anything it could not export and writes the git commit and a fingerprint of the safety-relevant files into `generated/MANIFEST.md`.
2. Copy the commit and the fingerprints onto the sign-off page. If the working tree has uncommitted changes the manifest says so; the commit alone then does not identify the reviewed code.
3. Re-run it after any change to the detector, thresholds, wording, escalation, prompts or helplines, and re-open the affected review.
4. `tests/test_review_packet.py` checks that the exporter runs, writes non-empty files, is deterministic and never writes a key or secret.
5. The narrative in the three packets was written on 2026-11-24 against the code of that date. When a generated file and a packet disagree, the generated file is right; fix the packet.

## Status wording to use

Say "draft, pending clinical review" and "draft, pending legal review". Never say "clinically validated", "legally approved", "compliant" or "certified" about the product until the matching signed page exists, and even then name its scope.
