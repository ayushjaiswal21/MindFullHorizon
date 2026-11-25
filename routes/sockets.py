"""SocketIO event handlers moved out of app.py (continuing the O-15 cleanup).

Registered with `register_socketio_handlers(socketio)` from app.py, mirroring the
`register_audio_routes(app)` pattern already used for Flask routes.
"""
import logging
import re

from flask import session
from flask_socketio import emit, join_room, leave_room, rooms

from core.decorators import can_join_telehealth

logger = logging.getLogger('app')  # same logger (and file handler) the handlers used inside app.py

TELEHEALTH_ROOM = re.compile(r'telehealth_room_(\d+)')


def _room_of(data):
    """Room name from a socket payload, or None if malformed or not a telehealth room."""
    room = data.get('room') if isinstance(data, dict) else None
    return room if isinstance(room, str) and TELEHEALTH_ROOM.fullmatch(room) else None


def _joined_room(data):
    """Room for signalling events: the caller must be logged in and already (authorised) in it."""
    room = _room_of(data)
    return room if room and session.get('user_id') and room in rooms() else None


def register_socketio_handlers(socketio):
    # --- SocketIO User Room Management ---
    @socketio.on('connect')
    def handle_connect():
        """Handle user connection and join their personal room"""
        if 'user_id' in session:
            user_room = f'user_{session["user_id"]}'
            join_room(user_room)
            logger.info(f"User {session['user_id']} connected and joined room {user_room}")
            emit('connected', {'message': 'Connected to notification system'})

    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle user disconnection"""
        if 'user_id' in session:
            user_room = f'user_{session["user_id"]}'
            leave_room(user_room)
            logger.info(f"User {session['user_id']} disconnected from room {user_room}")

    # --- SocketIO Chat Handler ---
    @socketio.on('chat_message')
    def handle_chat_message(data):
        import ai.service as ai_service

        # Basic validation - check if user is logged in via session
        if 'user_email' not in session:
            emit('error', {'message': 'Authentication required'})
            return

        user_message = data.get('message')
        if not user_message or not isinstance(user_message, str):
            emit('error', {'message': 'Invalid message format'})
            return

        # Sanitize user input
        user_message = user_message.strip()[:500]  # Limit message length
        if not user_message:
            emit('error', {'message': 'Message cannot be empty'})
            return

        try:
            ai_resp = ai_service.generate_chat_response(user_message)
            if isinstance(ai_resp, dict):
                reply_text = ai_resp.get('response') or ai_resp.get('reply') or str(ai_resp)
                is_crisis = bool(ai_resp.get('needs_followup')) or bool(ai_resp.get('is_crisis'))
            else:
                reply_text = str(ai_resp)
                is_crisis = False

            # Log the interaction for monitoring
            logger.info(f"Chat interaction - User: {session.get('user_email', 'unknown')}, Length: {len(user_message)}, Crisis: {is_crisis}")

        except Exception as e:
            logger.error(f"Chat handler error: {e}")
            reply_text = "I apologize, but I'm having trouble responding right now. Please try again in a moment."
            is_crisis = False

        # O-02: rule-based floor, independent of the model; the emergency reply below never waits on the DB write
        from utils.crisis import text_is_crisis, try_record_crisis
        if text_is_crisis(user_message):
            is_crisis = True
            try_record_crisis(session.get('user_id'), 'chat', 9, 'chat_self_harm')

        emit('chat_response', {'reply': reply_text, 'is_crisis': is_crisis})

    # --- SocketIO Telehealth Handlers ---
    @socketio.on('join')
    def on_join(data):
        room = _room_of(data)
        if not room or not can_join_telehealth(int(TELEHEALTH_ROOM.fullmatch(room).group(1))):
            emit('join_error', {'message': 'Not allowed to join this session'})
            return {'ok': False, 'error': 'forbidden'}
        join_room(room)
        emit('message', 'A participant has joined the session.', to=room)
        # Notify the other user in the room that a peer is ready
        emit('ready', to=room, include_self=False)
        return {'ok': True}

    @socketio.on('offer')
    def on_offer(data):
        if room := _joined_room(data):
            emit('offer', data, to=room, include_self=False)

    @socketio.on('answer')
    def on_answer(data):
        if room := _joined_room(data):
            emit('answer', data, to=room, include_self=False)

    @socketio.on('candidate')
    def on_candidate(data):
        if room := _joined_room(data):
            emit('candidate', data, to=room, include_self=False)

    @socketio.on('leave')
    def on_leave(data):
        if room := _joined_room(data):
            leave_room(room)
            emit('_disconnect', to=room, include_self=False)
            emit('message', 'A participant has left the session.', to=room)
