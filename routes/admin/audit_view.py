"""Audit log viewer (design 5.4). Staff actions of the admin's institution; the view itself is audited."""
from flask import g, jsonify, render_template, request

from core.decorators import admin_required
from core.extensions import db
from routes.admin import admin_bp
from routes.admin._inv import arg_date, arg_int, inst
from services import audit_view
from utils.audit import audit as write_audit
from utils.pagination import page_args


def _query():
    page, per_page = page_args(default=50)
    action = request.args.get('action') if request.args.get('action') in audit_view.KNOWN_ACTIONS else None
    actor = arg_int('actor')
    rows, meta, rng = audit_view.audit_page(inst(), action, actor, arg_date('from'), arg_date('to'), page, per_page)
    write_audit(g.actor.id, 'view_audit_log', 'audit_log', None, n=len(rows))
    db.session.commit()
    return rows, meta, {'action': action, 'actor': actor, **rng}


@admin_bp.route('/audit')
@admin_required
def audit():
    rows, meta, filters = _query()
    return render_template('admin/audit.html', rows=rows, meta=meta, filters=filters, actions=audit_view.KNOWN_ACTIONS,
                           staff=audit_view.staff_options(inst()))


@admin_bp.route('/api/audit')
@admin_required
def api_audit():
    rows, meta, filters = _query()
    return jsonify(success=True, items=rows, meta=meta, range={'from': filters['from'], 'to': filters['to']})
