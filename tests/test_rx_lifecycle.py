"""Prescription services: cancel, amend, immutability, expiry (design 3.8)."""
from datetime import timedelta

import pytest

from extensions import db
from models import AuditLog, Prescription
from services import prescriptions as P
from tests.rx_support import KEY, code_of, issue, issued, item, ready_draft, setup
from utils.timeutil import ist_day_bounds, to_ist_date, utcnow


@pytest.fixture
def s(app, make_user, make_doctor):
    return setup(app, make_user, make_doctor, meds=("A", "B", "C"))


def test_cancel_reasons_and_not_cancellable(app, s):
    rx = issued(app, s)
    assert code_of(app, lambda: P.cancel(s["doctor"], rx, "bogus")) == "field_invalid"
    with app.app_context():
        P.cancel(s["doctor"], rx, "error")
        db.session.commit()
        r = db.session.get(Prescription, rx)
        assert (r.status, r.cancel_reason, r.cancelled_by) == ("cancelled", "error", s["doctor"])
    assert code_of(app, lambda: P.cancel(s["doctor"], rx, "error")) == "not_cancellable"


def test_cancel_partial_keeps_dispensed(app, s):
    rx = issued(app, s)
    with app.app_context():
        r = db.session.get(Prescription, rx)
        r.status, r.items[0].quantity_dispensed = "partially_dispensed", 3
        db.session.commit()
        P.cancel(s["doctor"], rx, "clinical_change")
        db.session.commit()
        r = db.session.get(Prescription, rx)
        assert r.status == "cancelled" and r.items[0].quantity_dispensed == 3


def test_amend_links_and_cancels_old_on_issue(app, s):
    old = issued(app, s)
    with app.app_context():
        new = P.amend(s["doctor"], old)
        db.session.commit()
        assert new.amends_id == old and len(new.items) == 1 and db.session.get(Prescription, old).status == "issued"
        assert P.amend(s["doctor"], old).id == new.id  # a second press reuses the open draft
        new_id = new.id
    issue(app, s, new_id, key="amend-key-0001")
    with app.app_context():
        o = db.session.get(Prescription, old)
        assert (o.status, o.cancel_reason) == ("cancelled", "amended")


def test_amend_aborts_if_old_dispensed(app, s):
    old = issued(app, s)
    with app.app_context():
        new = P.amend(s["doctor"], old)
        db.session.commit()
        new_id = new.id
        db.session.get(Prescription, old).status = "dispensed"
        db.session.commit()
    assert code_of(app, lambda: P.issue(s["doctor"], new_id, "amend-key-0002", [])) == "amended_rx_changed"
    with app.app_context():
        assert db.session.get(Prescription, new_id).status == "draft"


def test_issued_is_immutable(app, s):
    rx = issued(app, s)
    with app.app_context():
        v = db.session.get(Prescription, rx).row_version
    assert code_of(app, lambda: P.save_draft(s["doctor"], rx, {"diagnosis": "changed"}, v)) == "not_draft"
    assert code_of(app, lambda: P.delete_draft(s["doctor"], rx)) == "not_draft"


def test_effective_status_expired_without_job_then_job_persists(app, s):
    rx = issued(app, s)
    with app.app_context():
        r = db.session.get(Prescription, rx)
        r.expiry_date = utcnow() - timedelta(minutes=1)
        db.session.commit()
        assert r.status == "issued" and P.effective_status(r) == "expired"
        assert P.public_status(r.number)["status"] == "expired"
        assert P.expire_due() == 1
        db.session.commit()
        assert db.session.get(Prescription, rx).status == "expired"


def test_no_free_text_in_audit_or_logs(app, s, caplog):
    marker = "SECRETMARKER123"
    rx = ready_draft(app, s["doctor"], s["patient"], s["meds"][:1], diagnosis=marker, allergies_status="listed",
                     allergies=marker, items=[item(s["meds"][0], instructions=marker, dose_text=marker)])
    caplog.set_level("DEBUG")
    issue(app, s, rx)
    with app.app_context():
        assert marker not in str([a.meta for a in AuditLog.query.all()])
    assert marker not in caplog.text
