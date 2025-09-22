from datetime import datetime, timezone, timedelta
from models import Gamification
from extensions import db

def award_points(user_id, points, activity_type):
    """Awards points to a user and updates their gamification stats."""
    gamification = Gamification.query.filter_by(user_id=user_id).first()
    if not gamification:
        gamification = Gamification(user_id=user_id, points=0, streak=0)
        db.session.add(gamification)

    gamification.points += points
    
    # Update streak logic
    today = datetime.now(timezone.utc).date()
    if gamification.last_activity:
        # Ensure last_activity is a date object
        last_activity_date = gamification.last_activity
        if isinstance(last_activity_date, datetime):
            last_activity_date = last_activity_date.date()

        if last_activity_date == today - timedelta(days=1):
            gamification.streak += 1
        elif last_activity_date < today:
            gamification.streak = 1 # Reset streak if there was a gap
    else:
        gamification.streak = 1 # First activity

    gamification.last_activity = today

    return gamification
