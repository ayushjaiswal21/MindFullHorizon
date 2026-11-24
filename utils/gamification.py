import logging
from datetime import datetime, timezone, timedelta

import models
from models import Gamification
from extensions import db

logger = logging.getLogger(__name__)

DAILY_CAP = 3  # max point awards per activity type per UTC day
# Never gamify assessments or mood scores (docs/SAFETY_RESEARCH.md).
NO_POINTS = {'assessment', 'mood'}
# activity type -> (model name, timestamp column); today's rows of that model are the award count.
SOURCES = {
    'log_medication': ('MedicationLog', 'taken_at'),
    'breathing_exercise': ('BreathingExerciseLog', 'created_at'),
    'yoga_session': ('YogaLog', 'created_at'),
    'digital_detox_log': ('DigitalDetoxLog', 'created_at'),
    'journal_entry': ('JournalEntry', 'created_at'),
    'voice_log': ('VoiceLog', 'created_at'),
}


def _logged_today(user_id, activity_type, day_start):
    name, col = SOURCES[activity_type]
    model = getattr(models, name, None)
    if model is None:
        return 0
    return model.query.filter(model.user_id == user_id, getattr(model, col) >= day_start).count()


def award_points(user_id, points, activity_type):
    """Award points and update the streak, then commit. Call after the activity row is added.

    No points for NO_POINTS or unknown types; at most DAILY_CAP awards per type per day.
    The streak counts distinct UTC days, so repeat activity on one day never changes it.
    """
    gamification = Gamification.query.filter_by(user_id=user_id).first()
    if activity_type in NO_POINTS or activity_type not in SOURCES:
        return gamification or Gamification(user_id=user_id, points=0, streak=0)
    if not gamification:
        gamification = Gamification(user_id=user_id, points=0, streak=0)
        db.session.add(gamification)

    today = datetime.now(timezone.utc).date()
    day_start = datetime(today.year, today.month, today.day)  # created_at columns hold naive UTC
    if _logged_today(user_id, activity_type, day_start) <= DAILY_CAP:
        gamification.points = (gamification.points or 0) + points

    last = gamification.last_activity
    if isinstance(last, datetime):
        last = last.date()
    if last != today:
        gamification.streak = (gamification.streak or 0) + 1 if last == today - timedelta(days=1) else 1
        gamification.last_activity = today

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("award_points commit failed")
    return gamification
