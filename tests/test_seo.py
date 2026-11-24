"""SEO, search and first-party event endpoint tests."""
import xml.etree.ElementTree as ET
from datetime import datetime

import pytest

import app as app_module
from extensions import db
from models import AnalyticsEvent, BlogPost, JournalEntry
from utils.seo import EVENT_NAMES, PRIVATE_PREFIXES, event_counts

NS = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
ORIGIN = {'Origin': 'http://localhost'}
CONSENT = {**ORIGIN, 'X-Analytics-Consent': 'granted'}


def _post(app, author_id, title='Post', content='Body', published=True, **kw):
    with app.app_context():
        p = BlogPost(title=title, content=content, author_id=author_id, is_published=published, **kw)
        db.session.add(p)
        db.session.commit()
        return p.id


def _sitemap(client):
    r = client.get('/sitemap.xml')
    assert r.status_code == 200 and r.mimetype == 'application/xml'
    root = ET.fromstring(r.data)  # raises if not well-formed
    return [u.find('sm:loc', NS).text for u in root.findall('sm:url', NS)], root


# ---------- robots / sitemap ----------

def test_robots(client):
    r = client.get('/robots.txt')
    assert r.mimetype == 'text/plain'
    assert 'max-age=86400' in r.headers['Cache-Control']
    body = r.get_data(as_text=True)
    for prefix in ('/patient', '/provider', '/api/', '/search'):
        assert f'Disallow: {prefix}' in body
    assert 'Allow: /login' in body
    assert 'Sitemap: http://localhost/sitemap.xml' in body


def test_robots_uses_site_url_env(client, monkeypatch):
    monkeypatch.setenv('SITE_URL', 'https://example.org/')
    assert 'Sitemap: https://example.org/sitemap.xml' in client.get('/robots.txt').get_data(as_text=True)


def test_sitemap_public_only_and_published_posts(client, app, make_user):
    uid = make_user('provider')
    pub = _post(app, uid, 'Published')
    draft = _post(app, uid, 'Draft', published=False)
    locs, root = _sitemap(client)
    paths = [loc.replace('http://localhost', '') for loc in locs]
    assert '/' in paths and '/login' in paths and '/blog/' in paths
    assert f'/blog/{pub}' in paths and f'/blog/{draft}' not in paths
    assert not any(p.startswith(tuple(x for x in PRIVATE_PREFIXES if x != '/blog/api/')) for p in paths)
    assert '/yoga/videos' not in paths
    post_url = [u for u in root.findall('sm:url', NS) if u.find('sm:loc', NS).text.endswith(f'/blog/{pub}')][0]
    assert post_url.find('sm:lastmod', NS).text == datetime.utcnow().date().isoformat()


def test_sitemap_skips_unrouted_pages_and_escapes(client, monkeypatch):
    import utils.seo as seo
    monkeypatch.setattr(seo, 'PUBLIC_PAGES', seo.PUBLIC_PAGES + [
        {'path': '/not-built-yet', 'title': 'x', 'description': 'x', 'public': True, 'changefreq': 'yearly', 'priority': 0.1}])
    monkeypatch.setenv('SITE_URL', 'https://example.org/a&b')
    locs, _ = _sitemap(client)  # '&' must be escaped or parsing fails
    assert 'https://example.org/a&b/login' in locs
    assert not any(loc.endswith('/not-built-yet') for loc in locs)


# ---------- search ----------

def test_search_empty_shows_index_and_noindex(client):
    r = client.get('/search')
    assert r.status_code == 200
    assert 'noindex' in r.headers['X-Robots-Tag']
    html = r.get_data(as_text=True)
    assert 'All pages' in html and 'href="/login"' in html


def test_search_xss_is_escaped(client):
    payload = '<script>alert(1)</script>'
    html = client.get('/search', query_string={'q': payload}).get_data(as_text=True)
    assert payload not in html and '&lt;script&gt;' in html


def test_search_highlight_escapes_then_marks(client, app, make_user):
    _post(app, make_user('provider'), 'Calm <b>breathing</b>', 'x')
    html = client.get('/search', query_string={'q': 'breath'}).get_data(as_text=True)
    assert '&lt;b&gt;<mark>breath</mark>ing&lt;/b&gt;' in html
    assert '<b>breathing' not in html


def test_search_wildcards_are_literal(client, app, make_user):
    uid = make_user('provider')
    _post(app, uid, 'Plain title', 'nothing special')
    _post(app, uid, '100% real', 'x')
    for q in ('%', '_', '\\'):
        html = client.get('/search', query_string={'q': q}).get_data(as_text=True)
        assert 'Plain title' not in html
    assert '100%' in client.get('/search', query_string={'q': '100%'}).get_data(as_text=True)


def test_search_sql_injection_string_is_harmless(client, app, make_user):
    _post(app, make_user('provider'), 'Plain', 'x')
    r = client.get('/search', query_string={'q': "' OR 1=1 --"})
    assert r.status_code == 200 and 'Plain' not in r.get_data(as_text=True)


def test_search_query_length_cap(client):
    html = client.get('/search', query_string={'q': 'a' * 500}).get_data(as_text=True)
    import re
    assert re.search(r'name="q" value="(a*)"', html).group(1) == 'a' * 100


def test_search_only_published_posts(client, app, make_user):
    uid = make_user('provider')
    _post(app, uid, 'Sleep tips', 'x')
    _post(app, uid, 'Sleep secret draft', 'x', published=False)
    html = client.get('/search', query_string={'q': 'sleep'}).get_data(as_text=True)
    assert '<mark>Sleep</mark> tips' in html and 'secret draft' not in html


