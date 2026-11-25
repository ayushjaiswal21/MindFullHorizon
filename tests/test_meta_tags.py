"""Crawl test for head metadata: every GET page without URL parameters, for each role (docs/SEO.md).

Checks title, description, canonical, robots, Open Graph, h1 count and JSON-LD on every HTML page that answers 200,
uniqueness across the public pages, and that the sitemap and robots.txt agree with the noindex rules.
"""
import json
import re
import struct
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

import pytest
from werkzeug.middleware.proxy_fix import ProxyFix

import utils.seo as seo
from core.extensions import db
from models import BlogPost

SITE = 'https://mfh.example.org'
INDEX, NOINDEX = 'index, follow', 'noindex, nofollow'
ROLES = ('guest', 'patient', 'provider', 'doctor', 'admin', 'desk')
SKIP = {'/logout', '/login/google', '/login/google/authorized'}
NS = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}


class Head(HTMLParser):
    """Collects what search engines read: title, meta tags, canonical, h1 count and JSON-LD blocks."""

    def __init__(self):
        super().__init__()
        self.title, self.meta, self.canonical, self.h1, self.ld = '', {}, None, 0, []
        self._in_title = self._in_ld = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'title' and not self.title:  # inline SVG titles in the body are not the page title
            self._in_title = True
        elif tag == 'meta':
            self.meta[a.get('name') or a.get('property') or ''] = a.get('content', '')
        elif tag == 'link' and a.get('rel') == 'canonical':
            self.canonical = a.get('href')
        elif tag == 'h1':
            self.h1 += 1
        elif tag == 'script' and a.get('type') == 'application/ld+json':
            self._in_ld = True
            self.ld.append('')

    def handle_endtag(self, tag):
        self._in_title = self._in_title and tag != 'title'
        self._in_ld = self._in_ld and tag != 'script'

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif self._in_ld:
            self.ld[-1] += data


def parse(resp):
    head = Head()
    head.feed(resp.get_data(as_text=True))
    return head


@pytest.fixture(autouse=True)
def site_env(monkeypatch):
    monkeypatch.setenv('SITE_URL', SITE)


@pytest.fixture
def posts(app, make_user):
    """(author id, published id, draft id)."""
    author = make_user('provider', name='Asha Rao')
    with app.app_context():
        pub = BlogPost(title='Sleeping better during exams', author_id=author, is_published=True,
                       content='Small habits that helped me sleep before exams, from a student who tried them.')
        draft = BlogPost(title='Unfinished draft', author_id=author, is_published=False, content='Not ready yet.')
        db.session.add_all([pub, draft])
        db.session.commit()
        return author, pub.id, draft.id


@pytest.fixture
def client_for(app, make_user, make_doctor):
    """client_for(role) -> test client signed in as that role; doctor is a verified prescriber, desk an admin with the pharmacy flag."""
    def _make(role):
        c = app.test_client()
        if role == 'guest':
            return c
        uid = {'doctor': make_doctor, 'desk': lambda: make_user('admin', is_pharmacy_desk=True)}.get(
            role, lambda: make_user(role, institution='Test University'))()
        with app.app_context():
            from models import User
            u = db.session.get(User, uid)
            sess = dict(user_id=uid, user_email=u.email, user_role=u.role, user_name=u.name, user_institution=u.institution)
        with c.session_transaction() as s:
            s.update(sess)
        return c
    return _make


def get_rules(app):
    return sorted({r.rule for r in app.url_map.iter_rules()
                   if 'GET' in r.methods and not r.arguments and not r.rule.startswith('/static') and r.rule not in SKIP})


def crawl(role, app, client_for, extra=()):
    """{path: Head} for every parameter-free GET page that answers 200 with HTML."""
    c = client_for(role)
    pages = {}
    for path in [*get_rules(app), *extra]:
        r = c.get(path)
        if r.status_code == 200 and r.mimetype == 'text/html':
            pages[path] = parse(r)
    return pages


def expected_robots(path, role):
    public = {p['path'] for p in seo.PUBLIC_PAGES} | {'/blog/'}
    if path == '/' and role != 'guest':
        return NOINDEX  # the signed-in home is a private dashboard page
    return INDEX if path in public or re.fullmatch(r'/blog/\d+', path) else NOINDEX


