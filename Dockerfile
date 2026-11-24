# Python 3.11: matches the pinned dependency set (numpy<2 etc. have no 3.13 wheels)
FROM python:3.11-slim

# Unbuffered logs reach Render's log stream at once; no .pyc files in the image.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

RUN useradd --create-home --shell /bin/bash app && chown -R app:app /app
USER app

ENV FLASK_APP=app.py

# Build the packed JS/CSS bundles now so the first request does not write to the disk.
# `flask assets build` imports app.py, which tries the database once; a throwaway SQLite file and
# SKIP_CREATE_ALL=1 keep that harmless (it logs "Failed to initialize database" and carries on).
# Not FLASK_ENV=production here, so the SECRET_KEY check does not fire at build time.
RUN DATABASE_URL=sqlite:////tmp/assets-build.db SKIP_CREATE_ALL=1 SECRET_KEY=build-only flask assets build \
    && rm -f /tmp/assets-build.db*

EXPOSE 5000

# Fails on non-2xx responses (requests.get alone would not). Render ignores this and uses healthCheckPath;
# it is for plain `docker run`. Uses the same PORT the server binds to.
HEALTHCHECK --interval=30s --timeout=30s --start-period=60s --retries=3 \
    CMD python -c "import os, requests; requests.get('http://localhost:%s/health' % os.getenv('PORT', '5000'), timeout=10).raise_for_status()" || exit 1

# 1. Migrate (3 tries, 5 s apart: the first try can fail while a scale-to-zero Neon database wakes up).
#    On failure print a clear message and exit non-zero so the platform marks the deploy failed and keeps the old version.
# 2. SocketIO needs the eventlet worker and exactly one worker process.
#    --timeout 60: eventlet workers heartbeat from the event loop, so this only catches a blocked loop.
#    --graceful-timeout 30: Render sends SIGTERM and waits 30 s before SIGKILL.
#    --keep-alive 75: longer than typical load balancer idle timeouts (Render's value is not documented).
CMD ["sh", "-c", "n=0; until SKIP_CREATE_ALL=1 flask db upgrade; do n=$((n+1)); if [ $n -ge 3 ]; then echo 'MIGRATION FAILED: check DATABASE_URL (use the direct Neon host) and the logs above. Not starting the server.' >&2; exit 1; fi; echo \"migration attempt $n failed, retrying in 5 s\" >&2; sleep 5; done; exec gunicorn --worker-class eventlet --workers 1 --bind 0.0.0.0:${PORT:-5000} --timeout 60 --graceful-timeout 30 --keep-alive 75 --access-logfile - --error-logfile - app:app"]
