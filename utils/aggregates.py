"""Institution aggregates with small-cell suppression (minimum group size K). Used by the admin dashboard and report.

The same rules as `routes/provider.py::institution_summary`, kept here so admin code does not import a route module.
A figure drawn from fewer than K people is None ("n/a").
"""
import os
from datetime import datetime, timedelta

from sqlalchemy import func

from core.extensions import db
from models import (Appointment, Assessment, DigitalDetoxLog, User, get_institutional_summary)
from utils.timeutil import ist_today


def normalize_institution_name(name):
    return (name or '').lower().strip()


def min_group():
    """K, from MIN_AGGREGATE_GROUP (default 5). Bad values fall back to 5."""
    try:
        return max(1, int(os.getenv('MIN_AGGREGATE_GROUP', '5')))
    except ValueError:
        return 5


def patient_ids_query(institution):
    """Subquery-able select of the patient ids of one institution (case-insensitive exact match)."""
    key = normalize_institution_name(institution)
    return db.session.query(User.id).filter(User.role == 'patient', func.lower(func.trim(User.institution)) == key)


def institution_summary_k(institution):
    k = min_group()
    out = get_institutional_summary(institution, db)
    if (out['total_users'] or 0) < k:
        return {name: None for name in out}
    pids = patient_ids_query(institution)
    since = ist_today() - timedelta(days=7)
    detox_n = db.session.query(func.count(func.distinct(DigitalDetoxLog.user_id))).filter(
        DigitalDetoxLog.user_id.in_(pids), DigitalDetoxLog.date >= since).scalar() or 0
    asmt_n = db.session.query(func.count(func.distinct(Assessment.user_id))).filter(
        Assessment.user_id.in_(pids), Assessment.created_at >= datetime.utcnow() - timedelta(days=30)).scalar() or 0
    if (out['active_users'] or 0) < k:
        out['active_users'] = out['engagement_rate'] = None
    if detox_n < k:
        out['avg_screen_time'] = out['high_risk_users'] = None
    elif 0 < (out['high_risk_users'] or 0) < k:
        out['high_risk_users'] = None
    if asmt_n < k:
        out['avg_wellness_score'] = None
    if (out['completion_rate'] is not None and
            Appointment.query.filter(Appointment.user_id.in_(pids), Appointment.status.in_(('completed', 'cancelled')),
                                     Appointment.date >= since).count() < k):
        out['completion_rate'] = None
    return out


def suppress(value, distinct_people, k=None):
    """`value` when at least K distinct people stand behind it, else None."""
    return value if distinct_people >= (k or min_group()) else None
