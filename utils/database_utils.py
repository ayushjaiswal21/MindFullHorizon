import os
import time
from urllib.parse import urlsplit

from flask import current_app
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from extensions import db


def normalize_db_url(url):
    """Render and Heroku hand out `postgres://`, which SQLAlchemy 1.4+ rejects.

    Also pins a bare `postgresql://` to the `psycopg2` driver explicitly. Without this, SQLAlchemy 2.1's own
    default dialect order picks `psycopg` (v3) first regardless of what is installed; `requirements.txt` only
    ships `psycopg2-binary`, so an unpinned URL crashes the app at startup with `ModuleNotFoundError: No module
    named 'psycopg'` the first time it is pointed at a real Postgres database (every test and the CI docker job
    use SQLite, so this was never exercised until a live Neon connection on 2026-11-25). A URL that already
    names a driver (`postgresql+psycopg2://`, `postgresql+psycopg://`) is left alone.
    """
    if url and url.startswith('postgres://'):
        url = 'postgresql://' + url[len('postgres://'):]
    if url and url.startswith('postgresql://'):
        url = 'postgresql+psycopg2://' + url[len('postgresql://'):]
    return url


def _int_env(env, name, default):
    try:
        return int(env.get(name, default))
    except (TypeError, ValueError):
        return default


def engine_options(url, env=os.environ):
    """SQLAlchemy engine options for the dialect in `url` (pool sizes are env-tunable).

    SQLite: no pool arguments (file databases use the default pool); `check_same_thread=False`
    because SocketIO and worker threads share connections. PostgreSQL: a small bounded pool
    (default 5 + 5 overflow stays under small managed plans), pre-ping, a 5 minute recycle (Neon suspends idle
    compute after 5 minutes), a connect timeout, and a server-side statement timeout sent as a startup option.
    Neon pooled hosts (`-pooler`) reject startup options, so they get no statement timeout here: set it on the role
    (`ALTER ROLE ... SET statement_timeout`), see docs/DEPLOY.md.
    """
    url = (url or '').lower()
    if url.startswith('sqlite'):
        return {'connect_args': {'check_same_thread': False}}
    opts = {'pool_pre_ping': True}
    if url.startswith('postgresql'):
        opts.update(
            pool_size=_int_env(env, 'DB_POOL_SIZE', 5),
            max_overflow=_int_env(env, 'DB_MAX_OVERFLOW', 5),
            pool_timeout=_int_env(env, 'DB_POOL_TIMEOUT', 10),
            pool_recycle=_int_env(env, 'DB_POOL_RECYCLE', 300),
        )
        if url.startswith(('postgresql:', 'postgresql+psycopg2:')):
            args = {'connect_timeout': _int_env(env, 'DB_CONNECT_TIMEOUT', 15)}
            if '-pooler' not in (urlsplit(url).hostname or ''):
                args['options'] = f"-c statement_timeout={_int_env(env, 'DB_STATEMENT_TIMEOUT_MS', 10000)}"
            opts['connect_args'] = args
    return opts


def wait_for_database(attempts=3, base_delay=1.0, probe=None):
    """`SELECT 1` with a short bounded retry (1 s, then 2 s): the first connection after a Neon scale-to-zero wake can
    fail or time out once. Only SQLAlchemy errors are retried. Returns True when the database answers (`probe` is
    a callable doing the query, default `SELECT 1`). Call inside an app context."""
    probe = probe or (lambda: db.session.execute(text('SELECT 1')))
    for attempt in range(attempts):
        try:
            probe()
            return True
        except SQLAlchemyError as exc:
            db.session.remove()
            current_app.logger.warning("Database not reachable (try %s of %s): %s", attempt + 1, attempts, type(exc).__name__)
            if attempt < attempts - 1:
                time.sleep(base_delay * (2 ** attempt))
    return False


def check_database():
    """Check if the database is properly initialized and accessible."""
    try:
        with current_app.app_context():
            if not wait_for_database():
                return False
            from models import User
            User.query.first()  # a missing users table raises here: the schema is not initialised
            current_app.logger.info("Database connection successful")
            return True
    except Exception as e:
        current_app.logger.error("Database connection error: %s", type(e).__name__, exc_info=True)
        return False

def init_db():
    """Dev/test bootstrap: create_all. Production (and `SKIP_CREATE_ALL=1`, needed for the first
    `flask db upgrade` on an empty DB) leaves the schema to Alembic migrations."""
    if os.getenv('FLASK_ENV') == 'production' or os.getenv('SKIP_CREATE_ALL') == '1':
        current_app.logger.warning("create_all skipped; run `flask db upgrade` (see docs/MIGRATIONS.md)")
        return False
    try:
        with current_app.app_context():
            db.create_all()
            current_app.logger.info("Database tables created successfully")
            return True
    except Exception as e:
        current_app.logger.error(f"Database initialization error: {str(e)}", exc_info=True)
        return False
