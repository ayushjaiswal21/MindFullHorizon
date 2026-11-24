"""Step 1 of dispensing: prepare a plan, write nothing (design 4.6). The plan is signed so confirm can check it."""
from flask import current_app
from itsdangerous import BadSignature, URLSafeTimedSerializer

from models import PrescriptionItem
from services.errors import MESSAGES, ServiceError
from services.dispensing import view
from services.inventory import usable_batches
from utils.timeutil import utcnow

SALT = 'rx-dispense-plan'
TOKEN_SECONDS = 600


def _serializer():
    return URLSafeTimedSerializer(current_app.config.get('SECRET_KEY') or current_app.secret_key, salt=SALT)


def allocate(institution_key, medicine_id, quantity):
    """FEFO allocation over usable stock: ([(batch, qty)], shortfall)."""
    left, picks = quantity, []
    for b in usable_batches(institution_key, medicine_id):
        if left <= 0:
            break
        take = min(left, b.quantity_on_hand)
        picks.append((b, take))
        left -= take
    return picks, max(left, 0)


def _wanted(rx, lines):
    """{item_id: quantity} the desk asks for. Default: everything remaining. Never above remaining."""
    remaining = {i.id: i.quantity - i.quantity_dispensed for i in rx.items}
    if lines is None:
        return {k: v for k, v in remaining.items() if v > 0}
    out = {}
    for row in lines:
        try:
            item_id, qty = int(row['item_id']), int(row['quantity'])
        except (KeyError, TypeError, ValueError):
            raise ServiceError('validation', 422, fields={'lines': 'Each line needs item_id and quantity.'})
        if item_id not in remaining or qty < 0 or qty > remaining[item_id]:
            raise ServiceError('validation', 422, fields={'lines': 'A quantity is more than what remains.'})
        if qty:
            out[item_id] = qty
    return out


def plan(rx_id, institution_key, actor_id, lines=None, now=None):
    """Plan dict: {rx, lines:[{item_id, medicine_label, remaining, requested, allocations, shortfall}], warnings, token}."""
    now = now or utcnow()
    rx = view.get_for_desk(rx_id, institution_key)
    if view.effective_status(rx, now) not in view.DISPENSABLE:
        raise ServiceError('rx_not_dispensable', 409)
    wanted = _wanted(rx, lines)
    out_lines, signed, warnings = [], [], []
    if view.prescriber_blocked(rx):
        warnings.append({'code': 'prescriber_not_verified', 'message': MESSAGES['prescriber_not_verified']})
    for item in rx.items:
        n = wanted.get(item.id)
        if not n:
            continue
        picks, short = allocate(institution_key, item.medicine_id, n)
        out_lines.append({'item_id': item.id, 'medicine_label': item.medicine_label,
                          'remaining': item.quantity - item.quantity_dispensed, 'requested': n, 'shortfall': short,
                          'allocations': [{'batch_id': b.id, 'batch_no': b.batch_no, 'expiry_date': b.expiry_date.isoformat(),
                                           'quantity': q} for b, q in picks]})
        signed.append([item.id, [[b.id, q] for b, q in picks]])
        if short:
            warnings.append({'code': 'stock_short', 'message': f'Stock is short for {item.medicine_label}.'})
    if not any(line['allocations'] for line in out_lines):
        raise ServiceError('nothing_to_dispense', 422)
    token = _serializer().dumps({'rx': rx.id, 'inst': institution_key, 'actor': actor_id,
                                 'rv': rx.updated_at.isoformat(), 'lines': signed})
    return {'rx': {'id': rx.id, 'number': rx.number, 'status': rx.status, 'patient_name': rx.patient_name,
                   'doctor_name': rx.doctor_name, 'valid_until': view.iso(rx.expiry_date)},
            'lines': out_lines, 'warnings': warnings, 'token': token, 'expires_in': TOKEN_SECONDS}


def read_token(token, rx_id, institution_key, actor_id):
    """Verified payload of a plan token, or ServiceError('bad_token')."""
    try:
        data = _serializer().loads(token or '', max_age=TOKEN_SECONDS)
    except BadSignature:
        raise ServiceError('bad_token', 400)
    if not (isinstance(data, dict) and data.get('rx') == rx_id and data.get('inst') == institution_key
            and data.get('actor') == actor_id):
        raise ServiceError('bad_token', 400)
    return data


def item_ids(rx_id):
    return [i for (i,) in PrescriptionItem.query.filter_by(prescription_id=rx_id).order_by(PrescriptionItem.id).with_entities(PrescriptionItem.id)]
