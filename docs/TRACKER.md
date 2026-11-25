# Tracker

Last updated: 2026-11-25. Single place for work status. Rule: an item is **Done** only with a test or a verifiable file or behaviour in the "Evidence" column. Update this file in the same PR as the change (see [RULES.md](RULES.md)).

Test suite: about 2,000 tests (run `pip install -r requirements/dev.txt && pytest tests -q`). Real-browser checks: `tools/e2e/` (see its README).

## 1. Done

| ID | Area | What changed | Evidence |
|----|------|--------------|----------|
| D-01 | Cleanup | Dead files removed, root reorganised (requirements/, tools/, docs/SECURITY.md, tests/pytest.ini); old branches merged and deleted, old `main` kept as tag `pre-overhaul-2026-11` | git history; docs/MEMORY.md |
| D-02 | Security | Authenticated endpoints, patient-only signup, invite codes for staff, SocketIO authorisation, OAuth fixes, headers | tests/test_security.py |
| D-03 | Safety | Deterministic crisis detection (Hinglish, negation, third party); PHQ-9/GAD-7 scored on the server with the item-9 rule; the emergency path shows a fixed reply and never waits on the model | tests/test_safety.py, test_llm_injection.py |
| D-04 | Crisis alerts | Event and job written in the caller's transaction; escalation at 15, 30, 45 minutes; journal and socket chat covered; `/health` and `/ready` | tests/test_crisis_durability.py, test_jobs.py, test_ops.py |
| D-05 | LLM security | Input guard, delimited data blocks, output guard, circuit breaker, budgets, 68-attack corpus, interactive 10 s deadline | tests/test_llm_injection.py, test_llm_resilience.py, test_ai_latency.py |
| D-06 | Data integrity | Idempotency keys, unique and partial unique constraints, appointment state machine, atomic points ledger, IST day handling | tests/test_idempotency.py, test_state.py, test_migrations.py |
| D-07 | Privacy | 18+ gate and consent records, assigned-only provider access, aggregates hidden below 5, audit log, export and delete | tests/test_privacy.py, test_provider_scope.py |
| D-08 | Clinical | Roles patient, provider (`provider_type` counsellor or doctor), admin; prescriber verification; prescriptions; medicine inventory with FEFO and two-step dispensing; admin dashboards; `flask create-admin` | docs/CLINICAL_DESIGN.md; tests/test_prescriber.py, test_rx_*.py, test_inventory.py, test_admin_api.py, test_ui_clinical.py |
| D-09 | Frontend | Design system, new light and dark palettes (105 contrast pairs pass), redesigned pages for all roles, honest landing comparison section, privacy, terms, FAQ, contact | tests/test_design_rules.py, test_theme_contrast.py, test_landing_claims.py, test_pages.py |
| D-10 | Real-use bugs | Assessment Start buttons (script order), progress page (AI no longer in render), chat (legacy handler, template bubbles, saved answers, print), breathing guide (reduced-motion), compact helpline card, admin sign-in (session stamp), header overflow | tests/test_ai_not_in_render.py, test_chat_templates.py, test_breathing_ux.py, test_login_stamp.py; tools/e2e/specs |
| D-11 | Gamification | Daily visit and activity points, forgiving streak, badges, never tied to mood or assessment scores | tests/test_gamification_ux.py; docs/GAMIFICATION.md |
| D-12 | Performance | Lazy heavy imports, pooling, pagination contract, cache with invalidation, flat query counts, memory test | tests/test_perf.py; docs/PERFORMANCE.md |
| D-13 | Deploy kit | Render + Neon files, predeploy checker, cookie sessions with stamp, no local uploads, ProxyFix, stdout logs, Neon options, event-driven worker | tests/test_deploy_code.py, test_deploy_config.py, test_jobs_wake.py; docs/DEPLOY.md |
| D-14 | Research and review kits | Competitive research, prescribing research, colour research; clinician, legal and pilot packets with an exporter | docs/research/, docs/review/ |
| D-15 | AI build wave (2026-11-25) | Fuzzy, typo-tolerant crisis-vocabulary matching on top of the deterministic detector; a clinician-approved lexical chat router answering ordinary messages from a fixed knowledge base before the model (`CHAT_ROUTER_ENABLED=1` in production); deterministic mood/sleep trend flags (no AI call, no points/streaks); a device-only browser text-to-speech "Listen" button. Voice-tone/emotion inference was built, then explicitly removed as invalid per research | `ai/fuzzy_crisis.py`, `ai/router.py`, `ai/kb.py`, `utils/trend_flags.py`, `static/js/speech-output.js`, migration 0010, `docs/research/ai/SYNTHESIS.md` |
| D-16 | Patient tools (shipped since D-10, mis-tracked as missing) | Safety plan builder, sleep log, email reminders, post-crisis 3-session follow-up tracker | `services/safety_plan.py`, `services/sleep_log.py`, `services/reminders.py`, `utils/followups.py`, `utils/followup_jobs.py`, `models/` follow-up and wellbeing tables; `tests/test_safety_plan.py`, `test_grounding_sleep.py`, `test_reminders*.py`, `test_followup_tracker.py` |
| D-17 | Cleanup (2026-11-25) | `extensions.py`/`decorators.py` moved into `core/` (old files kept as re-export shims); flat `models.py` split into a `models/` package by domain, re-exported from `models/__init__.py` | `core/`, `models/` |
| D-18 | Cleanup (2026-11-25) | O-12/AI-11: migrated off the end-of-life `google.generativeai` SDK to `google-genai` (`Client(api_key=...).models.generate_content(model=..., contents=..., config=types.GenerateContentConfig(...))`); same external interface, model selection, system-instruction wiring, timeout/retry/breaker behaviour | `ai/gemini_impl.py`, `requirements.txt`; tests/test_safety.py |

