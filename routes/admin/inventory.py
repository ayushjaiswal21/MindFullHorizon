"""Admin: stock levels, batches, receiving, adjustments, reorder levels, CSV (design 4.5, 4.9, 5.4).

Any administrator reads; writes need the pharmacy desk flag. Every write takes an Idempotency-Key header.
The institution always comes from the logged-in admin's row.
"""
from flask import g, jsonify, render_template, request, url_for

from core.decorators import admin_required, pharmacy_desk_required, prescriptions_required
from core.extensions import db, limiter
from routes.admin import admin_bp
from routes.admin._inv import arg_int, inst, tx_json
from routes.admin.catalogue import csv_response, read_upload
from services import inventory as stock
from services import inventory_csv as csvs
from services.http import idem_key, json_body, service_errors
from utils.audit import audit
from utils.pagination import page_args

REASONS = [{'code': 'count_correction', 'label': 'Count correction'}, {'code': 'damaged', 'label': 'Damaged'},
           {'code': 'lost', 'label': 'Lost'}, {'code': 'recalled', 'label': 'Recalled'}]
RECEIVE_REASONS = [{'code': 'purchase', 'label': 'Purchase'}, {'code': 'donation', 'label': 'Donation'},
                   {'code': 'transfer_in', 'label': 'Transfer in'}, {'code': 'opening_stock', 'label': 'Opening stock'}]


def _config():
    return {'stock': url_for('admin.api_stock'), 'batches': url_for('admin.api_batches'),
            'receive': url_for('admin.api_receive'), 'import': url_for('admin.api_stock_import'),
            'export': url_for('admin.stock_csv'), 'template': url_for('admin.stock_template'),
            'reorder_template': url_for('admin.api_reorder', medicine_id=0),
            'adjust_template': url_for('admin.api_adjust', batch_id=0),
            'writeoff_template': url_for('admin.api_writeoff', batch_id=0),
            'quarantine_template': url_for('admin.api_quarantine', batch_id=0),
            'catalogue_search': url_for('admin.api_catalogue_list')}


def _ctx(**extra):
    return dict(desk=bool(g.actor.is_pharmacy_desk), reasons=REASONS, receive_reasons=RECEIVE_REASONS, config=_config(),
                stats=stock.alert_counts(inst()), **extra)


@admin_bp.route('/inventory')
@prescriptions_required
@admin_required
def inventory():
    page, per_page = page_args()
    rows, meta = stock.stock_levels(inst(), request.args.get('q'), request.args.get('status'), page, per_page)
    return render_template('admin/inventory.html', **_ctx(rows=rows, meta=meta))


@admin_bp.route('/inventory/batches')
@prescriptions_required
@admin_required
def batches():
    page, per_page = page_args()
    rows, meta = stock.batches(inst(), arg_int('medicine_id'), page, per_page)
    return render_template('admin/batches.html', **_ctx(rows=rows, meta=meta))


@admin_bp.route('/inventory/receive')
@prescriptions_required
@pharmacy_desk_required
def receive():
    return render_template('admin/receive.html', **_ctx(rows=[], meta=None))


@admin_bp.route('/api/inventory/stock')
@prescriptions_required
@admin_required
def api_stock():
    page, per_page = page_args()
    rows, meta = stock.stock_levels(inst(), request.args.get('q'), request.args.get('status'), page, per_page)
    return jsonify(success=True, items=rows, meta=meta, stats=stock.alert_counts(inst()))


@admin_bp.route('/api/inventory/batches')
@prescriptions_required
@admin_required
def api_batches():
    page, per_page = page_args()
    rows, meta = stock.batches(inst(), arg_int('medicine_id'), page, per_page)
    return jsonify(success=True, items=rows, meta=meta)


@admin_bp.route('/api/inventory/receive', methods=['POST'])
@prescriptions_required
@pharmacy_desk_required
@service_errors
def api_receive():
    b = json_body()
    tx = stock.receive(inst(), b.get('medicine_id'), b.get('batch_no'), b.get('expiry_date'), b.get('quantity'),
                       g.actor.id, idem_key(), unit_cost=b.get('unit_cost'), supplier=b.get('supplier'),
                       reason_code=b.get('reason_code') or 'purchase')
    db.session.commit()
    return jsonify(success=True, transaction=tx_json(tx)), 201


@admin_bp.route('/api/inventory/batches/<int:batch_id>/adjust', methods=['POST'])
@prescriptions_required
@pharmacy_desk_required
@service_errors
def api_adjust(batch_id):
    b = json_body()
    tx = stock.adjust(batch_id, b.get('delta'), b.get('reason_code'), g.actor.id, idem_key(), institution_key=inst())
    db.session.commit()
    return jsonify(success=True, transaction=tx_json(tx))


@admin_bp.route('/api/inventory/batches/<int:batch_id>/write-off', methods=['POST'])
@prescriptions_required
@pharmacy_desk_required
@service_errors
def api_writeoff(batch_id):
    tx = stock.write_off_expired(batch_id, g.actor.id, idem_key(), institution_key=inst())
    db.session.commit()
    return jsonify(success=True, transaction=tx_json(tx))


@admin_bp.route('/api/inventory/batches/<int:batch_id>/quarantine', methods=['POST'])
@prescriptions_required
@pharmacy_desk_required
@service_errors
def api_quarantine(batch_id):
    batch = stock.set_quarantine(batch_id, json_body().get('on') is True, g.actor.id, institution_key=inst())
    db.session.commit()
    return jsonify(success=True, status=batch.status)


@admin_bp.route('/api/inventory/reorder/<int:medicine_id>', methods=['PUT'])
@prescriptions_required
@pharmacy_desk_required
@service_errors
def api_reorder(medicine_id):
    rule = stock.set_reorder_level(inst(), medicine_id, json_body().get('reorder_level'), g.actor.id)
    db.session.commit()
    return jsonify(success=True, medicine_id=medicine_id, reorder_level=rule.reorder_level)


@admin_bp.route('/api/inventory/import', methods=['POST'])
@limiter.limit('10 per hour')
@prescriptions_required
@pharmacy_desk_required
@service_errors
def api_stock_import():
    dry = request.form.get('dry_run', '1') not in ('0', 'false', 'no')
    result = csvs.import_stock(inst(), g.actor.id, read_upload(), dry_run=dry)
    db.session.rollback() if dry else db.session.commit()
    return jsonify(success=not result['errors'], **result), (200 if not result['errors'] else 422)


@admin_bp.route('/inventory/stock.csv')
@prescriptions_required
@admin_required
def stock_csv():
    from services import reports
    rows = reports.stock(inst())
    audit(g.actor.id, 'export_stock_csv', 'inventory_batch', None, rows=len(rows))
    db.session.commit()
    return csv_response(csvs.to_csv(reports.COLUMNS['stock'], rows), 'stock.csv')


@admin_bp.route('/inventory/template.csv')
@prescriptions_required
@admin_required
def stock_template():
    return csv_response(csvs.stock_template(), 'stock_template.csv')
