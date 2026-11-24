# MindFull Horizon: working notes

Flask mental-health app for Indian college students, counsellors, doctors and admins. Read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/STATUS.md](docs/STATUS.md) first.

## Commands
- Run with demo data: `python scripts/local_demo.py` (http://127.0.0.1:5000, throwaway `instance/demo.db`, demo password `Demo@Pass2026`; `--reset` starts fresh). Plain `python app.py` also works.
- Test: `pytest tests -q` (temp DB, no Gemini calls; fixtures in `tests/conftest.py`; settings in `tests/pytest.ini`).
- Browser checks (Edge via playwright-core): `tools/e2e/` (see its README). Run them for any UI change; unit tests alone missed real bugs.
- CSS: `cd tools/frontend && npm ci && npm run build:css` after adding layout classes; commit `static/css/tailwind.css`.

## Rules
- New routes go in `routes/` blueprints, never in `app.py`. `models.py` (and `models_clinical.py`) is the schema source of truth; schema changes need an Alembic migration.
- **No source file over 300 lines** (Python, JS, CSS, HTML, tests). Build new code in small modules; never grow a file that is already over the limit. Exceptions: generated or minified files and Alembic migrations.
- Every user-data route needs `@login_required` plus a role decorator and must filter by the session user (no trusting a client-sent user_id). Providers see assigned patients only.
- Never return `str(e)` to clients; never log patient text.
- Never call the AI while rendering a page; load AI output through a capped endpoint. The crisis path never waits on the model.
- Static JS must not contain Jinja tags (`{{ }}`); pass server values via `data-*` attributes or a JSON script block. No inline `on*=` handlers.
- Helpline numbers come from one config (Tele-MANAS 14416, KIRAN 1800-599-0019, 112); see [docs/SAFETY_RESEARCH.md](docs/SAFETY_RESEARCH.md).
- Never attach points or streaks to assessment or mood scores.
- No fake claims in UI copy (stats, testimonials, "encrypted" unless it is true). Design bans (no emoji, em dashes, purple gradients, pill buttons, motion gimmicks) are in [docs/DESIGN_SYSTEM.md](docs/DESIGN_SYSTEM.md) and enforced by `tests/test_design_rules.py`.
- Every sign-in path must call `stamp_session(user)` (cookie sessions are revoked through that stamp).

## Docs
- Index and reading order: [docs/README.md](docs/README.md). Full rulebook (IDs, PR checklist, Definition of Done, AGENT rules): [docs/RULES.md](docs/RULES.md).
- Decisions, gotchas, unknowns, hand-off template: [docs/MEMORY.md](docs/MEMORY.md). Work items: docs/TRACKER.md.
- Agents: stay inside the project folder, edit only files you own, no destructive action or push without owner approval, report failures faithfully.
