# Operations runbook

Owner: Q1a. Code: `utils/jobs.py`, `utils/mailer.py`, `utils/crisis.py`, `utils/logging_setup.py`, `routes/ops.py`.

## Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `JOBS_INPROCESS` | on when `FLASK_ENV=production`, else off | Run the job worker as a thread inside the web process |
| `JOB_LOCK_TIMEOUT` | 300 | Seconds a job may stay `running` before it is requeued (visibility timeout) |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | unset | Outgoing mail. Port 465 = SSL, anything else = STARTTLS. 15 s timeouts |
| `CONTACT_RECIPIENT` | unset | Inbox for contact-form messages |
| `CRISIS_ESCALATE_MINUTES` | 15 | Gap between escalation levels |
| `CRISIS_ESCALATION_EMAIL` | unset | Emailed at level 2 and 3. Body has the institution name, event id and time only |

With `SMTP_HOST` or `CONTACT_RECIPIENT` unset, contact emails are skipped, the job ends `done` with `last_error='skipped:smtp_unset'`, and the `ContactMessage` stays `new`. Read those rows in the database (or the future admin view).

## Job queue

Table `jobs` is a transactional outbox: the producer calls `utils.jobs.enqueue(...)` inside its own transaction and commits with its data, so a job exists if and only if the data it belongs to was saved. No Redis.

Status: `queued -> running -> done`. A failed attempt becomes `failed` with `run_at = now + U(0, min(15 min, 5 s * 2^attempts))` (full jitter). After `max_attempts` (default 5, crisis jobs 10) the job is `dead` and one ERROR line `job dead id=<n> kind=<kind>` is logged. `attempts` counts failed attempts and lock timeouts. A `PermanentJobError` or an unknown kind goes `dead` at once.

`last_error` is an exception class name or a short code (`ValueError`, `lock_timeout`, `unknown_kind`, `skipped:smtp_unset`). It never holds message text or patient text, and neither do the logs.

Handlers run at least once, so every handler is idempotent (the second run does nothing). Register one with `@register('kind')` in `utils/jobs.py`'s registry; `_load_handlers()` imports the modules that hold them.

### Running the worker

- In process: set `JOBS_INPROCESS=1` (default in production). One daemon thread starts with the app; it works under `gunicorn --worker-class eventlet --workers 1` (gunicorn's eventlet worker patches `threading`). It stops cleanly at exit. It does not start for `flask db upgrade` or other `flask` CLI commands, or in the reloader parent process.
- Separate process (when LLM work or deploys start to hurt the web process): set `JOBS_INPROCESS=0` on the web service and run `flask jobs-worker` as a second service with the same env and `DATABASE_URL` (a Render background worker, or a second container command). Several workers are safe: claims use `FOR UPDATE SKIP LOCKED` on PostgreSQL and a compare-and-set `UPDATE` on SQLite.
- One-off: `flask jobs-run-once` processes everything due, then exits. `flask jobs-stats` prints counts per status and the age of the oldest due job.

### Dead jobs

1. `flask jobs-stats` (or `/ready`, field `checks.jobs.dead`).
2. `SELECT id, kind, payload, attempts, last_error, finished_at FROM jobs WHERE status='dead';` (payloads hold ids only).
3. Fix the cause (SMTP credentials, missing row). To retry: `UPDATE jobs SET status='queued', attempts=0, run_at=now(), last_error=NULL, finished_at=NULL WHERE id=<n>;`. Safe because handlers are idempotent.
4. A dead `crisis_alert` or `crisis_escalate` job logs CRITICAL `crisis job DEAD ... event=<id>`: treat it as an incident. Open the provider dashboard and make sure someone has acknowledged that event.
5. A dead `send_email` marks its `ContactMessage` `email_failed`; answer it from the database.

## Crisis durability and escalation timeline

`utils.crisis.record_crisis(user_id, source, severity, reason)` adds a `CrisisEvent` and a `crisis_alert` job (key `crisis-alert:<event_id>`) to the caller's transaction and does NOT commit. Callers: assessment save (with the assessment), chat API, legacy socket chat, journal create (with the entry). `reason` is a code; no text is stored.

If the write fails the request fails visibly (journal: error flash, assessment: HTTP 500, chat: `alert_recorded: false`), an ERROR line carries only user id, source and exception class, and the student still gets the emergency text and helplines (they are computed before the write). The journal text is rule-checked with `ai.severity.classify`; no LLM is involved.

| Time | What happens |
|---|---|
| t0 | Event and `crisis_alert` job committed |
| ~t0 (the commit wakes the in-process worker, about a second; a separate `flask jobs-worker` process waits up to 60 s) | `crisis_alert`: one `Notification` per provider of the student's institution; schedules `crisis_escalate` level 1 |
| t0 + 15 min | Level 1, if `acknowledged_at` is still empty: `escalation_level=1`, `escalated_at` set, providers re-notified |
| t0 + 30 min | Level 2: same, and email to `CRISIS_ESCALATION_EMAIL` (if SMTP is configured) |
| t0 + 45 min | Level 3 (last): same, plus ERROR log `crisis alert UNACKNOWLEDGED at final escalation level event=<id>`. No further jobs |

Acknowledging the event (provider dashboard) stops the chain at the next tick. A provider sees unacknowledged events of their institution regardless of assignment (decision P-02), and that view is audited elsewhere. If an institution has no providers, nobody is notified but the escalation emails and log lines still fire; set `CRISIS_ESCALATION_EMAIL` in production.

## Health and readiness

- `GET /health`: liveness. Constant `200 {"status":"ok"}`, no DB, no auth, exempt from rate limit and CSRF. The Dockerfile HEALTHCHECK and the Render health check use it. Do not point restart probes at `/ready`: a DB blip would restart the only instance.
- `GET /ready`: readiness. Runs `SELECT 1`, compares `alembic_version` with the head in `migrations/` (in production a missing table counts as a mismatch; in dev/test with `create_all` it reports `untracked`), reads job counts. 200 with `{"status":"ready","checks":{...}}` (queued, dead, oldest due age, `jobs_warning: stale_jobs` when the oldest due job is more than 10 minutes old, which means the worker is not running), or 503 `{"status":"not_ready"}` with no detail (details are in the ERROR log). Point an uptime monitor at it and alert on 503, `dead > 0` or `stale_jobs`.

## Logs

- Every response carries `X-Request-ID`. An inbound `X-Request-ID` is kept if it matches `[A-Za-z0-9_-]{1,64}`, otherwise a new id is made.
- One access line per request (logger `access`): `request method=GET path=/x status=200 duration_ms=12 user_id=7 request_id=...`. No query string, no body, no email (`user_id` is an integer or `-`).
- A log record factory masks emails, `Bearer`/`Basic` tokens, `password=`/`token=`/`api_key=`/`secret=` values and long quoted strings in every record, for every handler. It is a safety net: do not log patient text in the first place.
- Find a request: grep the `request_id` from the response header, or from a user's error report.