@pytest.mark.parametrize('role', ROLES)
def test_every_page_head(role, app, client_for, posts):
    _, pub, draft = posts
    pages = crawl(role, app, client_for, extra=(f'/blog/{pub}', '/nope'))
    assert len(pages) >= (8 if role == 'guest' else 15), sorted(pages)
    bad = []
    for path, h in pages.items():
        title, desc = h.title.strip(), h.meta.get('description', '')
        checks = {
            'title<=60': 0 < len(title) <= 60,
            'title not doubled': title.lower().count('mindful horizon') <= 1 and ' - mindful' not in title.lower(),
            'description 50-160': 50 <= len(desc) <= 160,
            'canonical absolute, no query': h.canonical == SITE + (path if path != '/nope' else '/nope'),
            'robots': h.meta.get('robots') == (NOINDEX if path == '/nope' else expected_robots(path, role)),
            'og:title': bool(h.meta.get('og:title')), 'og:description': h.meta.get('og:description') == desc,
            'og:url': h.meta.get('og:url') == h.canonical, 'og:image absolute': h.meta.get('og:image', '').startswith(SITE + '/static/'),
            'twitter:image': h.meta.get('twitter:image') == h.meta.get('og:image'),
            'one h1': h.h1 == 1,
        }
        bad += [f'{role} {path}: {name} (title={title!r}, desc={len(desc)})' for name, ok in checks.items() if not ok]
        for block in h.ld:
            try:
                json.loads(block)
            except ValueError:
                bad.append(f'{role} {path}: invalid JSON-LD')
    assert not bad, '\n'.join(bad)


def test_public_titles_and_descriptions_are_unique(app, client_for, posts):
    _, pub, _ = posts
    pages = {p: h for p, h in crawl('guest', app, client_for, extra=(f'/blog/{pub}',)).items()
             if h.meta.get('robots') == INDEX}
    assert {'/', '/login', '/signup', '/about', '/faq', '/contact', '/privacy', '/terms', '/ai', '/blog/', f'/blog/{pub}'} <= set(pages)
    titles = [h.title.strip() for h in pages.values()]
    descs = [h.meta['description'] for h in pages.values()]
    assert len(set(titles)) == len(titles), titles
    assert len(set(descs)) == len(descs)


def test_breadcrumbs_on_public_pages_below_home(app, client_for, posts):
    _, pub, _ = posts
    pages = crawl('guest', app, client_for, extra=(f'/blog/{pub}',))
    for path, h in pages.items():
        if path == '/' or h.meta.get('robots') != INDEX:
            continue
        crumbs = [json.loads(b) for b in h.ld if '"BreadcrumbList"' in b]
        assert len(crumbs) == 1, path
        items = crumbs[0]['itemListElement']
        assert items[0]['name'] == 'Home' and items[-1]['position'] == len(items), path


def test_blog_post_article_jsonld_and_draft_noindex(app, posts):
    _, pub, draft = posts
    c = app.test_client()
    h = parse(c.get(f'/blog/{pub}'))
    art = next(json.loads(b) for b in h.ld if '"Article"' in b)
    assert art['headline'] == 'Sleeping better during exams' and art['author']['name'] == 'Asha Rao'
    assert art['datePublished'].startswith('20') and art['mainEntityOfPage'] == f'{SITE}/blog/{pub}'
    assert h.title.strip().startswith('Sleeping better') and 'sleep before exams' in h.meta['description']
    assert c.get(f'/blog/{draft}').status_code == 404  # drafts are visible to their author only


def test_blog_article_jsonld_escapes_user_text(app, make_user):
    author = make_user('provider', name='Mia </script><b>x')
    with app.app_context():
        post = BlogPost(title='A </script><script>alert(1)</script> title', author_id=author, is_published=True,
                        content='Some body text that is long enough to pass the description length rule for posts.')
        db.session.add(post)
        db.session.commit()
        pid = post.id
    html = app.test_client().get(f'/blog/{pid}').get_data(as_text=True)
    assert '</script><script>alert(1)' not in html
    h = Head()
    h.feed(html)
    assert any(json.loads(b).get('@type') == 'Article' for b in h.ld)


