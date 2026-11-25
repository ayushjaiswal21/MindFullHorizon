"""Small one-off routes moved out of app.py (continuing the O-15 cleanup).

Endpoint names and URLs are unchanged: they are registered on the app with `add_url_rule`, not on a
blueprint, because a blueprint would prefix every endpoint name.
"""
import logging
import re

from flask import jsonify, request

logger = logging.getLogger('app')  # same logger (and file handler) the routes used inside app.py


def ai_status():
    """Check the status of the AI service."""
    import ai.service as ai_service
    status = ai_service.check_api_status()
    return jsonify(status)


def log_client_error():
    """Log client-side JavaScript errors for debugging."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'success': False, 'message': 'No data provided'}), 400

    def clean(v, n):  # one line, bounded: client text must not forge log lines
        return re.sub(r'[^ -~]', ' ', str(v))[:n]

    logger.warning(f"Client-side error: {clean(data.get('message', 'Unknown error'), 300)} "
                   f"at {clean(data.get('filename', 'unknown'), 200)}:{clean(data.get('lineno', 'unknown'), 10)} "
                   f"from {request.remote_addr}")
    return jsonify({'success': True, 'message': 'Error logged'}), 200


def register_misc_routes(app):
    from core.decorators import login_required
    from core.extensions import csrf, limiter

    app.add_url_rule('/api/ai-status', 'ai_status', login_required(ai_status))
    # Error logging endpoint for client-side errors
    app.add_url_rule('/api/log-error', 'log_client_error',
                      csrf.exempt(limiter.limit("10 per minute")(log_client_error)), methods=['POST'])
