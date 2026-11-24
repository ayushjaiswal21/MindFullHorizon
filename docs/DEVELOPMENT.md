# Development & deployment

## Run locally

```bash
python -m venv venv && venv\Scripts\activate      # Windows
pip install -r requirements.txt                    # tests: requirements/dev.txt, voice analysis: requirements/voice.txt
cp .env.example .env                               # then fill in values
# development: tables are created automatically on first start; production/Docker: SKIP_CREATE_ALL=1 flask db upgrade (docs/MIGRATIONS.md)
python app.py                                      # http://127.0.0.1:5000
```

## Environment variables

| Name | Purpose |
|------|---------|
| `SECRET_KEY` | Session signing. **Must be set**; the code still has an insecure fallback (tracked in STATUS.md) |
| `DATABASE_URL` | e.g. `sqlite:///mindful_horizon.db` (resolves inside `instance/`) or a PostgreSQL URL |
| `GEMINI_API_KEY`, `GEMINI_MODEL_NAME` | AI features (model name is currently ignored by the code) |
| `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET` | Google sign-in |
| `AUDIO_BASE_URL` | Optional. Base URL of a bucket holding the dataset mp3s (see below) |
| `FLASK_ENV` | `development` / `production` |

## Hosting notes (Render / Docker)

- SocketIO needs the eventlet worker: `gunicorn --worker-class eventlet --workers 1 app:app` (as in the `Dockerfile`).
  Vercel-style serverless hosting does not suit this app (WebSockets, long-lived workers).
- Use PostgreSQL in production; SQLite files on ephemeral disks are lost on redeploy.
- Do not commit `.env`. Rotate any key that was ever shared.

## Audio dataset on a hosted server

mp3 files are git-ignored (the six real tracks are ~36 MB each; most other files are 44-byte placeholders).
Metadata (`tracks.csv`, `data.json`) stays in git.

1. Upload the real mp3s to object storage (Cloudflare R2, S3, GitHub Release assets) keeping the `tracks/<name>.mp3` paths.
2. Set `AUDIO_BASE_URL` to that bucket's public URL. `/audio/tracks/<name>.mp3` then redirects there.
3. Known limit: `/api/mood-audio` still lists tracks by scanning the local folder, so on a server without the files it returns an empty list and the music page falls back to YouTube links. Making that listing metadata-driven is on the roadmap.

## Engineering standards

- Blueprints per feature; no new routes in `app.py`.
- Every DB write path handles errors and rolls back; schema changes go through Alembic.
- Validate input at every API boundary, check ownership before returning user data, never return `str(e)` to clients.
- Never put patient text into logs.
- AI features must degrade gracefully and must not give medical advice; crisis wording must show helpline numbers (Tele-MANAS 14416 in India).

## Repository layout notes (root files)

Only files that tools expect at the root stay there: `Dockerfile`, `.dockerignore`, `.env`/`.env.example`, `README.md`, `LICENSE`, `CLAUDE.md`, `render.yaml`, `requirements.txt` and the entry point `app.py` (gunicorn runs `app:app`). Everything else lives in folders:

- `requirements/dev.txt` (tests) and `requirements/voice.txt` (optional voice analysis); both include `../requirements.txt`.
- `tests/pytest.ini` holds the pytest settings; run `pytest tests -q` from the project root.
- `tools/frontend/` holds the Tailwind build (`package.json`, `tailwind.config.js`, `build_css.mjs`). After adding layout classes to templates: `cd tools/frontend && npm ci && npm run build:css`, then commit `static/css/tailwind.css`.
- `docs/SECURITY.md` is the vulnerability reporting policy (GitHub also finds it in `docs/`).
