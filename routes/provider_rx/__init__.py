"""Prescribing routes of the provider blueprint (design 5.3).

`routes/provider.py` calls `register(provider_bp)` as its last line. Each module in this package defines `init(bp)`
that decorates its views with `bp.route`. This file also adds the `ist` Jinja filter and the `rx_section` context
processor that drives the Prescribing section of the provider dashboard.
"""
from flask import g, session

from utils.rx_format import rx_datetime


def _rx_section():
    """{'show', 'state', 'review_due_at'} for a logged-in doctor, else None (counsellors, patients, admins, flag off)."""
    from core.extensions import db
    from models import User
    from services import prescriber
    from services.http import iso
    from utils.feature_flags import prescriptions_enabled
    if session.get('user_role') != 'provider' or not prescriptions_enabled():
        return None
    if hasattr(g, '_rx_section'):
        return g._rx_section
    g._rx_section = None
    user = db.session.get(User, session.get('user_id') or 0)
    if user is not None and user.role == 'provider' and user.provider_type == 'doctor' and user.deactivated_at is None:
        p = prescriber.get_profile(user.id)
        g._rx_section = {'show': True, 'state': prescriber.state_of(p), 'review_due_at': iso(p.review_due_at) if p else None}
    return g._rx_section


def register(bp):
    from routes.provider_rx import api_drafts, api_issue, api_lookup, consults, pages, profile
    bp.add_app_template_filter(rx_datetime, 'ist')
    bp.app_context_processor(lambda: {'rx_section': _rx_section()})
    for module in (pages, profile, consults, api_lookup, api_drafts, api_issue):
        module.init(bp)
