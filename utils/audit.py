"""Access/change audit trail. Store ids and short codes only, never patient text."""
import logging

from core.extensions import db
from models import AuditLog

logger = logging.getLogger(__name__)


def audit(actor_id, action, target_type=None, target_id=None, **meta):
    """Add an AuditLog row to the CURRENT transaction (caller commits). Never raises into the request."""
    try:
        db.session.add(AuditLog(actor_id=actor_id, action=action, target_type=target_type,
                                target_id=target_id, meta=meta or None))
    except Exception:  # an audit failure must not break a patient-facing action
        logger.warning("audit write failed for action=%s", action)
