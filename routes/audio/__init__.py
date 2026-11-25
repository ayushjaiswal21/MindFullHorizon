"""Music and audio routes moved out of app.py (O-15), then split by domain for size (mood_music,
play, catalog, misc).

Endpoint names and URLs are unchanged (`url_for('serve_audio')` etc.): they are registered on the app
with `add_url_rule`, not on a blueprint, because a blueprint would prefix every endpoint name.
"""
from core.decorators import api_login_required
from core.extensions import limiter

from .mood_music import api_mood_music
from .play import api_play_mood, serve_audio
from .catalog import api_mood_audio
from .misc import api_log_mood_selection, music


def register_audio_routes(app):
    app.add_url_rule('/api/mood-music', 'api_mood_music', api_mood_music, methods=['GET'])
    app.add_url_rule('/api/play-mood', 'api_play_mood', api_login_required(api_play_mood), methods=['POST'])
    app.add_url_rule('/audio/<path:filename>', 'serve_audio', serve_audio, methods=['GET'])
    app.add_url_rule('/api/mood-audio', 'api_mood_audio', api_mood_audio, methods=['POST'])
    app.add_url_rule('/music', 'music', music, methods=['GET'])
    app.add_url_rule('/api/log-mood-selection', 'api_log_mood_selection', limiter.limit('30 per hour')(api_log_mood_selection), methods=['POST'])
