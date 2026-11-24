# Queue, Idempotency, and Reliability Research (MindFullHorizon)

Researched 2026-11-24. Every external fact carries a URL. "UNVERIFIED" means I could not confirm it from a source I opened (stated from general knowledge or a search snippet). "Judgement" means my recommendation, not a sourced fact.

Context: Flask 2.3, Flask-SQLAlchemy 3, SQLite dev / PostgreSQL prod on Render or Docker, ONE gunicorn eventlet worker (Flask-SocketIO), no Redis, small team, no Kubernetes.

---

## 1. Background job options for THIS situation

### Constraints that decide the answer

| Constraint | Source |
|---|---|
| Flask-SocketIO + gunicorn eventlet must run `-w 1`; scale by running several single-worker instances behind a sticky load balancer. | https://flask-socketio.readthedocs.io/en/latest/deployment.html |
| A SocketIO `message_queue` is only needed for more than one server process; "not required when using a single server process". With several processes (or an external emitter) it needs Redis, RabbitMQ or Kafka. | https://flask-socketio.readthedocs.io/en/latest/api.html and https://flask-socketio.readthedocs.io/en/latest/deployment.html |
| An external process (e.g. a worker) can emit to clients through a standalone `SocketIO(message_queue=...)` object created without `app`; it does not need eventlet itself. (From search snippets quoting Flask-SocketIO docs and the author; I did not read the exact docs section.) UNVERIFIED | https://flask-socketio.readthedocs.io/en/stable/deployment.html |
| Eventlet is in maintenance mode: "New usages of eventlet are now heavily discouraged", only bug fixes, retirement planned. Do not build new job code that depends on eventlet internals. | https://eventlet.readthedocs.io/en/latest/ |
| Render free tier: only web services, Postgres, Key Value. "Other service types don't support Free instances", so background workers and cron are paid. Free Postgres expires after 30 days and has no backups. Free Key Value is memory only and loses data on restart. | https://render.com/docs/free |
| Render Key Value paid instances persist to disk (journal+snapshot can lose up to the last second of writes). Use `noeviction` for job queues. | https://render.com/docs/key-value |
| Render prices (from the pricing page): worker/service compute from $7/mo (under 1 CPU, 512 MB), $25/mo (1 CPU, 2 GB); Key Value $10/mo for 256 MB; Postgres entry paid plans $6/mo (256 MB) and $19/mo (1 GB). Re-check before budgeting. | https://render.com/pricing.md |
| Render cron: $1/mo minimum per cron job, 12 hour max run, at most one run of a given cron job active at a time, UTC schedules. | https://render.com/docs/cronjobs |
| Dev machine is Windows. RQ workers need `fork()` and "don't run natively on Windows". | https://python-rq.org/docs/ |

### Comparison

