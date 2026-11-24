"""ProxyFix for deployments behind one TLS-terminating proxy (Render). See docs/DEPLOY.md.

Enabled when FLASK_ENV=production or TRUST_PROXY is truthy. Never enable it without a trusted proxy in front:
a client could then forge X-Forwarded-For (rate-limit bypass) and X-Forwarded-Proto/Host.
With it, `request.is_secure`, `url_for(_external=True)`, `request.host` and `request.remote_addr` (the rate-limit key)
describe the real client request.
"""
import os

from werkzeug.middleware.proxy_fix import ProxyFix


def proxy_enabled(env=os.environ):
    return env.get('FLASK_ENV') == 'production' or str(env.get('TRUST_PROXY') or '').strip().lower() in ('1', 'true', 'yes', 'on')


def init_proxy(app, env=os.environ):
    """Wrap `app.wsgi_app` (outermost, so Socket.IO sees the fixed environ too) when behind a proxy. Returns True if wrapped."""
    if not proxy_enabled(env):
        return False
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=0)
    return True
