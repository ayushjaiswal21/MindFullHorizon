"""Operational endpoints: /health (liveness) and /ready (readiness) (owned by the Q1 agent).

/health never touches the DB (it is the container restart probe). /ready checks the DB, the migration head and the
job queue, and returns a generic body on failure (no exception text).
"""
import logging
import os
from datetime import datetime
from functools import lru_cache

from flask import Blueprint, jsonify
from sqlalchemy import inspect, text

from extensions import csrf, db, limiter
from utils.database_utils import wait_for_database

ops_bp = Blueprint('ops', __name__)
logger = logging.getLogger(__name__)
STALE_JOB_SECONDS = 600


@ops_bp.route('/health')
@limiter.exempt
@csrf.exempt
def health():
    return jsonify({'status': 'ok'}), 200


@lru_cache(maxsize=1)
def _alembic_head():
    """Head revision from migrations/, or None when the folder is absent."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, 'migrations')
    if not os.path.isdir(path):
        return None
    cfg = Config()
    cfg.set_main_option('script_location', path)
    return ScriptDirectory.from_config(cfg).get_current_head()


@ops_bp.route('/ready')
@limiter.exempt
@csrf.exempt
def ready():
    checks = {}
    try:
        # short retry: the first query after a Neon scale-to-zero wake can fail once (docs/DEPLOY.md item 5)
        if not wait_for_database(2, 0.5, lambda: db.session.execute(text('SELECT 1'))):
            raise RuntimeError('database_unreachable')
        checks['database'] = 'ok'
        head = _alembic_head()
        if head:
            if inspect(db.engine).has_table('alembic_version'):
                current = db.session.execute(text('SELECT version_num FROM alembic_version')).scalar()
                checks['migrations'] = 'ok' if current == head else 'mismatch'
            else:  # dev/test bootstrap uses create_all and has no version table; production must be migrated
                checks['migrations'] = 'mismatch' if os.getenv('FLASK_ENV') == 'production' else 'untracked'
        from utils.jobs import stats
        s = stats()
        checks['jobs'] = {'queued': s['queued'], 'dead': s['dead'], 'oldest_due_age_s': s['oldest_due_age_s']}
        if s['oldest_due_age_s'] > STALE_JOB_SECONDS:
            checks['jobs_warning'] = 'stale_jobs'
    except Exception as exc:
        db.session.rollback()
        logger.error("readiness check failed err=%s", type(exc).__name__)
        return jsonify({'status': 'not_ready'}), 503
    if checks.get('migrations') == 'mismatch':
        return jsonify({'status': 'not_ready'}), 503
    return jsonify({'status': 'ready', 'checks': checks, 'time': datetime.utcnow().isoformat() + 'Z'}), 200
