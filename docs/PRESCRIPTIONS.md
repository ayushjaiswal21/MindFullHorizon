# Prescriptions: operator guide

Audience: the person who runs MindFull Horizon for an institution (the service operator) and the institution's administrators. Design contract: [CLINICAL_DESIGN.md](CLINICAL_DESIGN.md). Background and sources: [research/prescribing-inventory.md](research/prescribing-inventory.md).

**Status, stated plainly: this feature has not had legal or pharmacist review.** Section 15 of the design lists the open questions (Telemedicine Practice Guidelines, digital prescription validity, pharmacy licensing, record retention, DPDP). Treat everything here as a pilot for a controlled setting until that review is done. The software refuses what it can refuse; it does not make a college dispensary lawful.

## 1. Who does what

| Person | Account | Can do |
|--------|---------|--------|
| Student (patient) | self signup, 18+ | see own prescriptions from the moment a doctor issues them, allow or withdraw e-prescriptions, send a prescription to the pharmacy desk, print |
| Counsellor | `provider`, type counsellor, `PROVIDER_INVITE_CODE` | see the medicine lines (name, dose, frequency, duration, status) of assigned patients, read only. Never prescribes. Never sees diagnosis or allergies. |
| Doctor | `provider`, type doctor, `DOCTOR_INVITE_CODE` | prescribes only after an administrator has verified the registration, and only for assigned patients after a recorded consult |
| Administrator | created with `flask create-admin` only | verifies doctors, keeps the medicine catalogue, sees stock and reports, never sees patient lists |
| Pharmacy desk | administrator with the desk flag (`flask set-pharmacy-desk`) | receives stock, dispenses, reverses a dispense within 24 hours |

There is no separate doctor dashboard: a doctor uses the provider dashboard, which shows a Prescribing section only to doctors.

## 2. Setting up an institution (first time)

1. Create the first administrator on the server: `flask create-admin --email E --name N --institution I --pharmacy-desk`. There is no web form for this on purpose.
2. Set `DOCTOR_INVITE_CODE` (and `PROVIDER_INVITE_CODE` for counsellors). The two codes must differ. An unset code keeps that signup closed.
3. Create a second administrator if you want the four-eyes check on the medicine list (see 5). With one administrator set `CATALOGUE_FOUR_EYES=0`; the catalogue screen then shows a standing warning.
4. Add medicines to the catalogue (by hand or CSV). MindFull Horizon ships with **no** medicine data. An empty catalogue blocks all prescribing, which is the safe state.
5. Receive stock at the desk, set reorder levels.
6. Give doctors the invite code. They sign up and wait for verification.

## 3. Verifying a doctor

The app cannot query the National Medical Commission register: no official public API exists. An administrator checks by hand and records the evidence.

1. Open Administrator, Verification, choose the doctor.
2. Search the Indian Medical Register by registration number (link on the screen). Confirm that name, year of registration and State Medical Council match, that the doctor is not on the removed-doctors list, that the registration is for modern medicine, and that the person works at this institution.
3. Tick every checklist item and write a one-line evidence note (10 to 500 characters), then Verify.

A verified badge means an administrator of your institution checked the entry on that date. It does not mean the NMC confirmed it to this service.

- Verification lasts `PRESCRIBER_REVIEW_DAYS` (default 365). After that prescribing stops until it is checked again. Administrators are reminded 30 days before.
- Changing the registration number, council or year sends the doctor back to pending.
- Suspend at once if a doctor leaves, is struck off, or doubts arise. It takes effect on the doctor's next request. Prescriptions already issued stay valid for the patient but cannot be dispensed while the prescriber is suspended.

## 4. Issuing a prescription (what the software enforces)

A doctor can issue only when all of these hold at the moment of issue, checked on the server:

- the doctor is verified and the review date has not lapsed;
- the patient is assigned to the doctor (booked an appointment, or added by the operator), same institution;
- the patient has allowed e-prescriptions (tick box when booking a doctor, or the button on the Prescriptions page);
- the doctor pressed Start consult on a video or in-person appointment, within `RX_CONSULT_WINDOW_HOURS` (default 24). The software records the doctor's own action. It is not proof that a call took place;
- every medicine is active, confirmed by a second administrator, not Schedule H1, X or NDPS, not List C, and allowed by the consult type (first consult: lists O and A; follow-up after an in-person consult for the same condition, or in person: also B);
- at most `RX_MAX_ITEMS` medicines (default 6); each at most 14 days (first consult) or 30 days (follow-up), set as product policy for a student-health setting, not taken from a regulation. The clinical lead must confirm these numbers.

A prescription is immutable once issued. To change it the doctor cancels it or writes a corrected one (the old one is cancelled when the new one is issued). It expires at the end of the chosen day (up to `RX_EXPIRY_DAYS`, default 30, maximum 90).

Warnings are shown for the same medicine twice, the same class twice, a medicine the patient logs themselves, and a text match against allergies or current medicines. The doctor must acknowledge each one.

## 5. The medicine catalogue and the four-eyes check

