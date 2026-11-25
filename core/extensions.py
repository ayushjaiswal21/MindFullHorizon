"""Flask extensions initialization."""
import os
import sqlite3

from flask_caching import Cache
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_compress import Compress
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from sqlalchemy import event
from sqlalchemy.engine import Engine

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
compress = Compress()
csrf = CSRFProtect()
cache = Cache()
# Campus networks share one IP, so keep the global limit generous; auth routes add stricter ones.
# memory:// is per process (fine for the single eventlet worker); set RATELIMIT_STORAGE_URI=redis://... for more.
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["2000 per day", "300 per hour", "60 per minute"],
    storage_uri=os.getenv('RATELIMIT_STORAGE_URI') or "memory://",
    strategy="fixed-window",
    headers_enabled=True,
    retry_after="http-date",
)

COMPRESS_TYPES = [
    'text/html', 'text/css', 'text/plain', 'text/xml', 'text/javascript', 'application/javascript',
    'application/json', 'application/xml', 'application/xml+rss', 'application/rss+xml', 'image/svg+xml',
]


@event.listens_for(Engine, 'connect')
def _sqlite_tuning(dbapi_conn, _record):
    """WAL lets readers run beside the single writer; busy_timeout turns 'database is locked' into a short wait."""
    if isinstance(dbapi_conn, sqlite3.Connection):
        timeout_ms = int(os.getenv('SQLITE_BUSY_TIMEOUT_MS', '5000') or 5000)
        cur = dbapi_conn.cursor()
        cur.execute('PRAGMA journal_mode=WAL')
        cur.execute('PRAGMA synchronous=NORMAL')
        cur.execute(f'PRAGMA busy_timeout={timeout_ms}')
        cur.close()


def cache_config():
    """Flask-Caching settings from the environment. SimpleCache is per process: multi-worker needs Redis.

    Tests default to NullCache so aggregates cannot leak between tests; tests/test_perf.py swaps in a real one.
    """
    default = 'NullCache' if os.getenv('FLASK_ENV') == 'testing' else 'SimpleCache'
    cfg = {
        'CACHE_TYPE': os.getenv('CACHE_TYPE') or default,
        'CACHE_DEFAULT_TIMEOUT': int(os.getenv('CACHE_DEFAULT_TIMEOUT', '60') or 60),
        'CACHE_THRESHOLD': int(os.getenv('CACHE_THRESHOLD', '500') or 500),
    }
    if cfg['CACHE_TYPE'].lower() in ('rediscache', 'redis'):
        cfg['CACHE_REDIS_URL'] = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    return cfg


def init_extensions(app):
    """Initialize Flask extensions in the correct order."""
    # Ensure instance directory exists
    os.makedirs(os.path.join(app.root_path, 'instance'), exist_ok=True)

    # Initialize SQLAlchemy first
    db.init_app(app)

    # Then initialize Flask-Migrate
    migrate.init_app(app, db)

    # Initialize security features - CSRF is initialized in app.py
    # csrf.init_app(app)  # Already initialized in app.py

    # Caching, then compression last
    app.config.update(cache_config())
    cache.init_app(app)
    app.config.setdefault('COMPRESS_MIN_SIZE', 500)
    app.config.setdefault('COMPRESS_MIMETYPES', COMPRESS_TYPES)
    app.config.setdefault('COMPRESS_ALGORITHM', ['br', 'gzip'])
    app.config.setdefault('COMPRESS_BR_LEVEL', 4)
    compress.init_app(app)
