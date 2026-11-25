"""Provider blueprint, split by domain (dashboard/crisis, appointments, analytics, AI documentation,
wellness report, CLI). Shared query/scoping helpers live in helpers.py and are re-exported here so
`from routes.provider import scoped_patient_or_404` / `institution_summary` (used by
routes/provider_followups.py, routes/provider_meds.py and some tests) keeps working unchanged.
"""
from flask import Blueprint

provider_bp = Blueprint('provider', __name__, url_prefix='/provider', cli_group=None)

from .helpers import (all_institution_patients, assigned_patients, can_handle_appointment,  # noqa: E402,F401
                      institution_patients, institution_summary, latest_by_user, latest_scores,
                      min_group, normalize_institution_name, risk_from_band, scoped_patient_or_404,
                      severity_band, unacknowledged_crises)

from . import dashboard, appointments, analytics, documentation, wellness, cli  # noqa: E402,F401

from routes.provider_rx import register as _register_rx
_register_rx(provider_bp)  # prescribing routes (design 5.3)
