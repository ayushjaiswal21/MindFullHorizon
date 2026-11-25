"""Backward-compat shim: real implementation moved to core/decorators.py.

Kept so the many existing ``from decorators import ...`` call sites across
routes/, services/, utils/ and tests/ keep working unchanged.
"""
from core.decorators import (  # noqa: F401
    login_required, api_login_required, role_required,
    patient_required, provider_required, prescriptions_required,
    can_join_telehealth, roles_required, admin_required,
    pharmacy_desk_required, doctor_provider_required, verified_prescriber_required,
)
