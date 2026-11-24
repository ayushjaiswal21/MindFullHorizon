import logging

logger = logging.getLogger(__name__)


def record_crisis(user_id, source, severity, reason):
    """Write a CrisisEvent audit row. Never raises. `reason` is a short code, never user text."""
    if not user_id:
        return None
    try:
        from extensions import db
        from models import CrisisEvent
        event = CrisisEvent(user_id=user_id, source=source, severity=int(severity), reason=str(reason)[:100])
        db.session.add(event)
        db.session.commit()
        return event.id
    except Exception:
        logger.exception("Could not record crisis event")
        try:
            from extensions import db
            db.session.rollback()
        except Exception:
            pass
        return None
