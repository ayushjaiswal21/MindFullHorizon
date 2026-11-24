from flask import Blueprint, render_template, jsonify, request, session
from sqlalchemy.exc import SQLAlchemyError
from decorators import api_login_required

core_bp = Blueprint('core', __name__)

@core_bp.route('/')
def index():
    # Logged-in users get the app home; visitors get the public landing page.
    if session.get('user_id'):
        return render_template('index.html')
    from models import BlogPost
    try:
        posts = BlogPost.query.filter_by(is_published=True).order_by(BlogPost.created_at.desc()).limit(3).all()
    except SQLAlchemyError:
        posts = []
    return render_template('landing.html', posts=posts)

@core_bp.route('/api/status')
def status():
    return jsonify({"status": "ok"})

@core_bp.route('/api/ask', methods=['POST'])
@api_login_required
def ask_route():
    from ai.service import ask
    data = request.get_json(silent=True)
    prompt = data.get('prompt') if isinstance(data, dict) else None
    if not isinstance(prompt, str) or not prompt.strip():
        return jsonify({"error": "prompt is required"}), 400
    return jsonify({"response": ask(prompt[:2000])})
