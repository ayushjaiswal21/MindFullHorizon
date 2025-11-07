from flask import Blueprint, jsonify, current_app
bp = Blueprint('assessment', __name__, url_prefix='/api/assessment')

@bp.route('/next', methods=['GET'])
def next_assessment():
    sample = {
        "id": 1,
        "title": "Sample AI Assessment",
        "questions": [
            {"id": 1, "text": "What is AI?", "options": ["Algorithm", "Magic", "Process"]}
        ]
    }
    return jsonify(sample)