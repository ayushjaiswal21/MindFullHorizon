"""Patient prescription screens, JSON API and the public status check (docs/CLINICAL_DESIGN.md 5.2 and 3.9).

Every route filters by the session user; the prescription id in a URL is only ever looked up through the
patient's own rows (`get_for_patient`, `request_pharmacy`). Never log or audit free text.
"""
import logging

from flask import Blueprint, abort, jsonify, render_template, request, session

from decorators import login_required, patient_required, prescriptions_required
from extensions import db, limiter
from models import ProviderPatient, User
from services.errors import ServiceError
from services.http import fail, idem_key, iso, json_body, service_errors
from utils import rx_text
from utils.audit import audit
from utils.pagination import page_args
from utils.rx_format import rx_date, rx_datetime
from utils.seo import site_url
from utils.timeutil import utcnow

logger = logging.getLogger(__name__)

rx_patient_bp = Blueprint('rx_patient', __name__)
rx_patient_bp.add_app_template_filter(rx_date, 'rx_date')
rx_patient_bp.add_app_template_filter(rx_datetime, 'rx_datetime')

BUCKETS = ('active', 'past')


def _rxs():
    from services import prescriptions
    return prescriptions


def _consent():
    from services import consent
    return consent


# ---------- pages ----------

def list_page():
    """Body of `patient.my_prescriptions` (kept in routes/patient.py as a thin route so the endpoint name stays)."""
    uid = session['user_id']
    tab = request.args.get('tab') if request.args.get('tab') in BUCKETS else 'active'
    page, per_page = page_args(default=10, max_per_page=50)
    rows, meta = _rxs().list_for_patient(uid, tab, page, per_page)
    has_any = bool(rows)
    if not rows and tab == 'active':
        has_any = _rxs().list_for_patient(uid, 'past', 1, 1)[1]['total'] > 0
    return render_template('my_prescriptions.html', user_name=session['user_name'], rows=rows, meta=meta, tab=tab,
                           has_any=has_any, consent=_consent().erx_status(uid), rx_text=rx_text)


@rx_patient_bp.route('/patient/prescriptions/<int:rx_id>')
@prescriptions_required
@login_required
@patient_required
def detail(rx_id):
    try:
        rx = _rxs().get_for_patient(session['user_id'], rx_id)
    except ServiceError:
        abort(404)
    return render_template('rx_patient/detail.html', user_name=session['user_name'], rx=rx, rx_text=rx_text)


@rx_patient_bp.route('/patient/prescriptions/<int:rx_id>/print')
@prescriptions_required
@login_required
@patient_required
def print(rx_id):  # noqa: A001  (endpoint name is part of the contract: rx_patient.print)
    from models import Prescription
    try:
        _rxs().get_for_patient(session['user_id'], rx_id)  # 404 unless it is theirs and not a draft
    except ServiceError:
        abort(404)
    rx = _rxs().serialize(Prescription.query.filter_by(id=rx_id, patient_id=session['user_id']).one(), 'doctor')  # snapshot fields for the printout
    return render_template('provider_rx/print.html', rx=rx, site_url=site_url(), printed_at=utcnow())


@rx_patient_bp.route('/rx/<number>')
@limiter.limit('30 per minute')
@prescriptions_required
def status(number):
    """Public check: validity, issue date, doctor and institution only. Unknown and malformed numbers look the same."""
    from utils.rx_numbers import normalise
    info = _rxs().public_status(number)  # None for malformed (bad check character) and unknown numbers alike
    if not info:
        abort(404)
    info = dict(info, number=normalise(number))
    if request.accept_mimetypes.best == 'application/json':
        return jsonify(success=True, **info)
    return render_template('rx_patient/status.html', s=info)


# ---------- JSON API ----------

@rx_patient_bp.route('/patient/api/prescriptions')
@prescriptions_required
@login_required
@patient_required
def api_list():
    bucket = request.args.get('status') if request.args.get('status') in BUCKETS else 'active'
    page, per_page = page_args(default=10, max_per_page=50)
    rows, meta = _rxs().list_for_patient(session['user_id'], bucket, page, per_page)
    return jsonify(success=True, items=rows, meta=meta)


@rx_patient_bp.route('/patient/api/prescriptions/<int:rx_id>/request-pharmacy', methods=['POST'])
@prescriptions_required
@login_required
@patient_required
@service_errors
def request_pharmacy(rx_id):
    idem_key()  # required by contract; the operation is idempotent by itself (sets the time once)
    uid = session['user_id']
    before = _rxs().get_for_patient(uid, rx_id).get('dispense_requested_at')
    rx = _rxs().request_pharmacy(uid, rx_id)
    if not before:  # a replay changes nothing and is not audited again
        audit(uid, 'rx_send_to_desk', 'prescription', rx_id)
    db.session.commit()
    return jsonify(success=True, dispense_requested_at=iso(rx.dispense_requested_at))


@rx_patient_bp.route('/patient/api/prescriptions/consent', methods=['POST'])
@prescriptions_required
@login_required
@patient_required
@service_errors
def consent():
    value = json_body().get('consent')
    if not isinstance(value, bool):
        raise ServiceError('field_invalid', 422, fields={'consent': 'Send true or false.'})
    uid = session['user_id']
    _consent().set_erx_consent(uid, value)
    db.session.commit()
    return jsonify(success=True, consent=_consent().erx_status(uid))


# ---------- data for other patient pages ----------

def dashboard_context(user_id):
    """Extra context for the patient dashboard: the prescriptions widget and the care-team card.

    The widget is None when the feature is off or the service is unavailable; the dashboard must never fail on it.
    """
    from utils.feature_flags import prescriptions_enabled
    widget = None
    if prescriptions_enabled():
        try:
            rows, meta = _rxs().list_for_patient(user_id, 'active', 1, 50)
            expiries = sorted(r['valid_until'] for r in rows if r.get('valid_until'))
            widget = {'count': meta['total'], 'next_expiry': expiries[0] if expiries else None}
        except Exception as exc:  # noqa: BLE001  (class name only: never log patient text)
            logger.warning('prescriptions widget failed: %s', type(exc).__name__)
    team = (db.session.query(User.name, User.provider_type).join(ProviderPatient, ProviderPatient.provider_id == User.id)
            .filter(ProviderPatient.patient_id == user_id, User.role == 'provider').order_by(User.name).all())
    return {'rx_widget': widget, 'rx_text': rx_text,
            'care_team': [{'name': n, 'type': 'Doctor' if t == 'doctor' else 'Counsellor'} for n, t in team]}
