"""Reversal of a dispense line by the desk (design 4.7): the only kind of "return". Commits.

A patient returning medicine is NOT restocked. This exists to undo a desk error within 24 hours.
"""
from datetime import timedelta

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import InventoryBatch, InventoryTransaction, Prescription, PrescriptionItem
from services.db_util import cas
from services.errors import ServiceError
from services.inventory import _common as inv
from utils.audit import audit
from utils.timeutil import utcnow

WINDOW = timedelta(hours=24)


def reverse(tx_id, actor_id, idem_key, institution_key=None):
    """The new `return` ledger row. Same key again returns it; a second reversal of the same line is 409."""
    key = f'rev:{idem_key}'
    return inv.idempotent(key, lambda: _reverse(tx_id, actor_id, key, institution_key))


def _reverse(tx_id, actor_id, key, institution_key):
    orig = db.session.get(InventoryTransaction, tx_id)
    batch = db.session.get(InventoryBatch, orig.batch_id) if orig else None
    if orig is None or orig.kind != 'dispense' or (institution_key is not None and batch.institution_key != institution_key):
        raise ServiceError('not_found', 404)
    if (orig.prescription_item_id is None or utcnow() - orig.created_at > WINDOW
            or InventoryTransaction.query.filter_by(reverses_id=orig.id).first()):
        raise ServiceError('not_reversible', 409)
    n = -orig.delta
    item = db.session.get(PrescriptionItem, orig.prescription_item_id)
    if cas(PrescriptionItem, (PrescriptionItem.id == item.id, PrescriptionItem.quantity_dispensed >= n),
           quantity_dispensed=PrescriptionItem.quantity_dispensed - n) != 1:
        raise ServiceError('not_reversible', 409)
    inv.bump(batch.id, n)
    tx = inv.post(batch.id, n, 'return', 'dispense_reversed', actor_id, key, prescription_item_id=item.id,
                  rx_number=orig.rx_number, reverses_id=orig.id, group_ref=orig.group_ref)
    taken = db.session.query(func.coalesce(func.sum(PrescriptionItem.quantity_dispensed), 0)).filter(
        PrescriptionItem.prescription_id == item.prescription_id).scalar()
    cas(Prescription, (Prescription.id == item.prescription_id, Prescription.status.in_(('dispensed', 'partially_dispensed'))),
        status='partially_dispensed' if taken else 'issued')
    audit(actor_id, 'rx_dispense_reverse', 'prescription', item.prescription_id, tx_id=orig.id)
    try:
        db.session.commit()
    except IntegrityError:  # UNIQUE(reverses_id): another reversal of this line won
        db.session.rollback()
        raise ServiceError('not_reversible', 409)
    return tx