| Option | Extra infra | Fits eventlet / Flask-SocketIO | SQLite dev | Operational cost | Main failure modes | Source |
|---|---|---|---|---|---|---|
| **DB-backed jobs table / transactional outbox** (own, about 150 lines) | None (uses the existing DB) | Yes: poll loop as `socketio.start_background_task`, or a separate plain-Python process | Yes (same table) | $0 now; $7/mo only if you later split the worker out | Polling load on DB; hand-rolled bugs; no dashboard; the in-process worker dies with the web process (lease expiry recovers jobs) | Outbox: https://microservices.io/patterns/data/transactional-outbox.html ; SKIP LOCKED: https://www.postgresql.org/docs/current/sql-select.html |
| **Huey** (SQLite / Postgres / Redis storage) | None for SQLite or Postgres storage | Supports thread, process and greenlet workers (greenlet = gevent-flavoured, eventlet not stated) | Yes (`SqliteHuey`) | Low; `PostgresHuey` needs psycopg 3.2+ and LISTEN/NOTIFY; PgBouncer transaction pooling breaks LISTEN | Retries default to 0 (must be set); no per-job unique idempotency column of your own; thin ecosystem | https://huey.readthedocs.io/en/latest/ ; https://huey.readthedocs.io/en/latest/api.html |
| **Procrastinate** (Postgres only) | None beyond Postgres | Worker and CLI require an async connector even for a sync app; sync tasks run in threads | No: needs Postgres in dev (use Docker) | Low; one worker process; LISTEN/NOTIFY wake-ups | A killed worker leaves "doing" jobs stalled until you add a periodic retry task (heartbeat based, default 30 s stale); jobs sharing a lock can block | https://procrastinate.readthedocs.io/en/stable/discussions.html ; https://procrastinate.readthedocs.io/en/stable/howto/production/retry_stalled_jobs.html |
| **RQ** | Redis (Redis 5+ or Valkey 7.2+) | Separate fork-based worker; no eventlet issue, but no native Windows | Needs Redis in dev | Redis $10/mo+ paid on Render; free Redis loses queued jobs | Redis durability and `noeviction` must be configured; fork-only | https://python-rq.org/docs/ ; https://render.com/docs/key-value |
| **Celery** | RabbitMQ or Redis (both listed "Stable") | Has an eventlet pool (`-P eventlet`), with caveats (no long blocking, some C-extension libs cannot be monkeypatched) | Needs a broker in dev | Highest config and moving parts | `acks_late` gives at-least-once and can run a task twice after a crash, so tasks must be idempotent; `retry_backoff` and `retry_jitter` are built in; SQLAlchemy is not in the stable broker list | https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/index.html ; https://docs.celeryq.dev/en/stable/userguide/concurrency/eventlet.html ; https://docs.celeryq.dev/en/stable/userguide/tasks.html |
| **Dramatiq** | RabbitMQ or Redis | Not stated | Needs a broker in dev | Medium | No Postgres or SQLite broker listed | https://dramatiq.io/ |
| **APScheduler** | None | `GeventScheduler` only, eventlet not mentioned | Yes | Low | It is a scheduler, not a queue. "Job stores must never be shared between schedulers", "typically only one scheduler". Runs missed beyond `misfire_grace_time` are skipped, so reminders can silently vanish | https://apscheduler.readthedocs.io/en/3.x/userguide.html |
| **Render background worker / cron** | A paid Render service | Separate process, so no eventlet coupling | n/a | Worker from $7/mo; cron from $1/mo | These are hosting wrappers, not queues. You still need a queue or a poll loop inside them. Render lists Celery, Sidekiq, BullMQ and others as frameworks to run in a worker. | https://render.com/docs/background-workers ; https://render.com/docs/cronjobs |

### ONE recommended path now

**A `jobs` table in the existing database plus a small worker loop that you own.**

