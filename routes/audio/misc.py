"""Music page and mood-selection analytics logging."""
import json
import logging
import os
from datetime import datetime

from flask import jsonify, render_template, request, session

logger = logging.getLogger('app')  # same logger (and file handler) the routes used inside app.py
basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


def music():
    """Render the music discovery page which allows users to pick a mood and play binaural beats."""
    return render_template('music.html')


def api_log_mood_selection():
    """Log a user's mood music selection for analytics/debugging.

    Accepts JSON: { mood: 'calm', query: '...', video: 'youtube_id' }
    Logging is appended to `mood_selections.log` and written to the application logger.
    """
    if not request.is_json:
        return jsonify({'success': False, 'message': 'Request must be JSON'}), 400

    data = request.get_json() or {}
    mood = data.get('mood')
    query = data.get('query')
    video = data.get('video')
    user_id = session.get('user_id')

    if not mood:
        return jsonify({'success': False, 'message': 'Missing mood field'}), 400

    log_entry = {
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'user_id': user_id,
        'mood': mood,
        'query': query,
        'video': video,
        'ip': request.remote_addr
    }

    try:
        # Log via application logger for centralized logs
        logger.info(f"Mood selection: {log_entry}")

        # Also append to a simple file for quick analytics without DB migration
        try:
            with open(os.path.join(basedir, 'instance', 'mood_selections.log'), 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception as file_err:
            logger.debug(f"Failed to write mood selection to file: {file_err}")

        return jsonify({'success': True, 'message': 'Selection logged'})
    except Exception as e:
        logger.error(f"Error logging mood selection: {e}")
        return jsonify({'success': False, 'message': 'Failed to log selection'}), 500
