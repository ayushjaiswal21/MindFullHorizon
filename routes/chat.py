from flask import Blueprint, jsonify
from models import Notification, User
bp = Blueprint('chat', __name__, url_prefix='/api')

@bp.route('/chats/<int:chat_id>/messages', methods=['GET'])
def chat_messages(chat_id):
    # For simplicity, we'll just use the chat_id as the user_id to fetch messages for.
    # In a real app, you'd have a more complex chat room model.
    msgs = Notification.query.filter_by(recipient_id=chat_id).order_by(Notification.created_at.asc()).all()
    return jsonify([{"id":m.id, "user":m.sender.name if m.sender else 'System', "text":m.message} for m in msgs])