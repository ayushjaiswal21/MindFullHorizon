"""`followup_due` job: remind the plan owner on the day a follow-up step is due (docs/FOLLOWUPS.md).

One job per step (idempotency key `followup-due:<step id>:<due date>`, run_at 09:00 IST on the due date). The handler
re-checks state, adds one in-app Notification per owner and due date, and emails the owner only when SMTP and an
address exist. The text carries no patient name and no health data. Delivery is at-least-once, so the handler is idempotent.
"""
import os
from datetime import timedelta

from core.extensions import db
from models import FollowUpPlan, FollowUpStep, Notification, User
from utils.jobs import register
from utils.timeutil import ist_today, utcnow


def _text(today_or_late):
    return 'You have follow-ups due today.' if today_or_late else 'You have follow-ups waiting on your dashboard.'


@register('followup_due')
def followup_due(job):
    step = db.session.get(FollowUpStep, (job.payload or {}).get('step_id'))
    plan = db.session.get(FollowUpPlan, step.plan_id) if step else None
    if step is None or plan is None:
        return 'skipped:missing'
    if step.status != 'pending' or plan.status != 'open':
        return 'skipped:resolved'
    owner = db.session.get(User, plan.owner_provider_id) if plan.owner_provider_id else None
    if owner is None or owner.deactivated_at is not None:
        return 'skipped:no_owner'
    due = step.due_date.isoformat()
    recent = Notification.query.filter(Notification.recipient_id == owner.id, Notification.type == 'followup_due',
                                       Notification.created_at >= utcnow() - timedelta(days=30)).all()
    if any((n.payload or {}).get('date') == due for n in recent):
        return 'skipped:already_notified'  # another step of this owner due the same day already produced the reminder
    on_time = step.due_date >= ist_today()
    message = _text(on_time)
    db.session.add(Notification(recipient_id=owner.id, type='followup_due', message=message, payload={'date': due}))
    from utils.mailer import send_mail, smtp_configured
    if smtp_configured() and owner.email:
        site = (os.getenv('SITE_URL') or '').rstrip('/')
        send_mail(owner.email, '[MindFull Horizon] Follow-ups due', f'{message} Open the provider dashboard to see them.\n'
                  + (f'{site}/provider/dashboard\n' if site else ''))
        return 'sent'
    return 'sent:in_app'
