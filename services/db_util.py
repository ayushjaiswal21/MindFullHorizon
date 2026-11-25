"""Small query helpers shared by the services."""
from sqlalchemy import func, update

from core.extensions import db


def inst_match(column, key):
    """SQL predicate: the institution text in `column` equals the normalised institution key (lower and trim)."""
    return func.lower(func.trim(column)) == key


def cas(model, where, **values):
    """Compare-and-set UPDATE. Returns the number of rows changed (0 means the guard in `where` no longer held)."""
    return db.session.execute(update(model).where(*where).values(**values)).rowcount


def for_update(query):
    """Row lock on PostgreSQL; a no-op on SQLite, whose single writer lock plus compare-and-set updates protect us."""
    return query.with_for_update() if db.engine.dialect.name == 'postgresql' else query
