"""Receiving, adjusting, writing off and quarantining stock; reorder levels (design 4.5). Pharmacy desk only (routes)."""
from decimal import Decimal, InvalidOperation

from extensions import db
from models import InventoryBatch, Medicine, ReorderRule
from services.catalogue import clean
from services.db_util import cas
from services.errors import ServiceError
from services.inventory import _common as c
from utils.audit import audit
from utils.timeutil import ist_today, utcnow


def _insert_batch_ignore(values):
    """INSERT ... ON CONFLICT DO NOTHING on the batch identity (no SAVEPOINT, see utils/jobs._insert_ignore)."""
    dialect = db.engine.dialect.name
    if dialect == 'postgresql':
        from sqlalchemy.dialects.postgresql import insert
    elif dialect == 'sqlite':
        from sqlalchemy.dialects.sqlite import insert
    else:
        db.session.add(InventoryBatch(**values))
        db.session.flush()
        return
    db.session.execute(insert(InventoryBatch.__table__).values(**values).on_conflict_do_nothing(
        index_elements=['institution_key', 'medicine_id', 'batch_no', 'expiry_date']))


def receive(institution_key, medicine_id, batch_no, expiry_date, quantity, actor_id, idem_key,
            unit_cost=None, supplier=None, reason_code='purchase', audit_row=True):
    """Create the batch or top it up, plus one `receive` ledger row. Replays by `idem_key` return the first row."""
    return c.idempotent(idem_key, lambda: _receive(institution_key, medicine_id, batch_no, expiry_date, quantity,
                                                   actor_id, idem_key, unit_cost, supplier, reason_code, audit_row))


def _receive(institution_key, medicine_id, batch_no, expiry_date, quantity, actor_id, idem_key, unit_cost, supplier,
             reason_code, audit_row):
    med = db.session.get(Medicine, medicine_id) if isinstance(medicine_id, int) else None
    if med is None:
        raise ServiceError('not_found', 404)
    if not med.active:
        raise ServiceError('medicine_inactive', 422)
    if med.is_controlled or med.schedule not in ('none', 'H'):
        raise ServiceError('controlled_not_stocked', 422)
    if reason_code not in c.RECEIVE_REASONS:
        raise ServiceError('bad_reason', 422)
    qty = c.int_field(quantity, 1, 100000, 'quantity')
    batch_no = clean(batch_no, 40)
    if not 1 <= len(batch_no) <= 40:
        raise ServiceError('validation', 422, fields={'batch_no': 'Enter a batch number (up to 40 characters).'})
    expiry = c.date_field(expiry_date, 'expiry_date')
    if expiry <= c.cutoff():
        raise ServiceError('already_expired', 422, fields={'expiry_date': 'Already expired or too close to expiry.'})
    try:
        cost = None if unit_cost in (None, '') else Decimal(str(unit_cost))
        if cost is not None and (not cost.is_finite() or cost < 0 or cost >= Decimal('100000000')):
            raise InvalidOperation
    except InvalidOperation:
        raise ServiceError('validation', 422, fields={'unit_cost': 'Enter an amount of zero or more.'})
    supplier = clean(supplier, 120) or None
    if supplier and len(supplier) > 120:
        raise ServiceError('validation', 422, fields={'supplier': 'Too long.'})

    ident = dict(institution_key=institution_key, medicine_id=medicine_id, batch_no=batch_no, expiry_date=expiry)
    batch = InventoryBatch.query.filter_by(**ident).first()
    if batch is None:
        _insert_batch_ignore(dict(ident, quantity_on_hand=0, unit_cost=cost, supplier=supplier, status='active',
                                  received_at=utcnow(), updated_at=utcnow()))
        batch = InventoryBatch.query.filter_by(**ident).one()
    if not c.bump(batch.id, qty):
        raise ServiceError('conflict', 409)
    tx = c.post(batch.id, qty, 'receive', reason_code, actor_id, idem_key)
    if audit_row:
        audit(actor_id, 'stock_receive', 'inventory_batch', batch.id, delta=qty, reason_code=reason_code)
    return tx


def adjust(batch_id, delta, reason_code, actor_id, idem_key, institution_key=None):
    """Signed correction with a required reason; the result must stay at or above zero."""
    return c.idempotent(idem_key, lambda: _adjust(batch_id, delta, reason_code, actor_id, idem_key, institution_key))


def _adjust(batch_id, delta, reason_code, actor_id, idem_key, institution_key):
    batch = c.get_batch(batch_id, institution_key, lock=True)
    if reason_code not in c.ADJUST_REASONS:
        raise ServiceError('bad_reason', 422)
    n = c.int_field(delta, -100000, 100000, 'delta')
    if n == 0:
        raise ServiceError('validation', 422, fields={'delta': 'Enter a change other than zero.'})
    if batch.status == 'closed':
        raise ServiceError('conflict', 409)
    if not c.bump(batch.id, n):
        raise ServiceError('would_go_negative', 422)
    tx = c.post(batch.id, n, 'adjust', reason_code, actor_id, idem_key)
    audit(actor_id, 'stock_adjust', 'inventory_batch', batch.id, delta=n, reason_code=reason_code)
    return tx


def write_off_expired(batch_id, actor_id, idem_key, institution_key=None):
    """Remove all remaining stock of an expired batch (one `expire` ledger row) and close the batch."""
    return c.idempotent(idem_key, lambda: _write_off(batch_id, actor_id, idem_key, institution_key))


def _write_off(batch_id, actor_id, idem_key, institution_key):
    batch = c.get_batch(batch_id, institution_key, lock=True)
    qty = batch.quantity_on_hand
    if batch.expiry_date > ist_today():
        raise ServiceError('not_expired', 409)
    if qty <= 0:
        raise ServiceError('would_go_negative', 422)
    done = cas(InventoryBatch, (InventoryBatch.id == batch.id, InventoryBatch.quantity_on_hand == qty,
                                InventoryBatch.expiry_date <= ist_today()),
               quantity_on_hand=0, status='closed', updated_at=utcnow())
    if done != 1:
        raise ServiceError('conflict', 409)
    tx = c.post(batch.id, -qty, 'expire', 'expired_writeoff', actor_id, idem_key)
    audit(actor_id, 'stock_writeoff', 'inventory_batch', batch.id, delta=-qty, reason_code='expired_writeoff')
    return tx


def set_quarantine(batch_id, on, actor_id, institution_key=None):
    """Recall handling: a quarantined batch is skipped by allocation. A closed batch cannot change."""
    batch = c.get_batch(batch_id, institution_key, lock=True)
    if batch.status == 'closed':
        raise ServiceError('conflict', 409)
    batch.status = 'quarantined' if on else 'active'
    db.session.flush()
    audit(actor_id, 'stock_adjust', 'inventory_batch', batch.id, quarantine=bool(on), reason_code='recalled')
    return batch


def set_reorder_level(institution_key, medicine_id, level, actor_id):
    if db.session.get(Medicine, medicine_id) is None:
        raise ServiceError('not_found', 404)
    n = c.int_field(level, 0, 1000000, 'reorder_level')
    rule = ReorderRule.query.filter_by(institution_key=institution_key, medicine_id=medicine_id).first()
    if rule is None:
        rule = ReorderRule(institution_key=institution_key, medicine_id=medicine_id, reorder_level=n, updated_by=actor_id)
        db.session.add(rule)
    else:
        rule.reorder_level, rule.updated_by = n, actor_id
    db.session.flush()
    audit(actor_id, 'reorder_set', 'medicine', medicine_id, level=n)
    return rule
