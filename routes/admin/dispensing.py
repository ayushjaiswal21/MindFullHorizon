"""Admin: pharmacy desk dispensing (design 4.6, 4.7, 5.4). Every route needs the pharmacy desk flag.

The desk reaches a prescription only through the queue of prescriptions the patient sent, or by typing its number.
There is no list of all prescriptions, and an id in the URL opens only a queued or just looked-up prescription.
"""
from flask import abort, g, jsonify, render_template, url_for

from core.decorators import pharmacy_desk_required, prescriptions_required
from core.extensions import db, limiter
from routes.admin import admin_bp
from routes.admin._inv import inst, may_open, page_errors, remember_rx, tx_json
from services import dispensing as svc
from services.dispensing import view
from services.http import idem_key, json_body, service_errors
from utils.audit import audit
from utils.seo import site_url
from utils.timeutil import utcnow


def _config(rx_id=None):
    cfg = {'queue': url_for('admin.api_queue'), 'lookup': url_for('admin.api_lookup'),
           'detail_template': url_for('admin.dispensing_detail', rx_id=0),
           'reverse_template': url_for('admin.api_reverse', tx_id=0)}
    if rx_id:
        cfg.update(prepare=url_for('admin.api_prepare', rx_id=rx_id), confirm=url_for('admin.api_confirm', rx_id=rx_id),
                   print=url_for('admin.dispensing_print', rx_id=rx_id))
    return cfg


def _open(rx_id):
    """The prescription the desk may open, or 404. Audits one `rx_lookup_desk` row per open."""
    rx = view.get_for_desk(rx_id, inst())
    if not may_open(rx):
        abort(404)
    return rx


@admin_bp.route('/dispensing')
@prescriptions_required
@pharmacy_desk_required
def dispensing():
    return render_template('admin/dispensing.html', queue=svc.queue(inst()), rx=None, config=_config())


@admin_bp.route('/dispensing/<int:rx_id>')
@prescriptions_required
@pharmacy_desk_required
@page_errors
def dispensing_detail(rx_id):
    rx = _open(rx_id)
    audit(g.actor.id, 'rx_lookup_desk', 'prescription', rx.id, via='queue' if view.in_queue(rx) else 'number')
    db.session.commit()
    return render_template('admin/dispensing_detail.html', queue=[], rx=svc.rx_view(rx), config=_config(rx.id))


@admin_bp.route('/dispensing/<int:rx_id>/print')
@prescriptions_required
@pharmacy_desk_required
@page_errors
def dispensing_print(rx_id):
    rx = _open(rx_id)
    audit(g.actor.id, 'rx_print', 'prescription', rx.id, by='desk')
    db.session.commit()
    try:
        from services.prescriptions import serialize
        data = serialize(rx, 'desk')
    except (ImportError, TypeError):
        data = svc.rx_view(rx)
    return render_template('provider_rx/print.html', rx=data, site_url=site_url(), printed_at=utcnow())



@admin_bp.route('/api/dispensing/queue')
@prescriptions_required
@pharmacy_desk_required
def api_queue():
    return jsonify(success=True, items=svc.queue(inst()))


@admin_bp.route('/api/dispensing/lookup', methods=['POST'])
@limiter.limit('30 per minute')
@prescriptions_required
@pharmacy_desk_required
@service_errors
def api_lookup():
    rx = svc.lookup(json_body().get('number'), inst())
    remember_rx(rx.id)
    audit(g.actor.id, 'rx_lookup_desk', 'prescription', rx.id, via='number')
    db.session.commit()
    return jsonify(success=True, rx_id=rx.id)


@admin_bp.route('/api/dispensing/<int:rx_id>/prepare', methods=['POST'])
@prescriptions_required
@pharmacy_desk_required
@service_errors
def api_prepare(rx_id):
    _open(rx_id)
    lines = json_body().get('lines')
    return jsonify(success=True, **svc.plan(rx_id, inst(), g.actor.id, lines=lines if isinstance(lines, list) else None))


@admin_bp.route('/api/dispensing/<int:rx_id>/confirm', methods=['POST'])
@prescriptions_required
@pharmacy_desk_required
@service_errors
def api_confirm(rx_id):
    b = json_body()  # the signed plan token proves the desk opened this prescription in prepare
    key = idem_key()
    result = svc.confirm(rx_id, inst(), g.actor.id, b.get('token'), key, b.get('identity_checked'),
                                b.get('pharmacist_name'), b.get('pharmacist_reg_no'))
    return jsonify(success=True, **result)


@admin_bp.route('/api/dispensing/transactions/<int:tx_id>/reverse', methods=['POST'])
@prescriptions_required
@pharmacy_desk_required
@service_errors
def api_reverse(tx_id):
    tx = svc.reverse(tx_id, g.actor.id, idem_key(), institution_key=inst())
    return jsonify(success=True, transaction=tx_json(tx))
