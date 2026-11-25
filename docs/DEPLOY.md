# Deploying MindFull Horizon on Render and Neon

Written 2026-11-24 for a first-time deployer. Owner: deploy-prep agent. Files: `render.yaml`, `Dockerfile`, `.dockerignore`, `scripts/predeploy_check.py`, `scripts/backup_db.py`, `tests/test_deploy_config.py`. Docker was NOT run while writing this (it was not available), and nothing here was tested against a live Render or Neon account. Every web fact has a source URL and the date it was read; anything I could not confirm is marked **UNVERIFIED**.

> **Read this first: the free tier is for demos and dry runs only.**
> A free Render web service goes to sleep after 15 minutes without traffic. While it sleeps, the in-process job worker is stopped, so crisis escalation timers (15, 30 and 45 minutes), contact-form emails and every other background job do not run. A student who writes something alarming at 2 a.m. would not trigger the escalation chain until someone opens the site again. Render itself says free services are not for production. A pilot with real students needs an always-on paid instance (section 9) or a separate always-on worker, and you must complete section 11 first.

Contents: 1 Why these two services, 2 What you need, 3 Environment variables, 4 Neon setup, 5 Render setup, 6 First-run checklist, 7 Verification, 8 Domain and SEO, 9 Keys, backups, monitoring, 10 Rollback, 11 Costs, 12 Troubleshooting, 13 Code changes required before the first deploy.

## 1. Why Render plus Neon, and what free cannot do

- **Render** runs the Docker image from your GitHub repo and gives you HTTPS and a URL. **Neon** is a managed PostgreSQL database. The app needs a real database that survives restarts; Render's free filesystem does not.
- Both have a free plan, so a demo costs nothing.
- Facts about the free plans:

| Fact | Value | Source (read 2026-11-24) |
|---|---|---|
| Render free web service spins down | after 15 minutes with no inbound traffic (HTTP or WebSocket messages) | https://render.com/docs/free |
| Wake-up time | about one minute, the browser sees a loading page | same |
| Free instance hours | 750 per workspace per month | same |
| Filesystem | ephemeral: files are lost on every redeploy, restart and spin-down; no persistent disk on free | same |
| Shell / SSH on free | not available | same |
| Background workers on free | not available (free types: web service, Postgres, Key Value, static site) | same |
| Render says about production | "Do not use them for production applications." | same |
| Free instance size | 0.1 CPU, 512 MB RAM | https://render.com/docs/compute-plans |
| Neon free storage | 1 GB per project | https://neon.com/docs/introduction/plans |
| Neon free compute | 100 CU-hours per project per month | same |
| Neon scale to zero | compute suspends after 5 minutes idle, cannot be turned off on free | same |
| Neon free restore window | up to 6 hours of history (1 GB of changes) | same |
| Neon wake-up time | "typically a few hundred milliseconds" plus network distance | https://neon.com/docs/connect/connection-latency |

