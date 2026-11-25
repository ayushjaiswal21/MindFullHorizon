"""TTL caching for expensive aggregates, with write-driven invalidation.

Only institution-level aggregates and other non-personal data are cached. Keys always carry the
institution; never put per-user private responses here. Invalidation uses a generation counter:
any commit that touches a watched table bumps it, which orphans every key built from the old value
(no query, no key scanning). The TTL is the backstop. `cache` is per process (SimpleCache); a second
worker needs CACHE_TYPE=RedisCache, after which this code is unchanged.
"""
import time

from sqlalchemy import event
from sqlalchemy.orm import Session

from core.extensions import cache

SUMMARY_TTL = 60
ANALYTICS_TTL = 120
BLOG_TTL = 60

# model class name -> cache namespace whose generation it bumps
_WATCHED = {
    'User': 'inst', 'Assessment': 'inst', 'Appointment': 'inst', 'MoodLog': 'inst', 'DigitalDetoxLog': 'inst',
    'MedicationLog': 'inst', 'BreathingExerciseLog': 'inst', 'YogaLog': 'inst', 'MusicTherapyLog': 'inst',
    'Gamification': 'inst', 'CrisisEvent': 'inst',
    'BlogPost': 'blog', 'BlogLike': 'blog', 'BlogComment': 'blog',
}


def bump(namespace):
    """New unique generation. A time-based value stays unique even if the counter key itself is evicted."""
    # max(..., previous + 1): the Windows clock ticks in about 15 ms steps, so two bumps in one tick would share a value
    previous = cache.get(f'gen:{namespace}') or 0
    cache.set(f'gen:{namespace}', max(time.time_ns(), previous + 1), timeout=0)


def generation(namespace):
    gen = cache.get(f'gen:{namespace}')
    if gen is None:
        bump(namespace)
        gen = cache.get(f'gen:{namespace}') or 0
    return gen


def key(namespace, *parts):
    """e.g. key('inst', 'summary', 'campus a') -> 'inst:summary:campus a:g7'. Parts must be shared (non-personal) values."""
    return ':'.join([namespace, *map(str, parts), f'g{generation(namespace)}'])


def cached(namespace, parts, ttl, compute):
    """Return the cached value for (namespace, parts) or compute and store it."""
    k = key(namespace, *parts)
    value = cache.get(k)
    if value is None:
        value = compute()
        cache.set(k, value, timeout=ttl)
    return value


@event.listens_for(Session, 'after_flush')
def _note_watched_writes(session, _ctx):
    hit = session.info.setdefault('cache_ns', set())
    for obj in (*session.new, *session.dirty, *session.deleted):
        ns = _WATCHED.get(type(obj).__name__)
        if ns:
            hit.add(ns)


@event.listens_for(Session, 'after_commit')
def _bump_after_commit(session):
    for ns in session.info.pop('cache_ns', ()):
        try:
            bump(ns)
        except Exception:  # no app context or cache not initialised: never fail a commit over a cache
            pass


@event.listens_for(Session, 'after_rollback')
def _forget_on_rollback(session):
    session.info.pop('cache_ns', None)
