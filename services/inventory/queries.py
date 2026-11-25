"""Read side of the inventory: FEFO batches, availability, stock levels, alert counts, reconcile (design 4.2, 4.4, 4.10)."""
from datetime import timedelta

from sqlalchemy import and_, case, func

from core.extensions import db
from models import InventoryBatch, InventoryTransaction, Medicine, ReorderRule
from services import config
from services.inventory import _common as c
from utils.pagination import page_meta
from utils.timeutil import ist_today


def usable_batches(institution_key, medicine_id, lock=False):
    """FEFO query: usable batches with stock, earliest expiry first (design 4.2). `lock` takes row locks on PostgreSQL."""
    from services.db_util import for_update
    q = (InventoryBatch.query.filter(InventoryBatch.institution_key == institution_key,
                                     InventoryBatch.medicine_id == medicine_id, InventoryBatch.quantity_on_hand > 0,
                                     *c.usable_clause())
         .order_by(InventoryBatch.expiry_date, InventoryBatch.id))
    return for_update(q) if lock else q


def _per_medicine(institution_key, medicine_ids=None):
    """{medicine_id: (usable, expired_awaiting_writeoff)} summed over batches."""
    today = ist_today()
    usable = case((and_(*c.usable_clause()), InventoryBatch.quantity_on_hand), else_=0)
    expired = case((and_(InventoryBatch.expiry_date <= today, InventoryBatch.status != 'closed'),
                    InventoryBatch.quantity_on_hand), else_=0)
    q = (db.session.query(InventoryBatch.medicine_id, func.sum(usable), func.sum(expired))
         .filter(InventoryBatch.institution_key == institution_key).group_by(InventoryBatch.medicine_id))
    if medicine_ids is not None:
        q = q.filter(InventoryBatch.medicine_id.in_(medicine_ids or [0]))
    return {mid: (int(u or 0), int(e or 0)) for mid, u, e in q}


def _rules(institution_key):
    return {r.medicine_id: r.reorder_level for r in ReorderRule.query.filter_by(institution_key=institution_key)}


def _status(on_hand, level=None, wanted=0):
    if on_hand == 0:
        return 'out'
    if (wanted and on_hand < wanted) or (level is not None and on_hand <= level):
        return 'low'
    return 'in_stock'


def availability(institution_key, requests):
    """{medicine_id: {'status', 'on_hand'}} for (medicine_id, quantity) pairs. Providers get `status` only (route)."""
    wanted = {}
    for mid, qty in requests:
        wanted[mid] = max(wanted.get(mid, 0), qty or 0)
    usable = _per_medicine(institution_key, list(wanted))
    rules = _rules(institution_key)
    out = {}
    for mid, qty in wanted.items():
        on_hand = usable.get(mid, (0, 0))[0]
        out[mid] = {'status': _status(on_hand, rules.get(mid), qty), 'on_hand': on_hand}
    return out


def stock_levels(institution_key, q=None, status=None, page=1, per_page=20):
    """(rows, meta) of StockRow for medicines with a batch or a reorder rule here.

    shortcut: aggregated and paged in Python, fine for a campus formulary; move to SQL if it passes a few thousand medicines.
    """
    agg, rules = _per_medicine(institution_key), _rules(institution_key)
    meds = Medicine.query.filter(Medicine.id.in_(list(set(agg) | set(rules)) or [0]))
    if q:
        like = ' '.join(str(q).split()).lower()[:60]
        meds = meds.filter(Medicine.generic_key.contains(like, autoescape=True)
                           | func.lower(Medicine.brand_name).contains(like, autoescape=True))
    rows = []
    for m in meds.order_by(Medicine.generic_key, Medicine.strength, Medicine.id):
        usable, expired = agg.get(m.id, (0, 0))
        st = _status(usable, rules.get(m.id))
        if status in ('in_stock', 'low', 'out') and st != status:
            continue
        rows.append({'medicine_id': m.id, 'label': m.label, 'usable': usable, 'expired': expired,
                     'reorder_level': rules.get(m.id), 'status': st})
    page_rows = rows[(page - 1) * per_page: page * per_page]
    return page_rows, page_meta(page, per_page, len(rows))


def batches(institution_key, medicine_id=None, page=1, per_page=20):
    """(rows, meta) of BatchRow, soonest expiry first. Closed batches are left out."""
    q = (InventoryBatch.query.join(Medicine, Medicine.id == InventoryBatch.medicine_id)
         .filter(InventoryBatch.institution_key == institution_key, InventoryBatch.status != 'closed'))
    if medicine_id:
        q = q.filter(InventoryBatch.medicine_id == medicine_id)
    total = q.count()
    today = ist_today()
    rows = q.order_by(InventoryBatch.expiry_date, InventoryBatch.id).limit(per_page).offset((page - 1) * per_page).all()
    return [{'id': b.id, 'medicine_id': b.medicine_id, 'label': b.medicine.label, 'batch_no': b.batch_no,
             'expiry_date': b.expiry_date.isoformat(), 'quantity_on_hand': b.quantity_on_hand,
             'supplier': b.supplier, 'status': b.status, 'days_left': (b.expiry_date - today).days}
            for b in rows], page_meta(page, per_page, total)


def alert_counts(institution_key):
    """Counts for the nightly alert and the admin dashboard (design 4.10). Counts only, no names."""
    agg, rules = _per_medicine(institution_key), _rules(institution_key)
    low = out = 0
    for mid, level in rules.items():
        usable = agg.get(mid, (0, 0))[0]
        if usable == 0:
            out += 1
        elif usable <= level:
            low += 1
    today = ist_today()
    near = (InventoryBatch.query.filter(InventoryBatch.institution_key == institution_key,
                                        InventoryBatch.quantity_on_hand > 0, *c.usable_clause(),
                                        InventoryBatch.expiry_date <= today + timedelta(days=config.near_expiry_days()))
            .count())
    waiting = InventoryBatch.query.filter(InventoryBatch.institution_key == institution_key,
                                          InventoryBatch.quantity_on_hand > 0, InventoryBatch.status != 'closed',
                                          InventoryBatch.expiry_date <= today).count()
    return {'low': low, 'out': out, 'near_expiry': near, 'awaiting_writeoff': waiting}


def reconcile(institution_key):
    """Batches whose quantity_on_hand differs from the sum of their ledger deltas. Reports only; never fixes."""
    sums = (db.session.query(InventoryTransaction.batch_id, func.sum(InventoryTransaction.delta))
            .group_by(InventoryTransaction.batch_id).subquery())
    rows = (db.session.query(InventoryBatch.id, InventoryBatch.quantity_on_hand, func.coalesce(sums.c[1], 0))
            .outerjoin(sums, sums.c.batch_id == InventoryBatch.id)
            .filter(InventoryBatch.institution_key == institution_key).all())
    return [{'batch_id': i, 'on_hand': q, 'ledger_sum': int(s)} for i, q, s in rows if q != int(s)]