## 2. Open issues

| ID | Sev | Issue | Where |
|----|-----|-------|-------|
| O-01 | High | Owner action: rotate the Gemini key (the old key sat in a local `.env`); the live Gemini path was never exercised in CI | `.env` |
| O-02 | High | Clinician review of crisis phrases and the safety flow (not started); the crisis wording now tells the student that college counsellors can see an alert, wording needs sign-off | docs/review/ |
| O-03 | High | Legal review: DPA with the college, privacy and terms drafts, prescribing and pharmacy rules, prescription deletion with the patient account, record retention | docs/review/ |
| O-04 | High | Health data is plaintext at rest (no field encryption); do not claim otherwise | `models/` |
| O-05 | High | Free Render sleeps and stops escalation timers: a pilot needs an always-on instance, `CRISIS_ESCALATION_EMAIL`, an on-call counsellor SOP | docs/DEPLOY.md, docs/review/PILOT_PLAN.md |
| O-06 | Medium | Mood entries have no crisis detector | `routes/mood.py` |
| O-07 | Medium | Layout sweep at 390 to 1440 px in both themes (known: `/patient/schedule` overflows at 390 px) | templates, CSS |
| O-08 | Medium | Per-page meta tags, `/ai` in the sitemap, CSP still Report-Only (needs `frame-src` for youtube-nocookie) | templates, `app.py` |
| O-09 | Medium | 300-line file limit: 19 files still exceed it (`app.py`, `routes/provider.py`, `routes/audio.py`, `routes/auth.py`, `scripts/export_review_packet.py`, `ai/service.py`, `utils/llm_guard.py`, several JS, test files, `static/css/site.css`). `models.py` and `routes/patient.py` were split into packages 2026-11-25 (see D-17) | repo, `scripts/oversize_baseline.json` |
| O-10 | Medium | Legacy assets still loaded or dead: `static/js/scripts.js`, `enhanced.css`, `fallback-cards.css`, old inline JS bundle, `legacy_head` and `legacy_scripts` blocks in `base.html` | static, templates |
| O-11 | Medium | PostgreSQL paths (row locks, partial indexes, migrations) and the Docker build were never run; only SQLite was available | docs/DEPLOY.md |
| O-13 | Medium | Budgets, breaker, cache and rate limiter are per process; a second worker needs Redis | docs/PERFORMANCE.md |
| O-14 | Low | Logout is GET; no timing equalisation on login; rejecting an appointment keeps the provider link; blog like toggle race returns 500 | routes |
| O-15 | Low | No CI yet (pytest and `scripts/scan_imports.py` on every push) | repo |
| O-16 | Low | Hinglish and Devanagari phrase lists need native-speaker and clinician review | `ai/severity.py` |
| O-17 | Low | Hindi UI, SMS paging, drug-interaction database, telehealth TURN server, peer support are not built | PRD |

## 3. Decisions (owner, 2026-11-24)

| ID | Decision |
|----|----------|
| P-01 | Prescriptions ON everywhere, gated by a verified doctor; legal and pharmacist review still pending (O-03) |
| P-02 | Counsellors and doctors see assigned patients only; institution aggregates hidden below 5; crisis alerts visible institution-wide without patient text, always audited |
| P-03 | Audio served from `AUDIO_BASE_URL`; git history rewrite deferred |
| P-04 | Contact form saved first, email through the job queue when SMTP is configured |
| P-05 | The college is the data fiduciary and the project owner is the processor (DPA); 18+ only |
| P-06 | `main` fast-forwarded to the overhaul (done); old `main` tagged; only green checkpoints are pushed |
| P-07 | Crisis text tells the student that college counsellors who use the app can see an alert |
| P-08 | Alert channel for the pilot: dashboard, email and a named on-call counsellor by phone; no SMS yet |
| P-09 | Deploy on Render (web) and Neon (Postgres) |

## 4. Changelog

- 2026-11-25: AI build wave (fuzzy crisis matching, lexical chat router, trend flags, device-only TTS; voice-tone inference removed as invalid); cleanup pass (`core/` package, `models/` package split); STATUS.md and TRACKER.md corrected where they still said "not built" for shipped features.
- 2026-11-24 (evening): clinical build (admin, doctor, prescriptions, inventory), redesign, colour themes, real-use bug fixes (assessment, progress, chat, breathing), gamification, deploy-readiness code. Docs refreshed.
- 2026-11-24 (morning): first cleanup, security, safety, patient, DB and provider waves; docs set written.
