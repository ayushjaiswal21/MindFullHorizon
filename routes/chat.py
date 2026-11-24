from datetime import date

from flask import Blueprint, request, jsonify, current_app, session, url_for
from ai.service import ask_with_severity
from decorators import api_login_required
from extensions import db
from models import Appointment, Notification
from utils.crisis import record_crisis
from utils.pagination import paginate, set_page_headers
from utils import idempotency as idem
from utils.timeutil import ist_today
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload
import asyncio

bp = Blueprint('chat_api', __name__, url_prefix='/api')
bp.register_error_handler(idem.InvalidKey, idem.handle_invalid_key)


@bp.route('/chats/<int:chat_id>/messages', methods=['GET'])
@api_login_required
def chat_messages(chat_id):
    # A "chat" is the logged-in user's own inbox; the id must be theirs.
    if chat_id != session['user_id']:
        return jsonify({"ok": False, "error": "Forbidden"}), 403
    # Newest page first (?page=, ?per_page=, default 20, max 100), returned oldest-to-newest. The body stays a bare
    # array (chat JS does Array.isArray), so paging info goes in X-Page / X-Per-Page / X-Total-Count / X-Has-Next.
    msgs, meta = paginate(Notification.query.options(joinedload(Notification.sender)).filter_by(recipient_id=chat_id)
                          .order_by(Notification.created_at.desc(), Notification.id.desc()))
    msgs.reverse()
    resp = jsonify([{"id":m.id, "user":m.sender.name if m.sender else 'System', "text":m.message} for m in msgs])
    return set_page_headers(resp, meta)

@bp.route('/chat', methods=['POST'])
@api_login_required
def chat_handler():
    payload = request.get_json(silent=True)
    text = payload.get('message') if isinstance(payload, dict) else None
    if not isinstance(text, str) or not text.strip():
        return jsonify({"ok": False, "error": "message is required"}), 400
    try:
        # user id comes from the session only; a client-sent user_id is ignored
        # the service bounds the text itself (20k) so the crisis floor sees all of it, then caps what the model gets
        resp = asyncio.run(ask_with_severity(text, user_id=session['user_id']))
        if resp.get('rate_limited'):  # budget spent and no risk signal: crisis texts never get here (they are answered)
            return jsonify({"ok": False, "error": resp.get('notice'), "reply": resp.get('notice'), "rate_limited": True,
                            "retry_after": resp.get('retry_after', 0), "helplines": resp.get('helplines') or []}), 429
        out = {"ok": True, **{k: resp.get(k) for k in
               ("reply", "severity", "reason", "recommended_action", "escalate", "helplines")}}
        if resp.get('ai_unavailable'):
            out["ai_unavailable"], out["notice"] = True, resp.get('notice')
        if resp.get('escalate'):
            # event + alert job commit together; the emergency reply above is returned even if this fails
            try:
                record_crisis(session['user_id'], 'chat', resp.get('severity'), 'chat_self_harm')
                db.session.commit()
            except Exception as exc:
                db.session.rollback()
                current_app.logger.error("crisis record FAILED user=%s source=chat err=%s",
                                         session['user_id'], type(exc).__name__)
                out["alert_recorded"] = False
        return jsonify(out), 200
    except Exception:
        current_app.logger.exception("Chat handler failed")
        return jsonify({"ok": False, "error": "Something went wrong. Please try again."}), 500

@bp.route('/chat/template', methods=['POST'])
@api_login_required
def chat_template():
    """Answer one of the fixed starter questions (allowlisted id only; see utils/chat_templates.py). No user text."""
    from utils import chat_templates
    payload = request.get_json(silent=True)
    tid = payload.get('template_id') if isinstance(payload, dict) else None
    res = chat_templates.answer(tid)
    if res is None:
        return jsonify({"ok": False, "error": "Unknown starter question."}), 400
    return jsonify({"ok": True, **res})


@bp.route('/chat/book-appointment', methods=['POST'])
@api_login_required
def book_appointment():
    if session.get('user_role') != 'patient':
        return jsonify({"ok": False, "error": "Only patients can book"}), 403
    data = request.get_json(silent=True)
    note = data.get('user_message') if isinstance(data, dict) else None
    uid, key = session['user_id'], idem.get_key()

    def body(a):
        return {"ok": True, "id": a.id, "message": "Appointment request received. A provider will contact you.",
                "schedule_url": url_for('patient.schedule_appointment')}
    try:
        # Date/time are agreed later by the provider, so this is a pending request for today with time 'TBD'.
        # A replay (same key) or a second live request for today (DB unique index) returns the existing one with 200.
        today = ist_today()
        existing = idem.existing(Appointment, uid, key) or Appointment.query.filter(
            Appointment.user_id == uid, Appointment.date == today, Appointment.time == 'TBD',
            Appointment.status.in_(('pending', 'accepted', 'booked'))).first()
        if existing:
            return jsonify(body(existing)), 200
        appt = Appointment(user_id=uid, date=today, time='TBD', appointment_type='chat_referral',
                           notes=(note or '')[:500] if isinstance(note, str) else None, status='pending', client_request_id=key)
        db.session.add(appt)
        try:
            db.session.commit()
        except IntegrityError:  # concurrent double submit
            db.session.rollback()
            existing = idem.existing(Appointment, uid, key) or Appointment.query.filter_by(
                user_id=uid, date=today, time='TBD', status='pending').first()
            if existing is None:
                raise
            return jsonify(body(existing)), 200
        return jsonify(body(appt)), 201
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Book appointment failed")
        return jsonify({"ok": False, "error": "Could not save your request. Please use the schedule page."}), 500
