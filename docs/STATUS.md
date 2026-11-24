# Status (Nov 2026)

Short summary only. Item-level detail and IDs live in [TRACKER.md](TRACKER.md); the target product is in [PRD.md](PRD.md).

**Tests:** 265 passed (fresh venv, lean requirements, 2m57s).
**Estimate:** about 60% of the documented feature scope exists. The critical security and safety defects from the first audit are fixed and covered by tests. It is **not yet ready for a public launch** (see "Before launch").

## Feature status

| Area | State |
|------|-------|
| Blog, medication, yoga/breathing/music logs, digital detox, goals, journal, voice logs | Implemented (journal and voice logs now in the DB) |
| PHQ-9 / GAD-7 | Implemented: server-side scoring and item-9 rule |
| AI companion | Implemented with fallbacks; crisis floor is deterministic; model use needs a valid `GEMINI_API_KEY` |
| Crisis detection and escalation | Partial: detection, helplines, crisis event and provider acknowledge exist; alert durability and timed escalation are open (O-01, O-02) |
| Provider dashboard, appointments | Implemented with institution scoping; assigned-only scoping is a product decision (O-07) |
| Telehealth | Partial: authorised signalling; no TURN server, no session record |
| Prescriptions | Exists but unverified prescriber: needs a decision (O-06) |
| Gamification | Implemented and capped; never tied to assessments or mood |
| Remote patient monitoring, predictive analytics, peer support | Missing |

## Before launch (blocking)

1. Rotate the Gemini key that was in the local `.env` (O-03).
2. Durable crisis alerts and escalation (O-01, O-02).
3. Age gate and stored consent record (O-04, O-05); privacy policy text (P-05).
4. Decide on prescriptions and provider scope (P-01, P-02).
5. Enforce CSP, add `/ready`, CI (O-10, O-11, O-21).

## Not blocking, planned

Frontend/SEO wave, performance wave and queue/reliability wave: see [TRACKER.md](TRACKER.md) section 3.
