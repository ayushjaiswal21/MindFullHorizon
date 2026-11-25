"""Patient consent to receive e-prescriptions (design 3.6). Stored as ConsentRecord kinds, no schema change.

kind 'eprescription' is the grant and 'eprescription_off' the withdrawal, both at ERX_CONSENT_VERSION. Consent is
active when the newest of the two (by accepted_at) is the grant. A re-grant or re-withdrawal moves accepted_at forward
on the existing row because (user_id, kind, version) is unique.
"""
from datetime import timedelta

from core.extensions import db
from models import ConsentRecord
from services import config
from utils.audit import audit
from utils.timeutil import utcnow

GRANT, OFF = 'eprescription', 'eprescription_off'


def erx_status(patient_id):
    """{'active': bool, 'version': current version}. Only rows at the current version count."""
    version = config.erx_consent_version()
    rows = {r.kind: r.accepted_at for r in ConsentRecord.query.filter(
        ConsentRecord.user_id == patient_id, ConsentRecord.version == version, ConsentRecord.kind.in_((GRANT, OFF)))}
    grant, off = rows.get(GRANT), rows.get(OFF)
    return {'active': bool(grant and (off is None or grant > off)), 'version': version}


def set_erx_consent(patient_id, on):
    """Give or withdraw consent in the caller's transaction (the caller commits). Audited only when the state changes."""
    before = erx_status(patient_id)['active']
    if before == bool(on):
        return
    version, kind = config.erx_consent_version(), GRANT if on else OFF
    other = ConsentRecord.query.filter_by(user_id=patient_id, kind=OFF if on else GRANT, version=version).first()
    now = utcnow()
    if other and other.accepted_at >= now:  # a coarse clock must not tie with the opposite record: the newest decides
        now = other.accepted_at + timedelta(microseconds=1)
    row = ConsentRecord.query.filter_by(user_id=patient_id, kind=kind, version=version).first()
    if row:
        row.accepted_at = now
    else:
        db.session.add(ConsentRecord(user_id=patient_id, kind=kind, version=version, accepted_at=now))
    db.session.flush()
    audit(patient_id, 'erx_consent_give' if on else 'erx_consent_withdraw', 'user', patient_id, version=version)
