"""Appointment state machine. Every status change goes through `transition`.

pending -> accepted | rejected | cancelled;  accepted -> completed | cancelled;  the rest are terminal.
'booked' is a legacy alias of 'accepted'. The change is one compare-and-set UPDATE, so of two racing
requests exactly one wins and the other raises TransitionError (routes answer 409, generic message).
The caller commits.
"""
from sqlalchemy import update

from extensions import db
from models import Appointment
from utils.timeutil import utcnow

# (from, to) -> roles allowed to make the move. 'system' (jobs, scripts) may make any legal move.
RULES = {
    ('pending', 'accepted'): {'provider'},
    ('pending', 'rejected'): {'provider'},
    ('pending', 'cancelled'): {'patient'},
    ('accepted', 'completed'): {'provider'},
    ('accepted', 'cancelled'): {'patient', 'provider'},
}
CONFLICT_MESSAGE = 'This appointment cannot be changed that way any more.'


class TransitionError(Exception):
    """Illegal move, wrong actor, or someone else changed the appointment first."""


def canonical(status):
    return 'accepted' if status == 'booked' else status


def transition(appt, new_status, actor, **fields):
    """Move `appt` to `new_status` as `actor` ('patient' | 'provider' | 'system'); extra `fields` are set in the same UPDATE."""
    old = canonical(appt.status)
    roles = RULES.get((old, new_status))
    if roles is None or (actor != 'system' and actor not in roles):
        raise TransitionError(f'{old} -> {new_status} by {actor}')
    sources = ('accepted', 'booked') if old == 'accepted' else (old,)
    changed = db.session.execute(
        update(Appointment).where(Appointment.id == appt.id, Appointment.status.in_(sources))
        .values(status=new_status, updated_at=utcnow(), **fields)).rowcount
    if changed != 1:
        db.session.expire(appt)
        raise TransitionError('appointment changed concurrently')
    db.session.expire(appt)  # reload the new values on next access
    if new_status == 'accepted':
        from utils.appt_reminders import schedule  # late: it imports the job queue
        schedule(appt)  # the 24 h reminder job joins the caller's transaction
    return appt
