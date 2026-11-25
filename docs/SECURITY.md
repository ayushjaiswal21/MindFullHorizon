# Security policy

MindFull Horizon handles sensitive mental-health data. Please report vulnerabilities privately.

- Use GitHub's "Report a vulnerability" (Security tab -> Advisories) on https://github.com/ayushjaiswal21/MindFullHorizon . Do not open a public issue with exploit details.
- Include the affected URL or file, steps to reproduce and impact. Never include real user data.
- Known open issues are tracked in [docs/STATUS.md](docs/STATUS.md); please check it before reporting.

## Sessions (cookie sessions and the stamp)

Sessions are Flask's signed cookies (`mindfullhorizon_session`: HttpOnly, SameSite Lax, Secure in production, lifetime `SESSION_LIFETIME_HOURS`, default 24). Nothing is stored on the server, so restarts, redeploys and Render sleep do not log anyone out, and there is no session folder to prune. Trade-offs: the cookie content (id, name, email, role, institution) is signed but readable by its owner, it must stay well under 4 KB (a test checks this), and `SECRET_KEY` rotation logs everyone out. A cookie cannot be revoked by the server, so login stores `session['stamp']` (a 16 character HMAC of the user id, password hash and role, keyed with `SECRET_KEY`, `utils/session_stamp.py`). One `before_request` check compares it with the user's current values (one primary-key query, logged-in requests only, not static, `/health` or `/ready`). A password change, role change or account deletion makes older cookies stale, and the request continues as anonymous. A stolen cookie still works until one of those happens or it expires. The profile page refreshes the stamp after the user's own password change. Sessions written by test helpers without a stamp are accepted only when `TESTING` is on.

Operational rules for maintainers: never commit `.env` or database files, rotate any API key that was ever shared, and keep helpline numbers in one config file with a "last verified" date.

## Content-Security-Policy (enforcing)

Built per request in `utils/security_headers.py` (`init_security_headers(app)`, called once from `app.py`). Every response (pages, JSON, error pages) carries `Content-Security-Policy`, `X-Content-Type-Options`, `Referrer-Policy`, `X-Frame-Options`, `Cross-Origin-Opener-Policy: same-origin` and `Permissions-Policy` (camera and microphone for this origin only: voice logs and telehealth). `Strict-Transport-Security` and `upgrade-insecure-requests` are sent only when `FLASK_ENV=production`.

Policy: `default-src 'self'`; `script-src 'self' 'nonce-<n>'`; `style-src 'self' 'nonce-<n>'`; `style-src-attr 'none'`; `img-src 'self' data: https://i.ytimg.com`; `font-src 'self'`; `connect-src 'self'` plus `wss://<host>` (and `ws://<host>` outside production) for Socket.IO; `media-src 'self' blob:` plus the `AUDIO_BASE_URL` origin when set; `frame-src https://www.youtube-nocookie.com`; `object-src 'none'`; `base-uri 'self'`; `form-action 'self'`; `frame-ancestors 'none'`; `report-uri /csp-report`. No `unsafe-inline`, `unsafe-eval` or CDN host is allowed in `script-src` or `style-src`.

Rules for templates and scripts (a test enforces them across the url map): no `on*=` attributes, no `javascript:` URLs, no `style=` attributes (use a class), every inline `<script>` carries `nonce="{{ g.csp_nonce }}"` (JSON blocks with `type="application/json"` need none). Setting styles from JavaScript through `element.style.x = ...` is allowed; `setAttribute('style', ...)` and HTML strings containing `style=` are not.

Google sign-in is a link to `/login/google` (a navigation, not a form post), so it needs no extra directive. Socket.IO is same host.

Vendored libraries (no CDN at runtime), in `static/vendor/` with their licences: Chart.js 4.4.1 (`chart.umd.min.js`, MIT) and Socket.IO client 4.7.4 (`socket.io.min.js`, MIT). Both are the exact files the CDN served. Font Awesome was removed (no template used it). To upgrade, replace the file, keep the licence next to it and change the version here.

`/csp-report` (`routes/csp.py`) receives violation reports, limited to 30 per minute per client, and logs only the directive and the blocked origin (no query string, no page content).

Emergency fallback: set `CSP_REPORT_ONLY=1` (Render environment tab, then redeploy or restart). The same policy is then sent as `Content-Security-Policy-Report-Only`, which blocks nothing. Remove the variable once the cause is fixed. `CSP_ENFORCE=0` is the old spelling and does the same.

Checking a change: `pytest tests/test_csp.py -q` (headers, nonce, strict scan of every rendered page) and the browser sweep `tools/e2e/specs/csp_sweep.mjs` (see tools/e2e/README.md), which loads every page as every demo role under the enforced policy and fails on any `securitypolicyviolation`.