def test_search_guest_has_no_private_shortcuts(client):
    html = client.get('/search', query_string={'q': 'journal'}).get_data(as_text=True)
    assert '/patient/journal' not in html and 'Your tools' not in html


def test_search_patient_shortcuts_and_provider_differs(patient_client, provider_client):
    html = patient_client[0].get('/search', query_string={'q': 'journal'}).get_data(as_text=True)
    assert 'href="/patient/journal"' in html
    phtml = provider_client[0].get('/search', query_string={'q': 'journal'}).get_data(as_text=True)
    assert '/patient/journal' not in phtml
    assert 'href="/provider/analytics"' in provider_client[0].get('/search').get_data(as_text=True)


def test_search_never_returns_journal_text(app, patient_client):
    c, uid = patient_client
    with app.app_context():
        db.session.add(JournalEntry(user_id=uid, title='t', content='zebra-secret-thought'))
        db.session.commit()
    html = c.get('/search', query_string={'q': 'zebra-secret'}).get_data(as_text=True)
    assert 'zebra-secret-thought' not in html and 'No results' in html


def test_search_has_rate_limit(app):
    lim = app_module.limiter
    lim.enabled = True
    lim.reset()
    try:
        c = app.test_client()
        codes = [c.get('/search').status_code for _ in range(62)]
        assert codes[0] == 200 and codes[-1] == 429
    finally:
        lim.reset()
        lim.enabled = False


# ---------- /api/event ----------

def _event(client, body=None, headers=CONSENT):
    body = {'name': 'page_view', 'path': '/about'} if body is None else body
    return client.post('/api/event', json=body, headers=headers)


def _rows(app):
    with app.app_context():
        return AnalyticsEvent.query.all()


def test_event_stores_clean_row(client, app):
    r = _event(client, {'name': 'cta_click', 'path': '/signup?email=a@b.c#x', 'utm_source': 'news<letter>',
                        'utm_medium': 'email', 'utm_campaign': 'c' * 300})
    assert r.status_code == 204
    (row,) = _rows(app)
    assert (row.name, row.path) == ('cta_click', '/signup')
    assert row.utm_source == 'newsletter' and row.utm_medium == 'email' and len(row.utm_campaign) == 100


def test_event_path_truncated(client, app):
    assert _event(client, {'name': 'page_view', 'path': '/' + 'a' * 500}).status_code == 204
    assert len(_rows(app)[0].path) == 200


@pytest.mark.parametrize('body', [
    {'name': 'delete_everything', 'path': '/'},
    {'name': 'page_view'},
    {'name': 'page_view', 'path': 'about'},
    {'name': 'page_view', 'path': '//evil.com/x y'},
    {'name': 'page_view', 'path': '/', 'user_id': 5},
    {'name': 'page_view', 'path': '/', 'utm_source': ['a']},
    ['page_view'],
])
def test_event_bad_input_rejected_without_row(client, app, body):
    assert _event(client, body).status_code == 400
    assert _rows(app) == []


def test_event_non_json_rejected(client, app):
    r = client.post('/api/event', data='name=page_view', headers=CONSENT)
    assert r.status_code == 400 and _rows(app) == []


def test_event_same_origin_required(client, app):
    assert _event(client, headers={'Origin': 'https://evil.example', 'X-Analytics-Consent': 'granted'}).status_code == 403
    assert _event(client, headers={'X-Analytics-Consent': 'granted'}).status_code == 403
    assert _rows(app) == []
    ok = _event(client, headers={'Referer': 'http://localhost/about', 'X-Analytics-Consent': 'granted'})
    assert ok.status_code == 204 and len(_rows(app)) == 1


def test_event_dnt_and_missing_consent_store_nothing(client, app):
    assert _event(client, headers={**CONSENT, 'DNT': '1'}).status_code == 204
    assert _event(client, headers=ORIGIN).status_code == 204
    assert _rows(app) == []


def test_event_works_without_csrf_token(app):
    app.config['WTF_CSRF_ENABLED'] = True
    try:
        assert _event(app.test_client()).status_code == 204
    finally:
        app.config['WTF_CSRF_ENABLED'] = False


def test_event_noindex_header_and_get_not_allowed(client):
    assert client.get('/api/event').status_code == 405
    assert client.get('/api/event').headers['X-Robots-Tag'] == 'noindex'


def test_event_stores_no_identity_columns(patient_client, app):
    c, _ = patient_client
    assert _event(c).status_code == 204
    cols = {col.name for col in AnalyticsEvent.__table__.columns}
    assert cols == {'id', 'name', 'path', 'utm_source', 'utm_medium', 'utm_campaign', 'created_at'}


def test_event_rate_limit(app):
    lim = app_module.limiter
    lim.enabled = True
    lim.reset()
    try:
        c = app.test_client()
        h = {**CONSENT, 'DNT': '1'}  # DNT returns before any write, keeps the loop cheap
        codes = [_event(c, headers=h).status_code for _ in range(122)]
        assert codes[0] == 204 and codes[-1] == 429 and 429 not in codes[:120]
    finally:
        lim.reset()
        lim.enabled = False


def test_event_counts(client, app):
    for n in ('page_view', 'page_view', 'login'):
        _event(client, {'name': n, 'path': '/'})
    with app.app_context():
        assert event_counts(30) == {'page_view': 2, 'login': 1}
    assert {'page_view', 'login', 'blog_read'} <= EVENT_NAMES
