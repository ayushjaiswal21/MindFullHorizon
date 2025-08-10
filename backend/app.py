import os
from flask import Flask, request, jsonify, render_template, send_from_directory
import json
import random

# For demonstration, we'll use a dummy model. You will replace this with your real ML model.
try:
    from ml_model.dummy_model import predict_risk_score
except ImportError:
    # This will print an error if the dummy_model file is not found.
    print("ERROR: Could not find 'ml_model/dummy_model.py'. Please check your file structure.")
    # We'll create a dummy function to allow the server to start for now.
    def predict_risk_score(responses):
        return random.randint(0, 100), ["Dummy insights: Model file not found."]

# The key change is here: we set the static_url_path to serve static files from the root.
app = Flask(__name__, static_folder='../frontend', template_folder='../frontend', static_url_path='')

# --- In-memory "Database" for Prototype ---
# In a real application, you would use a proper database like MySQL or PostgreSQL.
users = {
    "patient@example.com": {"password": "password123", "role": "patient", "name": "John Doe"},
    "student@example.com": {"password": "password123", "role": "student", "name": "Jane Smith"},
    "doctor@example.com": {"password": "password123", "role": "doctor", "name": "Dr. Smith"},
}

# --- Frontend Routes ---
# This serves all your static HTML, CSS, and JS files.
@app.route('/')
def home():
    """Serves the main landing page."""
    return render_template('index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    """Serves all other static files from the frontend directory."""
    return send_from_directory(app.template_folder, filename)

# --- API Endpoints ---
@app.route('/api/register', methods=['POST'])
def register_user():
    """Handles new user registration."""
    data = request.json
    email = data.get('email')
    password = data.get('password')
    role = data.get('role')
    name = data.get('name')

    if email in users:
        return jsonify({"success": False, "message": "Email already exists."}), 409

    users[email] = {"password": password, "role": role, "name": name}
    print(f"New user registered: {email} with role {role}")
    return jsonify({"success": True, "message": "User registered successfully."}), 201

@app.route('/api/login', methods=['POST'])
def login_user():
    """Handles user login."""
    data = request.json
    email = data.get('email')
    password = data.get('password')

    user = users.get(email)

    if user and user['password'] == password:
        # In a real app, you would generate a JWT token here.
        print(f"User logged in: {email}")
        return jsonify({
            "success": True,
            "message": "Login successful.",
            "user": {"email": email, "role": user['role'], "name": user['name']}
        }), 200
    else:
        return jsonify({"success": False, "message": "Invalid email or password."}), 401

@app.route('/api/predict', methods=['POST'])
def predict_assessment():
    """Handles the mental health assessment submission and provides a prediction."""
    data = request.json
    # The 'data' payload would contain the user's responses.
    # We call our dummy model here.
    risk_score, insights = predict_risk_score(data.get('responses', []))
    
    return jsonify({
        "success": True,
        "risk_score": risk_score,
        "insights": insights,
        "message": "Assessment processed successfully."
    }), 200

if __name__ == '__main__':
    app.run(debug=True)
