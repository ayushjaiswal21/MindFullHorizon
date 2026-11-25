"""Opt-in reminder emails with double confirmation (docs/WELLBEING_TOOLS.md).

Nothing is sent until the student opens a signed, expiring link emailed to the account address, which protects other
people's mailboxes. Every email carries a generic line, the app link and a one-click unsubscribe link: no health
information. At most one reminder per user per IST day. Sending runs through the job queue (`reminder_send`), which
schedules the next run itself.
"""
import os
import secrets
from datetime import datetime, timedelta, timezone

from flask import current_app
from itsdangerous import BadSignature, URLSafeSerializer, URLSafeTimedSerializer

from extensions import db
from models import ReminderPref, User
from utils.jobs import enqueue, register
from utils.mailer import send_mail, smtp_configured
from utils.timeutil import IST, ist_today, utcnow

KIND = 'reminder_send'
CONFIRM_MAX_AGE = 2 * 24 * 3600
LATE_AFTER = timedelta(hours=6)  # a worker that was asleep does not send a reminder many hours after its time
WEEKDAYS = ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')


def _key():
    return current_app.config.get('SECRET_KEY') or current_app.secret_key


def confirm_token(user, pref):
    return URLSafeTimedSerializer(_key(), salt='reminder-confirm').dumps({'u': user.id, 'e': user.email, 'n': pref.nonce})


def read_confirm_token(token):
    """(user, pref) when the signature, age, address and nonce all still match and the preference is pending; else None."""
    try:
        data = URLSafeTimedSerializer(_key(), salt='reminder-confirm').loads(token, max_age=CONFIRM_MAX_AGE)
        user, pref = db.session.get(User, data['u']), ReminderPref.query.filter_by(user_id=data['u']).first()
    except (BadSignature, KeyError, TypeError):
        return None
    if user is None or pref is None or pref.status != 'pending' or pref.nonce != data.get('n') or user.email != data.get('e'):
        return None
    return user, pref


def unsubscribe_token(user_id):
    return URLSafeSerializer(_key(), salt='reminder-unsubscribe').dumps({'u': user_id})


def read_unsubscribe_token(token):
    """The user id, or None. These links never expire: an old email must still be able to stop the emails."""
    try:
        return URLSafeSerializer(_key(), salt='reminder-unsubscribe').loads(token)['u']
    except (BadSignature, KeyError, TypeError):
        return None


def next_due(pref, after):
    """First reminder time strictly after `after` (naive UTC) as (naive UTC datetime, IST date)."""
    local = after.replace(tzinfo=timezone.utc).astimezone(IST)
    cand = local.replace(hour=pref.hour_ist, minute=0, second=0, microsecond=0)
    while cand <= local or (pref.frequency == 'weekly' and cand.weekday() != pref.weekday):
        cand += timedelta(days=1)
    return cand.astimezone(timezone.utc).replace(tzinfo=None), cand.date()


def _enqueue(kind, pref, run_at, key_date, site):
    payload = {'user_id': pref.user_id, 'nonce': pref.nonce, 'kind': kind, 'site': site, 'due': run_at.isoformat()}
    return enqueue(KIND, payload, idempotency_key=f'reminder:{kind}:{pref.user_id}:{pref.nonce}:{key_date}', run_at=run_at)


def start(user_id, frequency, hour, weekday, site):
    """Create or change the preference and queue the confirmation email (or, for an active one, the new schedule).
    Returns the pref. Caller commits."""
    pref = ReminderPref.query.filter_by(user_id=user_id).first()
    was_active = bool(pref and pref.status == 'active')
    if pref is None:
        pref = ReminderPref(user_id=user_id)
        db.session.add(pref)
    pref.frequency, pref.hour_ist, pref.weekday = frequency, hour, weekday
    pref.nonce = secrets.token_hex(8)  # a new nonce ends older confirmation links and older job chains
    pref.status = 'active' if was_active else 'pending'
    db.session.flush()
    if was_active:
        due, day = next_due(pref, utcnow())
        _enqueue('reminder', pref, due, day, site)
    else:
        _enqueue('confirm', pref, utcnow(), ist_today().isoformat(), site)
    return pref


def confirm(pref, site):
    pref.status, pref.confirmed_at = 'active', utcnow()
    due, day = next_due(pref, utcnow())
    _enqueue('reminder', pref, due, day, site)


def _site(payload):
    return (os.getenv('SITE_URL') or payload.get('site') or '').strip().rstrip('/')


def _confirm_body(site, token):
    return ('Hello,\n\nSomeone, hopefully you, asked MindFull Horizon to send gentle reminder emails to this address.\n'
            'To turn them on, open this link within 2 days:\n'
            f'{site}/patient/reminders/confirm/{token}\n\n'
            'If this was not you, do nothing. No reminders will be sent and no account is changed.\n')


def _reminder_body(site, token):
    return ('Hello,\n\nA gentle reminder to take a few minutes for yourself today.\n'
            f'Open MindFull Horizon: {site}/\n\n'
            'You get this email because you turned on reminders in your MindFull Horizon account.\n'
            f'To stop these emails with one click: {site}/patient/reminders/unsubscribe/{token}\n')


@register(KIND)
def reminder_send(job):
    """payload: user_id, nonce, kind ('confirm' or 'reminder'), due (naive UTC ISO), site. Idempotent: a stale chain
    (old nonce), an unsubscribed or deleted user, a second send on one IST day and a very late run all skip."""
    p = job.payload or {}
    pref = ReminderPref.query.filter_by(user_id=p.get('user_id')).first()
    if pref is None or pref.nonce != p.get('nonce'):
        return 'skipped:stale'
    user = db.session.get(User, pref.user_id)
    if user is None or user.deactivated_at is not None:
        return 'skipped:no_user'
    site = _site(p)
    if p.get('kind') == 'confirm':
        if pref.status != 'pending':
            return 'skipped:not_pending'
        if not smtp_configured() or not site:
            return 'skipped:smtp_unset'
        send_mail(user.email, 'Confirm your MindFull Horizon reminders', _confirm_body(site, confirm_token(user, pref)))
        return 'sent'
    if pref.status != 'active':
        return 'skipped:not_active'
    now, due = utcnow(), datetime.fromisoformat(p['due'])
    nxt, day = next_due(pref, max(now, due))
    _enqueue('reminder', pref, nxt, day, site)  # the chain continues whatever happens below
    today = ist_today()
    if pref.last_sent_on == today:
        return 'skipped:rate_limit'
    if now - due > LATE_AFTER:
        return 'skipped:late'
    if not smtp_configured() or not site:
        return 'skipped:smtp_unset'
    pref.last_sent_on = today  # set before sending: if the send raises, the whole transaction (and this) rolls back
    token = unsubscribe_token(user.id)
    unsub = f'{site}/patient/reminders/unsubscribe/{token}'
    send_mail(user.email, 'A gentle reminder from MindFull Horizon', _reminder_body(site, token),
              headers={'List-Unsubscribe': f'<{unsub}>', 'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click'})
    return 'sent'
