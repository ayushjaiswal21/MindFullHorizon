# CI/CD: GitHub Actions and Render

Written 2026-11-24. Files: `.github/workflows/ci.yml`, `.github/workflows/post-deploy.yml`, `.github/dependabot.yml`,
`.github/pull_request_template.md`, `scripts/ci_local.py`, `scripts/check_file_sizes.py`, `scripts/oversize_baseline.json`,
`tests/test_ci_config.py`, `tests/test_file_size.py`, the `autoDeployTrigger` line in `render.yaml`.

**What was not verified.** GitHub Actions and Docker could not be run where this was written (Windows, no Docker, no
GitHub access). Everything below was checked locally only as far as stated: the YAML parses, every path the workflows
mention exists, and the pytest, scan_imports, css build, `node --check` and file-size commands were run for real. The
workflows themselves have never run. Expect the first run to need small fixes (checklist at the end). Action versions
(`checkout@v4`, `setup-python@v5`, `setup-node@v4`) are the newest majors I could confirm from memory; I could not
look up newer ones. Dependabot proposes upgrades weekly. The `cache` step is the built-in cache of `setup-python` and `setup-node`.

## 1. The pipeline

```
push or pull request
   |
   v
CI workflow (ci.yml) ---- test      pip install, scan_imports, compileall, pytest        ~4-6 min
   |                  |-- frontend  npm ci, build:css, git diff on tailwind.css, node --check  ~1-2 min
   |                  |-- docker    docker build, run with FLASK_ENV=production, /health, /ready  ~4-7 min
   |                  |-- e2e       demo server + 4 browser specs (advisory, continue-on-error)    ~5-8 min
   |                  |-- audit     pip-audit, npm audit (advisory)                                 ~1 min
   |                  '-- ci-ok     passes only if test, frontend, docker all succeeded
   v
push to main only: Render "checksPass" waits for CI, then builds the Dockerfile and deploys
   |   (container start runs `flask db upgrade`, then gunicorn; Render polls /health)
   v
post-deploy.yml (after CI succeeds on main): needs repository variable SITE_URL
   waits for /health then /ready (up to 10 min), checks /robots.txt and /sitemap.xml
```

Times are estimates, not measurements. Update them after the first runs.

## 2. What each job checks and how to read a failure

| Job | Checks | If it fails |
|---|---|---|
| `test` | `scan_imports.py` (imports match `requirements.txt`), `compileall`, `pytest tests -q`. The suite sets its own temp SQLite DB and env in `tests/conftest.py`; no secrets, no Gemini | Open the failed step. Pytest prints the failing test; reproduce with `pytest tests/<file>.py -q`. `tests/test_file_size.py` failing means the 300-line rule (section 3) |
| `frontend` | Rebuilds `static/css/tailwind.css` and fails when it differs from the committed file; `node --check` on every `static/js/**/*.js` | CSS diff: run `cd tools/frontend && npm ci && npm run build:css`, commit the file. JS: the log names the file with the syntax error |
| `docker` | Builds the repo `Dockerfile`, confirms user `app` and `static/gen`, runs the image with `FLASK_ENV=production`, a random 48-char `SECRET_KEY`, `DATABASE_URL=sqlite:////tmp/ci.db`, then polls `/health` (90 s) and `/ready` | The last step prints the container log. `MIGRATION FAILED` means `flask db upgrade` broke (new migration problem). `SECRET_KEY must be set` means a new required env var. This is the only place the Dockerfile and the start-up migration path are exercised |
| `e2e` | Starts `scripts/local_demo.py --port 5000` (seeded demo accounts), runs `assessment_progress`, `chat`, `breathing`, `clinical_smoke` in Chrome. Not required yet | The log groups one block per spec; each prints PASS or FAIL lines. The job is marked passed even when it fails (`continue-on-error`), so look at the job itself, not the summary tick |
| `audit` | `pip-audit -r requirements.txt`, `npm audit --omit=dev` in `tools/frontend`. Output is also in the job summary | Advisory only. Read it weekly; fix by bumping the pinned range in `requirements.txt` |
| `ci-ok` | Needs `test`, `frontend`, `docker` all `success`. Uses `if: always()` because a skipped job would otherwise count as passed | Fix whichever of the three failed |

`concurrency` cancels a run when a newer push to the same branch arrives, so "cancelled" on an old run is normal.

### Making e2e required

