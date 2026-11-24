# Security policy

MindFull Horizon handles sensitive mental-health data. Please report vulnerabilities privately.

- Use GitHub's "Report a vulnerability" (Security tab -> Advisories) on https://github.com/ayushjaiswal21/MindFullHorizon . Do not open a public issue with exploit details.
- Include the affected URL or file, steps to reproduce and impact. Never include real user data.
- Known open issues are tracked in [docs/STATUS.md](docs/STATUS.md); please check it before reporting.

## Sessions (cookie sessions and the stamp)

Sessions are Flask's signed cookies (`mindfullhorizon_session`: HttpOnly, SameSite Lax, Secure in production, lifetime `SESSION_LIFETIME_HOURS`, default 24). Nothing is stored on the server, so restarts, redeploys and Render sleep do not log anyone out, and there is no session folder to prune. Trade-offs: the cookie content (id, name, email, role, institution) is signed but readable by its owner, it must stay well under 4 KB (a test checks this), and `SECRET_KEY` rotation logs everyone out. A cookie cannot be revoked by the server, so login stores `session['stamp']` (a 16 character HMAC of the user id, password hash and role, keyed with `SECRET_KEY`, `utils/session_stamp.py`). One `before_request` check compares it with the user's current values (one primary-key query, logged-in requests only, not static, `/health` or `/ready`). A password change, role change or account deletion makes older cookies stale, and the request continues as anonymous. A stolen cookie still works until one of those happens or it expires. The profile page refreshes the stamp after the user's own password change. Sessions written by test helpers without a stamp are accepted only when `TESTING` is on.

Operational rules for maintainers: never commit `.env` or database files, rotate any API key that was ever shared, and keep helpline numbers in one config file with a "last verified" date.
