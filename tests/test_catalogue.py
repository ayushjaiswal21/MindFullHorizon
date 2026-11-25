"""Medicine catalogue: create, edit, four-eyes, uniqueness, routes (design 4.1, 4.12)."""
import pytest

from core.extensions import db
from models import AuditLog, Medicine
from services import catalogue
from services.errors import ServiceError
from tests.inv_helpers import client_for

BODY = {'generic_name': 'Testamol', 'strength': '10 mg', 'form': 'tablet', 'tpg_list': 'A'}


@pytest.fixture
def two_admins(app, make_user):
    return make_user('admin'), make_user('admin')


def _create(app, admin_id, **extra):
    with app.app_context():
        m = catalogue.create(admin_id, dict(BODY, **extra))
        db.session.commit()
        return m.id


def test_create_edit_deactivate(app, two_admins):
    a, _ = two_admins
    mid = _create(app, a)
    with app.app_context():
        m = db.session.get(Medicine, mid)
        assert (m.generic_key, m.brand_name, m.route, m.active, m.is_demo) == ('testamol', '', 'oral', True, False)
        catalogue.update(a, mid, {'therapeutic_class': 'SSRI'})
        catalogue.set_active(a, mid, False)
        db.session.commit()
        assert db.session.get(Medicine, mid).active is False
        acts = [r.action for r in AuditLog.query.order_by(AuditLog.id)]
        assert acts == ['medicine_create', 'medicine_edit', 'medicine_deactivate']
        assert AuditLog.query.filter_by(action='medicine_edit').one().meta == {'fields': ['therapeutic_class']}


def test_new_medicine_is_unverified_and_list_edit_resets_verification(app, two_admins):
    a, b = two_admins
    mid = _create(app, a)
    with app.app_context():
        assert db.session.get(Medicine, mid).list_verified_at is None
        catalogue.verify_list(b, mid)
        db.session.commit()
        assert db.session.get(Medicine, mid).list_verified_at is not None
        catalogue.update(a, mid, {'strength': '20 mg'})  # not a classification field
        assert db.session.get(Medicine, mid).list_verified_at is not None
        catalogue.update(a, mid, {'tpg_list': 'B'})
        m = db.session.get(Medicine, mid)
        assert m.list_verified_at is None and m.updated_by == a


def test_four_eyes_blocks_same_admin(app, two_admins, monkeypatch):
    a, b = two_admins
    mid = _create(app, a)
    with app.app_context():
        with pytest.raises(ServiceError) as e:
            catalogue.verify_list(a, mid)
        assert e.value.code == 'second_admin_required' and e.value.http == 409
        catalogue.verify_list(b, mid)
    monkeypatch.setenv('CATALOGUE_FOUR_EYES', '0')
    mid2 = _create(app, a, generic_name='Otherol')
    with app.app_context():
        catalogue.verify_list(a, mid2)  # a single-admin pilot may confirm its own entry


def test_unique_identity_and_validation(app, two_admins):
    a, _ = two_admins
    _create(app, a)
    with app.app_context():
        with pytest.raises(ServiceError) as e:
            catalogue.create(a, dict(BODY, generic_name='  TESTAMOL '))
        assert e.value.code == 'conflict'
        with pytest.raises(ServiceError) as e:
            catalogue.create(a, {'generic_name': '', 'tpg_list': 'Z'})
        assert {'generic_name', 'strength', 'form', 'tpg_list'} <= set(e.value.fields)


def test_unknown_list_defaults_to_c_and_schedule_x_forces_controlled(app, two_admins):
    a, _ = two_admins
    with app.app_context():
        m = catalogue.create(a, {'generic_name': 'Mystery', 'strength': '1 mg', 'form': 'tablet'})
        assert m.tpg_list == 'C'
        x = catalogue.create(a, {'generic_name': 'Strongol', 'strength': '1 mg', 'form': 'tablet', 'schedule': 'x',
                                 'tpg_list': 'A', 'is_controlled': False})
        assert x.schedule == 'X' and x.is_controlled is True
        db.session.commit()


def test_routes_any_admin_manages_catalogue(admin_client, make_user):
    c, _ = admin_client
    r = c.get('/admin/api/catalogue')
    assert r.status_code == 200 and r.get_json()['items'] == [] and r.get_json()['meta']['total'] == 0  # empty state
    r = c.post('/admin/api/catalogue', json=BODY)
    assert r.status_code == 201
    med = r.get_json()['medicine']
    assert med['needs_second_check'] is True and med['can_verify'] is False and med['label'] == 'TESTAMOL 10 mg tablet'
    assert c.post(f"/admin/api/catalogue/{med['id']}/verify-list").get_json()['error'] == 'second_admin_required'
    assert c.put(f"/admin/api/catalogue/{med['id']}", json={'therapeutic_class': 'X'}).status_code == 200
    assert c.post('/admin/api/catalogue', json=BODY).status_code == 409
    assert c.post(f"/admin/api/catalogue/{med['id']}/deactivate").get_json()['medicine']['active'] is False
    assert c.get('/admin/api/catalogue?active=yes').get_json()['items'] == []
    assert c.get('/admin/api/catalogue?q=testam&list=A&verified=no').get_json()['meta']['total'] == 1


def test_second_admin_verifies_through_route(app, admin_client, make_user):
    c, _ = admin_client
    mid = c.post('/admin/api/catalogue', json=BODY).get_json()['medicine']['id']
    other = client_for(app, make_user('admin'))
    assert other.post(f'/admin/api/catalogue/{mid}/verify-list').get_json()['medicine']['verified'] is True


def test_catalogue_routes_need_admin_and_flag(app, client, patient_client, admin_client, monkeypatch):
    assert client.get('/admin/api/catalogue').status_code in (302, 401)
    assert patient_client[0].get('/admin/api/catalogue', headers={'X-Requested-With': 'XMLHttpRequest'}).status_code == 403
    monkeypatch.setenv('ENABLE_PRESCRIPTIONS', '0')
    assert admin_client[0].get('/admin/api/catalogue').status_code == 404
