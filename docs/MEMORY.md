# Project memory

Durable context for humans and future AI sessions. Facts here were checked against files in this repo on 2026-11-24 unless marked UNVERIFIED. If this file disagrees with code or tests, the code and tests win; fix this file.
Rules live in [RULES.md](RULES.md). Plan and status live in [TRACKER.md](TRACKER.md) and [STATUS.md](STATUS.md). Index: [README.md](README.md).

---

## 1. Snapshot

**Product.** MindFull Horizon: a Flask web app for college-student mental-health monitoring in India. Students: PHQ-9/GAD-7 screening, mood, journal, breathing, yoga, binaural music, digital detox, goals, medication log, AI wellness chat, appointments. Providers (campus counsellors): caseload, crisis panel, appointments, prescriptions, wellness reports, telehealth signalling. Not a medical device ([README.md](../README.md)). Product scope: [PRD.md](PRD.md).

**Stack.** Python 3.11 (the `Dockerfile` pins 3.11; some pins have no 3.13 wheels), Flask 2.x, Flask-SQLAlchemy, Flask-Migrate/Alembic, Flask-WTF (CSRF), Flask-Limiter, Flask-SocketIO (eventlet), Flask-Session (filesystem), Flask-Dance (Google OAuth), Flask-Assets (jsmin/cssmin), Gemini via `google-generativeai`, Jinja2 + Tailwind/Bootstrap CDN. SQLite in dev, PostgreSQL in prod.

**Where things live** (design detail: [ARCHITECTURE.md](ARCHITECTURE.md)).

| Thing | Path |
|-------|------|
| App setup, security headers, SocketIO, OAuth, legacy routes | `app.py` |
| Blueprints | `routes/` (`auth core patient provider blog assessment mood chat`) |
| Schema (source of truth) | `models.py`; migrations `migrations/versions/0001_baseline.py` |
| Role/ownership decorators | `decorators.py` |
| AI: Gemini call, crisis floor, scoring | `ai/gemini_impl.py`, `ai/service.py`, `ai/severity.py`, `ai/scoring.py`; prompts `ai_prompts/` |
| Helplines (one config, `LAST_VERIFIED`) | `utils/helplines.py` |
| Crisis audit write | `utils/crisis.py`, model `CrisisEvent` |
| Gamification | `utils/gamification.py` |
| Tests | `tests/` (`conftest.py` makes a temp DB); old manual scripts in `tests/manual/` (excluded) |
| Scripts | `scripts/seed_demo.py` (refuses in production), `scripts/import_binaural_dataset.py`, `scripts/scan_imports.py` |
| Archived deploy files | `.archive/deploy/` (Procfile, render.yaml, vercel.json) |
| Audio dataset | `data/binaural-beats-dataset/` (csv/json in git, mp3 ignored) |

