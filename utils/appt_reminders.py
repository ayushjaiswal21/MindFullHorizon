"""Appointment reminders: one `appointment_reminder` job per accepted appointment, 24 hours before the slot (IST).

`schedule()` is called from `utils.state.transition` when an appointment becomes accepted, inside the caller's
transaction. Idempotency key `appt-reminder:<id>:24h`. The handler re-checks everything when it runs: a cancelled,
completed or moved appointment, or a slot already past, is a no-op, so no reminder is ever sent after the appointment
time. Text is generic (day, time, provider name); no health detail. Email goes to the student only when SMTP is set.
"""
from datetime import datetime, timedelta, timezone

from core.extensions import db
from models import Appointment, Job, Notification, User
from utils.jobs import enqueue, register
from utils.timeutil import IST, ist_now, utcnow

KIND = '24h'
LEAD = timedelta(hours=24)


def key_for(appointment_id):
    return f'appt-reminder:{appointment_id}:{KIND}'


def slot_of(appt):
    """Naive IST wall-clock datetime of the appointment, or None when date or time cannot be read."""
    try:
        return datetime.strptime(f'{appt.date} {appt.time}', '%Y-%m-%d %H:%M')
    except (TypeError, ValueError):
        return None


def schedule(appt):
    """Queue the reminder for an accepted appointment (no commit). Returns the Job, or None for a past or unreadable slot."""
    slot = slot_of(appt)
    if slot is None or slot <= ist_now():
        return None
    due_utc = (slot - LEAD).replace(tzinfo=IST).astimezone(timezone.utc).replace(tzinfo=None)
    return enqueue('appointment_reminder', {'appointment_id': appt.id, 'slot': slot.isoformat()},
                   idempotency_key=key_for(appt.id), run_at=max(due_utc, utcnow()))


def states(appointment_ids):
    """{appointment id: 'scheduled' | 'sent'} for appointments that really have a live or finished reminder job."""
    keys = {key_for(i): i for i in appointment_ids}
    out = {}
    for job in Job.query.filter(Job.idempotency_key.in_(list(keys))).all() if keys else []:
        if job.status in ('queued', 'running', 'failed'):
            out[keys[job.idempotency_key]] = 'scheduled'
        elif job.status == 'done' and (job.last_error or '').startswith('sent'):
            out[keys[job.idempotency_key]] = 'sent'
    return out


def _when(slot, now):
    gap = (slot.date() - now.date()).days
    return 'today' if gap == 0 else 'tomorrow' if gap == 1 else slot.strftime('%d %b')


def _notify(user_id, appt_id, message):
    seen = Notification.query.filter(Notification.recipient_id == user_id, Notification.type == 'appointment_reminder',
                                     Notification.created_at >= utcnow() - timedelta(days=3)).all()
    if not any((n.payload or {}).get('appointment_id') == appt_id for n in seen):
        db.session.add(Notification(recipient_id=user_id, type='appointment_reminder', message=message,
                                    payload={'appointment_id': appt_id}))


@register('appointment_reminder')
def appointment_reminder(job):
    appt = db.session.get(Appointment, (job.payload or {}).get('appointment_id'))
    if appt is None or appt.status not in ('accepted', 'booked'):
        return 'skipped:not_accepted'
    slot, now = slot_of(appt), ist_now()
    if slot is None or slot.isoformat() != (job.payload or {}).get('slot'):
        return 'skipped:rescheduled'
    if now >= slot:
        return 'skipped:past'
    when, hhmm = _when(slot, now), slot.strftime('%H:%M')
    patient = db.session.get(User, appt.user_id)
    provider = db.session.get(User, appt.provider_id) if appt.provider_id else None
    if patient is None:
        return 'skipped:no_patient'
    _notify(patient.id, appt.id, f'Reminder: appointment {when} at {hhmm} with {provider.name if provider else "your counsellor"}')
    if provider is not None:
        _notify(provider.id, appt.id, f'Reminder: appointment {when} at {hhmm} with {patient.name}')
    from utils.mailer import send_mail, smtp_configured
    if smtp_configured() and patient.email:
        send_mail(patient.email, '[MindFull Horizon] Appointment reminder',
                  f'Reminder: appointment {when} at {hhmm} with {provider.name if provider else "your counsellor"}.\n')
        return 'sent'
    return 'sent:in_app'
