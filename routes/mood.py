from flask import Blueprint, request, jsonify, current_app, session
from decorators import api_login_required
from extensions import db
from models import MoodLog

bp = Blueprint('mood', __name__, url_prefix='/api')

@bp.route('/mood', methods=['POST'])
@api_login_required
def save_mood():
    data = request.get_json(silent=True) or {}
    try:
        val = int(data.get('value'))
    except (TypeError, ValueError, AttributeError):
        val = 0
    if not 1 <= val <= 10:
        return jsonify({"error": "'value' must be a whole number from 1 to 10"}), 400
    try:
        m = MoodLog(mood_score=int(val), user_id=session['user_id'])
        db.session.add(m)
        db.session.commit()

        return jsonify({
            "ok": True,
            "id": m.id,
            "mood": m.mood_score,
            "created_at": m.created_at.isoformat() if hasattr(m, 'created_at') else None,
            "message": "Mood saved."
        }), 201
    except Exception:
        current_app.logger.exception("Mood save failed")
        db.session.rollback()
        return jsonify({"error": "server", "message": "Could not save mood."}), 500

@bp.route('/mood', methods=['GET'])
@api_login_required
def get_moods():
    try:
        moods = MoodLog.query.filter_by(user_id=session['user_id']).order_by(MoodLog.created_at.asc()).limit(500).all()
        out = []
        for m in moods:
            out.append({
                "id": m.id,
                "mood": m.mood_score,
                "created_at": m.created_at.isoformat() if hasattr(m, 'created_at') else None
            })
        return jsonify({"ok": True, "moods": out}), 200
    except Exception:
        current_app.logger.exception("Get moods failed")
        return jsonify({"ok": False, "error": "Could not load moods."}), 500
