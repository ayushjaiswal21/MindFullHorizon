"""Read-only JSON lookups for the prescribe screen (design 5.3, 5.5): dashboard, patients, eligibility, medicines."""
import logging

from flask import g, jsonify, request
from sqlalchemy import func, or_

from decorators import doctor_provider_required, login_required, prescriptions_required, verified_prescriber_required
from extensions import limiter
from models import Medicine, ProviderPatient, User
from routes.provider_rx._common import limits, patient_or_404
from services import prescriptions
from services.db_util import inst_match
from services.errors import MESSAGES
from services.http import iso, service_errors
from services.roles import norm_inst
from services.rx_rules import allowed_lists, medicine_block_code
from utils.pagination import paginate

logger = logging.getLogger(__name__)
MIN_QUERY, MAX_RESULTS = 2, 20


def _like(text):
    return '%' + text.lower().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'


def availability_badges(institution_key, medicine_ids):
    """{medicine_id: 'in_stock' | 'low' | 'out'}, never a number. Falls back to 'out' while stock is unavailable."""
    out = {i: 'out' for i in medicine_ids}
    if not medicine_ids:
        return out
    try:
        from services.inventory import availability
        found = availability(institution_key, [(i, 0) for i in medicine_ids])
        out.update({i: found[i]['status'] for i in medicine_ids if i in found})
    except Exception as exc:  # noqa: BLE001  (ImportError while stock is not installed; class name only in the log)
        logger.warning('availability unavailable: %s', type(exc).__name__)
    return out


def _item(m, allowed, badge):
    code = medicine_block_code(m, allowed)
    return {'id': m.id, 'label': m.label, 'generic_name': m.generic_name, 'brand_name': m.brand_name,
            'strength': m.strength, 'form': m.form, 'route': m.route, 'tpg_list': m.tpg_list,
            'prescribable': code is None, 'blocked_code': code, 'blocked_text': MESSAGES[code] if code else None,
            'availability': badge}


def init(bp):
    @bp.route('/api/rx/dashboard')
    @prescriptions_required
    @login_required
    @doctor_provider_required  # pending and suspended doctors need the verification banner too
    @service_errors
    def rx_api_dashboard():
        return jsonify(prescriptions.doctor_dashboard(g.actor.id))

    @bp.route('/api/rx/patients')
    @prescriptions_required
    @login_required
    @verified_prescriber_required
    def rx_api_patients():
        q = (request.args.get('q') or '').strip()[:100]
        query = (User.query.join(ProviderPatient, ProviderPatient.patient_id == User.id)
                 .filter(ProviderPatient.provider_id == g.actor.id, User.role == 'patient',
                         inst_match(User.institution, norm_inst(g.actor.institution))))
        if q:
            query = query.filter(func.lower(User.name).like(_like(q), escape='\\'))
        rows, meta = paginate(query.order_by(User.name, User.id), default=20)
        return jsonify(success=True, items=[{'id': u.id, 'name': u.name} for u in rows], meta=meta)

    @bp.route('/api/rx/eligibility')
    @prescriptions_required
    @login_required
    @verified_prescriber_required
    def rx_api_eligibility():
        patient = patient_or_404(request.args.get('patient_id', type=int) or 0)
        el = prescriptions.consult_eligibility(g.actor.id, patient.id, request.args.get('attest') == '1')
        consult = ({'appointment_id': el.consult_appointment_id, 'modality': el.modality,
                    'started_at': iso(el.started_at)} if el.consult_appointment_id else None)
        return jsonify(success=True, patient={'id': patient.id, 'name': patient.name}, consult=consult,
                       tpg_context=el.tpg_context, allowed_lists=sorted(el.allowed_lists),
                       follow_up_possible=el.follow_up_possible, erx_consent=el.erx_consent,
                       limits=limits(el.tpg_context), blockers=el.blockers)

    @bp.route('/api/rx/medicines')
    @limiter.limit('60 per minute')
    @prescriptions_required
    @login_required
    @verified_prescriber_required
    def rx_api_medicines():
        q = (request.args.get('q') or '').strip()[:60]
        if len(q) < MIN_QUERY:
            return jsonify(success=True, items=[])
        allowed = allowed_lists('first')
        if request.args.get('patient_id', type=int):
            patient = patient_or_404(request.args.get('patient_id', type=int))
            allowed = prescriptions.consult_eligibility(g.actor.id, patient.id).allowed_lists
        like = _like(q)
        meds = (Medicine.query.filter(Medicine.active.is_(True), or_(Medicine.generic_key.like(like, escape='\\'),
                                                                     func.lower(Medicine.brand_name).like(like, escape='\\')))
                .order_by(Medicine.generic_key, Medicine.strength).limit(MAX_RESULTS).all())
        badges = availability_badges(norm_inst(g.actor.institution), [m.id for m in meds])
        return jsonify(success=True, items=[_item(m, allowed, badges[m.id]) for m in meds])
