from flask import Blueprint, request, jsonify, current_app
from ai.service import ask_with_severity
from appointment import create_appointment_stub
from models import Notification, User
import asyncio

bp = Blueprint('chat_api', __name__, url_prefix='/api')

@bp.route('/chats/<int:chat_id>/messages', methods=['GET'])
def chat_messages(chat_id):
    # For simplicity, we'll just use the chat_id as the user_id to fetch messages for.
    # In a real app, you'd have a more complex chat room model.
    msgs = Notification.query.filter_by(recipient_id=chat_id).order_by(Notification.created_at.asc()).all()
    return jsonify([{"id":m.id, "user":m.sender.name if m.sender else 'System', "text":m.message} for m in msgs])

@bp.route('/chat', methods=['POST'])
def chat_handler():
    try:
        payload = request.get_json(force=True)
        text = payload.get('message','')
        user_id = payload.get('user_id')
        # call ask_with_severity (it's async wrapper but here run synchronously)
        resp = asyncio.run(ask_with_severity(text, user_id=user_id))
        out = {
            "ok": True,
            "reply": resp.get('reply'),
            "severity": resp.get('severity'),
            "reason": resp.get('reason'),
            "recommended_action": resp.get('recommended_action')
        }
        return jsonify(out), 200
    except Exception as e:
        current_app.logger.exception("Chat handler failed")
        return jsonify({"ok": False, "error": str(e)}), 500

@bp.route('/chat/book-appointment', methods=['POST'])
def book_appointment():
    try:
        data = request.get_json(force=True)
        result = create_appointment_stub(data)
        return jsonify(result), 201
    except Exception as e:
        current_app.logger.exception("Book appointment failed")
        return jsonify({"ok": False, "error": str(e)}), 500
