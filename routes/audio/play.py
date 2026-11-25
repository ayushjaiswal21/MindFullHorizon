"""Picking and serving a single binaural track for a mood."""
import logging
import os
from urllib.parse import quote

from flask import jsonify, redirect, request, send_from_directory

logger = logging.getLogger('app')  # same logger (and file handler) the routes used inside app.py
basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


def api_play_mood():
    """Attempt to play a binaural track for the requested mood.

    Priority:
      1. Look for local audio files in data/binaural-beats-dataset/audio/ whose filename contains the mood.
         If found, return its /audio/ URL for the browser to play (never launch anything on the server).
      2. If DB has BinauralTrack with youtube_id for the mood, return a YouTube URL for frontend to open.
      3. Otherwise return a YouTube search URL for the mood query.

    Returns JSON: { success: True, action: 'local'|'youtube', url }
    """
    data = request.get_json(silent=True)
    mood = str(data.get('mood') or '').strip().lower() if isinstance(data, dict) else ''

    if not mood:
        return jsonify({'success': False, 'message': 'Missing mood parameter'}), 400

    # 1) local audio folder
    audio_dir = os.path.join(basedir, 'data', 'binaural-beats-dataset', 'audio')
    try:
        if os.path.isdir(audio_dir):
            # look for files containing the mood in filename
            for fn in os.listdir(audio_dir):
                if mood in fn.lower() and fn.lower().endswith(('.mp3', '.wav', '.m4a', '.flac')):
                    return jsonify({'success': True, 'action': 'local', 'url': f'/audio/audio/{quote(fn)}'})

    except Exception as e:
        logger.debug(f"Error while searching for local audio files: {e}")

    # 2) DB-backed YouTube id
    try:
        from models import BinauralTrack
        tracks = BinauralTrack.query.filter(BinauralTrack.emotion.ilike(f"%{mood}%")).all()
        if tracks:
            # Prefer tracks with youtube_id
            for t in tracks:
                if t.youtube_id:
                    url = f"https://www.youtube.com/watch?v={t.youtube_id}"
                    return jsonify({'success': True, 'action': 'youtube', 'url': url})
    except Exception:
        pass

    # Removed YouTube fallback. If no local file/DB record found return not found.
    return jsonify({'success': False, 'message': 'No local audio or DB track found for this mood.'}), 404


def serve_audio(filename):
    """Serve audio files from data/binaural-beats-dataset for in-browser playback.

    Supports both 'audio/' and 'tracks/' subdirectories found in common datasets.

    NOTE: This route is intentionally simple. If you deploy publicly, consider adding
    authentication and range requests for large files.
    """
    base_dir = os.path.join(basedir, 'data', 'binaural-beats-dataset')

    # Hosted deploys keep the big mp3s off git: set AUDIO_BASE_URL (e.g. an R2/S3 bucket URL)
    # and any file missing locally is redirected there.
    audio_base = os.environ.get('AUDIO_BASE_URL', '').rstrip('/')
    if audio_base and '..' not in filename.replace('\\', '/').split('/') \
            and not os.path.isfile(os.path.join(base_dir, filename)):
        return redirect(f"{audio_base}/{quote(filename)}")

    if not os.path.isdir(base_dir):
        return jsonify({'success': False, 'message': 'Audio directory not found'}), 404

    # Prevent directory traversal and ensure the file resides within base_dir
    safe_filename = os.path.normpath(filename).replace('\\', '/')
    if safe_filename.startswith('../') or safe_filename.startswith('..\\') or '..' in safe_filename.split('/'):
        return jsonify({'success': False, 'message': 'Invalid filename'}), 400

    full_path = os.path.join(base_dir, safe_filename)
    try:
        full_path = os.path.normpath(full_path)
        # Ensure full_path is inside base_dir
        if not full_path.startswith(os.path.normpath(base_dir)):
            return jsonify({'success': False, 'message': 'Invalid path'}), 400
        # Serve via send_from_directory using base_dir and the relative safe path
        return send_from_directory(base_dir, safe_filename)
    except Exception:
        return jsonify({'success': False, 'message': 'File not found'}), 404
