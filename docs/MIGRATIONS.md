# Database migrations (Alembic via Flask-Migrate)

Schema source of truth: `models.py`. Baseline migration: `migrations/versions/0001_baseline.py`
(SQLite batch mode is on in `migrations/env.py`).

The database comes from `DATABASE_URL` (default `instance/mindful_horizon.db`). All commands run from the
project root with `FLASK_APP=app.py`.

| Task | Command |
|------|---------|
| New / empty database | `SKIP_CREATE_ALL=1 flask db upgrade` |
| After editing models | `SKIP_CREATE_ALL=1 flask db migrate -m "what changed"`, review the file, then `flask db upgrade` |
| Roll back one step | `flask db downgrade` |
| Current revision | `flask db current` |

PowerShell: `$env:SKIP_CREATE_ALL=1; flask db upgrade`.

## Why `SKIP_CREATE_ALL`

App start runs `db.create_all()` (`utils/database_utils.py`) when the `users` table is missing. That is the
dev/test bootstrap. If it ran first, `upgrade` would fail with "table already exists". It is skipped
automatically when `FLASK_ENV=production`, so production schema changes only come from migrations:
run `flask db upgrade` before starting the app.

## Existing dev database made by `create_all`

It has no `alembic_version` table. Either delete it and run `upgrade`, or mark it as current:
`flask db stamp 0001` (only if its schema equals the baseline).

`tests/test_db.py::test_migration_upgrade_matches_create_all` fails if `models.py` changes without a new migration.