Once `e2e` has been green on every push for about a week: in `ci.yml` delete `continue-on-error: true` from the `e2e` job,
add `e2e` to `needs` of `ci-ok` and to its final `test` line, and update `tests/test_ci_config.py` (`test_ci_jobs_and_ci_ok_gate`).
Keep the one required check name `ci-ok`. Until then a flaky spec cannot block a deploy.

## 3. Run it locally

```
python scripts/ci_local.py          # pytest, scan_imports, compileall, file sizes, YAML, css build, node --check
python scripts/ci_local.py --fast   # same without pytest
```

It prints PASS, FAIL or SKIP per step and the total time (Windows and Linux). The css step is skipped when `node` or
`tools/frontend/node_modules` is missing (`cd tools/frontend && npm ci`). Docker and the browser specs are not part of it:

- Docker: the commands in the `docker` job, or `docs/DEPLOY.md` section 7.
- e2e: `python scripts/local_demo.py --port 5000`, then `cd tools/e2e && node specs/<name>.mjs` (see `tools/e2e/README.md`; set `EDGE` if the browser is not Edge on Windows).

YAML checks and `tests/test_ci_config.py` need PyYAML (`pip install -r requirements/dev.txt`).

### The 300-line rule

`scripts/check_file_sizes.py` (run by `tests/test_file_size.py`) counts lines of `.py`, `.js`, `.css`, `.html` files, tests included. It skips
`migrations/`, `static/gen`, `static/uploads`, minified files, `static/css/tailwind.css`, `node_modules`, `docs`, `data`, `instance`,
dot folders and `venv*`. Files already over the limit are listed with their size in `scripts/oversize_baseline.json`. The test fails when
(a) a new file is over 300 lines, (b) a listed file grew, (c) a listed file is now 300 lines or fewer: delete its entry. When the split
wave empties the list, delete `scripts/oversize_baseline.json` and the baseline code path. `python scripts/check_file_sizes.py --write-baseline`
regenerates the file from today's sizes: use it only once, at the start, never to silence a failure.

## 4. Repository variable SITE_URL (post-deploy check)

1. GitHub, repository **Settings**, **Secrets and variables**, **Actions**, tab **Variables**, **New repository variable**.
2. Name `SITE_URL`, value `https://your-name.onrender.com` (https, no trailing slash). **Add variable**.

Without it `post-deploy.yml` finishes green with a notice "SITE_URL is not set". It is a variable, not a secret: a public URL.
The workflow also has a **Run workflow** button (Actions tab, "Post-deploy check") to test the live site by hand.

Limit: `/health` returns no build id, so the check cannot prove the answering instance is the new build. It sleeps 150 s so Render
has started the deploy, then waits for `/health` and `/ready` (a free instance needs about a minute to cold start). It does prove
that the live site is up, migrated (`/ready` is 200) and serves `robots.txt` and `sitemap.xml`. For exact proof, a later change could
add `RENDER_GIT_COMMIT` to `/health` and compare it to `github.event.workflow_run.head_sha`. Also note: Render's `checksPass`
waits for the checks on the commit; this workflow's own run is created after CI ends, so it should not hold up the deploy, but
that ordering is unverified. If a deploy ever waits on it, remove `post-deploy.yml` from the required checks.

## 5. Branch protection (the owner does this in the GitHub UI)

1. Run CI once on `main` or on a pull request, so the name `ci-ok` exists (GitHub only offers check names it has seen).
2. Repository **Settings**, **Branches**, **Add branch protection rule** (or **Add classic branch protection rule**).
3. Branch name pattern: `main`.
4. Tick **Require status checks to pass before merging**; tick **Require branches to be up to date before merging**.
5. In the search box type `ci-ok` and select it (source GitHub Actions). Do not add `test`, `docker`, `e2e` separately.
6. Optional for a team: **Require a pull request before merging**. Leave **Do not allow bypassing the above settings** unticked while one person owns the repo.
7. **Create** / **Save changes**.

Warning: with required checks, GitHub rejects a direct push to `main` that has not already passed them. Enable this after the
planned fast-forward of `main` (decision P-06), or tick **Allow specified actors to bypass** for the owner. Newer repositories may show
this under **Settings**, **Rules**, **Rulesets**; the same option is called "Require status checks to pass".

## 6. How the Render deploy trigger works

