"""Public pages: about, faq, contact, privacy, terms (owned by the F2 agent).

The FAQ list lives here so the visible accordion and the FAQPage JSON-LD are built from the same data.
Never log or print contact message text.
"""
import os
import re
import time
from datetime import datetime

from flask import (Blueprint, current_app, redirect, render_template, request, session, url_for)
from itsdangerous import BadSignature, URLSafeSerializer

from extensions import db, limiter
from models import ContactMessage
from utils.helplines import get_helplines
from utils.jobs import enqueue
from utils.seo import site_url

pages_bp = Blueprint('pages', __name__)

REPO_URL = 'https://github.com/ayushjaiswal21/MindFullHorizon'
LAST_UPDATED = '24 November 2026'
FORM_MIN_SECONDS = 3
FORM_MAX_SECONDS = 2 * 60 * 60
EMAIL_RE = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
LIMITS = {'name': 100, 'email': 120, 'subject': 150, 'message_min': 10, 'message_max': 2000}


# ---------- FAQ (single source for the page and its JSON-LD) ----------
# `a` is plain text. `link` is an optional (endpoint, label) pair shown under the answer.
def _hl(key):
    """Number of the helpline whose name contains `key`, from the single helpline config."""
    return next((h['number'] for h in get_helplines() if key in h['name']), '')


def build_faqs():
  nums = {k: _hl(k) for k in ('Tele-MANAS', 'KIRAN', 'Emergency')}
  return [
    {'id': 'therapy', 'q': 'Is Mindful Horizon therapy?',
     'a': 'No. It is a wellness and screening tool. You can log your mood, take the PHQ-9 and GAD-7 questionnaires, '
          'write a journal, try breathing and movement exercises, and book a session with a counsellor at your college. '
          'It does not diagnose anything and it does not replace a counsellor, doctor or psychiatrist.'},
    {'id': 'human', 'q': 'Is the chat a human?',
     'a': 'No. The chat companion, Anya, is an AI assistant. It is not a therapist and it cannot see your history with '
          'a counsellor. If you want to talk to a person, book an appointment with a counsellor or call a helpline.'},
    {'id': 'who-sees', 'q': 'Who can see my data?',
     'a': 'You can. Your assigned counsellor can see the patient data that your assignment allows. Counsellors at your '
          'institution see only totals for groups above a minimum size, plus crisis alerts. Our AI provider, Google '
          'Gemini, receives the text of the features that use AI. Every counsellor view of an individual record is '
          'written to an audit log. The privacy policy lists each category in full.',
     'link': ('pages.privacy', 'Read the privacy policy')},
    {'id': 'self-harm', 'q': 'What happens if I mention self-harm?',
     'a': 'Every chat message goes through a fixed rule-based check before anything else, and it works even if the AI '
          'service is down. If it finds language about harming yourself, the app shows helpline numbers (Tele-MANAS '
          f"{nums['Tele-MANAS']}, KIRAN {nums['KIRAN']}, emergency {nums['Emergency']}) and records a crisis "
          'event without your message text. '
          'Counsellors at your institution can see that an alert exists. A PHQ-9 answer above zero on the question about '
          'thoughts of self-harm triggers the same help screen. This is not an emergency service: if you are in danger, '
          f"call {nums['Emergency']}."},
    {'id': 'journal', 'q': 'Are my journal entries private?',
     'a': 'Journal entries are tied to your account and are not shown to other students. The counsellor pages '
          'do not display journal entries. If you ask for an AI suggestion on an entry, the text of '
          'that entry is sent to Google Gemini to produce the suggestion. Your entries are stored in the service database; '
          'we do not claim they are encrypted at rest.'},
    {'id': 'counsellor-sees', 'q': 'What does my counsellor see?',
     'a': 'Only counsellors linked to you see your individual records. A link is created when you book an appointment '
          'with a counsellor, or when one is added by hand. They can see your assessments, mood history and appointments. '
          'A counsellor at your institution can also see an unacknowledged crisis alert, even without a link, so that no '
          'alert is missed. Those views are audited.'},
    {'id': 'cost', 'q': 'What does it cost?',
     'a': 'There is no payment or subscription feature in the app, and nothing to buy. The service is an early-stage '
          'project run by its operator, so features and availability can change.'},
    {'id': 'age', 'q': 'Do I need to be 18 or older?',
     'a': 'Yes. For now accounts are for adults only. You confirm you are 18 or older when you sign up. If you are '
          f"younger, please do not create an account. Tele-MANAS {nums['Tele-MANAS']} is open to everyone at any age."},
    {'id': 'delete', 'q': 'How do I delete my account?',
     'a': 'Sign in and open your data page. From there you can download a copy of your data or delete your account. '
          'Deletion removes your account and the records tied to it from the service database, including any '
          'prescriptions issued to you. Backups, if the '
          'host keeps any, expire on their own schedule.',
     'link': ('auth.account_data', 'Open the data page')},
    {'id': 'ai-model', 'q': 'Which AI model is used and what is sent to it?',
     'a': 'Google Gemini, through the Gemini API (a Flash model, set by the operator). It receives your chat messages, '
          'and, only when you use the matching feature, a journal entry, assessment scores and answers, or goal, '
          'medication and mood summaries. Your name, email address and user ID are not part of those requests. '
          'The AI is told it is not a therapist, and its output is never what decides whether to show crisis help.'},
    {'id': 'devices', 'q': 'Which browsers and devices work?',
     'a': 'Any current version of Chrome, Edge, Firefox or Safari on a phone, tablet or computer. Pages work with '
          'JavaScript on or off for sign-in and forms. Chat, charts, voice logs and video sessions need JavaScript, '
          'and voice logs and video also need microphone or camera permission that you grant in the browser.'},
]


