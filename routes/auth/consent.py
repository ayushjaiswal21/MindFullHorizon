"""Privacy-notice consent: version tracking, the pending-consent guard, and the /consent route.

`_checked` and `_home` are small request helpers also used by login.py and account.py.
"""
import os

from flask import render_template, request, redirect, url_for, flash, session, jsonify

from models import ConsentRecord, db
from core.decorators import login_required
from services.roles import home_endpoint

from . import auth_bp

CONSENT_KINDS = ('privacy', 'age18')
# Paths a user with a pending consent may still open (everything else is sent to /consent).
CONSENT_EXEMPT = ('/consent', '/logout', '/privacy', '/terms', '/health')


def consent_version():
    """Version of the privacy notice users accept now (env CONSENT_VERSION, default 2026-11). Read per call."""
    return os.getenv('CONSENT_VERSION', '2026-11')


def has_current_consent(user_id):
    """True when the user has accepted BOTH the privacy notice and the 18+ statement at the current version."""
    kinds = {k for (k,) in db.session.query(ConsentRecord.kind).filter_by(user_id=user_id, version=consent_version())}
    return set(CONSENT_KINDS) <= kinds


def needs_reconsent(user):
    """True when the user consented to an OLDER notice version and not yet to the current one.

    Bumping CONSENT_VERSION (for example after the privacy notice changes) makes every earlier ConsentRecord stale:
    the next login of each such user is routed to /consent, and accepting writes new rows, so the old rows stay as proof
    of what was accepted when. Accounts with no consent rows at all (created before consent was recorded) return False
    and are not interrupted; they are listed in docs/PRIVACY_AND_CONSENT.md as an operator decision.
    """
    if not ConsentRecord.query.filter_by(user_id=user.id).first():
        return False
    return not has_current_consent(user.id)


def add_consent_records(user_id):
    """Add the two ConsentRecord rows for the current version to the caller's transaction (skips ones that exist)."""
    version = consent_version()
    have = {k for (k,) in db.session.query(ConsentRecord.kind).filter_by(user_id=user_id, version=version)}
    for kind in CONSENT_KINDS:
        if kind not in have:
            db.session.add(ConsentRecord(user_id=user_id, kind=kind, version=version))


def _checked(name):
    return (request.form.get(name) or '').strip().lower() in ('yes', 'on', 'true', '1')


def _home(role):
    return url_for(home_endpoint(role))


@auth_bp.before_app_request
def consent_guard():
    """Send users whose consent is pending (new Google sign-ups, version bumps) to /consent first."""
    if not session.get('consent_pending'):
        return None
    path = request.path
    if path.startswith('/static/') or path in CONSENT_EXEMPT:
        return None
    if path.startswith('/api') or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify(success=False, error='consent_required', message='Please accept the privacy notice first.'), 403
    return redirect(url_for('auth.consent'))


@auth_bp.route('/consent', methods=['GET', 'POST'])
@login_required
def consent():
    """Privacy notice and 18+ confirmation for users who did not go through the signup form."""
    user_id = session['user_id']
    if request.method == 'POST':
        if not (_checked('consent') and _checked('age_confirm')):
            flash('Please tick both boxes to continue.', 'error')
            return render_template('consent.html', consent_version=consent_version()), 400
        add_consent_records(user_id)
        db.session.commit()
        session.pop('consent_pending', None)
        return redirect(_home(session.get('user_role')))
    if not session.get('consent_pending') and has_current_consent(user_id):
        return redirect(_home(session.get('user_role')))
    return render_template('consent.html', consent_version=consent_version())