- It adds no infrastructure, works identically on SQLite and PostgreSQL, and fits the requirement that crisis alerts must never be lost: the job row is written in the same DB transaction as the event that caused it (transactional outbox, "messages are guaranteed to be sent if and only if the database transaction commits": https://microservices.io/patterns/data/transactional-outbox.html).
- Start the worker loop as a background task in the existing eventlet process. Keep its code plain Python with no eventlet imports, so the same `python -m app.worker` can run as a separate Render background worker (from $7/mo) later.
- Make the claim step portable (compare-and-set `UPDATE ... WHERE`, see section 2), and use `FOR UPDATE SKIP LOCKED` as a PostgreSQL optimisation only. Postgres documents SKIP LOCKED for "multiple consumers accessing a queue-like table" and warns it gives an inconsistent view, so it is not for general queries: https://www.postgresql.org/docs/current/sql-select.html
- Risk to check before relying on it: running the Google client inside eventlet. The grpc transport and eventlet monkey patching may not cooperate. UNVERIFIED. Use the REST transport (or `requests`/`httpx`) for Gemini, and prefer running LLM jobs in a separate plain-thread worker process.

### Upgrade path (in order, trigger-based)

1. **Split the worker out** to a Render background worker ($7/mo, https://render.com/pricing.md). No code change. Trigger: LLM jobs slow the web process, or deploys keep killing in-flight jobs.
2. **Add paid Render Key Value** ($10/mo, persistence on, `noeviction`: https://render.com/docs/key-value). It unlocks three things at once: SocketIO `message_queue` (needed to emit from the worker or to run more than one SocketIO process), shared rate-limit storage (Flask-Limiter says in-memory storage is per process and lost on restart: https://flask-limiter.readthedocs.io/en/stable/configuration.html), and RQ/Celery if wanted. Do not use the free Key Value for anything that matters (https://render.com/docs/free).
3. **Swap the hand-rolled jobs table for Procrastinate** if you want less custom code and are happy to run Postgres in dev (stalled-job retry and LISTEN/NOTIFY included), or **Celery/RQ on Redis** if you need fan-out, chains or rate limits. Keep the `jobs` table as the outbox: the web request still writes a row, and a relay enqueues it.

---

## 2. Reliable delivery patterns

| Pattern | What to do here | Source |
|---|---|---|
| **Transactional outbox** | Insert the job row inside the same transaction as the business write (assessment saved + crisis alert + notify job). A relay or worker then processes it. | https://microservices.io/patterns/data/transactional-outbox.html |
| **At-least-once + idempotent consumer** | The relay may deliver twice (crash after send, before recording). Consumers must be idempotent, e.g. track processed ids. Celery says the same: use `acks_late` only with idempotent tasks. | https://microservices.io/patterns/data/transactional-outbox.html ; https://docs.celeryq.dev/en/stable/userguide/tasks.html |
| **Retries with backoff and jitter** | Full jitter: `sleep = U(0, min(cap, base * 2^n))`. Equal jitter: `v/2 + U(0, v/2)`. Decorrelated: `min(cap, U(base, prev*3))`. Code from the AWS simulator. The Architecture Blog post itself argues "the solution isn't to remove backoff, it's to add jitter", and its 100-client simulation cut calls by more than half versus un-jittered backoff (search snippet, I could not fetch the post body). | https://github.com/aws-samples/aws-arch-backoff-simulator/blob/master/src/backoff_simulator.py ; https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/ |
| **Retry limits** | Retry at one layer only: three retries across five layers is a 243x load multiplier. Use a token bucket to cap retries. Set timeouts on every remote call. | https://builder.aws.com/content/3EumjoZascWd1oZiEgL8ORlv3qE/timeouts-retries-and-backoff-with-jitter |
| **Lease / visibility timeout** | `locked_until` is the lease. A worker that dies stops extending it, so the job becomes claimable again. Procrastinate does the same with 10 s heartbeats and a 30 s stale threshold. | https://procrastinate.readthedocs.io/en/stable/howto/production/retry_stalled_jobs.html |
| **Poison messages / dead-letter** | Count attempts on claim (so a job that crashes the worker is counted). At `max_attempts` set `status='dead'`, keep the row, alert. Permanent errors (400, validation) go dead immediately; only transient errors (408, 429, 5xx, timeouts) retry. | Gemini retry classes: https://aistudio.google.com/docs/troubleshooting |
| **Crisis alerts** | Separate `crisis_alerts` row (new -> notified -> acked -> escalated) written in the assessment transaction. The job only notifies. If not acked within a set time, re-notify and escalate by a second channel. The student-facing crisis resources must render synchronously and never wait for the queue. (Judgement.) | n/a |

### Job states

`pending -> running -> succeeded`; on failure `running -> pending` (with `run_after` = now + backoff) while `attempts < max_attempts`; else `running -> dead`. A `running` row whose `locked_until` has passed is treated as claimable (lease expiry).

### DDL (SQLite and PostgreSQL compatible; use JSONB for payload on Postgres if you like)

```sql
CREATE TABLE jobs (
  id               INTEGER PRIMARY KEY,            -- BIGSERIAL / GENERATED ... AS IDENTITY on Postgres
  type             VARCHAR(80)  NOT NULL,
  payload_json     TEXT         NOT NULL DEFAULT '{}',
  status           VARCHAR(12)  NOT NULL DEFAULT 'pending'
                   CHECK (status IN ('pending','running','succeeded','dead','cancelled')),
  attempts         INTEGER      NOT NULL DEFAULT 0,
  max_attempts     INTEGER      NOT NULL DEFAULT 5,
  run_after        TIMESTAMP    NOT NULL,           -- store UTC; Postgres: TIMESTAMPTZ
  locked_by        VARCHAR(80),
  locked_until     TIMESTAMP,
  last_error       TEXT,
  idempotency_key  VARCHAR(200) NOT NULL UNIQUE,    -- e.g. 'crisis:{alert_id}:email'
  created_at       TIMESTAMP    NOT NULL,
  finished_at      TIMESTAMP
);
CREATE INDEX ix_jobs_claim ON jobs (status, run_after);
```

Portable claim (correct on SQLite and Postgres; Postgres Read Committed re-checks the WHERE clause after a concurrent update, so only one claimer wins: https://www.postgresql.org/docs/current/transaction-iso.html):

```sql
-- 1. candidate
SELECT id FROM jobs
 WHERE run_after <= :now AND (status='pending' OR (status='running' AND locked_until < :now))
   AND attempts < max_attempts
 ORDER BY run_after LIMIT 1;
-- 2. compare-and-set claim; rowcount == 1 means you own it
UPDATE jobs SET status='running', locked_by=:w, locked_until=:now_plus_lease, attempts=attempts+1
 WHERE id=:id AND (status='pending' OR (status='running' AND locked_until < :now));
-- 3. reaper (run each loop): poison / exhausted
UPDATE jobs SET status='dead', last_error=COALESCE(last_error,'lease expired at max_attempts')
 WHERE status='running' AND locked_until < :now AND attempts >= max_attempts;
```

Postgres-only single-statement variant: `WITH c AS (SELECT id FROM jobs WHERE ... ORDER BY run_after LIMIT 1 FOR UPDATE SKIP LOCKED) UPDATE jobs j SET ... FROM c WHERE j.id=c.id RETURNING j.*` (SKIP LOCKED semantics: https://www.postgresql.org/docs/current/sql-select.html). `RETURNING` on SQLite needs 3.35+. UNVERIFIED.

Enqueue is idempotent: insert and catch `IntegrityError` on `idempotency_key` (treat as "already queued").

---

## 3. HTTP/API idempotency

Facts:

- IETF draft `draft-ietf-httpapi-idempotency-key-header` (version -09, Standards Track intent, still a draft): header value is an RFC 9651 Structured String, a UUID or similar random value is recommended. Retry while the first is in flight: **409 Conflict**. Same key with a different payload: **422**. Missing header on an operation that requires it: **400**. Key lifetime is not fixed; if you expire keys, publish the policy. Fingerprinting the request is optional but needed to detect payload mismatch. https://datatracker.ietf.org/doc/draft-ietf-httpapi-idempotency-key-header/
- Stripe (API v1): saves status code and body of the first request after execution begins, returns the same response for retries (including 500s); key up to 255 chars; keys may be pruned after at least 24 hours; compares incoming parameters and errors if they differ; validation failures and concurrent-conflict responses are not saved so they can be retried; all POSTs accept keys, GET and DELETE do not need them. https://docs.stripe.com/api/idempotent_requests
- Retrying side-effecting calls is only safe if the API is idempotent. https://builder.aws.com/content/3EumjoZascWd1oZiEgL8ORlv3qE/timeouts-retries-and-backoff-with-jitter

Two layers, use both:

| Layer | Use for | How |
|---|---|---|
| **Natural idempotency (unique constraints)**, preferred | Medication log (one per medication per day), daily mood (one per user per day), appointment slot, points awards | `UniqueConstraint(...)`; on `IntegrityError` return the existing row with 200 |
| **Idempotency-Key header** | Anything without a natural key: assessment save, award-points, free-form POSTs | Table + decorator below. Frontend generates a UUID per form render and re-sends it on retry; disable the button on submit as well |

Natural constraints (Postgres supports partial unique indexes: https://www.postgresql.org/docs/current/indexes-partial.html ; SQLAlchemy SQLite uses `sqlite_where`: https://docs.sqlalchemy.org/en/20/dialects/sqlite.html):

```python
UniqueConstraint("medication_id", "log_date", name="uq_medlog_med_day")
UniqueConstraint("user_id", "mood_date", name="uq_mood_user_day")
Index("uq_appt_active_slot", "provider_id", "starts_at", unique=True,
      postgresql_where=text("status IN ('requested','confirmed')"),
      sqlite_where=text("status IN ('requested','confirmed')"))
# Overlapping (not just equal) times: a Postgres exclusion constraint on a time range needs
# btree_gist. UNVERIFIED (general knowledge). A fixed slot grid + the unique index above is enough to start.
```

SQLAlchemy sketch (claim-first design: the key row is committed before the handler runs; a stale `in_progress` row older than 60 s is treated as abandoned):

```python
class IdempotencyKey(db.Model):
    user_id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(255), primary_key=True)
    request_hash = db.Column(db.String(64), nullable=False)
    status = db.Column(db.String(12), nullable=False, default="in_progress")
    response_code = db.Column(db.Integer); response_body = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)  # purge > 24h

def idempotent(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        key = request.headers.get("Idempotency-Key")
        if not key: return jsonify(error="Idempotency-Key required"), 400
        h = hashlib.sha256(request.method.encode() + request.path.encode() + request.get_data()).hexdigest()
        row = IdempotencyKey(user_id=current_user.id, key=key, request_hash=h)
        db.session.add(row)
        try: db.session.commit()                       # PK collision = retry or concurrent duplicate
        except IntegrityError:
            db.session.rollback()
            row = db.session.get(IdempotencyKey, (current_user.id, key))
            if row.request_hash != h: return jsonify(error="key reused with different request"), 422
            if row.status == "done": return Response(row.response_body, row.response_code, mimetype="application/json")
            if datetime.utcnow() - row.created_at < timedelta(seconds=60): return jsonify(error="in progress"), 409
            row.created_at = datetime.utcnow(); db.session.commit()   # abandoned: take over
        resp = make_response(fn(*a, **kw))
        if resp.status_code < 500:                     # do not cache server errors; client may retry
            row.status, row.response_code, row.response_body = "done", resp.status_code, resp.get_data(as_text=True)
            db.session.commit()
        else: db.session.delete(row); db.session.commit()
        return resp
    return wrapper
```

Limit: if the handler commits its domain write and the process dies before the key row is marked `done`, a retry re-runs the handler after 60 s. That is why the natural unique constraints stay as the second line of defence. A stricter variant puts the key insert and the domain write in one transaction (handlers must stop calling `commit()` themselves). Concurrent duplicates then block on the unique index; I believe Postgres waits for the first transaction to finish before raising the duplicate error. UNVERIFIED.

---

## 4. Resilience for calling Gemini

Verified retry facts (Google docs):

| Code | Meaning | Action | Source |
|---|---|---|---|
| 429 RESOURCE_EXHAUSTED | Rate limit hit (RPM, TPM, RPD, spend) | Retry with exponential backoff and jitter; lower rate or size | https://aistudio.google.com/docs/troubleshooting ; https://aistudio.google.com/docs/api-errors?generate-content=true |
| 503 UNAVAILABLE | Overloaded or down | Retry with backoff; "temporarily switch models" | same |
| 500 INTERNAL | Google-side error, can be caused by too-long input | Reduce input, retry | https://aistudio.google.com/docs/api-errors?generate-content=true |
| 504 DEADLINE_EXCEEDED | Prompt too large to process in time | Raise client timeout or shrink the prompt | same |
| 408 | Transient timeout | Retry | https://aistudio.google.com/docs/troubleshooting |
| 400 / 402 / 403 | Bad request, no credits, key or project problem | Do NOT retry | same |

Docs suggest about 1, 2, 4, 8 s waits with jitter and a maximum retry count; the Python SDK retries transient errors up to 4 times from about 1 s to a 60 s maximum (https://aistudio.google.com/docs/troubleshooting). That worst case is far too long for an interactive request. Set your own tighter budget.

Recommended stack for interactive (user waiting) calls (judgement unless cited):

| Layer | Setting |
|---|---|
| Timeouts | Connect 3 s, read 20 s, total deadline about 25 s. Set on the client (parameter names differ by SDK; check the SDK you use). AWS: timeouts on every remote call, with connect and request timeouts: https://builder.aws.com/content/3EumjoZascWd1oZiEgL8ORlv3qE/timeouts-retries-and-backoff-with-jitter |
| Retries | At most 2 retries inside a request, only for 408/429/5xx/timeouts, full jitter, honour a total deadline. In background jobs, use the `jobs` table retries (up to 5 with a cap of several minutes) instead of sleeping in-process. Do not retry at several layers. |
| Circuit breaker | States closed / open / half-open (Fowler: threshold trips it, reset timeout, one trial call in half-open: https://martinfowler.com/bliki/CircuitBreaker.html). Suggested: open after 5 consecutive failures, stay open 30 s, then one trial. Single process means an in-memory breaker is enough. Caveat: AWS finds breakers add modal behaviour that is hard to test and prefers a local retry token bucket (https://builder.aws.com/content/3EumjoZascWd1oZiEgL8ORlv3qE/timeouts-retries-and-backoff-with-jitter). Keep it about 30 lines, or use only the token bucket. |
| Bulkhead | A semaphore of 4 to 8 concurrent Gemini calls; acquire with a short timeout, and on failure go straight to fallback. This stops LLM latency from starving the single eventlet worker that also serves SocketIO. |
| Degradation order | 1. Gemini (primary model) 2. second model (the doc says switching models is a valid response to 503) 3. cached answer for identical or similar prompt 4. rule-based/template reply with static helplines. Crisis keyword screening must be rule-based and run before and independent of the LLM. |
| Cost / token budget | `max_output_tokens` cap, prompt length cap, per-user daily call or token cap, log token usage from the response metadata, a global monthly budget alarm in Google Cloud / AI Studio. A 504 is a signal the prompt is too big. |
| Async | Do not call `asyncio.run` inside sync views under eventlet; use the synchronous client. (General knowledge, UNVERIFIED.) |
| Non-interactive uses (summaries, reports, nightly insights) | Always a `jobs` row, never inline. |

Hedging is not needed (it multiplies LLM spend and load).

---

## 5. Database state integrity

### State machines

Keep the allowed-transition table in code, and enforce with a compare-and-set UPDATE so two racing requests cannot both win:

```python
ALLOWED = {"requested": {"confirmed","cancelled"}, "confirmed": {"completed","cancelled","no_show"},
           "completed": set(), "cancelled": set(), "no_show": set()}
# UPDATE appointments SET status=:new, version=version+1 WHERE id=:id AND status=:old  -> rowcount==1 or 409
```

| Entity | States | Notes |
|---|---|---|
| Appointment | requested -> confirmed -> completed; requested or confirmed -> cancelled; confirmed -> no_show | `CHECK (status IN (...))` replaces free text; partial unique index on active slots (section 3) |
| Assessment | in_progress -> submitted -> scored -> reviewed (if a provider reviews) | Scoring runs as a job; "submitted" is the outbox moment |
| Crisis alert | new -> notified -> acked -> resolved; new or notified -> escalated | Time-to-ack is a core metric |

### Optimistic locking

SQLAlchemy `version_id_col`: the UPDATE includes the old version in WHERE and bumps it; zero matched rows raises `StaleDataError`. Needs a NOT NULL integer column; it applies at `Session.flush()` only, bulk `Query.update()` / `delete()` bypass it. https://docs.sqlalchemy.org/en/20/orm/versioning.html
Use it on appointments and provider-edited records. Catch `StaleDataError`, reload, return 409.

### Atomic counters

`UPDATE users SET points = points + :n WHERE id = :id` is safe: in Postgres Read Committed a concurrently updated row is waited for and the WHERE is re-evaluated against the new version (https://www.postgresql.org/docs/current/transaction-iso.html). Better: an append-only `points_ledger` table with `UNIQUE(user_id, event_key)`, so a repeated award is rejected by the database, and update the counter in the same transaction (the counter becomes a cache of `SUM(ledger)`). Do not read-modify-write in Python.

### Isolation and engine settings

| Topic | Guidance | Source |
|---|---|---|
| Postgres default | Read Committed. Stay on it and use constraints, atomic UPDATEs and compare-and-set. REPEATABLE READ / SERIALIZABLE need a retry loop on SQLSTATE 40001. | https://www.postgresql.org/docs/current/transaction-iso.html |
| SQLite WAL | `PRAGMA journal_mode=WAL` persists in the file. Readers and the writer run concurrently but there is only one writer at a time; does not work on network filesystems; long-lived readers can stop checkpoints and make the WAL grow. | https://www.sqlite.org/wal.html |
| SQLite pragmas | `busy_timeout` (e.g. 5000 ms) so the second writer waits instead of failing with "database is locked"; `foreign_keys=ON` per connection (off by default); `synchronous=NORMAL` in WAL can lose the last commits on power loss (fine for dev). | https://www.sqlite.org/pragma.html#pragma_busy_timeout |
| SQLite FKs in SQLAlchemy | Register an engine `connect` event that runs `PRAGMA foreign_keys=ON` (also for `create_all`). | https://docs.sqlalchemy.org/en/20/dialects/sqlite.html |
| pysqlite transaction quirk | The legacy driver mode does not emit BEGIN for SELECT/DDL/SAVEPOINT, so SAVEPOINT and rollback behave unexpectedly; apply the documented workaround if you use nested transactions in tests. | https://docs.sqlalchemy.org/en/20/dialects/sqlite.html |
| Dev/prod parity | Run the job-claim and idempotency tests against Postgres in CI (Docker). SQLite cannot reproduce row-lock behaviour. (Judgement.) | n/a |

### Constraints

Add `CHECK` on status columns and numeric ranges (PHQ-9 item 0-3, mood 1-5, etc.), `NOT NULL`, real foreign keys with `ON DELETE` rules, and unique constraints from section 3. Name every constraint (needed for Alembic batch on SQLite).

### Soft delete vs hard delete for health data (judgement plus legal context)

- Default for clinical-like records (assessments, appointments, medication logs, crisis alerts): soft delete or status = cancelled / voided with `deleted_at` + `deleted_by`, because accidental deletion is irreversible and providers may need history. Hard delete (or irreversible anonymisation) only through an explicit erasure workflow with its own audit entry.
- India's DPDP Act gives data principals a right to correction and erasure, and the Rules reportedly require action within 90 days; breach-notification timing sources conflict. Secondary sources only, not the Gazette text, so confirm with counsel before relying on any number. UNVERIFIED. https://www.dpdpa.com/dpdpa2023/chapter-3/section12.html and https://www.mondaq.com/india/data-protection/1708164/digital-personal-data-protection-rules-2025-notified
- Soft-deleted rows must be excluded by default in queries and in unique indexes (add `deleted_at IS NULL` to partial uniques).

### Audit log (who accessed which patient's data)

Append-only table `audit_log`: `id, ts_utc, actor_user_id, actor_role, action (view/list/export/create/update/delete/login_fail), resource_type, resource_id, patient_user_id, request_id, ip, outcome (ok/denied), reason`. Rules: write on every provider read of a student record and every denied access; never store the health content itself; the app DB user has INSERT and SELECT only (no UPDATE/DELETE); copy to read-only storage on a schedule; alert on log gaps. OWASP: log authentication and access-control failures and access to sensitive data, do not log health information or PII in free text, build in tamper detection, and use an interaction identifier to link events. https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html

### Migrations and backups

- Alembic batch mode is required on SQLite for anything other than `add_column` (it does "move and copy": reflect, create new table, copy, drop, rename). Name constraints via `naming_convention`; unnamed CHECKs are dropped from the recreated table (Boolean/Enum need names); disable `PRAGMA foreign_keys` during batch migrations. https://alembic.sqlalchemy.org/en/latest/batch.html
- Discipline: one migration per change, test `upgrade` on a copy of prod data, additive first (expand), backfill, then constrain (contract), never edit a shipped migration. (Judgement.)
- Render Postgres: paid databases get point-in-time recovery (3 days Hobby, 7 days Pro+); a restore creates a NEW instance you verify before repointing; logical exports are kept 7 days; free databases get no backups. Free Postgres also expires 30 days after creation. https://render.com/docs/postgresql-backups and https://render.com/docs/free
- Restore drill (judgement): monthly, restore to a new instance, run row counts and an app smoke test, record the time taken. An untested backup is not a backup. Keep an off-platform `pg_dump` weekly (documented as supported: https://render.com/docs/postgresql-backups).

---

## 6. Operability

| Endpoint | Purpose | Checks | Notes |
|---|---|---|---|
| `/health` (liveness) | "Process is alive and the event loop is responsive" | Returns 200 with no DB or external calls | Point Render's `healthCheckPath` here. Render: 2xx/3xx is healthy, must answer within 5 s; after 15 s of failures traffic stops, after 60 s the instance is restarted; deploys wait for checks to pass (15-minute limit). https://render.com/docs/health-checks |
| `/ready` (readiness) | "Safe to take traffic and do work" | `SELECT 1` with short timeout; oldest pending job age; count of dead jobs; unacked crisis alerts older than threshold | Return 503 with a JSON body of which check failed. Do NOT use `/ready` as the Render restart probe: a DB blip would restart the only instance and drop SocketIO sessions. Use it for external uptime monitoring and humans. (Judgement based on the restart behaviour above.) |

Logging: one JSON object per line to stdout (stdlib `logging` with a JSON formatter such as python-json-logger or structlog; package choice UNVERIFIED). Fields: `ts, level, msg, request_id, user_id (not name), route, status, duration_ms, job_id, job_type, attempt`. Generate `request_id` in a `before_request` hook (or accept an inbound `X-Request-ID`), return it in a response header, and copy it into the job payload so a job log line can be tied to the request. Never log health content or tokens (OWASP: https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html).

Metrics worth tracking and suggested alert thresholds (all thresholds are judgement; tune after a month of data):

| Metric | How to get it cheaply | Alert when |
|---|---|---|
| Job lag (now - `run_after` of oldest pending) | `/ready` query | over 2 min for normal jobs; over 30 s for crisis notify |
| Dead jobs | `COUNT(*) WHERE status='dead'` | any (page for crisis types) |
| Job failure rate | failed attempts / total in 15 min | over 20 percent |
| LLM latency p95 and error rate (429/5xx/timeouts) | log duration and status per call | p95 over 15 s, or errors over 10 percent in 5 min; breaker open at all |
| LLM tokens / spend per day | log usage per call | over 80 percent of daily budget |
| Crisis alert time-to-ack | `acked_at - created_at` | unacked after 10 min (escalate), median trend weekly |
| DB: `database is locked` or pool timeouts | count log lines | any in prod; recurring in dev means missing `busy_timeout` |
| 5xx rate and p95 request latency | access log | 5xx over 2 percent for 5 min |

For a small team, send these to one place: Render logs plus a free uptime pinger on `/ready`, an email or Slack webhook sent from the app itself for dead jobs and unacked crisis alerts. Do not run Prometheus or Grafana yet.

---

## 7. Recommended design for this project

**Build first (week 1): correctness at the database, no new infrastructure.**
1. Unique constraints and CHECKs from sections 3 and 5 (medication per day, mood per day, active appointment slot, status CHECK), `foreign_keys=ON`, WAL and `busy_timeout` on SQLite, and `points = points + n` through a `points_ledger`. Reason: this removes duplicate rows and the points race with zero new moving parts, and it protects against every retry path, not only HTTP ones.
2. `/health` and `/ready`, JSON logs with `request_id`. Reason: you cannot operate what you cannot see, and it is a few dozen lines.

**Build second (weeks 2-3): the `jobs` table + worker loop + `crisis_alerts`.** Crisis detection writes the alert row and the notify job in the assessment's transaction; the worker retries with full jitter to `max_attempts` of about 20, then escalates and marks dead; unacked alerts older than 10 minutes surface on `/ready` and by email. Reason: this is the only part that must never fail, and the outbox gives that guarantee on SQLite and Postgres alike. Move Gemini work that nobody is waiting for into jobs here too.

**Build third: wrap Gemini.** One module with timeouts, 2 retries with jitter on 408/429/5xx, a semaphore bulkhead, a small circuit breaker, a template fallback, and a token cap. Add the `Idempotency-Key` decorator to assessment save, appointment booking and award-points, with the UI sending a UUID per form render. Reason: interactive calls cannot use the queue, and the decorator covers endpoints that have no natural key.

Then: `version_id_col` on appointments, transition table, `audit_log`, a monthly restore drill.

**Do NOT build yet:** Celery/RabbitMQ, Kubernetes, a Redis dependency (until you need more than one SocketIO process or shared rate limits), Prometheus/Grafana, a full distributed circuit-breaker library, Postgres exclusion constraints, event sourcing, hedged LLM requests, new eventlet-specific code (eventlet is in maintenance mode).

**Upgrade triggers:** worker contention with the web process -> separate $7 Render worker; second SocketIO process, shared rate limiting, or fan-out workloads -> paid Key Value with persistence and `noeviction` (then RQ or Celery, or Procrastinate if staying Postgres-only).

---

## Source index

- Flask-SocketIO deployment: https://flask-socketio.readthedocs.io/en/latest/deployment.html ; API: https://flask-socketio.readthedocs.io/en/latest/api.html
- Eventlet status: https://eventlet.readthedocs.io/en/latest/
- Postgres SELECT / SKIP LOCKED: https://www.postgresql.org/docs/current/sql-select.html ; isolation: https://www.postgresql.org/docs/current/transaction-iso.html ; partial indexes: https://www.postgresql.org/docs/current/indexes-partial.html
- Outbox: https://microservices.io/patterns/data/transactional-outbox.html
- AWS jitter simulator: https://github.com/aws-samples/aws-arch-backoff-simulator/blob/master/src/backoff_simulator.py ; AWS blog: https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/ ; Builders' Library: https://builder.aws.com/content/3EumjoZascWd1oZiEgL8ORlv3qE/timeouts-retries-and-backoff-with-jitter
- IETF Idempotency-Key draft: https://datatracker.ietf.org/doc/draft-ietf-httpapi-idempotency-key-header/ ; Stripe: https://docs.stripe.com/api/idempotent_requests
- Gemini errors: https://aistudio.google.com/docs/troubleshooting , https://aistudio.google.com/docs/api-errors?generate-content=true
- Circuit breaker: https://martinfowler.com/bliki/CircuitBreaker.html
- Queues: https://procrastinate.readthedocs.io/en/stable/discussions.html , https://procrastinate.readthedocs.io/en/stable/howto/production/retry_stalled_jobs.html , https://python-rq.org/docs/ , https://huey.readthedocs.io/en/latest/ , https://huey.readthedocs.io/en/latest/api.html , https://docs.celeryq.dev/en/stable/userguide/tasks.html , https://docs.celeryq.dev/en/stable/userguide/concurrency/eventlet.html , https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/index.html , https://dramatiq.io/ , https://apscheduler.readthedocs.io/en/3.x/userguide.html
- Render: https://render.com/docs/background-workers , https://render.com/docs/cronjobs , https://render.com/docs/free , https://render.com/docs/key-value , https://render.com/docs/health-checks , https://render.com/docs/postgresql-backups , https://render.com/pricing.md
- SQLite: https://www.sqlite.org/wal.html , https://www.sqlite.org/pragma.html#pragma_busy_timeout ; SQLAlchemy: https://docs.sqlalchemy.org/en/20/orm/versioning.html , https://docs.sqlalchemy.org/en/20/dialects/sqlite.html ; Alembic: https://alembic.sqlalchemy.org/en/latest/batch.html
- Flask-Limiter storage: https://flask-limiter.readthedocs.io/en/stable/configuration.html
- OWASP logging: https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html
- DPDP (secondary sources): https://www.dpdpa.com/dpdpa2023/chapter-3/section12.html , https://www.mondaq.com/india/data-protection/1708164/digital-personal-data-protection-rules-2025-notified
