"""CSV templates, import (dry run or all-or-nothing) and safe export for the catalogue and for stock (design 4.9).

Everything is built in memory. Errors name a row number, a field and a code, never the cell text.
"""
import csv
import hashlib
import io

from extensions import db
from models import Medicine
from services import catalogue
from services import inventory as stock
from services.catalogue import clean
from services.errors import ServiceError
from utils.audit import audit
from utils.timeutil import utcnow

CATALOGUE_COLUMNS = ['generic_name', 'brand_name', 'strength', 'form', 'route', 'tpg_list', 'schedule',
                     'therapeutic_class', 'active']
STOCK_COLUMNS = ['generic_name', 'brand_name', 'strength', 'form', 'batch_no', 'expiry_date', 'quantity', 'unit_cost',
                 'supplier']
MAX_ROWS, MAX_BYTES = 2000, 1_000_000
_DANGEROUS = ('=', '+', '-', '@', '\t', '\r')


def safe_cell(value):
    """Spreadsheet formula injection guard: a cell that starts with = + - @ gets a leading single quote."""
    text = '' if value is None else str(value)
    return "'" + text if text.startswith(_DANGEROUS) else text


def to_csv(columns, rows):
    """CSV text of dict rows in column order, every cell escaped with safe_cell."""
    out = io.StringIO()
    w = csv.writer(out, lineterminator='\r\n')
    w.writerow(columns)
    for row in rows:
        w.writerow([safe_cell(row.get(c)) for c in columns])
    return out.getvalue()


def catalogue_template():
    return to_csv(CATALOGUE_COLUMNS, [])


def stock_template():
    return to_csv(STOCK_COLUMNS, [])


def catalogue_export():
    rows = [dict(catalogue.serialize(m), active='true' if m.active else 'false', verified='yes' if m.list_verified_at else 'no')
            for m in Medicine.query.order_by(Medicine.generic_key, Medicine.strength, Medicine.id)]
    return to_csv(CATALOGUE_COLUMNS + ['verified', 'is_demo'], rows)


def parse(data, columns):
    """List of row dicts from uploaded bytes. Header must match exactly; at most 2000 rows and 1 MB."""
    if len(data) > MAX_BYTES:
        raise ServiceError('import_too_large', 413)
    try:
        text = data.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise ServiceError('import_invalid', 422, errors=[{'row': 0, 'field': 'file', 'code': 'not_utf8'}])
    rows = list(csv.reader(io.StringIO(text)))
    if not rows or [h.strip() for h in rows[0]] != columns:
        raise ServiceError('import_invalid', 422, errors=[{'row': 1, 'field': 'header', 'code': 'bad_header'}])
    body = [r for r in rows[1:] if any(cell.strip() for cell in r)]
    if len(body) > MAX_ROWS:
        raise ServiceError('import_too_large', 413)
    return [dict(zip(columns, r + [''] * (len(columns) - len(r)))) for r in body]


def _errors(err, row_no):
    return [{'row': row_no, 'field': f, 'code': err.code} for f in (err.fields or {'row': 1})]


