"""Prescriber verification service (design 2.3): states, checks, institution scope, audit, bookable staff."""
from datetime import timedelta

import pytest

from core.extensions import db
from models import AuditLog, PrescriberProfile, User
from services import prescriber
from services.errors import ServiceError
from services.roles import bookable_staff
from utils.timeutil import utcnow

CHECKS = {k: True for k in prescriber.CHECK_KEYS}
NOTE = 'NMR search 2026-11-24, found, name and year match'


@pytest.fixture
def doc(app, make_user):
    """(doctor id, admin id) in one institution, doctor profile pending."""
    d = make_user('provider', provider_type='doctor')
    a = make_user('admin')
    with app.app_context():
        p = prescriber.submit_profile(d, 'MH 12345', 'Maharashtra Medical Council', 2011, 'Psychiatry')
        db.session.commit()
        return d, a, p.id


def _profile(pid):
    return db.session.get(PrescriberProfile, pid)


def test_submit_pending_normalises(app, doc):
    with app.app_context():
        p = _profile(doc[2])
        assert (p.status, p.registration_number, p.council_key) == ('pending', 'MH12345', 'maharashtra medical council')
        assert not prescriber.is_verified(p)


def test_verify_requires_all_checks_and_note(app, doc):
    d, a, pid = doc
    with app.app_context():
        for checks in ({}, dict(CHECKS, works_here=False), None):
            with pytest.raises(ServiceError) as e:
                prescriber.verify(pid, a, checks, NOTE)
            assert e.value.code == 'checks_incomplete'
        with pytest.raises(ServiceError) as e:
            prescriber.verify(pid, a, CHECKS, 'short')
        assert e.value.code == 'note_required'
        p = prescriber.verify(pid, a, CHECKS, NOTE)
        db.session.commit()
        assert p.status == 'verified' and p.verified_by == a and p.review_due_at > utcnow() + timedelta(days=360)
        assert prescriber.require_verified(d).id == pid


def test_verify_other_institution_is_404(app, doc, make_user):
    other = make_user('admin', institution='Another College')
    with app.app_context():
        with pytest.raises(ServiceError) as e:
            prescriber.verify(doc[2], other, CHECKS, NOTE)
        assert e.value.http == 404
        assert prescriber.queue('another college')[0] == []


def test_edit_registration_resets_to_pending_but_specialisation_does_not(app, doc):
    d, a, pid = doc
    with app.app_context():
        prescriber.verify(pid, a, CHECKS, NOTE)
        prescriber.submit_profile(d, 'MH12345', 'Maharashtra Medical Council', 2011, 'Child psychiatry')
        assert _profile(pid).status == 'verified'
        prescriber.submit_profile(d, 'MH99999', 'Maharashtra Medical Council', 2011, 'Child psychiatry')
        p = _profile(pid)
        assert p.status == 'pending' and p.verified_at is None
        with pytest.raises(ServiceError):
            prescriber.require_verified(d)
        assert AuditLog.query.filter_by(action='prescriber_edit_reset').count() == 1


def test_suspend_then_not_verified_and_reinstate(app, doc):
    d, a, pid = doc
    with app.app_context():
        prescriber.verify(pid, a, CHECKS, NOTE)
        prescriber.suspend(pid, a, 'Complaint received, under review')
        with pytest.raises(ServiceError) as e:
            prescriber.require_verified(d)
        assert e.value.code == 'prescriber_not_verified' and e.value.http == 403
        with pytest.raises(ServiceError):
            prescriber.reinstate(pid, a, {}, NOTE)  # checklist again
        prescriber.reinstate(pid, a, CHECKS, NOTE)
        assert prescriber.require_verified(d)


def test_lapsed_review_blocks_but_status_stays_verified(app, doc):
    d, a, pid = doc
    with app.app_context():
        prescriber.verify(pid, a, CHECKS, NOTE)
        p = _profile(pid)
        p.review_due_at = utcnow() - timedelta(days=1)
        db.session.commit()
        assert p.status == 'verified' and prescriber.state_of(p) == 'lapsed'
        with pytest.raises(ServiceError):
            prescriber.require_verified(d)
        prescriber.verify(pid, a, CHECKS, NOTE)  # a lapsed profile can be re-checked
        assert prescriber.require_verified(d)


def test_duplicate_registration_blocked_and_rejected_can_resubmit(app, doc, make_user):
    d, a, pid = doc
    other = make_user('provider', provider_type='doctor')
    with app.app_context():
        with pytest.raises(ServiceError) as e:
            prescriber.submit_profile(other, 'mh12345', 'maharashtra  medical council', 2012)
        assert e.value.code == 'registration_in_use'
        prescriber.reject(pid, a, 'Not found in the register')
        assert _profile(pid).status == 'rejected'
        prescriber.submit_profile(other, 'MH12345', 'Maharashtra Medical Council', 2012)  # the rejected one frees the number
        db.session.commit()
        prescriber.submit_profile(d, 'MH12346', 'Maharashtra Medical Council', 2011)  # rejected doctor corrects it
        assert _profile(pid).status == 'pending'


def test_field_limits(app, make_user):
    d = make_user('provider', provider_type='doctor')
    with app.app_context():
        for args in (('ab', 'Council', 2011), ('MH12345', 'x', 2011), ('MH12345', 'Council', 1949),
                     ('MH12345', 'Council', 'abc'), ('MH 12$45', 'Council', 2011)):
            with pytest.raises(ServiceError) as e:
                prescriber.submit_profile(d, *args)
            assert e.value.code == 'validation' and e.value.fields


def test_every_transition_audited_with_from_to(app, doc):
    d, a, pid = doc
    with app.app_context():
        prescriber.verify(pid, a, CHECKS, NOTE)
        prescriber.suspend(pid, a, 'Complaint received, under review')
        prescriber.reinstate(pid, a, CHECKS, NOTE)
        db.session.commit()
        rows = AuditLog.query.filter(AuditLog.action.like('prescriber_%')).order_by(AuditLog.id).all()
        assert [r.action for r in rows] == ['prescriber_submit', 'prescriber_verify', 'prescriber_suspend',
                                            'prescriber_reinstate']
        assert rows[2].meta == {'from': 'verified', 'to': 'suspended'}
        assert NOTE not in str([r.meta for r in rows])  # free text is not copied into audit meta


def test_unverified_doctor_not_bookable(app, doc, make_user):
    d, a, pid = doc
    c = make_user('provider')
    with app.app_context():
        assert [u.id for u in bookable_staff('Test University')] == [c]
        prescriber.verify(pid, a, CHECKS, NOTE)
        db.session.commit()
        assert {u.id for u in bookable_staff('Test University')} == {c, d}
        assert bookable_staff('Other') == [] and bookable_staff('') == []
        db.session.get(User, d).deactivated_at = utcnow()
        db.session.commit()
        assert [u.id for u in bookable_staff('Test University')] == [c]
