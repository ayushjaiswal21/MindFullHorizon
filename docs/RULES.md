# Engineering and AI-agent rulebook

Scope: this repository only (`d:\MINDFULLHORIZON2.0\MindFullHorizon`). The parent folder is not part of the project.
Words MUST, MUST NOT, SHOULD, SHOULD NOT, MAY are used as in RFC 2119.
Format per rule: **ID** rule. *Why.* Enforced by: `x`.

"Enforced by" names the real check today. `manual (add test)` means the rule is binding but no automated check exists yet; whoever touches that area SHOULD add one. Where a rule describes a target that the code does not yet meet, it is marked **[target]** and the gap is tracked in [TRACKER.md](TRACKER.md) / [STATUS.md](STATUS.md).

Related: [ARCHITECTURE.md](ARCHITECTURE.md) (how it is built), [PRD.md](PRD.md) (what and why), [DESIGN.md](DESIGN.md) (UI and budgets), [SAFETY_RESEARCH.md](SAFETY_RESEARCH.md) (clinical rules), [MEMORY.md](MEMORY.md) (decisions and gotchas).

---

## ARCH: structure

- **ARCH-01** New routes MUST live in a blueprint under `routes/`, never in `app.py`. *`app.py` is legacy and shrinking; duplicates caused silent shadowing.* Enforced by: `tests/test_security.py::test_duplicate_routes_gone`, code review.
- **ARCH-02** A blueprint MUST be registered in `routes/__init__.py` only. *One place to see the URL surface.* Enforced by: code review.
- **ARCH-03** Templates MUST NOT contain business logic (scoring, risk, permissions, DB queries); compute in Python and pass plain values. *Logic in Jinja cannot be unit-tested.* Enforced by: code review.
- **ARCH-04** Heavy or optional imports (Gemini SDK, numpy/pandas, speech, audio) MUST be imported lazily inside the function that needs them. *Cold start and import failures must not take the whole app down.* Enforced by: `python scripts/scan_imports.py`, code review.
- **ARCH-05** `models.py` is the schema source of truth; helpers that touch the DB MUST go through `extensions.db`, not a second engine. *One schema, one session.* Enforced by: `tests/test_db.py::test_migration_upgrade_matches_create_all`.
- **ARCH-06** Roles and ownership checks MUST use `decorators.py` (`login_required`, `role_required`, `patient_required`, `provider_required`), not ad-hoc `session` checks. *One audited gate.* Enforced by: `tests/test_security.py`, code review.
- **ARCH-07** Crisis, helpline and scoring logic MUST each have exactly one implementation (`ai/severity.py`, `utils/helplines.py`, `ai/scoring.py`, `utils/crisis.py`). *Two copies drift; drift in safety code hurts people.* Enforced by: `tests/test_safety.py::test_no_us_numbers_in_ai_service`, code review.
- **ARCH-08** Do not add a new top-level service (Redis, Celery, a second process) without an ADR in [MEMORY.md](MEMORY.md) and owner approval. *Solo-maintainer ops budget.* Enforced by: code review.

## CODE: style and errors

- **CODE-01** Python MUST follow PEP 8 with 120-column lines; names are `snake_case`, classes `PascalCase`. *Consistency.* Enforced by: code review (no linter configured yet).
- **CODE-02** Code MUST NOT return `str(e)`, tracebacks or exception text to clients; return a stable message and log server-side. *Leaks internals and sometimes user data.* Enforced by: `tests/test_security.py::test_chat_bad_payload_is_400_without_details`, code review. Known gap: `app.py` `validate_upload`-style helper returns `f"File validation error: {str(e)}"` to its caller (see TRACKER).
- **CODE-03** Logs MUST NOT contain patient-authored text (chat, journal, voice transcripts, mood notes), model output derived from it, OAuth profile data, or emails. Log ids, lengths, codes. *Logs are copied to third parties.* Enforced by: `tests/test_security.py::test_google_login_does_not_log_profile`, `::test_log_error_cannot_inject_log_lines`, code review.
- **CODE-04** Any value written to a log line from a client MUST have newlines stripped. *Log forging.* Enforced by: `tests/test_security.py::test_log_error_cannot_inject_log_lines`.
- **CODE-05** Every DB write path MUST `commit()` inside try/except and `rollback()` on failure. *A failed write otherwise poisons the session.* Enforced by: code review.
- **CODE-06** Diffs MUST be minimal and targeted: no drive-by reformatting, renames or file moves unrelated to the change. *Reviewable, revertable.* Enforced by: PR review checklist.
- **CODE-07** Dead code and commented-out code MUST be deleted, not kept. *History lives in git and the backup zip.* Enforced by: code review.
- **CODE-08** Comments SHOULD explain why, not what. Shortcuts with a known limit SHOULD carry `shortcut: <limit>, <when to upgrade>`. *Keeps debt visible.* Enforced by: code review.
- **CODE-09** User-facing copy MUST be plain, calm and free of blame; it MUST NOT claim a feature that does not exist. See CONTENT. Enforced by: code review.

