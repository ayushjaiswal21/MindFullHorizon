# Clinical workflow design: roles, prescriber verification, prescriptions, inventory, dashboards

Status: design contract for the Nov 2026 wave. Written 2026-11-24 against the repo state at that date (migration head `0003`, 265 tests). Implementers treat this file as the contract: if the code and this file disagree, fix the code or open a change to this file, do not improvise. Regulatory background and URLs are in [research/prescribing-inventory.md](research/prescribing-inventory.md). Nothing here is legal advice; section 15 lists what needs legal and pharmacist review before real use.

**Role model (lead decision, supersedes the owner's four-role request):** the database has THREE roles: `patient`, `provider`, `admin`. There is no `doctor` role. A doctor is a `provider` with `User.provider_type = 'doctor'` whose `PrescriberProfile.status` is `verified`. A counsellor is a `provider` with `provider_type = 'counsellor'` (or NULL, which means counsellor). So there are three dashboards: patient, provider (counsellor view, plus a "Prescribing" section that exists only for verified doctors) and admin.

Existing rules this design must not weaken (CLAUDE.md, RULES.md, decisions P-01 to P-06): every user-data route has `@login_required` plus a role decorator and filters by the session user; never return `str(e)`; never log patient text; no Jinja in static JS; helplines only from `utils/helplines.py`; no points or streaks on assessments; no fake claims in UI copy; new routes in blueprints, never in `app.py`; schema changes need Alembic; no emoji and no em dashes anywhere.

## 0. Decisions at a glance

| ID | Decision | Why |
|----|----------|-----|
| C-01 | Roles stay `patient`, `provider`, `admin`. `provider_type` ('counsellor' or 'doctor', nullable) separates counsellors from doctors. Admin has an optional capability flag `is_pharmacy_desk`. | One provider dashboard and one set of provider routes (lead). The flag keeps "which student takes which medicine" away from a dean-type administrator. |
| C-02 | Doctor accounts come from `DOCTOR_INVITE_CODE`, counsellor accounts from `PROVIDER_INVITE_CODE`, admins only from `flask create-admin`. Admins cannot sign in with Google. Providers signed in with Google are not possible today and stay so. | Smallest privilege-escalation surface. |
| C-03 | Prescribing needs a `PrescriberProfile` with `status = verified` and a review date in the future, checked again inside the issue transaction. The check is a manual lookup by an institution admin. | The NMC publishes no official API (research file). Manual with evidence is honest. |
| C-04 | A prescription is issued only after a recorded consult (`appointments.modality` video or in_person, `consult_started_at` set by the doctor, inside a window), for an assigned patient who gave e-prescription consent. | "Consult happened" is a stored fact the server checks, not a checkbox on the prescribe form. |
| C-05 | TPG lists are data on `Medicine`, verified by a second admin (four-eyes). Unknown or unverified means blocked. List C, Schedule H1, X and NDPS medicines are blocked from prescribing and from stock in v1. | The lists change and conflict between sources; software must not guess. |
| C-06 | Issued prescriptions are immutable. Amendment = cancel plus reissue linked by `amends_id`. | Audit and pharmacy trust. |
| C-07 | No stock reservation at issue. The doctor sees advisory availability. Dispensing is the single point of truth and uses compare-and-set updates. | Prescriptions are portable for 30 days; reservations would lock stock for people who never collect. |
| C-08 | Inventory is an append-only ledger (`InventoryTransaction`) plus a stored `quantity_on_hand` on the batch, both changed in one transaction, with `CHECK (quantity_on_hand >= 0)` as the last line of defence. | Cannot oversell under concurrency. |
| C-09 | Dispensing is by an admin with `is_pharmacy_desk`, in two steps (prepare, confirm), with a signed plan token and an idempotency key. The desk finds a prescription by number or from a queue of prescriptions the patient chose to send. | Pharmacist check; no browsable list of all students' medicines. |
| C-10 | Drug-interaction checking is NOT built and NOT claimed. Only a same-medicine and same-class duplicate warning and a plain allergy text match. | No licensed database. |
| C-11 | `ENABLE_PRESCRIPTIONS` default flips to ON. | Safe only because issuing is gated by a verified doctor and an empty catalogue blocks everything (section 13). |
| C-12 | No real clinical data in migrations. Demo medicines exist only in `scripts/seed_demo.py`, have fictional names and `is_demo = true`, and are refused in production. | Wrong real data is worse than none. |

## 1. Roles, accounts, scoping, permissions

### 1.1 Roles and provider types

| Role | `provider_type` | Who | Can prescribe | Home endpoint |
|------|-----------------|-----|---------------|---------------|
| `patient` | NULL | Student (18+). Self signup only. | no | `patient.patient_dashboard` |
| `provider` | `counsellor` or NULL | Counsellor (psychologist, social worker). | never | `provider.provider_dashboard` |
| `provider` | `doctor` | Registered medical practitioner (psychiatrist or physician). Until verified it behaves exactly like a counsellor. | only while verified (1.5) | `provider.provider_dashboard` |
| `admin` | NULL | Institution administrator. With `is_pharmacy_desk = true` also the pharmacy desk. | no | `admin.dashboard` |

`services/roles.py` (owner A) exports:

```python
ROLES = ('patient', 'provider', 'admin')
def home_endpoint(role) -> str                       # 'patient.patient_dashboard' | 'provider.provider_dashboard' | 'admin.dashboard'
def norm_inst(name) -> str                           # lower, strip, collapse whitespace; '' for empty
def same_inst(a, b) -> bool                          # bool(norm_inst(a)) and norm_inst(a) == norm_inst(b)
def provider_type_of(user) -> str | None             # None for non-providers; 'counsellor' when provider_type is NULL
def is_doctor(user) -> bool                          # role provider and provider_type == 'doctor' (NOT verification)
def bookable_staff(institution) -> list[User]        # providers a patient may book: counsellors, and doctors only when verified
```

Every `_home(role)`, nav and redirect uses `home_endpoint`, so nothing else hard-codes "patient else provider".

### 1.2 Account creation

| Account | How | Gate |
|---------|-----|------|
| patient | `/signup`, hidden `role=patient` | consent and 18+ checkboxes (P-05) |
| counsellor | `/signup`, `role=provider`, `provider_type=counsellor`, `invite_code` | `PROVIDER_INVITE_CODE` (unset = closed), `hmac.compare_digest` |
| doctor | `/signup`, `role=provider`, `provider_type=doctor`, `invite_code`, `registration_number`, `council`, `registered_since`, `specialisation` | `DOCTOR_INVITE_CODE` (unset = closed). Creates the `User` and a `PrescriberProfile(status='pending')` in the same transaction as `ConsentRecord`s. |
| admin | `flask create-admin --email E --name N --institution I [--pharmacy-desk]` only. Password read with `click.prompt(hide_input=True, confirmation_prompt=True)` and checked by `is_strong_password`. Refuses if the email exists. Writes `AuditLog(actor_id=None, action='admin_created')`. | Operator shell access. No env code, no web form, no promotion of an existing user. |

Extra CLI in `services/admin_cli.py` (registered by one line in `app.py` through `init_admin_cli(app)`): `flask set-pharmacy-desk --email E --on|--off`, `flask admin-set-password --email E`, `flask set-provider-type --email E --type counsellor|doctor` (creates a `pending` profile row if switching to doctor with none). All audited, all require the target to have the matching role.

Rules enforced in code and tested:
- `/signup` with role `admin` or any unknown role returns "Invalid role." and creates nothing (existing `test_signup_unknown_role_rejected` stays valid).
- The two invite codes are different secrets. If both env vars are set and equal, doctor signup is disabled (log a warning with no code). The code must match the code of the CHOSEN `provider_type`: the counsellor code never makes a doctor, the doctor code never makes a counsellor.
- Doctor signup with a wrong or missing code returns "Doctor accounts need a valid invite code." and creates nothing, including no `PrescriberProfile`.
- Field limits: registration number 4 to 20 characters `[A-Za-z0-9/\-]`, council 3 to 100, `registered_since` integer 1950 to the current year, specialisation 0 to 100. Invalid values re-render the form with an error; passwords and the code are never echoed.
- Main `/login` accepts roles `patient` and `provider`. A POST with role `admin` fails with the same generic `LOGIN_ERROR` as a wrong password. Admins sign in at `/admin/login` (no role field, limiter `5 per minute`, same generic error, same `session` keys, role must be `admin`).
- Google OAuth never signs in an `admin` account (generic "use your password" message). Edit in `app.py` by A is that one check. `/save_role` is unchanged (patients only); `tests/test_security.py::test_save_role_*` must still pass.
- Session keys are unchanged: `user_id`, `user_email`, `user_role`, `user_name`, `user_institution`. Decorators for prescribing and admin actions re-read the `User` row (1.5) and never trust `session['user_role']` alone.
- `provider_type` is set only at signup or by the CLI. No route lets a user edit it. Changing the doctor's `registration_number` or `council` resets the profile to `pending` (section 2).

### 1.3 Role CHECK migration (the only constraint change on `role`)

`models.py`: `db.CheckConstraint("role IN ('patient','provider','admin')", name='ck_user_role')`. One code path for SQLite and PostgreSQL:

```python
with op.batch_alter_table('users') as b:
    b.drop_constraint('ck_user_role', type_='check')
    b.create_check_constraint('ck_user_role', "role IN ('patient','provider','admin')")
```

- SQLite: batch mode recreates the table. The constraint was created with the explicit name `ck_user_role`, so reflection finds it. If `drop_constraint` raises "No such constraint" on a database created some other way, fall back to `op.batch_alter_table('users', recreate='always', table_args=(sa.CheckConstraint(NEW, name='ck_user_role'),))`.
- SQLite foreign keys: `models.py` turns `PRAGMA foreign_keys=ON` for every connection, and a `DROP TABLE users` inside batch recreate can cascade-delete child rows when foreign keys are on. **Required:** read how `migrations/env.py` and migration `0003` handle this first; if foreign keys are not already disabled around batch operations, run `PRAGMA foreign_keys=OFF` before and `ON` after the batch block when `bind.dialect.name == 'sqlite'`. Add a migration test that a patient with an assessment and a provider with an appointment survive the upgrade (row counts equal before and after).
- PostgreSQL: `ALTER TABLE ... DROP CONSTRAINT`, then `ADD CONSTRAINT ... CHECK`. `users` is small; one validating scan, no `NOT VALID`.
- Same migration adds: `users.provider_type String(12) NULL` with `CHECK (provider_type IS NULL OR provider_type IN ('counsellor','doctor'))` named `ck_user_provider_type`, `users.deactivated_at DateTime NULL`, `users.is_pharmacy_desk Boolean NOT NULL server_default false`. It backfills `provider_type = 'counsellor'` for existing `role = 'provider'` rows. There is deliberately NO check tying role to provider_type, because `tests/conftest.py::make_user` creates providers with `provider_type` NULL.
- Downgrade is for development only: refuse with `RuntimeError` if any `admin` row exists; drop the three columns; restore the two-value CHECK.

`tests/test_db.py` line 42 inserts role `admin` and expects `IntegrityError`; change the value to `'superuser'` (section 12).

### 1.4 Institution scoping

There is no `Institution` table. `User.institution` is free text; matching is `lower(trim())` equality (`utils/assignments.same_institution`). This wave keeps that. New tables store `institution_key = norm_inst(...)` (String 100), never the display string. Rules:
- An `admin` and a `provider_type = 'doctor'` provider must have a non-empty institution (signup and CLI reject empty). The signup form default "Default University" stays for patients and counsellors.
- Every admin query filters by the admin's institution key read from the DB row, never from the client.
- The medicine catalogue is institution-independent. Stock, reorder rules and the dispensing log are per `institution_key`.
- A doctor prescribes only for patients of the same institution who are assigned to them.
- Typos split campuses (MEMORY.md debt). The admin staff screen shows "Institution as typed" so the admin can spot it. An `Institution` table is the later fix, out of scope.

### 1.5 Decorators (`decorators.py`, owner A)

Keep every existing decorator untouched (`provider_required`, `role_required`, `prescriptions_required`...). Add:

```python
def roles_required(*roles): ...            # session role in roles; 401/403/redirect like role_required
def admin_required(f): ...                 # login + role admin + DB re-check: row exists, role still admin, deactivated_at is None
def pharmacy_desk_required(f): ...         # admin_required + users.is_pharmacy_desk
def doctor_provider_required(f): ...       # provider_required + DB re-check provider_type == 'doctor' and deactivated_at is None (profile page, may be unverified)
def verified_prescriber_required(f): ...   # doctor_provider_required + services.prescriber.require_verified(user_id); JSON 403 {"error":"prescriber_not_verified"} or flash + redirect to provider.rx_profile
```

- JSON 401/403 for paths under `/provider/api/`, `/admin/api/`, any `/api` path and `X-Requested-With: XMLHttpRequest`; HTML routes redirect with a flash like the existing ones.
- `doctor_provider_required` and `verified_prescriber_required` answer 404 (not 403) when the provider is not `provider_type = 'doctor'`, so counsellors cannot discover prescribing exists; an unverified doctor gets 403 JSON `prescriber_not_verified` or a redirect to `provider.rx_profile`. A patient or admin hitting a provider route gets the existing `provider_required` behaviour.
- Denials on prescribing, admin and desk routes write one `AuditLog(action='denied', target_type='route', meta={'code': 'role'|'inactive'|'not_verified'|'not_desk'})` in its own short transaction (`db.engine.begin()`), so a rolled-back request still leaves a row. No path or query string in meta.
- Deactivated users: `login` refuses users with `deactivated_at` set (generic error). Existing sessions of a deactivated admin or doctor die at the next decorator re-check; counsellor sessions die at next login (accepted: counsellors keep today's behaviour, called out in section 13).
- `can_join_telehealth` needs no change (role `provider` already covers doctors).
- `prescriptions_required` stays; flag semantics in section 13.

### 1.6 How staff get access to patients

Unchanged P-02 mechanism; doctors are providers, so `link_provider_patient` already works for them with no code change.
- A patient books an appointment with a counsellor or doctor of the same institution; the existing `link_provider_patient(provider_id, patient_id, source='appointment')` creates the `ProviderPatient` row. `flask assign-patient` works for doctors unchanged.
- The patient schedule form lists `bookable_staff(institution)`: counsellors, and doctors only when `PrescriberProfile.status = 'verified'` and the review date is in the future, so an unverified registrant never appears to patients. Each option shows "Counsellor" or "Doctor". Package C changes `routes/patient.py::schedule_appointment` (including the validity check at line ~166) to call `bookable_staff`.
- Appointments with a doctor carry `modality` (`video` or `in_person`); the form shows the field when a doctor is selected. Counsellor appointments keep `modality = NULL`.
- A doctor and a counsellor can share a patient: two `ProviderPatient` rows. Each sees what the matrix (1.7) allows, never the other's `ClinicalNote`s. The patient dashboard shows a "Your care team" card (assigned staff by name and type, from `ProviderPatient`), so the patient knows who can see their data.
- No admin UI assigns patients (admins must not browse students). CLI only.
- Existing "accept unassigned institution requests" behaviour stays for counsellors. For doctors, accept and reject apply only to appointments addressed to them (`appointment.provider_id == session user`); an unassigned request is not shown to a doctor.

### 1.7 Permission matrix

Legend: `own` = the user's own rows; `assigned` = patients linked by `ProviderPatient`; `agg(K)` = institution aggregate with small cells suppressed (K = `MIN_AGGREGATE_GROUP`, default 5); `ro` = read only; `-` = no access. "Counsellor" also describes a doctor who is not verified. "Doctor" means `provider_type = 'doctor'` AND verified. "Desk" means admin with `is_pharmacy_desk`. Rows marked audit write an `AuditLog` row (1.8).

| Data or action | patient | counsellor | doctor (verified) | admin | admin + desk |
|---|---|---|---|---|---|
| Own profile, consent, export, delete | own | own | own (delete becomes "deactivate, contact admin" once a prescription exists) | own | own |
| Assessments, mood, detox, goals | own | assigned ro, audit | assigned ro, audit | - | - |
| Journal entries, voice logs, AI chat text | own | - | - | - | - |
| Self-logged medication list (`Medication`) | own rw | assigned ro, audit | assigned ro, audit | - | - |
| Clinical notes (`ClinicalNote`) | - | own rw, author only | own rw, author only | - | - |
| Another staff member's notes | - | - | - | - | - |
| Crisis events | own alert UX | institution safety override (all unacknowledged events of the institution), may acknowledge, audit | same as counsellor | `{any, count}` of overdue open alerts, count shown only when >= K, no identity | same |
| Institution aggregates | - | agg(K) | agg(K) | agg(K) | agg(K) |
| Appointments | own | own plus unassigned institution requests | own addressed to them; accept, reject, start consult, complete | counts only, agg(K) | counts only |
| Telehealth room | own appointment | assigned | assigned | - | - |
| Prescription: create draft, edit, issue, cancel, amend | - | - (404) | own only | - | - |
| Prescription: read | own, from issue onward | assigned patients: item lines only (medicine, dose, frequency, duration, status), audit | own: all states; other staff's Rx of an assigned patient: item lines only, audit | - | only a prescription looked up by number or sent by the patient: full content, audit |
| Prescription: print | own | - | own | - | desk, same lookup rule, audit |
| Send prescription to pharmacy desk | own | - | - | - | - |
| Dispense, reverse a dispense | - | - | - | - | yes, audit |
| Medicine search with availability badge | - | - | yes | - | - |
| Medicine catalogue: list, create, edit, deactivate, CSV | - | - | - | yes | yes |
| Catalogue list verification (TPG list, schedule) | - | - | - | yes, by a different admin than the last editor | same |
| Stock levels, batches, expiry, reorder rules, reports | - | - | availability badge only | read only | read and write (receive, adjust, write off, reorder rules, CSV import) |
| Dispensing log | - | - | - | read, Rx number masked | read, full number |
| Usage-by-medicine report | - | - | - | agg(K) by distinct patients | agg(K) |
| Prescriber verification (verify, reject, suspend, reinstate) | - | - | own status only | institution's doctors | same |
| Staff list, deactivate or reactivate staff | - | - | - | institution staff | same |
| Audit log viewer | - | - | - | institution (actor in institution), ro | same |
| Annual report export | - | - | - | agg(K) | agg(K) |
| Contact message inbox | - | - | - | yes, audit | same |
| Patient names or ids in lists | - | assigned | assigned | never | only the one looked-up or sent prescription |

Rules behind the matrix, each with a test:
1. Counsellors and doctors see only assigned patients (existing `scoped_patient_or_404`); a non-assigned id returns 404, never 403.
2. Institution aggregates hide any figure drawn from fewer than K people.
3. Admins never receive assessments, journal, chat, notes, mood or a patient list. Admin templates and JSON contain no patient name or id, except the desk exception.
4. Crisis visibility for providers is unchanged (institution-wide, audited).
5. Every sensitive read is audited.
6. 404, not 403, for any patient id outside a user's scope. 403 only for role failures.
7. A counsellor can never reach a prescribing route (the decorator returns 404 for a non-doctor, 403 JSON for an unverified doctor; section 5.3).

### 1.8 Audit actions (additions to `AuditLog.action`, no schema change)

`utils.audit.audit(actor_id, action, target_type, target_id, **meta)` is used everywhere. Meta holds ids and short codes only: never diagnosis, allergy text, dose text, search text. Medicine ids are allowed.

| Action | target_type | When | meta |
|---|---|---|---|
| `view_patient` | `user` | doctor opens patient detail (existing name, reuse) | none |
| `view_patient_meds` | `user` | a provider reads another staff member's Rx lines | `n` |
| `rx_draft_create`, `rx_draft_delete` | `prescription` | | `patient_id` |
| `rx_issue` | `prescription` | | `patient_id`, `items`, `lists` such as `OA`, `warnings` codes |
| `rx_issue_blocked` | `prescription` | issue refused by a rule | `code` |
| `rx_cancel` | `prescription` | | `reason_code`, `by` (`doctor` or `system`) |
| `rx_amend` | `prescription` | | `old_id` |
| `rx_print` | `prescription` | doctor or desk prints | `by` |
| `rx_lookup_desk` | `prescription` | desk finds by number or opens from queue | `via` (`number` or `queue`) |
| `rx_send_to_desk` | `prescription` | patient requests collection | none |
| `rx_dispense`, `rx_dispense_reverse` | `prescription` | | `group_ref`, `lines` |
| `erx_consent_give`, `erx_consent_withdraw` | `user` | patient | `version` |
| `prescriber_submit`, `prescriber_edit_reset`, `prescriber_verify`, `prescriber_reject`, `prescriber_suspend`, `prescriber_reinstate` | `prescriber_profile` | every status transition | `from`, `to` |
| `consult_start`, `consult_complete` | `appointment` | doctor | `modality` |
| `medicine_create`, `medicine_edit`, `medicine_deactivate`, `medicine_list_verify` | `medicine` | | changed field names only |
| `stock_receive`, `stock_adjust`, `stock_writeoff`, `stock_import`, `reorder_set` | `inventory_batch` or `medicine` | | `delta`, `reason_code`, `rows` |
| `staff_deactivate`, `staff_reactivate` | `user` | | none |
| `view_audit_log`, `export_annual_report`, `export_stock_csv`, `view_contact_message` | various | one row per list view or export, not per row | counts |
| `admin_created`, `admin_pharmacy_desk_set`, `admin_password_set`, `provider_type_set` | `user` | CLI | none |
| `denied` | `route` | decorator denial | `code` |

Retention: keep audit rows at least one year (DPDP Rule 8(3) as reported by secondary sources) and never delete them in code. `AuditLog` is append-only by convention and by test (no `update()` or `delete()` of `AuditLog` in `routes/`, `services/`). DB triggers are NOT added in this wave because `tests/conftest.py::clean_db` deletes rows from every table; revisit when the fixture can bypass them.

## 2. Prescriber verification

### 2.1 Table `prescriber_profiles` (`PrescriberProfile`)

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `user_id` | Integer FK `users.id` ON DELETE CASCADE, NOT NULL, UNIQUE | one profile per provider; only users with `provider_type = 'doctor'` get one |
| `registration_number` | String(20) NOT NULL | normalised on write: strip, upper-case, remove spaces |
| `council` | String(100) NOT NULL | "National Medical Commission" or the State Medical Council as the register shows it |
| `council_key` | String(100) NOT NULL | lower-case, collapsed spaces version of `council`, for uniqueness |
| `registered_since` | Integer NOT NULL | year of registration |
| `specialisation` | String(100) NULL | |
| `status` | String(10) NOT NULL default `pending` | CHECK `status IN ('pending','verified','rejected','suspended')` named `ck_prescriber_status` |
| `submitted_at` | DateTime NOT NULL | naive UTC |
| `verified_at` | DateTime NULL | set on `verified`, cleared when status leaves verified |
| `verified_by` | Integer FK `users.id` ON DELETE SET NULL, NULL | the admin who made the last status decision |
| `review_due_at` | DateTime NULL | `verified_at + PRESCRIBER_REVIEW_DAYS` (default 365) |
| `notes` | String(500) NULL | evidence note or reason, admin-written, never shown to patients |
| `status_changed_at` | DateTime NOT NULL | |
| `created_at`, `updated_at` | DateTime | |

Indexes: `idx_prescriber_status` on `(status)`, and a PARTIAL unique index `uq_prescriber_reg_active` on `(registration_number, council_key)` with `WHERE status IN ('pending','verified','suspended')` (both `sqlite_where` and `postgresql_where`, the same pattern as `uq_appt_active_slot`), so one registration number cannot be held by two live accounts, but a rejected registrant can correct and resubmit.

### 2.2 The honest limit

The app cannot call the NMC registry. No official public API was found (research file section 2); third-party wrappers are unverified, may scrape the register against its terms, and would put a paid dependency in the safety path. So verification is a human check by an institution admin, recorded with evidence. The admin screen says so in plain words: "This check is done by a person. MindFull Horizon does not query the NMC register automatically. A verified badge means an administrator of your institution checked the entry on the date shown, not that the NMC confirmed it to us."

The manual check (a checklist on the screen, every box required to approve):
1. Open the Indian Medical Register search at https://www.nmc.org.in/information-desk/indian-medical-register/ and search by registration number (State council and year help narrow results).
2. The entry's name matches the doctor's account name, the year of registration matches `registered_since`, and the State Medical Council matches `council`.
3. The doctor is not on the NMC removed-doctors list https://www.nmc.org.in/information-desk/indian-medical-register/black-list-doctors/ (disciplinary orders can lag online; if in doubt ask the State Medical Council).
4. The registration is for modern medicine (not AYUSH).
5. The doctor really works with this institution (institutional email or staff ID).

The admin also writes a one-line evidence note (required, 10 to 500 characters, for example "NMR search 2026-11-24, found, name and year match"). A "not found" result is not proof of fraud (older registrants may be only in a State register): the admin may reject with a reason or leave `pending` and contact the doctor.

### 2.3 Status machine

| From | To | Who | Condition | Effect |
|---|---|---|---|---|
| (none) | `pending` | doctor signup, or CLI `set-provider-type` | | no prescribing |
| `pending` | `verified` | admin of the same institution | all checklist boxes plus evidence note | sets `verified_at`, `verified_by`, `review_due_at`; the doctor may prescribe |
| `pending` | `rejected` | admin | reason required | no prescribing |
| `verified` | `suspended` | admin | reason required | prescribing blocked on the NEXT request (no cache); dispensing of their issued prescriptions blocked (3.8) |
| `suspended` | `verified` | admin | checklist again plus note | resumes |
| `rejected` | `pending` | the doctor, by editing and resubmitting | | back in the queue |
| `pending` or `verified` | `pending` | the doctor edits `registration_number`, `council` or `registered_since` | | `verified_at` cleared; prescribing blocked until re-verified; audit `prescriber_edit_reset` |
| `verified`, lapsed | stays `verified` | time | `now >= review_due_at` | NOT a stored change: `is_verified()` returns false, the admin dashboard asks for a re-check; a nightly job (4.10) notifies the institution's admins 30 days before and on the day |

Rules: the verifying admin and the doctor share a normalised institution; an admin is never a doctor, so nobody verifies themself by construction; a doctor never changes `status`, `verified_*` or `notes` (only the three identity fields above, and specialisation without a reset). Every transition writes `AuditLog` with `from` and `to` (1.8) and the route commits the status change and the audit row together.

```python
# services/prescriber.py (owner A)
def submit_profile(user_id, registration_number, council, registered_since, specialisation=None) -> PrescriberProfile
def get_profile(user_id) -> PrescriberProfile | None
def is_verified(profile, now=None) -> bool                      # status == 'verified' and review_due_at > now
def require_verified(user_id, lock=False) -> PrescriberProfile  # raises ServiceError('prescriber_not_verified', 403); lock=True: SELECT ... FOR UPDATE on PostgreSQL
def verify(profile_id, admin_id, checks: dict, note: str) -> PrescriberProfile
def reject(profile_id, admin_id, note: str) -> PrescriberProfile
def suspend(profile_id, admin_id, note: str) -> PrescriberProfile
def reinstate(profile_id, admin_id, checks: dict, note: str) -> PrescriberProfile
def queue(institution_key, status=None, page=1, per_page=20) -> (rows, meta)   # rows join User
```

Every function asserts the admin and the profile's user share an institution (`ServiceError('not_found', 404)` otherwise, so existence does not leak across institutions). They flush but do not commit; the route commits.

## 3. Prescription lifecycle and rules

### 3.1 Tables

`prescriptions` (existing table, altered in the migration of section 11). Legacy columns `medication_name` and `dosage` become NULLABLE and are used only by legacy rows. `issue_date` loses `default=utcnow` and is NULL for drafts. `provider_id` FK changes from CASCADE to RESTRICT (a doctor with prescriptions cannot be hard-deleted, see 3.9). New columns:

| Column | Type | Notes |
|---|---|---|
| `number` | String(24) UNIQUE NULL | NULL for drafts |
| `status` | String(20) NOT NULL | CHECK `draft, issued, partially_dispensed, dispensed, cancelled, expired, legacy` (`ck_rx_status`). Existing rows migrate to `legacy`; the Python default for new rows is `draft`. |
| `institution_key`, `institution_name` | String(100) | snapshot of the doctor's institution at draft creation |
| `doctor_name`, `doctor_reg_no`, `doctor_council`, `doctor_specialisation` | String | copied at issue so the printout never changes if the profile later does |
| `patient_name` | String(100) | snapshot at issue |
| `consult_appointment_id` | Integer FK `appointments.id` ON DELETE SET NULL | the qualifying consult |
| `tpg_context` | String(10) | `first`, `follow_up` or `in_person`, computed by the server at issue |
| `same_condition_attested` | Boolean default false | doctor's attestation, used only for `follow_up` |
| `diagnosis` | String(120) | required at issue; free text or an ICD-10 code (the psychiatry guidance asks for a diagnosis and suggests an ICD code for confidentiality: Secondary) |
| `allergies_status` | String(12) | `none_reported`, `listed`, `unknown`; CHECK |
| `allergies` | String(300) NULL | required when `listed` |
| `current_meds_status` | String(12) | same three values; CHECK |
| `current_meds` | String(300) NULL | required when `listed` |
| `warnings_ack` | JSON NULL | list of warning codes the doctor acknowledged |
| `consent_version` | String(20) NULL | the e-prescription consent version found at issue |
| `amends_id` | Integer FK `prescriptions.id` ON DELETE SET NULL | on the NEW row, points to the cancelled old one |
| `cancelled_at`, `cancelled_by` | DateTime; Integer FK users SET NULL | |
| `cancel_reason` | String(20) NULL | CHECK `error, patient_request, clinical_change, amended, system` |
| `dispense_requested_at` | DateTime NULL | the patient pressed "send to pharmacy desk" |
| `client_request_id` | String(64) NULL | idempotency for draft creation |
| `issue_request_id` | String(64) NULL | idempotency for issue |
| `row_version` | Integer NOT NULL default 1 | optimistic concurrency for draft edits |
| `created_at`, `updated_at` | DateTime | |

Existing `issue_date` = issue time (naive UTC) and `expiry_date` = expiry instant (naive UTC). Indexes: `idx_rx_provider_status (provider_id, status)`, `idx_rx_patient_status (patient_id, status)`, `idx_rx_inst_status_req (institution_key, status, dispense_requested_at)`, UNIQUE `uq_rx_provider_crid (provider_id, client_request_id)`, UNIQUE `uq_rx_provider_issue_rid (provider_id, issue_request_id)`. Relationships: `User.prescribed_prescriptions` loses `cascade='all, delete-orphan'` (use `passive_deletes=True` only); `User.received_prescriptions` keeps its cascade (patient deletion removes their prescriptions, see 3.9).

`prescription_items` (`PrescriptionItem`):

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `prescription_id` | FK `prescriptions.id` ON DELETE CASCADE, NOT NULL | |
| `line_no` | Integer NOT NULL | 1-based; UNIQUE `(prescription_id, line_no)` |
| `medicine_id` | FK `medicines.id` ON DELETE RESTRICT, NOT NULL | UNIQUE `(prescription_id, medicine_id)`: the same medicine twice in one prescription is an error, not a warning |
| `medicine_label` | String(200) | snapshot at issue: `GENERIC NAME strength form`, generic in capitals as the TPG psychiatry guidance asks |
| `tpg_list` | String(1) | snapshot at issue |
| `dose_text` | String(60) NOT NULL | for example "1 tablet" |
| `frequency` | String(60) NOT NULL | for example "twice daily after food" |
| `duration_days` | Integer NOT NULL | CHECK `duration_days BETWEEN 1 AND 90` (`ck_rxi_duration`); the effective cap is lower (3.4) |
| `quantity` | Integer NOT NULL | CHECK `quantity BETWEEN 1 AND 500` (`ck_rxi_qty`); in units of the medicine's form |
| `quantity_dispensed` | Integer NOT NULL default 0 | CHECK `quantity_dispensed >= 0 AND quantity_dispensed <= quantity` (`ck_rxi_dispensed`) |
| `instructions` | String(200) NULL | |

Free text rules (all text fields above, plus `diagnosis`, `allergies`, `current_meds`): `strip()`, collapse whitespace and newlines to single spaces, remove control characters (`\x00-\x1f`, `\x7f`), enforce the length (422 `field_too_long`), store as text, output only through Jinja autoescape or `textContent`. They are NEVER written to logs, audit meta, job payloads, error messages or analytics. Front-end JS never forwards them to `log_client_error`.

### 3.2 Who may do what

| Action | Actor | Preconditions |
|---|---|---|
| Create draft | verified doctor | patient assigned (`ProviderPatient`), same institution, patient `role = 'patient'` |
| Edit or delete draft | the doctor who owns it | status `draft`, `row_version` matches |
| Validate (dry run) | the owner | status `draft` |
| Issue | the owner | 3.3 to 3.7 |
| Cancel | the issuing doctor, or the system (job) | status `issued` or `partially_dispensed`; reason code required |
| Amend | the issuing doctor | status `issued` only (for `partially_dispensed`, cancel the remainder and write a new prescription) |
| View | patient (own, from `issued`), the issuing doctor, other providers (item lines, 1.7), pharmacy desk (lookup rule) | |
| Send to desk | the patient | status `issued` or `partially_dispensed`, not expired |
| Dispense or reverse | pharmacy desk | 4.6 and 4.7 |

Counsellors and admins without the desk flag cannot reach any write route (404 for counsellors, 403 for admins).

### 3.3 The "consult happened" representation

Today `appointments.appointment_type` is free text from a select (`therapy`, `consultation`, `follow-up`) and there is no modality. Add to `appointments`:

| Column | Type | Notes |
|---|---|---|
| `modality` | String(10) NULL | CHECK `modality IS NULL OR modality IN ('video','in_person','audio','chat')` (`ck_appt_modality`). NULL for legacy and for counsellor appointments. Only `video` and `in_person` can qualify a prescription in v1. |
| `consult_started_at` | DateTime NULL | set by the doctor pressing "Start consult" |

Routes (module `routes/provider_rx/consults.py`): `POST /provider/appointments/<id>/start-consult` (verified doctor, own appointment, status `accepted` or `booked`, `date == ist_today()`, modality `video` or `in_person`; sets `consult_started_at` once; audit `consult_start`) and `POST /provider/appointments/<id>/complete-consult` (status to `completed`; audit `consult_complete`; frees the live-slot unique index as completion does today).

Honest limit: `consult_started_at` records the doctor's own action, not proof that a call took place. Call logs are not stored. The doctor UI says: "Starting a consult records that you are seeing this patient now. Only start it while the consult is happening."

`services.prescriptions.consult_eligibility(doctor_id, patient_id, same_condition_attested=False, now=None) -> Eligibility`:
- Qualifying consult `A` = newest appointment with `user_id = patient`, `provider_id = doctor`, `modality IN ('video','in_person')`, `consult_started_at IS NOT NULL`, `status IN ('accepted','booked','completed')`, `consult_started_at >= now - RX_CONSULT_WINDOW_HOURS` (default 24). None gives blocker `no_consult`.
- `tpg_context`: if `A.modality == 'in_person'` then `in_person`. Otherwise look for a prior in-person consult `B` with the same doctor and patient, `modality = 'in_person'`, `status = 'completed'`, `B.id != A.id`, `B.consult_started_at >= now - 183 days` (six months, UNVERIFIED rounding). If found and `same_condition_attested` then `follow_up`, else `first`.
- Allowed TPG lists: `first` gives `{O, A}`; `follow_up` and `in_person` give `{O, A, B}`. List C is never allowed in v1 (3.4).
- Returns `Eligibility(consult_appointment_id, modality, tpg_context, allowed_lists, max_days, blockers: list[str], erx_consent: bool)`. The TPG's patient-identification step at a first consult is met only by the patient being a logged-in account of the same institution (legal list, section 15).

### 3.4 Medicine rules (server side, pure functions in `services/rx_rules.py`)

A medicine is prescribable only if ALL hold: `active`; `list_verified_at IS NOT NULL` (and, when `CATALOGUE_FOUR_EYES` is on, `list_verified_by != updated_by`); `schedule IN ('none','H')`; `is_controlled = false`; `tpg_list IN allowed_lists`; not (`is_demo` while `FLASK_ENV == 'production'` without `ALLOW_DEMO_DATA=1`). Codes and the exact text shown to the doctor:

| Code | Text |
|---|---|
| `medicine_inactive` | "This medicine is no longer in the catalogue." |
| `medicine_unverified` | "The list classification of this medicine has not been confirmed by a second administrator, so it cannot be prescribed yet." |
| `medicine_blocked_c` | "This medicine cannot be prescribed through teleconsultation (Telemedicine Practice Guidelines 2020, List C). See the patient in person and prescribe outside this system." |
| `medicine_controlled` | "This is a Schedule H1, Schedule X or NDPS medicine. It cannot be prescribed in this system." |
| `medicine_needs_followup` | "This is a List B medicine. It can be prescribed at a follow-up consult within 6 months of an in-person consult for the same condition, or at an in-person consult." |
| `medicine_demo_blocked` | "Demo medicine. Not for real prescriptions." |

Limits (section 8): at most `RX_MAX_ITEMS` (default 6) items; `duration_days` at most `RX_MAX_DAYS_FIRST` (default 14) when `tpg_context = first`, else `RX_MAX_DAYS_FOLLOWUP` (default 30). These numbers are product policy for a student-health setting, NOT taken from a regulation (no numeric TPG limit was verified); the clinical lead must confirm them.

Counsellors cannot reach these rules: the routes sit behind `verified_prescriber_required`.

### 3.5 Warnings (duplicate therapy only) and capture of allergies and current medicines

Required at issue: `allergies_status` and `current_meds_status` set explicitly (`unknown` is allowed and printed as "not recorded"; `listed` needs text). `services.prescriptions.warnings(rx) -> list[Warning(code, item_id, text_key)]`:

| Code | Trigger |
|---|---|
| `dup_active_rx` | another unexpired, uncancelled prescription of this patient (any doctor, status `issued` or `partially_dispensed`) holds an item with the same `Medicine.generic_key` |
| `dup_class` | two different medicines with the same non-empty `therapeutic_class`, in this prescription or between an item and an active prescription's item |
| `dup_self_logged` | the generic name (4 characters or more, lower-cased) appears in the name of one of the patient's active self-logged `Medication` rows |
| `allergy_text_match` | the allergy text, lower-cased, contains the generic or brand name of an item (text match only) |
| `current_meds_text_match` | same test against the current-medicines text |

The doctor must acknowledge each code by listing it in `acknowledged_warnings` on the issue call, otherwise 409 `warnings_unacknowledged` with the list. Acknowledged codes go to `warnings_ack` and to audit meta. UI wording shown with every warning block: "This check finds the same medicine or the same class only. It is not a drug interaction check. Check interactions yourself before issuing."

Explicitly NOT built and NOT claimed anywhere in UI copy or docs: drug-drug interaction checking, dose-range checking, contraindication, pregnancy or renal checks. If the owner wants interaction checking: (1) the NLM RxNav interaction API was discontinued on 2 January 2024, so there is no free official feed to wire in; (2) a licensed database must be chosen (India-specific vendors such as CIMS or MIMS, or a commercial DrugBank licence: terms UNVERIFIED); (3) the catalogue needs codes the vendor understands (ATC or RxNorm), a catalogue schema change; (4) a regulatory opinion on whether decision-support software is a medical device (CDSCO, UNVERIFIED); (5) alert-fatigue design with the clinical lead. That is a separate project.

### 3.6 Patient consent to receive an e-prescription

Stored as `ConsentRecord(kind='eprescription', version=ERX_CONSENT_VERSION)` (`kind` is `String(20)` with no CHECK; `CONSENT_KINDS` in `routes/auth.py` is NOT changed, so existing users are not pushed through `/consent`). The patient gives it by:
- a required checkbox on the schedule form when a doctor is selected: "I agree that this doctor may issue me an electronic prescription through MindFull Horizon. The prescription shows my name, the diagnosis the doctor enters and the medicines. I can withdraw this at any time on the prescriptions page."
- or the "Allow e-prescriptions" button on `/patient/my-prescriptions`.

Withdrawal stores `ConsentRecord(kind='eprescription_off', version=...)`, newer than the grant, and deletes nothing already issued; it only blocks new issues (blocker `no_consent`). Consent is active when the newest of the two kinds is the grant at the current version. Audit `erx_consent_give` and `erx_consent_withdraw`. The wording lives in `utils/rx_text.py` (package C) so doctor, patient and print pages share it.

### 3.7 The issue transaction (the only place a prescription becomes real)

`services.prescriptions.issue(doctor_id, rx_id, issue_key, acknowledged) -> IssueResult(prescription, replayed)` runs inside one database transaction in this order. SQLite takes its single write lock at step 2; PostgreSQL row-locks what it reads for update.

1. Idempotent replay: a row with `provider_id = doctor_id` and `issue_request_id = issue_key` is returned with `replayed=True` (HTTP 200). The same prescription already `issued` under a different key gives 409 `already_issued`.
2. CAS claim: `UPDATE prescriptions SET status='issued', issue_request_id=:key, row_version=row_version+1 WHERE id=:id AND provider_id=:doctor AND status='draft' AND row_version=:v`. Zero rows updated: re-read and answer 404 (not yours), 409 `not_draft` or 409 `stale_draft`.
3. `require_verified(doctor_id, lock=True)`; the doctor row has `deactivated_at IS NULL`.
4. Patient exists, `role = 'patient'`, same institution as the doctor, assigned via `ProviderPatient`, active e-prescription consent.
5. `consult_eligibility(...)`; every item passes 3.4 against the SERVER-computed `allowed_lists`; item count and duration limits; at least one item; `diagnosis` non-empty; allergy and current-medicine fields valid.
6. Warnings computed; unacknowledged ones abort with 409.
7. If `amends_id` is set: `UPDATE prescriptions SET status='cancelled', cancel_reason='amended', cancelled_at=:now, cancelled_by=:doctor WHERE id=:old AND status='issued' AND provider_id=:doctor`; zero rows means the old one was dispensed or cancelled meanwhile: abort 409 `amended_rx_changed`.
8. Fill snapshots (`doctor_*`, `patient_name`, `institution_*`, item `medicine_label` and `tpg_list`), `issue_date = utcnow()`, `expiry_date` = end of the IST day (issue IST date + `expiry_days`) via `utils.timeutil.ist_day_bounds`, `tpg_context`, `consent_version`, `warnings_ack`, `number = new_number()`.
9. `audit(..., 'rx_issue', ...)` and commit.

Any failure in steps 3 to 7 rolls the transaction back (the draft stays a draft) and writes an `rx_issue_blocked` audit row with the code, in a separate short transaction. `expiry_days` is chosen by the doctor from 1 up to `RX_EXPIRY_DAYS` (default 30, hard maximum 90): shorten, never extend.

`new_number(now)`: `RX{YYMM in IST}-{10 random chars}{check}`. Alphabet `0123456789ABCDEFGHJKMNPQRSTVWXYZ` (Crockford, no I L O U), body from `secrets.choice`, check character `ALPHABET[sum((i + 1) * ALPHABET.index(c) for i, c in enumerate(body)) % 32]` so the desk catches typing errors before a lookup. Example shape `RX2611-7K3M9QX4PD2`. Uniqueness is the UNIQUE index on `number`; on `IntegrityError` roll back and retry the whole `issue()` up to 3 times (no SAVEPOINT: `utils/jobs.py` documents that pysqlite's SAVEPOINT handling can commit the caller's transaction). Random numbers leave no gaps to audit; sequential numbering, if a regulator wants it, is a later change (requirement UNVERIFIED).

### 3.8 Cancel, amend, expiry, dispensing blocks

- Cancel: `cancel(actor_id, rx_id, reason_code)`. CAS `UPDATE ... SET status='cancelled' ... WHERE id=:id AND provider_id=:actor AND status IN ('issued','partially_dispensed')`. On `partially_dispensed` only the undispensed remainder is cancelled; dispensed quantities and the ledger stay. Reasons: `error`, `patient_request`, `clinical_change`, `amended`, `system`. Cancelled prescriptions cannot be dispensed (the dispense CAS checks status).
- Amend: `amend(doctor_id, rx_id) -> Prescription(draft)` copies patient, items and fields into a NEW draft with `amends_id = old.id`. The old one stays `issued` until the new one is issued (step 7). Deleting the amending draft leaves the old one untouched.
- Immutability: no route or service updates items or clinical fields after `issued`. Allowed updates after issue: `status`, `quantity_dispensed` (dispensing only), `cancel*`, `dispense_requested_at`, `updated_at`. A behavioural test sends `PUT` on an issued prescription (409 `not_draft`).
- Expiry: `effective_status(rx, now)` returns `expired` for `issued` or `partially_dispensed` rows whose `expiry_date <= now`, so correctness never depends on a job. The nightly job (4.10) persists `status='expired'`. Expired prescriptions cannot be dispensed or amended.
- Suspended prescriber: issued prescriptions stay valid in the database, but dispensing is blocked while the prescriber's profile status is `suspended` or `rejected` (409 `prescriber_not_verified` from the dispense service). A lapsed review date alone does NOT block dispensing of prescriptions issued while valid. The patient detail shows "This prescription cannot be dispensed right now. Contact your institution's pharmacy desk."

### 3.9 Printable prescription, public status check, account deletion, export

- `templates/provider_rx/print.html` (package B), reached from `provider.rx_print`, `rx_patient.print` and `admin.dispensing_print`, renders from the snapshot columns only: institution name, doctor name, "Reg. No. {doctor_reg_no}, {doctor_council}", specialisation, issue date and time in IST, valid-until date, prescription number (also on a monospaced line to read aloud), patient name, diagnosis, allergies and current medicines (or "not recorded"), the items table (generic name in capitals, dose, frequency, duration, quantity, instructions), and the footer: "Issued electronically through MindFull Horizon after a consultation on {date}. This document has no handwritten or digital signature. Check its status at {site_url}/rx/{number}." Cancelled and expired prescriptions print with a large CANCELLED or EXPIRED banner. A print stylesheet hides navigation. Whether an unsigned electronic prescription is accepted by a pharmacy outside the institution is a legal question (the psychiatry guidance asks for a digital signature on digital prescriptions: Secondary, section 15).
- Public status check `GET /rx/<number>` (blueprint `rx_patient`, no login, limiter `30 per minute`): validates the check character first, then returns only `status` (`valid`, `partially_dispensed`, `dispensed`, `cancelled`, `expired`), issue date, `doctor_name`, `doctor_reg_no` and institution name. No patient data, no items. Unknown or malformed numbers return the same 404 page.
- Patient account deletion cascades to their prescriptions (existing behaviour). The ledger references items with `ON DELETE SET NULL` and keeps a copy of `rx_number`, so stock history survives. The privacy page must say this (request to the lead for `routes/pages.py`). Retention law may require keeping prescriptions: section 15.
- A doctor with any prescription cannot be hard-deleted (RESTRICT). `routes/auth.py::account_delete` (package A) handles this before deleting: for a doctor with prescriptions it sets `deactivated_at`, clears the session and shows "Your account was deactivated, not deleted, because prescriptions you issued must be kept. Contact your institution administrator." It refuses `role = 'admin'` (operator uses the CLI).
- `routes/auth.py::_EXPORT` gains `prescription_items` (through `Prescription.patient_id`), so the patient's data export includes the items and the snapshot fields.

## 4. Medicine inventory

### 4.1 Tables

`medicines` (`Medicine`), the catalogue, shared by all institutions:

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `generic_name` | String(120) NOT NULL | as entered; printed in capitals |
| `generic_key` | String(120) NOT NULL | lower-case, collapsed spaces; used for search, duplicates and uniqueness |
| `brand_name` | String(120) NOT NULL default `''` | empty string, not NULL, so the unique constraint works on SQLite and PostgreSQL |
| `strength` | String(40) NOT NULL | for example `10 mg` |
| `form` | String(30) NOT NULL | tablet, capsule, syrup, injection, ... free text from the CSV, trimmed |
| `route` | String(20) NOT NULL default `oral` | |
| `tpg_list` | String(1) NOT NULL | CHECK `tpg_list IN ('O','A','B','C')` (`ck_med_list`). Unknown at import means `C`. |
| `schedule` | String(8) NOT NULL default `none` | CHECK `schedule IN ('none','H','H1','X','NDPS')` (`ck_med_schedule`) |
| `is_controlled` | Boolean NOT NULL default false | CHECK `schedule NOT IN ('X','NDPS') OR is_controlled` (`ck_med_controlled`) |
| `therapeutic_class` | String(60) NULL | admin-entered, for the duplicate-class warning only |
| `active` | Boolean NOT NULL default true | deactivate instead of delete |
| `is_demo` | Boolean NOT NULL default false | set only by `scripts/seed_demo.py` |
| `list_verified_at`, `list_verified_by` | DateTime NULL; FK users SET NULL | the four-eyes confirmation of `tpg_list`, `schedule`, `is_controlled` |
| `created_by`, `updated_by` | FK users SET NULL | `updated_by` is the last admin to change any classification field |
| `created_at`, `updated_at` | DateTime | |

UNIQUE `uq_medicine_identity (generic_key, brand_name, strength, form)`. Editing `tpg_list`, `schedule` or `is_controlled` sets `list_verified_at = NULL` and `updated_by = editor`; the medicine is unprescribable until a DIFFERENT admin (`list_verified_by != updated_by` when `CATALOGUE_FOUR_EYES=1`, the default) confirms on the catalogue screen. A single-admin pilot can set `CATALOGUE_FOUR_EYES=0` and accepts the risk; the screen then shows a standing banner "Four-eyes check is off". Audit records changed field names, never values of free text.

`inventory_batches` (`InventoryBatch`):

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `institution_key` | String(100) NOT NULL, indexed | |
| `medicine_id` | FK `medicines.id` ON DELETE RESTRICT | |
| `batch_no` | String(40) NOT NULL | |
| `expiry_date` | Date NOT NULL | ISO date only |
| `quantity_on_hand` | Integer NOT NULL default 0 | CHECK `quantity_on_hand >= 0` (`ck_batch_qty`), the database-level oversell guard |
| `unit_cost` | Numeric(10,2) NULL | optional, informational |
| `supplier` | String(120) NULL | |
| `status` | String(12) NOT NULL default `active` | CHECK `active, quarantined, closed` (`ck_batch_status`). `quarantined` batches are skipped by allocation (recall). `closed` is set when an expired batch is written off to zero. |
| `received_at`, `updated_at` | DateTime | |

UNIQUE `uq_batch_identity (institution_key, medicine_id, batch_no, expiry_date)`. Index `idx_batch_fefo (institution_key, medicine_id, status, expiry_date)`.

`inventory_transactions` (`InventoryTransaction`), the append-only ledger:

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `batch_id` | FK `inventory_batches.id` ON DELETE RESTRICT, NOT NULL, indexed | |
| `delta` | Integer NOT NULL | signed units |
| `kind` | String(10) NOT NULL | CHECK `receive, dispense, adjust, expire, return` |
| CHECK `ck_invtx_sign` | | `(kind IN ('receive','return') AND delta > 0) OR (kind IN ('dispense','expire') AND delta < 0) OR (kind = 'adjust' AND delta <> 0)` |
| `prescription_item_id` | FK `prescription_items.id` ON DELETE SET NULL, NULL | |
| `rx_number` | String(24) NULL | copy of the prescription number, survives item deletion |
| `actor_id` | FK `users.id` ON DELETE SET NULL, NULL | |
| `reason_code` | String(24) NOT NULL | CHECK in `purchase, donation, transfer_in, opening_stock, dispense, dispense_reversed, count_correction, damaged, lost, recalled, expired_writeoff` (`ck_invtx_reason`). `receive` takes the first four, `dispense` takes `dispense`, `return` takes `dispense_reversed`, `adjust` takes `count_correction, damaged, lost, recalled`, `expire` takes `expired_writeoff`; the service rejects other pairings. |
| `group_ref` | String(36) NULL, indexed | groups the lines of one dispense confirm |
| `reverses_id` | FK `inventory_transactions.id` NULL, UNIQUE | a dispense line can be reversed once |
| `dispenser_label` | String(140) NULL | the pharmacist's name and registration number typed at the desk (professional data, not patient data) |
| `idempotency_key` | String(80) NOT NULL UNIQUE | |
| `created_at` | DateTime NOT NULL, indexed | |

No service or route updates or deletes a ledger row (a test searches `routes/` and `services/` for `InventoryTransaction` with `.update(` or `.delete(`). `quantity_on_hand` of a batch always equals the sum of its ledger deltas. Both change in the same transaction; the "opening" row of a new batch is a `receive` line. `services.inventory.reconcile(institution_key) -> list[Mismatch]` compares them, is run by a test and by the nightly job, and ONLY reports (an alert to admins), it never auto-fixes.

`reorder_rules` (`ReorderRule`): `id`, `institution_key`, `medicine_id` FK RESTRICT, `reorder_level` Integer NOT NULL CHECK `>= 0`, `updated_by`, `updated_at`; UNIQUE `(institution_key, medicine_id)`.

### 4.2 Usable stock, FEFO, expiry

- Today is `utils.timeutil.ist_today()`. A batch is USABLE when `status = 'active'` and `expiry_date > ist_today() + INVENTORY_MIN_SHELF_DAYS` (default 0). Conservative: stock is not used ON its expiry date.
- FEFO allocation order: `ORDER BY expiry_date ASC, id ASC` over usable batches with `quantity_on_hand > 0` for the prescription's institution and the item's medicine. Take from the earliest-expiring batch first, spill into the next.
- Expired stock is never dispensed: the selection excludes it, and the batch compare-and-set update (4.3) repeats the expiry condition, so a batch that expires between prepare and confirm fails the update.
- Expired stock stays in `quantity_on_hand` until the pharmacy desk writes it off (`kind = 'expire'`, `reason_code = 'expired_writeoff'`, one ledger line per batch, batch set `closed` at zero). The report "Expired, awaiting write-off" lists them. The job only alerts; it does not write off by itself (a write-off is a stock-loss decision for a person).

### 4.3 Atomic decrement, concurrency

Every decrement is a compare-and-set `UPDATE`, identical on SQLite and PostgreSQL, so correctness never depends on isolation level:

```sql
UPDATE inventory_batches
   SET quantity_on_hand = quantity_on_hand - :n, updated_at = :now
 WHERE id = :batch_id AND institution_key = :inst AND status = 'active'
   AND expiry_date > :cutoff AND quantity_on_hand >= :n;
-- rowcount must be 1, otherwise the whole transaction rolls back with 409 plan_stale
```

- PostgreSQL additionally takes row locks in a fixed order before updating, to prevent deadlocks between two desks: lock the prescription row, then its items `ORDER BY id`, then the candidate batches `ORDER BY id` (`with_for_update()`); the compare-and-set update still runs.
- SQLite has one writer at a time; the compare-and-set update alone is the guard. Tests run on SQLite, so the concurrency tests use two threads with separate sessions against a file database (there is a temp file DB in `tests/conftest.py`) plus a deterministic "stale plan" test; a PostgreSQL run is a CI job once CI exists.
- `CHECK (quantity_on_hand >= 0)` and `CHECK (quantity_dispensed <= quantity)` turn any logic bug that slips past the compare-and-set into an `IntegrityError` and a rollback, never into negative stock.

### 4.4 Availability at prescribing time (no reservation)

Decision (C-07): NO reservation at issue. Reasons: a prescription is valid for up to 30 days and patients may collect part, late or elsewhere; reservations would lock stock for people who never come, need a release job and a per-prescription quantity ledger, and add a second state that can disagree with the real shelf. The cost: a patient may arrive and find stock gone; the pharmacy desk then dispenses partially (4.6) and the prescription stays `partially_dispensed` until expiry.

`services.inventory.availability(institution_key, requests: list[tuple[int, int]]) -> dict[int, dict]` where `requests` are `(medicine_id, quantity)` pairs (quantity 0 or omitted at search time). Returns `{medicine_id: {"status": "in_stock"|"low"|"out", "on_hand": int}}` with `on_hand` = the sum of USABLE batches. `out` when `on_hand == 0`; `low` when `0 < on_hand < quantity` or `on_hand <= reorder_level` (when a rule exists); else `in_stock`. Providers receive `status` only (the route strips `on_hand`); admins receive both. The prescribe screen shows: "In stock at your pharmacy desk", "Low stock", "Out of stock" with the line "Availability is a guide. Stock is not held for this prescription." Out of stock does not block issuing (the patient may buy elsewhere).

### 4.5 Receiving, adjusting, writing off (pharmacy desk only)

`services/inventory.py` (owner A), all take `institution_key` from the admin's DB row, all write ledger plus batch in one transaction and one `audit` row, all require an `idempotency_key` (the route derives it from the `Idempotency-Key` header, required):

```python
def receive(institution_key, medicine_id, batch_no, expiry_date, quantity, actor_id, idem_key,
            unit_cost=None, supplier=None, reason_code='purchase') -> InventoryTransaction
def adjust(batch_id, delta, reason_code, actor_id, idem_key) -> InventoryTransaction     # reason required; result must stay >= 0
def write_off_expired(batch_id, actor_id, idem_key) -> InventoryTransaction              # only when expiry_date <= today; delta = -quantity_on_hand
def set_quarantine(batch_id, on: bool, actor_id) -> InventoryBatch                       # recall handling; audited
def set_reorder_level(institution_key, medicine_id, level, actor_id) -> ReorderRule
def availability(...)                                                                    # 4.4
def stock_levels(institution_key, q=None, status=None, page=1, per_page=20) -> (rows, meta)
def reconcile(institution_key) -> list
```

`receive` rules: medicine exists, `active`, `schedule IN ('none','H')` and not controlled (else 422 `controlled_not_stocked`); `expiry_date > ist_today() + INVENTORY_MIN_SHELF_DAYS` (else 422 `already_expired`); quantity 1 to 100000; `unit_cost >= 0`; an existing batch with the same identity is topped up, otherwise created with `INSERT ... ON CONFLICT DO NOTHING` (the dialect pattern in `utils/jobs._insert_ignore`, to avoid SAVEPOINT) then incremented. `adjust` rejects a delta that would drive the batch below zero (422 `would_go_negative`) and requires one of the four adjust reason codes. Receiving a batch in which the medicine's classification is unverified is allowed (stock can arrive before the list is confirmed); prescribing is what is blocked.

### 4.6 Dispensing: two-step confirm by the pharmacy desk

Only `pharmacy_desk_required` routes. The desk finds a prescription by:
- typing the prescription number (check character validated first; `30 per minute` limiter; unknown numbers return the same 404; audit `rx_lookup_desk` via `number`), or
- the QUEUE of prescriptions of its institution where the patient pressed "send to pharmacy desk" (`dispense_requested_at IS NOT NULL`, status `issued` or `partially_dispensed`, unexpired). The queue row shows the prescription number, the patient's initials only (first letters of first and last name), the item count, and the request time. Opening a queue row shows the full prescription (audit via `queue`). There is deliberately no list of all prescriptions.

Step 1, prepare: `services.dispensing.plan(rx_id, institution_key, actor_id, lines=None) -> Plan`. Nothing is written. For each requested line (default: every item with remaining quantity; the desk may lower a quantity or drop a line, never raise above remaining) it runs FEFO allocation over usable stock. `Plan` = `{rx: {...}, lines: [{item_id, medicine_label, remaining, requested, allocations: [{batch_id, batch_no, expiry_date, quantity}], shortfall}], warnings: [], token}`. `token` is `itsdangerous.URLSafeTimedSerializer(SECRET_KEY, salt='rx-dispense-plan').dumps({'rx': id, 'inst': key, 'actor': id, 'rv': prescription.updated_at.isoformat(), 'lines': [[item_id, [[batch_id, qty], ...]], ...]})`, valid 600 seconds, bound to the actor and institution. A plan with a shortfall is allowed (partial dispensing); a plan with zero total quantity is not (422 `nothing_to_dispense`). Warnings: prescriber suspended (blocks, 4.6 confirm), prescription cancelled or expired (blocks), "stock short for line N".

Step 2, confirm: `services.dispensing.confirm(rx_id, institution_key, actor_id, token, idem_key, identity_checked, pharmacist_name, pharmacist_reg_no) -> DispenseResult`. Requirements: `identity_checked` true (the screen text: "I have checked the patient's identity and the prescription number"), pharmacist name 3 to 100 characters and registration number 3 to 40 characters (`dispenser_label = "name, Reg. registration"`, a professional label, legal basis UNVERIFIED, section 15), the `Idempotency-Key` header (required). Single transaction, in this order:

1. Replay: `group = sha256(f"{rx_id}:{idem_key}").hexdigest()[:32]`. If any ledger row has `group_ref = group`, return the stored result with HTTP 200 (`replayed: true`).
2. Verify the token (signature, age, actor, institution, `rx`), reload the prescription. If `updated_at` differs from `rv` or the plan cannot be applied unchanged, answer 409 `plan_stale` with a fresh plan in the body (the desk reviews it and confirms again with a NEW key).
3. Claim the prescription: `UPDATE prescriptions SET updated_at = :now WHERE id = :id AND institution_key = :inst AND status IN ('issued','partially_dispensed') AND expiry_date > :now`; zero rows gives 409 `rx_not_dispensable` (cancelled, expired, dispensed or foreign institution). This also serialises two desks working on the same prescription.
4. Prescriber check: profile `status` must not be `suspended` or `rejected` (409 `prescriber_not_verified`).
5. For each plan line: `UPDATE prescription_items SET quantity_dispensed = quantity_dispensed + :n WHERE id = :item AND prescription_id = :id AND quantity_dispensed + :n <= quantity` (zero rows is `plan_stale`).
6. For each allocation: the batch compare-and-set of 4.3 and one ledger row `kind='dispense'`, `delta = -n`, `reason_code='dispense'`, `idempotency_key = f"{group}:{item_id}:{batch_id}"`, `group_ref = group`, `rx_number`, `actor_id`, `dispenser_label`.
7. Status: if no item has remaining quantity then `dispensed`, else `partially_dispensed`: `UPDATE prescriptions SET status = :s WHERE id = :id AND status IN ('issued','partially_dispensed')`.
8. `audit(... 'rx_dispense' ...)`, commit. An `IntegrityError` on the idempotency key (a double click that raced past step 1) rolls back, then step 1 is run again and returns the first result.

If the pharmacist selects "dispense later" the plan simply expires; nothing was written. The patient detail page maps item state to words: not collected (0 dispensed), partly collected (`3 of 10 tablets`), collected.

### 4.7 Reversal (the only "return")

A patient returning medicine is NOT restocked (returned medicines are not put back on the shelf: policy choice, pharmacist to confirm, section 15). The ledger `return` kind exists only to undo a desk error: `services.dispensing.reverse(tx_id, actor_id, idem_key) -> InventoryTransaction`, allowed when the original line is `kind = 'dispense'`, not already reversed (UNIQUE `reverses_id`), within 24 hours of `created_at`, and in the desk's institution. In one transaction: a `return` ledger row (`delta = +n`, `reason_code = 'dispense_reversed'`, `reverses_id = tx_id`), the batch is increased (`quantity_on_hand = quantity_on_hand + n`), the item CAS `quantity_dispensed = quantity_dispensed - n WHERE quantity_dispensed >= n`, and the prescription status is recomputed (`dispensed` back to `partially_dispensed` or `issued`) only if it is currently `dispensed` or `partially_dispensed`. A cancelled or expired prescription keeps its status. Audit `rx_dispense_reverse`. Any other correction (damage, loss, count error) is an `adjust` with a reason code.

### 4.8 Controlled substances

Not stocked and not prescribed in this version. `schedule IN ('H1','X','NDPS')` or `is_controlled` medicines may exist in the catalogue (so a doctor searching sees "cannot be prescribed in this system"), but `receive` rejects them and `issue` rejects them. This removes the need for the Schedule H1 register and NDPS forms (research file section 3). Enabling controlled medicines later is a separate legal project.

### 4.9 CSV import and export

Routes in `routes/admin/catalogue.py` and `routes/admin/inventory.py`; logic in `services/inventory_csv.py` (owner A). Template downloads are static strings generated by the service (no clinical rows).

Catalogue template `medicines_template.csv` (header only, one comment row is NOT allowed):

```
generic_name,brand_name,strength,form,route,tpg_list,schedule,therapeutic_class,active
```

Stock template `stock_template.csv`:

```
generic_name,brand_name,strength,form,batch_no,expiry_date,quantity,unit_cost,supplier
```

Rules (both imports): UTF-8 (BOM tolerated), comma separated, header required and exact, at most 2000 rows and 1 MB (`MAX_CONTENT_LENGTH` for that route via `request.content_length` check), `dry_run=1` returns per-row errors and counts and writes nothing; a real run is ALL OR NOTHING (any row error rejects the file, with row numbers and codes, no free text echo of cell values longer than 40 characters). `expiry_date` must be ISO `YYYY-MM-DD` (month-only dates are rejected: ambiguous). `quantity` positive integer. Catalogue import upserts by the identity tuple, sets `list_verified_at = NULL` for new rows and for any row whose classification changed (so an import can never silently make a medicine prescribable), sets `tpg_list = 'C'` when the cell is empty, never sets `is_demo`. Stock import matches rows to catalogue entries by the identity tuple (unknown medicine is a row error), refuses controlled medicines, and writes `receive` ledger lines with `idempotency_key = f"imp:{sha256(file bytes + institution_key).hexdigest()[:16]}:{row_no}"`, so re-uploading the same file fails with `import_duplicate` instead of doubling stock. Audit `stock_import` with the row count.

Exports (`GET /admin/catalogue.csv`, `GET /admin/inventory/stock.csv`, report CSVs): same column order as the templates plus read-only columns after them; every cell that starts with `=`, `+`, `-` or `@` is prefixed with a single quote (spreadsheet formula injection); `Content-Disposition: attachment`, `Cache-Control: no-store`; audit `export_stock_csv`. Exports never contain patient data (the dispensing log CSV carries the masked prescription number for base admins).

### 4.10 Jobs (existing queue in `utils/jobs.py`)

One recurring job kind `ops_daily`, registered with `@register('ops_daily')` in `services/ops_jobs.py`; `utils.jobs._load_handlers` gets one import line (`import services.ops_jobs  # noqa: F401`). There is no scheduler in the queue, so the handler re-enqueues itself at the end: `enqueue('ops_daily', {}, idempotency_key=f'ops_daily:{next_ist_date}', run_at=<06:00 IST of the next day as naive UTC>)`. The first run is seeded by `ensure_ops_daily_scheduled()` (an idempotent enqueue for today's key), called from `flask ops-daily-schedule` (CLI), at the end of `init_jobs` start-up when the in-process worker starts, and when an admin opens the dashboard. If the worker was down, the next run catches up because every step is state-based and idempotent. The handler does, for every institution that has stock rows or doctors:
1. `expire_due_prescriptions(now)`: persist `status = 'expired'` for `issued` and `partially_dispensed` rows with `expiry_date <= now`.
2. `inventory_alerts(institution_key)`: counts of (a) medicines with a reorder rule whose usable stock is at or below the level (`low`), (b) usable stock zero with a rule (`out`), (c) batches with stock expiring within `INVENTORY_NEAR_EXPIRY_DAYS` (default 60) and still usable (`near_expiry`), (d) expired batches still holding stock (`awaiting_writeoff`). If any count is non-zero it creates ONE `Notification(recipient_id=admin.id, type='inventory_alert', payload={...counts...}, message=<fixed sentence with the counts>)` per admin with the desk flag per IST day (dedupe by a payload `date` field, the same pattern as `utils/crisis._notify`). Counts only, no medicine names in the message.
3. `reconcile(institution_key)`: any mismatch creates a Notification `inventory_mismatch` and a `logger.error` line with the batch id only.
4. `prescriber_review_alerts(institution_key)`: profiles whose `review_due_at` is within 30 days or past: one Notification `prescriber_review_due` per admin per day with the count.
Handlers raise on DB errors (the queue retries with backoff); `last_error` carries the exception class name only.

### 4.11 Reports (`services/reports.py`)

All aggregate. None shows a patient name. All accept `institution_key` from the admin's row, support CSV via the same function with `fmt='csv'`.

| Report | Columns | Visible to |
|---|---|---|
| Stock on hand | medicine label, usable on hand, expired on hand (awaiting write-off), reorder level, status in_stock/low/out | admin, desk |
| Expiring in N days (default 60, 1 to 365) | medicine label, batch no, expiry date, quantity, days left | admin, desk |
| Dispensing log (date range in IST, `ist_day_bounds`, default last 7 days, paginated) | time (IST), kind, masked prescription number (full for desk), medicine label, batch no, delta, dispenser label (desk only), reason code | admin (masked), desk (full) |
| Usage by medicine (month range) | medicine label, units dispensed (dispense minus reversals), distinct prescriptions, `suppressed` flag. A row whose distinct patients is below K shows `units = null` and `suppressed = true`. | admin, desk |

`mask_rx(number) = number[:7] + '*' * 8 + number[-3:]`. The dispensing log still pairs a pseudonymous number with a medicine for anyone who has the log; that is why base admins get the masked number and the full log is a desk function (stated honestly in the UI: "Prescription numbers are shown in part for administrators").

### 4.12 Catalogue operations

Routes for catalogue management are admin routes (any admin, desk not required): list with filters (`q`, `list`, `verified`, `active`), create, edit, deactivate, verify classification. A medicine with stock cannot be deleted (no delete route exists; deactivation only). Deactivating a medicine blocks new prescribing; existing issued prescriptions keep their item snapshot and can still be dispensed (the dispense service checks stock and prescription state, not `active`). The catalogue screen shows "Needs second check" for unverified classification and disables the verify button for the admin who last edited it.

## 5. Dashboards, routes and APIs

Three dashboards, built from the components in `docs/DESIGN_SYSTEM.md` (`.card`, `.stat`, `.table` in `.table-wrap`, `.badge`, `.alert`, `.empty-state`, `.tabs`, `.btn`, `MFH.confirm`, `MFH.toast`, icons from the sprite: `pill`, `file`, `users`, `shield`, `clock`, `alert`, `download`, `search`, `plus`, `check`, `x`, `edit`, `eye`). No emoji, no gradients, numbers only from the database or `n/a`.

### 5.1 Conventions for every new endpoint

- JSON success: `{"success": true, ...payload}`. JSON error: `{"success": false, "error": "<code>", "message": "<safe text from the code table>", "fields": {"<field>": "<message>"}}` (`fields` only for validation errors). Messages come from a fixed table in `services/errors.py`; `str(e)` and exception text never reach a client. Status codes: 400 malformed, 401 not logged in, 403 role, 404 not found or out of scope, 409 state conflict, 422 validation, 429 limiter.
- Lists: `?page=` and `?per_page=` through `utils/pagination.page_args` and `paginate`; response `{"success": true, "items": [...], "meta": {"page", "per_page", "total", "has_next"}}`. Offset paging is used (docs/DESIGN.md allows it for small tables; these tables are per institution and per doctor). The dispensing log and audit viewer are the only ones that can grow: they require a date range (default 7 days, maximum 92) so a page is always bounded.
- State-changing JSON calls send `X-CSRFToken` (from `meta[name="csrf-token"]`, as `static/js/shell.js` does) and `Content-Type: application/json`. Calls marked IDEM require an `Idempotency-Key` header matching `^[A-Za-z0-9._-]{8,64}$` (`utils/idempotency.KEY_RE`); a missing or malformed key is 400 `idempotency_key_required`. The browser creates the key with `crypto.randomUUID()` when the screen or form is opened and re-sends the SAME key on retry.
- Times in JSON are ISO 8601 UTC strings with `Z` (stored values are naive UTC); every screen formats them to IST (`Asia/Kolkata`) in the browser, and server-rendered pages use a Jinja filter `ist` (package A adds it in `routes/provider_rx/__init__.py` via `app_template_filter`). "Today" and date ranges use `utils.timeutil.ist_day_bounds`.
- Every route has `@login_required` plus a role decorator (1.5), and `@prescriptions_required` first for prescribing, patient prescription and desk routes (flag, section 13). Patient ids in the URL are checked with `scoped_patient_or_404`. Rate limits (flask-limiter, existing `limiter`): medicine search `60 per minute`, desk lookup `30 per minute`, issue `20 per minute`, CSV import `10 per hour`, `/admin/login` `5 per minute`, `/rx/<number>` `30 per minute`.
- File size: every new Python module under 300 lines. Existing oversized files (`routes/patient.py`, `routes/provider.py`, `app.py`) are not grown beyond one-line hooks; new code goes in the modules named below.

### 5.2 Patient dashboard (existing blueprint `patient`; new blueprint `rx_patient` in `routes/rx_patient.py`)

Existing screens stay (dashboard, assessments, chat, schedule, journal, goals, progress, breathing, yoga, music, medications, profile, account data). Changes and additions (package C):

| Screen | URL, endpoint | Content |
|---|---|---|
| Dashboard widget "Prescriptions" (only when `prescriptions_enabled`) | `/patient/dashboard`, `patient.patient_dashboard` | Stat "Active prescriptions" (count of `issued` or `partially_dispensed`, unexpired), note "Next expires {date}"; link to the list. Empty state: "No prescriptions yet. A doctor you have seen through MindFull Horizon can send one here." |
| Dashboard card "Your care team" | same | Assigned staff (name, "Counsellor" or "Doctor") from `ProviderPatient`; line "These people can see the information you share on this service." Empty: "You have not booked with anyone yet." |
| Prescriptions list | `/patient/my-prescriptions`, `patient.my_prescriptions` (existing endpoint kept) | Consent banner: if no active e-prescription consent, `.alert-info` "Allow e-prescriptions so a doctor can send you a prescription here" with button "Allow e-prescriptions"; if active, text "You have allowed e-prescriptions" and a link-style button "Withdraw". Tabs "Active" and "Past" (past = dispensed, cancelled, expired, legacy). Each card: prescription number, doctor name, issue date, status badge, valid-until date, collection status ("Not collected", "Partly collected", "Collected"), buttons "Details", "Print", "Send to pharmacy desk". Empty (Active): "No active prescriptions." Empty (Past): "No past prescriptions." Legacy rows show a warning badge "Issued before doctor verification existed. Ask your doctor to issue it again." and no print or desk button. Feature flag off: the existing "not available" page. |
| Prescription detail | `/patient/prescriptions/<id>`, `rx_patient.detail` | Header (number, status badge, doctor name, "Reg. No. ...", institution, issue and valid-until dates), diagnosis, allergies and current medicines as entered, items table (medicine, dose, frequency, duration, quantity, "collected X of Y" per row, instructions), status steps (Issued, Sent to desk, Partly collected, Collected), blocker notice when the prescriber is suspended (3.8), buttons Print, Send to pharmacy desk (hidden once sent; shows "Sent on {date}"), Back. |
| Print | `/patient/prescriptions/<id>/print`, `rx_patient.print` | `provider_rx/print.html` (3.9). |
| Public status check | `/rx/<number>`, `rx_patient.status` | 3.9. |
| Schedule form | `/patient/schedule`, `patient.schedule_appointment` | Lists `bookable_staff`; when a doctor is chosen shows `modality` (Video or In person) and the e-prescription consent checkbox (3.6). |

JSON for these pages (all `@patient_required`, `@prescriptions_required`, filtered by the session user):

| Method and URL | Endpoint | Notes |
|---|---|---|
| `GET /patient/api/prescriptions?status=active|past&page=` | `rx_patient.api_list` | list of PatientRx, 10 per page default |
| `POST /patient/api/prescriptions/<id>/request-pharmacy` | `rx_patient.request_pharmacy` | IDEM. Sets `dispense_requested_at` once; replays return 200; 409 `not_sendable` when cancelled, expired, dispensed. Audit `rx_send_to_desk`. |
| `POST /patient/api/prescriptions/consent` | `rx_patient.consent` | body `{"consent": true|false}`; IDEM not required (idempotent by design); writes the `ConsentRecord` kinds of 3.6. |

PatientRx shape: `{"id", "number", "status", "effective_status", "doctor_name", "doctor_reg_no", "institution", "issued_at", "valid_until", "dispense_requested_at", "collection": "none|partial|complete", "dispensable": bool, "items": [{"medicine_label","dose_text","frequency","duration_days","quantity","quantity_dispensed","instructions"}]}`. Never includes `warnings_ack`, `notes`, other patients or the doctor's internal ids.

Service functions C calls (package A provides, section 14): `services.prescriptions.list_for_patient(patient_id, bucket, page, per_page)`, `get_for_patient(patient_id, rx_id)`, `request_pharmacy(patient_id, rx_id, now=None)`, `services.consent.erx_status(patient_id) -> {"active": bool, "version": str}`, `set_erx_consent(patient_id, on: bool)`.

### 5.3 Provider dashboard (existing blueprint `provider`; one dashboard for counsellors and doctors)

Existing screens stay: dashboard (crisis panel, caseload, appointments, institution summary with K = 5), appointments, analytics, patient wellness report, telehealth, AI documentation. Changes:

**For every provider (package C, files `routes/provider.py`, `templates/wellness_report.html`, new `routes/provider_meds.py`):**
- The old "Send prescription" form and the route `provider.send_prescription` are REMOVED (section 12 lists the tests that change). `/provider/send_prescription/<id>` now returns 404 for everyone, with the flag on or off.
- Patient wellness report gains a read-only "Medications" panel: the patient's active self-logged medicines and the item lines of the patient's active prescriptions (medicine, dose, frequency, duration, status, prescribed by name). Source `GET /provider/api/patients/<id>/medications` (`provider_meds.api_list`, `@provider_required`, `scoped_patient_or_404`, audit `view_patient_meds`). It never shows diagnosis or allergies. Empty: "No medicines recorded for this patient." Help text: "Medicines are listed so you can take them into account. Only a verified doctor can change a prescription."
- The caseload table gets a small badge "Rx" on patients with an active prescription (one batched query `services.prescriptions.active_rx_patient_ids(patient_ids)`).
- Appointment rows show the modality badge when set.
- Nav: nothing new for counsellors. Counsellors never see a prescribing link, button or section; their requests to prescribing URLs return 404.

**"Prescribing" section, only for `provider_type = 'doctor'` (package B templates and JS, package A routes):** it is a section of the SAME dashboard, rendered by `templates/provider_rx/_dashboard_section.html`, included once by `provider_dashboard.html` as `{% if rx_section %}{% include 'provider_rx/_dashboard_section.html' %}{% endif %}`. `rx_section` is injected for provider sessions by a context processor in `routes/provider_rx/__init__.py`: `{"show": bool, "state": "pending|verified|rejected|suspended|lapsed", "review_due_at": iso|None}`; it is falsy for counsellors, patients and admins. Data for the widgets comes from one JSON call.

| Widget | Source (`GET /provider/api/rx/dashboard`) | Empty state and actions |
|---|---|---|
| Verification banner (always shown to doctors) | `state`, `review_due_at` | pending: "Your registration is waiting for an administrator to check it. You cannot prescribe yet." with link "Prescribing profile"; rejected: "Your registration was not accepted. Check the details and send them again." (reason shown only as "see your administrator"); suspended: "Prescribing is switched off for your account. Contact your administrator."; lapsed: "Your registration check has expired. An administrator needs to check it again."; verified: small text "Verified until {date}" |
| "New prescription" button | | disabled with a reason unless `state = verified` |
| Consults today | `consults_today: [{appointment_id, time, patient_name, modality, status, started, can_start, can_complete}]` (own appointments, `ist_today()`, patient names allowed: assigned patients) | "No consults today." Buttons "Start consult" (POST `provider.consult_start`) and "Complete" (POST `provider.consult_complete`); each with `MFH.confirm` |
| Drafts | `drafts: [{id, patient_name, updated_at, items}]` (max 5) and `drafts_total` | "No drafts." Links Continue (`provider.rx_prescribe?draft_id=`), Delete (confirm) |
| Recently issued | `recent: [{id, number, patient_name, status, issued_at}]` (max 5) | "You have not issued a prescription yet." Link "All prescriptions" |
| Awaiting collection | `awaiting_collection`: count of own `issued` prescriptions, unexpired, issued more than 7 days ago, nothing dispensed | hidden when 0 |

**Prescribing screens (all behind `@verified_prescriber_required` except the profile):**

1. Prescribe `/provider/prescribe?patient_id=<id>&draft_id=<id>`, endpoint `provider.rx_prescribe`, template `provider_rx/prescribe.html`. One page, five steps with a step indicator, state kept in JS and the draft saved on the server.
   - Step 1, patient: search box over `GET /provider/api/rx/patients?q=` (assigned patients only, name search, 20 per page). Empty: "No patients are assigned to you yet. A patient appears here after booking an appointment with you." Selecting a patient calls `GET /provider/api/rx/eligibility?patient_id=` and shows a panel: consult state ("Consult in progress since 14:05, video" or the blocker), TPG context in words ("First consult: medicines from List O and List A only", "Follow-up: List B also allowed", "In-person consult: lists O, A and B"), e-prescription consent state, limits ("Up to 6 medicines. Up to 14 days each."). Blockers disable "Continue" and show the code's text with an action: `no_consult` links to the appointments table ("Start a consult"), `no_consent` says "Ask the patient to allow e-prescriptions on their Prescriptions page", `patient_not_assigned` cannot occur from the picker. The "same condition as the previous in-person consult" checkbox appears only when `follow_up_possible` is true.
   - Step 2, clinical details: diagnosis (required, 120), allergies (radio: None reported / Listed / Not known, text when Listed), current medicines (same), expiry (select 1 to `RX_EXPIRY_DAYS` days, default max).
   - Step 3, medicines: a search input with 250 ms debounce, minimum 2 characters, an `AbortController` cancels the previous request, results `GET /provider/api/rx/medicines?q=&patient_id=`. Each result shows label, TPG list badge (`List O|A|B`), availability badge (In stock, Low stock, Out of stock; plus the line "Stock is not held for this prescription"), and a disabled, explained state for non-prescribable ones (the `blocked_text`). "Add" appends an item editor (dose, frequency, duration in days, quantity, instructions, remove). Up to 6 items; adding a seventh shows the limit text. Duplicate medicine in the same prescription is refused inline.
   - Step 4, review: calls `POST .../validate`; shows blocking errors per field or item (red, linked to the field) and warnings (each with a checkbox "I have seen this", plus the permanent line "This check finds the same medicine or the same class only. It is not a drug interaction check."). "Issue prescription" is disabled until there are no errors and every warning is ticked.
   - Step 5, confirm modal (`MFH.confirm`): patient name, medicines list, valid until, "This cannot be edited after it is issued. You can cancel it or write a new one." Confirm sends `POST .../issue` with the stored key and `acknowledged_warnings`. The button shows `aria-busy` and is disabled while the request runs; a network failure keeps the key so a retry cannot double-issue. Success redirects to `provider.rx_detail` with a toast and a "Print" button.
   - Autosave: `PUT` when the user leaves a step and every 20 seconds if dirty; a 409 `stale_draft` shows "This draft was changed in another tab. Reload to continue."
   - Empty catalogue: "No medicines are available yet. Ask your institution administrator to add them."
2. My prescriptions `/provider/prescriptions`, `provider.rx_list`, template `provider_rx/list.html`: tabs Drafts, Issued (issued and partially dispensed), Closed (dispensed, cancelled, expired); search by prescription number; columns number, patient name, date, items, status badge, collection status; pagination. Empty states: "No drafts.", "No issued prescriptions.", "Nothing closed yet."
3. Detail `/provider/prescriptions/<id>`, `provider.rx_detail`, template `provider_rx/detail.html`: full read-only content, collection status per item, timeline, links Print. Actions: "Cancel prescription" (modal with a reason select: error, patient request, clinical change; confirm text "The patient and the pharmacy desk will see it as cancelled"), "Write a corrected prescription" (amend, only when `issued`, confirm modal, creates a draft and opens step 2). Another doctor's prescription (item lines only) is not reachable here: 404.
4. Print `/provider/prescriptions/<id>/print`, `provider.rx_print` (3.9), audit `rx_print`.
5. Prescribing profile `/provider/prescribing-profile`, `provider.rx_profile` (GET) and `provider.rx_profile_save` (POST form), template `provider_rx/profile.html`, behind `@doctor_provider_required` only (a pending or suspended doctor must reach it). Shows status card, the submitted registration number, council, year, specialisation; an edit form with the notice "Changing the registration number, council or year sends your account back for checking and switches prescribing off until it is checked"; "Sent for checking on {date}".

Provider prescribing endpoints (module and name):

| Method and URL | Endpoint | Module | Notes |
|---|---|---|---|
| `GET /provider/prescriptions` | `provider.rx_list` | `pages.py` | |
| `GET /provider/prescribe` | `provider.rx_prescribe` | `pages.py` | |
| `GET /provider/prescriptions/<int:rx_id>` | `provider.rx_detail` | `pages.py` | |
| `GET /provider/prescriptions/<int:rx_id>/print` | `provider.rx_print` | `pages.py` | |
| `GET /provider/prescribing-profile` | `provider.rx_profile` | `profile.py` | |
| `POST /provider/prescribing-profile` | `provider.rx_profile_save` | `profile.py` | form post, resets status per 2.3 |
| `POST /provider/appointments/<int:appointment_id>/start-consult` | `provider.consult_start` | `consults.py` | JSON or redirect |
| `POST /provider/appointments/<int:appointment_id>/complete-consult` | `provider.consult_complete` | `consults.py` | |
| `GET /provider/api/rx/dashboard` | `provider.rx_api_dashboard` | `api_lookup.py` | |
| `GET /provider/api/rx/patients` | `provider.rx_api_patients` | `api_lookup.py` | |
| `GET /provider/api/rx/eligibility` | `provider.rx_api_eligibility` | `api_lookup.py` | |
| `GET /provider/api/rx/medicines` | `provider.rx_api_medicines` | `api_lookup.py` | |
| `GET /provider/api/rx/prescriptions` | `provider.rx_api_list` | `api_drafts.py` | `status=draft|issued|closed` |
| `POST /provider/api/rx/prescriptions` | `provider.rx_api_create` | `api_drafts.py` | create draft; optional IDEM |
| `GET, PUT, DELETE /provider/api/rx/prescriptions/<int:rx_id>` | `provider.rx_api_get`, `rx_api_update`, `rx_api_delete` | `api_drafts.py` | PUT and DELETE only for drafts |
| `POST /provider/api/rx/prescriptions/<int:rx_id>/validate` | `provider.rx_api_validate` | `api_issue.py` | no state change |
| `POST /provider/api/rx/prescriptions/<int:rx_id>/issue` | `provider.rx_api_issue` | `api_issue.py` | IDEM required |
| `POST /provider/api/rx/prescriptions/<int:rx_id>/cancel` | `provider.rx_api_cancel` | `api_issue.py` | body `{"reason_code"}` |
| `POST /provider/api/rx/prescriptions/<int:rx_id>/amend` | `provider.rx_api_amend` | `api_issue.py` | returns the new draft |

Package layout (A): `routes/provider_rx/__init__.py` holds `def register(bp)` which imports the five modules (each defines `def init(bp)` that decorates its functions with `bp.route`) and also registers the context processor and the `ist` filter through `bp.app_context_processor` and `bp.app_template_filter`. `routes/provider.py` gets ONE new last line, `from routes.provider_rx import register as _register_rx; _register_rx(provider_bp)`, placed before the blueprint is registered with the app (it executes at import time, which happens first). Moving `provider.py` into a package is NOT done in this wave: other agents are editing it and `tests/test_perf.py` and `tests/test_provider_scope.py` import `routes.provider.institution_summary`. A later refactor can turn `routes/provider.py` into `routes/provider/__init__.py` re-exporting the same names.

Decorator order on every prescribing route: `@prescriptions_required`, `@login_required`, then `@verified_prescriber_required` (or `@doctor_provider_required` for the profile). A counsellor gets 404 (the decorator does not reveal the feature), an unverified doctor gets 403 JSON `prescriber_not_verified` or a redirect to `provider.rx_profile` with a flash.

### 5.4 Admin dashboard (new blueprint `admin`, package `routes/admin/`)

Layout for B: `templates/admin/_nav.html` is a left or top navigation with sections Overview, People (Staff, Verification), Medicines (Catalogue, Inventory, Dispensing, Reports), Governance (Audit, Annual report, Messages). Dispensing and the inventory write buttons are rendered only when `desk` is true. An admin without the desk flag sees the read-only inventory and the masked log; the dispensing link is hidden and its URL returns 403.

| Screen | URL, endpoint | Content, empty state, actions |
|---|---|---|
| Login | `/admin/login`, `admin.login` | email and password only. Generic error. Link back to the public site. |
| Dashboard | `/admin/dashboard`, `admin.dashboard` | Widgets below. |
| Staff | `/admin/staff`, `admin.staff` | Table: name, email, type (Counsellor or Doctor), institution as typed, joined date, status (Active, Deactivated), for doctors the verification badge. Actions: Deactivate and Reactivate (`MFH.confirm`, danger style for deactivate, text "They will not be able to sign in. Their data is kept."). Filter by type and status. Empty: "No counsellors or doctors have registered for your institution yet." No patient rows, ever. |
| Verification queue | `/admin/verification`, `admin.verification` | Tabs Pending, Verified, Suspended, Rejected with counts. Rows: doctor name, registration number, council, year, specialisation, submitted date, review due. Empty (Pending): "No registrations waiting." Row action: Review. |
| Verification detail | `/admin/verification/<profile_id>`, `admin.verification_detail` | The honest-limit paragraph (2.2), the doctor's submitted details, a button "Open the Indian Medical Register" (new tab, `rel="noopener noreferrer"`), a link to the NMC removed-doctors page, the 5-item checklist (all required), an evidence note textarea (10 to 500), and buttons Verify, Reject (reason), Suspend (reason, when verified), Reinstate (when suspended). Each action confirms with `MFH.confirm` and shows the resulting status and date. History line: `verified_by` name and `verified_at`. |
| Catalogue | `/admin/catalogue`, `admin.catalogue`; form `/admin/catalogue/new`, `/admin/catalogue/<id>/edit` (`admin.catalogue_form`) | Table: medicine label, form, route, TPG list badge, schedule, class, status badges (Active, "Needs second check", "Demo"), actions Edit, Deactivate, Verify list (disabled for the last editor, with the reason shown). Buttons Import CSV, Export CSV, "Download template". Banner when `CATALOGUE_FOUR_EYES=0`. Empty: "The catalogue is empty. Add a medicine or import a CSV file. MindFull Horizon does not include any medicine data." The form carries the help text "Choose the list from the current Telemedicine Practice Guidelines notification. If unsure, choose List C: the medicine will be blocked." |
| Inventory (stock levels) | `/admin/inventory`, `admin.inventory` | Table per medicine: usable on hand, expired awaiting write-off, reorder level (inline edit for desk), status badge (In stock, Low, Out). Filters: status, search. Stat row: medicines low, out of stock, expiring within 60 days, awaiting write-off. Empty: "No stock recorded yet." (desk: button "Receive stock"). |
| Batches | `/admin/inventory/batches?medicine_id=`, `admin.batches` | Table: medicine, batch no, expiry date (red badge when within 60 days or expired), quantity, supplier, status. Desk actions: Adjust (reason select), Write off (only expired), Quarantine and Release. |
| Receive stock | `/admin/inventory/receive`, `admin.receive` | Form (medicine search select, batch no, expiry date, quantity, unit cost, supplier) and the CSV import box with "Check file" (dry run) then "Import". Desk only. |
| Dispensing | `/admin/dispensing`, `admin.dispensing` | Desk only. Lookup box "Prescription number" and the queue table (number, patient initials, items, sent at). Empty queue: "No prescriptions have been sent to the desk." |
| Dispense | `/admin/dispensing/<rx_id>`, `admin.dispensing_detail` | Prescription content (patient name, doctor, items with remaining quantity), warnings (prescriber status, expiry), editable quantity per line (cannot exceed remaining), button "Prepare" shows the plan (batches, expiry dates, shortfall). Step 2 panel: checkbox "I have checked the patient's identity and the prescription number", pharmacist name and registration number, button "Confirm dispensing" (`MFH.confirm`). After success: a receipt view and a "Reverse" action on each line for 24 hours. |
| Reports | `/admin/reports?tab=stock|expiring|log|usage`, `admin.reports` | Tabs with filters (date range, days) and Export CSV per tab (4.11). |
| Audit log | `/admin/audit`, `admin.audit` | Filters action, actor (staff name select), date range (default 7 days, max 92); table time (IST), actor name and role, action, target type and id, meta codes. No patient names. Pagination. |
| Annual report | `/admin/annual-report?year=`, `admin.annual` | Year select (current and previous 4), sections and metrics below, "Print" and "Export CSV". Footer line: "Figures drawn from fewer than 5 people are hidden." |
| Contact messages | `/admin/messages`, `admin.messages` | List (name, email, subject, date, status new or read), open a message in a panel, "Mark as read", `mailto:` reply link. Warning text above the panel: "Messages can contain personal or health information. Do not forward them." Empty: "No messages." |

Dashboard widgets (`GET /admin/api/dashboard`, also server-rendered on first load as the context `d`):

| Widget | Key | Rule |
|---|---|---|
| Doctors waiting for verification | `pending_verifications` | count; link to the queue; shown to every admin |
| Staff | `staff: {counsellors, doctors_verified, doctors_pending}` | counts |
| Patients | `patients: {total}` | `null` and the text "fewer than 5" when below K |
| Engagement and wellness | `summary` | the existing K-suppressed institution summary (`utils/aggregates.institution_summary_k`), figures `null` shown as "n/a" |
| Overdue crisis alerts | `crisis_overdue: {any: bool, count: int|null}` | alerts unacknowledged for longer than `CRISIS_ESCALATE_MINUTES` (existing env, default 15); `count` only when >= K; no identity; message "A crisis alert needs a counsellor. Check that counsellors are available." |
| Stock alerts | `stock: {low, out, near_expiry, awaiting_writeoff}` | counts from `inventory_alerts` logic, live |
| Prescribers due for re-check | `review_due` | count within 30 days |
| Prescriptions this month | `rx_month` | issued count, `null` when distinct patients < K |
| Dispensed today (desk only) | `dispensed_today` | count of dispense groups in `ist_day_bounds()` |
| Unread contact messages | `unread_messages` | count |
| Recent admin actions | `recent_audit` | last 5 rows of this admin's own audit actions |

Annual report metrics (`services/annual_report.py`, year bounds from `ist_day_bounds` of 1 Jan and 1 Jan next year; every count below that comes from distinct people or events fewer than K is replaced by `null` with `suppressed: true`): patients registered by the end of the year and new in the year; active patients (any logged activity in the year); screenings completed (PHQ-9, GAD-7) and the severity-band distribution (each band cell suppressed below K); appointments requested, completed, cancelled; crisis alerts raised, share acknowledged within the escalation window and median time to acknowledge; counsellors and verified doctors; prescriptions issued and prescriptions fully dispensed; medicine units dispensed (total only). CSV columns `section,metric,value,note` with `value` empty and `note = "suppressed (fewer than K people)"` for hidden cells. The page and the CSV state the year, the institution and the generated-at time in IST. Audit `export_annual_report`. No claim of validation: "Counts from this service only; not a prevalence estimate."

Admin endpoints (all `@prescriptions_required` except login, staff, verification, audit, annual, messages, dashboard: those work with the flag off; the decorators of 1.5; `D` means desk required; `IDEM` means header required):

| Method and URL | Endpoint | Module | Notes |
|---|---|---|---|
| `GET, POST /admin/login` | `admin.login` | `auth.py` | |
| `GET /admin/dashboard`, `GET /admin/api/dashboard` | `admin.dashboard`, `admin.api_dashboard` | `dashboard.py` | |
| `GET /admin/staff`; `POST /admin/api/staff/<int:user_id>/deactivate|reactivate` | `admin.staff`, `admin.api_staff_deactivate`, `admin.api_staff_reactivate` | `staff.py` | only `role = 'provider'` users of the admin's institution |
| `GET /admin/verification`, `GET /admin/verification/<int:profile_id>` | `admin.verification`, `admin.verification_detail` | `verification.py` | |
| `GET /admin/api/verification?status=&page=` | `admin.api_verification_list` | `verification.py` | |
| `POST /admin/api/verification/<int:profile_id>/verify|reject|suspend|reinstate` | `admin.api_verification_verify`, `..._reject`, `..._suspend`, `..._reinstate` | `verification.py` | body `{checks: {...}, note}` |
| `GET /admin/catalogue`, `GET /admin/catalogue/new`, `GET /admin/catalogue/<int:medicine_id>/edit` | `admin.catalogue`, `admin.catalogue_form` (two routes, one endpoint with `medicine_id=None`) | `catalogue.py` | |
| `GET /admin/api/catalogue?q=&list=&verified=&active=&page=` | `admin.api_catalogue_list` | `catalogue.py` | |
| `POST /admin/api/catalogue`; `PUT /admin/api/catalogue/<int:medicine_id>` | `admin.api_catalogue_create`, `admin.api_catalogue_update` | `catalogue.py` | |
| `POST /admin/api/catalogue/<int:medicine_id>/deactivate|activate|verify-list` | `admin.api_catalogue_deactivate`, `..._activate`, `..._verify_list` | `catalogue.py` | verify refuses the last editor with 409 `second_admin_required` |
| `POST /admin/api/catalogue/import` (multipart, `dry_run`), `GET /admin/catalogue.csv`, `GET /admin/catalogue/template.csv` | `admin.api_catalogue_import`, `admin.catalogue_csv`, `admin.catalogue_template` | `catalogue.py` | |
| `GET /admin/inventory`, `GET /admin/inventory/batches`, `GET /admin/inventory/receive` | `admin.inventory`, `admin.batches`, `admin.receive` | `inventory.py` | `receive` page is D |
| `GET /admin/api/inventory/stock`, `GET /admin/api/inventory/batches` | `admin.api_stock`, `admin.api_batches` | `inventory.py` | |
| `POST /admin/api/inventory/receive` (D, IDEM) | `admin.api_receive` | `inventory.py` | |
| `POST /admin/api/inventory/batches/<int:batch_id>/adjust` (D, IDEM), `.../write-off` (D, IDEM), `.../quarantine` (D) | `admin.api_adjust`, `admin.api_writeoff`, `admin.api_quarantine` | `inventory.py` | |
| `PUT /admin/api/inventory/reorder/<int:medicine_id>` (D) | `admin.api_reorder` | `inventory.py` | |
| `POST /admin/api/inventory/import` (D, multipart, `dry_run`), `GET /admin/inventory/stock.csv`, `GET /admin/inventory/template.csv` | `admin.api_stock_import`, `admin.stock_csv`, `admin.stock_template` | `inventory.py` | |
| `GET /admin/dispensing`, `GET /admin/dispensing/<int:rx_id>`, `GET /admin/dispensing/<int:rx_id>/print` (all D) | `admin.dispensing`, `admin.dispensing_detail`, `admin.dispensing_print` | `dispensing.py` | |
| `GET /admin/api/dispensing/queue` (D); `POST /admin/api/dispensing/lookup` (D) | `admin.api_queue`, `admin.api_lookup` | `dispensing.py` | lookup body `{"number"}`, returns `{rx_id}` only |
| `POST /admin/api/dispensing/<int:rx_id>/prepare` (D) | `admin.api_prepare` | `dispensing.py` | |
| `POST /admin/api/dispensing/<int:rx_id>/confirm` (D, IDEM) | `admin.api_confirm` | `dispensing.py` | |
| `POST /admin/api/dispensing/transactions/<int:tx_id>/reverse` (D, IDEM) | `admin.api_reverse` | `dispensing.py` | |
| `GET /admin/reports`, `GET /admin/api/reports/<name>`, `GET /admin/reports/<name>.csv` | `admin.reports`, `admin.api_report`, `admin.report_csv` | `reports.py` | `name` in `stock, expiring, log, usage` |
| `GET /admin/audit`, `GET /admin/api/audit` | `admin.audit`, `admin.api_audit` | `audit_view.py` | |
| `GET /admin/annual-report`, `GET /admin/annual-report.csv` | `admin.annual`, `admin.annual_csv` | `annual.py` | |
| `GET /admin/messages`, `POST /admin/api/messages/<int:message_id>/read` | `admin.messages`, `admin.api_message_read` | `messages.py` | |

Package layout (A): `routes/admin/__init__.py` defines `admin_bp = Blueprint('admin', __name__, url_prefix='/admin')` and imports the modules at the bottom; `routes/__init__.py` imports `admin_bp` and appends it to `all_blueprints`. Create `routes/rx_patient.py` and `routes/provider_meds.py` as EMPTY blueprint stubs (`rx_patient_bp`, `provider_meds_bp`) in the first hour and register them, so package C owns the files without touching `routes/__init__.py`.

### 5.5 JSON shapes (the contract between packages A, B and C)

```jsonc
// MedicineSearchItem  (GET /provider/api/rx/medicines)
{"id": 12, "label": "ESCITALOPRAM 10 mg tablet", "generic_name": "Escitalopram", "brand_name": "", "strength": "10 mg",
 "form": "tablet", "route": "oral", "tpg_list": "A", "prescribable": true, "blocked_code": null, "blocked_text": null,
 "availability": "in_stock"}   // "in_stock" | "low" | "out"; never a number for providers

// Eligibility  (GET /provider/api/rx/eligibility?patient_id=&attest=0|1)
{"success": true, "patient": {"id": 7, "name": "A. Student"}, "consult": {"appointment_id": 41, "modality": "video", "started_at": "2026-11-24T08:30:00Z"},
 "tpg_context": "first", "allowed_lists": ["O","A"], "follow_up_possible": true, "erx_consent": true,
 "limits": {"max_items": 6, "max_days": 14, "expiry_days_max": 30}, "blockers": []}   // blockers: ["no_consult","no_consent",...]

// Draft / Prescription  (GET/PUT /provider/api/rx/prescriptions/<id>)  PUT body = same minus read-only fields
{"id": 90, "row_version": 3, "status": "draft", "number": null, "patient": {"id": 7, "name": "A. Student"},
 "consult_appointment_id": 41, "tpg_context": "first", "same_condition_attested": false,
 "diagnosis": "F41.1", "allergies_status": "none_reported", "allergies": null,
 "current_meds_status": "unknown", "current_meds": null, "expiry_days": 30, "amends_id": null,
 "items": [{"line_no": 1, "medicine_id": 12, "medicine_label": "ESCITALOPRAM 10 mg tablet", "tpg_list": "A",
            "dose_text": "1 tablet", "frequency": "once daily", "duration_days": 14, "quantity": 14,
            "quantity_dispensed": 0, "instructions": "After breakfast"}],
 "issued_at": null, "valid_until": null, "cancel_reason": null, "dispense_requested_at": null, "collection": "none"}
// PUT replaces all editable fields AND the items array wholesale; the request carries row_version; 409 stale_draft on mismatch.

// ValidateResult  (POST .../validate; also the 409 body of issue)
{"success": true, "ok": false,
 "errors": [{"code": "medicine_blocked_c", "item": 2, "field": null, "message": "..."}, {"code": "field_required", "item": null, "field": "diagnosis", "message": "..."}],
 "warnings": [{"code": "dup_active_rx", "item": 1, "message": "..."}]}

// Issue  (POST .../issue, IDEM)   request: {"acknowledged_warnings": ["dup_active_rx"]}
// 200/201: {"success": true, "replayed": false, "prescription": {...Prescription with number, issued_at, valid_until...}}
// 409: {"success": false, "error": "warnings_unacknowledged", "warnings": [...]}   // or already_issued, not_draft, stale_draft, amended_rx_changed
// 403: {"success": false, "error": "prescriber_not_verified"} ; 422 carries "errors": [...] as in ValidateResult

// RxListItem  (GET /provider/api/rx/prescriptions?status=)
{"id": 90, "number": "RX2611-7K3M9QX4PD2", "status": "issued", "patient_name": "A. Student", "issued_at": "...", "valid_until": "...", "items": 2, "collection": "none"}

// Dashboard  (GET /provider/api/rx/dashboard)
{"success": true, "state": "verified", "review_due_at": "2027-11-24T00:00:00Z", "can_prescribe": true, "consults_today": [...], "drafts": [...], "drafts_total": 1, "recent": [...], "awaiting_collection": 0}

// DispensePlan  (POST /admin/api/dispensing/<id>/prepare)
{"success": true, "token": "...", "expires_in": 600, "rx": {"id": 90, "number": "RX2611-7K3M9QX4PD2", "status": "issued", "patient_name": "A. Student", "doctor_name": "Dr X", "valid_until": "..."},
 "lines": [{"item_id": 301, "medicine_label": "...", "remaining": 14, "requested": 14, "shortfall": 0,
            "allocations": [{"batch_id": 5, "batch_no": "B123", "expiry_date": "2027-03-31", "quantity": 14}]}], "warnings": []}
// confirm request: {"token": "...", "identity_checked": true, "pharmacist_name": "...", "pharmacist_reg_no": "..."}
// confirm 200: {"success": true, "replayed": false, "status": "dispensed", "group_ref": "...", "lines": [...]}  ; 409 plan_stale carries a fresh "plan"

// StockRow  (GET /admin/api/inventory/stock)
{"medicine_id": 12, "label": "...", "usable": 120, "expired": 10, "reorder_level": 50, "status": "in_stock"}
// BatchRow  {"id": 5, "medicine_id": 12, "label": "...", "batch_no": "B123", "expiry_date": "2027-03-31", "quantity_on_hand": 120, "supplier": "...", "status": "active", "days_left": 127}
// VerificationItem  {"id": 3, "user_name": "...", "email": "...", "registration_number": "...", "council": "...", "registered_since": 2011, "specialisation": "...", "status": "pending", "submitted_at": "...", "review_due_at": null}
```

Patient name in the provider and desk shapes is the full name of an assigned patient (provider) or of the looked-up prescription (desk). The queue shows initials only (`"A. S."`).

### 5.6 Templates and page context (what package A passes, what package B renders)

Pages that are mostly server-rendered receive context directly; pages that are interactive read their config from `<script type="application/json" id="page-config">` built with `|tojson` (no Jinja in static JS), holding endpoint URLs made with `url_for` and the Idempotency-Key is created in JS.

| Template (owner B) | Rendered by | Context variables |
|---|---|---|
| `provider_rx/_dashboard_section.html` | included from `provider_dashboard.html` | `rx_section` (dict above) |
| `provider_rx/prescribe.html` | `provider.rx_prescribe` | `config` (URLs: `patients`, `eligibility`, `medicines`, `drafts`, `detail_template` with `0` placeholder, `appointments`, `profile`), `patient` (dict or None), `draft` (Prescription dict or None), `limits` (dict), `rx_texts` (dict from `utils/rx_text.py`) |
| `provider_rx/list.html` | `provider.rx_list` | `tab`, `config` |
| `provider_rx/detail.html` | `provider.rx_detail` | `rx` (Prescription dict), `can_cancel`, `can_amend`, `config` |
| `provider_rx/print.html` | the three print endpoints | `rx` (Prescription dict with snapshots), `site_url`, `printed_at` |
| `provider_rx/profile.html` | `provider.rx_profile` | `profile` (dict), `state`, `form` (dict), `errors` (dict) |
| `admin/login.html` | `admin.login` | `form`, none else |
| `admin/dashboard.html` | `admin.dashboard` | `d` (Dashboard dict), `desk` (bool), `admin_name`, `institution` |
| `admin/staff.html` | `admin.staff` | `rows` (list of dicts: id, name, email, provider_type, institution_typed, created_at, deactivated, verification_state), `meta`, `filters` |
| `admin/verification.html` | `admin.verification` | `tab`, `counts` (dict by status), `rows`, `meta` |
| `admin/verification_detail.html` | `admin.verification_detail` | `p` (VerificationItem plus `notes`, `verified_by_name`, `verified_at`), `register_url`, `blacklist_url`, `checklist` (list of `{key, text}`), `actions` (list of allowed action names) |
| `admin/catalogue.html`, `admin/catalogue_form.html` | `admin.catalogue`, `admin.catalogue_form` | `rows`, `meta`, `filters`, `four_eyes` (bool), `me_id`; form: `medicine` (dict or None), `lists` (`O,A,B,C` with one-line meanings), `schedules`, `errors` |
| `admin/inventory.html`, `admin/batches.html`, `admin/receive.html` | `admin.inventory`, `admin.batches`, `admin.receive` | `rows`, `meta`, `stats`, `desk`, `reasons` (adjust reason codes with labels), `config` |
| `admin/dispensing.html`, `admin/dispensing_detail.html` | `admin.dispensing`, `admin.dispensing_detail` | `queue` (list), `rx` (dict), `config` |
| `admin/reports.html` | `admin.reports` | `tab`, `config`, `desk` |
| `admin/audit.html` | `admin.audit` | `rows`, `meta`, `filters`, `actions` (known action names), `staff` (id, name pairs) |
| `admin/annual.html` | `admin.annual` | `report` (dict: `year`, `institution`, `generated_at`, `sections`: list of `{title, metrics: [{name, value, note}]}`), `years` |
| `admin/messages.html` | `admin.messages` | `rows`, `meta`, `selected` |

Static files (owner B): `static/css/clinical.css`, `static/js/clinical-common.js` (`MFH.api(method, url, body, {idem: bool})` adds the CSRF header and Idempotency-Key, returns parsed JSON or throws `{status, error, message}`), `rx_prescribe.js`, `rx_list.js`, `rx_detail.js`, `rx_dashboard.js`, `admin_verification.js`, `admin_catalogue.js`, `admin_inventory.js`, `admin_dispensing.js`, `admin_reports.js`. `templates/base.html` gets an `elif role == 'admin'` nav branch and an admin `home_href`; the provider nav gains "Prescriptions" only inside `{% if rx_section and rx_section.show %}` (package B edits with small `Edit` calls; no other package touches `base.html`). `tests/test_design_rules.py` (if present) and the existing JS-no-Jinja test patterns must pass for the new files.

### 5.7 Tests per screen

Test files: A writes `tests/test_roles_admin.py`, `test_prescriber.py`, `test_rx_rules.py`, `test_rx_lifecycle.py`, `test_rx_api_provider.py`, `test_inventory.py`, `test_dispensing.py`, `test_inventory_csv.py`, `test_ops_jobs.py`, `test_admin_api.py`, `test_migration_roles.py`. B writes `tests/test_ui_clinical.py`. C writes `tests/test_rx_patient.py`, `tests/test_provider_meds.py`.

| Screen or unit | Tests (name stems) |
|---|---|
| Roles and signup | `signup_provider_type_counsellor_needs_provider_code`, `signup_doctor_needs_doctor_code`, `signup_doctor_creates_pending_profile`, `doctor_code_never_makes_counsellor`, `equal_codes_disable_doctor_signup`, `signup_admin_rejected`, `login_admin_on_main_form_fails_generic`, `admin_login_page_requires_admin`, `google_cannot_sign_in_admin`, `create_admin_cli_prompts_and_audits`, `create_admin_refuses_existing_email`, `deactivated_user_cannot_login`, `deactivated_admin_session_dies`, `role_check_allows_admin_rejects_unknown`, `migration_preserves_rows` |
| Decorators | `counsellor_gets_404_on_prescribing_routes`, `unverified_doctor_gets_403_json`, `suspension_blocks_next_request`, `denial_writes_audit_row`, `admin_without_desk_403_on_dispensing`, `patient_cannot_reach_admin_or_prescribing` |
| Prescriber verification | `submit_pending`, `verify_requires_all_checks_and_note`, `verify_other_institution_404`, `edit_registration_resets_to_pending`, `suspend_then_issue_fails`, `lapsed_review_blocks_issue_not_dispense`, `duplicate_registration_number_blocked`, `rejected_can_resubmit`, `every_transition_audited`, `unverified_doctor_not_bookable` |
| Provider prescribing dashboard section | `section_hidden_for_counsellor`, `banner_text_per_state`, `consults_today_scoped_to_self`, `drafts_listed`, `empty_states` |
| Prescribe flow (API) | `patients_list_assigned_only`, `eligibility_no_consult`, `eligibility_stale_consult_after_window`, `eligibility_first_vs_followup_vs_in_person`, `medicines_search_min_length_and_limit`, `medicines_blocked_reasons`, `availability_badges_no_numbers`, `draft_create_idempotent`, `draft_put_row_version_conflict`, `draft_other_doctor_404`, `validate_reports_errors_and_warnings`, `issue_happy_path_sets_snapshots_and_number`, `issue_idempotent_replay_200`, `issue_twice_different_key_409`, `issue_concurrent_double_submit_one_row`, `issue_blocks_list_c_h1_x_ndps`, `issue_list_b_needs_followup`, `issue_item_limits_and_duration_cap`, `issue_requires_consent`, `issue_requires_assigned_patient`, `issue_requires_allergy_and_meds_status`, `issue_warning_ack_required`, `issue_demo_medicine_blocked_in_production`, `number_check_char_and_format`, `number_collision_retries`, `expiry_end_of_ist_day`, `cancel_reasons`, `cancel_partial_keeps_dispensed`, `amend_links_and_cancels_old_on_issue`, `amend_aborts_if_old_dispensed`, `issued_is_immutable`, `effective_status_expired_without_job`, `no_free_text_in_audit_or_logs` |
| Provider prescription pages | `list_tabs_and_paging`, `detail_scoped_to_issuer`, `print_uses_snapshots_and_banners`, `print_audited`, `profile_edit_form`, `consult_start_rules`, `consult_complete` |
| Medication panel (counsellor) | `panel_assigned_only`, `panel_hides_diagnosis_and_allergies`, `panel_audited`, `panel_empty_state`, `send_prescription_route_gone` |
| Patient screens | `list_buckets`, `detail_own_only_404_other`, `drafts_invisible`, `legacy_row_warning_no_actions`, `collection_status_words`, `request_pharmacy_idempotent`, `request_pharmacy_not_for_cancelled`, `consent_give_withdraw`, `withdraw_blocks_new_issue_keeps_old`, `public_status_check_minimal_fields`, `public_status_bad_check_char_404`, `dashboard_widget_and_care_team`, `schedule_lists_verified_doctors_only`, `schedule_modality_and_consent_required_for_doctor`, `export_includes_items` |
| Catalogue | `create_edit_deactivate`, `list_edit_resets_verification`, `four_eyes_blocks_same_admin`, `four_eyes_off_banner`, `unique_identity`, `schedule_x_forces_controlled`, `csv_import_dry_run_and_all_or_nothing`, `csv_import_never_verifies`, `csv_export_formula_injection_escaped`, `catalogue_empty_state`, `no_seed_data_in_migration` |
| Inventory | `receive_creates_batch_and_ledger_in_one_tx`, `receive_tops_up_existing_batch`, `receive_rejects_expired_and_controlled`, `adjust_requires_reason_and_stays_nonnegative`, `writeoff_only_expired`, `quarantine_skips_allocation`, `reconcile_detects_mismatch`, `ledger_never_updated_or_deleted`, `stock_import_duplicate_file_rejected`, `reorder_rule_crud`, `non_desk_admin_read_only`, `institution_isolation` |
| Dispensing | `fefo_order`, `expired_batch_never_allocated`, `partial_dispense_marks_partially`, `full_dispense_marks_dispensed`, `plan_stale_when_stock_changed`, `confirm_idempotent_replay`, `two_threads_cannot_oversell`, `two_desks_same_rx_one_wins`, `cancelled_or_expired_rx_not_dispensable`, `suspended_prescriber_blocks`, `identity_and_pharmacist_required`, `reverse_within_24h_once`, `reverse_restores_status`, `queue_shows_initials_only`, `lookup_check_char_and_rate_limit`, `other_institution_rx_404`, `patient_return_not_restocked` |
| Reports and dashboard | `stock_report`, `expiring_report_window`, `log_masks_number_for_base_admin`, `usage_suppresses_below_k`, `dashboard_counts`, `dashboard_patient_total_hidden_below_k`, `crisis_overdue_count_hidden_below_k`, `no_patient_identity_in_any_admin_json` (walks every admin JSON and HTML response for patient names seeded in the DB, except the desk exception) |
| Audit viewer, annual, messages | `audit_institution_scope`, `audit_date_range_cap`, `audit_view_itself_audited`, `annual_k_suppression`, `annual_csv_columns`, `messages_read_flag`, `messages_audited` |
| Jobs | `ops_daily_registers_and_reschedules`, `ops_daily_idempotent_key`, `expires_prescriptions`, `alerts_once_per_day`, `alerts_counts_only` |
| UI (B) | `templates_render_with_sample_context`, `no_jinja_in_new_js`, `node_check_js` (skipped without node), `no_emoji_no_em_dash_in_new_files`, `buttons_have_labels_and_aria_busy`, `empty_states_present` |

## 6. Data model summary

| Table | Change | Key columns | Delete behaviour |
|---|---|---|---|
| `users` | alter | role CHECK adds `admin`; `provider_type`, `deactivated_at`, `is_pharmacy_desk` | unchanged cascades |
| `prescriber_profiles` | new | `user_id` unique, `registration_number`, `council_key`, `status`, `verified_by`, `review_due_at` | CASCADE from user |
| `appointments` | alter | `modality`, `consult_started_at` | unchanged |
| `medicines` | new | `generic_key`, `tpg_list`, `schedule`, `is_controlled`, `list_verified_*`, `is_demo` | never deleted (RESTRICT from children) |
| `inventory_batches` | new | `institution_key`, `medicine_id`, `batch_no`, `expiry_date`, `quantity_on_hand` CHECK >= 0 | RESTRICT |
| `reorder_rules` | new | `(institution_key, medicine_id)` unique, `reorder_level` | RESTRICT on medicine |
| `prescriptions` | alter | `number`, `status`, snapshots, consult link, consent, warnings, `amends_id`, idempotency keys, `row_version`; `provider_id` becomes RESTRICT | patient delete cascades, doctor delete blocked |
| `prescription_items` | new | `prescription_id`, `medicine_id`, `dose_text`, `frequency`, `duration_days`, `quantity`, `quantity_dispensed` | CASCADE from prescription, RESTRICT on medicine |
| `inventory_transactions` | new | `batch_id`, `delta`, `kind`, `prescription_item_id`, `rx_number`, `idempotency_key` unique, `reverses_id` unique | RESTRICT on batch, SET NULL on item |
| `consent_records` | no schema change | new `kind` values `eprescription`, `eprescription_off` | |
| `audit_log`, `jobs`, `notifications`, `contact_messages` | no schema change | new action names, job kind `ops_daily`, notification types `inventory_alert`, `inventory_mismatch`, `prescriber_review_due` | |

`models.py` is the source of truth; every table and constraint name above is exact so `tests/test_db.py::test_migration_upgrade_matches_create_all` passes. `Medication` (the patient's own medicine log) is unchanged and is NOT linked to prescriptions in this wave.

## 7. State machines

Prescription (`status`; `effective_status` adds time-based expiry):

| From | To | Trigger | Guard (compare-and-set `WHERE`) |
|---|---|---|---|
| (new) | `draft` | doctor creates | verified, assigned patient |
| `draft` | `issued` | issue transaction (3.7) | `status = 'draft' AND row_version = :v AND provider_id = :me` |
| `issued` | `partially_dispensed` | desk confirm with remaining items | `status IN ('issued','partially_dispensed') AND expiry_date > :now` |
| `issued`, `partially_dispensed` | `dispensed` | desk confirm, nothing remaining | same |
| `dispensed` | `partially_dispensed` or `issued` | desk reverses a line within 24 h | `status IN ('dispensed','partially_dispensed')` |
| `issued`, `partially_dispensed` | `cancelled` | issuing doctor, amendment, or system | `status IN (...) AND provider_id = :me` |
| `issued`, `partially_dispensed` | `expired` | `expiry_date <= now` (derived at read, persisted by the nightly job) | |
| `draft` | (deleted) | owner deletes | `status = 'draft'` |
| `legacy` | none | migration only | read-only forever |
| `dispensed`, `cancelled`, `expired` | none | terminal | |

Prescriber profile: table in 2.3. Consult: `accepted` or `booked` appointment gets `consult_started_at` (once), then `completed`. Batch: `active` to `quarantined` and back (desk), `active` to `closed` only by a write-off to zero of an expired batch. Dispense line: created `dispense`, may be reversed once by a `return` line within 24 h. Draft edits: `row_version` increments on every successful `PUT`.

## 8. Configuration (all read at call time, section 13 for the flag)

| Env var | Default | Meaning |
|---|---|---|
| `ENABLE_PRESCRIPTIONS` | **on** (changed from off) | master switch for prescribing, patient prescription pages, desk and inventory routes |
| `PROVIDER_INVITE_CODE` | unset (closed) | counsellor signup |
| `DOCTOR_INVITE_CODE` | unset (closed) | doctor signup; must differ from the counsellor code |
| `PRESCRIBER_REVIEW_DAYS` | 365 | re-verification period |
| `RX_EXPIRY_DAYS` | 30 (max 90) | longest validity a doctor can choose |
| `RX_MAX_ITEMS` | 6 | items per prescription |
| `RX_MAX_DAYS_FIRST`, `RX_MAX_DAYS_FOLLOWUP` | 14, 30 | duration caps per item (policy, not regulation) |
| `RX_CONSULT_WINDOW_HOURS` | 24 | how long a started consult qualifies |
| `ERX_CONSENT_VERSION` | `2026-11` | version stored with the e-prescription consent |
| `CATALOGUE_FOUR_EYES` | 1 | second-admin confirmation of list classification |
| `INVENTORY_MIN_SHELF_DAYS` | 0 | batches expiring sooner are not allocated |
| `INVENTORY_NEAR_EXPIRY_DAYS` | 60 | near-expiry alert and report window |
| `ALLOW_DEMO_DATA` | 0 | allows `is_demo` medicines when `FLASK_ENV=production` |
| `MIN_AGGREGATE_GROUP` | 5 (existing) | K |
| `CRISIS_ESCALATE_MINUTES` | 15 (existing) | "overdue" crisis alert on the admin dashboard |

A reads them through one module `services/config.py` with typed getters and clamps (bad values fall back to the default, never raise), and appends the new names with comments to `.env.example` by `Edit` (append-only).

## 9. Seed and demo data

- Migrations insert NO rows into `medicines`, `inventory_*`, `prescriber_profiles` or `reorder_rules`. A test (`no_seed_data_in_migration`) upgrades an empty database and asserts those tables are empty.
- `scripts/seed_demo.py` (package C) refuses to run when `FLASK_ENV=production` (existing guard) and, in addition to the demo patient and counsellor, creates: a demo doctor (`provider_type='doctor'`, profile `verified` with `notes='DEMO ONLY, not a real registration'` and a registration number like `DEMO0001`), a demo admin with `is_pharmacy_desk`, an appointment with `modality='video'` and `consult_started_at=now` between the demo patient and the demo doctor, the demo patient's e-prescription consent, and about 8 FICTIONAL medicines with `is_demo=True` and names such as "Democillin 10 mg tablet (DEMO)" covering lists O, A, B and C and one controlled entry, all `list_verified_*` set by two different demo admins, plus a few batches with future, near and past expiry dates for the demo institution. Passwords random, printed once (existing behaviour).
- Demo medicines are labelled "Demo" in every UI list (badge), and `medicine_demo_blocked` stops them from being prescribed when `FLASK_ENV=production` unless `ALLOW_DEMO_DATA=1`.

## 10. Concurrency and idempotency summary

| Operation | Key or guard | Race outcome |
|---|---|---|
| Create draft | `Idempotency-Key` or body `client_request_id`, UNIQUE `(provider_id, client_request_id)` | second call returns the first draft |
| Edit draft | `row_version` | stale write gets 409 `stale_draft` |
| Issue | `issue_request_id` UNIQUE plus CAS on `status='draft'` | one winner; replay with the same key returns 200; another key gets 409 |
| Prescription number | UNIQUE `number`, whole-transaction retry | collision retried up to 3 times |
| Dispense confirm | `group_ref` from the key, UNIQUE ledger `idempotency_key`, CAS on prescription, item and batch | one winner, no oversell, replay returns the stored result |
| Reverse | UNIQUE `reverses_id` | second reversal fails 409 |
| Receive, adjust | required `Idempotency-Key` stored as the ledger key | replay returns the stored line |
| Stock import | content hash in the ledger key | the same file twice is rejected |
| Patient send-to-desk, consent | naturally idempotent | |
| Daily job | `ops_daily:{date}` job key | one run per day |

## 11. Migration order

Current head at the time of writing: `0003` (`0003_idempotency_state_integrity`). The implementers run `flask db heads` first and renumber if the head moved. Four migrations, each with a working `downgrade()` (development use), each applied in order and covered by `tests/test_migration_roles.py` plus `test_db.py::test_migration_upgrade_matches_create_all`:

| Revision | File | Contents |
|---|---|---|
| `0004` | `0004_roles_provider_type_prescriber.py` | role CHECK (1.3), `users.provider_type` + CHECK, `users.deactivated_at`, `users.is_pharmacy_desk`, backfill `provider_type='counsellor'`, `prescriber_profiles` (+ partial unique index), `appointments.modality` + CHECK, `appointments.consult_started_at` |
| `0005` | `0005_medicines_batches_reorder.py` | `medicines`, `inventory_batches`, `reorder_rules` (no rows inserted) |
| `0006` | `0006_prescriptions_v2.py` | add columns to `prescriptions` (nullable first), `UPDATE prescriptions SET status='legacy'` for all existing rows, then enforce NOT NULL and the CHECKs, make `medication_name` and `dosage` nullable, change the provider FK to RESTRICT (batch recreate on SQLite), create `prescription_items`, indexes |
| `0007` | `0007_inventory_ledger.py` | `inventory_transactions` (needs `prescription_items`) |

Rules: SQLite uses `op.batch_alter_table` everywhere; PostgreSQL uses the same code path. Partial indexes use both `sqlite_where` and `postgresql_where`. Data steps are bounded and idempotent. Each migration is tested on an empty DB and on a DB created at the previous head with sample rows (users of each role, an appointment, a legacy prescription). Package A (acting as the schema owner, the role "Q1b" in the brief) is the ONLY package that edits `models.py` and `migrations/` in this wave; B and C request changes through the lead.

## 12. Effect on existing tests

The 265 existing tests must pass except these intentional changes (change minimally and say so in the report):

| Test | Change |
|---|---|
| `tests/test_db.py` line ~42 (role CHECK) | insert role `'superuser'` instead of `'admin'`; add one that `'admin'` inserts fine |
| `tests/test_db.py` line ~78 (creates a `Prescription` with `medication_name`, `dosage`) | still valid because the columns are nullable and `status` defaults to `draft`; if the row needs a status, pass `status='legacy'` |
| `tests/test_provider.py` lines ~129 to 161 (`send_prescription` happy path, foreign patient, form action in the wellness report) | replace with: route returns 404, the form is absent from the report, the medications panel is present |
| `tests/test_provider_scope.py` lines ~30 to 43 (cross-institution `send_prescription`) | retarget at the new draft-create API (foreign patient gives 404 and zero rows) |
| `tests/test_provider_scope.py` lines ~225 to 257 (prescriptions gate) | the default is now ON: the "404 by default" tests set `ENABLE_PRESCRIPTIONS=0` explicitly; the "works when on" test is replaced by the new flow tests; the JSON gate test keeps working with the env set to 0 |
| `tests/test_redesign_patient.py` lines ~102 to 108 | `test_dashboard_hides_prescriptions_by_default` sets the flag to 0; the "shows when enabled" test stays |
| `tests/test_security.py` role tests | unchanged and must pass (`test_signup_unknown_role_rejected`, `test_save_role_*`); `test_signup_provider_needs_matching_invite_code` stays valid because a missing `provider_type` field means `counsellor` |
| `tests/conftest.py` | append-only: fixtures `admin_client` (admin with `is_pharmacy_desk=False`), `desk_client`, `doctor_client` (provider with `provider_type='doctor'` and a verified profile) built on `make_user`; `make_user` itself must accept `provider_type=` through an extra keyword (backwards compatible) |
| `tests/test_design_rules.py` | will scan the new templates and JS; new files must pass (no emoji, no em dash, no pill radius, no colour utilities, no Jinja in JS) |
| `tests/test_security.py::test_duplicate_routes_gone` | new route rules must not duplicate existing paths |

## 13. Feature flag, failure modes, operations

**Flag semantics.** `ENABLE_PRESCRIPTIONS` now defaults to ON. This is safe only because: (a) no prescription can be created without a doctor whose registration an institution admin verified, (b) every prescribing route is behind `verified_prescriber_required` and re-checks inside the issue transaction, (c) the catalogue is empty in a fresh deployment (no migration seeds it) so nobody can issue until an admin adds and a second admin verifies medicines, (d) counsellors have no prescribing UI, and (e) the legacy open-form route is deleted. Setting the variable to `0` returns 404 for prescribing, patient prescription pages, desk and inventory routes and hides every link (`prescriptions_enabled` template flag, unchanged). Role management, verification, audit, annual report and contact inbox do not depend on the flag. Change `utils/feature_flags.py` default to `True` and its docstring; the lead updates P-01 in the tracker.

| Failure mode | Mitigation |
|---|---|
| Double dispense (double click, two desks, retry) | prepare/confirm with signed plan, `Idempotency-Key`, ledger unique key, compare-and-set on prescription, item and batch; two-thread test |
| Expired stock dispensed | usable-stock predicate in selection AND in the update; conservative "not on expiry day"; expiry is a `Date` compared with the IST date |
| Negative stock | `CHECK (quantity_on_hand >= 0)`, compare-and-set, `adjust` guard, nightly `reconcile` |
| Doctor suspended mid-session | decorator re-reads the DB each request; issue re-checks with a lock; dispensing blocked for suspended or rejected prescribers; drafts stay but cannot be issued |
| Deactivated provider with a live session | admin and doctor routes re-check `deactivated_at`; counsellor sessions end at the next login (known gap: the existing `provider_required` reads only the session; adding a DB read there is a follow-up) |
| Concurrent edits to one draft | `row_version` and 409 |
| Prescription cancelled while being dispensed | the claim `UPDATE ... WHERE status IN (...)` fails the whole dispense transaction |
| Clock and timezone | stored times are naive UTC; "today", expiry end-of-day, shelf checks and report ranges use `utils.timeutil` (IST day bounds); prescription `expiry_date` is the end of an IST day; no `datetime.now()` or `date.today()` in new code (a test greps `services/` and `routes/admin|provider_rx/`) |
| Demo data in production | `is_demo` plus `medicine_demo_blocked`, seed script refuses production |
| Wrong TPG list entered | four-eyes confirmation, unknown means C, CSV can never verify, the help text says "choose C if unsure" |
| Free text leaks | no free text in audit meta, logs or jobs; test seeds a marker string in diagnosis, allergies, dose and instructions and asserts it appears in none of `AuditLog.meta`, `Job.payload`, captured log records |
| Admin sees patient data | no admin template or JSON includes patient identity except the desk exception; test walks admin endpoints with seeded patient names |
| Privilege escalation to admin or doctor | no web path creates admin; doctor needs a secret code and then a human check; `provider_type` has no edit route; Google cannot sign in admins |
| Enumeration of prescription numbers | 50-bit random bodies, check character, `30 per minute` limiter, uniform 404, desk-only lookup, public check shows minimal fields |
| Backups | prescriptions, items, ledger, audit and consent rows are clinical records: `docs/OPERATIONS.md` must state that the database backup includes them, is encrypted at rest by the host, is tested by restore, and that the ledger and audit tables are never truncated by maintenance scripts. A restore to an older point can lose issued prescriptions and dispensing lines: the desk must reconcile stock with a physical count after any restore (document in the runbook). |
| Job worker down | alerts are also computed live on the admin dashboard; expiry is derived at read time |
| SQLite in production | single writer makes the compare-and-set safe, but throughput and backups are limited; PostgreSQL is the production target (existing guidance) |

## 14. Work packages (three agents, no shared files)

Rule for all: no edits to files owned by another package; shared files only through small `Edit` calls named below; stay inside the project folder; do not edit `docs/TRACKER.md`, `STATUS.md`, `MEMORY.md`; run only your own tests plus the tests of code you touched; report failures plainly.

### Package A: schema, services, decorators, API routes, backend tests

Owned files (create or edit): `models.py`, `migrations/versions/0004...0007`, `services/` (new package: `__init__.py`, `errors.py`, `config.py`, `roles.py`, `prescriber.py`, `rx_rules.py`, `prescriptions.py`, `consent.py`, `inventory.py`, `dispensing.py`, `inventory_csv.py`, `reports.py`, `annual_report.py`, `ops_jobs.py`, `admin_cli.py`, `appointments.py`, `db_util.py`), `utils/aggregates.py`, `utils/rx_numbers.py` (number and check character), `decorators.py`, `utils/feature_flags.py`, `utils/assignments.py` (no change needed except a doc line; leave unless a test shows otherwise), `routes/auth.py` (signup roles, login, `_home`, `account_delete`, `_EXPORT`), `routes/admin/` (package), `routes/provider_rx/` (package), `routes/__init__.py` (register `admin_bp`, `rx_patient_bp`, `provider_meds_bp`), `.env.example` (append), `tests/` files listed in 5.7 for A, `tests/conftest.py` (append-only fixtures).

One-line edits A makes in files it does not own: `app.py` (Google sign-in refusal for admins; `init_admin_cli(app)`; telehealth needs none), `routes/provider.py` (the single registration line, last line of the file), `utils/jobs.py` (`_load_handlers` import of `services.ops_jobs`). First hour deliverables so B and C can start: `services/errors.py`, `services/roles.py`, the model classes (even before migrations pass), empty stub modules `routes/rx_patient.py` and `routes/provider_meds.py` with `rx_patient_bp` and `provider_meds_bp`, and registration of all new blueprints.

Function contracts A provides (signatures are frozen; add parameters only with defaults):

```python
# services/errors.py
class ServiceError(Exception):  # code: str, http: int, fields: dict | None
    def __init__(self, code, http=400, fields=None, **ctx): ...
MESSAGES: dict[str, str]       # code -> safe user text (the codes in 3.4, 4.x, 5.1)

# services/roles.py            (1.1)
# services/prescriber.py       (2.3)
# services/prescriptions.py
def consult_eligibility(doctor_id, patient_id, same_condition_attested=False, now=None) -> Eligibility
def create_draft(doctor_id, patient_id, client_request_id=None) -> Prescription
def save_draft(doctor_id, rx_id, payload: dict, row_version: int) -> Prescription
def delete_draft(doctor_id, rx_id) -> None
def validate(doctor_id, rx_id) -> ValidationResult            # errors, warnings, no state change
def warnings(rx) -> list
def issue(doctor_id, rx_id, issue_key, acknowledged) -> IssueResult
def cancel(actor_id, rx_id, reason_code) -> Prescription
def amend(doctor_id, rx_id) -> Prescription
def effective_status(rx, now=None) -> str
def expire_due(now=None) -> int
def serialize(rx, viewer: str) -> dict                        # viewer in 'doctor','patient','desk','staff_lines'
def doctor_dashboard(doctor_id) -> dict                       # 5.5 Dashboard
def list_for_doctor(doctor_id, bucket, q=None, page=1, per_page=20) -> (rows, meta)
def list_for_patient(patient_id, bucket, page=1, per_page=10) -> (rows, meta)
def get_for_patient(patient_id, rx_id) -> dict                # 404 ServiceError if not theirs or draft
def request_pharmacy(patient_id, rx_id, now=None) -> Prescription
def medication_lines_for_staff(patient_id) -> dict            # {"self_logged": [...], "prescriptions": [...]} item lines only
def active_rx_patient_ids(patient_ids) -> set[int]
def public_status(number) -> dict | None                      # 3.9

# services/consent.py
def erx_status(patient_id) -> dict       # {"active": bool, "version": str}
def set_erx_consent(patient_id, on: bool) -> None

# services/rx_rules.py (pure)
def medicine_block_code(med, allowed_lists, env=None) -> str | None
def allowed_lists(tpg_context) -> set[str]
def check_limits(items, tpg_context, cfg) -> list[dict]

# services/inventory.py        (4.5)  # services/dispensing.py: plan, confirm, reverse, queue(institution_key), lookup(number, institution_key)
# services/reports.py: stock(institution_key, ...), expiring(...), log(..., masked: bool), usage(..., k)
# services/annual_report.py: build(institution_key, year, k) -> dict (5.6 `report`)
# utils/aggregates.py: normalize_institution_name, min_group, institution_summary_k(institution) -> dict   (moved logic of routes/provider.py)
# utils/rx_numbers.py: new_number(now) -> str; is_valid_number(s) -> bool; mask_rx(s) -> str
```

Contracts A needs from others: from C, `utils/rx_text.py` constants (`ERX_CONSENT_TEXT`, `SAFETY_LINES`) imported by the issue UI context; if C is late A creates the file with the texts quoted in this document and C edits wording later (C owns the file after creation).

### Package B: admin and provider-prescribing UI

Owned files: `templates/admin/*` (list in 5.6), `templates/provider_rx/*`, `static/css/clinical.css`, `static/js/clinical-common.js`, `rx_prescribe.js`, `rx_list.js`, `rx_detail.js`, `rx_dashboard.js`, `admin_verification.js`, `admin_catalogue.js`, `admin_inventory.js`, `admin_dispensing.js`, `admin_reports.js`, `tests/test_ui_clinical.py`. Shared-file edits by small `Edit` only: `templates/base.html` (admin nav branch, admin `home_href`, provider "Prescriptions" nav item under `rx_section.show`), `templates/provider_dashboard.html` (the one include line of 5.3), `static/css/site.css` only if a missing shared class is unavoidable (prefer `clinical.css`). B does not write Python. B builds against the JSON shapes in 5.5 and the context table in 5.6, using sample dicts in `tests/test_ui_clinical.py` to render every template with `render_template` inside `app.test_request_context`, with the empty case and a populated case. Follow `docs/DESIGN_SYSTEM.md` (no emoji, no em dash, flat, semantic colour classes, `empty_state` macro, icons from the sprite, WCAG focus, 44 px touch targets). All strings that state limits or warnings are copied verbatim from this document (3.4, 3.5, 4.4, 2.2).

### Package C: patient and counsellor views, seed, docs

Owned files: `routes/patient.py` (prescriptions list route, schedule form changes, dashboard widget data, care-team data), `routes/rx_patient.py` (after A's stub), `routes/provider.py` (remove `send_prescription` and its import use, medications hook data; the registration line at the bottom belongs to A: do not delete it), `routes/provider_meds.py` (after A's stub), `templates/my_prescriptions.html`, `templates/patient_dashboard.html`, `templates/schedule.html`, `templates/wellness_report.html` (remove the form, add the Medications panel), `templates/rx_patient/` (`detail.html`; it extends the shared print template for printing, owned by B), `static/js/rx_patient.js`, `utils/rx_text.py`, `scripts/seed_demo.py`, `docs/` additions (a short `docs/PRESCRIPTIONS.md` operator guide may be added; the lead updates TRACKER, STATUS and MEMORY), the changed existing tests of section 12 for patient and provider files, `tests/test_rx_patient.py`, `tests/test_provider_meds.py`. Requests to the lead: privacy page text about prescriptions and account deletion (`routes/pages.py`), `docs/PRD.md` FR-APT-06 status.

### Contracts between packages

| Contract | Provider | Consumer | Frozen form |
|---|---|---|---|
| Models and table names | A | B (none), C | section 6 names and columns |
| Service functions | A | C (and A's own routes) | section 14 signatures |
| Blueprint stubs `rx_patient_bp`, `provider_meds_bp` | A (stub), C (content) | app | names above |
| Endpoint names | A for provider and admin, C for patient | B, C | tables in 5.2, 5.3, 5.4 (templates call `url_for` with them) |
| JSON shapes | A | B, C | 5.5 |
| Template names and context | B names, A fills | | 5.6 |
| `rx_section` context processor | A | B (`_dashboard_section.html`), provider dashboard | 5.3 |
| Print template `provider_rx/print.html` | B | A, C routes | context `rx`, `site_url`, `printed_at` |
| Warning, limit and consent wording | this document, then `utils/rx_text.py` (C) | A, B | verbatim |
| Fixtures `admin_client`, `desk_client`, `doctor_client` | A | B, C tests | 12 |
| Idempotency headers | B sends, A requires | | 5.1 |

Order: A hour 1 (stubs, models, errors, roles) unblocks B and C. A then ships migrations and services (C needs `list_for_patient`, `get_for_patient`, `medication_lines_for_staff`, `request_pharmacy`, `erx_status`, `set_erx_consent` early). B works against the JSON contract with sample data; A's routes land last. Integration pass: the lead runs the whole suite, then the seed script and a manual walk: sign up a doctor with the invite code, create the admin by CLI, verify the doctor, add and verify two demo medicines with two admins, receive stock, book and start a consult, issue, send to desk, dispense, check the log and the patient view.

## 15. Needs legal and pharmacist review before real use

None of this is legal advice; every item is UNVERIFIED against primary text unless it says otherwise. Sources and what was and was not found are in [research/prescribing-inventory.md](research/prescribing-inventory.md).

| Topic | Question for the reviewer | Why it matters here |
|---|---|---|
| Telemedicine Practice Guidelines 2020 (primary PDF not opened) | Exact definitions of first consult and follow-up (6 months, same condition, in-person), the list contents and the current notification of lists, whether in-person consults fall outside the lists, the consent and identification clauses, and whether clonazepam and clobazam are List A, B or C | `tpg_context`, `allowed_lists`, the 183-day window, and the sources conflict on benzodiazepines |
| Prescriber registration | Whether a manual NMC register check by an institution admin is acceptable; State Medical Council registers; re-verification period; AYUSH practitioners excluded | verification design |
| Digital prescription format | Whether an unsigned electronic prescription is valid for dispensing by outside pharmacies; whether a digital signature (Information Technology Act) is required; required fields (diagnosis on the prescription, generic names, patient age and sex which this app does not store) | print template and `/rx/<number>` |
| Drugs and Cosmetics Act 1940 and Rules 1945 | Schedule H prescribing and sale conditions, Schedule H1 register (3 years) and Schedule X, whether v1 "no H1, X or NDPS" is sufficient, draft G.S.R. 791(E) of 8 Sep 2026 (CCTV) if a real counter is run | `schedule` rules, controlled handling |
| NDPS Act 1985 | Confirm that excluding NDPS and psychotropic-substance medicines removes licensing duties | List C handling |
| Pharmacy Practice Regulations 2015 and pharmacy licensing | Whether an institution can run an in-house dispensing desk, who must supervise (registered pharmacist), whether a college dispensary needs a retail or institutional drug licence, whether the pharmacist name and registration captured at the desk is the right record, and whether returned medicines may be restocked (v1 says no) | the desk design and `dispenser_label` |
| Medical records and retention | Retention of outpatient prescriptions (the 2002 Regulations mention 3 years for indoor records; outpatient period not found), the patient's right to records within 72 hours, effect of the 2023 NMC regulation held in abeyance | no code deletes prescriptions, ledger or audit; patient account deletion currently deletes the patient's prescriptions |
| DPDP Act 2023 and Rules 2025 | Health data and prescription data under the Rules (notified Nov 2025, phased), Rule 8(3) one-year log retention as reported by secondary sources, erasure versus statutory retention, consent artefacts for e-prescriptions, breach duties, role of the institution versus the operator as fiduciary | consent design (3.6), audit retention, deletion behaviour |
| Medical device and software regulation | Whether the duplicate-therapy and allergy text warnings are decision support that needs CDSCO classification; wording "not a drug interaction check" | warnings in 3.5 |
| Professional rules for doctors | Whether a doctor may prescribe to a student of the institution where they work, conflict-of-interest, student counsellor-doctor information sharing, duty to maintain a consultation record | provider sharing rules and the consult record |
| Product policy numbers | Item limit, duration caps, consult window, review period, expiry maximum | defaults in section 8 are policy, not regulation |
| Patient-facing notices | Privacy page, terms and the consent text for e-prescriptions marked "Draft pending legal review" | package C copy |
