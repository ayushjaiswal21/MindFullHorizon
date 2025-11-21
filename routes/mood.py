from flask import Blueprint, request, jsonify, current_app
from extensions import db
from models import MoodLog

bp = Blueprint('mood', __name__, url_prefix='/api')

@bp.route('/mood', methods=['POST'])
def save_mood():
    try:
        data = request.get_json(force=True)
        val = data.get('value')
        if val is None:
            return jsonify({"error":"missing 'value'"}), 400

        # TODO: replace user_id=1 with actual authenticated user id
        m = MoodLog(mood_score=int(val), user_id=1)
        db.session.add(m)
        db.session.commit()

        return jsonify({
            "ok": True,
            "id": m.id,
            "mood": m.mood_score,
            "created_at": m.created_at.isoformat() if hasattr(m, 'created_at') else None,
            "message": "Mood saved."
        }), 201
    except Exception as e:
        current_app.logger.exception("Mood save failed")
        db.session.rollback()
        return jsonify({"error": "server", "message": str(e)}), 500

@bp.route('/mood', methods=['GET'])
def get_moods():
    try:
        moods = MoodLog.query.order_by(MoodLog.created_at.asc()).limit(500).all()
        out = []
        for m in moods:
            out.append({
                "id": m.id,
                "mood": m.mood_score,
                "created_at": m.created_at.isoformat() if hasattr(m, 'created_at') else None
            })
        return jsonify({"ok": True, "moods": out}), 200
    except Exception as e:
        current_app.logger.exception("Get moods failed")
        return jsonify({"ok": False, "error": str(e)}), 500