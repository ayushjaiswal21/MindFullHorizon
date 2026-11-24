"""Helpers for the JSON routes of the clinical blueprints (design 5.1)."""
from functools import wraps

from flask import jsonify, request
from sqlalchemy.exc import IntegrityError

from extensions import db
from services.errors import ServiceError
from utils.idempotency import KEY_RE


def iso(value):
    """Stored naive UTC datetime -> ISO 8601 string with Z (None stays None)."""
    return value.isoformat() + 'Z' if value else None


def fail(err):
    """JSON error body and status of a ServiceError. Only fixed messages reach the client."""
    return jsonify(err.body()), err.http


def idem_key():
    """The validated Idempotency-Key header, or ServiceError('idempotency_key_required', 400)."""
    key = request.headers.get('Idempotency-Key', '')
    if not KEY_RE.fullmatch(key):
        raise ServiceError('idempotency_key_required', 400)
    return key


def json_body():
    body = request.get_json(silent=True)
    return body if isinstance(body, dict) else {}


def service_errors(f):
    """Turn ServiceError (and a lost unique-constraint race) into the standard JSON error; roll the session back."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ServiceError as err:
            db.session.rollback()
            return fail(err)
        except IntegrityError:
            db.session.rollback()
            return fail(ServiceError('conflict', 409))
    return wrapper