`render.yaml` has `autoDeployTrigger: checksPass` on the web service. Source: https://render.com/docs/blueprint-spec (read
2026-11-24): the field replaces the deprecated `autoDeploy` boolean and takes `commit` (every push to the branch),
`checksPass` ("deploy only if the linked branch's CI checks pass") or `off`. https://render.com/docs/deploys (read 2026-11-24):
"After CI Checks Pass" works with GitHub Actions; Render does **not** deploy when zero checks are found for the commit or when at least
one fails. CI therefore runs on every push to `main` (no path filter in `ci.yml`), and the advisory jobs use `continue-on-error`
so their failure does not block a deploy; only `test`, `frontend`, `docker` can.

- **Sync the Blueprint.** Editing `render.yaml` changes nothing until Render re-reads it: Render dashboard, **Blueprints**, the
  MindFull Horizon blueprint, **Sync** (exact labels not verified). If the service was created by hand instead, set it in
  the service: **Settings**, **Build & Deploy**, **Auto-Deploy**: **After CI Checks Pass**.
- `docs/DEPLOY.md` step 7 still says `autoDeployTrigger: commit`; this file supersedes it.
- A failed deploy keeps the previous version running. A migration runs at container start, so a bad migration fails the deploy before traffic moves (`docs/DEPLOY.md` sections 5 and 12).

### Rollback

Render dashboard, service, **Deploys**, pick an earlier successful deploy, **Rollback**. A dashboard rollback turns auto deploy off
for the service: turn it back on afterwards (https://render.com/docs/rollbacks, read 2026-11-24, via `docs/DEPLOY.md` section 10). The database is not rolled back:
if the bad deploy included a migration, prefer a fix-forward commit (read `docs/DEPLOY.md` section 10 before running any `flask db downgrade`).
Each pull request has a Rollback section for this reason.

## 7. Secrets

No Actions secrets are used and none are needed: the workflows use `permissions: contents: read`, a throw-away `SECRET_KEY` generated inside the
docker job, and a local SQLite file. `tests/test_ci_config.py` fails if a workflow references `secrets.` or contains a token-like string.
Real secrets (`DATABASE_URL`, `GEMINI_API_KEY`, SMTP) live only in the Render dashboard. If a secret is ever added to Actions
(for example a deploy hook), document it here, add it under the job that needs it, and update that test deliberately.
Never run live Gemini in CI.

## 8. Pushing workflow files

A push that creates or changes anything under `.github/workflows/` is rejected unless the token or credential has the `workflow` scope
(GitHub error "refusing to allow an OAuth App to create or update workflow ... without `workflow` scope"). The lead handles this
push. With `gh`: `gh auth refresh -s workflow`. A fine-grained token needs **Workflows: read and write**.

## 9. First-run checklist

Open the Actions tab after the first push and expect to fix some of these (they come from developing on Windows):

- [ ] **Chrome path.** `EDGE=/usr/bin/google-chrome`. If the e2e job says it cannot launch, check the runner image still ships Chrome.
- [ ] **CSS diff.** The committed `tailwind.css` was built on Windows. If `frontend` fails on the diff at the very first run, rebuild on Linux once (`npm ci && npm run build:css`) and commit; check for line endings (`.gitattributes` with `* text=auto`).
- [ ] **Case and path separators.** Linux paths are case sensitive: an import or template name with the wrong case works on Windows only. `tests/` use `os.path`, but a hard-coded backslash would fail.
- [ ] **Line endings.** CRLF in shell scripts or `.sh` files breaks them on Linux (none exist in this repo today).
- [ ] **Migrations on SQLite.** The docker job migrates a SQLite file, production uses Postgres. A migration that needs `batch_alter_table` can pass on one and fail on the other.
- [ ] **Docker `/ready`.** Returns 200 only when `alembic_version` equals the head. If it is 503 in the smoke test, read the log before relaxing the check.
- [ ] **Chat spec.** It needs a fallback reply longer than 40 characters with no `GEMINI_API_KEY`; it may need loosening. Fine while `e2e` is advisory.
- [ ] **`pip install -r requirements/dev.txt`.** Heavy packages (`eventlet`, `psycopg2-binary`, `google-generativeai`) may resolve differently from the local venv; compare with `pip freeze` if the suite behaves differently.
- [ ] **Repository variable** `SITE_URL` (section 4) and **branch protection** (section 5).
- [ ] **Render.** Sync the Blueprint, then push a trivial commit and check that Render waits for CI. Fill in the real times in section 1.
