"""Aggregate inventory reports (design 4.11). No patient names anywhere. `institution_key` comes from the admin's row."""
from datetime import timedelta, timezone

from sqlalchemy import case, func

from extensions import db
from models import InventoryBatch, InventoryTransaction, Medicine, Prescription, PrescriptionItem
from services import config
from services.inventory import stock_levels
from utils.pagination import page_meta
from utils.rx_numbers import mask_rx
from utils.timeutil import IST, ist_day_bounds, ist_today

MAX_RANGE_DAYS = 92
COLUMNS = {
    'stock': ['label', 'usable', 'expired', 'reorder_level', 'status'],
    'expiring': ['label', 'batch_no', 'expiry_date', 'quantity', 'days_left'],
    'log': ['time_ist', 'kind', 'rx_number', 'label', 'batch_no', 'delta', 'dispenser_label', 'reason_code'],
    'usage': ['label', 'units', 'prescriptions', 'suppressed'],
}


def date_range(start=None, end=None, default_days=7):
    """(start, end) IST dates, inclusive, at most MAX_RANGE_DAYS long. Bad input falls back to the default."""
    end = end or ist_today()
    start = start or end - timedelta(days=default_days - 1)
    if end < start:
        start, end = end, start
    return max(start, end - timedelta(days=MAX_RANGE_DAYS - 1)), end


def _bounds(start, end):
    return ist_day_bounds(start)[0], ist_day_bounds(end)[1]


def stock(institution_key):
    rows, _ = stock_levels(institution_key, page=1, per_page=100000)
    return rows


def expiring(institution_key, days=None):
    """Batches with stock that expire within `days` (default 60, 1 to 365), already expired ones first."""
    days = max(1, min(365, days or config.near_expiry_days()))
    today = ist_today()
    rows = (InventoryBatch.query.filter(InventoryBatch.institution_key == institution_key, InventoryBatch.quantity_on_hand > 0,
                                        InventoryBatch.status != 'closed', InventoryBatch.expiry_date <= today + timedelta(days=days))
            .order_by(InventoryBatch.expiry_date, InventoryBatch.id).all())
    return [{'label': b.medicine.label, 'batch_no': b.batch_no, 'expiry_date': b.expiry_date.isoformat(),
             'quantity': b.quantity_on_hand, 'days_left': (b.expiry_date - today).days} for b in rows]


def _ist_text(naive_utc):
    return naive_utc.replace(tzinfo=timezone.utc).astimezone(IST).strftime('%Y-%m-%d %H:%M')


def log(institution_key, start=None, end=None, masked=True, page=1, per_page=50):
    """(rows, meta) of ledger lines in an IST date range, newest first. Base admins get a masked prescription number
    and no dispenser label; the pharmacy desk gets both."""
    start, end = date_range(start, end)
    lo, hi = _bounds(start, end)
    q = (db.session.query(InventoryTransaction, InventoryBatch, Medicine)
         .join(InventoryBatch, InventoryBatch.id == InventoryTransaction.batch_id)
         .join(Medicine, Medicine.id == InventoryBatch.medicine_id)
         .filter(InventoryBatch.institution_key == institution_key, InventoryTransaction.created_at >= lo,
                 InventoryTransaction.created_at < hi))
    total = q.count()
    rows = q.order_by(InventoryTransaction.created_at.desc(), InventoryTransaction.id.desc()).limit(per_page).offset((page - 1) * per_page).all()
    out = [{'time': t.created_at.isoformat() + 'Z', 'time_ist': _ist_text(t.created_at), 'kind': t.kind,
            'rx_number': mask_rx(t.rx_number) if masked else t.rx_number, 'label': m.label, 'batch_no': b.batch_no,
            'delta': t.delta, 'dispenser_label': None if masked else t.dispenser_label, 'reason_code': t.reason_code}
           for t, b, m in rows]
    return out, dict(page_meta(page, per_page, total), start=start.isoformat(), end=end.isoformat())


def usage(institution_key, start=None, end=None, k=None):
    """Units dispensed per medicine (dispenses minus reversals). A medicine given to fewer than K distinct patients
    shows units and prescriptions as None with suppressed=True."""
    k = k or config.min_group()
    today = ist_today()
    start, end = start or today.replace(day=1), end or today
    lo, hi = _bounds(start, end)
    kinds = ('dispense', 'return')
    agg = (db.session.query(InventoryBatch.medicine_id, func.sum(-InventoryTransaction.delta),
                            func.count(func.distinct(case((InventoryTransaction.kind == 'dispense', InventoryTransaction.rx_number)))),
                            func.count(func.distinct(Prescription.patient_id)))
           .select_from(InventoryTransaction)
           .join(InventoryBatch, InventoryBatch.id == InventoryTransaction.batch_id)
           .outerjoin(PrescriptionItem, PrescriptionItem.id == InventoryTransaction.prescription_item_id)
           .outerjoin(Prescription, Prescription.id == PrescriptionItem.prescription_id)
           .filter(InventoryBatch.institution_key == institution_key, InventoryTransaction.kind.in_(kinds),
                   InventoryTransaction.created_at >= lo, InventoryTransaction.created_at < hi)
           .group_by(InventoryBatch.medicine_id).all())
    labels = {m.id: m.label for m in Medicine.query.filter(Medicine.id.in_([a[0] for a in agg] or [0]))}
    rows = []
    for mid, units, rxs, patients in sorted(agg, key=lambda a: labels.get(a[0], '')):
        hidden = patients < k
        rows.append({'medicine_id': mid, 'label': labels.get(mid), 'units': None if hidden else int(units or 0),
                     'prescriptions': None if hidden else rxs, 'suppressed': hidden})
    return rows
