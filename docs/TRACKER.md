# Tracker

Last updated: 2026-11-24. Single place for work status. Rule: an item is **Done** only with a test or a verifiable file/behaviour in the "Evidence" column. Update this file in the same PR as the change (see [RULES.md](RULES.md)).

Test suite: **265 passed (fresh venv, lean requirements, 2m57s)** (run `pip install -r requirements-dev.txt && pytest tests -q`).

## 1. Done

| ID | Area | What changed | Evidence |
|----|------|--------------|----------|
| D-01 | Cleanup | ~70 dead files removed (demo seeders, upload patches, `secure_routes`/`security_fixes`, `.bak`, generated caches, `.kiro`), root reorganised; backup zip kept outside the repo | git diff; `docs/MEMORY.md` |
| D-02 | DB | Old DB with demo accounts deleted; `init_db` import bug fixed; schema built from `models.py` | `tests/test_smoke.py` |
| D-03 | Security | Open endpoints now need login and use the session user (`/api/chat`, `/api/ask`, `/api/mood`, `/api/chats/<id>/messages`, `/patient/api/progress`, `/api/play-mood` no longer runs `os.startfile`) | `tests/test_security.py` |
| D-04 | Security | Public signup is patient-only; provider needs `PROVIDER_INVITE_CODE`; `/save_role` cannot grant provider | `tests/test_security.py` |
| D-05 | Security | `SECRET_KEY` fallback removed (production refuses to start); SocketIO needs login and room authorisation; same-origin CORS; security headers (CSP is Report-Only); sane rate limits | `tests/test_security.py` |
| D-06 | Security | Google OAuth: correct endpoints, verified-email link only, random hash for new users, Lax cookies | `tests/test_security.py` |
| D-07 | Safety | Crisis detection rewritten (word boundary, Hinglish, negation, third-party); a crisis hit forces the emergency path regardless of the model; helplines from one config (`utils/helplines.py`) | `tests/test_safety.py` (128 tests) |
| D-08 | Safety | PHQ-9/GAD-7 scored on the server, item 9 rule, canonical assessment types, crisis event on item 9 or severe score | `tests/test_safety.py` |
| D-09 | AI | `system_instruction`, `GEMINI_MODEL_NAME`, request timeout, safe handling of blocks and bad model output, no US helplines, no model output in logs | `tests/test_safety.py` |
| D-10 | AI/UX | Chat renders with `textContent` (no stored XSS), AI disclosure on chat page, persona renamed "Anya" | `tests/test_safety.py`, `tests/test_integration.py` |
| D-11 | Patient | `award_points` commits, daily cap, UTC-day streaks; no points for assessments or mood | `tests/test_patient.py` |
| D-12 | Patient | Mood double-save removed, honest "No data yet" dashboard, fake stats/testimonials/encryption claims removed from index, landing, signup | `tests/test_patient.py` |
| D-13 | Patient | Medication ownership check + fetch UI; goal validation; appointment validation and slot conflict check; digital detox one log per day | `tests/test_patient.py` |
| D-14 | Patient | Journal and voice logs stored in the DB (`JournalEntry`, `VoiceLog`), `upload_voice` rebuilt | `tests/test_patient.py` |
| D-15 | DB | Indexes, cascades, FK pragma, CHECK constraints, `CrisisEvent`, institutional summary as SQL aggregates, Alembic baseline, `scripts/seed_demo.py` | `tests/test_db.py` |
| D-16 | Provider | Exact institution scoping, risk from PHQ/GAD and unacknowledged crisis events, crisis panel with acknowledge, Jinja removed from static JS, telehealth room from server | `tests/test_provider.py` |
| D-17 | Blog | Author checks, drafts hidden, `is_published` parsing, like/comment/replies API in the blueprint, XSS-safe rendering | `tests/test_blog.py` |
| D-18 | UI | Landing page for guests at `/`, yoga video library page (verified video ids), redundant `edit_profile.html` removed | `tests/test_smoke.py`, `tests/test_patient.py` |
| D-19 | Build | `requirements.txt` cut to direct imports (96 packages after install vs ~160), voice stack optional, dev requirements split, `jsmin`/`cssmin` added (fresh installs used to 500), Dockerfile on Python 3.11 with `flask db upgrade`, `.dockerignore` | fresh-venv full test run; `tests/test_integration.py` |
| D-20 | Compliance | Server-side consent check on signup; "n/a" instead of fake/None metrics | `tests/test_integration.py` |
| D-21 | Docs | PRD, ARCHITECTURE, DESIGN, RULES, MEMORY, TRACKER, STATUS, MIGRATIONS, SAFETY_RESEARCH, three research notes, README, SECURITY, CLAUDE.md | `docs/README.md` |

## 2. Open issues

