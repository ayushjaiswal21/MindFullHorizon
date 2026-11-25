"""Crisis durability (O-01, O-02). Owned by Q1a.

`record_crisis` writes the CrisisEvent AND a `crisis_alert` job in the CALLER's transaction (no commit, no swallowed
errors): the alert exists if and only if the data it belongs to is committed. The student's own emergency reply and
helplines never depend on this write (callers compute them first, see `try_record_crisis`).

Timeline: event -> `crisis_alert` job (notify providers of the institution) -> `crisis_escalate` level 1 after
CRISIS_ESCALATE_MINUTES (default 15) -> level 2 (+ email CRISIS_ESCALATION_EMAIL) -> level 3 (last, dead-letter alert log).
Acknowledging the event (CrisisEvent.acknowledged_at) stops the chain. No patient text is ever stored or emailed.
"""
import logging
import os
from datetime import datetime, timedelta

from extensions import db
from models import CrisisEvent, Notification, User
from utils.jobs import PermanentJobError, enqueue, register

logger = logging.getLogger(__name__)
MAX_LEVEL = 3


def _minutes():
    try:
        return max(0, float(os.getenv('CRISIS_ESCALATE_MINUTES') or 15))
    except ValueError:
        return 15.0


def text_is_crisis(text):
    """True if the rule-based detector (floor + raise-only fuzzy layer, ai/severity.py + ai/fuzzy_crisis.py)
    flags self-harm language. Never calls an LLM."""
    return text_is_crisis_detailed(text)[0]


def text_is_crisis_detailed(text):
    """(is_crisis, matched_via): matched_via is 'exact', 'fuzzy' or 'none', for audit tagging (never calls an LLM).
    'fuzzy' means only the edit-distance-1 crisis-vocabulary layer found it, not the exact-match regexes."""
    from ai.fuzzy_crisis import classify_with_fuzzy
    level, matched_via = classify_with_fuzzy(text)
    return level == 'crisis', matched_via


def record_crisis(user_id, source, severity, reason):
    """Add a CrisisEvent and its `crisis_alert` job to the CURRENT transaction; the caller commits.

    Returns the event id (flushed). Raises on failure: callers must not swallow it silently.
    `reason` is a short code, never user text.
    """
    if not user_id:
        return None
    event = CrisisEvent(user_id=user_id, source=source, severity=int(severity), reason=str(reason)[:100])
    db.session.add(event)
    db.session.flush()
    enqueue('crisis_alert', {'event_id': event.id}, idempotency_key=f'crisis-alert:{event.id}', max_attempts=10)
    return event.id


def try_record_crisis(user_id, source, severity, reason):
    """record_crisis + commit for callers with no other data in the transaction (chat). False on failure.

    On failure: rollback and an ERROR line with ids only; the caller still returns the emergency response.
    """
    try:
        record_crisis(user_id, source, severity, reason)
        db.session.commit()
        return True
    except Exception as exc:
        db.session.rollback()
        logger.error("crisis record FAILED user=%s source=%s err=%s", user_id, source, type(exc).__name__)
        return False


def _providers(user):
    return User.query.filter(User.role == 'provider', User.institution == user.institution).all()


def _notify(providers, event, level, message):
    """One Notification per provider and (event, level); safe to run twice."""
    for p in providers:
        seen = Notification.query.filter(Notification.recipient_id == p.id, Notification.type == 'crisis_alert',
                                         Notification.created_at >= event.created_at).all()
        if any((n.payload or {}).get('event_id') == event.id and (n.payload or {}).get('level') == level for n in seen):
            continue
        db.session.add(Notification(recipient_id=p.id, type='crisis_alert', message=message,
                                    payload={'event_id': event.id, 'level': level}))


def _event(job):
    event = db.session.get(CrisisEvent, (job.payload or {}).get('event_id'))
    if event is None:
        raise PermanentJobError('event_missing')
    return event


def _dead(job):
    logger.critical("crisis job DEAD, alert not delivered event=%s kind=%s job=%s",
                    (job.payload or {}).get('event_id'), job.kind, job.id)


@register('crisis_alert', on_dead=_dead)
def crisis_alert(job):
    event = _event(job)
    if event.acknowledged_at:
        return 'skipped:acknowledged'
    user = db.session.get(User, event.user_id)
    _notify(_providers(user) if user else [], event, 0,
            'A student at your institution needs urgent follow-up. Open the dashboard to review.')
    enqueue('crisis_escalate', {'event_id': event.id, 'level': 1}, idempotency_key=f'crisis-escalate:{event.id}:1',
            run_at=datetime.utcnow() + timedelta(minutes=_minutes()), max_attempts=10)
    return 'notified'


@register('crisis_escalate', on_dead=_dead)
def crisis_escalate(job):
    event = _event(job)
    level = int((job.payload or {}).get('level') or 1)
    if event.acknowledged_at:
        return 'skipped:acknowledged'
    if event.escalation_level >= level:
        return 'skipped:already_escalated'
    user = db.session.get(User, event.user_id)
    institution = (user.institution if user else None) or 'an institution'
    now = datetime.utcnow()
    event.escalation_level, event.escalated_at = level, now
    _notify(_providers(user) if user else [], event, level,
            f'Escalation {level}: a student still needs follow-up and nobody has acknowledged the alert.')
    target = os.getenv('CRISIS_ESCALATION_EMAIL')
    if level >= 2 and target:
        from utils.mailer import send_mail, smtp_configured
        if smtp_configured():
            send_mail(target, f'[MindFull Horizon] Unacknowledged crisis alert (level {level})',
                      f'A student at {institution} needs follow-up, open the dashboard.\n'
                      f'Event id: {event.id}\nTime: {event.created_at:%Y-%m-%d %H:%M} UTC\n')
        else:
            logger.warning("crisis escalation email not sent: SMTP unset event=%s", event.id)
    if level < MAX_LEVEL:
        enqueue('crisis_escalate', {'event_id': event.id, 'level': level + 1},
                idempotency_key=f'crisis-escalate:{event.id}:{level + 1}',
                run_at=now + timedelta(minutes=_minutes()), max_attempts=10)
    else:
        logger.error("crisis alert UNACKNOWLEDGED at final escalation level event=%s", event.id)
    return f'escalated:{level}'
