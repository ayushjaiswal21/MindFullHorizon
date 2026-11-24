"""Admin screens and JSON: staff, verification, audit viewer, annual report, messages, dashboard, no student identity."""
from datetime import timedelta

import pytest

from extensions import db
from models import AuditLog, ContactMessage, CrisisEvent, PrescriberProfile, User
from services import prescriber
from utils.timeutil import utcnow

CHECKS = {k: True for k in prescriber.CHECK_KEYS}
NOTE = 'NMR search 2026-11-24, found, name and year match'


def _json(r):
    assert r.status_code == 200, r.data[:300]
    return r.get_json()


def test_staff_list_and_toggle(app, admin_client, make_user, make_doctor):
    c, _ = admin_client
    cons, doc = make_user('provider', name='Casey Counsellor'), make_doctor('pending')
    foreign = make_user('provider', institution='Other College')
    make_user('patient', name='Pat Student')
    body = c.get('/admin/staff').data.decode()
    assert 'Casey Counsellor' in body and 'Pat Student' not in body
    assert c.post(f'/admin/api/staff/{foreign}/deactivate').status_code == 404  # other institution: not found
    assert c.post(f'/admin/api/staff/{cons}/deactivate').get_json()['deactivated'] is True
    with app.app_context():
        assert db.session.get(User, cons).deactivated_at is not None
        assert AuditLog.query.filter_by(action='staff_deactivate', target_id=cons).count() == 1
    assert 'Casey Counsellor' not in c.get('/admin/staff?status=active').data.decode()
    assert _json(c.post(f'/admin/api/staff/{cons}/reactivate'))['deactivated'] is False
    assert c.post(f'/admin/api/staff/{doc}/deactivate').status_code == 200
    assert 'Doctor' in c.get('/admin/staff?type=doctor').data.decode()


def test_staff_cannot_target_a_patient(app, admin_client, make_user):
    pid = make_user('patient')
    assert admin_client[0].post(f'/admin/api/staff/{pid}/deactivate').status_code == 404


def test_verification_flow_over_api(app, admin_client, make_doctor):
    c, _ = admin_client
    doc = make_doctor('pending')
    with app.app_context():
        pid = PrescriberProfile.query.filter_by(user_id=doc).one().id
    assert c.get('/admin/verification').status_code == 200
    assert _json(c.get('/admin/api/verification?status=pending'))['meta']['total'] == 1
    assert c.get(f'/admin/verification/{pid}').status_code == 200
    r = c.post(f'/admin/api/verification/{pid}/verify', json={'checks': {}, 'note': NOTE})
    assert r.status_code == 422 and r.get_json()['error'] == 'checks_incomplete'
    r = c.post(f'/admin/api/verification/{pid}/verify', json={'checks': CHECKS, 'note': NOTE})
    assert r.get_json()['state'] == 'verified'
    assert c.post(f'/admin/api/verification/{pid}/verify', json={'checks': CHECKS, 'note': NOTE}).status_code == 409
    assert c.post(f'/admin/api/verification/{pid}/suspend', json={'note': 'Complaint under review'}).get_json()['status'] == 'suspended'
    assert c.post(f'/admin/api/verification/{pid}/reinstate', json={'checks': CHECKS, 'note': NOTE}).status_code == 200


def test_verification_other_institution_404(app, make_user, make_doctor):
    from tests.conftest import _login_as
    doc = make_doctor('pending', institution='Elsewhere University')
    other = app.test_client()
    _login_as(other, app, make_user('admin'))
    with app.app_context():
        pid = PrescriberProfile.query.filter_by(user_id=doc).one().id
    assert other.get(f'/admin/verification/{pid}').status_code == 404
    assert other.post(f'/admin/api/verification/{pid}/reject', json={'note': 'x' * 12}).status_code == 404


def test_audit_scope_range_and_self_audit(app, admin_client, make_user):
    c, aid = admin_client
    other_admin = make_user('admin', institution='Other College')
    patient = make_user('patient', name='Hidden Student')
    with app.app_context():
        from utils.audit import audit
        audit(aid, 'stock_receive', 'inventory_batch', 5, delta=3)
        audit(other_admin, 'stock_receive', 'inventory_batch', 6)
        audit(patient, 'erx_consent_give', 'user', patient)
        audit(aid, 'view_patient', 'user', patient, patient_id=patient)
        db.session.add(AuditLog(actor_id=aid, action='old_event', created_at=utcnow() - timedelta(days=200)))
        db.session.commit()
    d = _json(c.get('/admin/api/audit'))
    actions = [(r['action'], r['target_id']) for r in d['items']]
    assert ('stock_receive', 5) in actions and ('stock_receive', 6) not in actions
    assert all(r['action'] != 'erx_consent_give' for r in d['items'])  # patients are never actors
    assert ('view_patient', None) in actions  # the student id is hidden
    assert 'Hidden Student' not in c.get('/admin/audit').data.decode()
    wide = _json(c.get('/admin/api/audit?from=2000-01-01'))
    assert all(r['action'] != 'old_event' for r in wide['items'])  # range is capped at 92 days
    with app.app_context():
        assert AuditLog.query.filter_by(action='view_audit_log', actor_id=aid).count() >= 3


