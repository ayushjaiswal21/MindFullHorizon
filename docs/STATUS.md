# Status (2026-11-25, AI build wave and cleanup pass)

Short summary only. Item-level detail and IDs live in [TRACKER.md](TRACKER.md); the target product is in [PRD.md](PRD.md); the owner's decisions are in [MEMORY.md](MEMORY.md).

**Tests:** about 2,000 pytest tests (the last full run before this update: 2,013 passed, 5 skipped, 3 failures that were fixed afterwards). The real-browser checks in `tools/e2e/` (Edge via playwright-core) were run by hand for the assessment flow, chat, breathing guide, colour themes and the clinical pages; they are not part of `pytest`.
**Where it stands:** feature-complete for a supervised pilot demo, **not cleared for real students**. Nothing has been reviewed by a clinician or a lawyer (see "Before real students").

## Feature status

| Area | State |
|------|-------|
| Student tools: mood (1-10), PHQ-9 / GAD-7 (server scoring, item-9 rule), journal, goals, breathing guide, yoga, music, digital detox, medication log, appointments | Built and tested; assessment and breathing verified in a real browser |
| Gentle gamification (daily visit, activity points, streak with one forgiven day a week, badges) | Built. Never tied to mood or screening scores; no leaderboard |
| AI companion "Anya" | Built: fixed crisis reply (the model is never asked on crisis text), saved answers for 6 template questions, print and copy, 10 s hard deadline, circuit breaker, per-user budgets (in memory). Live Gemini never exercised in CI |
| Crisis alerts | Durable (written in the same transaction), timed escalation at 15, 30 and 45 minutes, email only if the operator configured it. Fuzzy, typo-tolerant crisis-vocabulary matching (`ai/fuzzy_crisis.py`) added on top of the deterministic keyword/negation detector. Mood entries have no crisis detector |
| Chat routing | Lexical chat router (`ai/router.py` + `ai/kb.py`), clinician-approved, on by default in production (`CHAT_ROUTER_ENABLED=1`); answers an ordinary (non-crisis) message locally from a fixed knowledge base before falling back to the model |
| Mood/sleep trend flags | Deterministic trend flags over recent mood and sleep logs (`utils/trend_flags.py`); no AI call, no points or streaks attached |
| Accessibility | Device-only, browser-native text-to-speech "Listen" button (`static/js/speech-output.js`); nothing is sent to a server. Voice-tone / emotion inference was built, then explicitly removed (migration 0010) after `docs/research/ai/SYNTHESIS.md` found pitch-based mood detection invalid (mostly detects pitch/sex, not mood) |
| Counsellor and doctor dashboard (one provider role, `provider_type`) | Built: assigned patients only, aggregates hidden below 5, crisis panel, audit log |
| Admin role (`/admin/login`) | Built: overview, doctor verification, catalogue, inventory, dispensing, reports, audit, messages, annual report; `flask create-admin` |
| Prescriptions and inventory | Built and ON by owner decision (verified doctor required, List C and controlled drugs blocked, FEFO stock, two-step dispensing). **Needs legal and pharmacist review before real use** |
| Safety plan, sleep log, reminders, post-crisis follow-up | Built: patient safety plan (`services/safety_plan.py`), sleep log (`services/sleep_log.py`), reminder preferences and sending (`services/reminders.py`, `utils/followup_jobs.py`), post-crisis follow-up tracker (`utils/followups.py`, `models/` follow-up tables) |
| Privacy | Consent and age (18+) records, export and delete (`/account/data`), privacy and terms pages (drafts) |
| SEO and shell | Design system, dark and light themes (new calm palettes), sitemap, robots, search, consent-gated first-party analytics |
| Deploy | Render + Neon kit (`render.yaml`, `docs/DEPLOY.md`, `scripts/predeploy_check.py`); cookie sessions with revocation stamp, no local file storage, ProxyFix, stdout logs, event-driven job worker. Docker build and a live deploy were never run |
| Missing | Hindi UI, SMS paging, drug-interaction checking, telehealth TURN server, peer support |

## Before real students (blocking)

1. Clinician review of crisis phrases and the safety flow ([review/CLINICIAN_REVIEW_PACKET.md](review/CLINICIAN_REVIEW_PACKET.md)). Not started.
2. Legal review ([review/LEGAL_REVIEW_PACKET.md](review/LEGAL_REVIEW_PACKET.md)): data fiduciary agreement with the college, privacy and terms text, prescribing and pharmacy rules. Not started.
3. Rotate the Gemini key (the old key was in a local `.env`).
4. Pilot plan gates ([review/PILOT_PLAN.md](review/PILOT_PLAN.md)): named on-call counsellor, always-on hosting (a free Render instance sleeps and the escalation timers stop), `CRISIS_ESCALATION_EMAIL`, backup and restore drill.
5. Walk every page in a browser on a phone width and in both themes (layout sweep still open, see TRACKER).

## Not blocking, planned

Layout sweep at 390 to 1440 px, per-page meta tags, CSP enforcement, the 300-line file split, new patient and counsellor features: see [TRACKER.md](TRACKER.md).
