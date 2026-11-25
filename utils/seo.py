"""SEO helpers: public page registry, private prefixes, site URL, sitemap entries, event counts."""
import re
import time
from datetime import datetime, timedelta

from flask import current_app
from werkzeug.exceptions import HTTPException

from utils.site_context import SITE_LAST_UPDATED, site_url as _site_url

# Pages a guest can open without being redirected to login. Pages owned by other agents may not
# exist yet; `public_pages()` drops any path the URL map does not resolve, so this list self-heals.
# Blog index is `/blog/` because `/blog` is only a redirect.
PUBLIC_PAGES = [
    {'path': '/', 'title': 'Home', 'public': True, 'changefreq': 'weekly', 'priority': 1.0,
     'description': 'Track your mood, take PHQ-9 and GAD-7 screenings, and book a session with your college counsellor.'},
    {'path': '/login', 'title': 'Log in', 'public': True, 'changefreq': 'yearly', 'priority': 0.5,
     'description': 'Sign in as a student or a counsellor to reach your mood log, screenings and appointments.'},
    {'path': '/signup', 'title': 'Create an account', 'public': True, 'changefreq': 'yearly', 'priority': 0.7,
     'description': 'Create a free student or counsellor account. You must be 18 or older.'},
    {'path': '/about', 'title': 'About', 'public': True, 'changefreq': 'monthly', 'priority': 0.6,
     'description': 'What Mindful Horizon does, who it is for, and how it handles your data.'},
    {'path': '/faq', 'title': 'Frequently asked questions', 'public': True, 'changefreq': 'monthly', 'priority': 0.6,
     'description': 'Answers about screenings, the AI companion, privacy and counsellor access.'},
    {'path': '/contact', 'title': 'Contact', 'public': True, 'changefreq': 'yearly', 'priority': 0.4,
     'description': 'Send a message to the Mindful Horizon team. We cannot answer crisis messages.'},
    {'path': '/privacy', 'title': 'Privacy policy', 'public': True, 'changefreq': 'monthly', 'priority': 0.3,
     'description': 'What data the service stores, who can see it and how to ask for deletion.'},
    {'path': '/terms', 'title': 'Terms of use', 'public': True, 'changefreq': 'monthly', 'priority': 0.3,
     'description': 'The terms for using Mindful Horizon.'},
    {'path': '/blog/', 'title': 'Blog', 'public': True, 'changefreq': 'daily', 'priority': 0.8,
     'description': 'Articles on student mental health and wellbeing.'},
    {'path': '/ai', 'title': 'How the AI companion works', 'public': True, 'changefreq': 'monthly', 'priority': 0.5,
     'description': 'What the AI companion is, what data it receives, what it cannot do, and how the crisis check works.'},
    # Not listed: /yoga/videos does not exist (the real page is /patient/yoga/videos and needs a patient login).
]

# Everything behind login, API and operational endpoints (from the real url map). Used by robots.txt.
PRIVATE_PREFIXES = [
    '/patient', '/provider', '/chat', '/api/', '/account', '/admin', '/assessment', '/mood',
    '/profile', '/schedule', '/telehealth', '/telehealth_session', '/music', '/audio',
    '/role_selection', '/save_role', '/logout', '/login/google', '/blog/create', '/blog/api/',
    '/search', '/health', '/ready', '/consent', '/ops',
]

# Responses that must never carry X-Robots-Tag: crawlers fetch them on purpose.
DISCOVERY_PATHS = ('/robots.txt', '/sitemap.xml', '/favicon.ico')

EVENT_NAMES = frozenset({
    'page_view', 'signup_start', 'signup_complete', 'login', 'assessment_start', 'assessment_complete',
    'chat_open', 'contact_submit', 'blog_read', 'cta_click', 'theme_toggle',
})

SITEMAP_LIMIT = 5000
_memo = {}  # shortcut: per-process TTL memo; use flask-caching (lives in app.py) if several workers must share it


def site_url():
    """Canonical origin without a trailing slash: env SITE_URL, else the request's own root.

    Behind Render ProxyFix (production) the request root already carries the public scheme and host.
    """
    return _site_url()


def is_indexable_path(path):
    """True for a path that is meant to be indexed: a registry page or a blog post (`/blog/<id>`)."""
    return path in {p['path'] for p in PUBLIC_PAGES if p['public']} or re.fullmatch(r'/blog/\d+', path) is not None


def _resolves(path):
    try:
        current_app.url_map.bind('').match(path, method='GET')
        return True
    except HTTPException:  # NotFound, MethodNotAllowed, RequestRedirect
        return False


def public_pages():
    """Registry entries that are public and actually routed right now."""
    return [p for p in PUBLIC_PAGES if p['public'] and _resolves(p['path'])]


def _ttl(key, seconds, fn):
    if current_app.testing:
        return fn()
    hit = _memo.get(key)
    if hit and hit[0] > time.time():
        return hit[1]
    value = fn()
    _memo[key] = (time.time() + seconds, value)
    return value


def _build_sitemap_entries():
    from flask import url_for
    from models import BlogPost
    pages = public_pages()
    entries = [{'path': p['path'], 'lastmod': SITE_LAST_UPDATED, 'changefreq': p['changefreq'], 'priority': p['priority']}
               for p in pages]
    rows = (BlogPost.query.with_entities(BlogPost.id, BlogPost.created_at, BlogPost.updated_at)
            .filter(BlogPost.is_published.is_(True))
            .order_by(BlogPost.created_at.desc())
            .limit(max(SITEMAP_LIMIT - len(entries), 0)).all())
    stamps = []
    for post_id, created, updated in rows:
        stamp = updated or created
        if stamp:
            stamps.append(stamp)
        entries.append({'path': url_for('blog.blog_detail', post_id=post_id),
                        'lastmod': stamp.date().isoformat() if stamp else None,
                        'changefreq': 'monthly', 'priority': 0.6})
    if stamps:
        for e in entries:
            if e['path'] == '/blog/':
                e['lastmod'] = max(stamps).date().isoformat()
    return entries


def sitemap_entries():
    """Public paths for the sitemap, cached 1 hour. Host-independent, so it is safe to share."""
    return _ttl('sitemap', 3600, _build_sitemap_entries)


def event_counts(days=30):
    """Read-only aggregate for later dashboards: {event name: count} over the last `days` days."""
    from sqlalchemy import func
    from extensions import db
    from models import AnalyticsEvent
    since = datetime.utcnow() - timedelta(days=max(int(days), 1))
    rows = (db.session.query(AnalyticsEvent.name, func.count(AnalyticsEvent.id))
            .filter(AnalyticsEvent.created_at >= since)
            .group_by(AnalyticsEvent.name).all())
    return {name: n for name, n in rows}
