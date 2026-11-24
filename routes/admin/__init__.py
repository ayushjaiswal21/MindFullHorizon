"""Admin blueprint (design 5.4). One module per screen group; each registers its routes on `admin_bp` at import."""
from flask import Blueprint

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# each module owns one screen group (see docs/CLINICAL_DESIGN.md 5.4); the import order does not matter
from routes.admin import (annual, audit_view, auth, catalogue, dashboard, dispensing, inventory,  # noqa: E402,F401
                          messages, reports, staff, verification)
