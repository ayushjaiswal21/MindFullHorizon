# End-to-end browser checks

Uses `playwright-core` with the Microsoft Edge that is already installed (no browser download).

    cd tools/e2e && npm install
    python ../../scripts/local_demo.py --port 5000      # in another terminal (demo accounts, password Demo@Pass2026)
    node specs/<file>.mjs

`lib.mjs` exports `launch(colorScheme, reducedMotion)`, `login(page, email, role)` and `B` (base URL, override with
the `BASE` environment variable). `page.errors` collects console and page errors. Specs print what they check; they are
manual smoke checks, not part of `pytest`.

## Chrome instead of Edge (CI and Linux)

The harness reads the browser path from the `EDGE` environment variable. GitHub Actions `ubuntu-latest` ships Google Chrome, so
the `e2e` job in `.github/workflows/ci.yml` sets `EDGE=/usr/bin/google-chrome`. Locally on Linux or macOS do the same with your Chrome path.
Specs that CI runs (each exits non-zero on failure): `assessment_progress`, `chat`, `breathing`, `clinical_smoke`.
Set `SHOTS=<dir>` for the screenshots that `chat` and `breathing` write. See `docs/CICD.md`.

## CSP sweep

`specs/csp_sweep.mjs` loads every GET page (list from `csp_routes.py`, which reads the Flask url map and the demo database) as each demo role with the Content-Security-Policy enforced, exercises chat, breathing, the yoga facade, modals, the theme switch, telehealth, voice logs and the consent banner, and exits 1 on any `securitypolicyviolation`. Needs a server on `BASE` whose rate limiter is off or generous, plus `DATABASE_URL` (same database as the server) and `PYTHON` for the helper script.