def test_messages_read_flag_and_audit(app, admin_client):
    c, aid = admin_client
    with app.app_context():
        m = ContactMessage(name='Sam', email='sam@x.org', subject='Hello', message='Body text here')
        db.session.add(m)
        db.session.commit()
        mid = m.id
    assert 'Hello' in c.get('/admin/messages').data.decode()
    assert 'Body text here' in c.get(f'/admin/messages?id={mid}').data.decode()
    assert c.post(f'/admin/api/messages/{mid}/read').status_code == 200
    assert c.post('/admin/api/messages/999/read').status_code == 404
    with app.app_context():
        assert db.session.get(ContactMessage, mid).status == 'read'
        assert AuditLog.query.filter_by(action='view_contact_message', actor_id=aid).count() == 2


def test_dashboard_counts_and_k_suppression(app, admin_client, make_user, make_doctor):
    c, _ = admin_client
    make_user('provider')
    make_doctor('pending')
    make_doctor('verified')
    for _ in range(2):
        make_user('patient')
    d = _json(c.get('/admin/api/dashboard'))
    assert d['staff'] == {'counsellors': 1, 'doctors_verified': 1, 'doctors_pending': 1}
    assert d['pending_verifications'] == 1 and d['patients']['total'] is None  # 2 students: below K
    for _ in range(4):
        make_user('patient')
    assert _json(c.get('/admin/api/dashboard'))['patients']['total'] == 6
    assert c.get('/admin/dashboard').status_code == 200


def test_crisis_overdue_count_hidden_below_k(app, admin_client, make_user):
    c, _ = admin_client
    pids = [make_user('patient') for _ in range(6)]
    with app.app_context():
        old = utcnow() - timedelta(hours=2)
        db.session.add(CrisisEvent(user_id=pids[0], source='chat', severity=3, reason='kw', created_at=old))
        db.session.commit()
    d = _json(c.get('/admin/api/dashboard'))['crisis_overdue']
    assert d == {'any': True, 'count': None}
    with app.app_context():
        for p in pids[1:5]:
            db.session.add(CrisisEvent(user_id=p, source='chat', severity=3, reason='kw', created_at=old))
        db.session.commit()
    assert _json(c.get('/admin/api/dashboard'))['crisis_overdue'] == {'any': True, 'count': 5}


def _metric(report, name):
    return next(m for s in report['sections'] for m in s['metrics'] if m['name'] == name)


def test_annual_k_suppression_and_csv_columns(app, admin_client, make_user):
    from services import annual_report
    from utils.timeutil import ist_today
    c, _ = admin_client
    for _ in range(2):
        make_user('patient')
    with app.app_context():
        rep = annual_report.build('test university', ist_today().year)
        m = _metric(rep, 'Students registered by the end of the year')
        assert m['value'] is None and m['suppressed']
    for _ in range(4):
        make_user('patient')
    with app.app_context():
        assert _metric(annual_report.build('test university', ist_today().year),
                       'Students registered by the end of the year')['value'] == 6
    r = c.get('/admin/annual-report.csv')
    assert r.status_code == 200 and r.mimetype == 'text/csv' and 'attachment' in r.headers['Content-Disposition']
    lines = r.data.decode().splitlines()
    assert lines[0] == 'section,metric,value,note'
    assert any('suppressed (fewer than 5 people)' in line for line in lines)  # empty cells stay hidden
    assert c.get('/admin/annual-report?year=1900').status_code == 200  # an unknown year falls back
    with app.app_context():
        assert AuditLog.query.filter_by(action='export_annual_report').count() == 2


def test_no_patient_identity_in_any_admin_json_or_html(app, admin_client, desk_client, make_user):
    """Walk every admin GET page and API as both admin kinds with student names in the database."""
    from tests.test_admin_routes import _admin_rules
    names = ['Zelda Studentova', 'Quentin Learner']
    pids = [make_user('patient', name=n, email=f'{n.split()[0].lower()}@students.test') for n in names]
    make_user('provider', name='Casey Counsellor')
    with app.app_context():
        from utils.audit import audit
        audit(pids[0], 'erx_consent_give', 'user', pids[0])
        audit(admin_client[1], 'view_patient', 'user', pids[1], patient_id=pids[1])
        db.session.commit()
    for client, _ in (admin_client, desk_client):
        for method, path in _admin_rules(app):
            if method != 'GET' or path == '/admin/login' or 'dispensing/1' in path:  # the desk exception is tested apart
                continue
            body = client.get(path).data.decode()
            for needle in names + ['zelda@students.test', 'quentin@students.test']:
                assert needle not in body, (path, needle)
