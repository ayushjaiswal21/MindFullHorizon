"""Every admin URL, built from the url map, as admin, as a non-admin and signed out: never a 500 (lead bug report)."""
import re

import pytest


def _admin_rules(app):
    rules = []
    for rule in app.url_map.iter_rules():
        if not rule.endpoint.startswith('admin.'):
            continue
        path = re.sub(r'<(?:int:)?name>', 'stock', rule.rule)
        path = re.sub(r'<int:\w+>', '1', path)
        for method in sorted(rule.methods & {'GET', 'POST', 'PUT'}):
            rules.append((method, path))
    return sorted(set(rules))


def _is_api(path):
    return path.startswith('/admin/api/')


def _call(client, method, path):
    kw = {'json': {}} if method != 'GET' else {}
    return client.open(path, method=method, **kw)


def test_expected_pages_are_registered(app):
    paths = {p for m, p in _admin_rules(app) if m == 'GET'}
    for expected in ('/admin/', '/admin/login', '/admin/dashboard', '/admin/staff', '/admin/verification',
                     '/admin/audit', '/admin/annual-report', '/admin/annual-report.csv', '/admin/messages',
                     '/admin/catalogue', '/admin/inventory', '/admin/dispensing', '/admin/reports'):
        assert expected in paths, expected


def test_admin_home_redirects(app, client, admin_client):
    assert client.get('/admin').status_code in (301, 308)
    r = client.get('/admin/')
    assert r.status_code == 302 and '/admin/login' in r.headers['Location']
    r = admin_client[0].get('/admin/')
    assert r.status_code == 200 and b'Overview' in r.data  # /admin/ renders the overview


def test_signed_out_never_500(app, client):
    for method, path in _admin_rules(app):
        if path in ('/admin/login', '/admin/'):
            continue
        r = _call(client, method, path)
        assert r.status_code == (401 if _is_api(path) else 302), (method, path, r.status_code)
        if not _is_api(path) and method == 'GET':
            assert '/admin/login' in r.headers['Location'] and 'next=' in r.headers['Location'], path


@pytest.mark.parametrize('who', ['patient_client', 'provider_client', 'doctor_client'])
def test_non_admin_is_refused(app, who, request):
    client, _ = request.getfixturevalue(who)
    for method, path in _admin_rules(app):
        if path in ('/admin/login', '/admin/'):
            continue
        r = _call(client, method, path)
        assert r.status_code == (403 if _is_api(path) else 302), (who, method, path, r.status_code)


def test_admin_pages_never_500(app, admin_client):
    for method, path in _admin_rules(app):
        if method != 'GET' or path == '/admin/login':
            continue
        r = _call(admin_client[0], method, path)
        assert r.status_code < 500, (path, r.status_code)


def test_desk_admin_pages_never_500(app, desk_client):
    for method, path in _admin_rules(app):
        if method != 'GET' or path == '/admin/login':
            continue
        r = _call(desk_client[0], method, path)
        assert r.status_code < 500, (path, r.status_code)


def test_admin_login_page_and_generic_failure(app, client, make_user):
    assert client.get('/admin/login').status_code == 200
    make_user('admin', email='boss@test.local')
    r = client.post('/admin/login', data={'email': 'boss@test.local', 'password': 'wrong'})
    assert r.status_code == 200 and b'Invalid email, password or role' in r.data
    from tests.conftest import PASSWORD
    r = client.post('/admin/login', data={'email': 'boss@test.local', 'password': PASSWORD})
    assert r.status_code == 302 and r.headers['Location'].endswith('/admin/')
    assert client.get('/admin/dashboard').status_code == 200


def test_unauthenticated_catalogue_redirects_with_next_then_lands_back(app, client, make_user):
    from tests.conftest import PASSWORD
    make_user('admin', email='demo.admin@example.com')
    r = client.get('/admin/catalogue')
    assert r.status_code == 302 and '/admin/login?next=' in r.headers['Location']
    page = client.get(r.headers['Location'])
    assert page.status_code == 200 and 'noindex' in page.headers['X-Robots-Tag'] and b'name="next"' in page.data
    r = client.post(r.headers['Location'], data={'email': 'demo.admin@example.com', 'password': PASSWORD})
    assert r.status_code == 302 and r.headers['Location'].endswith('/admin/catalogue')


def test_admin_login_lands_on_overview_and_logout_works(app, client, make_user):
    from tests.conftest import PASSWORD
    make_user('admin', email='demo.admin@example.com')
    r = client.post('/admin/login', data={'email': 'demo.admin@example.com', 'password': PASSWORD}, follow_redirects=True)
    assert r.status_code == 200 and b'Overview' in r.data
    assert client.get('/logout').status_code == 302
    assert client.get('/admin/dashboard').status_code == 302


def test_login_next_cannot_leave_the_admin_area(app, client, make_user):
    from tests.conftest import PASSWORD
    make_user('admin', email='demo.admin@example.com')
    for bad in ('//evil.example', 'https://evil.example', '/patient/dashboard', '/admin' + chr(92) + 'x'):
        r = client.post('/admin/login', data={'email': 'demo.admin@example.com', 'password': PASSWORD, 'next': bad})
        assert r.headers['Location'].endswith('/admin/'), bad
        client.get('/logout')


def test_normal_login_still_refuses_admin(app, client, make_user):
    from tests.conftest import PASSWORD
    make_user('admin', email='demo.admin@example.com')
    r = client.post('/login', data={'email': 'demo.admin@example.com', 'password': PASSWORD, 'role': 'admin'})
    assert b'Invalid email, password or role' in r.data
