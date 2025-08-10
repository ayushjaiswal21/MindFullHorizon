from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from datetime import datetime, timedelta
import json
from functools import wraps

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-in-production'

# Mock data storage (in production, use a proper database)
users = {
    'patient@example.com': {'password': 'password', 'role': 'patient', 'name': 'John Doe'},
    'provider@example.com': {'password': 'password', 'role': 'provider', 'name': 'Dr. Smith'}
}

# Patient gamification data
patient_data = {
    'patient@example.com': {
        'points': 1250,
        'streak': 7,
        'badges': ['Early Bird', 'Consistency Champion', 'Mood Tracker'],
        'rpm_data': {
            'heart_rate': 72,
            'sleep_duration': 7.5,
            'steps': 8500,
            'mood_score': 8
        }
    }
}

# Provider caseload data
caseload_data = [
    {'name': 'John Doe', 'age': 28, 'risk_level': 'Low', 'last_session': '2024-01-08', 'status': 'Active'},
    {'name': 'Jane Smith', 'age': 34, 'risk_level': 'Medium', 'last_session': '2024-01-07', 'status': 'Active'},
    {'name': 'Mike Johnson', 'age': 42, 'risk_level': 'High', 'last_session': '2024-01-06', 'status': 'Needs Attention'},
    {'name': 'Sarah Wilson', 'age': 29, 'risk_level': 'Low', 'last_session': '2024-01-05', 'status': 'Active'}
]

# BI mock data
bi_data = {
    'patient_engagement': 75,
    'avg_session_duration': 45,
    'completion_rate': 82,
    'satisfaction_score': 4.2
}

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_role' not in session or session['user_role'] != role:
                flash('Access denied. Insufficient permissions.', 'error')
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']
        
        if email in users and users[email]['password'] == password and users[email]['role'] == role:
            session['user_email'] = email
            session['user_role'] = role
            session['user_name'] = users[email]['name']
            
            if role == 'patient':
                return redirect(url_for('patient_dashboard'))
            elif role == 'provider':
                return redirect(url_for('provider_dashboard'))
        else:
            flash('Invalid credentials. Please try again.', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('index'))

@app.route('/patient-dashboard')
@login_required
@role_required('patient')
def patient_dashboard():
    user_email = session['user_email']
    data = patient_data.get(user_email, {})
    
    # Check for RPM alerts
    alerts = []
    rpm = data.get('rpm_data', {})
    if rpm.get('heart_rate', 0) > 100:
        alerts.append('High heart rate detected')
    if rpm.get('sleep_duration', 0) < 6:
        alerts.append('Insufficient sleep detected')
    
    return render_template('patient_dashboard.html', 
                         data=data, 
                         alerts=alerts,
                         user_name=session['user_name'])

@app.route('/provider-dashboard')
@login_required
@role_required('provider')
def provider_dashboard():
    return render_template('provider_dashboard.html', 
                         caseload=caseload_data,
                         bi_data=bi_data,
                         user_name=session['user_name'])

@app.route('/chat')
@login_required
def chat():
    return render_template('chat.html', user_name=session['user_name'])

@app.route('/schedule', methods=['GET', 'POST'])
@login_required
def schedule():
    if request.method == 'POST':
        date = request.form['date']
        time = request.form['time']
        flash(f'Appointment scheduled for {date} at {time}', 'success')
        return redirect(url_for('patient_dashboard'))
    
    return render_template('schedule.html', user_name=session['user_name'])

@app.route('/ai-documentation', methods=['GET', 'POST'])
@login_required
@role_required('provider')
def ai_documentation():
    if request.method == 'POST':
        transcript = request.form['transcript']
        
        # Simulate AI processing
        clinical_note = generate_clinical_note(transcript)
        
        return render_template('ai_documentation.html', 
                             clinical_note=clinical_note,
                             user_name=session['user_name'])
    
    return render_template('ai_documentation.html', user_name=session['user_name'])

def generate_clinical_note(transcript):
    """Simulate AI-powered clinical note generation"""
    return f"""
CLINICAL NOTE - Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}

PATIENT PRESENTATION:
Based on the session transcript, the patient presented with concerns related to their mental health status.

KEY OBSERVATIONS:
- Patient engagement level: High
- Emotional state: Stable with some areas of concern
- Treatment compliance: Good

ASSESSMENT:
The patient demonstrates good insight into their condition and shows willingness to engage in therapeutic interventions.

PLAN:
1. Continue current therapeutic approach
2. Monitor progress in next session
3. Consider additional resources if needed

SESSION SUMMARY:
{transcript[:200]}{'...' if len(transcript) > 200 else ''}

Next appointment recommended within 1-2 weeks.

Dr. {session.get('user_name', 'Provider')}
Licensed Mental Health Professional
"""

@app.route('/telehealth')
@login_required
def telehealth():
    return render_template('telehealth.html', user_name=session['user_name'])

if __name__ == '__main__':
    app.run(debug=True, port=5000)
