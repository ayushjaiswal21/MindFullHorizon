"""Template context shared by every page (base.html, partials, errors) and the 404/500 renderers.

Env: SITE_URL (public origin, no trailing slash), CONTACT_RECIPIENT, CONSENT_VERSION, ASSET_VERSION.
"""
import os
from datetime import date

from flask import current_app, has_request_context, jsonify, render_template, request, url_for
from werkzeug.routing import BuildError

from utils import ai_policy, daily_tip
from utils.feature_flags import prescriptions_enabled
from utils.helplines import get_helplines

# Bump when the site content or policies change in a way a visitor should see in the footer.
SITE_LAST_UPDATED = '2026-11-24'

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ASSET_FILES = ('static/css/site.css', 'static/css/site-components.css', 'static/css/components.css',
                'static/css/tailwind.css', 'static/js/shell.js', 'static/js/components.js') + tuple(
    f'static/css/site-legacy-{i}.css' for i in range(1, 8))


def _asset_version():
    """Cache-busting token for ?v= links: ASSET_VERSION env, else newest mtime of the shell assets."""
    env = os.environ.get('ASSET_VERSION', '').strip()
    if env:
        return env
    stamps = []
    for rel in _ASSET_FILES:
        try:
            stamps.append(int(os.path.getmtime(os.path.join(_ROOT, rel))))
        except OSError:
            pass
    return str(max(stamps)) if stamps else SITE_LAST_UPDATED


def site_url():
    configured = os.environ.get('SITE_URL', '').strip().rstrip('/')
    if configured:
        return configured
    return request.url_root.rstrip('/') if has_request_context() else ''


def abs_url(path):
    """Absolute URL for a site path; absolute URLs pass through."""
    if not path or path.startswith(('http://', 'https://')):
        return path or ''
    return site_url() + (path if path.startswith('/') else '/' + path)


def nav_url(endpoint, fallback='/'):
    """url_for that never crashes a page when another blueprint renames or lacks an endpoint."""
    try:
        return url_for(endpoint)
    except BuildError:
        return fallback


def _display_date(iso):
    try:
        d = date.fromisoformat(iso)
        return f'{d.day} {d.strftime("%b %Y")}'
    except ValueError:
        return iso


def _context():
    return {
        'prescriptions_enabled': prescriptions_enabled(),
        'site_url': site_url(),
        'contact_email': os.environ.get('CONTACT_RECIPIENT', '').strip(),
        'helplines': get_helplines(),
        'consent_version': os.environ.get('CONSENT_VERSION', '2026-11').strip() or '2026-11',
        'site_last_updated': SITE_LAST_UPDATED,
        'site_last_updated_display': _display_date(SITE_LAST_UPDATED),
        'asset_version': _asset_version(),
        'ai_personal_text': ai_policy.personal_text_allowed(),  # copy must match what is really sent to a model
        'anya_kind': ai_policy.assistant_kind(),
    }


_MESSAGES = {
    404: 'That page was not found.',
    500: 'Something went wrong on our side.',
}


def render_error_page(code):
    """HTML error page for browsers, small JSON for /api/ paths and fetch callers. Never exposes exception text."""
    wants_json = request.path.startswith('/api/') or (
        request.accept_mimetypes.best == 'application/json' and not request.accept_mimetypes.accept_html)
    if wants_json:
        return jsonify({'success': False, 'error': _MESSAGES.get(code, 'Request failed.')}), code
    try:
        return render_template(f'errors/{code}.html'), code
    except Exception:  # the page itself must never turn a 500 into a blank screen
        current_app.logger.exception('error template failed')
        return f'<h1>{_MESSAGES.get(code, "Error")}</h1><p><a href="/">Back to home</a></p>', code


def init_site_context(app):
    app.context_processor(_context)
    app.jinja_env.globals.update(abs_url=abs_url, nav_url=nav_url, daily_tip=daily_tip.get_tip)
    app.register_error_handler(404, lambda e: render_error_page(404))
