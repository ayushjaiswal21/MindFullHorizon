"""Security response headers and the Content-Security-Policy (enforcing by default).

One call from app.py: `init_security_headers(app)`. It creates the per-request nonce (`g.csp_nonce`, used by the
templates), adds the headers to every response (pages, JSON, error pages) and registers the `/csp-report` endpoint.

Env switches: `CSP_REPORT_ONLY=1` sends the same policy as Content-Security-Policy-Report-Only (emergency fallback if a
page breaks in production; nothing is blocked). `CSP_ENFORCE=0` is the legacy spelling of the same fallback.
`AUDIO_BASE_URL` adds its origin to `media-src`. Policy and rationale: docs/SECURITY.md.
"""
import base64
import os
from urllib.parse import urlsplit

from flask import g, request

_SELF = "'self'"


def _production():
    return os.getenv('FLASK_ENV') == 'production'


def report_only_mode():
    """True when the fallback switch asks for Report-Only (CSP_REPORT_ONLY=1, or the legacy CSP_ENFORCE=0)."""
    return os.getenv('CSP_REPORT_ONLY') == '1' or os.getenv('CSP_ENFORCE') == '0'


def _origin(url):
    parts = urlsplit((url or '').strip())
    return f'{parts.scheme}://{parts.netloc}' if parts.scheme in ('http', 'https') and parts.netloc else ''


def build_csp(nonce, host='', audio_base_url=None, production=None):
    """Return the policy string. `host` (the request Host) is added as ws/wss for Socket.IO, because Safari does not
    treat 'self' as covering websockets."""
    production = _production() if production is None else production
    audio_base_url = os.environ.get('AUDIO_BASE_URL', '') if audio_base_url is None else audio_base_url
    audio = _origin(audio_base_url)
    sockets = [f'wss://{host}'] + ([] if production else [f'ws://{host}']) if host else []
    directives = [
        ('default-src', [_SELF]),
        ('script-src', [_SELF, f"'nonce-{nonce}'"]),
        ('style-src', [_SELF, f"'nonce-{nonce}'"]),
        ('style-src-attr', ["'none'"]),  # no inline style= attributes anywhere (tests/test_csp.py scans for them)
        ('img-src', [_SELF, 'data:', 'https://i.ytimg.com']),
        ('font-src', [_SELF]),
        ('connect-src', [_SELF] + sockets),
        ('media-src', [_SELF, 'blob:'] + ([audio] if audio else [])),  # blob: plays back the user's own voice recording
        ('frame-src', ['https://www.youtube-nocookie.com']),
        ('object-src', ["'none'"]),
        ('base-uri', [_SELF]),
        ('form-action', [_SELF]),  # Google sign-in is a link to /login/google, not a form post
        ('frame-ancestors', ["'none'"]),
        ('report-uri', ['/csp-report']),
    ]
    parts = [f"{name} {' '.join(values)}" for name, values in directives]
    if production:
        parts.append('upgrade-insecure-requests')
    return '; '.join(parts)


def apply_headers(response, nonce, host=''):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Cross-Origin-Opener-Policy'] = 'same-origin'
    # Voice logs and telehealth need the microphone and camera, for this origin only.
    response.headers['Permissions-Policy'] = 'camera=(self), microphone=(self), geolocation=()'
    name = 'Content-Security-Policy-Report-Only' if report_only_mode() else 'Content-Security-Policy'
    response.headers[name] = build_csp(nonce or '', host)
    if _production():
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response


def init_security_headers(app):
    from routes.csp import csp_bp  # imported here: routes import extensions, which app.py has loaded by now

    @app.before_request
    def generate_csp_nonce():
        g.csp_nonce = base64.b64encode(os.urandom(18)).decode('ascii')  # 24 characters, new for every request

    @app.after_request
    def add_security_headers(response):
        return apply_headers(response, g.get('csp_nonce'), request.host)

    app.register_blueprint(csp_bp)
