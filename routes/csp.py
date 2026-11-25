"""POST /csp-report: browsers send a CSP violation here (report-uri). Logs only the directive and the blocked origin."""
import logging
from urllib.parse import urlsplit

from flask import Blueprint, request

from core.extensions import csrf, limiter

csp_bp = Blueprint('csp', __name__)
logger = logging.getLogger(__name__)


def _short(value, limit=80):
    return ''.join(c for c in str(value or '') if c.isprintable())[:limit]


@csp_bp.route('/csp-report', methods=['POST'])
@csrf.exempt  # browsers cannot send a CSRF token with a report
@limiter.limit('30 per minute')
def csp_report():
    body = request.get_json(silent=True, force=True) or {}
    report = body.get('csp-report') if isinstance(body, dict) else None
    if isinstance(report, dict):
        blocked = str(report.get('blocked-uri') or '')
        parts = urlsplit(blocked)  # origin only: a full URL can carry a query string with personal data
        origin = f'{parts.scheme}://{parts.netloc}' if parts.netloc else blocked
        logger.warning('csp violation directive=%s blocked=%s', _short(report.get('effective-directive') or
                       report.get('violated-directive')), _short(origin))
    return '', 204
