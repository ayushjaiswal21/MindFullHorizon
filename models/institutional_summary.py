"""Cross-domain institutional aggregate query, split out of the old flat models.py."""
from datetime import date, datetime, timedelta
from sqlalchemy import case, func, select, union
from extensions import db
from utils.timeutil import ist_today

from .user import User
from .clinical_core import Appointment
from .wellness_logs import Assessment, DigitalDetoxLog, BreathingExerciseLog, MusicTherapyLog, YogaLog
from .clinical_core import MedicationLog

__all__ = ["get_institutional_summary"]


def get_institutional_summary(institution, db=db, days_active=7, days_risk=7, days_assessments=30):
    """Aggregate stats for the patients of ONE institution (case-insensitive exact match).

    Everything is a SQL aggregate. A metric that cannot be computed from stored data is None
    (never a made-up number): avg_session_duration and satisfaction_score are not stored at all.
    """
    name = (institution or '').strip().lower()
    out = {'total_users': 0, 'active_users': 0, 'avg_screen_time': None, 'high_risk_users': 0,
           'engagement_rate': None, 'avg_wellness_score': None, 'avg_session_duration': None,
           'completion_rate': None, 'satisfaction_score': None}
    if not name:
        return out
    s = db.session
    pids = select(User.id).where(User.role == 'patient', func.lower(func.trim(User.institution)) == name)
    total = s.scalar(select(func.count()).select_from(pids.subquery()))
    if not total:
        return out

    now = datetime.utcnow()  # created_at/taken_at columns are stored as naive UTC
    since = lambda days: now - timedelta(days=days)
    active_from, risk_from = since(days_active), since(days_risk)
    active = union(*(
        select(col).where(col.in_(pids), when >= (ist_today() - timedelta(days=days_active) if when.type.python_type is date else active_from))
        for col, when in (
            (DigitalDetoxLog.user_id, DigitalDetoxLog.date), (Assessment.user_id, Assessment.created_at),
            (MedicationLog.user_id, MedicationLog.taken_at), (BreathingExerciseLog.user_id, BreathingExerciseLog.created_at),
            (YogaLog.user_id, YogaLog.created_at), (MusicTherapyLog.user_id, MusicTherapyLog.created_at),
        )))
    active_users = s.scalar(select(func.count()).select_from(active.subquery()))

    screen = (select(DigitalDetoxLog.user_id, func.avg(DigitalDetoxLog.screen_time_hours).label('avg'))
              .where(DigitalDetoxLog.user_id.in_(pids), DigitalDetoxLog.date >= ist_today() - timedelta(days=days_risk))
              .group_by(DigitalDetoxLog.user_id).subquery())
    avg_screen, high_risk = s.execute(select(
        func.avg(screen.c.avg), func.coalesce(func.sum(case((screen.c.avg > 8, 1), else_=0)), 0))).one()

    # lower GAD-7/PHQ-9 score = better; scale to 0-10. Daily Mood is stored 1-10 already (no scaling).
    wellness = case(
        (Assessment.assessment_type == 'GAD-7', (1 - Assessment.score / 21.0) * 10),
        (Assessment.assessment_type == 'PHQ-9', (1 - Assessment.score / 27.0) * 10),
        (Assessment.assessment_type == 'Daily Mood', Assessment.score * 1.0))
    avg_wellness = s.scalar(select(func.avg(wellness)).where(
        Assessment.user_id.in_(pids), Assessment.created_at >= since(days_assessments)))

    # completion = completed / (completed + cancelled) over the active window, patients' own appointments
    done, cancelled = s.execute(select(
        func.coalesce(func.sum(case((Appointment.status == 'completed', 1), else_=0)), 0),
        func.coalesce(func.sum(case((Appointment.status == 'cancelled', 1), else_=0)), 0),
    ).where(Appointment.user_id.in_(pids), Appointment.date >= ist_today() - timedelta(days=days_active))).one()

    out.update(
        total_users=total, active_users=active_users,
        engagement_rate=round(active_users / total * 100, 1),
        avg_screen_time=None if avg_screen is None else round(avg_screen, 1),
        high_risk_users=int(high_risk or 0),
        avg_wellness_score=None if avg_wellness is None else round(avg_wellness, 1),
        completion_rate=round(done / (done + cancelled) * 100, 1) if done + cancelled else None)
    return out
