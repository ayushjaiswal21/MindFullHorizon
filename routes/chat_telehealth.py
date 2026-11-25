"""Chat page and telehealth routes moved out of app.py (continuing the O-15 cleanup).

Endpoint names and URLs are unchanged (`url_for('chat')`, `url_for('telehealth')`, ...): they are
registered on the app with `add_url_rule`, not on a blueprint, because a blueprint would prefix
every endpoint name.
"""
import logging

from flask import jsonify, render_template, request, session

from decorators import can_join_telehealth, login_required
from extensions import limiter

logger = logging.getLogger('app')  # same logger (and file handler) the routes used inside app.py


def chat():
    from utils.chat_templates import public_list
    return render_template('chat.html', user_name=session['user_name'], starters=public_list())


def api_message():
    """Quick message between a patient and a provider who are linked (ProviderPatient row or an appointment)."""
    from extensions import db
    from models import Appointment, Notification, ProviderPatient, User

    data = request.get_json(silent=True)
    data = data if isinstance(data, dict) else {}
    recipient_id, message = data.get('recipient_id'), data.get('message')
    if isinstance(recipient_id, str) and recipient_id.isdigit():
        recipient_id = int(recipient_id)
    if isinstance(recipient_id, bool) or not isinstance(recipient_id, int) or not isinstance(message, str) or not message.strip():
        return jsonify(success=False, error='recipient_id and message are required'), 400
    message = message.strip()
    if len(message) > 1000:
        return jsonify(success=False, error='Message is too long (1000 characters at most)'), 400
    sender_id, role = session.get('user_id'), session.get('user_role')
    recipient = db.session.get(User, recipient_id) if recipient_id != sender_id else None
    allowed = False
    if recipient and {role, recipient.role} == {'patient', 'provider'}:
        patient_id, provider_id = (sender_id, recipient_id) if role == 'patient' else (recipient_id, sender_id)
        allowed = (ProviderPatient.query.filter_by(provider_id=provider_id, patient_id=patient_id).first() is not None
                   or Appointment.query.filter_by(user_id=patient_id, provider_id=provider_id).first() is not None)
    if not allowed:  # same answer for unknown, self, wrong role and unlinked recipients: no user enumeration
        return jsonify(success=False, error='You cannot message this recipient'), 403
    try:
        notif = Notification(sender_id=sender_id, recipient_id=recipient_id, message=message, type='message', payload=None)
        db.session.add(notif)
        db.session.commit()
        return jsonify(success=True, id=notif.id)
    except Exception as e:
        db.session.rollback()
        logger.error("Failed to create message: %s", type(e).__name__)
        return jsonify(success=False, error='Could not send message'), 500


def telehealth_session(user_id):
    from models import User

    if session.get('user_role') != 'provider' or not can_join_telehealth(user_id):
        return "Forbidden", 403
    patient = User.query.get_or_404(user_id)
    return render_template('telehealth.html',
                            user_name=session['user_name'],
                            patient_id=patient.id,
                            patient_name=patient.name)


def telehealth():
    return render_template('telehealth.html', user_name=session['user_name'])


def register_chat_telehealth_routes(app):
    app.add_url_rule('/chat', 'chat', login_required(chat))
    app.add_url_rule('/api/message', 'api_message', login_required(limiter.limit('30 per minute')(api_message)), methods=['POST'])
    app.add_url_rule('/telehealth_session/<int:user_id>', 'telehealth_session', login_required(telehealth_session))
    app.add_url_rule('/telehealth', 'telehealth', login_required(telehealth))
