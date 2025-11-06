from flask import Blueprint, render_template, jsonify, request

core_bp = Blueprint('core', __name__)

@core_bp.route('/')
def index():
    return render_template('index.html')

@core_bp.route('/api/status')
def status():
    return jsonify({"status": "ok"})

@core_bp.route('/api/ask', methods=['POST'])
def ask_route():
    from ai.service import ask
    prompt = request.json.get('prompt')
    response = ask(prompt)
    return jsonify({"response": response})