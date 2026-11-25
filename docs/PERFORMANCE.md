# Performance and memory

Owner: wave P (backend). Written 2026-11-24 against the code of that day. Measured on a Windows 11 dev laptop, Python 3.11, SQLite, other processes running, so read the numbers as ratios, not budgets. Guards live in `tests/test_perf.py` (`pytest tests/test_perf.py -q`; skip the slow memory loop with `-k "not memory_growth"`). Design intent: [DESIGN.md](DESIGN.md) section 6.

## 1. Measured results

| Metric | Before | After | How |
|---|---|---|---|
| `import app` wall time | 8.3 s | 4.6 to 5.3 s (two runs) | `python -X importtime` on a script that only does `import app` (temp SQLite DB) |
| `import app` RSS | 161 MB | 143 MB | `psutil` right after the import |
| `nltk`, `textblob` in `sys.modules` after import | both | neither (`librosa`, `numpy` are not installed here; the test checks them too) | `test_import_app_does_not_load_heavy_libraries` (subprocess) |
| Provider dashboard SQL statements, 3 vs 30 assigned patients | not measured | flat, same count at both sizes (ceiling asserted: 25) | `test_provider_dashboard_query_count_is_flat` |
| Blog list SQL statements, 3 vs 31 posts | 3 per post | flat (ceiling 8) | `test_blog_list_query_count_is_flat` |

| RSS after 1,200 requests (6 routes, guest and patient) | n/a | 142.2 MB at request 1, 143.4 at 100, 143.6 at 1,200 (flat) | script: create app, loop `test_client` requests, `psutil` RSS after `gc.collect()` |
| tracemalloc net growth over 300 requests after warm-up | n/a | 443 KiB | `test_memory_growth_over_300_requests` (limit 4 MB) |

What is left in the 4.6 to 5.3 s: `google.generativeai` about 1.4 s and 40 MB (imported at the top of `ai/gemini_impl.py`, owned by the LLM agent: move the import inside the functions that call it to reach about 3.7 s), `models`/SQLAlchemy/Alembic about 1.5 s, `eventlet` DNS about 0.65 s (pulled in by Flask-SocketIO because eventlet is installed), Flask-SocketIO itself 0.5 s. `app` module self time fell from 2.5 s to 0.4 s once the nltk corpus check and download were removed.

Reproduce:

```
python -X importtime scripts_or_snippet_that_imports_app 2> imports.txt
sort -t'|' -k2 -n -r imports.txt | head -25
```

## 2. What changed

### Startup and memory (items 1, 7)
- `app.py` no longer imports `nltk` and never downloads corpora. `TextBlob` is wrapped in `utils/sentiment.py` (`TextBlob(text)` imports on first call; `TEXTBLOB_AVAILABLE` is a `find_spec` check). TextBlob's default pattern analyser needs no corpus, so sentiment still works without nltk data.
- `librosa` and `numpy` are imported inside `utils/voice_features.extract_features` only; `LIBROSA_AVAILABLE` is a cheap `find_spec`. The audio goes to a temp file deleted in `finally`; only the measurements are stored.
- Log file: development only, `logs/mindful_horizon.log` (`RotatingFileHandler`, 5 MB x 3 files). Production and `LOG_TO_STDOUT=1` log to stdout only.
- Sessions: signed cookies, `PERMANENT_SESSION_LIFETIME` 24 h (`SESSION_LIFETIME_HOURS`); no server-side files, no `SESSION_FILE_*`, no `flask prune-sessions` (docs/SECURITY.md, Sessions).
- Rate limiter: explicit `memory://` storage (per process, bounded by the 1-day window; `RATELIMIT_STORAGE_URI` overrides, Redis when a second worker exists).

Sweep result (module-level state): no unbounded dict or list found. `utils/seo._memo` has a fixed set of keys; `ai/service` and `routes/ops` use `lru_cache(maxsize=1..4)`; `utils/llm_guard` per-user state is an `OrderedDict` with a `max_users` bound; `utils/jobs` registries are filled at import and never grow; the SocketIO handlers hold no global state (rooms are released by python-socketio on disconnect). Jinja environment, SQLAlchemy engine and `Compress` are created once, not per request. Known remaining growth: Flask-Limiter memory counters grow with distinct IPs until their window expires.

Memory proof: `test_memory_growth_over_300_requests` warms up 60 requests, then runs 300 over nine endpoints (guest pages, patient and provider dashboards, JSON APIs) under `tracemalloc` and fails if net allocation growth passes 4 MB; it prints the top five growing lines on failure.