## API: HTTP and JSON

- **API-01** Auth MUST run first: decorator order is `@route`, rate limit, `@login_required`, role decorator, then input validation. *Do not reveal validation behaviour to anonymous callers.* Enforced by: `tests/test_security.py::test_anonymous_json_api_gets_401`.
- **API-02** JSON endpoints MUST return **401** when not authenticated and **403** when authenticated but the role is wrong; HTML pages MAY redirect to login. *Clients and monitors need to tell them apart.* Enforced by: `tests/test_security.py`.
- **API-03** Every query for user data MUST filter by the session user id (or the provider's institution plus an appointment/consent link); a client-sent `user_id` MUST be ignored. *IDOR is the most likely severe bug here.* Enforced by: `tests/test_security.py::test_chat_ignores_client_user_id`, `test_mood_writes_and_reads_session_user_only`, `tests/test_patient.py::test_goal_other_user_404`, `tests/test_provider.py::test_patient_scoped_pages_blocked_for_other_institution`.
- **API-04** Another user's object MUST return **404**, not 403. *Do not confirm that the id exists.* Enforced by: `tests/test_patient.py::test_goal_other_user_404`, `tests/test_provider.py::test_crisis_ack_foreign_event_404`.
- **API-05** Request bodies MUST be validated (type, range, length, enum) at the boundary and bad input MUST return 400 with a generic message. *No 500s from user input.* Enforced by: `tests/test_security.py::test_mood_rejects_bad_values`, `tests/test_patient.py::test_goal_create_bad_target_is_400`.
- **API-06** List endpoints MUST paginate or cap (`limit`, default and max stated in the route; today most use `.limit(500)` or less). *Unbounded reads are a DoS and a PHI over-share.* Enforced by: code review.
- **API-07** Unsafe retried operations that can double-write (assessment save, appointment booking, points) SHOULD accept an `Idempotency-Key` header or have a natural unique constraint. **[target]** *Mobile retries and double clicks.* Enforced by: manual (add test); design in [research/queue-reliability.md](research/queue-reliability.md) section 3.
- **API-08** JSON responses MUST use one envelope, `{"success": false, "message": "<stable, generic text>"}` (the shape `decorators.py` and most routes use today), with a correct HTTP status; do not invent a second shape. *Predictable client handling.* Enforced by: `tests/test_security.py::test_error_handler_matches_blueprint_endpoint`, code review.
- **API-09** Methods MUST match semantics: GET never writes; PUT replaces; POST creates. *Prefetchers and CSRF assumptions.* Enforced by: `tests/test_patient.py::test_goal_put_semantics`.
- **API-10** Server-side actions with side effects (for example launching local audio) MUST NOT be triggered from a request. *Remote code or nuisance execution.* Enforced by: `tests/test_security.py::test_play_mood_never_launches_server_side`.

## DB: data layer

- **DB-01** Schema changes MUST go through Alembic (`migrations/versions/`) generated from `models.py`; no hand-run DDL. *Reproducible, reviewable.* Enforced by: `tests/test_db.py::test_migration_upgrade_matches_create_all`. See [MIGRATIONS.md](MIGRATIONS.md).
- **DB-02** Scalar rules MUST be CHECK constraints, uniqueness MUST be UNIQUE constraints, ownership MUST be a foreign key. *The DB is the last line when app code has a bug.* Enforced by: `tests/test_db.py::test_check_constraints`.
- **DB-03** Foreign keys MUST be enforced on SQLite and deletes MUST cascade or SET NULL deliberately (no orphans). *Right-to-erasure must really delete.* Enforced by: `tests/test_db.py::test_delete_user_leaves_no_orphans`, `::test_delete_user_via_raw_sql_cascades`.
- **DB-04** Columns used in `WHERE`/`ORDER BY` of hot queries (user_id, created_at, status) MUST be indexed. Enforced by: `tests/test_db.py::test_hot_indexes_exist`.
- **DB-05** Raw destructive scripts (`DROP`, `DELETE` without `WHERE`, file deletion of `instance/*.db`) MUST NOT be committed or run without explicit owner approval. *No real data may be lost by an agent.* Enforced by: AGENT-04, code review.
- **DB-06** The repo MUST NOT contain demo credentials, seeded users in migrations, or SQL with passwords. Demo users come only from `python scripts/seed_demo.py`, which refuses to run when `FLASK_ENV=production`. *Known-password accounts in prod are a breach.* Enforced by: `scripts/seed_demo.py` guard, `grep -rIn "password" --include=*.sql .` returns nothing, code review.
- **DB-07** Aggregates MUST be computed in SQL, not by loading rows into Python loops (no N+1). Enforced by: `tests/test_db.py::test_institutional_summary_is_constant_query_count`.
- **DB-08** Tests MUST use a temp database (see `tests/conftest.py`); they MUST NOT read or write `instance/mindful_horizon.db`. Enforced by: `tests/conftest.py`.
- **DB-09** Institution matching MUST be exact on the normalised name (lower, trimmed), never `LIKE`/keyword. *Keyword match leaked students across campuses.* Enforced by: `tests/test_provider.py::test_institution_match_is_exact_not_keyword`.

## SEC: security

- **SEC-01** Secrets (`SECRET_KEY`, `GEMINI_API_KEY`, OAuth secrets, `PROVIDER_INVITE_CODE`) MUST come from the environment; `.env` MUST NOT be committed. Production MUST refuse to start without `SECRET_KEY`. Enforced by: `tests/test_security.py::test_production_without_secret_key_refuses_to_start`, `.gitignore`, `.dockerignore`.
- **SEC-02** Any key that was ever pasted into chat, a ticket or a commit MUST be rotated. *Treat as leaked.* Enforced by: manual (see OPS-04). `.env` currently holds a key that STATUS.md says to rotate.
- **SEC-03** All state-changing requests MUST be CSRF-protected (Flask-WTF `CSRFProtect`); `@csrf.exempt` needs a code comment justifying it. *Cookie auth.* Enforced by: code review; `grep -rn "csrf.exempt"` is reviewed on every PR.
- **SEC-04** Responses MUST send security headers (`X-Content-Type-Options`, frame protection, referrer policy, CSP). CSP is currently **Report-Only**; it SHOULD be switched to enforcing once inline scripts are gone. Enforced by: `tests/test_security.py::test_security_headers`.
- **SEC-05** Session cookies MUST be `HttpOnly`, `Secure` in production and `SameSite=Lax` (Strict breaks the Google OAuth redirect). Enforced by: `tests/test_security.py::test_cookies_are_lax`.
- **SEC-06** Static JS (`static/js/**`) MUST NOT contain Jinja tags (`{{ }}`, `{% %}`); pass server values via `data-*` attributes or a JSON script block. *Jinja in a static file is not rendered and fails silently.* Enforced by: `tests/test_provider.py::test_static_js_has_no_jinja`.
- **SEC-07** Untrusted text MUST be rendered with `textContent` or an escaping template, never `innerHTML`/`|safe`. Enforced by: `tests/test_safety.py::test_chat_js_has_no_innerhtml`, `tests/test_patient.py::test_goals_template_no_unsafe_attr`, code review.
- **SEC-08** Auth, signup, AI and upload endpoints MUST have per-route rate limits; the default limit MUST NOT block normal browsing. Enforced by: `tests/test_security.py::test_default_limit_allows_normal_browsing_but_login_is_strict`.
- **SEC-09** Uploads MUST check extension and MIME, cap size, use server-generated filenames, and be served only to their owner. Voice uploads are rate limited. Enforced by: `tests/test_patient.py::test_voice_upload_list_delete`, code review.
- **SEC-10** Provider accounts MUST be created only with the invite code (`PROVIDER_INVITE_CODE`); `/save_role` and OAuth MUST NOT grant `provider`. Enforced by: `tests/test_security.py::test_signup_provider_needs_matching_invite_code`, `test_save_role_cannot_make_provider`.
- **SEC-11** Google sign-in MUST require a verified email and MUST NOT link to an existing account by unverified email. Enforced by: `tests/test_security.py::test_google_unverified_email_does_not_take_over_account`.
- **SEC-12** SocketIO events MUST authenticate the session, scope rooms to the user (or provider with a same-institution appointment), and CORS origins MUST NOT be `*`. Enforced by: `tests/test_security.py::test_socket_*`, `::test_socketio_cors_not_wildcard`.
- **SEC-13** Passwords MUST be hashed with Werkzeug; OAuth-only users MUST have an unusable password. Enforced by: `tests/test_security.py::test_google_new_user_has_unusable_password_and_patient_dashboard`.
- **SEC-14** `DEBUG_DISABLE_SECURITY` and Flask debug MUST be off in production. Enforced by: code review; OPS checklist.
- **SEC-15** Vulnerability reports go through [SECURITY.md](../SECURITY.md); a fix for a reported issue MUST NOT discuss exploit details in a public issue. Enforced by: manual.

## PRIV: privacy and health data

- **PRIV-01** Collect the minimum: do not add a field to `models.py` holding health or identity data without a stated purpose in [PRD.md](PRD.md). *DPDP purpose limitation.* Enforced by: PR review checklist.
- **PRIV-02** Consent MUST be explicit, specific and withdrawable before any data is shared with a provider or sent to an AI vendor. **[target]** Enforced by: manual (add test). Legal basis is research only; see [SAFETY_RESEARCH.md](SAFETY_RESEARCH.md) and get counsel.
- **PRIV-03** Under-18 users: the product SHOULD gate by age and MUST NOT add behavioural tracking or ad/analytics SDKs for them; verifiable parental consent is required before launch to minors. **[target]** *DPDP s.9 (secondary source, UNVERIFIED in detail).* Enforced by: manual.
- **PRIV-04** Retention MUST be defined per data class (chat, journal, voice, assessments, crisis events) and implemented as a purge job or erasure path before public launch. **[target]** Enforced by: manual; user deletion cascades are tested (DB-03).
- **PRIV-05** Personal text MUST be redacted (names, emails, phone numbers) before it is sent to an external model. **[target]** Enforced by: manual (add test); see [research/llm-security.md](research/llm-security.md) section 6.
- **PRIV-06** Use a paid-tier Gemini key for any real user data; unpaid-tier content may be used by the vendor for improvement and human review (per Google terms cited in [research/llm-security.md](research/llm-security.md) section 4). Enforced by: manual / OPS-04.
- **PRIV-07** The UI MUST say exactly who can see what (student, counsellor of the same institution, nobody else). It MUST NOT promise "100% confidential" or "anonymous". Enforced by: code review; see CONTENT-03.
- **PRIV-08** Provider access to a patient's data MUST be limited to the same institution plus an appointment or consent relationship. Enforced by: `tests/test_provider.py::test_patient_scoped_pages_blocked_for_other_institution`, `::test_appointment_makes_patient_reachable`.
- **PRIV-09** DB backups MUST be treated as PHI: encrypted at rest, access logged, never committed. Enforced by: `.gitignore` (`*.db`, `*.bak*`, `_backup_*.zip`).

## AI: model use

- **AI-01** Every AI surface MUST state that the user is talking to an AI and that it is not a clinician. Enforced by: `tests/test_safety.py::test_chat_template_has_ai_disclosure`.
- **AI-02** The AI MUST NOT diagnose, prescribe, adjust medication or give medical advice, and MUST NOT present itself as a doctor (no "Dr." persona). *AI counselling/prescribing is restricted by Indian telemedicine guidelines (secondary sources); ethical risk regardless.* Enforced by: prompt in `ai_prompts/`, code review. Known gap: `ai/service.py` (journal insights prompt) still says "You are Dr. Anya"; remove it (see TRACKER).
- **AI-03** Rules MUST go in the model's `system_instruction`; user text MUST NOT be concatenated into the rules string. Enforced by: `tests/test_safety.py::test_gemini_impl_uses_system_instruction_and_env_model`, `::test_journal_text_is_not_in_system_prompt`.
- **AI-04** Model output MUST be parsed as JSON in try/except, validated against a schema (types, clamped ranges, allow-listed enums), length-clamped, and unknown keys dropped before use. **[target]** for non-chat `generate_*` functions (see [research/llm-security.md](research/llm-security.md) C9). Enforced by: `tests/test_safety.py` (chat path), manual elsewhere.
- **AI-05** The deterministic crisis floor (`ai/severity.py`) MUST run before and independently of the model; model output MUST NEVER lower the floor's severity, action or helpline display. Enforced by: `tests/test_safety.py::test_crisis_forces_emergency_even_if_llm_says_none`, `::test_crisis_fails_conservative`, `::test_safety_block_keeps_crisis_resources`.
- **AI-06** If the model errors, times out or is safety-blocked, the app MUST fall back to a canned response and MUST keep crisis resources if the floor fired. Enforced by: `tests/test_safety.py::test_save_assessment_survives_gemini_failure`.
- **AI-07** The prompt-injection corpus MUST pass: crisis and escalation behaviour is unchanged by hostile user text. The corpus (55 cases) is in [research/llm-security.md](research/llm-security.md) section 5; until `tests/test_llm_security.py` exists, any change to `ai/` MUST be checked against it manually and the result reported in the PR. **[target]** Enforced by: manual (add test).
- **AI-08** Model name, key and timeout MUST come from env (`GEMINI_MODEL_NAME`, `GEMINI_API_KEY`, `GEMINI_TIMEOUT`); no hard-coded model ids. *Models are retired on a schedule (see MEMORY gotchas).* Enforced by: `tests/test_safety.py::test_gemini_impl_uses_system_instruction_and_env_model`.
- **AI-09** Tests MUST NOT call a live model; mock at `ai/gemini_impl`. Enforced by: `tests/conftest.py` (pops `GEMINI_API_KEY`).
- **AI-10** AI-written provider summaries MUST be labelled "AI draft" and shown beside code-computed crisis flags, never instead of them. Enforced by: code review.
- **AI-11** The legacy `google.generativeai` SDK is end-of-life; new AI code SHOULD target the supported `google-genai` SDK and be isolated behind `ai/gemini_impl.py`. **[target]** Enforced by: code review.

## CRISIS: safety-critical behaviour

- **CRISIS-01** Helpline numbers MUST come from `utils/helplines.py`, which carries a `LAST_VERIFIED` date and is re-verified quarterly; numbers MUST NOT be pasted into templates, JS, prompts or tests as literals. Defaults: Tele-MANAS 14416, KIRAN 1800-599-0019, 112. Enforced by: `tests/test_safety.py::test_helplines_config_is_india_only`, `::test_no_us_numbers_in_ai_service`, `tests/test_smoke.py::test_landing_for_guest_has_helpline`.
- **CRISIS-02** `CrisisEvent.reason` MUST be a short code; user text MUST NEVER be stored in crisis events or alerts. Enforced by: `utils/crisis.py` (truncates), `tests/test_safety.py::test_save_assessment_item9_creates_crisis_record_and_helplines`.
- **CRISIS-03** PHQ-9 item 9 >= 1 MUST be treated as positive regardless of total; a skipped item 9 is "unanswered", never 0. Scoring is server-side; client scores are ignored. Enforced by: `tests/test_safety.py::test_phq9_item9_positive_regardless_of_total`, `::test_phq9_skipped_item9_is_unanswered_not_zero`, `::test_save_assessment_canonicalises_type_and_recomputes_score`.
- **CRISIS-04** A crisis alert MUST be durable (written in the same transaction as the triggering record) and MUST stay visible to providers until acknowledged; acknowledgement is recorded with who and when. Today: `crisis_events` rows plus provider panel; an outbox/notification job is **[target]**. Enforced by: `tests/test_provider.py::test_crisis_panel_and_acknowledge`.
- **CRISIS-05** Crisis wording MUST show helplines prominently, MUST NOT promise confidentiality, give means or methods, or debate reasons; after a flag, celebratory UI MUST be suppressed. Enforced by: `tests/test_safety.py::test_crisis_phrases_trigger`, code review; guidance in [SAFETY_RESEARCH.md](SAFETY_RESEARCH.md).
- **CRISIS-06** Negated or ambiguous text MUST become a soft check-in, never be dropped; third-party risk ("my friend...") goes to the helping-a-friend path. Enforced by: `tests/test_safety.py::test_ambiguous_or_negated_is_soft_checkin`, `::test_third_party_is_friend_path`, `::test_negation_in_other_clause_does_not_hide_crisis`.
- **CRISIS-07** One severe statement MUST reach emergency level on the heuristic path. Enforced by: `tests/test_safety.py::test_single_statement_reaches_emergency_level`.
- **CRISIS-08** Phrase lists are test fixtures, not a validated corpus; a clinician and Hindi/Hinglish speakers MUST review them before public launch. Enforced by: manual (launch gate).

## CONTENT: copy and engagement

- **CONTENT-01** UI copy MUST NOT contain fake statistics, testimonials, user counts or placeholder numbers. Enforced by: `tests/test_patient.py::test_index_and_landing_have_no_fake_claims`, `::test_dashboard_no_fake_vitals`.
- **CONTENT-02** The product MUST NOT claim "encrypted", "HIPAA/DPDP compliant", "clinically proven", "AI therapist", "prevents suicide" or endorsement by a body unless it is true and evidenced. Claim list: [research/product-market.md](research/product-market.md) section 8. Enforced by: code review.
- **CONTENT-03** Privacy claims MUST be literal (who can see what, per PRIV-07). Enforced by: code review.
- **CONTENT-04** Streaks MUST NOT be loss-framed ("you lost your streak"); rest days and pauses are allowed. Enforced by: code review, `tests/test_patient.py::test_streak_same_day_and_gap`.
- **CONTENT-05** Points, badges and leaderboards MUST NOT attach to PHQ-9/GAD-7, mood scores or disclosing distress. Enforced by: `tests/test_patient.py::test_assessment_and_mood_give_no_points`.
- **CONTENT-06** Points MUST have a daily cap. Enforced by: `tests/test_patient.py::test_points_have_daily_cap`.
- **CONTENT-07** The product is "not a medical device"; wording MUST say screening/wellbeing support, not diagnosis. Enforced by: code review.

## PERF: budgets (proposals; DESIGN.md and PRD.md override when they set numbers)

- **PERF-01** Server pages SHOULD respond in under 300 ms p95 and JSON APIs under 200 ms p95 on the dev dataset, excluding model calls. **[proposal]** Enforced by: manual profiling.
- **PERF-02** Model calls MUST have a timeout (`GEMINI_TIMEOUT`, default 20 s) and a canned fallback; the page MUST NOT block on them without a visible loading state. Enforced by: `ai/gemini_impl.py`, `tests/test_safety.py::test_crisis_fails_conservative`.
- **PERF-03** No N+1 queries; aggregate in SQL; reads are capped (API-06, DB-07). Enforced by: `tests/test_db.py::test_institutional_summary_is_constant_query_count`.
- **PERF-04** Large or below-the-fold assets (video, audio, charts) MUST lazy-load; audio MUST come from `AUDIO_BASE_URL` when not on disk. SHOULD keep the initial page under about 1 MB. **[proposal]** Enforced by: manual.
- **PERF-05** Input handlers that call the server on each keystroke MUST debounce (>= 300 ms). Enforced by: code review.
- **PERF-06** Caches MUST have a TTL and MUST NOT hold per-user PHI in a shared cache key. Enforced by: code review.

## TEST: quality gate

- **TEST-01** `pytest tests -q` MUST pass before a PR is opened. Enforced by: author, reviewer.
- **TEST-02** Bug fixes MUST start with a failing test that reproduces the bug, then the fix. Enforced by: PR review checklist.
- **TEST-03** New behaviour MUST ship with tests; security and safety behaviour MUST have a negative test (what must NOT happen). Enforced by: PR review checklist.
- **TEST-04** Tests MUST be hermetic: temp DB, no network, no live model, no wall-clock dependence. Enforced by: `tests/conftest.py`.
- **TEST-05** Scripts in `tests/manual/` are not tests and are excluded by `pytest.ini`; do not rely on them. Enforced by: `pytest.ini`.
- **TEST-06** A test that is flaky or skipped MUST have an owner and a reason in the PR; deleting a failing test to go green is forbidden. Enforced by: code review.
- **TEST-07** Run tests in a venv that has `requirements-dev.txt` installed (see MEMORY.md snapshot); a green run in a different environment MUST say which. Enforced by: manual.

## GIT / RELEASE

- **GIT-01** Branch names: `feat/<slug>`, `fix/<slug>`, `docs/<slug>`, `chore/<slug>`, `sec/<slug>`. Enforced by: manual.
- **GIT-02** PRs SHOULD be small (one concern, under about 400 changed lines excluding generated files and tests). Enforced by: reviewer.
- **GIT-03** Commit messages: imperative subject under 72 chars, body explains why. Enforced by: reviewer.
- **GIT-04** `.env`, `*.db`, `instance/`, `flask_session/`, logs, `*.mp3`, backups and zips MUST NOT be committed. Enforced by: `.gitignore`; PR checklist runs `git status` before commit.
- **GIT-05** This folder is currently not a git repository on this machine. Sync with https://github.com/ayushjaiswal21/MindFullHorizon happens only when the owner asks, via explicit instruction. Enforced by: AGENT-04.
- **GIT-06** Force-push, history rewrite and branch deletion on the shared remote MUST NOT happen without explicit owner approval. Enforced by: AGENT-04.
- **GIT-07** A release (tag/deploy) needs: tests green, migration reviewed, `.env.example` updated for new variables, docs updated per [README.md](README.md) ownership table. Enforced by: Definition of Done.

## OPS

- **OPS-01** `/health` (process alive) exists; a `/ready` endpoint (DB reachable, migrations at head, unacknowledged crisis events older than a threshold) SHOULD be added. **[target]** Enforced by: manual (add test).
- **OPS-02** Production logs MUST be structured, to stdout, with a request id and no patient text (CODE-03). **[target]** for request ids.
- **OPS-03** Production MUST use PostgreSQL, run `flask db upgrade` before starting the app, and run one eventlet worker: `gunicorn --worker-class eventlet --workers 1 app:app`. Enforced by: [DEVELOPMENT.md](DEVELOPMENT.md), `Dockerfile`.
- **OPS-04** Keys MUST be rotated on exposure and at least every 90 days; rotation = new key in the host's secret store, redeploy, revoke old. Enforced by: manual.
- **OPS-05** Database backups MUST run daily in production, with a restore drill at least quarterly; a backup never restored is not a backup. **[target]** Enforced by: manual.
- **OPS-06** Do not use serverless hosts for this app (WebSockets, long-lived worker). Enforced by: ADR-008 in [MEMORY.md](MEMORY.md).

## AGENT: rules for AI coding agents in this repo

- **AGENT-01** The project root is `d:\MINDFULLHORIZON2.0\MindFullHorizon`. Agents MUST NOT read, edit or run anything in the parent `d:\MINDFULLHORIZON2.0` (old copies, `main.py`, `models.py`, backup zip) unless the owner says so. *The parent holds stale prototypes that look like current code.*
- **AGENT-02** When several agents run in parallel, each MUST have an explicit file ownership list from the lead and MUST NOT edit files outside it; if a needed change is outside it, report it instead.
- **AGENT-03** Agents MUST read before editing, make targeted edits (CODE-06), and follow test-first for bugs (TEST-02). They MUST NOT regenerate or reformat whole files.
- **AGENT-04** Agents MUST NOT take destructive or irreversible actions without explicit owner approval in the current session: deleting files or data, resetting or migrating the DB, `git push`, force operations, rotating or printing secrets, installing system software. A past instruction is not approval for a new action.
- **AGENT-05** Agents MUST NOT touch `.env` contents, print secret values, or copy them into docs, logs or prompts.
- **AGENT-06** Agents MUST report faithfully: what changed, what was run, what failed and what was not checked. A failing or skipped test MUST be stated, never hidden. Do not claim "tested" for anything not executed.
- **AGENT-07** Research claims marked UNVERIFIED or SECONDARY (in `docs/research/` and [SAFETY_RESEARCH.md](SAFETY_RESEARCH.md)) MUST be treated as unverified: do not turn them into UI copy, legal claims or hard requirements without a primary source.
- **AGENT-08** Do not duplicate content between docs; link to the owner doc (see [README.md](README.md) ownership rule). Facts in docs MUST be checkable against files or tests.
- **AGENT-09** Docs lag code: when STATUS.md, DEVELOPMENT.md or README disagree with code and tests, the code and tests win; record the mismatch in the hand-off and fix the doc if you own it.
- **AGENT-10** Agents MUST NOT weaken a safety or security test, helpline list, crisis floor or consent rule to make a change pass; stop and ask.
- **AGENT-11** Do not create new top-level files, docs or dependencies unless the task needs them; prefer editing existing ones.

---

## PR review checklist (one page)

Author ticks before requesting review; reviewer confirms.

1. **Scope**: one concern; diff is minimal; no unrelated reformatting; no files outside the stated scope.
2. **Tests**: `pytest tests -q` green (state the environment); bug fix has a test that failed first; negative test for any security/safety rule.
3. **Routes**: in a blueprint; decorators in order (rate limit, `login_required`, role); 401 vs 403 vs 404 correct; query filtered by session user / institution; input validated; list capped.
4. **Errors and logs**: no `str(e)` or traceback to clients; no patient text, emails or profile data in logs; DB writes commit/rollback.
5. **DB**: model change has an Alembic migration (`flask db migrate`, reviewed, upgrade tested); constraints and indexes added; no raw destructive SQL; no demo credentials.
6. **Frontend**: no Jinja in `static/js`; no `innerHTML` with untrusted text; CSRF token sent on writes; no inline-script growth; lazy-load heavy assets.
7. **Security**: no secrets in code or docs; `.env.example` updated for new env vars; new endpoints rate limited; uploads validated.
8. **Privacy**: new field justified in PRD; who-can-see-what is true; retention and deletion path considered.
9. **AI**: disclosure present; rules in `system_instruction`; output validated; crisis floor untouched or strengthened; injection corpus run (report result); no diagnosis or prescribing; model and key from env.
10. **Crisis/helplines**: numbers only from `utils/helplines.py`; no user text in crisis events; alert durable and acknowledgeable.
11. **Content**: no fake stats, testimonials or "encrypted"/"compliant" claims; no loss-framed streaks; no points on assessment or mood.
12. **Performance**: no N+1; timeouts on external calls; caches have TTL.
13. **Docs**: owner doc updated per [README.md](README.md); TRACKER item updated; ADR added in MEMORY.md if a decision changed.
14. **Hygiene**: `git status` shows no `.env`, `.db`, mp3, logs, zips.

## Definition of Done

A change is done only when all hold:

- [ ] Behaviour works as described in the PRD/TRACKER item and was exercised (tests, and the running app for UI changes).
- [ ] `pytest tests -q` passes; new tests cover the change and its failure modes.
- [ ] Every applicable rule above is met or the exception is written in the PR with an owner and date.
- [ ] Migration included, reviewed and round-trips (`upgrade`, `downgrade`) if the schema changed.
- [ ] No new secret, key, PHI, demo credential or large binary in the tree.
- [ ] `.env.example` and [DEVELOPMENT.md](DEVELOPMENT.md) updated if configuration changed.
- [ ] Docs updated per the ownership table in [README.md](README.md); ADR added if a decision was made.
- [ ] Safety-affecting changes (crisis, scoring, AI, helplines, consent) reviewed by a second person; clinical wording reviewed by a clinician before public launch.
- [ ] The PR or hand-off states what was run, what failed, and what was not checked.
