"""Admin dashboard figures (design 5.4). Counts only; no student is named. Figures below K are None."""
from datetime import timedelta

from sqlalchemy import func, or_

from core.extensions import db
from models import (AuditLog, ContactMessage, CrisisEvent, InventoryBatch, InventoryTransaction, Prescription, User)
from services import config
from services.db_util import inst_match
from services.http import iso
from services.prescriber import counts as profile_counts, review_due_count
from utils.aggregates import institution_summary_k, patient_ids_query, suppress
from utils.feature_flags import prescriptions_enabled
from utils.timeutil import ist_day_bounds, ist_today, utcnow


def _staff(key):
    staff = User.query.filter(User.role == 'provider', User.deactivated_at.is_(None), inst_match(User.institution, key))
    counsellors = staff.filter(or_(User.provider_type == 'counsellor', User.provider_type.is_(None))).count()
    c = profile_counts(key)
    return {'counsellors': counsellors, 'doctors_verified': c['verified'], 'doctors_pending': c['pending']}


def _summary(institution):
    s = institution_summary_k(institution)
    return dict(s, aggregates_hidden=s['total_users'] is None, total_patients=s['total_users'],
                patient_engagement=s['engagement_rate'])


def _crisis_overdue(institution, k):
    cutoff = utcnow() - timedelta(minutes=config.crisis_escalate_minutes())
    n = CrisisEvent.query.filter(CrisisEvent.acknowledged_at.is_(None), CrisisEvent.created_at < cutoff,
                                 CrisisEvent.user_id.in_(patient_ids_query(institution))).count()
    return {'any': n > 0, 'count': suppress(n, n, k)}  # the count is shown only when K or more alerts stand behind it


def _month_bounds():
    today = ist_today()
    first = today.replace(day=1)
    nxt = (first + timedelta(days=32)).replace(day=1)
    return ist_day_bounds(first)[0], ist_day_bounds(nxt)[0]


def _rx_month(key, k):
    start, end = _month_bounds()
    q = [Prescription.institution_key == key, Prescription.issue_date >= start, Prescription.issue_date < end,
         Prescription.status != 'draft']
    n = db.session.query(func.count(Prescription.id)).filter(*q).scalar() or 0
    people = db.session.query(func.count(func.distinct(Prescription.patient_id))).filter(*q).scalar() or 0
    return suppress(n, people, k)


def _dispensed_today(key):
    start, end = ist_day_bounds()
    return (db.session.query(func.count(func.distinct(InventoryTransaction.group_ref)))
            .join(InventoryBatch, InventoryBatch.id == InventoryTransaction.batch_id)
            .filter(InventoryBatch.institution_key == key, InventoryTransaction.kind == 'dispense',
                    InventoryTransaction.created_at >= start, InventoryTransaction.created_at < end).scalar() or 0)


def _stock(key):
    from services.inventory import alert_counts
    return alert_counts(key)


def build(admin, institution_key):
    """The dashboard dict `d` (design 5.4 widgets). Rx and stock widgets are None-safe when prescriptions are off."""
    k = config.min_group()
    patients = patient_ids_query(admin.institution).count()
    d = {'pending_verifications': profile_counts(institution_key)['pending'], 'staff': _staff(institution_key),
         'patients': {'total': suppress(patients, patients, k)}, 'summary': _summary(admin.institution),
         'crisis_overdue': _crisis_overdue(admin.institution, k),
         'review_due': review_due_count(institution_key, 30),
         'unread_messages': ContactMessage.query.filter(ContactMessage.status != 'read').count(),
         'recent_audit': [{'created_at': iso(r.created_at), 'action': r.action, 'target_type': r.target_type,
                           'target_id': r.target_id}
                          for r in AuditLog.query.filter_by(actor_id=admin.id).order_by(AuditLog.id.desc()).limit(5)]}
    if prescriptions_enabled():
        d.update(stock=_stock(institution_key), rx_month=_rx_month(institution_key, k))
        if admin.is_pharmacy_desk:
            d['dispensed_today'] = _dispensed_today(institution_key)
    return d
