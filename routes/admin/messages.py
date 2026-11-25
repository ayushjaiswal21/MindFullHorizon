"""Contact message inbox for administrators (design 5.4). Messages can hold personal information: every view is audited."""
from flask import g, jsonify, render_template

from core.decorators import admin_required
from core.extensions import db
from models import ContactMessage
from routes.admin import admin_bp
from routes.admin._inv import arg_int
from services.errors import ServiceError
from services.http import iso, service_errors
from utils.audit import audit as write_audit
from utils.pagination import page_args, page_meta


def _row(m, body=False):
    out = {'id': m.id, 'name': m.name, 'subject': m.subject, 'created_at': iso(m.created_at), 'read': m.status == 'read'}
    if body:
        out.update(email=m.email, body=m.message)
    return out


@admin_bp.route('/messages')
@admin_required
def messages():
    page, per_page = page_args()
    q = ContactMessage.query.order_by(ContactMessage.id.desc())
    total = q.count()
    rows = q.limit(per_page).offset((page - 1) * per_page).all()
    selected = db.session.get(ContactMessage, arg_int('id', 0))
    write_audit(g.actor.id, 'view_contact_message', 'contact_message', selected.id if selected else None, n=len(rows))
    db.session.commit()
    return render_template('admin/messages.html', rows=[_row(m) for m in rows],
                           meta=page_meta(page, per_page, total), selected=_row(selected, True) if selected else None)


@admin_bp.route('/api/messages/<int:message_id>/read', methods=['POST'])
@admin_required
@service_errors
def api_message_read(message_id):
    m = db.session.get(ContactMessage, message_id)
    if m is None:
        raise ServiceError('not_found', 404)
    m.status = 'read'
    db.session.commit()
    return jsonify(success=True)
