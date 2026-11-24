"""Optional request idempotency for POST-create routes.

A client may send `Idempotency-Key: <key>` or a `client_request_id` JSON/form field (key format
[A-Za-z0-9._-]{8,64}). The row stores it in `client_request_id`; (user_id, client_request_id) is unique, so a
replay or a concurrent double submit finds the first row and the route answers with it (HTTP 200) instead of
creating a duplicate. No key means no protection, so old clients keep working.
"""
import re

from flask import flash, jsonify, redirect, request, url_for
from sqlalchemy.exc import IntegrityError

from extensions import db

KEY_RE = re.compile(r'[A-Za-z0-9._-]{8,64}')


class InvalidKey(ValueError):
    """The client sent a malformed idempotency key."""


def get_key():
    """The validated key from the header or body, or None. Raises InvalidKey if present but malformed."""
    key = request.headers.get('Idempotency-Key')
    if key is None:
        body = request.get_json(silent=True) if request.is_json else None
        key = (body if isinstance(body, dict) else request.form).get('client_request_id')
    if key is None or key == '':
        return None
    if not isinstance(key, str) or not KEY_RE.fullmatch(key):
        raise InvalidKey
    return key


def handle_invalid_key(_error):
    """Blueprint error handler: JSON 400 for API callers, flash and redirect for form posts."""
    msg = 'Invalid request id.'
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', ''):
        return jsonify(success=False, ok=False, message=msg, error=msg), 400
    flash(msg, 'error')
    return redirect(request.referrer or url_for('core.index'))


def existing(model, user_id, key):
    """The row this user already created with this key, or None."""
    return model.query.filter_by(user_id=user_id, client_request_id=key).first() if key else None


def add_once(model, row, key):
    """Add and commit `row`. Returns (row, created). If the unique key was already used, returns (first row, False).

    Any other IntegrityError is re-raised for the caller (natural unique constraints).
    """
    uid = row.user_id
    db.session.add(row)
    try:
        db.session.commit()
        return row, True
    except IntegrityError:
        db.session.rollback()
        first = existing(model, uid, key)
        if first is None:
            raise
        return first, False
