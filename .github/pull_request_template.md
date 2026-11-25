## What and why

<!-- One or two sentences. Link the TRACKER item if there is one. -->

## Checklist

- [ ] `python scripts/ci_local.py` passes (or CI is green)
- [ ] New or changed behaviour has tests (`pytest tests -q`)
- [ ] UI change: I ran the matching spec in `tools/e2e/specs` and looked at the page (light and dark)
- [ ] Schema change: `models.py` plus an Alembic migration, and `flask db migrate` shows no drift
- [ ] Docs updated (`docs/`, and `.env.example` if I added an environment variable)
- [ ] No source file over 300 lines; no grandfathered file grew (`python scripts/check_file_sizes.py`)
- [ ] No secrets, tokens, real student data or patient text in code, logs, tests or screenshots
- [ ] No `str(e)` returned to clients; user-data routes have `@login_required`, a role decorator and filter by the session user

## Rollback

<!-- How to undo this if it goes wrong after deploy. Example: "Render dashboard rollback is safe" or
     "includes migration 00NN: roll forward only, downgrade drops a column". -->
