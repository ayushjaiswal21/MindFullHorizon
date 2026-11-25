"""Audit log viewer for institution admins (design 5.4): rows whose actor is staff of the admin's institution.

Patients are never listed as actors, so no student name reaches an admin screen. Date range default 7 days, at most 92.
"""
from datetime import timedelta

from core.extensions import db
from models import AuditLog, User
from services.db_util import inst_match
from services.http import iso
from utils.pagination import page_meta
from utils.timeutil import ist_day_bounds, ist_today

MAX_DAYS = 92
KNOWN_ACTIONS = (
    'view_patient', 'view_patient_meds', 'ack_crisis', 'rx_draft_create', 'rx_draft_delete', 'rx_issue', 'rx_issue_blocked',
    'rx_cancel', 'rx_amend', 'rx_print', 'rx_lookup_desk', 'rx_send_to_desk', 'rx_dispense', 'rx_dispense_reverse',
    'prescriber_submit', 'prescriber_edit_reset', 'prescriber_verify', 'prescriber_reject', 'prescriber_suspend',
    'prescriber_reinstate', 'consult_start', 'consult_complete', 'medicine_create', 'medicine_edit', 'medicine_deactivate',
    'medicine_list_verify', 'stock_receive', 'stock_adjust', 'stock_writeoff', 'stock_import', 'reorder_set',
    'staff_deactivate', 'staff_reactivate', 'view_audit_log', 'export_annual_report', 'export_stock_csv',
    'view_contact_message', 'admin_created', 'admin_pharmacy_desk_set', 'admin_password_set', 'provider_type_set', 'denied')


def staff_options(institution_key):
    """[(id, name)] of providers and admins of the institution, for the actor filter."""
    rows = (User.query.filter(User.role.in_(('provider', 'admin')), inst_match(User.institution, institution_key))
            .order_by(User.name).all())
    return [(u.id, u.name) for u in rows]


def date_range(start, end):
    """(from_date, to_date) as IST dates: default the last 7 days, never more than MAX_DAYS."""
    to = end or ist_today()
    frm = start or to - timedelta(days=6)
    if frm > to:
        frm = to
    return max(frm, to - timedelta(days=MAX_DAYS - 1)), to


def audit_page(institution_key, action=None, actor_id=None, start=None, end=None, page=1, per_page=50):
    frm, to = date_range(start, end)
    lo, hi = ist_day_bounds(frm)[0], ist_day_bounds(to)[1]
    staff = db.session.query(User.id).filter(User.role.in_(('provider', 'admin')), inst_match(User.institution, institution_key))
    q = (db.session.query(AuditLog, User).outerjoin(User, User.id == AuditLog.actor_id)
         .filter(AuditLog.created_at >= lo, AuditLog.created_at < hi, AuditLog.actor_id.in_(staff)))
    if action:
        q = q.filter(AuditLog.action == action)
    if actor_id:
        q = q.filter(AuditLog.actor_id == actor_id)
    total = q.count()
    rows = q.order_by(AuditLog.id.desc()).limit(per_page).offset((page - 1) * per_page).all()
    user_targets = [a.target_id for a, _ in rows if a.target_type == 'user' and a.target_id]
    students = {i for (i,) in db.session.query(User.id).filter(User.id.in_(user_targets or [0]), User.role == 'patient')}
    items = [{'created_at': iso(a.created_at), 'actor_name': u.name if u else None, 'actor_role': u.role if u else None,
              'action': a.action, 'target_type': a.target_type,
              'target_id': None if a.target_id in students else a.target_id,  # no student id on an admin screen
              'meta': {k: v for k, v in (a.meta or {}).items() if k != 'patient_id'} or None}
             for a, u in rows]
    return items, page_meta(page, per_page, total), {'from': frm.isoformat(), 'to': to.isoformat()}