**Run.** `python -m venv venv`, activate, `pip install -r requirements/dev.txt`, copy `.env.example` to `.env` and set `SECRET_KEY`, then `python app.py` (http://127.0.0.1:5000; creates `instance/mindful_horizon.db` on first start). Migrations: [MIGRATIONS.md](MIGRATIONS.md). Env vars and hosting: [DEVELOPMENT.md](DEVELOPMENT.md).

**Test.** `pytest tests -q` from the project root. Temp SQLite DB, `GEMINI_API_KEY` removed, rate limiter and CSRF off in the test app, no network.
*Test environment note:* no virtualenv is stored in the repo (`venv/` is git-ignored and absent), and the system Python 3.11.9 on the owner's machine had no Flask installed when this file was written, so a bare `pytest` fails on import. Create a venv and install `requirements/dev.txt` first. Use Python 3.11. If a result came from some other environment, say so (TEST-07).

---

## 2. Timeline: Nov 2026 cleanup and hardening

Dates are 2026-11 (the backup zip's modification time is 2026-11-24 12:46). Sources: the zip listing, current tree, `.gitignore`, [STATUS.md](STATUS.md).

| Step | What | Why |
|------|------|-----|
| Audit | Code audit wrote [STATUS.md](STATUS.md): about 50-55% of documented features, about 30-35% production readiness; critical list = unauthenticated APIs, role escalation, open SocketIO, weak crisis logic, insecure secret fallback, Jinja inside static JS, plaintext PHI. | Decide what to fix before any public deploy. |
| Backup | Full project snapshot saved as **`_backup_before_cleanup.zip`** in the parent folder `d:\MINDFULLHORIZON2.0\` (245 entries; includes `instance/mindful_horizon.db`, `flask_session/`, `.kiro/`, `.archive/`, and the root-level scripts listed below). | Safety net before deleting. Not in the project tree; do not commit it (`_backup_*.zip` is git-ignored). |
| Deleted or removed from the tree (all present in the zip) | Ad-hoc root scripts and patches: `add_demo_users.py`, `create_demo_now.py`, `enable_demo.py`, `insert_demo_users.sql`, `setup_demo.sql`, `test_login_credentials.md` (demo credentials); `app_upload_patch.py`, `file_upload_fix.py`, `security_fixes.py`, `secure_routes.py`, `upload_diagnostics.py`, `test_upload.html`; `check_schema.py`, `check_users.py`, `debug_appointments.py`, `appointment.py`, `create_schema_direct.py`; root-level `severity.py`, `shared_data.py`, `gamification_engine.py` (current equivalents: `ai/severity.py`, DB tables, `utils/gamification.py`); `.kiro/` editor hooks and steering; `.archive/tests/`; `manifest.json`, `design.md`, `requirements.md`/`MindFull_Horizon_Process_Flow.md` at root (copies now under `docs/`). | Demo credentials and one-off patches were a security and confusion risk; stray copies of modules next to the real ones invite editing the wrong file. |
| Moved | Deploy files (`Procfile`, `render.yaml`, `vercel.json`) to `.archive/deploy/`; old manual verification scripts to `tests/manual/`; `shared_data.py` in-memory journal/voice store replaced by DB tables `JournalEntry` and `VoiceLog` (test: `test_shared_data_not_used`); long docs under `docs/`. | Keep the root clean; serverless configs do not fit SocketIO (ADR-008). |
| Database reset | The dev SQLite DB was rebuilt from the Alembic baseline; it held demo/test data only, no real user data (ADR-009). `instance/mindful_horizon.db` now is a fresh file. | Start from a known schema; old DB came from `create_all` and had no `alembic_version`. |
| Hardening | Auth on all JSON APIs; provider signup by invite only; exact institution matching; SocketIO room auth and non-wildcard CORS; `SECRET_KEY` required in production; security headers; Lax cookies; rate limits; duplicate routes removed; server-side PHQ-9/GAD-7 scoring with item-9 rule; crisis floor with Hinglish and negation handling; `crisis_events` table with provider acknowledge; helplines from one config; landing page for guests; fake stats removed; `jsmin`/`cssmin` added to requirements; baseline migration 0001; CHECK constraints, FKs, indexes. | Each is covered by a test under `tests/` (see RULES.md "Enforced by"). |
| Repo | Upstream: https://github.com/ayushjaiswal21/MindFullHorizon . This folder is not a git repository on the owner's machine at the time of writing (no `.git`); sync only when the owner asks (GIT-05). | |
| Docs | [ARCHITECTURE.md](ARCHITECTURE.md), [DEVELOPMENT.md](DEVELOPMENT.md), [MIGRATIONS.md](MIGRATIONS.md), [SAFETY_RESEARCH.md](SAFETY_RESEARCH.md), three research notes under `docs/research/`, then [PRD.md](PRD.md), [DESIGN.md](DESIGN.md), [TRACKER.md](TRACKER.md), RULES.md, MEMORY.md. | |

Not verified from files: the exact order and time of each step; the contents of the old DB beyond "no real data" as stated by the owner.

---

## 3. Decisions log (ADR style)

All dated 2026-11. Status values: Accepted (in code now), Accepted-target (decided, not built yet), Superseded.

### ADR-001 DB-backed jobs table instead of Redis
- **Status:** Accepted-target. No `jobs` table or worker exists yet (no model in `models.py`).
- **Context:** Crisis alerts and slow Gemini work need retries and durability. One small VM, SQLite dev and Postgres prod, one eventlet process, one maintainer. Research: [research/queue-reliability.md](research/queue-reliability.md).
- **Decision:** Use a `jobs` table (states, `run_after`, attempts, claim by atomic UPDATE; `SKIP LOCKED` on Postgres) with a worker loop; write the alert row and its notify job in the same transaction. No Redis/Celery for now.
- **Consequences:** Works on both DBs, no new service, transactional with domain writes. Polling latency and DB load are higher than a broker; upgrade triggers (second SocketIO process, shared rate limits) are listed in the research note. Eventlet and the Google client may interact badly (UNVERIFIED).

### ADR-002 Exact institution matching
- **Status:** Accepted (`tests/test_provider.py::test_institution_match_is_exact_not_keyword`).
- **Context:** A keyword/`LIKE` match let a provider see students of other campuses.
- **Decision:** Providers see patients whose normalised institution name (lower, trimmed) equals theirs exactly, plus appointment relationship for per-patient pages.
- **Consequences:** Typos split campuses; fix with an institution table or admin-managed list later (data quality, not a security trade-off).

### ADR-003 Provider signup by invite code only
- **Status:** Accepted (`test_signup_provider_needs_matching_invite_code`, `test_save_role_cannot_make_provider`).
- **Context:** Signup and `/save_role` accepted `provider`, so anyone could read caseloads.
- **Decision:** Provider role requires `PROVIDER_INVITE_CODE` (env) at signup; Google sign-in and `/save_role` never grant it; without the env var provider signup is blocked.
- **Consequences:** Manual onboarding of counsellors. A shared code is weak; per-person invites or admin approval is the next step.

### ADR-004 Helplines from one config
- **Status:** Accepted (`utils/helplines.py`, `LAST_VERIFIED = '2026-11'`).
- **Context:** US numbers (988/911) were shown to Indian students; numbers were scattered.
- **Decision:** One list: Tele-MANAS 14416, KIRAN 1800-599-0019, 112. Everything imports it. Re-verify quarterly. Others (iCall, AASRA, Vandrevala) stay out until verified ([SAFETY_RESEARCH.md](SAFETY_RESEARCH.md)).
- **Consequences:** A stale number is a single-file fix; a quarterly chore exists.

### ADR-005 No points on assessment or mood
- **Status:** Accepted (`test_assessment_and_mood_give_no_points`).
- **Context:** Rewarding disclosure of scores can bias reporting and trivialise distress; loss-framed streaks may harm low-mood users (harm plausible, evidence UNVERIFIED either way).
- **Decision:** Points only for activities (breathing, yoga, music, ...), capped daily; none for PHQ-9/GAD-7, mood or disclosure; no loss-framed streak copy; suspend celebratory UI after a crisis flag.
- **Consequences:** Less "engagement" from the main check-in; accepted.

### ADR-006 mp3s out of git with AUDIO_BASE_URL
- **Status:** Accepted.
- **Context:** Six real tracks are about 36 MB each; most other files are 44-byte placeholders.
- **Decision:** `data/**/*.mp3` is git-ignored; csv/json metadata stays. `/audio/<path>` serves local files or redirects to `AUDIO_BASE_URL`.
- **Consequences:** Hosted deploys need a bucket. Known limit: `/api/mood-audio` still scans the local folder, so it returns nothing on a server without the files ([DEVELOPMENT.md](DEVELOPMENT.md)).

### ADR-007 SQLite for dev, PostgreSQL for prod
- **Status:** Accepted.
- **Context:** Zero-setup local work versus concurrent writes, backups and ephemeral hosting disks.
- **Decision:** SQLite at `instance/mindful_horizon.db` unless `DATABASE_URL` is set; production uses PostgreSQL. Migrations must pass on both; SQLite uses Alembic batch mode.
- **Consequences:** Features must avoid dialect-only SQL, or guard it. FK enforcement on SQLite is explicitly enabled and tested.

### ADR-008 Single eventlet worker
- **Status:** Accepted (`gunicorn --worker-class eventlet --workers 1 app:app`).
- **Context:** SocketIO telehealth signalling keeps in-process room state; several workers would need a message queue.
- **Decision:** One eventlet worker. Not suited to serverless (Vercel): `.archive/deploy/vercel.json` is archived for that reason.
- **Consequences:** Vertical scaling only; a second process needs Redis (or Postgres notify) first. Eventlet is in maintenance mode (research note); revisit.

### ADR-009 DB reset with no real data
- **Status:** Accepted, executed 2026-11.
- **Context:** The old dev DB came from `create_all`, held demo/test rows and demo credentials.
- **Decision:** Discard it and rebuild from migration 0001. Safe only because no real user data existed (owner statement; not independently verifiable from files). The old DB is inside `_backup_before_cleanup.zip`.
- **Consequences:** From the first real user, resets are forbidden without owner approval (DB-05, AGENT-04).

### ADR-010 Landing page for guests at /
- **Status:** Accepted (`test_landing_for_guest_has_helpline`).
- **Context:** `index.html` carried placeholder stats and testimonials and was shown to everyone.
- **Decision:** `/` renders `landing.html` for guests (honest copy, helplines visible) and `index.html` for logged-in users.
- **Consequences:** Two templates to keep consistent; copy rules in RULES CONTENT apply to both.

### ADR-011 Deterministic crisis floor over model output
- **Status:** Accepted (`tests/test_safety.py`).
- **Context:** LLMs miss or soften suicide risk; the old heuristic scored one severe phrase below the escalation threshold; model JSON was trusted ([research/llm-security.md](research/llm-security.md) C5-C7).
- **Decision:** `ai/severity.py` classifies first (normalise, word-boundary regex, negation window, friend path). A first-person hit forces emergency severity and helplines; the model may add detail or raise severity, never lower it; if the model fails, show the card anyway (fail conservative).
- **Consequences:** More false positives (accepted). Phrase lists need clinician and Hinglish-speaker review before launch; recall on real text is UNKNOWN.

### ADR-012 models.py as schema source, Alembic baseline
- **Status:** Accepted ([MIGRATIONS.md](MIGRATIONS.md)).
- **Context:** Schema was created by `create_all` and ad-hoc scripts; no migrations.
- **Decision:** `models.py` is truth; `migrations/versions/0001_baseline.py` is the baseline; `create_all` runs only as a dev/test bootstrap (skipped when `FLASK_ENV=production` or `SKIP_CREATE_ALL=1`); a test fails if models and migrations diverge.
- **Consequences:** Any model edit needs a reviewed migration; dev DBs made by `create_all` need `flask db stamp 0001` or a fresh file.

---

## 4. Glossary

| Term | Meaning |
|------|---------|
| PHQ-9 / GAD-7 | 9-item depression and 7-item anxiety screening questionnaires, items 0-3. Screening, not diagnosis. Bands in [SAFETY_RESEARCH.md](SAFETY_RESEARCH.md). |
| Item 9 | PHQ-9 question on thoughts of being better off dead or self-harm; >= 1 is positive regardless of total (project rule, our inference). |
| Crisis floor | The deterministic minimum severity and response set by code (`ai/severity.py`) that the model cannot lower. |
| Soft check-in | Gentle response to negated/ambiguous distress ("I don't want to die", "this exam is killing me"); no crisis card. |
| Friend path | Response for third-party risk ("my friend says she wants to die"). |
| CrisisEvent | Audit row for a detected crisis (source, severity, short reason code, acknowledged_at/by). Never user text. |
| Provider | Campus counsellor/clinician user role. Patient = student role. |
| Institution | Free-text college name on the user, matched exactly after normalising. |
| Tele-MANAS | Government of India 24x7 mental-health helpline, 14416. KIRAN: 1800-599-0019. |
| DPDP | India's Digital Personal Data Protection Act 2023 and Rules 2025. Secondary sources only; get counsel. |
| PHI | Personal health information (chat, journal, voice, assessments, mood). |
| Outbox / jobs table | DB table of pending work written in the same transaction as the event (ADR-001). |
| Idempotency key | Client-sent unique id so a retried write is applied once. |
| Baseline migration | `0001_baseline.py`, the first Alembic revision. |
| ADR | Architecture decision record (section 3). |
| UNVERIFIED / SECONDARY | Research labels: not confirmed on a primary page / taken from a summary. Do not treat as fact. |
| Hand-off | The short note an agent leaves for the next session (section 8). |

---

## 5. Gotchas and lessons learned

1. **`flask_session/` shadows the package.** The runtime session folder `flask_session/` (filesystem sessions, `SESSION_FILE_DIR`) has the same name as the `flask_session` package. A naive import scan or `sys.path` entry at the project root can treat the folder as a module and report false results. `scripts/scan_imports.py` exists for import checks; keep `flask_session/` git-ignored and out of docker contexts.
2. **Jinja tags inside static JS break silently.** `{{ }}` in `static/js/**` is never rendered, so pages (analytics, telehealth, wellness report, provider dashboard) loaded but did nothing. Pass values via `data-*` attributes or a JSON script block. Guard: `tests/test_provider.py::test_static_js_has_no_jinja`.
3. **`SameSite=Strict` breaks the Google OAuth redirect.** The cookie is dropped on the cross-site return, so login looks like it fails. Cookies are `Lax` (comment in `app.py`; test `test_cookies_are_lax`).
4. **Requirements lacked `jsmin` and `cssmin`.** `Flask-Assets` bundles in `app.py` need them; a fresh install returned 500 on every page. They are now in `requirements.txt`.
5. **Gemini model and SDK churn.** The code had `gemini-1.5-flash` hard-coded; Google's changelog (search snippet, recheck live) lists 1.5 models as shut down in 2025-09, and `google.generativeai` as end-of-life 2025-08-31. The model name now comes from `GEMINI_MODEL_NAME` (default `gemini-flash-latest`). A listed 2.5-flash shutdown date of 2026-10-16 is UNVERIFIED; check before relying on any model id. Migrating to `google-genai` is open (AI-11).
6. **One severe keyword scored below the escalation threshold.** In the old heuristic a single phrase such as "I want to kill myself" scored 6 while escalation needed 7. Fixed by the floor design (ADR-011); test `test_single_statement_reaches_emergency_level`.
7. **Docs lag.** [STATUS.md](STATUS.md) still lists many items as open (for example "No tests", unauthenticated endpoints) that the code and tests now cover, and [DEVELOPMENT.md](DEVELOPMENT.md) still mentions `scripts/create_schema_direct.py` (removed) and says the model name is ignored (no longer true). Trust tests and TRACKER.
8. **CSP is Report-Only.** `app.py` sends `Content-Security-Policy-Report-Only`; enforcing it needs inline scripts removed first.
9. **`create_all` vs Alembic.** App start can create tables before `flask db upgrade` runs and then upgrade fails with "table already exists". Use `SKIP_CREATE_ALL=1` (see MIGRATIONS.md).
10. **Duplicate routes shadow silently.** Same URL in `app.py` and a blueprint: whichever registers first wins. Test: `test_duplicate_routes_gone`.
11. **Parent folder is a trap.** `d:\MINDFULLHORIZON2.0\` holds old prototypes (`main.py`, `models.py`, `crew_logic.py`, `mental_health.db`, `_app.py.before_dedupe`, `_backup_before_cleanup.zip`). They are not the project (AGENT-01).
12. **`.env` holds a real key** per STATUS.md; it is git-ignored but must be rotated (SEC-02). Never print it.
13. **Helpline typos exist online.** Some pages print KIRAN as 1800-500-0019; the verified number is 1800-599-0019 (via PIB). AASRA: use 022 2754 6669, not 9820466726.
14. **Known doc/code gaps recorded 2026-11-24:** `ai/service.py` still uses a "Dr. Anya" persona in the journal-insight prompt; `app.py` file-validation helper returns `str(e)` to its caller; no `/ready`, jobs table, idempotency keys, retention job or prompt-injection test file yet.

---

## 6. Known unknowns and UNVERIFIED items

From [SAFETY_RESEARCH.md](SAFETY_RESEARCH.md) and `docs/research/`. Do not turn these into UI copy or requirements without a primary source.

**Safety and clinical**
- Phrase lists (English, Hinglish, Devanagari) are constructed fixtures, not a validated corpus; recall on real student text is unknown.
- PHQ-9 item-9 "positive if >= 1 regardless of total" is our inference, not an official rule. Exact functional-difficulty wording must be copied from the official form.
- Vandrevala Foundation number: secondary sources only. iCall hours conflict.
- Whether the Mental Healthcare Act 2017 s.23-24 binds a wellness app is unverified.

**Law and regulation (all secondary)**
- DPDP Rules 2025 phase dates, Rule 10/12 child-consent details, any exemption for education/health bodies, and breach and erasure timelines (sources conflict).
- Telemedicine Practice Guidelines 2020 clause numbers for "AI cannot counsel or prescribe" (official PDF not read).
- CDSCO/Medical Device Rules position on screening software; ABDM/ABHA obligations; ICMR ethics review for research use.
- UGC draft mental-health guidelines (Jan 2026) final status; NTF final report.

**Market and evidence**
- India student prevalence, stigma, counsellor ratios (IIT figures from a secondary site), competitor status and pricing (Youper, Amaha, YourDOST), 2026 chatbot meta-analysis effect sizes (primary pages not opened), whether streaks cause guilt in mental-health apps (no evidence either way). Success-metric targets in the research are proposals, not facts.

**Engineering**
- Gemini retention period and training use on the paid tier; Google client under eventlet monkey patching (grpc vs REST); exact deprecation dates of current Gemini models; legacy-SDK call forms for `response_schema`.
- Package choices for JSON logging; Postgres exclusion constraints for overlapping appointments.

---

## 7. How to resume work

Read order (about 30 minutes): this file, [README.md](README.md), [RULES.md](RULES.md), [TRACKER.md](TRACKER.md), [ARCHITECTURE.md](ARCHITECTURE.md), [PRD.md](PRD.md), [DESIGN.md](DESIGN.md) (when working on UI), [SAFETY_RESEARCH.md](SAFETY_RESEARCH.md) (when touching crisis, scoring, AI), then the relevant `docs/research/*.md`. [STATUS.md](STATUS.md) is a dated audit; check it against tests.

Commands (project root, venv active):

```bash
pip install -r requirements/dev.txt
pytest tests -q                              # full suite, temp DB, no network
pytest tests/test_safety.py -q               # crisis, scoring, AI wrapper
pytest tests/test_security.py -q             # auth, CSRF-adjacent, headers, sockets
SKIP_CREATE_ALL=1 flask db upgrade           # PowerShell: $env:SKIP_CREATE_ALL=1; flask db upgrade
python scripts/seed_demo.py                  # dev only; refuses in production
python app.py                                # http://127.0.0.1:5000
```

Before any change: read the files you will touch, check [RULES.md](RULES.md) for the category, write a failing test for bugs, make a minimal diff, run the full suite, update the owner doc, write the hand-off.

---

## 8. Agent hand-off template

Copy into the PR description or the last message of a session.

```
## Hand-off
Date / agent / task:
Scope (files I was allowed to edit):
Changed (file: what, why):
Rules touched (IDs from RULES.md):
Tests: command run, environment (python version, venv), result (pass/fail counts). Failures or skips, verbatim:
Not run / not checked:
Decisions made (new ADR needed? y/n):
Docs updated (owner doc per README.md):
Docs or code inconsistencies found:
Open questions for the owner:
Destructive or irreversible actions taken (should be none without approval):
Next step I would take:
```

## Branch consolidation (2026-11-24)

The overhaul commit `59f606b` was fast-forwarded onto `main`. The old `main` is kept as tag `pre-overhaul-2026-11` (`f2a0355`). The remote branches below were deleted after checking they were already contained in `main` or superseded. To restore one, run `git push origin <sha>:refs/heads/<name>` (GitHub keeps unreachable commits for a limited time, so do it soon if needed).

| Branch | Tip SHA | State when deleted |
|--------|---------|--------------------|
| `cleanup/overhaul-2026-11` | `59f606bed63c7716eb86e994e99e05e90bd3a748` | equal to `main` |
| `tidy/diagnose-icons-auth-20251106` | `5945bc4182e61fe5324994597cb67ebec49d75ef` | fully merged into old `main` |
| `snyk-fix-e2a2980d0f8f6a4a87448e2ff0801af7` | `5a262785110379949dd39789bedf8f7d5e9229ca` | fully merged into old `main` |
| `snyk-fix-5411f8bd849f6b39f8d1e0d261768491` | `ecb2e745391a745868b65e31814c7a94ec9f044b` | 1 unique Snyk commit (jinja2 3.1.6, python-multipart 0.0.18); jinja2 floor added to `requirements.txt`, python-multipart is not used |

Working rule from now on: only green checkpoints (full suite passing) are pushed, directly to `main`.

## Owner decisions and gotchas (2026-11-24, evening)

Decisions are in [TRACKER.md](TRACKER.md) section 3 (P-01 to P-09). Gotchas found in real use:

- **Unit tests missed real bugs.** Script load order broke the assessment Start buttons; a legacy `scripts.js` swallowed chat submits; `prefers-reduced-motion` hid the breathing circle; a missing session stamp looped the admin login. Use `tools/e2e/` for UI work.
- **Never call the AI inside a page render.** The progress page took 25 to 60 seconds that way. Use a capped JSON endpoint with a negative cache.
- **The Windows clock ticks in about 15 ms steps**; two cache-generation bumps in one tick shared a value. `utils/cache_utils.bump` now adds at least 1.
- **Templates are cached** (`TEMPLATES_AUTO_RELOAD` off): restart the server to see template edits.
- **Cookie sessions** carry an HMAC stamp (id, password hash, role). New sign-in paths must call `stamp_session(user)`; tests are lenient (TESTING accepts stamp-less sessions), so check the stamp directly.
- **A free Render instance sleeps**, so crisis escalation timers stop; a pilot needs an always-on instance.
- **`.env` GEMINI_API_KEY**: a key that was exposed is auto-disabled by Google; replace it after rotating.
