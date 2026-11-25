"""Journal-entry and voice-log routes moved out of app.py (continuing the O-15 cleanup).

Endpoint names and URLs are unchanged: they are registered on the app with `add_url_rule`, not on a
blueprint, because a blueprint would prefix every endpoint name.
"""
import logging
import os

from flask import jsonify, request, session

logger = logging.getLogger('app')  # same logger (and file handler) the routes used inside app.py

# File upload configuration
ALLOWED_EXTENSIONS = {'wav', 'mp3', 'ogg'}  # voice logs only; nothing uploaded is stored on disk
ALLOWED_MIME_TYPES = {'audio/wav', 'audio/mpeg', 'audio/ogg'}


def validate_file_security(file):
    """
    Comprehensive file validation for security and compatibility
    Returns: (is_valid: bool, error_message: str)
    """
    try:
        # Check if file exists
        if not file or not file.filename:
            return False, "No file selected"

        # Check file extension
        if not ('.' in file.filename and
                file.filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS):
            return False, f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"

        # Get file size
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)  # Reset file pointer

        # Check file size (16MB max)
        max_size = 16 * 1024 * 1024
        if file_size > max_size:
            return False, f"File too large. Maximum size: {max_size // (1024 * 1024)}MB"

        # Check for malicious content in filename
        if any(char in file.filename for char in ['..', '/', '\\', ':', '*', '?', '"', '<', '>', '|']):
            return False, "Invalid characters in filename"

        return True, "File validation successful"

    except Exception as e:
        logger.error(f"Error during file validation: {e}")
        return False, "File validation error"


def delete_journal_entry(entry_id):
    """Delete one of the session user's journal entries."""
    from core.extensions import db
    from models import JournalEntry

    entry = JournalEntry.query.filter_by(id=entry_id, user_id=session['user_id']).first()
    if not entry:
        return jsonify({'success': False, 'message': 'Journal entry not found'}), 404
    try:
        db.session.delete(entry)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Journal entry deleted successfully'})
    except Exception:
        db.session.rollback()
        logger.exception("Error deleting journal entry")
        return jsonify({'success': False, 'message': 'Failed to delete journal entry'}), 500


def delete_voice_log(voice_log_id):
    """Delete one of the session user's voice logs (measurements and note; no audio is stored)."""
    from core.extensions import db
    from models import VoiceLog

    voice_log = VoiceLog.query.filter_by(id=voice_log_id, user_id=session['user_id']).first()
    if not voice_log:
        return jsonify({'success': False, 'message': 'Voice log not found'}), 404
    try:
        db.session.delete(voice_log)
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("Error deleting voice log")
        return jsonify({'success': False, 'message': 'Failed to delete voice log'}), 500
    return jsonify({'success': True, 'message': 'Voice log deleted successfully'})


def upload_voice():
    """Upload a voice recording, analyse it if possible and store a VoiceLog for the session user."""
    from core.extensions import db
    from models import VoiceLog
    from utils.gamification import award_points

    user_id = session['user_id']
    audio_file = request.files.get('audio')
    if not audio_file or not audio_file.filename:
        return jsonify({'success': False, 'message': 'No audio file provided'}), 400
    if not (audio_file.content_type or '').startswith('audio/'):
        return jsonify({'success': False, 'message': 'Invalid file type. Please upload an audio file.'}), 400
    is_valid, error_message = validate_file_security(audio_file)
    if not is_valid:
        return jsonify({'success': False, 'message': error_message}), 400

    try:
        from utils.voice_features import extract_features  # analysed in memory/temp file; only duration is stored
        audio_features = extract_features(audio_file, audio_file.filename.rsplit('.', 1)[1].lower())
        voice_log = VoiceLog(
            user_id=user_id,
            filename='not-stored',  # placeholder for the non-null column: the audio is never kept
            audio_features=audio_features,
        )
        db.session.add(voice_log)
        db.session.commit()
        award_points(user_id, 20, 'voice_log', ref=f'voice:{voice_log.id}')

        return jsonify({
            'success': True,
            'message': 'Voice log saved. The audio was analysed and not kept.',
            'voice_log': {'id': voice_log.id, 'audio_features': audio_features}
        })
    except Exception:
        db.session.rollback()
        logger.exception("Error uploading voice file")
        return jsonify({'success': False, 'message': 'Failed to process voice recording'}), 500


def register_journal_voice_routes(app):
    from core.decorators import login_required, role_required
    from core.extensions import limiter

    app.add_url_rule('/api/delete-journal-entry/<int:entry_id>', 'delete_journal_entry',
                      login_required(role_required('patient')(delete_journal_entry)), methods=['DELETE'])
    app.add_url_rule('/api/delete-voice-log/<int:voice_log_id>', 'delete_voice_log',
                      login_required(role_required('patient')(delete_voice_log)), methods=['DELETE'])
    app.add_url_rule('/api/upload-voice', 'upload_voice',
                      login_required(role_required('patient')(limiter.limit("5 per hour")(upload_voice))), methods=['POST'])
