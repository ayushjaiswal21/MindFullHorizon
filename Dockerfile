# Python 3.11: matches the pinned dependency set (numpy<2 etc. have no 3.13 wheels)
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd --create-home --shell /bin/bash app && chown -R app:app /app
USER app

ENV FLASK_APP=app.py

EXPOSE 5000

# Fails on non-2xx responses (requests.get alone would not)
HEALTHCHECK --interval=30s --timeout=30s --start-period=15s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5000/health', timeout=10).raise_for_status()" || exit 1

# SocketIO needs the eventlet worker and a single worker process
CMD ["sh", "-c", "SKIP_CREATE_ALL=1 flask db upgrade && exec gunicorn --worker-class eventlet --workers 1 --bind 0.0.0.0:${PORT:-5000} app:app"]
