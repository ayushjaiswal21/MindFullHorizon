from flask import Blueprint, request, jsonify, current_app
from extensions import db
from models import MoodLog

bp = Blueprint('mood', __name__, url_prefix='/api')

@bp.route('/mood', methods=['POST'])
def save_mood():
    try:
        data = request.get_json(force=True)
        m = MoodLog(mood_score=int(data.get('value', 0)), user_id=1) # Assuming user_id 1 for now
        db.session.add(m)
        db.session.commit()
        return jsonify({"ok": True}), 201
    except Exception as e:
        current_app.logger.exception("Mood save failed")
        db.session.rollback()
        return jsonify({"error": "server"}), 500