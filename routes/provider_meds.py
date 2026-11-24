"""Read-only medications panel for counsellors and doctors (docs/CLINICAL_DESIGN.md 5.3).

Shows the patient's active self-logged medicines and the item lines of active prescriptions (medicine, dose,
frequency, duration, status, prescribed by). Never diagnosis, allergies or prescription numbers. Only assigned
patients are reachable (404 otherwise) and every read is audited with a count, never text.
"""
from flask import Blueprint, jsonify, session

from decorators import login_required, provider_required
from extensions import db
from utils import rx_text
from utils.audit import audit

provider_meds_bp = Blueprint('provider_meds', __name__)


def panel_context(patient_id):
    """{'meds': {'self_logged': [...], 'prescriptions': [...]}, 'rx_text': module}. The caller has already scoped the patient.

    Audits `view_patient_meds` in the caller's transaction (the caller commits). Prescription lines are left out
    while the prescriptions feature is switched off.
    """
    from services.prescriptions import medication_lines_for_staff
    from utils.feature_flags import prescriptions_enabled
    meds = medication_lines_for_staff(patient_id)
    if not prescriptions_enabled():
        meds = dict(meds, prescriptions=[])
    audit(session['user_id'], 'view_patient_meds', 'user', patient_id,
          n=len(meds.get('self_logged', [])) + len(meds.get('prescriptions', [])))
    return {'meds': meds, 'rx_text': rx_text}


def rx_patient_ids(patient_ids):
    """Ids among `patient_ids` with an active prescription (one batched query); empty while the feature is off."""
    from utils.feature_flags import prescriptions_enabled
    if not patient_ids or not prescriptions_enabled():
        return set()
    from services.prescriptions import active_rx_patient_ids
    return set(active_rx_patient_ids(patient_ids))


@provider_meds_bp.route('/provider/api/patients/<int:patient_id>/medications')
@login_required
@provider_required
def api_list(patient_id):
    from routes.provider import scoped_patient_or_404  # imported late: routes.provider is large and loads first
    patient = scoped_patient_or_404(patient_id)
    ctx = panel_context(patient.id)
    db.session.commit()
    return jsonify(success=True, **ctx['meds'])