def faq_jsonld(faqs):
    return {
        '@context': 'https://schema.org',
        '@type': 'FAQPage',
        'mainEntity': [{'@type': 'Question', 'name': f['q'],
                        'acceptedAnswer': {'@type': 'Answer', 'text': f['a']}} for f in faqs],
    }


# ---------- helpers ----------
def _now():
    return time.time()


def _account_data_url():
    try:
        return url_for('auth.account_data')
    except Exception:  # route is added by another agent; keep the page working until it exists
        return '/account/data'


def _email_configured():
    return bool(os.getenv('SMTP_HOST') and os.getenv('CONTACT_RECIPIENT'))


def _page_ctx(title, description, jsonld_type='WebPage', **extra):
    url = site_url() + request.path
    ctx = {
        'page_title': title,
        'page_description': description,
        'canonical_url': url,
        'helplines': get_helplines(),
        'tele_manas': _hl('Tele-MANAS'),
        'emergency_number': _hl('Emergency'),
        'consent_version': os.getenv('CONSENT_VERSION', '2026-11'),
        'last_updated': LAST_UPDATED,
        'repo_url': REPO_URL,
        'account_data_url': _account_data_url(),
        'contact_recipient': os.getenv('CONTACT_RECIPIENT', ''),
        'grievance_email': os.getenv('GRIEVANCE_EMAIL', ''),
        'fiduciary_name': os.getenv('DATA_FIDUCIARY_NAME', ''),
        'jsonld': [{'@context': 'https://schema.org', '@type': jsonld_type, 'name': title,
                    'description': description, 'url': url, 'inLanguage': 'en-IN'}],
    }
    ctx.update(extra)
    return ctx


# ---------- static pages ----------
@pages_bp.route('/about')
def about():
    return render_template('about.html', **_page_ctx(
        'About Mindful Horizon',
        'What Mindful Horizon does and does not do, who it is for, how your data moves, and how crisis safety works.',
        'AboutPage'))


@pages_bp.route('/faq')
def faq():
    faqs = build_faqs()
    ctx = _page_ctx('Frequently asked questions',
                    'Answers about screenings, the AI chat, privacy, counsellor access and deleting your account.',
                    'FAQPage', faqs=faqs)
    ctx['jsonld'] = [faq_jsonld(faqs)]
    return render_template('faq.html', **ctx)


@pages_bp.route('/privacy')
def privacy():
    return render_template('privacy.html', **_page_ctx(
        'Privacy policy',
        'What Mindful Horizon stores, why, who can see it, which processors receive it, and how to access or delete it.'))