- Each medicine carries its Telemedicine Practice Guidelines list (O, A, B or C) and its schedule. If unsure, choose List C: the medicine is blocked.
- Changing the list, schedule or controlled flag clears the confirmation. A **different** administrator must confirm before anyone can prescribe it. A CSV import can never confirm anything.
- Deactivate instead of deleting. Issued prescriptions keep their text.

## 6. Dispensing and stock

- The desk finds a prescription by number (with a check character, so typing errors are caught) or from the queue of prescriptions patients chose to send. There is deliberately no list of all prescriptions.
- Two steps: Prepare shows which batches will be used (earliest expiry first); Confirm records it. Confirm needs the box "I have checked the patient's identity and the prescription number" and the pharmacist's name and registration number.
- Stock is not held when a prescription is issued. The doctor sees In stock, Low stock or Out of stock as a guide only. If stock runs out the desk dispenses part and the prescription stays partly collected until it expires.
- Expired stock is never dispensed. It stays on the books until the desk writes it off.
- Every change of stock is a ledger line. Nothing is edited or deleted. A reversal within 24 hours undoes a desk mistake. A medicine a patient brings back is **not** returned to the shelf.
- Controlled medicines (H1, X, NDPS) are not stocked and not prescribed in this version.
- After restoring a database backup, count the shelf and reconcile before dispensing: a restore can lose recent issues and dispensing lines.

## 7. What the system does not do

- It does not check drug interactions, doses, contraindications, pregnancy or kidney function, and says so on screen. It finds the same medicine or class only.
- It does not prescribe by AI. The chat companion cannot prescribe, change or comment on a prescription.
- It does not query the NMC register, and it does not digitally sign prescriptions. The printout states it has no handwritten or digital signature and points to the public status page `/rx/<number>`. Whether an outside pharmacy accepts it is a legal question.
- It does not keep patient age or sex on the prescription.
- It does not run any pharmacy licence, register or reporting duty.
- It does not number prescriptions in sequence (numbers are random with a check character).

## 8. Patient data and deletion (needs legal review)

- The institution (data fiduciary) decides why prescription data is used. The service operator (processor) runs the software for it.
- **Deleting a student's account deletes their prescriptions** (the patient side cascades). Stock history survives because the ledger keeps its own copy of the number. Record-retention duties for prescriptions (period, who must keep them) are unresolved and need legal review before real use. Until then, tell students that deleting an account removes their prescriptions.
- A doctor who has issued prescriptions cannot be deleted; the account is deactivated.
- Counsellors can see medicine lines of assigned patients and every such view is written to the audit log (counts only, never text). Patients are told this on their Prescriptions page.
- Audit rows, ledger rows and prescriptions are clinical records. Backups include them, and maintenance scripts must never truncate them.

## 9. Demo data

`python scripts/seed_demo.py` creates a demo patient, counsellor, doctor (verified, marked `DEMO ONLY, not a real registration`), two administrators (one is the desk), about eight fictional medicines named "... (DEMO)", a few batches (current, near expiry, expired), a started video consult, the patient's consent and one sample prescription. Passwords are random and printed once. Re-running adds nothing.

It refuses to run when `FLASK_ENV=production`. `--force` overrides that and is for a throwaway database only: never run it against real data. Demo medicines are marked and are refused for prescribing in production unless `ALLOW_DEMO_DATA=1`. Migrations insert no clinical rows.

## 10. Settings

`ENABLE_PRESCRIPTIONS` (default on; set to 0 to hide every prescribing, patient prescription, desk and inventory page), `DOCTOR_INVITE_CODE`, `PRESCRIBER_REVIEW_DAYS`, `RX_EXPIRY_DAYS`, `RX_MAX_ITEMS`, `RX_MAX_DAYS_FIRST`, `RX_MAX_DAYS_FOLLOWUP`, `RX_CONSULT_WINDOW_HOURS`, `ERX_CONSENT_VERSION`, `CATALOGUE_FOUR_EYES`, `INVENTORY_MIN_SHELF_DAYS`, `INVENTORY_NEAR_EXPIRY_DAYS`, `ALLOW_DEMO_DATA`. Meanings are in design section 8.

## 11. Review items before real use

1. Legal reading of the Telemedicine Practice Guidelines 2020 (first consult, follow-up, lists, consent, identification).
2. Whether a manual register check by an administrator is acceptable, and the re-check period.
3. Whether an unsigned electronic prescription can be dispensed by an outside pharmacy; need for a digital signature.
4. Pharmacy licensing and supervision for an in-house desk; whether the pharmacist name and registration captured at the desk is the right record; whether returned medicines may be restocked (this version says no).
5. Retention of prescriptions against account deletion (section 8) and the DPDP position on health data, with the institution as data fiduciary and the operator as processor.
6. Whether the duplicate-therapy warnings count as decision-support software needing classification.
7. Whether a doctor may prescribe to a student of the institution where they work, and how a doctor and a counsellor may share information about one student.
8. A pharmacist's review of the stock rules, the 24-hour reversal and the expiry margin.
9. Clinical lead sign-off on the item limits and day limits in section 4.
10. The patient e-prescription consent is a required tick box when booking a doctor. Whether tying consent to booking is acceptable under DPDP (consent should be specific and not bundled) needs a legal view.
