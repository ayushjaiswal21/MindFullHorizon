"""Roles, signup by provider type, admin CLI, login rules, decorators (design 1.2 to 1.5)."""
import pytest

from extensions import db
from models import AuditLog, PrescriberProfile, User
from tests.conftest import PASSWORD

BASE = dict(name='Dr Test', email='doc@test.local', password=PASSWORD, confirm_password=PASSWORD,
            institution='Test University', consent='on', age_confirm='on')
DOC = dict(BASE, role='provider', provider_type='doctor', invite_code='doctor-secret-1', registration_number='MH-12345',
           council='Maharashtra Medical Council', registered_since='2011', specialisation='Psychiatry')


@pytest.fixture(autouse=True)
def codes(monkeypatch):
    monkeypatch.setenv('PROVIDER_INVITE_CODE', 'counsellor-secret-1')
    monkeypatch.setenv('DOCTOR_INVITE_CODE', 'doctor-secret-1')


def _signup(client, **over):
    return client.post('/signup', data=dict(DOC, **over))


def test_signup_counsellor_needs_provider_code(app, client):
    r = client.post('/signup', data=dict(BASE, role='provider', invite_code='wrong'))
    assert b'Provider accounts need a valid invite code' in r.data
    client.post('/signup', data=dict(BASE, role='provider', invite_code='counsellor-secret-1'))
    with app.app_context():
        assert User.query.one().provider_type == 'counsellor' and PrescriberProfile.query.count() == 0


def test_signup_doctor_needs_doctor_code_and_creates_pending_profile(app, client):
    r = _signup(client, invite_code='wrong')
    assert b'Doctor accounts need a valid invite code' in r.data
    with app.app_context():
        assert User.query.count() == 0 and PrescriberProfile.query.count() == 0
    assert _signup(client).status_code == 302
    with app.app_context():
        u = User.query.one()
        p = PrescriberProfile.query.one()
        assert (u.role, u.provider_type, p.status, p.registration_number) == ('provider', 'doctor', 'pending', 'MH-12345')
        assert AuditLog.query.filter_by(action='prescriber_submit').count() == 1


def test_codes_never_cross(app, client):
    assert b'Doctor accounts need a valid invite code' in _signup(client, invite_code='counsellor-secret-1').data
    r = client.post('/signup', data=dict(BASE, role='provider', provider_type='counsellor', invite_code='doctor-secret-1'))
    assert b'Provider accounts need a valid invite code' in r.data
    with app.app_context():
        assert User.query.count() == 0


def test_equal_codes_disable_doctor_signup(app, client, monkeypatch):
    monkeypatch.setenv('DOCTOR_INVITE_CODE', 'counsellor-secret-1')
    assert b'Doctor accounts need a valid invite code' in _signup(client, invite_code='counsellor-secret-1').data
    with app.app_context():
        assert User.query.count() == 0


@pytest.mark.parametrize('field,value', [('registration_number', 'a'), ('council', 'x'), ('registered_since', '1900'),
                                          ('registered_since', 'abc')])
def test_doctor_field_limits(app, client, field, value):
    r = _signup(client, **{field: value})
    assert r.status_code == 200
    with app.app_context():
        assert User.query.count() == 0 and PrescriberProfile.query.count() == 0
    assert PASSWORD.encode() not in r.data and b'doctor-secret-1' not in r.data


def test_signup_admin_and_unknown_roles_rejected(app, client):
    for role in ('admin', 'superuser', ''):
        client.post('/signup', data=dict(BASE, role=role, invite_code='counsellor-secret-1'))
    with app.app_context():
        assert User.query.count() == 0


def test_login_admin_on_main_form_fails_generic(app, client, make_user):
    make_user('admin', email='a@test.local')
    r = client.post('/login', data={'email': 'a@test.local', 'password': PASSWORD, 'role': 'admin'})
    assert b'Invalid email, password or role' in r.data
    r = client.post('/login', data={'email': 'a@test.local', 'password': PASSWORD, 'role': 'provider'})
    assert b'Invalid email, password or role' in r.data


def test_deactivated_user_cannot_login(app, client, make_user):
    from utils.timeutil import utcnow
    uid = make_user('provider', email='p@test.local')
    with app.app_context():
        db.session.get(User, uid).deactivated_at = utcnow()
        db.session.commit()
    r = client.post('/login', data={'email': 'p@test.local', 'password': PASSWORD, 'role': 'provider'})
    assert b'Invalid email, password or role' in r.data


def test_deactivated_admin_session_dies(app, admin_client):
    from utils.timeutil import utcnow
    client, uid = admin_client
    assert client.get('/admin/dashboard').status_code == 200
    with app.app_context():
        db.session.get(User, uid).deactivated_at = utcnow()
        db.session.commit()
    assert client.get('/admin/dashboard').status_code == 302
    assert client.get('/admin/api/dashboard').status_code in (401, 403)


def test_google_cannot_sign_in_admin(app, make_user):
    import app as app_module
    make_user('admin', email='g@test.local')
    with app.app_context():
        db.session.get(User, User.query.one().id).google_id = 'gid-1'
        db.session.commit()

    class Resp:
        ok = True
        def json(self):
            return {'id': 'gid-1', 'email': 'g@test.local', 'name': 'G'}

    class Blueprint:
        class session:
            @staticmethod
            def get(_):
                return Resp()

    with app.test_request_context('/login/google/authorized'):
        from flask import session
        resp = app_module.google_logged_in(Blueprint, {'access_token': 'x'})
        assert resp.status_code == 302 and '/login' in resp.headers['Location']
        assert 'user_id' not in session


