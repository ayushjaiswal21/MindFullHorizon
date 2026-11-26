"""Auth blueprint, split by domain (consent, login/signup/logout, account data rights). Shared
constants and the consent helpers live in consent.py and are re-exported here so
`from routes.auth import LOGIN_ERROR / is_strong_password / has_current_consent / needs_reconsent`
(used by routes/admin/auth.py, routes/google_oauth.py, routes/profile_onboarding.py,
services/admin_cli.py and tests/test_privacy.py) keeps working unchanged.
"""
from flask import Blueprint

auth_bp = Blueprint('auth', __name__)

from .consent import (CONSENT_KINDS, CONSENT_EXEMPT, consent_version, has_current_consent,  # noqa: E402,F401
                      needs_reconsent, add_consent_records)
from .login import LOGIN_ERROR, is_strong_password  # noqa: E402,F401
from .account import DELETE_PHRASE  # noqa: E402,F401

from . import consent, login, account  # noqa: E402,F401