### Database (items 2, 3)
- `utils/database_utils.engine_options(url)`: SQLite gets only `check_same_thread=False` (no pool arguments); PostgreSQL gets `pool_size=5`, `max_overflow=5`, `pool_timeout=10`, `pool_recycle=1800`, `pool_pre_ping=True` and `statement_timeout=10000` ms. Env: `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT`, `DB_POOL_RECYCLE`, `DB_STATEMENT_TIMEOUT_MS`. Bad values fall back to the defaults.
- `normalize_db_url` rewrites `postgres://` to `postgresql://`.
- SQLite connect listener in `extensions.py`: `journal_mode=WAL`, `synchronous=NORMAL`, `busy_timeout` (`SQLITE_BUSY_TIMEOUT_MS`, default 5000). The existing `foreign_keys=ON` listener in `models.py` is untouched.
- N+1 and row-volume fixes: blog list (`utils/query_utils.with_blog_counts`: two grouped COUNTs for the whole page, the template keeps using `post.like_count`/`post.comment_count`; author via `joinedload`); chat history (`joinedload(sender)`); provider dashboard and appointments (`latest_by_user` and `latest_scores` now use one `ROW_NUMBER() OVER (PARTITION BY ...)` statement instead of reading every row of every patient); analytics (detox trends and engagement are `GROUP BY` queries, not Python loops over rows); breathing and yoga totals load two columns (`load_only`). Unbounded `.all()` calls got caps: caseload 1000, patient appointments 500, assessments page 500, progress page 1000, blog comments 200.

### Caching (item 5)
- `extensions.cache` (Flask-Caching). `CACHE_TYPE` env: default `SimpleCache` (per process), `NullCache` when `FLASK_ENV=testing`, `RedisCache` with `REDIS_URL` (needed for more than one worker; today there is one eventlet worker). `CACHE_DEFAULT_TIMEOUT` 60, `CACHE_THRESHOLD` 500.
- `utils/cache_utils.py`: `cached(namespace, key_parts, ttl, compute)`. Keys carry the institution (lower-cased, trimmed) and the minimum-group size, e.g. `inst:summary:test university:5:g1732...`. Invalidation: a `Session` `after_flush`/`after_commit` listener bumps a per-namespace generation when a commit touches a watched model (users, assessments, appointments, moods, detox, medication, breathing, yoga, music, gamification, crisis events for `inst`; blog post, like, comment for `blog`). Bumping orphans old keys without scanning. TTL is the backstop (summary 60 s, analytics 120 s, blog insights 60 s). Bulk `query.update()`/`delete()` bypass the listener and wait for the TTL.
- Cached: `institution_summary` (dashboard and analytics), the analytics aggregates, blog list insights. Never cached: anything per user (moods, journal, chat, patient pages) and rendered HTML (it carries the CSRF token, CSP nonce and flashes).
- HTTP: `/static/gen/*` with a query string, any static file with `?v=`, and file names with a hash segment get `public, max-age=31536000, immutable`. Other static files keep Flask's `ETag` + `Last-Modified` conditional responses (304). HTML: `no-cache` (`private, no-cache` when logged in) with `Vary: Cookie`. JSON: `no-store`. A route that sets its own `Cache-Control` wins.

### Compression (item 6)
Flask-Compress: gzip and brotli (`br` first), `COMPRESS_MIN_SIZE=500`, `COMPRESS_BR_LEVEL=4`, types html, css, js, json, svg, xml, rss, plain text. Dynamic responses (HTML, JSON) use brotli or gzip. Static files are streamed responses, and Flask-Compress streams only zstd, br and deflate (gzip is off for streams by default), so a client that sends only `gzip` gets static files uncompressed, while browsers that send `deflate` or `br` get them compressed. Verified by tests for JSON, HTML, static CSS/JS/SVG (when a file over 600 bytes exists), a small response staying uncompressed, and Socket.IO polling carrying no `Content-Encoding`.

### Server response (item 8)
`TEMPLATES_AUTO_RELOAD` is on only with `FLASK_DEBUG=1`; outside debug a Jinja `FileSystemBytecodeCache` lives in `instance/jinja_cache`. The two `after_request` hooks do header work only (no queries; the cache hook reads the already loaded session). Gemini calls already have timeouts and are owned by `ai/`. The Dockerfile `CMD` is unchanged: `--preload` is unsafe with eventlet and the jobs thread, `--max-requests` would drop WebSockets, and the eventlet worker already multiplexes connections.

