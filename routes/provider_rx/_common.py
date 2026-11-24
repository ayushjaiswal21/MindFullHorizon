"""Helpers shared by the prescribing routes: page config, texts, scoped patient lookup."""
from flask import abort, g, url_for

from services import config
from services.prescriptions._common import assigned_patient
from services.rx_rules import limits_cfg, max_days
from utils import rx_text


def rx_texts():
    """Fixed wording for the prescribe page (design 3.5, 3.6, 4.4), one dict for the template."""
    return {'consent': rx_text.ERX_CONSENT_TEXT, **rx_text.SAFETY_LINES}


def limits(tpg_context='first'):
    cfg = limits_cfg()
    return {'max_items': cfg['max_items'], 'max_days': max_days(tpg_context, cfg),
            'expiry_days_max': config.rx_expiry_days()}


def page_config():
    """URLs for the interactive pages (read by JS from a JSON script block; no Jinja in static JS)."""
    return {'patients': url_for('provider.rx_api_patients'), 'eligibility': url_for('provider.rx_api_eligibility'),
            'medicines': url_for('provider.rx_api_medicines'), 'drafts': url_for('provider.rx_api_create'),
            'list': url_for('provider.rx_api_list'), 'dashboard': url_for('provider.rx_api_dashboard'),
            'detail_template': url_for('provider.rx_detail', rx_id=0), 'prescribe': url_for('provider.rx_prescribe'),
            'appointments': url_for('provider.provider_appointments'), 'profile': url_for('provider.rx_profile')}


def patient_or_404(patient_id):
    """The assigned patient of the logged-in doctor, else 404 (never 403: existence does not leak)."""
    patient = assigned_patient(g.actor, patient_id)
    if patient is None:
        abort(404)
    return patient
