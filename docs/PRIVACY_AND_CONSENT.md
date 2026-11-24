# Privacy, consent and access rules

What the code does today about personal data. Written from the implementation (`routes/auth.py`, `routes/provider.py`, `utils/assignments.py`, `utils/audit.py`), not from a legal template. Items marked **Operator task** need a decision or a name that engineering cannot supply. The public Privacy Policy and Terms are drafts pending legal review.

## 1. Roles and who sees what

| Role | Sees |
|---|---|
| Patient (student) | Only their own data. |
| Provider (counsellor) | Individual data only for patients **assigned** to them (section 2). Institution-wide figures are aggregates only (section 3). Open crisis alerts of the whole institution (section 4). |
| Operator (database access) | Everything stored. Access is outside the app; see open items. |

Provider accounts need the `PROVIDER_INVITE_CODE`. There is no admin or dean role in the app yet.

## 2. Assigned-only rule (decision P-02)

A provider can open a patient's profile, assessments, mood and check-ins, notes, appointments and prescriptions only if a `ProviderPatient` row links the two. The row is created:

- automatically, in the same transaction, when a patient books an appointment with that provider (`/patient/schedule`);
- automatically when a provider accepts an unassigned appointment request from a patient of their institution;
- manually: `flask assign-patient <provider_email> <patient_email>` (same institution only; audited).

Rules enforced in `utils/assignments.py::link_provider_patient`: both roles must be right and both users must have the same institution (case-insensitive exact match). Creating the row is idempotent (unique constraint plus savepoint). A patient cannot book a provider of another institution.

An unassigned provider asking for a patient gets **404**, never 403, so a counsellor cannot probe which students exist. Unassigned appointment requests in the provider's queue show the student's name, date and slot only: no email, no notes, no health summary. The `/provider/appointments` JSON returns `patient_health_data: null`, `notes: null`, `patient_email: null`, `patient_id: null` for those rows.

Limits to know about:

- Rejecting an appointment does **not** remove the link. A provider who was booked and rejected can still open that student. Remove it with SQL or add an unassign command if this matters for the pilot.
- Databases that predate this rule have no links. Run `flask backfill-assignments` once: it links every patient who already has a non-rejected appointment with a provider.
- Deleting a provider account deletes the clinical notes they wrote (database cascade on `clinical_notes.provider_id`). If clinical records must outlive the counsellor's account, that foreign key has to change (**Operator task**, needs a retention decision).

## 3. Small-group rule for institution aggregates (K)

`MIN_AGGREGATE_GROUP` (default 5) is the minimum number of people behind any institution-level figure. In `routes/provider.py::institution_summary` and the analytics page:

- fewer than K patients in the institution: every figure is `None` (templates show "n/a");
- a count between 1 and K-1 is `None` (zero stays zero);
- an average built from fewer than K contributors (screen time, wellness score, completion rate) is `None`;
- daily chart points built from fewer than K logs are dropped.

This reduces re-identification in small colleges; it is not a formal anonymity guarantee (differencing across time windows is still possible).

## 4. Crisis safety override

Open (unacknowledged) crisis events of the provider's institution are shown to **every** provider of that institution, assigned or not, so an alert is never stuck with a counsellor who is away. The panel shows display name, source, severity and time. It never shows free text (the stored `reason` is a short code and is not shown either). Opening the panel writes one `view_crisis_panel` audit row (event ids only) and acknowledging writes `ack_crisis`. Seeing an alert does not open the student's file; that still needs an assignment.

## 5. Consent and the age gate (decision P-05)

- Signup requires two ticked boxes, checked on the server: `consent` (privacy notice) and `age_confirm` (18 or older). Both missing cases re-render the form with an error; passwords and the invite code are never echoed back.
- On success the user row and two `ConsentRecord` rows (`kind='privacy'`, `kind='age18'`) are written in one transaction. `version` is `CONSENT_VERSION` (default `2026-11`); `accepted_at` is UTC.
- Google sign-up: a new Google user is created, `session['consent_pending']` is set and the user is redirected to `/consent`. A guard (`before_app_request`) sends a pending user to `/consent` for every path except `/consent`, `/logout`, `/privacy`, `/terms`, `/health` and `/static/`. API and XHR calls get `403 {"error": "consent_required"}`. Posting both boxes at `/consent` writes the records and clears the flag.
- Version bumps: raising `CONSENT_VERSION` makes older records stale. `needs_reconsent(user)` is true for users who have records but none at the current version; their next login goes to `/consent`, and new rows are added next to the old ones (the old ones stay as proof). Users with no consent rows at all (accounts created before this feature) are **not** interrupted. **Operator task:** decide whether to force them through `/consent` once.
- Under-18 users are not supported; there is no parental-consent flow. The age box is a self-declaration, not verification.

## 6. Audit log

Table `audit_log` (`actor_id`, `action`, `target_type`, `target_id`, `meta` JSON, `created_at`). It stores ids and short codes only, never text a patient wrote.

| action | when | meta |
|---|---|---|
| `view_patient` | provider opens a patient's wellness report | none |
| `view_crisis_panel` | provider dashboard shows open crisis events | `event_ids` |
| `ack_crisis` | provider acknowledges a crisis event | none (target is the event) |
| `add_clinical_note` | provider saves a session note | none (target is the patient) |
| `send_prescription` | prescription created (only when the feature flag is on) | `patient_id` |
| `assign_patient` | CLI assignment | `provider_id`, `source` |
| `export_account` | user downloads their data | none |
| `delete_account` | user deletes their account | none; `actor_id` is empty, `target_id` is the deleted user id |

