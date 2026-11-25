"""SEO and discovery routes: /robots.txt, /sitemap.xml, /search, POST /api/event (owned by F3a).

/favicon.ico is served by app.py (`favicon`), not here, to avoid a duplicate rule.
"""
import re
from urllib.parse import urlsplit
from xml.sax.saxutils import escape as xml_escape

from flask import Blueprint, Response, jsonify, render_template, request, session, url_for
from markupsafe import Markup, escape
from werkzeug.routing import BuildError

from core.extensions import csrf, db, limiter
from utils.seo import (DISCOVERY_PATHS, EVENT_NAMES, PRIVATE_PREFIXES, is_indexable_path, public_pages,
                       sitemap_entries, site_url)

seo_bp = Blueprint('seo', __name__)

# Static shortcuts for logged-in users: (endpoint, title, description). No private data is ever searched.
_SHORTCUTS = {
    'patient': [
        ('patient.patient_dashboard', 'Mood check-in', 'Log how you feel today and see your history.'),
        ('patient.assessment', 'Assessments', 'PHQ-9 and GAD-7 screenings.'),
        ('chat', 'Chat', 'Talk to the AI assistant.'),
        ('patient.patient_journal', 'Journal', 'Write a private journal entry.'),
        ('patient.goals', 'Goals', 'Set and track personal goals.'),
        ('patient.schedule_appointment', 'Schedule', 'Book a session with your counsellor.'),
        ('patient.breathing', 'Breathing', 'Guided breathing exercises.'),
        ('patient.yoga', 'Yoga', 'Yoga sessions and videos.'),
        ('music', 'Music', 'Calming music and sounds.'),
        ('patient.safety_plan', 'Safety plan', 'Write a private plan for hard moments.'),
        ('patient.grounding', 'Grounding exercise', 'A five-step exercise using your senses.'),
        ('patient.sleep_log', 'Sleep log', 'Note your sleep and see the last 14 days.'),
        ('patient.reminders', 'Reminder emails', 'Choose an optional reminder email.'),
    ],
    'provider': [
        ('provider.provider_dashboard', 'Dashboard', 'Your patients and appointments.'),
        ('provider.analytics', 'Analytics', 'Aggregate institution data.'),
        ('telehealth', 'Telehealth', 'Start or join a video session.'),
    ],
}

_RESULT_LIMIT = 20
_QUERY_MAX = 100
_TAG_RE = re.compile(r'<[^>]*>')
_CTRL_RE = re.compile(r'[\x00-\x1f\x7f]')


# ---------- robots.txt, sitemap.xml ----------

def _cached(body, mimetype, seconds):
    resp = Response(body, mimetype=mimetype)
    resp.headers['Cache-Control'] = f'public, max-age={seconds}'
    return resp


@seo_bp.route('/robots.txt')
def robots():
    lines = ['User-agent: *', 'Allow: /$']
    lines += [f'Allow: {p["path"]}' for p in public_pages() if p['path'] != '/']
    lines += [f'Disallow: {p}' for p in PRIVATE_PREFIXES]
    lines += ['', f'Sitemap: {site_url()}/sitemap.xml', '']
    return _cached('\n'.join(lines), 'text/plain', 86400)


@seo_bp.route('/sitemap.xml')
def sitemap():
    base = site_url()
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for e in sitemap_entries():
        out.append('<url>')
        out.append(f'<loc>{xml_escape(base + e["path"])}</loc>')
        if e['lastmod']:
            out.append(f'<lastmod>{e["lastmod"]}</lastmod>')
        out.append(f'<changefreq>{e["changefreq"]}</changefreq>')
        out.append(f'<priority>{e["priority"]:.1f}</priority>')
        out.append('</url>')
    out.append('</urlset>')
    return _cached('\n'.join(out), 'application/xml', 3600)


@seo_bp.after_app_request
def _noindex_headers(response):
    """One rule for every response: anything that is not a public page gets X-Robots-Tag noindex.

    Exempt: public pages (their <meta name="robots"> decides, so a draft post stays noindex there), the discovery
    files and static assets. A route that sets its own X-Robots-Tag keeps it.
    """
    path = request.path
    if (is_indexable_path(path) or path in DISCOVERY_PATHS or request.endpoint == 'static'
            or 'X-Robots-Tag' in response.headers):
        return response
    response.headers['X-Robots-Tag'] = 'noindex, nofollow'
    return response


# ---------- search ----------

def _terms(q):
    return q.split()[:5]


