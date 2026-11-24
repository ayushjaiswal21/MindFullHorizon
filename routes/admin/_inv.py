"""Small helpers shared by the catalogue, inventory, dispensing and reports admin modules."""
from datetime import date
from functools import wraps

from flask import abort, g, request, session

from services.errors import ServiceError
from services.roles import norm_inst


def inst():
    """The institution key of the logged-in admin, from the database row loaded by the decorator, never the client."""
    return norm_inst(g.actor.institution)


def page_errors(f):
    """HTML routes: a ServiceError becomes the plain HTTP error (404 for anything out of scope)."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ServiceError as err:
            abort(err.http if err.http in (400, 403, 404, 409, 422) else 400)
    return wrapper


def arg_date(name):
    """ISO date from the query string, or None when missing or malformed."""
    try:
        return date.fromisoformat(request.args.get(name, '')[:10])
    except ValueError:
        return None


def arg_int(name, default=None):
    try:
        return int(request.args.get(name, ''))
    except ValueError:
        return default


def tx_json(tx):
    return {'id': tx.id, 'batch_id': tx.batch_id, 'delta': tx.delta, 'kind': tx.kind, 'reason_code': tx.reason_code}


def remember_rx(rx_id):
    """The desk may open a prescription it looked up by number in this session (the queue needs no memory)."""
    seen = [i for i in session.get('desk_rx', []) if i != rx_id]
    session['desk_rx'] = (seen + [rx_id])[-10:]


def may_open(rx):
    from services.dispensing import in_queue
    return in_queue(rx) or rx.id in session.get('desk_rx', [])
