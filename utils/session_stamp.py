"""Session stamp: lets signed-cookie sessions be invalidated server side (docs/SECURITY.md, "Sessions").

A Flask cookie session cannot be revoked, so login stores `session['stamp']`, a short keyed hash of the user's id,
password hash and role. One before_request check compares it with the user's current values: a password change,
an account deletion or a role change makes every older cookie stale. One cheap query by primary key, and only
for logged-in requests that are not static, health or ready.
"""
import hashlib
import hmac

from flask import current_app, request, session

from core.extensions import db
from models import User

_SKIP_ENDPOINTS = frozenset({'static', 'ops.health', 'ops.ready'})


def make_stamp(user_id, password_hash, role):
    key = (current_app.secret_key or '').encode()
    msg = f'{user_id}:{password_hash or ""}:{role or ""}'.encode()
    return hmac.new(key, msg, hashlib.sha256).hexdigest()[:16]


def stamp_session(user):
    """Call after login and after anything that changes the user's password or role in the SAME request."""
    session['stamp'] = make_stamp(user.id, user.password_hash, user.role)


def _check_stamp():
    uid = session.get('user_id')
    if uid is None or request.endpoint in _SKIP_ENDPOINTS or request.path.startswith('/static/'):
        return None
    stamp = session.get('stamp')
    if stamp is None and current_app.config.get('TESTING'):
        return None  # tests write session['user_id'] directly; production sessions always carry a stamp
    row = None
    if isinstance(uid, int) and isinstance(stamp, str):
        row = db.session.query(User.password_hash, User.role).filter(User.id == uid).first()
    if row is None or not hmac.compare_digest(stamp, make_stamp(uid, row.password_hash, row.role)):
        session.clear()  # the request carries on as anonymous: login_required redirects to the login page
    return None


def init_session_stamp(app):
    app.before_request(_check_stamp)
