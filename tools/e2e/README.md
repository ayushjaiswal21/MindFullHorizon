# End-to-end browser checks

Uses `playwright-core` with the Microsoft Edge that is already installed (no browser download).

    cd tools/e2e && npm install
    python ../../scripts/local_demo.py --port 5000      # in another terminal (demo accounts, password Demo@Pass2026)
    node specs/<file>.mjs

`lib.mjs` exports `launch(colorScheme, reducedMotion)`, `login(page, email, role)` and `B` (base URL, override with
the `BASE` environment variable). `page.errors` collects console and page errors. Specs print what they check; they are
manual smoke checks, not part of `pytest`.
