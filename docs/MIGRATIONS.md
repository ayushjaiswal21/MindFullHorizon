# Database migrations (Alembic via Flask-Migrate)

Schema source of truth: `models.py`. Baseline migration: `migrations/versions/0001_baseline.py`
(SQLite batch mode is on in `migrations/env.py`).

The database comes from `DATABASE_URL` (default `instance/mindful_horizon.db`). All commands run from the
project root with `FLASK_APP=app.py`.

| Task | Command |
|------|---------|
| New / empty database | `SKIP_CREATE_ALL=1 flask db upgrade` |
| After editing models | `SKIP_CREATE_ALL=1 flask db migrate -m "what changed"`, review the file, then `flask db upgrade` |
| Roll back one step | `flask db downgrade` |
| Current revision | `flask db current` |

PowerShell: `$env:SKIP_CREATE_ALL=1; flask db upgrade`.

## Why `SKIP_CREATE_ALL`

App start runs `db.create_all()` (`utils/database_utils.py`) when the `users` table is missing. That is the
dev/test bootstrap. If it ran first, `upgrade` would fail with "table already exists". It is skipped
automatically when `FLASK_ENV=production`, so production schema changes only come from migrations:
run `flask db upgrade` before starting the app.

## Existing dev database made by `create_all`

It has no `alembic_version` table. Either delete it and run `upgrade`, or mark it as current:
`flask db stamp 0001` (only if its schema equals the baseline).

`tests/test_db.py::test_migration_upgrade_matches_create_all` fails if `models.py` changes without a new migration.

## Revision log

| Rev | What |
|-----|------|
| 0001 | Baseline |
| 0002 | `jobs`, `contact_messages`, `audit_log`, `consent_records`, `provider_patients`, `analytics_events`, crisis escalation columns |
| 0003 | Idempotency keys, one-per-day and no-double-booking constraints, `points_ledger`, value CHECKs, two hot-path indexes (below) |

Each revision must upgrade a fresh SQLite DB and be PostgreSQL-compatible; `tests/test_migrations.py` checks upgrade,
downgrade one step and back, no drift against `models.py` (`alembic.autogenerate.compare_metadata`), and that the
constraints really reject bad rows. After editing models run `flask db migrate`: it must say "No changes in schema
detected" once your revision is in. Delete trial files.

## Data conventions (owner: schema agent)

- **Stored timestamps are naive UTC** (`utils.timeutil.utcnow()`; no schema change planned). Never write
  `datetime.now()` or an aware datetime into a `DateTime` column.
- **A patient's "day" is the IST calendar day** (`Asia/Kolkata`, `utils.timeutil.ist_today()`, `ist_day_bounds(day)` gives
  the UTC range of an IST day, `to_ist_date(ts)` converts a stored timestamp). `Date` columns that mean "the patient's
  day" hold the IST date: `digital_detox_logs.date`, `medication_logs.log_date`, `gamification.last_activity`.
  Appointment `date` and `time` are IST wall-clock text/date; compare them with `ist_now()`.
- `zoneinfo` has no tz database on Windows; `tzdata` is in `requirements.txt`, and `timeutil` falls back to a fixed
  UTC+05:30 (India has no DST) if it is missing.
- **Daily Mood** is stored 1-10 everywhere (`mood_logs.mood_score`, `assessments.score` for type `Daily Mood`). The old x2 scaling
  (which assumed 1-5) is gone; bands: 1-3 negative, 4-6 neutral, 7-10 positive. No historical mood data exists, so nothing was
  converted. Mood stays a time series (several entries a day are allowed); it is deduplicated by `client_request_id`, not by day.

## Idempotency (0003)

Optional and backward compatible. A client sends `Idempotency-Key: <key>` or a `client_request_id` JSON/form field,
format `[A-Za-z0-9._-]{8,64}` (a UUID works). Unique `(user_id, client_request_id)` on `assessments`, `mood_logs`,
`appointments`, `goals`, `journal_entries`, `breathing_exercise_logs`, `yoga_logs`, `music_therapy_logs` (NULL never collides).
A replay returns the first row (HTTP 200, same body for JSON routes; the same redirect for form routes), a malformed key
is 400 `Invalid request id.` Helper: `utils/idempotency.py`.

Natural constraints (they also protect non-HTTP retries):

| Table | Constraint |
|-------|-----------|
| `medication_logs` | `UNIQUE(medication_id, log_date)` (IST day); later duplicates answer `already_logged: true` |
| `digital_detox_logs` | `UNIQUE(user_id, date)` (was a plain index) |
| `appointments` | partial unique `uq_appt_active_slot (provider_id, date, time)` and `uq_appt_active_user_slot (user_id, date, time)` WHERE live AND `provider_id IS NULL` (double submits of a provider-less request); a reject/cancel/complete frees the slot; a lost race is 409 |
| `points_ledger` | `UNIQUE(user_id, ref)`, `ref = '<activity>:<row id>'`: a replayed award changes nothing; the daily cap (3 paid awards per activity per IST day) counts ledger rows |

Points and the streak change in single `UPDATE ... SET points = points + :n` statements (streak: one compare-and-set per IST
day), never read-modify-write. Known limit: on PostgreSQL two truly simultaneous awards can both pass the cap check; the
ledger still guarantees one award per activity.

CHECKs added: appointment live slots above, `mood_logs.mood_score BETWEEN 1 AND 10`, breathing/yoga/music
`duration_minutes BETWEEN 1 AND 180`, goals (`status`, `priority` enums, non-negative values), `gamification` non-negative.
Indexes: `clinical_notes (patient_id, session_date)`, `notifications (recipient_id, created_at)`.
0003 repairs old rows first (never fails on legacy duplicates): extra live appointments for one slot become `cancelled`
(earliest id wins), duplicate detox/medication logs keep one row, out-of-range values are clamped.

## Appointment states (`utils/state.py`)

`pending -> accepted | rejected | cancelled`, `accepted -> completed | cancelled`; the rest are terminal; `booked` is a legacy alias
of `accepted`. Every change goes through `transition(appt, new, actor)`, one compare-and-set UPDATE; an illegal move or lost
race raises `TransitionError`, routes answer 409 with a generic message. Who may move: patient cancels (pending or accepted);
provider accepts, rejects (pending), completes, cancels (accepted).
