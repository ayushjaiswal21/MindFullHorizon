"""Reminder email settings (attached to the patient blueprint) and the public confirm / unsubscribe links.

The address is always the account email. Turning reminders on only queues a confirmation email; nothing else is sent
until the student opens the signed link (services/reminders.py)."""
from flask import flash, redirect, render_template, request, session, url_for

from decorators import login_required, patient_required
from extensions import csrf, db, limiter
from models import ReminderPref, User
from routes.patient import patient_bp
from services import reminders as rem
from utils.mailer import smtp_configured
from utils.site_context import site_url

BAD_LINK = ('This link has expired or is not valid',
            'Open your reminder settings while signed in and turn reminders on again to get a new confirmation email.')


def _hours():
    return [(h, f"{(h % 12) or 12}:00 {'am' if h < 12 else 'pm'}") for h in range(24)]


def _page(status=200):
    pref = ReminderPref.query.filter_by(user_id=session['user_id']).first()
    user = db.session.get(User, session['user_id'])
    return render_template('reminders.html', pref=pref, email=user.email, smtp_ok=smtp_configured(), hours=_hours(),
                           weekdays=list(enumerate(rem.WEEKDAYS))), status


def _result(title, message, status=200):
    return render_template('reminders_result.html', title=title, message=message), status


@patient_bp.route('/reminders')
@login_required
@patient_required
def reminders():
    return _page()


@patient_bp.route('/reminders', methods=['POST'])
@login_required
@patient_required
@limiter.limit('5 per hour', methods=['POST'])
def reminders_save():
    if not smtp_configured():
        flash('Email is not set up on this server, so reminders cannot be turned on.', 'error')
        return _page(400)
    freq = request.form.get('frequency')
    try:
        hour, weekday = int(request.form.get('hour', '')), int(request.form.get('weekday') or 0)
    except ValueError:
        hour = weekday = -1
    if freq not in ('daily', 'weekly') or not 0 <= hour <= 23 or not 0 <= weekday <= 6:
        flash('Choose daily or weekly, and an hour.', 'error')
        return _page(400)
    pref = rem.start(session['user_id'], freq, hour, weekday, site_url())
    db.session.commit()
    flash('Reminders are saved.' if pref.status == 'active' else
          'We sent a confirmation link to your email address. Reminders start only after you open it.', 'success')
    return redirect(url_for('patient.reminders'))


@patient_bp.route('/reminders/off', methods=['POST'])
@login_required
@patient_required
def reminders_off():
    ReminderPref.query.filter_by(user_id=session['user_id']).delete()
    db.session.commit()
    flash('Reminders are off. Nothing more will be sent.', 'success')
    return redirect(url_for('patient.reminders'))


@patient_bp.route('/reminders/confirm/<token>')
def reminders_confirm_page(token):
    found = rem.read_confirm_token(token)
    if not found:
        return _result(*BAD_LINK, status=400)
    return render_template('reminders_confirm.html', token=token, email=found[0].email)


@patient_bp.route('/reminders/confirm/<token>', methods=['POST'])
def reminders_confirm(token):
    found = rem.read_confirm_token(token)
    if not found:
        return _result(*BAD_LINK, status=400)
    rem.confirm(found[1], site_url())
    db.session.commit()
    return _result('Reminders are on', 'Thank you for confirming. You can change the time or turn reminders off at any '
                   'time in your reminder settings. Every email also has a link to stop them.')


@patient_bp.route('/reminders/unsubscribe/<token>', methods=['GET', 'POST'])
@csrf.exempt  # a mail client posts the one-click unsubscribe without a form token; the signed token is the credential
def reminders_unsubscribe(token):
    uid = rem.read_unsubscribe_token(token)
    if uid is None:
        return _result('This link is not valid', 'Sign in and use your reminder settings to turn reminders off.', 400)
    ReminderPref.query.filter_by(user_id=uid).delete()
    db.session.commit()
    return _result('You are unsubscribed', 'We will not send you reminder emails. You can turn them on again in your reminder settings.')
