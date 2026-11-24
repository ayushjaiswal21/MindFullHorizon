"""Step 2 of dispensing: confirm a signed plan in one transaction (design 4.6). Commits.

Every write is a compare-and-set, so two desks or a double click can never oversell or dispense twice: the
prescription claim, each item update and each batch update must change exactly one row or the whole thing rolls back.
"""
import hashlib
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import InventoryBatch, InventoryTransaction, Prescription, PrescriptionItem
from services.catalogue import clean
from services.db_util import cas, for_update
from services.dispensing import view
from services.dispensing.plan import plan as make_plan
from services.dispensing.plan import read_token
from services.errors import ServiceError
from services.inventory import _common as inv
from utils.audit import audit
from utils.timeutil import utcnow


def group_of(rx_id, idem_key):
    return hashlib.sha256(f'{rx_id}:{idem_key}'.encode()).hexdigest()[:32]


def stored_result(group, replayed=True):
    """The result of an earlier confirm with this group reference, or None."""
    rows = InventoryTransaction.query.filter_by(group_ref=group, kind='dispense').order_by(InventoryTransaction.id).all()
    if not rows:
        return None
    rx = Prescription.query.filter_by(number=rows[0].rx_number).first()
    return {'replayed': replayed, 'status': rx.status if rx else None, 'group_ref': group,
            'lines': [{'tx_id': r.id, 'item_id': r.prescription_item_id, 'batch_id': r.batch_id, 'quantity': -r.delta}
                      for r in rows]}


def _label(name, reg_no):
    name, reg_no = clean(name, 100), clean(reg_no, 40)
    if not (3 <= len(name) <= 100 and 3 <= len(reg_no) <= 40):
        raise ServiceError('pharmacist_required', 422)
    return f'{name}, Reg. {reg_no}'[:140]


def confirm(rx_id, institution_key, actor_id, token, idem_key, identity_checked, pharmacist_name, pharmacist_reg_no):
    """DispenseResult dict: {replayed, status, group_ref, lines}. A replay (same key) returns the first result."""
    view.get_for_desk(rx_id, institution_key)  # 404 for another institution, before anything else
    if not idem_key:
        raise ServiceError('idempotency_key_required', 400)
    group = group_of(rx_id, idem_key)
    done = stored_result(group)
    if done:
        return done
    if identity_checked is not True:
        raise ServiceError('identity_required', 422)
    label = _label(pharmacist_name, pharmacist_reg_no)
    try:
        result = _apply(rx_id, institution_key, actor_id, token, group, label)
        db.session.commit()
        return result
    except IntegrityError:
        db.session.rollback()
        done = stored_result(group)
        if done:
            return done
        raise
    except ServiceError as err:
        db.session.rollback()
        done = stored_result(group)  # a twin request with the same key won the race
        if done:
            return done
        if err.code == 'plan_stale':
            try:
                err.ctx['plan'] = make_plan(rx_id, institution_key, actor_id)
            except ServiceError:
                err.ctx['plan'] = None
        raise


def _apply(rx_id, institution_key, actor_id, token, group, label):
    data = read_token(token, rx_id, institution_key, actor_id)
    now = utcnow()
    # PostgreSQL row locks in a fixed order (prescription, items by id, batches by id); no-ops on SQLite
    rx = for_update(Prescription.query.filter_by(id=rx_id)).populate_existing().one()
    for_update(PrescriptionItem.query.filter_by(prescription_id=rx_id).order_by(PrescriptionItem.id)).populate_existing().all()
    batch_ids = sorted({b for _, allocs in data['lines'] for b, _ in allocs})
    if batch_ids:
        for_update(InventoryBatch.query.filter(InventoryBatch.id.in_(batch_ids)).order_by(InventoryBatch.id)).all()

    if view.effective_status(rx, now) not in view.DISPENSABLE:
        raise ServiceError('rx_not_dispensable', 409)
    if view.prescriber_blocked(rx):
        raise ServiceError('prescriber_not_verified', 409)
    rv = datetime.fromisoformat(data['rv'])
    claimed = cas(Prescription, (Prescription.id == rx_id, Prescription.institution_key == institution_key,
                                 Prescription.status.in_(view.DISPENSABLE), Prescription.expiry_date > now,
                                 Prescription.updated_at == rv), updated_at=now)
    if claimed != 1:
        raise ServiceError('plan_stale', 409)

    lines = []
    for item_id, allocs in data['lines']:
        n = sum(q for _, q in allocs)
        if n <= 0:
            continue
        if cas(PrescriptionItem, (PrescriptionItem.id == item_id, PrescriptionItem.prescription_id == rx_id,
                                  PrescriptionItem.quantity_dispensed + n <= PrescriptionItem.quantity),
               quantity_dispensed=PrescriptionItem.quantity_dispensed + n) != 1:
            raise ServiceError('plan_stale', 409)
        for batch_id, q in allocs:
            if cas(InventoryBatch, (InventoryBatch.id == batch_id, InventoryBatch.institution_key == institution_key,
                                    InventoryBatch.quantity_on_hand >= q, *inv.usable_clause()),
                   quantity_on_hand=InventoryBatch.quantity_on_hand - q, updated_at=now) != 1:
                raise ServiceError('plan_stale', 409)
            tx = inv.post(batch_id, -q, 'dispense', 'dispense', actor_id, f'{group}:{item_id}:{batch_id}',
                          prescription_item_id=item_id, rx_number=rx.number, group_ref=group, dispenser_label=label)
            lines.append({'tx_id': tx.id, 'item_id': item_id, 'batch_id': batch_id, 'quantity': q})

    open_items = (db.session.query(func.count(PrescriptionItem.id))
                  .filter(PrescriptionItem.prescription_id == rx_id,
                          PrescriptionItem.quantity_dispensed < PrescriptionItem.quantity).scalar())
    status = 'partially_dispensed' if open_items else 'dispensed'
    cas(Prescription, (Prescription.id == rx_id, Prescription.status.in_(view.DISPENSABLE)), status=status)
    audit(actor_id, 'rx_dispense', 'prescription', rx_id, group_ref=group, lines=len(lines))
    return {'replayed': False, 'status': status, 'group_ref': group, 'lines': lines}
