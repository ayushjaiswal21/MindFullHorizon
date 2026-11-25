"""Shared query/scoping helpers for the provider blueprint (institution scoping, risk bands, caching).

Re-exported from `routes.provider` so `from routes.provider import scoped_patient_or_404` (etc.), used
by routes/provider_followups.py, routes/provider_meds.py and some tests, keeps working unchanged.
"""
import os
from datetime import datetime, timedelta

from flask import abort, session
from sqlalchemy import func

from ai.scoring import band_for, canonical_type
from models import (Appointment, Assessment, CrisisEvent, DigitalDetoxLog, ProviderPatient, User,
                     db, get_institutional_summary)
from utils.cache_utils import ANALYTICS_TTL, SUMMARY_TTL, cached
from utils.query_utils import latest_rows
from utils.timeutil import ist_today


def normalize_institution_name(institution_name):
    """Normalize institution name for exact matching."""
    if not institution_name:
        return ''
    return institution_name.lower().strip()


def all_institution_patients():
    """Every patient of the provider's institution. Aggregates and the crisis safety override ONLY, never individual lists."""
    inst = normalize_institution_name(session.get('user_institution'))
    if not inst:
        return User.query.filter(db.false())
    return User.query.filter(User.role == 'patient', func.lower(func.trim(User.institution)) == inst)


def assigned_patients():
    """Patients linked to the logged-in provider by a ProviderPatient row (decision P-02), same institution only."""
    return (all_institution_patients().join(ProviderPatient, ProviderPatient.patient_id == User.id)
            .filter(ProviderPatient.provider_id == session['user_id']))


institution_patients = assigned_patients  # old name, now assignment-scoped so no caller can list the whole institution


def scoped_patient_or_404(patient_id):
    """The patient, if assigned to this provider; else 404 (never 403, so existence does not leak)."""
    patient = assigned_patients().filter(User.id == patient_id).first()
    if patient is None:
        abort(404)
    return patient


def min_group():
    """Minimum cell size K for institution aggregates (env MIN_AGGREGATE_GROUP, default 5)."""
    try:
        return max(1, int(os.getenv('MIN_AGGREGATE_GROUP', '5')))
    except ValueError:
        return 5


def institution_summary(institution):
    """Cached (60 s TTL, bumped by writes to the watched tables, see utils/cache_utils.py). Aggregate only, key = institution."""
    return cached('inst', ('summary', normalize_institution_name(institution), min_group()), SUMMARY_TTL,
                  lambda: _institution_summary(institution))


def _institution_summary(institution):
    """get_institutional_summary with small-cell suppression: a figure drawn from fewer than K people becomes None ('n/a')."""
    k = min_group()
    out = get_institutional_summary(institution, db)
    if (out['total_users'] or 0) < k:
        return {name: None for name in out}
    pids = all_institution_patients().with_entities(User.id)
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


def severity_band(assessment_type, score):
    """Display band ('Moderate', ...) from ai.scoring; None for other types or no score. Old rows hold long titles, hence canonical_type."""
    band = band_for(canonical_type(assessment_type), score)
    return band.capitalize() if band else None


def latest_scores(ids):
    """{user_id: {'PHQ-9': row, 'GAD-7': row}} newest first. One query: the newest row per (user, stored type string),
    then merged by canonical type in Python (old rows carry long titles), so cost is flat in history length."""
    out = {}
    rows = latest_rows(Assessment, Assessment.user_id, (Assessment.created_at.desc(), Assessment.id.desc()), ids,
                       extra_partition=(Assessment.assessment_type,))
    for a in sorted(rows, key=lambda r: (r.created_at, r.id), reverse=True):
        t = canonical_type(a.assessment_type)
        if t:
            out.setdefault(a.user_id, {}).setdefault(t, a)
    return out


def risk_from_band(band):
    return {'Moderate': 'Medium', 'Moderately severe': 'High', 'Severe': 'High'}.get(band, 'Low')


def latest_by_user(model, ids, order_cols, key='user_id', *conditions):
    """{user_id: newest row} in one query (ROW_NUMBER window), so cost does not grow with history length."""
    return {getattr(row, key): row for row in latest_rows(model, getattr(model, key), order_cols, ids, *conditions)}


def unacknowledged_crises():
    """Safety override: open crisis events of the provider's whole institution, not only assigned patients."""
    ids = all_institution_patients().with_entities(User.id)
    return (CrisisEvent.query.filter(CrisisEvent.acknowledged_at.is_(None), CrisisEvent.user_id.in_(ids))
            .order_by(CrisisEvent.created_at.desc()).all())


def can_handle_appointment(appointment):
    """Own appointments, or unassigned requests from this institution (accepting one assigns the patient)."""
    if appointment.provider_id is not None:
        return appointment.provider_id == session['user_id']
    return all_institution_patients().filter(User.id == appointment.user_id).first() is not None
