"""Application logger setup. Production (and LOG_TO_STDOUT=1): stdout only, since the Render disk is ephemeral and the
dashboard shows stdout. Development: also a rotating file at logs/mindful_horizon.log (git-ignored).
Redaction and request ids live in utils/logging_setup.py and apply to every handler.
"""
import logging
import os
from logging.handlers import RotatingFileHandler

APP_LOGGER = 'app'  # also what Flask's `app.logger` is called; app.py must not let `from models import *` rebind it
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def stdout_only(env=os.environ):
    return env.get('FLASK_ENV') == 'production' or str(env.get('LOG_TO_STDOUT') or '').strip().lower() in ('1', 'true', 'yes', 'on')


def setup_app_logging(name=APP_LOGGER, env=os.environ, log_dir=None):
    """Return the app logger with a clean handler set. Console output comes from the root handler (logging.basicConfig)."""
    logger = logging.getLogger(name)
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    logger.setLevel(logging.DEBUG if env.get('FLASK_DEBUG') == '1' else logging.INFO)
    if stdout_only(env):
        return logger
    try:
        directory = log_dir or os.path.join(ROOT, 'logs')
        os.makedirs(directory, exist_ok=True)
        handler = RotatingFileHandler(os.path.join(directory, 'mindful_horizon.log'), maxBytes=5 * 1024 * 1024,
                                      backupCount=3, encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logger.addHandler(handler)
    except OSError:
        logger.warning("Log file is not writable; logging to the console only")
    return logger
