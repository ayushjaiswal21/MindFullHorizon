"""Request ids, one access-log line per request, and a redaction filter. Owned by Q1a.

Never logs request bodies, query strings, emails or tokens. `init_logging(app)` is idempotent.
"""
import logging
import re
import time
import uuid

from flask import g, request, session

_RID_OK = re.compile(r'[A-Za-z0-9_-]{1,64}')
_EMAIL = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
_BEARER = re.compile(r'(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]{8,}')
_SECRET = re.compile(r'(?i)\b(password|passwd|secret|token|api[_-]?key|authorization)\b(\s*[=:]\s*)\S+')
_LONG_TEXT = re.compile(r'"[^"\n]{120,}"|\'[^\'\n]{120,}\'')


def redact(text):
    text = _EMAIL.sub('[email]', text)
    text = _BEARER.sub(r'\1 [redacted]', text)
    text = _SECRET.sub(r'\1\2[redacted]', text)
    return _LONG_TEXT.sub('[text omitted]', text)


class RedactionFilter(logging.Filter):
    """Handler-level variant of `redact` (the record factory installed by init_logging already covers all handlers)."""

    def filter(self, record):
        record.msg, record.args = redact(record.getMessage()), None
        return True


def _user_id():
    try:
        uid = session.get('user_id')
    except Exception:
        return '-'
    return uid if isinstance(uid, int) else '-'


def _install_record_factory():
    """Redact at record creation: covers every handler, including ones added later (file rotation, etc.)."""
    old = logging.getLogRecordFactory()
    if getattr(old, '_is_redacting', False):
        return

    def factory(*args, **kwargs):
        record = old(*args, **kwargs)
        try:
            record.msg, record.args = redact(record.getMessage()), None
        except Exception:
            pass
        return record
    factory._is_redacting = True
    logging.setLogRecordFactory(factory)


def init_logging(app):
    """Redact every log record and add the request-id/access-log hooks. Idempotent."""
    if app.extensions.get('logging_setup'):
        return
    app.extensions['logging_setup'] = True
    _install_record_factory()
    access = logging.getLogger('access')

    @app.before_request
    def _start():
        inbound = request.headers.get('X-Request-ID', '')
        g.request_id = inbound if _RID_OK.fullmatch(inbound) else uuid.uuid4().hex
        g.request_start = time.perf_counter()

    @app.after_request
    def _finish(response):
        rid = getattr(g, 'request_id', None)
        if rid:
            response.headers['X-Request-ID'] = rid
            ms = int((time.perf_counter() - getattr(g, 'request_start', time.perf_counter())) * 1000)
            access.info('request method=%s path=%s status=%s duration_ms=%s user_id=%s request_id=%s',
                        request.method, request.path, response.status_code, ms, _user_id(), rid)
        return response