@pages_bp.route('/terms')
def terms():
    return render_template('terms.html', **_page_ctx(
        'Terms of use',
        'The terms for using Mindful Horizon: what it is, who may use it, acceptable use and limits of liability.'))


# ---------- contact ----------
def _signer():
    return URLSafeSerializer(current_app.secret_key, salt='contact-form')


def _form_token():
    return _signer().dumps({'t': int(time.time())})


def _check_token(token):
    """Return 'ok', 'fast' (under the minimum time) or 'bad' (missing, forged or expired)."""
    try:
        age = _now() - _signer().loads(token or '')['t']
    except (BadSignature, KeyError, TypeError):
        return 'bad'
    if age < FORM_MIN_SECONDS:
        return 'fast'
    return 'ok' if age <= FORM_MAX_SECONDS else 'bad'


def _contact_page(values=None, errors=None, form_error=None, status=200, sent=False):
    values = values or {'name': session.get('user_name', ''), 'email': session.get('user_email', ''),
                        'subject': '', 'message': ''}
    ctx = _page_ctx('Contact', 'Send a message to the Mindful Horizon team. We cannot answer crisis messages.',
                    'ContactPage', values=values, errors=errors or {}, form_error=form_error,
                    form_token=_form_token(), sent=sent, email_configured=_email_configured(), limits=LIMITS)
    return render_template('contact.html', **ctx), status


def _validate_contact(form):
    values = {k: (form.get(k) or '').strip() for k in ('name', 'email', 'subject', 'message')}
    errors = {}
    if not values['name']:
        errors['name'] = 'Enter your name.'
    elif len(values['name']) > LIMITS['name']:
        errors['name'] = f"Use {LIMITS['name']} characters or fewer."
    if not values['email']:
        errors['email'] = 'Enter your email address so we can reply.'
    elif not EMAIL_RE.match(values['email']) or len(values['email']) > LIMITS['email']:
        errors['email'] = 'Enter a valid email address, like name@example.com.'
    if len(values['subject']) > LIMITS['subject']:
        errors['subject'] = f"Use {LIMITS['subject']} characters or fewer."
    n = len(values['message'])
    if n < LIMITS['message_min']:
        errors['message'] = f"Write at least {LIMITS['message_min']} characters so we can understand your message."
    elif n > LIMITS['message_max']:
        errors['message'] = f"Shorten your message to {LIMITS['message_max']} characters or fewer (now {n})."
    return values, errors


@pages_bp.route('/contact', methods=['GET', 'POST'])
@limiter.limit('5 per hour', methods=['POST'])
def contact():
    if request.method == 'GET':
        return _contact_page(sent=request.args.get('sent') == '1')

    if (request.form.get('website') or '').strip():
        # Honeypot: pretend it worked and store nothing.
        return redirect(url_for('pages.contact', sent=1))

    values, errors = _validate_contact(request.form)
    token = _check_token(request.form.get('form_token'))
    if token == 'bad':
        return _contact_page(values, errors, 'This form has expired. Check your message and send it again.', 400)
    if token == 'fast':
        return _contact_page(values, errors, 'That was very quick. Wait a few seconds, then send it again.', 400)
    if errors:
        return _contact_page(values, errors, None, 400)

    try:
        # A double click or a refresh of the same message must not create a second record or email.
        since = _now() - 300
        recent = (ContactMessage.query.filter_by(email=values['email'], message=values['message'])
                  .filter(ContactMessage.created_at >= datetime.utcfromtimestamp(since)).first())
        if recent is None:
            recent = ContactMessage(name=values['name'], email=values['email'], subject=values['subject'] or None,
                                    message=values['message'], user_id=session.get('user_id'))
            db.session.add(recent)
            db.session.flush()
        enqueue('send_email', {'contact_message_id': recent.id}, idempotency_key=f'contact-email:{recent.id}')
        db.session.commit()
        current_app.logger.info('contact message saved id=%s', recent.id)
    except Exception as exc:  # never log exc text: it can carry the submitted message
        db.session.rollback()
        current_app.logger.error('contact save failed: %s', type(exc).__name__)
        return _contact_page(values, {}, 'We could not save your message. Try again in a few minutes.', 500)
    return redirect(url_for('pages.contact', sent=1))
