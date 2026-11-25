"""Shared pieces of the inventory services: usable-stock predicate, ledger posting, idempotent replay (design 4.2, 4.3)."""
from datetime import date, timedelta

from sqlalchemy.exc import IntegrityError

from core.extensions import db
from models import InventoryBatch, InventoryTransaction
from services import config
from services.db_util import cas, for_update
from services.errors import ServiceError
from utils.timeutil import ist_today, utcnow

RECEIVE_REASONS = ('purchase', 'donation', 'transfer_in', 'opening_stock')
ADJUST_REASONS = ('count_correction', 'damaged', 'lost', 'recalled')


def cutoff():
    """A batch is usable only when its expiry date is AFTER this date (today plus the minimum shelf life)."""
    return ist_today() + timedelta(days=config.min_shelf_days())


def usable_clause():
    return (InventoryBatch.status == 'active', InventoryBatch.expiry_date > cutoff())


def int_field(value, low, high, field):
    try:
        n = int(value)
        if isinstance(value, bool) or not low <= n <= high:
            raise ValueError
        return n
    except (TypeError, ValueError):
        raise ServiceError('validation', 422, fields={field: f'Enter a whole number from {low} to {high}.'})


def date_field(value, field):
    """ISO date (YYYY-MM-DD) or a date object. Month-only dates are ambiguous and rejected."""
    if isinstance(value, date):
        return value
    try:
        if not isinstance(value, str) or len(value.strip()) != 10:
            raise ValueError
        return date.fromisoformat(value.strip())
    except ValueError:
        raise ServiceError('validation', 422, fields={field: 'Use the date format YYYY-MM-DD.'})


def get_batch(batch_id, institution_key=None, lock=False):
    q = InventoryBatch.query.filter_by(id=batch_id)
    batch = (for_update(q) if lock else q).populate_existing().first()
    if batch is None or (institution_key is not None and batch.institution_key != institution_key):
        raise ServiceError('not_found', 404)
    return batch


def existing_tx(idem_key):
    return InventoryTransaction.query.filter_by(idempotency_key=idem_key).first()


def idempotent(idem_key, work):
    """Run `work()` once per idempotency key. A replay (or a concurrent twin that lost the unique-key race) returns the
    first ledger row instead of doing the work again."""
    if not idem_key:
        raise ServiceError('idempotency_key_required', 400)
    prior = existing_tx(idem_key)
    if prior:
        return prior
    try:
        return work()
    except IntegrityError:
        db.session.rollback()
        prior = existing_tx(idem_key)
        if prior:
            return prior
        raise


def bump(batch_id, delta):
    """Compare-and-set change of quantity_on_hand that can never go below zero. False when the guard failed."""
    return cas(InventoryBatch, (InventoryBatch.id == batch_id, InventoryBatch.quantity_on_hand + delta >= 0),
               quantity_on_hand=InventoryBatch.quantity_on_hand + delta, updated_at=utcnow()) == 1


def post(batch_id, delta, kind, reason, actor_id, idem_key, **extra):
    """Append one ledger row (flushed, not committed)."""
    tx = InventoryTransaction(batch_id=batch_id, delta=delta, kind=kind, reason_code=reason, actor_id=actor_id,
                              idempotency_key=idem_key, created_at=utcnow(), **extra)
    db.session.add(tx)
    db.session.flush()
    return tx