def import_catalogue(admin_id, data, dry_run=True):
    """{'dry_run', 'rows', 'created', 'updated', 'errors'}. A real run with any error raises import_invalid; nothing is
    written. New medicines and any row whose classification changes are left UNVERIFIED: an import cannot make a
    medicine prescribable."""
    rows = parse(data, CATALOGUE_COLUMNS)
    errors, seen, plan = [], set(), []
    for n, raw in enumerate(rows, start=2):
        raw = dict(raw, tpg_list=raw['tpg_list'].strip() or 'C')
        try:
            f = catalogue.normalise(raw)
        except ServiceError as err:
            errors += _errors(err, n)
            continue
        ident = (f['generic_key'], f['brand_name'], f['strength'], f['form'])
        if ident in seen:
            errors.append({'row': n, 'field': 'generic_name', 'code': 'duplicate_row'})
        seen.add(ident)
        plan.append((n, f, ident))
    created = updated = 0
    for _, f, ident in plan:
        existing = Medicine.query.filter_by(generic_key=ident[0], brand_name=ident[1], strength=ident[2], form=ident[3]).first()
        created, updated = (created + 1, updated) if existing is None else (created, updated + 1)
    result = {'dry_run': dry_run, 'rows': len(rows), 'created': created, 'updated': updated, 'errors': errors}
    if errors and not dry_run:
        raise ServiceError('import_invalid', 422, errors=errors, rows=len(rows))
    if dry_run or errors:
        return result
    for _, f, ident in plan:
        m = Medicine.query.filter_by(generic_key=ident[0], brand_name=ident[1], strength=ident[2], form=ident[3]).first()
        if m is None:
            db.session.add(Medicine(**f, is_demo=False, created_by=admin_id, updated_by=admin_id, created_at=utcnow()))
            continue
        if any(getattr(m, k) != f[k] for k in catalogue.CLASS_FIELDS):
            m.list_verified_at = m.list_verified_by = None
            m.updated_by = admin_id
        for k, v in f.items():
            setattr(m, k, v)
    db.session.flush()
    audit(admin_id, 'medicine_create', 'medicine', None, rows=len(rows), via='import')
    return result


def _stock_row(raw, n, institution_key):
    """(medicine, kwargs for receive) or a list of errors for one stock CSV row."""
    key = clean(raw['generic_name'], 120).lower()
    med = Medicine.query.filter_by(generic_key=key, brand_name=clean(raw['brand_name'], 120),
                                   strength=clean(raw['strength'], 40), form=clean(raw['form'], 30)).first()
    if med is None:
        return None, [{'row': n, 'field': 'generic_name', 'code': 'unknown_medicine'}]
    if med.is_controlled or med.schedule not in ('none', 'H'):
        return None, [{'row': n, 'field': 'generic_name', 'code': 'controlled_not_stocked'}]
    return {'medicine_id': med.id, 'batch_no': raw['batch_no'], 'expiry_date': raw['expiry_date'].strip(),
            'quantity': raw['quantity'].strip(), 'unit_cost': raw['unit_cost'].strip() or None,
            'supplier': raw['supplier']}, []


def import_stock(institution_key, actor_id, data, dry_run=True):
    """Receive every row as stock, all or nothing. The same file imported twice is refused (import_duplicate)."""
    rows = parse(data, STOCK_COLUMNS)
    digest = hashlib.sha256(data + institution_key.encode()).hexdigest()[:16]
    if stock._common.existing_tx(f'imp:{digest}:2'):
        raise ServiceError('import_duplicate', 409)
    errors, plan = [], []
    for n, raw in enumerate(rows, start=2):
        kwargs, errs = _stock_row(raw, n, institution_key)
        if errs:
            errors += errs
        else:
            plan.append((n, kwargs))
    result = {'dry_run': dry_run, 'rows': len(rows), 'errors': errors}
    if errors and not dry_run:
        raise ServiceError('import_invalid', 422, errors=errors, rows=len(rows))
    if dry_run or errors:
        # validate quantities and dates through the real service inside a rolled-back transaction
        if not errors:
            errors += _trial(institution_key, actor_id, digest, plan)
            result['errors'] = errors
        return result
    try:
        for n, kw in plan:
            stock.receive(institution_key, actor_id=actor_id, idem_key=f'imp:{digest}:{n}', audit_row=False, **kw)
    except ServiceError as err:
        db.session.rollback()
        raise ServiceError('import_invalid', 422, errors=_errors(err, n), rows=len(rows))
    audit(actor_id, 'stock_import', 'inventory_batch', None, rows=len(rows))
    return result


def _trial(institution_key, actor_id, digest, plan):
    errors = []
    for n, kw in plan:
        try:
            stock.receive(institution_key, actor_id=actor_id, idem_key=f'imp:{digest}:{n}', audit_row=False, **kw)
        except ServiceError as err:
            errors += _errors(err, n)
    db.session.rollback()
    return errors
