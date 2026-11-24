"""Hard time cap for model calls made on behalf of a page, plus a small per-user "do not retry yet" memory.

A page must never wait on the model. `run_capped` runs the call on a small worker pool and gives up after
`seconds`; the late worker finishes on its own and its answer is dropped. `NegativeCache` remembers, per user,
that generation just failed, so every later visit inside `ttl` skips the model and shows the plain fallback.
"""
import logging
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout

from flask import current_app

logger = logging.getLogger(__name__)

_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix='ai-cap')


def run_capped(fn, *args, seconds=8.0, **kwargs):
    """(ok, value): ok is False when fn raised or did not finish within `seconds`. Never raises."""
    app = current_app._get_current_object()

    def job():
        with app.app_context():
            return fn(*args, **kwargs)

    future = _POOL.submit(job)
    try:
        return True, future.result(timeout=seconds)
    except FutureTimeout:
        logger.warning('ai call capped after %ss (%s)', seconds, getattr(fn, '__name__', 'fn'))
    except Exception as exc:  # the model layer failed; never log its text
        logger.warning('ai call failed (%s)', type(exc).__name__)
    return False, None


class NegativeCache:
    """key -> expiry, at most `limit` keys (oldest dropped first), safe across threads."""

    def __init__(self, ttl=600.0, limit=2000):
        self.ttl, self.limit = ttl, limit
        self._items = OrderedDict()
        self._lock = threading.Lock()

    def blocked(self, key):
        with self._lock:
            until = self._items.get(key)
            if until is None:
                return False
            if until <= time.monotonic():
                del self._items[key]
                return False
            return True

    def add(self, key):
        with self._lock:
            self._items.pop(key, None)
            self._items[key] = time.monotonic() + self.ttl
            while len(self._items) > self.limit:
                self._items.popitem(last=False)

    def clear(self):
        with self._lock:
            self._items.clear()
