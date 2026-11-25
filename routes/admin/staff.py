"""Staff list and deactivate/reactivate (design 5.4). Counsellors and doctors only, never a student."""
from flask import g, jsonify, render_template, request

from core.decorators import admin_required
from core.extensions import db
from routes.admin import admin_bp
from routes.admin._inv import inst
from services import staff as staff_svc
from services.http import service_errors
from utils.pagination import page_args


@admin_bp.route('/staff')
@admin_required
def staff():
    ptype = request.args.get('type') if request.args.get('type') in ('counsellor', 'doctor') else None
    status = request.args.get('status') if request.args.get('status') in ('active', 'deactivated') else None
    page, per_page = page_args()
    rows, meta = staff_svc.staff_page(inst(), ptype, status, page, per_page)
    return render_template('admin/staff.html', rows=rows, meta=meta, filters={'type': ptype, 'status': status})


def _toggle(user_id, active):
    staff_svc.set_active(g.actor.id, user_id, active)
    db.session.commit()
    return jsonify(success=True, deactivated=not active)


@admin_bp.route('/api/staff/<int:user_id>/deactivate', methods=['POST'])
@admin_required
@service_errors
def api_staff_deactivate(user_id):
    return _toggle(user_id, False)


@admin_bp.route('/api/staff/<int:user_id>/reactivate', methods=['POST'])
@admin_required
@service_errors
def api_staff_reactivate(user_id):
    return _toggle(user_id, True)