When a user is deleted the database sets `actor_id` to empty on their earlier audit rows; the rows remain. Retention of the audit log is an open item.

## 7. Export and deletion (DPDP rights)

`/account/data` (any logged-in role) explains what is stored and offers both actions.

- **Export**, `POST /account/export`: a JSON download (`Content-Disposition: attachment`, `Cache-Control: no-store`), rate limited, audited. Contents: profile without the password hash; assessments; mood and daily check-ins; journal entries; voice log measurements and AI analysis (the audio is never stored); digital detox, medication, breathing, yoga and music logs; goals; progress recommendations; appointments (as patient; as provider only date, time, type and status); notifications addressed to the user; crisis events as source, severity, code and time only; consent records; prescriptions received; the user's blog posts and comments; contact messages they sent; assigned providers (ids). Not included: other people's data, **clinical notes written by providers** (the product does not show them to patients, so they are not exported; change this together with any feature that shows notes to patients), chat messages (chat is not stored; only the Notification inbox is).
- **Delete**, `POST /account/delete`: needs the current password. Google-only accounts (no usable password) type their email address and the phrase `DELETE MY ACCOUNT`. CSRF protected, rate limited (5 per hour per client). The user row is deleted and the database cascades remove every dependent row. Rows that must survive are set to NULL: appointments where the user was the provider, `crisis_events.acknowledged_by`, audit actors, sent notifications. No uploaded files exist to remove: voice audio is analysed in memory and discarded, and profile pictures are not supported. The session is cleared, and the server-side stamp (docs/SECURITY.md, Sessions) makes any other cookie for this account stale. Only the `delete_account` audit row remains. The audit rows of other people that mention this id as `target_id` (for example a provider viewed this student earlier) keep the number but no name or text.
- Backups and logs: deletion does not reach database backups or the application log file. **Operator task:** state the backup retention in the privacy policy.

## 8. Data map

| Table | Purpose | Who can read | Retention | Deleted with account |
|---|---|---|---|---|
| `users` | Login and profile | Owner; assigned providers see name and email | Until deletion | Yes |
| `assessments` | PHQ-9, GAD-7, daily mood results and AI insight | Owner; assigned providers | Until deletion (period to be set) | Yes (cascade) |
| `mood_logs`, `rpm_data` | Mood and check-in series | Owner; assigned providers | Until deletion | Yes |
| `journal_entries` | Journal text, sentiment, AI suggestions | Owner only (providers see no journal text) | Until deletion | Yes |
| `voice_logs` | Voice measurements, emotion guess, AI note (no audio, no transcript) | Owner only | Until deletion | Yes |
| `digital_detox_logs` | Screen-time logs | Owner; assigned providers | Until deletion | Yes |
| `medications`, `medication_logs` | Reminders and adherence | Owner; assigned providers (adherence view) | Until deletion | Yes |
| `breathing_exercise_logs`, `yoga_logs`, `music_therapy_logs` | Activity history | Owner; counted in aggregates | Until deletion | Yes |
| `goals`, `progress_recommendations` | Goals and AI suggestions | Owner; assigned providers (goals in report) | Until deletion | Yes |
| `gamification` | Points and streak | Owner; aggregate averages | Until deletion | Yes |
| `appointments` | Booking, status, patient note | Patient; the booked provider; unassigned requests: name and slot to institution providers | Until deletion | Yes (as patient); provider link set to NULL |
| `provider_patients` | Assignment | Provider and patient side of the link | Until deletion | Yes |
| `clinical_notes` | Provider session notes and transcript | The writing provider (and assigned providers of that patient) | Until deletion | Yes when the patient is deleted; also when the writing provider is deleted |
| `prescriptions` | Feature off by default (P-01) | Patient; prescribing provider | Until deletion | Yes |
| `crisis_events` | Time, source, severity, code; no text | Providers of the institution while open; assigned providers after | Until deletion (period to be set) | Yes |
| `notifications` | Inbox messages | Recipient | Until deletion | Yes (recipient); sender link set to NULL |
| `consent_records` | Proof of consent, version and time | Owner (export); operator | Until deletion | Yes |
| `audit_log` | Access and change trail | Operator | To be set | Rows stay, actor emptied |
| `contact_messages` | Public contact form | Operator | To be set | User link set to NULL; message stays (sender can ask for removal) |
| `blog_posts`, `blog_comments`, `blog_likes` | Community content | Public or logged-in readers | Until deletion | Yes |
| `jobs`, `analytics_events` | Background work and consent-gated page events | Operator | Jobs 7 to 90 days (see DESIGN.md); events to be set | Jobs hold ids only; events hold no user id |

Health data is stored as plain text in the database; there is no field-level encryption yet (tracker item O-04). Do not describe it as encrypted.

## 9. Open legal and operator items

- **Operator task:** name the data fiduciary (`DATA_FIDUCIARY_NAME`).
- **Operator task:** name the grievance officer and mailbox (`GRIEVANCE_EMAIL`), with the response time promised.
- **Operator task:** set retention periods per data class (assessments, journal, voice, crisis events, audit log, backups) with counsel; no automatic deletion job exists.
- **Operator task:** decide whether a Data Protection Officer or a significant-data-fiduciary assessment applies.
- **Operator task:** decide the handling of under-18 students (parental consent) before lowering the age gate.
- **Operator task:** confirm cross-border processing terms for the AI provider.
- **Operator task:** state who may read database backups and application logs, and how access is recorded.
- Registered-prescriber verification does not exist; prescriptions stay behind `ENABLE_PRESCRIPTIONS` (default off) until it does.
