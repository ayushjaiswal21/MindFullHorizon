# Follow-ups, score flags and appointment reminders

Three counsellor and doctor features added in November 2026 (migration `0009`). Code: `utils/followups.py` (plans and state machine), `utils/followup_jobs.py` (`followup_due`), `utils/followup_views.py` (read side), `utils/score_flags.py`, `utils/appt_reminders.py`, `routes/provider_followups.py`, `models_followup.py`, templates in `templates/provider_followups/`, `static/js/followups.js`, `static/css/followups.css`.

## 1. Post-crisis follow-up tracker

**Creation.** Acknowledging a `CrisisEvent` (`POST /provider/crisis/<id>/acknowledge`) opens a `FollowUpPlan` automatically, in the same transaction. Automatic was chosen over a button because a missed click would silently leave a crisis with no follow-up; a plan costs nothing if it is later closed early. Only the request that wins the acknowledge compare-and-set creates the plan, and `crisis_event_id` is unique, so replays and races create nothing extra.

**Steps.** N steps, each with an IST calendar `due_date`, counted from the IST date of the acknowledgement.

| Setting | Default | Meaning |
|---|---|---|
| `FOLLOWUP_SESSIONS` | `3` | Number of steps (1 to 10). |
| `FOLLOWUP_DAYS` | `2,7,14` | Days after acknowledgement for each step. A shorter list is padded weekly; an invalid list falls back to the default. |

**Unverified.** The figure "at least three follow-up counselling sessions after a crisis" comes from the UGC draft guidelines circulated in January 2026 (docs/research/product-market.md 1.6). I found no confirmation that the draft was notified in final form. It is therefore configuration, marked as a draft, and the product does not claim compliance with it. The intervals 2, 7 and 14 days are a product choice, not taken from any guideline.

**State machine** (`utils/followups.py`, style of `utils/state.py`). Step: `pending -> done | missed | skipped`, all terminal, one compare-and-set UPDATE each. `done` needs an outcome code: `contacted_in_person`, `contacted_by_phone`, `no_answer`, `patient_declined`, `referred`, `other`. Plan: `open -> completed` automatically when no step is pending, or `open -> closed_early` with a reason code (`patient_declined`, `referred`, `transferred`, `no_longer_needed`, `other`), which marks pending steps `skipped`. A replay of the same change is a quiet success; anything else illegal is HTTP 409 with a generic message.

**No free text.** `followup_plans` and `followup_steps` contain ids, dates, status and codes only (a test asserts no text column). The optional note in the "Mark done" dialog is saved as a `ClinicalNote` (`provider_notes`) and audited as `add_clinical_note`; the step does not link to it.

**Who sees and acts.**

| Who | Sees the plan | Can act |
|---|---|---|
| Provider assigned to the patient (`ProviderPatient`) | Yes: dashboard panel and report timeline | Yes |
| Plan owner (the provider who acknowledged) who is NOT assigned | Yes: dashboard panel only, marked "not on your caseload" | No (404) |
| Any other provider, patient, anonymous | No | No (404 or login redirect) |

Crisis alerts themselves stay institution-visible without patient text, as designed (docs/PRIVACY_AND_CONSENT.md section 4). The plan does not widen that. The owner already saw the student's name in the alert panel, which is why the name appears in their panel.

**Reminders.** One `followup_due` job per step, key `followup-due:<step id>:<due date>`, run at 09:00 IST on the due date. The handler skips resolved steps and plans, and creates one in-app `Notification` per owner and due date. It emails the owner only when `SMTP_HOST` is set and the account has an address. Text: "You have follow-ups due today." (or "...waiting on your dashboard." if the job ran late). No patient name or health data in either channel. On a sleeping free-tier instance the job runs when the worker wakes, so a reminder can arrive late; the panel always shows overdue steps regardless.

**Appointment offer.** If a patient on an open plan has an appointment with the plan owner that was completed after the previous step was done (or after the plan began), the next step shows "Record session" instead of "Mark done". It never completes the step on its own.

**Audit actions** (ids and codes only): `followup_plan_create`, `followup_step_done|missed|skipped`, `followup_plan_complete`, `followup_plan_close`, plus the existing `ack_crisis` and `add_clinical_note`.

**Routes** (blueprint `provider_followups`; all `@login_required` plus `@provider_required`; writes need the CSRF header): `POST /provider/api/followups/steps/<id>` (`action`, `outcome`, `note`), `POST /provider/api/followups/plans/<id>/close` (`reason`), `GET /provider/api/appointment-reminders`.

## 2. Score-change flags

`utils/score_flags.py`. A flag appears for an assigned patient when the latest PHQ-9 or GAD-7 result rose by 5 or more points since the previous result of the same type, or entered a higher severity band (bands from `ai/scoring.py`). Badge text: "Score up 6 since last screening (PHQ-9)" or "Moved to a higher band since last screening (GAD-7)". The caseload has a "With score flag" checkbox (client side filter) and the report has a sparkline per screening with a text table. One SQL window query reads all assigned patients. Wording is "screening result", never "diagnosis", and nothing happens automatically. The 5 point threshold is a product choice (`RISE_POINTS`); it is not a validated clinical cut-off.

## 3. Appointment reminders

When an appointment becomes `accepted` (`utils/state.py::transition`) one `appointment_reminder` job is queued for 24 hours before the slot (IST wall clock converted to UTC), key `appt-reminder:<id>:24h`. If less than 24 hours remain it is due at once; if the slot is already past, nothing is queued. When it runs the handler re-checks: not accepted any more, slot changed, or slot already passed means a no-op (`skipped:*` in `jobs.last_error`), so no reminder is sent after the appointment time. It writes an in-app `Notification` to the student and the provider ("Reminder: appointment tomorrow at 10:00 with Dr Rao"; the provider copy names the student) and emails the student only when SMTP is configured. The provider dashboard shows "Reminder scheduled" or "Reminder sent" on an appointment row only when the job exists in that state.

Appointments accepted before this feature, or created directly as accepted by scripts, have no reminder job. There is no backfill command yet. The student-side schedule page does not show reminder status.

## Privacy notes

- Plans, steps and flags are derived from data the assigned provider could already see. The email and notification texts carry no name and no health data.
- Add the audit actions above to the table in docs/PRIVACY_AND_CONSENT.md section 6 (owner of that file).
- Deleting a patient cascades their plans and steps; deleting the owner sets `owner_provider_id` to NULL (reminders then skip).

## Unverified or open

- UGC three-session figure (draft, see above) and the 5 point threshold.
- Effect of follow-up contact: the caring-contacts evidence is for attempts, inconclusive for deaths (docs/research/competitive-2026.md). The tracker supports a workflow; it makes no outcome claim.
- Email reminder effectiveness is unverified (research covers SMS).
- Clinical review of the wording and the interval defaults.