### CSP switch (item 9)
The CSP is enforcing by default and its rules are tested in tests/test_csp.py (see docs/SECURITY.md); `CSP_REPORT_ONLY=1` is the emergency fallback.

## 3. Pagination contract

Request: `?page=` (1-based) and `?per_page=` (default 20, maximum 100). Anything that is not an integer falls back to the default; numbers clamp into range (`page=0` is 1, `per_page=0` is 1, `per_page=100000` is 100); a page past the end returns an empty list with `has_next: false`. Never a 500. Helper: `utils/pagination.py` (`page_args`, `paginate`, `page_meta`, `set_page_headers`).

Response: `{"items": [...], "page": n, "per_page": n, "total": n, "has_next": bool}` for new endpoints. Existing endpoints keep their legacy key (their JS reads it) and gain `"meta": {"page", "per_page", "total", "has_next"}`. Bare-array bodies stay arrays and send `X-Page`, `X-Per-Page`, `X-Total-Count`, `X-Has-Next` headers. Order is newest first for paging; chart endpoints reverse the page so the array reads oldest to newest.

| Endpoint | Legacy shape kept | Default `per_page` | Why not 20 |
|---|---|---|---|
| `GET /api/mood` | `{"ok", "moods"}` + `meta` | 20 | dashboard chart shows 14 |
| `GET /patient/api/progress` | `{"ok", "assessments", "moods"}` + `meta: {assessments, moods}` | 100 | feeds history charts |
| `GET /patient/api/digital-detox-data` | bare array + headers | 30 | a month chart |
| `GET /api/chats/<id>/messages` | bare array + headers | 20 | chat JS does `Array.isArray` |
| `GET /patient/api/goals` | `{"success", "goals"}` + `meta` | 100 | goals page has no paging UI |
| `GET /provider/appointments` | `{"success", "appointments"}` + `meta` | 100 | dashboard table has no paging UI |
| `GET /blog/api/<post>/comments/<id>/replies` | `{"success", "replies"}` + `meta` | 100 | no paging UI |
| `GET /blog/` (HTML) | template context `pagination` | 20 | `?page=` works; the template has no pager yet |
| `GET /patient/journal`, `/patient/voice-logs` (HTML) | template context `pagination` | 50 | same |

A frontend that wants a pager reads `meta.has_next` / `X-Has-Next` and requests `page+1`. The tests clamp-check every row above (`test_paginated_endpoints_never_500`).

## 4. app.py split (O-15)
The music and audio routes (`/api/mood-music`, `/api/play-mood`, `/audio/<path>`, `/api/mood-audio`, `/music`, `/api/log-mood-selection`) moved to `routes/audio.py` (about 550 lines out of `app.py`). They are registered with `app.add_url_rule` from `register_audio_routes(app)`, not as a blueprint, so every endpoint name and URL is unchanged (`url_for('serve_audio')` still works); the auth and rate-limit decorators are applied in that function. Still in `app.py`: profile, chat page, `/api/message`, telehealth pages, voice upload and delete, journal delete, error handlers, SocketIO handlers, Google OAuth.

## 5. Environment variables added

`DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT`, `DB_POOL_RECYCLE`, `DB_CONNECT_TIMEOUT`, `DB_STATEMENT_TIMEOUT_MS`, `SQLITE_BUSY_TIMEOUT_MS`, `CACHE_TYPE`, `CACHE_DEFAULT_TIMEOUT`, `CACHE_THRESHOLD`, `REDIS_URL`, `RATELIMIT_STORAGE_URI`, `SESSION_LIFETIME_HOURS`, `CSP_REPORT_ONLY`, `JOB_IDLE_MAX_SECONDS`, `TRUST_PROXY`, `LOG_TO_STDOUT`.

## 6. Not done, and risks

- `import app` is still above the 3 s budget until `ai/gemini_impl.py` imports `google.generativeai` lazily (not mine to edit).
- Cache invalidation is generation-wide per namespace: any write to a watched table refreshes every institution's aggregates. Correct, but the hit rate drops under heavy write traffic. Per-institution keys would need the institution on every write path.
- SimpleCache and the rate limiter are per process. A second worker or a SocketIO message queue means Redis for both.
- Offset pagination is used (the DESIGN keyset idea is for new unbounded feeds); fine at current table sizes.
- Voice upload retention and moving uploads out of `static/` are open (see DESIGN 6.10).
- Window functions need SQLite 3.25+ (Python 3.11 ships 3.4x) or PostgreSQL.
