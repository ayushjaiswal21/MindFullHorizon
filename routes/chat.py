from datetime import date

from flask import Blueprint, request, jsonify, current_app, session, url_for
from ai.service import ask_with_severity
from decorators import api_login_required
from extensions import db
from models import Appointment, Notification
from utils.crisis import record_crisis
import asyncio

bp = Blueprint('chat_api', __name__, url_prefix='/api')


@bp.route('/chats/<int:chat_id>/messages', methods=['GET'])
@api_login_required
def chat_messages(chat_id):
    # A "chat" is the logged-in user's own inbox; the id must be theirs.
    if chat_id != session['user_id']:
        return jsonify({"ok": False, "error": "Forbidden"}), 403
    msgs = Notification.query.filter_by(recipient_id=chat_id).order_by(Notification.created_at.asc()).all()
    return jsonify([{"id":m.id, "user":m.sender.name if m.sender else 'System', "text":m.message} for m in msgs])

@bp.route('/chat', methods=['POST'])
@api_login_required
def chat_handler():
    payload = request.get_json(silent=True)
    text = payload.get('message') if isinstance(payload, dict) else None
    if not isinstance(text, str) or not text.strip():
        return jsonify({"ok": False, "error": "message is required"}), 400
    try:
        # user id comes from the session only; a client-sent user_id is ignored
        resp = asyncio.run(ask_with_severity(text[:2000], user_id=session['user_id']))
        if resp.get('escalate'):
            record_crisis(session['user_id'], 'chat', resp.get('severity'), 'chat_self_harm')
        out = {"ok": True, **{k: resp.get(k) for k in
               ("reply", "severity", "reason", "recommended_action", "escalate", "helplines")}}
        return jsonify(out), 200
    except Exception:
        current_app.logger.exception("Chat handler failed")
        return jsonify({"ok": False, "error": "Something went wrong. Please try again."}), 500

@bp.route('/chat/book-appointment', methods=['POST'])
@api_login_required
def book_appointment():
    if session.get('user_role') != 'patient':
        return jsonify({"ok": False, "error": "Only patients can book"}), 403
    data = request.get_json(silent=True)
    note = data.get('user_message') if isinstance(data, dict) else None
    try:
        # Date/time are agreed later by the provider, so this is a pending request for today with time 'TBD'.
        appt = Appointment(user_id=session['user_id'], date=date.today(), time='TBD', appointment_type='chat_referral',
                           notes=(note or '')[:500] if isinstance(note, str) else None, status='pending')
        db.session.add(appt)
        db.session.commit()
        return jsonify({"ok": True, "id": appt.id, "message": "Appointment request received. A provider will contact you.",
                        "schedule_url": url_for('patient.schedule_appointment')}), 201
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Book appointment failed")
        return jsonify({"ok": False, "error": "Could not save your request. Please use the schedule page."}), 500
