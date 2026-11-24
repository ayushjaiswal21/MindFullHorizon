# MindFull Horizon: working notes

Flask mental-health app for Indian college students. Read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/STATUS.md](docs/STATUS.md) first.

## Commands
- Run: `python app.py` (http://127.0.0.1:5000; creates `instance/mindful_horizon.db` on first start)
- Test: `pytest tests -q` (temp DB, no Gemini calls; fixtures in `tests/conftest.py`)

## Rules
- New routes go in `routes/` blueprints, never in `app.py`. `models.py` is the schema source of truth; schema changes need an Alembic migration.
- Every user-data route needs `@login_required` plus a role decorator and must filter by the session user (no trusting a client-sent user_id).
- Never return `str(e)` to clients; never log patient text.
- Static JS must not contain Jinja tags (`{{ }}`); pass server values via `data-*` attributes or a JSON script block.
- Helpline numbers come from one config (Tele-MANAS 14416, KIRAN 1800-599-0019, 112); see [docs/SAFETY_RESEARCH.md](docs/SAFETY_RESEARCH.md).
- Never attach points or streaks to assessment or mood scores.
- No fake claims in UI copy (stats, testimonials, "encrypted" unless it is true).

## Docs
- Index and reading order: [docs/README.md](docs/README.md). Full rulebook (IDs, PR checklist, Definition of Done, AGENT rules): [docs/RULES.md](docs/RULES.md).
- Decisions, gotchas, unknowns, hand-off template: [docs/MEMORY.md](docs/MEMORY.md). Work items: docs/TRACKER.md.
- Agents: stay inside the project folder, edit only files you own, no destructive action or push without owner approval, report failures faithfully.
