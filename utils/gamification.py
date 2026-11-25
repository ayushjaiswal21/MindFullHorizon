import logging
import uuid
from datetime import timedelta

from sqlalchemy import case, func, select, update
from sqlalchemy.exc import IntegrityError

from models import Gamification, PointsLedger
from core.extensions import db
from utils.timeutil import ist_day_bounds, ist_today

logger = logging.getLogger(__name__)

DAILY_CAP = 3  # max point awards per activity type per IST day
# Never gamify assessments or mood scores (docs/SAFETY_RESEARCH.md).
NO_POINTS = {'assessment', 'mood'}
ACTIVITY_TYPES = {'log_medication', 'breathing_exercise', 'yoga_session', 'digital_detox_log', 'journal_entry', 'voice_log',
                  'goal_progress', 'visit', 'grounding_exercise'}
VISIT_POINTS = 5  # once per IST day, whatever the person does; unrelated to any score (docs/GAMIFICATION.md)


def _ensure_row(user_id):
    """Create the user's Gamification row if missing; safe when two requests race (unique user_id)."""
    if db.session.scalar(select(Gamification.id).where(Gamification.user_id == user_id)) is None:
        try:
            db.session.add(Gamification(user_id=user_id, points=0, streak=0))
            db.session.commit()
        except IntegrityError:
            db.session.rollback()


def award_points(user_id, points, activity_type, ref=None):
    """Award points and update the streak, then commit. Call after the activity row is committed.

    `ref` names the activity ('medlog:12'); UNIQUE(user_id, ref) in points_ledger makes a replay award nothing.
    No points for NO_POINTS or unknown types; at most DAILY_CAP paid awards per type per IST day (best effort
    under true concurrency on PostgreSQL: the ledger row, not the cap, is the hard guarantee).
    Points and streak change in single UPDATE statements, so concurrent requests cannot lose an update.
    """
    if activity_type in NO_POINTS or activity_type not in ACTIVITY_TYPES:
        return Gamification.query.filter_by(user_id=user_id).first() or Gamification(user_id=user_id, points=0, streak=0)
    ref = ref or f'{activity_type}:{uuid.uuid4().hex}'
    try:
        _ensure_row(user_id)
        start, end = ist_day_bounds()
        paid_today = db.session.scalar(select(func.count()).select_from(PointsLedger).where(
            PointsLedger.user_id == user_id, PointsLedger.activity_type == activity_type,
            PointsLedger.points > 0, PointsLedger.created_at >= start, PointsLedger.created_at < end))
        awarded = points if paid_today < DAILY_CAP else 0
        try:
            db.session.add(PointsLedger(user_id=user_id, ref=ref, activity_type=activity_type, points=awarded))
            db.session.flush()
        except IntegrityError:  # this activity was already awarded: replay, change nothing
            db.session.rollback()
            return Gamification.query.filter_by(user_id=user_id).first()
        if awarded:
            db.session.execute(update(Gamification).where(Gamification.user_id == user_id)
                               .values(points=func.coalesce(Gamification.points, 0) + awarded))
        # streak: one compare-and-set per IST day; the second concurrent writer matches no row
        today = ist_today()
        db.session.execute(update(Gamification).where(
            Gamification.user_id == user_id, (Gamification.last_activity.is_(None)) | (Gamification.last_activity < today))
            .values(streak=case((Gamification.last_activity == today - timedelta(days=1),
                                 func.coalesce(Gamification.streak, 0) + 1), else_=1),
                    last_activity=today))
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("award_points failed")
    return Gamification.query.filter_by(user_id=user_id).first()


def award_daily_visit(user_id):
    """First authenticated visit of the IST day: 5 points once, ref 'visit:<yyyy-mm-dd>' (a replay awards nothing)."""
    return award_points(user_id, VISIT_POINTS, 'visit', ref=f'visit:{ist_today().isoformat()}')