def test_search_title_and_description_follow_the_query(client):
    h = parse(client.get('/search', query_string={'q': 'sleep'}))
    assert 'sleep' in h.title and 'sleep' in h.meta['description'] and h.meta['robots'] == NOINDEX
    assert h.canonical == SITE + '/search'
    assert 'noindex' in client.get('/search').headers['X-Robots-Tag']


def test_x_robots_tag_systematic(app, client_for, posts):
    _, pub, _ = posts
    c = client_for('patient')
    for path in ('/patient/dashboard', '/profile', '/chat', '/health', '/nope', '/api/mood', '/search'):
        assert c.get(path).headers.get('X-Robots-Tag') == NOINDEX, path
    anon = app.test_client()
    for path in ('/', '/about', '/blog/', f'/blog/{pub}', '/robots.txt', '/sitemap.xml', '/static/img/og-default.png'):
        assert 'X-Robots-Tag' not in anon.get(path).headers, path
    assert anon.post('/api/event', json={'name': 'page_view', 'path': '/'}, headers={'Origin': 'http://localhost'}).status_code == 204


def test_sitemap_urls_are_indexable_and_complete(app, posts):
    _, pub, draft = posts
    c = app.test_client()
    root = ET.fromstring(c.get('/sitemap.xml').data)
    paths = [u.find('sm:loc', NS).text.removeprefix(SITE) for u in root.findall('sm:url', NS)]
    assert len(paths) == len(set(paths))
    assert {'/', '/ai', '/blog/', f'/blog/{pub}', '/login', '/signup', '/about', '/faq', '/contact', '/privacy', '/terms'} <= set(paths)
    assert f'/blog/{draft}' not in paths
    for path in paths:
        r = c.get(path)
        assert r.status_code == 200, path
        assert parse(r).meta['robots'] == INDEX, path
        assert not path.startswith(tuple(p for p in seo.PRIVATE_PREFIXES if p != '/blog/api/')), path
    for u in root.findall('sm:url', NS):
        assert u.find('sm:lastmod', NS) is not None


def test_robots_txt_matches_noindex_rules(app, client_for, posts):
    body = app.test_client().get('/robots.txt').get_data(as_text=True)
    disallow = [ln.split(': ', 1)[1] for ln in body.splitlines() if ln.startswith('Disallow: ')]
    assert f'Sitemap: {SITE}/sitemap.xml' in body
    for path in ('/', '/login', '/signup', '/about', '/faq', '/contact', '/privacy', '/terms', '/ai', '/blog/', '/blog/1'):
        assert not path.startswith(tuple(disallow)), path
    for role in ROLES[1:]:
        for path, h in crawl(role, app, client_for).items():
            if h.meta['robots'] == NOINDEX and path != '/':
                assert path.startswith(tuple(disallow)), f'{path} is noindex but not disallowed'


def test_social_image_files_and_sizes():
    base = 'static/img/og-default'
    png = open(base + '.png', 'rb').read(32)
    assert png[:8] == b'\x89PNG\r\n\x1a\n' and struct.unpack('>II', png[16:24]) == (1200, 630)
    webp = open(base + '.webp', 'rb').read(32)
    assert webp[:4] == b'RIFF' and webp[8:12] == b'WEBP' and webp[12:16] == b'VP8 '
    assert struct.unpack('<HH', webp[26:30]) == (1200, 630)


def test_site_url_never_localhost_when_configured(client):
    h = parse(client.get('/about', base_url='http://localhost'))
    for value in (h.canonical, h.meta['og:url'], h.meta['og:image']):
        assert value.startswith(SITE) and 'localhost' not in value
    assert 'localhost' not in ''.join(h.ld)


def test_site_url_behind_proxy_uses_forwarded_origin(app, monkeypatch):
    monkeypatch.delenv('SITE_URL', raising=False)
    monkeypatch.setattr(app, 'wsgi_app', ProxyFix(app.wsgi_app, x_proto=1, x_host=1))
    h = parse(app.test_client().get('/about', headers={'X-Forwarded-Proto': 'https', 'X-Forwarded-Host': 'mfh.example.in'}))
    assert h.canonical == 'https://mfh.example.in/about'
    assert h.meta['og:image'].startswith('https://mfh.example.in/static/')