| ID | Sev | Issue | Where | Wave |
|----|-----|-------|-------|------|
| O-01 | Critical | A crisis alert can be lost: `record_crisis` commits after the assessment save and swallows errors. Write it in the same transaction and add timed escalation | `utils/crisis.py`, `routes/patient.py` | Q |
| O-02 | Critical | Journal text and the legacy socket chat do not create a `CrisisEvent` (chat API and PHQ-9 do) | `routes/patient.py`, `app.py` | Q |
| O-03 | High | Owner action: rotate the real Gemini key that sits in the local `.env` | `.env` (not in git) | owner |
| O-04 | High | Health data is plaintext at rest; no access audit log; consent is a checkbox only (no stored timestamp/version) | `models.py` | Q |
| O-05 | High | No age gate or verifiable parental consent for under-18 users (DPDP) | signup | F2 + product |
| O-06 | High | Prescriptions have no prescriber or drug verification; Telemedicine Practice Guidelines allow only registered doctors to prescribe | `routes/provider.py` | product |
| O-07 | High | Provider scope is institution-wide, not assigned-patients-only | `routes/provider.py` | product |
| O-08 | High | `/api/message` has no recipient check and returns `str(e)` | `app.py` | Q |
| O-09 | High | `provider.telehealth_session` page and the socket join use different authorisation rules; use `can_join_telehealth` in both | `routes/provider.py`, `decorators.py` | Q |
| O-10 | Medium | CSP is Report-Only (inline handlers remain) | `app.py`, templates | F1 |
| O-11 | Medium | `/health` always returns 200; no `/ready` | `app.py` | Q |
| O-12 | Medium | `google.generativeai` SDK is end-of-life; model default `gemini-flash-latest` never exercised against the live API | `ai/gemini_impl.py` | Q |
| O-13 | Medium | Datetime mix (`utcnow` vs `now`); IST "today" misaligned for medication and provider queries | `routes/provider.py`, `routes/patient.py`, `models.py` | Q |
| O-14 | Medium | Appointment status `completed` is never set, so completion rate is mostly `None` | `routes/provider.py` | Q |
| O-15 | Medium | `app.py` is still a ~2000-line legacy file (audio/music, voice, OAuth, sockets) | `app.py` | P |
| O-16 | Medium | `BlogComment` has no `user` relationship; blog code references an `admin` role the DB forbids | `models.py`, `routes/blog.py` | Q |
| O-17 | Medium | `import app` takes ~10 s and 160 MB: nltk data check and eager imports at startup | `app.py` | P |
| O-18 | Medium | "Daily Mood" assessment is scaled x2 (assumes 1-5) while mood is stored 1-10 | `routes/patient.py` | Q |
| O-19 | Low | Breathing/yoga duration unbounded; AI prompt says reply max 200 chars while code clamps at 400 | `routes/patient.py`, `ai/service.py` | Q |
| O-20 | Low | Hinglish/Devanagari phrase lists need review by a clinician and Hindi speakers | `ai/severity.py` | owner |
| O-21 | Medium | No CI yet (pytest + `scripts/scan_imports.py` on every push) | repo | Q |
| O-22 | Medium | Client-side `/api/message`-style leftovers and unused `get_user_wellness_trend` stub in `models.py` | `models.py`, `app.py` | P |

Wave key: **F** frontend/SEO, **P** performance, **Q** queue/reliability/security hardening, **owner** needs the repo owner, **product** needs a product decision.

## 3. Planned waves

### F: frontend, SEO and UX (3 agents, after the current code freeze)
- Shell: dark mode toggle, cookie/consent banner (essential-only by default), scroll progress, back-to-top check, mobile menu accessibility, print stylesheet, reduced-motion everywhere, toast system, loading skeletons and shared empty states, hover/focus states, site search, "last updated" footer, breadcrumbs.
- Head/SEO: unique title and meta description per page, canonical, Open Graph + Twitter with a real 1200x630 image, schema.org JSON-LD, `noindex` for private pages, `/robots.txt`, `/sitemap.xml`, 404/500 pages, favicon set, internal links between related pages.
- Components: password show/hide, inline form error and success states (`aria-invalid`, `aria-live`), confirmation modal, copy helper, accessible accordion, contact form (stored in DB, email by SMTP through the job queue), consent-gated first-party event tracking and UTM capture.

### P: performance
- Lazy-import heavy libraries; drop the nltk download at import; measure `import app` (today ~10 s, 160 MB RSS).
- Replace the Tailwind 2.2.19 CDN CSS with a purged build; self-host and subset fonts; `defer` scripts; per-page JS chunks; lazy-load images, iframes and Chart.js; WebP images; debounce input handlers.
- N+1 removal, pagination contract for list APIs, DB pooling per dialect (SQLite vs PostgreSQL), TTL cache for expensive aggregates, cache headers on hashed assets, JSON/HTML compression.
- Memory-leak sweep: unbounded caches, session files on disk, socket rooms, JS listeners and intervals; measure with tracemalloc.

### Q: queue, reliability and LLM security
- DB-backed `jobs` table (outbox, retries with backoff, dead-letter) and a worker loop; first jobs: crisis escalation, AI insights, email.
- Idempotency keys and unique constraints for assessment save, daily mood, medication log, appointment slot, points.
- Appointment, crisis and job state machines; atomic counters; optimistic locking where needed.
- Gemini resilience: circuit breaker, bounded retries, per-user budgets; prompt-injection test corpus (`tests/test_llm_injection.py`) from `docs/research/llm-security.md`; `/health` + `/ready`; structured logs with request id; audit log.
- Details: [DESIGN.md](DESIGN.md), research in `docs/research/`.

## 4. Decisions needed from the owner

| ID | Question | Why it blocks |
|----|----------|---------------|
| P-01 | Keep, gate or remove the prescription feature (registered-doctor verification)? | O-06; legal exposure |
| P-02 | Should counsellors see all students of an institution or only assigned students? | O-07; privacy model |
| P-03 | Where to host the six real audio tracks (bucket URL for `AUDIO_BASE_URL`)? They are still tracked in the old git history | music on hosted deploys |
| P-04 | Contact-form recipient address and SMTP provider | F wave |
| P-05 | Who is the data fiduciary, and the privacy policy / consent text and version | O-04, O-05 |
| P-06 | Merge policy for `main` (the cleanup branch rewrites most of the tree) | release |

## 5. Changelog

- 2026-11-24: first cleanup, security, safety, patient, DB and provider fix waves merged on branch `cleanup/overhaul-2026-11`; docs set written; lean requirements; this tracker created.
