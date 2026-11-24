# MindFull Horizon

A Flask web app for college-student mental-health monitoring. Students check in (PHQ-9 / GAD-7, mood, journal, breathing, yoga, music), chat with an AI wellness companion, track goals and medication, and book sessions. Campus counselors get a provider dashboard with caseload, appointments, prescriptions and wellness reports.

> **Not a medical device.** MindFull Horizon supports everyday wellbeing and screening; it does not diagnose or treat any condition. If you or someone else is in danger, call **112**, or **Tele-MANAS 14416** (India, free, 24x7).

Status: work in progress. See [docs/STATUS.md](docs/STATUS.md) for what works, known issues and the roadmap.

## Features

| Area | What exists |
|------|-------------|
| Students | PHQ-9 / GAD-7 assessments, mood log, journal with sentiment, breathing, yoga (video library), music (binaural), digital detox, goals, medication log, gamification, progress and wellness reports |
| AI | Gemini-powered chat companion with a severity heuristic, assessment insights, journal and goal suggestions (falls back to canned text without an API key) |
| Providers | Caseload and risk level, appointment accept/reject, prescriptions, analytics, AI note drafting, telehealth signalling (WebRTC over SocketIO) |
| Community | Blog with likes and comments |

## Quick start

```bash
python -m venv venv && venv\Scripts\activate        # Windows (use source venv/bin/activate on Linux/macOS)
pip install -r requirements.txt
copy .env.example .env                               # then edit .env (SECRET_KEY, GEMINI_API_KEY)
python app.py                                        # http://127.0.0.1:5000
```

The SQLite database is created automatically on first start (`instance/mindful_horizon.db`).

## Tests

```bash
pip install -r requirements-dev.txt
pytest tests -q
```

Tests use a throw-away SQLite database and never call Gemini.

## Project layout

```
app.py            Flask app setup, SocketIO, OAuth, remaining legacy routes
routes/           Blueprints: auth, core, patient, provider, blog, assessment, mood, chat
models.py         SQLAlchemy models (source of truth for the schema)
ai/               Gemini service, severity heuristic; prompts in ai_prompts/
utils/            DB helpers, gamification
templates/ static/  Jinja2 pages, CSS, JS
tests/            pytest suite (tests/manual holds old manual scripts)
docs/             Architecture, development guide, status, safety research, requirements
scripts/          One-off tools (dataset import, schema bootstrap)
```

More detail: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

## Deploy

Use PostgreSQL (`DATABASE_URL`) and the eventlet worker, which SocketIO needs:

```bash
gunicorn --worker-class eventlet --workers 1 app:app
```

Set `SECRET_KEY`, `GEMINI_API_KEY`, `DATABASE_URL`, `FLASK_ENV=production`. The binaural-audio mp3s are not in git; see "Audio dataset on a hosted server" in [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md). A `Dockerfile` is provided.

## Security and privacy

Please report vulnerabilities privately; see [SECURITY.md](SECURITY.md). The app handles sensitive health data: never commit `.env`, rotate any key that was shared, and read the open issues in [docs/STATUS.md](docs/STATUS.md) before any public deployment.

## License

MIT, see [LICENSE](LICENSE). The binaural dataset under `data/binaural-beats-dataset/` carries its own license and README.