# ---- CLI ----

def _cli(app, *args, **kw):
    return app.test_cli_runner().invoke(args=list(args), **kw)


def test_create_admin_cli_prompts_and_audits(app):
    r = _cli(app, 'create-admin', '--email', 'Boss@Test.local', '--name', 'Boss', '--institution', 'Test University',
             '--pharmacy-desk', input=f'{PASSWORD}\n{PASSWORD}\n')
    assert r.exit_code == 0, r.output
    with app.app_context():
        u = User.query.one()
        assert (u.role, u.email, u.is_pharmacy_desk) == ('admin', 'boss@test.local', True) and u.check_password(PASSWORD)
        row = AuditLog.query.filter_by(action='admin_created').one()
        assert row.actor_id is None and row.target_id == u.id
    assert PASSWORD not in r.output


def test_create_admin_password_env_weak_and_existing(app, make_user, monkeypatch):
    monkeypatch.setenv('NEW_ADMIN_PW', PASSWORD)
    args = ('create-admin', '--email', 'e@test.local', '--name', 'E', '--institution', 'Test University',
            '--password-env', 'NEW_ADMIN_PW')
    assert _cli(app, *args).exit_code == 0
    assert 'already exists' in _cli(app, *args).output  # refuses an existing email
    monkeypatch.setenv('NEW_ADMIN_PW', 'weak')
    r = _cli(app, 'create-admin', '--email', 'w@test.local', '--name', 'W', '--institution', 'Test University',
             '--password-env', 'NEW_ADMIN_PW')
    assert r.exit_code != 0
    with app.app_context():
        assert User.query.filter_by(email='w@test.local').count() == 0


def test_create_admin_refuses_existing_patient_email_and_never_promotes(app, make_user):
    make_user('patient', email='p@test.local')
    r = _cli(app, 'create-admin', '--email', 'p@test.local', '--name', 'P', '--institution', 'X', input=f'{PASSWORD}\n{PASSWORD}\n')
    assert r.exit_code != 0
    with app.app_context():
        assert User.query.one().role == 'patient'


def test_other_cli_commands(app, make_user):
    make_user('admin', email='a@test.local')
    pid = make_user('provider', email='v@test.local')
    assert _cli(app, 'set-pharmacy-desk', '--email', 'a@test.local', '--on').exit_code == 0
    assert _cli(app, 'set-provider-type', '--email', 'v@test.local', '--type', 'doctor').exit_code == 0
    assert _cli(app, 'set-provider-type', '--email', 'a@test.local', '--type', 'doctor').exit_code != 0  # not a provider
    with app.app_context():
        assert User.query.filter_by(role='admin').one().is_pharmacy_desk
        assert db.session.get(User, pid).provider_type == 'doctor'
        assert PrescriberProfile.query.filter_by(user_id=pid, status='pending').count() == 1
        assert {a.action for a in AuditLog.query} >= {'admin_pharmacy_desk_set', 'provider_type_set'}


# ---- decorators ----

def test_counsellor_gets_404_on_prescribing_routes(provider_client):
    c, _ = provider_client
    for path in ('/provider/prescribe', '/provider/prescriptions', '/provider/prescribing-profile'):
        assert c.get(path).status_code == 404, path
    assert c.get('/provider/api/rx/dashboard').status_code == 404


def test_unverified_doctor_gets_403_json_and_denial_is_audited(app, make_doctor):
    from tests.conftest import _login_as
    c = app.test_client()
    uid = make_doctor('pending')
    _login_as(c, app, uid)
    r = c.get('/provider/api/rx/patients')
    assert r.status_code == 403 and r.get_json()['error'] == 'prescriber_not_verified'
    assert c.get('/provider/prescribe').status_code == 302
    with app.app_context():
        assert AuditLog.query.filter_by(action='denied').first().meta == {'code': 'not_verified'}


def test_suspension_blocks_next_request(app, doctor_client):
    c, uid = doctor_client
    assert c.get('/provider/api/rx/patients').status_code == 200
    with app.app_context():
        PrescriberProfile.query.filter_by(user_id=uid).one().status = 'suspended'
        db.session.commit()
    assert c.get('/provider/api/rx/patients').status_code == 403


def test_admin_without_desk_403_on_dispensing(admin_client, desk_client):
    assert admin_client[0].get('/admin/dispensing').status_code == 403
    assert admin_client[0].get('/admin/api/dispensing/queue').status_code == 403
    assert desk_client[0].get('/admin/dispensing').status_code == 200


def test_patient_cannot_reach_admin_or_prescribing(patient_client):
    c, _ = patient_client
    assert c.get('/admin/dashboard').status_code == 302
    assert c.get('/admin/api/dashboard').status_code == 403
    assert c.get('/provider/prescribe').status_code in (302, 403, 404)
    assert c.get('/provider/api/rx/dashboard').status_code in (401, 403, 404)


def test_account_delete_rules(app, admin_client, doctor_client):
    c, uid = admin_client
    r = c.post('/account/delete', data={'password': PASSWORD})
    assert r.status_code == 302
    with app.app_context():
        assert db.session.get(User, uid) is not None