def _like_escape(term):
    return term.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


@seo_bp.app_template_filter('highlight')
def highlight(text, q):
    """Escape first, then wrap matches in <mark>. Returns Markup built only from escaped pieces."""
    text = str(text or '')
    terms = sorted({t for t in _terms(q or '')}, key=len, reverse=True)
    if not terms:
        return escape(text)
    parts = re.split('(' + '|'.join(re.escape(t) for t in terms) + ')', text, flags=re.IGNORECASE)
    return Markup('').join(Markup('<mark>%s</mark>') % p if i % 2 else escape(p) for i, p in enumerate(parts))


def _search_pages(terms):
    hits = []
    for p in public_pages():
        hay = (p['title'] + ' ' + p['description']).lower()
        if all(t.lower() in hay for t in terms):
            hits.append({'path': p['path'], 'title': p['title'], 'description': p['description']})
    return hits


def _search_posts(terms):
    from models import BlogPost
    query = BlogPost.query.filter(BlogPost.is_published.is_(True))
    for t in terms:
        pat = f'%{_like_escape(t)}%'
        query = query.filter(db.or_(BlogPost.title.ilike(pat, escape='\\'), BlogPost.content.ilike(pat, escape='\\')))
    posts = query.order_by(BlogPost.created_at.desc()).limit(_RESULT_LIMIT).all()
    return [{'path': url_for('blog.blog_detail', post_id=p.id), 'title': p.title,
             'description': _TAG_RE.sub('', p.content or '')[:160]} for p in posts]


def _shortcuts(terms):
    out = []
    for endpoint, title, desc in _SHORTCUTS.get(session.get('user_role') if session.get('user_email') else None, []):
        try:
            path = url_for(endpoint)
        except BuildError:
            continue
        if all(t.lower() in (title + ' ' + desc).lower() for t in terms):
            out.append({'path': path, 'title': title, 'description': desc})
    return out


@seo_bp.route('/search')
@limiter.limit('60 per minute')
def search():
    q = _CTRL_RE.sub(' ', request.args.get('q', '')).strip()[:_QUERY_MAX]
    terms = _terms(q)
    pages = _search_pages(terms)
    posts = _search_posts(terms) if terms else []
    shortcuts = _shortcuts(terms)
    return render_template('search.html', q=q, pages=pages[:_RESULT_LIMIT], posts=posts,
                           shortcuts=shortcuts, canonical_url=site_url() + '/search')


# ---------- first-party analytics ----------

_EVENT_FIELDS = {'name', 'path', 'utm_source', 'utm_medium', 'utm_campaign'}
_PATH_RE = re.compile(r"^/[A-Za-z0-9._~!$&'()*+,;=:@%/\-]*$")
_UTM_BAD_RE = re.compile(r'[^A-Za-z0-9._~ +\-]')


def _reject(code):
    return jsonify(error='invalid request'), code


def _same_origin():
    """Origin header, else Referer, must name this host. Neither present means reject."""
    source = request.headers.get('Origin') or request.headers.get('Referer')
    return bool(source) and urlsplit(source).netloc == request.host


@seo_bp.route('/api/event', methods=['POST'])
# CSRF-exempt on purpose: a JSON beacon from scripts that may run before a token is rendered.
# Compensating controls: same-origin Origin/Referer check, custom consent header (forces a CORS
# preflight cross-site), JSON content type, strict allowlist, no auth-dependent behaviour.
@csrf.exempt
@limiter.limit('120 per minute')
def track_event():
    if not _same_origin():
        return _reject(403)
    if request.headers.get('DNT') == '1' or request.headers.get('X-Analytics-Consent') != 'granted':
        return '', 204  # no consent, nothing stored
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not set(data) <= _EVENT_FIELDS:
        return _reject(400)
    name, path = data.get('name'), data.get('path')
    if name not in EVENT_NAMES or not isinstance(path, str):
        return _reject(400)
    path = path.split('?', 1)[0].split('#', 1)[0][:200]
    if not _PATH_RE.match(path):
        return _reject(400)
    utm = {}
    for key in ('utm_source', 'utm_medium', 'utm_campaign'):
        value = data.get(key)
        if value is not None and not isinstance(value, str):
            return _reject(400)
        utm[key] = _UTM_BAD_RE.sub('', value or '')[:100] or None
    from models import AnalyticsEvent
    db.session.add(AnalyticsEvent(name=name, path=path, **utm))
    db.session.commit()
    return '', 204
