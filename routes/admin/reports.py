"""Admin: inventory reports and their CSV exports (design 4.11, 5.4).

Any administrator reads. Prescription numbers are masked for administrators without the pharmacy desk flag.
Reports are aggregates over stock and the ledger: no patient names.
"""
from flask import abort, g, jsonify, render_template, request, url_for

from core.decorators import admin_required, prescriptions_required
from core.extensions import db
from routes.admin import admin_bp
from routes.admin._inv import arg_date, arg_int, inst
from routes.admin.catalogue import csv_response
from services import inventory_csv as csvs
from services import reports as rep
from utils.audit import audit
from utils.pagination import page_args

NAMES = ('stock', 'expiring', 'log', 'usage')


def _data(name, paged):
    """(items, meta) of a report from the query string. `paged` False returns every row (CSV)."""
    key = inst()
    if name == 'stock':
        return rep.stock(key), None
    if name == 'expiring':
        return rep.expiring(key, arg_int('days')), None
    if name == 'usage':
        return rep.usage(key, arg_date('from'), arg_date('to')), None
    page, per_page = page_args(default=50) if paged else (1, 100000)
    return rep.log(key, arg_date('from'), arg_date('to'), masked=not g.actor.is_pharmacy_desk, page=page, per_page=per_page)


def _check(name):
    if name not in NAMES:
        abort(404)


@admin_bp.route('/reports')
@prescriptions_required
@admin_required
def reports():
    tab = request.args.get('tab') if request.args.get('tab') in NAMES else 'stock'
    cfg = {'api_template': url_for('admin.api_report', name='stock').replace('stock', '__name__'),
           'csv_template': url_for('admin.report_csv', name='stock').replace('stock', '__name__'), 'names': list(NAMES)}
    return render_template('admin/reports.html', tab=tab, config=cfg, desk=bool(g.actor.is_pharmacy_desk))


@admin_bp.route('/api/reports/<name>')
@prescriptions_required
@admin_required
def api_report(name):
    _check(name)
    items, meta = _data(name, paged=True)
    return jsonify(success=True, items=items, meta=meta, columns=rep.COLUMNS[name])


@admin_bp.route('/reports/<name>.csv')
@prescriptions_required
@admin_required
def report_csv(name):
    _check(name)
    items, _ = _data(name, paged=False)
    audit(g.actor.id, 'export_stock_csv', 'report', None, name=name, rows=len(items))
    db.session.commit()
    return csv_response(csvs.to_csv(rep.COLUMNS[name], items), f'{name}.csv')