- **Keeping a demo awake with a pinger.** An uptime service such as UptimeRobot can request `/health` every 5 to 10 minutes, so the free instance never reaches 15 idle minutes. Limits: it is a workaround, not a fix. It uses your 750 free hours (one always-awake service uses about 730 hours a month, so it just fits, but only for one service), Render can restart a free service at any time (https://render.com/docs/free, via search result read 2026-11-24), and Render may suspend a free service with unusually high outbound traffic. A Render community reply says deliberately keeping a free service awake is abuse of the free tier. That is a forum post, not Render's terms, and I could not find or confirm the terms wording (**UNVERIFIED**). Read https://render.com/terms yourself before relying on it. Do not use a pinger for a pilot.
- **The job worker no longer keeps Neon awake.** It used to poll every 2 seconds. Now an idle worker queries the database only after a job is enqueued, when a scheduled job is due, or every `JOB_IDLE_MAX_SECONDS` (900 s). The web service's own requests still wake Neon (section 13, item 8).

## 2. What you need

- A GitHub account with this repo pushed (Render deploys from GitHub). Never commit `.env`.
- A Render account (https://render.com) and a Neon account (https://neon.com).
- Optional: a Gemini API key (https://aistudio.google.com), an SMTP account for email (any provider; Gmail needs an app password), an object-storage bucket for the audio files, a domain name.
- On your own computer: Python 3.11 and this repo installed (`pip install -r requirements.txt`) to run migrations and admin commands (Render free has no shell). Optional: PostgreSQL client tools for `pg_dump` and `pg_restore`.

## 3. Environment variables

`render.yaml` lists only variables the code reads (checked with a search of `os.getenv` and `os.environ` over all `.py` files).

| Variable | Where it comes from | Notes |
|---|---|---|
| `FLASK_ENV=production` | fixed in render.yaml | turns on secure cookies, HSTS, the SECRET_KEY check, ProxyFix, stdout-only logging and the `JOBS_INPROCESS` default |
| `CSP_REPORT_ONLY` | not set (optional) | emergency fallback: `1` sends the Content-Security-Policy as Report-Only so a page that breaks under the policy works again while you fix it. Default is enforcing. See docs/SECURITY.md |
| `SECRET_KEY` | Render generates it | the app refuses to start without it. If it changes, all signed data (CSRF tokens, session cookies once cookie sessions are used) is invalidated |
| `DATABASE_URL` | you paste the Neon DIRECT string | see section 4 |
| `SITE_URL` | you | `https://...`, no trailing slash |
| `GEMINI_API_KEY` | you (optional) | without it the AI uses canned text. With it, Gemini is used only for the general "Tip of the day" |
| `AI_SEND_PERSONAL_TEXT` | fixed `0` in render.yaml | `0` (default): nothing a student writes or that is tied to a user is sent to Gemini; chat answers come from the crisis check and saved answers. `1` sends it, which on Google's free tier may let Google use the content, so only with the college's written approval, recorded in `AI_PERSONAL_TEXT_APPROVED_BY`. See docs/LLM_SECURITY.md |
| `AI_PERSONAL_TEXT_APPROVED_BY` | you (only with the flag on) | free-text record of the written approval; `scripts/predeploy_check.py` warns when the flag is on without it |
| `PROVIDER_INVITE_CODE` | Render generates it | counsellors need it to sign up. Copy it from the dashboard. Unset means provider signup is off |
| `CRISIS_ESCALATION_EMAIL` | you | **required for a pilot**: emailed at escalation levels 2 and 3. Without it, an institution with no counsellor accounts notifies nobody |
| `CONTACT_RECIPIENT`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | you (optional) | all-or-none; without them the contact page says the message was saved |
| `GRIEVANCE_EMAIL`, `DATA_FIDUCIARY_NAME` | you | shown on the privacy page |
| `AUDIO_BASE_URL` | you (optional) | the mp3 files are not in the image |
| `ENABLE_PRESCRIPTIONS=1` | fixed | owner decision: on, verified doctors only; legal and pharmacist review still pending |
| `DOCTOR_INVITE_CODE` | Render generates it | doctors need it to sign up; must differ from `PROVIDER_INVITE_CODE` |
| `TRUST_PROXY=1`, `LOG_TO_STDOUT=1` | fixed | one proxy hop (ProxyFix) and stdout-only logs; both are already on when `FLASK_ENV=production` |
| `JOB_IDLE_MAX_SECONDS=900` | fixed | longest sleep of an idle job worker; lets Neon suspend |
| `JOBS_INPROCESS=1` | fixed | job worker thread inside the web process |
| `CONSENT_VERSION=2026-11` | fixed | bump after a policy change |

Not set on purpose:
- `WEB_CONCURRENCY`: no code reads it. The Dockerfile passes `--workers 1` on the command line, which wins. More than one worker breaks Socket.IO, the rate limiter and the cache (all per process).
- `PYTHON_VERSION`: only used by Render's native Python runtime. With Docker the version is `FROM python:3.11-slim`.
- `PORT`: Render sets it (default 10000, https://render.com/docs/web-services, read 2026-11-24); the Dockerfile binds `${PORT:-5000}` on `0.0.0.0`, which Render requires.

Optional tuning variables the code also reads (defaults are fine): `GEMINI_MODEL_NAME`, `GEMINI_TIMEOUT`, `AI_MAX_RETRIES`, `AI_BREAKER_FAILURES`, `AI_BREAKER_RESET_SECONDS`, `AI_DAILY_LIMIT`, `AI_BURST_LIMIT`, `AI_MAX_REPLY_CHARS`, `AI_CANARY`, `JOB_LOCK_TIMEOUT`, `CRISIS_ESCALATE_MINUTES`, `CORS_ORIGINS`, `CSP_ENFORCE`, `MIN_AGGREGATE_GROUP`, `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT`, `DB_POOL_RECYCLE`, `DB_CONNECT_TIMEOUT`, `DB_STATEMENT_TIMEOUT_MS`, `SESSION_LIFETIME_HOURS`, `CACHE_TYPE`, `CACHE_DEFAULT_TIMEOUT`, `CACHE_THRESHOLD`, `REDIS_URL`, `RATELIMIT_STORAGE_URI`, `SQLITE_BUSY_TIMEOUT_MS`, `ASSET_VERSION`.

## 4. Neon setup (about 10 minutes)

1. Sign up at https://neon.com and create a project. Name it `mindfull-horizon`. Choose Postgres 16 or 17.
2. **Region.** Neon's regions (https://neon.com/docs/introduction/regions, read 2026-11-24): US East N. Virginia, US East Ohio, US West Oregon, Frankfurt, London, Singapore (`aws-ap-southeast-1`), Sydney, Sao Paulo. There is no India region. Choose **Singapore** and put the Render service in Singapore too. Render has no India region either (https://render.com/docs/regions, read 2026-11-24; regions are Oregon, Ohio, Virginia, Frankfurt, Singapore). Keep both in the same region: every page makes several database calls and a cross-ocean hop makes each one slow.
3. In the Neon console click **Connect**. You will see a toggle called **Connection pooling**. Copy two strings:
   - **DIRECT** (toggle off): host looks like `ep-name-123456.ap-southeast-1.aws.neon.tech`.
   - **POOLED** (toggle on): the same host with `-pooler` added: `ep-name-123456-pooler.ap-southeast-1.aws.neon.tech`.
   (https://neon.com/docs/connect/connection-pooling, read 2026-11-24.)
4. Both end with `?sslmode=require` and usually `&channel_binding=require`. Keep `sslmode=require`. `channel_binding=require` is a safety feature that only works if the client library supports it; the `psycopg2-binary` wheel's bundled libpq support for it is **UNVERIFIED**. If the app or `flask db upgrade` fails with a channel binding error, delete `&channel_binding=require` from the string.
5. **Which string goes where.**
   - **DIRECT everywhere**, for now: the Render `DATABASE_URL`, migrations, `create-admin`, `pg_dump`. Neon recommends the direct connection for migrations and `pg_dump` (https://neon.com/docs/connect/connection-pooling).
   - **Prefer DIRECT for the web service.** Since item 5 the code skips the startup option for `-pooler` hosts, so a pooled string should now connect, but it was never run (**UNVERIFIED**) and has no statement timeout. Background: `utils/database_utils.py` used to send `-c statement_timeout=...` as a startup option. Neon's pooler rejects unsupported startup options with "unsupported startup parameter in options" and only accepts `client_encoding`, `datestyle`, `timezone`, `standard_conforming_strings` and `application_name` (https://neon.com/docs/connect/connection-errors, read 2026-11-24). I have not run this combination (**UNVERIFIED** in practice), but it is what the docs say. The app's own pool is only 5 plus 5 connections, so the direct host is enough for one instance. Neon's free `max_connections` is **UNVERIFIED** (the plans page does not state it).
   - If you try the pooled host for the web service, keep the direct string for migrations.
6. If the password contains characters such as `@` or `/`, they must be percent-encoded in the URL. Neon's generated strings already are.
7. Run `python scripts/predeploy_check.py` with your values (section 7) before the first deploy.

## 5. Render setup from the Blueprint

1. Push the repo to GitHub (branch `main`).
2. In Render: **New** then **Blueprint**, connect GitHub, choose the repo. Render reads `render.yaml` (https://render.com/docs/blueprint-spec, read 2026-11-24).
3. Render shows the variables marked `sync: false` and asks for them **once, at creation** (later changes to those are made in the dashboard Environment tab, because Render ignores `sync: false` variables when a Blueprint is updated; same source). Fill in:
   - `DATABASE_URL`: the Neon DIRECT string.
   - `SITE_URL`: you do not know the final URL yet. Use `https://mindfull-horizon.onrender.com` as a guess, then correct it after the first deploy in the dashboard (Environment tab) if Render gave a different name.
   - `GEMINI_API_KEY`, `CRISIS_ESCALATION_EMAIL`, `CONTACT_RECIPIENT`, `GRIEVANCE_EMAIL`, `DATA_FIDUCIARY_NAME`, and the SMTP values: fill what you have. Whether Render accepts an empty value for a `sync: false` prompt is **UNVERIFIED**; if it insists, enter a single space or a placeholder you will fix, and then correct it in the Environment tab (a wrong `SMTP_HOST` only makes email jobs retry and die; it does not stop the app).
4. Click **Apply**. Render builds the image (several minutes: it installs the dependencies, then builds the CSS/JS bundles). Open the service, then **Logs**.
5. What a good start looks like: `migration ...` lines from Alembic (`Running upgrade ... -> 0003`), then gunicorn lines `Listening at: http://0.0.0.0:10000` and `Using worker: eventlet`. Render marks the deploy live when `/health` answers 2xx or 3xx within 5 seconds (https://render.com/docs/health-checks, read 2026-11-24). If it does not pass within 15 minutes, Render cancels the deploy and keeps the old version.
6. A failed migration prints `MIGRATION FAILED: ...` and the container exits; the deploy fails. Fix the cause (usually `DATABASE_URL`) and redeploy: **Manual Deploy** then **Deploy latest commit**.
7. Auto deploy: `autoDeployTrigger: commit` redeploys on every push to `main`. The Dockerfile runs `flask db upgrade` on every start, so a pushed migration is applied automatically.
8. Free instance note: 0.1 CPU is slow. Importing the app took about 5 seconds on a laptop, so expect the first start and each wake-up to take noticeably longer.

## 6. First-run checklist

1. **Migrations.** They ran automatically at container start. Confirm with `https://YOUR-URL/ready`: `{"status":"ready"...}` means the database answers and `alembic_version` matches the code. 503 means a mismatch (section 12).
2. **First admin without shell access.** Render free has no Shell (https://render.com/docs/free). You run commands from your own computer, pointed at the Neon DIRECT URL.

   > Available after the admin role lands. `flask create-admin` does not exist in the code today (searched `*.py`, 2026-11-24). Until it exists, the only account types are patient and provider (provider via `PROVIDER_INVITE_CODE`). Update this section when the command is built, and check its real arguments with `flask create-admin --help`.

   Safe setup for any command that touches the production database from your PC. `FLASK_ENV=production` and `SKIP_CREATE_ALL=1` stop the app from running `create_all()` against your real database when it starts; the `SECRET_KEY` can be any 32+ character dummy for CLI commands.

   PowerShell (Windows):
   ```powershell
   cd D:\MINDFULLHORIZON2.0\MindFullHorizon
   $env:FLASK_APP = "app.py"
   $env:FLASK_ENV = "production"
   $env:SKIP_CREATE_ALL = "1"
   $env:SECRET_KEY = "cli-only-dummy-key-0123456789abcdef0123"
   $env:DATABASE_URL = "postgresql://USER:PASSWORD@ep-name-123456.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"
   flask db current            # shows the revision; should say 0003 (or newer) (head)
   flask create-admin ...      # after the admin role lands; see --help for the arguments
   ```
   bash (macOS, Linux, Git Bash):
   ```bash
   cd ~/MindFullHorizon
   export FLASK_APP=app.py FLASK_ENV=production SKIP_CREATE_ALL=1
   export SECRET_KEY=cli-only-dummy-key-0123456789abcdef0123
   export DATABASE_URL='postgresql://USER:PASSWORD@ep-name-123456.ap-southeast-1.aws.neon.tech/neondb?sslmode=require'
   flask db current
   flask create-admin ...      # after the admin role lands
   ```
   Close the terminal afterwards (the password sits in the environment). Do not paste the URL into chat tools or commit it. The same pattern runs `flask db upgrade`, `flask jobs-stats` and `flask jobs-run-once`.
3. **Set the counsellor invite code.** Copy `PROVIDER_INVITE_CODE` from Render (Environment tab) and give it only to real counsellors.
4. **Email.** Submit the contact form and check the inbox. If `SMTP_*` is blank the page says honestly that the message was saved; read it in the `contact_messages` table.
5. **Crisis email.** Set `CRISIS_ESCALATION_EMAIL` to a mailbox that a human reads at night, not a shared inbox nobody opens.

## 7. Verification

Run these after every first deploy and after changing environment variables.

1. **Config check on your computer** (no network unless `--check-db`). PowerShell: set the same variables as in Render, then:
   ```powershell
   python scripts/predeploy_check.py --pilot --check-db
   ```
   bash: `python scripts/predeploy_check.py --pilot --check-db`. It prints PASS, WARN or FAIL per item and exits 1 on any FAIL. It never prints secret values. `--pilot` makes a missing `CRISIS_ESCALATION_EMAIL` a failure. `--check-db` connects with a 10 second timeout, runs `SELECT 1` and reads `alembic_version`.
2. `https://YOUR-URL/health` returns `{"status":"ok"}` (always, even when the database is down).
3. `https://YOUR-URL/ready` returns `ready`, `migrations: ok`, `jobs.dead: 0`. A `jobs_warning: stale_jobs` means the worker is not running.
4. Sign up as a patient (age and consent boxes), log out, log in. If login loops, see cookies in section 12.
5. Send a message through the contact form. Check the email arrives, or the row exists.
6. **Crisis test, staging only, never on a live pilot database.** Create a separate Render service and Neon branch, sign in as a test patient and write a clearly marked test phrase in the journal. Confirm that the helplines show, a provider notification appears, and the escalation email arrives at the 30 minute mark (with an awake instance). Do not rehearse with real student accounts.
7. Check that response headers carry `Strict-Transport-Security` and that cookies are `Secure` (browser developer tools, Application tab).
8. Open the privacy page and confirm the grievance email and fiduciary name show real values, not placeholders.

Docker check you can do before pushing (I could not run Docker): from the repo root,
```bash
docker build -t mindfull-test .
docker run --rm -p 5000:5000 \
  -e FLASK_ENV=production -e SECRET_KEY=$(python -c "import secrets;print(secrets.token_urlsafe(48))") \
  -e DATABASE_URL='postgresql://...direct neon string...' \
  mindfull-test
```
(PowerShell: use `` ` `` at line ends, and put a 32+ character `SECRET_KEY` literal.) Then open http://localhost:5000/health. Expected: the log shows the migration, then `Using worker: eventlet`. Also try `docker run --rm mindfull-test ls static/gen` to confirm `packed.js` and `packed.css` were built into the image, and `docker run --rm mindfull-test id` to confirm it runs as user `app`.

## 8. Domain, SITE_URL, favicon and OG image

1. Buy a domain or use a free subdomain you control. In Render open the service, **Settings**, **Custom Domains**, add it, and create the DNS record Render shows at your registrar. Render issues the HTTPS certificate itself.
2. Then set `SITE_URL=https://your-domain` (no trailing slash) in the Environment tab and redeploy. `SITE_URL` drives canonical links, Open Graph tags, the sitemap and structured data (`utils/seo.py:53`, `utils/site_context.py:37`). Without it these come from the request URL, which is wrong behind a proxy until ProxyFix is added (section 13).
3. Also set `SITE_URL` in the Google OAuth console redirect URIs if you use Google sign-in.
4. Favicon: `static/favicon.ico`, `static/img/favicon.svg`, `static/site.webmanifest` exist. The Open Graph image: check `templates/` for the `og:image` path and make sure the file exists in `static/` and is at least 1200 by 630 pixels (I did not verify an image file is present; **UNVERIFIED**). Share the URL in a chat app to test the preview.

## 9. Key rotation, backups, monitoring

**Rotating secrets**
- `SECRET_KEY`: change it in the Environment tab; Render redeploys. Everyone is logged out. Do it after any suspected leak, and when a team member leaves.
- Neon password: Neon console, **Roles**, reset password, copy the new string, update `DATABASE_URL` in Render, redeploy. Also update any local scripts.
- `GEMINI_API_KEY`, `SMTP_PASSWORD`: revoke at the provider, create a new one, update Render.
- `PROVIDER_INVITE_CODE`: change it after the counsellors have signed up.

**Backups.** Neon free gives up to 6 hours of point-in-time history (https://neon.com/docs/introduction/plans), which protects against a bad migration or delete today, not against anything older. Paid Launch keeps up to 7 days at $0.20 per GB-month. Make your own copies too:
```bash
python scripts/backup_db.py ~/mindfull-backups        # bash
```
```powershell
python scripts/backup_db.py D:\backups\mindfull       # PowerShell, with DATABASE_URL set to the DIRECT string
```
`scripts/backup_db.py` wraps `pg_dump --format=custom`, writes `mindfull-<UTC time>.dump`, refuses to write inside the repo, refuses a `-pooler` host and never prints the URL. **It has not been tested against a live database.** It needs `pg_dump` on PATH, with a major version at least equal to the server's. The dump contains student data: store it encrypted and private, never in Git.

**Restore drill (do it once before the pilot, into a scratch Neon project, not into production).**
1. Create a new empty Neon project (the scratch one) and copy its DIRECT string.
2. `pg_restore --no-owner --no-acl --dbname "SCRATCH_DIRECT_URL" mindfull-20261124T101500Z.dump`
3. Point a local copy of the app at the scratch database (section 6 variables) and run `flask db current` and `python scripts/predeploy_check.py --check-db`; log in as a known user.
4. Restoring over production: first take a fresh dump, then restore into an empty database (create a new Neon branch or project) and switch `DATABASE_URL` to it, rather than overwriting the live one.
5. Write down how long it took.

**Monitoring**
- Render **Logs** tab (live stream; the app logs one access line per request with a request id, no patient text, see `docs/OPERATIONS.md`).
- Uptime: a monitor (for example UptimeRobot, https://uptimerobot.com) on `https://YOUR-URL/health` every 5 minutes. A second monitor on `/ready` that alerts on a 503, `jobs.dead > 0` or `stale_jobs`. Do not make `/ready` Render's health check path: a database blip would restart the only instance (`docs/OPERATIONS.md`).
- Alert on: `/health` down, `/ready` 503, `crisis job DEAD`, `crisis alert UNACKNOWLEDGED` and `job dead` log lines, a failed deploy email from Render, Neon storage above 80 percent of 1 GB, Neon compute hours above 80 of 100.
- Render stops routing traffic after 15 seconds of failed health checks and restarts the instance after 60 seconds (https://render.com/docs/health-checks).

## 10. Rollback

- **Code:** Render dashboard, service, **Deploys**, pick an earlier successful deploy, **Rollback** then **Rollback to this deploy**. Render redeploys that build. A dashboard rollback turns auto deploy off for the service; turn it back on in **Settings** (https://render.com/docs/rollbacks, read 2026-11-24). How many builds are kept, and whether free plans have a lower limit, is **UNVERIFIED**.
- **The database is NOT rolled back.** If the bad deploy included a migration, the old code now runs against a newer schema, and `/ready` returns 503 because `alembic_version` no longer equals the head the old code knows. Two ways out: (a) roll forward with a fixed commit (preferred); (b) from your computer with the direct URL, run `flask db downgrade` one step, and then roll back the code. Downgrades can drop columns and tables and delete data. Take a `scripts/backup_db.py` dump first, and read the migration file before downgrading. Never downgrade past data you cannot lose.
- For risky releases, first create a Neon branch (copy of the data) and rehearse the migration there.

## 11. Cost ladder (what to pay for first)

| Step | What | Why | Price |
|---|---|---|---|
| 0 | Free Render + free Neon | demos, dry runs, a classroom walkthrough | 0 |
| 1 | Render always-on instance (Starter: 0.5 CPU, 512 MB) | no sleep: crisis timers, emails and WebSocket chat keep running. This is the first thing a pilot needs | Starter is reported at about 7 USD per month in a search result; I could not read the official price page (**UNVERIFIED**, check https://render.com/pricing) |
| 2 | Neon paid (Launch) | free compute is only 100 CU-hours a month. The idle job worker no longer polls (section 13, item 8), but web traffic and the 900 s idle check still wake the compute, so an always-on pilot can exceed the free hours (check your own usage in the Neon console). Launch also gives a 7 day restore window | no flat fee, usage based: compute 0.106 USD per CU-hour, restore storage 0.20 USD per GB-month (https://neon.com/docs/introduction/plans, read 2026-11-24) |
| 3 | Separate always-on worker (`flask jobs-worker`, `JOBS_INPROCESS=0` on the web service) | only when background jobs hurt web latency. Render free has no workers, so this is a paid service (`docs/OPERATIONS.md`). A separate process is not reached by the in-process wake event, so it checks the queue every 60 s | paid worker price **UNVERIFIED** |
| 4 | Object storage for the audio tracks | the Docker image has no mp3 files (voice recordings and profile pictures are not stored at all) | provider dependent |

Also keep in mind: Render free outbound bandwidth counts against a monthly allowance; the amount is not stated on the page I read (**UNVERIFIED**).

## 12. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| First page after a while takes about a minute | free Render instance was asleep (and Neon too) | normal on free; pay for always-on, or accept it for demos |
| 502 or timeout on the first request | cold start plus 0.1 CPU; the app import is slow | wait and reload; paid instance |
| Deploy fails, log ends with `MIGRATION FAILED` | wrong or unreachable `DATABASE_URL`, pooled host with a failing migration, Neon waking | check the string (direct host, `sslmode=require`); the container already retried 3 times 5 seconds apart; redeploy |
| `OperationalError: ... SSL connection has been closed unexpectedly` or `server closed the connection` after idle | Neon suspended the compute and a pooled connection died | the engine uses `pool_pre_ping=True`, so a retry works; if it persists lower `DB_POOL_RECYCLE` (for example 300) in Render |
| `unsupported startup parameter in options: statement_timeout` | an older build sent the option to a `-pooler` host | current code skips it for `-pooler` hosts; the direct host is still recommended (section 4) |
| `channel binding` error | libpq does not support it | remove `&channel_binding=require` from the URL |
| Container exits at start: `SECRET_KEY must be set in production` | variable missing | set it in the Environment tab |
| `/ready` returns 503 | migrations mismatch, database down, or another error (details are in the log, never in the response) | read the log line `readiness check failed err=...`; run `flask db current` from your computer; run `flask db upgrade` |
| `/ready` 200 with `stale_jobs` | the job worker is not running | check `JOBS_INPROCESS=1`; free instance was asleep |
| Login works, then you are logged out on the next click | the cookie is `Secure` and the page is on `http://`, `SECRET_KEY` changed, or the password or role changed (the session stamp) | use HTTPS only; keep `SECRET_KEY` stable (section 13, item 1) |
| "Session expired or invalid request" on every form | CSRF token tied to a lost session, or `SECRET_KEY` changed | log in again; do not rotate `SECRET_KEY` during use |
| Cookies not set, or redirects go to `http://` | ProxyFix is off (`FLASK_ENV` is not `production` and `TRUST_PROXY` is unset) | section 13, item 3 |
| Everyone is rate limited at once | all users share the proxy's IP address | ProxyFix is on in production; check `TRUST_PROXY` elsewhere (section 13, item 3) |
| Socket.IO chat does not connect | page loaded over `http://`, a blocked `ws://`, or `CORS_ORIGINS` set to the wrong origin; Render requires `wss://` (https://render.com/docs/websocket, read 2026-11-24) | use the HTTPS URL; leave `CORS_ORIGINS` unset for same origin; clients should reconnect after sleeps and deploys |
| Profile pictures or voice recordings are missing | by design: pictures are not supported and audio is never stored | section 13, item 2 |
| Binaural audio 404 | mp3 files are not in the image | set `AUDIO_BASE_URL` |
| Privacy page shows placeholders | `GRIEVANCE_EMAIL`, `DATA_FIDUCIARY_NAME` unset | set them |
| gunicorn fails to start with an eventlet import error | gunicorn 21.2 with a very new eventlet (unpinned `eventlet>=0.33,<1.0` installs the newest) | **UNVERIFIED**: the gunicorn 21.2 source handles the removed `ALREADY_HANDLED` name, but I could not run gunicorn here (Windows). Run the `docker run` check in section 7; if it fails, pin `eventlet` in `requirements.txt` |

## 13. Code changes required before the first deploy

I may not edit these files. Line numbers are from 2026-11-24 and will move; search for the quoted text. Status is "TODO" unless the code already handles it.

| # | Item | Where | Status and what to do |
|---|---|---|---|
| 1 | **Sessions are files on the container disk.** | `app.py`, `extensions.py` | **DONE 2026-11-24.** Flask signed cookie sessions, no server-side storage, `SESSION_FILE_*` and `flask prune-sessions` removed, Flask-Session dropped from `requirements.txt`. Login stores a keyed stamp (`utils/session_stamp.py`) so a password change, role change or account deletion invalidates old cookies. Trade-offs in `docs/SECURITY.md` (Sessions). Tests: `tests/test_deploy_code.py` |
| 2 | **Uploads on local disk, publicly fetchable.** | `app.py`, `routes/auth.py`, `templates/patient_voice_logs.html`, `templates/profile.html` | **DONE 2026-11-24.** Voice audio is analysed in a temp file deleted in `finally` (`utils/voice_features.py`) and only the measurements and AI note are stored (`VoiceLog.filename` is the placeholder `not-stored`). Profile picture upload removed (initial avatar). `UPLOAD_FOLDER`, the playback link and the file cleanup on account delete are gone; `static/uploads/.gitkeep` stays. Privacy page and `docs/PRIVACY_AND_CONSENT.md` updated |
| 3 | **ProxyFix.** | `utils/proxy.py`, `app.py` | **DONE 2026-11-24.** `ProxyFix(x_for=1, x_proto=1, x_host=1, x_prefix=0)` when `FLASK_ENV=production` or `TRUST_PROXY` is truthy (one proxy hop; never enable it without a trusted proxy, clients could forge `X-Forwarded-For`). The rate-limit key (`request.remote_addr`), `url_for(_external=True)`, `request.is_secure` and the `/api/event` same-origin check use the forwarded values. Render's exact `X-Forwarded-*` headers are still **UNVERIFIED** (no live account). Tests send forwarded headers |
| 4 | **Logging to a file on an ephemeral disk.** | `utils/log_config.py`, `app.py` | **DONE 2026-11-24.** Production and `LOG_TO_STDOUT=1`: stdout only, no `RotatingFileHandler`. Development: `logs/mindful_horizon.log` (git-ignored). The app logger is named `app` explicitly (it was silently rebound to models' logger by `from models import *`). Redaction and request ids are unchanged |
| 5 | **Engine options for Neon.** | `utils/database_utils.py`, `routes/ops.py` | **DONE 2026-11-24.** `-pooler` hosts get no `options` startup parameter (so no statement timeout there; set one on the role with `ALTER ROLE ... SET statement_timeout` if wanted); `connect_timeout` 15 s (`DB_CONNECT_TIMEOUT`); `pool_recycle` 300; `postgres://` normalised; `wait_for_database()` retries 3 times (1 s, 2 s) at startup and twice in `/ready`. Not verified against a live Neon |
| 6 | **`FLASK_APP` and `.flaskenv`.** | `Dockerfile` (`ENV FLASK_APP=app.py`) | Done in the image: no `.flaskenv` is needed (and none exists). On your own computer set `FLASK_APP=app.py` (section 6) |
| 7 | **Scheduler and worker.** The in-process worker starts from `init_jobs(app)`, only for web processes, not for `flask` CLI commands, and defaults on in production. It works with the single eventlet worker. | `app.py:213`, `utils/jobs.py:217-230` and `:271-290` | Done for one always-on instance. Remaining: on a sleeping instance timers stop (section 1). `--preload` and several workers must not be used (each would start its own worker thread) |
| 8 | **Job poll keeps Neon awake.** | `utils/jobs.py`, `utils/worker_wake.py` | **DONE 2026-11-24.** The worker no longer polls. It sleeps until a commit that enqueued a job (in-process wake event), the next job's `run_at`, or `JOB_IDLE_MAX_SECONDS` (900 s in-process, 60 s for a separate `flask jobs-worker`). Crisis alerts run about a second after commit; escalation timers run at their `run_at`. A job left `running` by a crash is recovered within the idle cap (up to 15 min) |
| 9 | **webassets output directory.** The bundles `gen/packed.js` and `gen/packed.css` are written to `static/gen`. | `app.py:216-233` | Done: the Dockerfile runs `flask assets build` at image build time (tested locally: the command works with a throwaway SQLite path and `SKIP_CREATE_ALL=1`, it logs "Failed to initialize database" and carries on). The files are owned by user `app`, so runtime rebuilds would also work. The Jinja cache `instance/jinja_cache` (`app.py:153-160`) falls back to memory if not writable |
| 10 | **Other writes to the local disk at runtime.** `instance/` and `flask_session/` are created in `/app` (writable by `app`). | `extensions.py:90`, `app.py:156` | Done (all are safe to lose) |

Items 1 to 5 and 8 are done in code; what remains is verifying them on a real Render and Neon account (nothing here was run against either).

## Sources (all read 2026-11-24)

- https://render.com/docs/free (free limits, spin-down, shell, workers, ephemeral disk)
- https://render.com/docs/blueprint-spec (render.yaml fields, `generateValue`, `sync: false`, regions, `autoDeployTrigger`)
- https://render.com/docs/web-services (PORT 10000, bind 0.0.0.0, TLS terminated at the load balancer)
- https://render.com/docs/health-checks (2xx/3xx within 5 s, 15 minute deploy window, restart after 60 s)
- https://render.com/docs/websocket (WebSocket support, use wss://)
- https://render.com/docs/rollbacks (dashboard rollback)
- https://render.com/docs/regions (five regions, none in India)
- https://render.com/docs/compute-plans (free: 0.1 CPU, 512 MB)
- https://neon.com/docs/introduction/plans (free 1 GB, 100 CU-hours, 5 minute suspend, 6 hour restore, Launch pricing)
- https://neon.com/docs/introduction/regions (eight regions, Singapore `aws-ap-southeast-1`)
- https://neon.com/docs/connect/connection-pooling (`-pooler`, transaction mode, use direct for migrations and pg_dump)
- https://neon.com/docs/connect/connection-errors (unsupported startup parameter)
- https://neon.com/docs/connect/connect-from-any-app (connection string format, `sslmode=require`)
- https://neon.com/docs/connect/connection-latency (wake-up time, connect timeout, retries)
