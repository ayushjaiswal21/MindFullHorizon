"""Outgoing email (stdlib smtplib) and the `send_email` job handler. Owned by Q1a.

Env: SMTP_HOST, SMTP_PORT (587 STARTTLS, 465 SSL), SMTP_USER, SMTP_PASSWORD, SMTP_FROM, CONTACT_RECIPIENT.
Never logs message bodies or addresses.
"""
import logging
import os
import re
import smtplib
import ssl
from email.message import EmailMessage

from core.extensions import db
from models import ContactMessage
from utils.jobs import PermanentJobError, register

logger = logging.getLogger(__name__)
SMTP_TIMEOUT = 15


def clean_header(value, limit=200):
    """One line only: CR/LF and other control characters would allow header injection."""
    return re.sub(r'[\x00-\x1f\x7f]+', ' ', str(value or '')).strip()[:limit]


def smtp_configured():
    return bool(os.getenv('SMTP_HOST'))


def send_mail(to, subject, body, reply_to=None, headers=None):
    """Send one plain-text email. Raises on SMTP failure (the job retries). Requires SMTP_HOST."""
    host = os.getenv('SMTP_HOST')
    port = int(os.getenv('SMTP_PORT') or 587)
    user, password = os.getenv('SMTP_USER'), os.getenv('SMTP_PASSWORD')
    sender = clean_header(os.getenv('SMTP_FROM') or user or 'noreply@localhost')
    msg = EmailMessage()
    msg['From'], msg['To'], msg['Subject'] = sender, clean_header(to), clean_header(subject, 150)
    if reply_to:
        msg['Reply-To'] = clean_header(reply_to, 120)
    for name, value in (headers or {}).items():  # extra headers (List-Unsubscribe): same one-line cleaning
        msg[clean_header(name, 60)] = clean_header(value, 400)
    msg.set_content(body)
    ctx = ssl.create_default_context()
    if port == 465:
        server = smtplib.SMTP_SSL(host, port, timeout=SMTP_TIMEOUT, context=ctx)
    else:
        server = smtplib.SMTP(host, port, timeout=SMTP_TIMEOUT)
    with server:
        if port != 465:
            server.starttls(context=ctx)
        if user and password:
            server.login(user, password)
        server.send_message(msg)


def _contact_failed(job):
    cm = db.session.get(ContactMessage, (job.payload or {}).get('contact_message_id'))
    if cm is not None and cm.status == 'new':
        cm.status = 'email_failed'


@register('send_email', on_dead=_contact_failed)
def send_email(job):
    """payload: {'contact_message_id': int}. Idempotent: an already 'emailed' message is not sent again."""
    cm_id = (job.payload or {}).get('contact_message_id')
    cm = db.session.get(ContactMessage, cm_id) if cm_id else None
    if cm is None:
        raise PermanentJobError('contact_message_missing')
    if cm.status != 'new':
        return 'skipped:already_handled'
    recipient = os.getenv('CONTACT_RECIPIENT')
    if not smtp_configured() or not recipient:
        return 'skipped:smtp_unset'  # message stays 'new' and is read in the database; no endless retries
    name, email, subject = clean_header(cm.name, 100), clean_header(cm.email, 120), clean_header(cm.subject, 150)
    body = f"From: {name} <{email}>\nSent: {cm.created_at:%Y-%m-%d %H:%M} UTC\n\n{cm.message}\n"
    send_mail(recipient, f"[MindFull Horizon contact] {subject or 'No subject'}", body, reply_to=email)
    cm.status = 'emailed'
    return 'sent'
