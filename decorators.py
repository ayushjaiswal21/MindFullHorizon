from functools import wraps
from flask import session, flash, redirect, url_for, request, jsonify

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify(success=False, message='Authentication required'), 401
            return redirect(url_for('auth.login'))
        
        # Refresh session on activity to prevent unexpected timeouts
        session.permanent = True
        session.modified = True
        return f(*args, **kwargs)
    return decorated_function

def api_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            return jsonify(success=False, message='Authentication required'), 401
        
        # Refresh session on activity to prevent unexpected timeouts
        session.permanent = True
        session.modified = True
        return f(*args, **kwargs)
    return decorated_function

def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_role' not in session or session['user_role'] != role:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify(success=False, message='Insufficient permissions'), 403
                flash('Access denied. Insufficient permissions.', 'error')
                return redirect(url_for('auth.login'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Combined decorator for patient routes
def patient_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify(success=False, message='Authentication required'), 401
            return redirect(url_for('auth.login'))
        if session.get('user_role') != 'patient':
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify(success=False, message='Insufficient permissions'), 403
            flash('Access denied. Please log in as a patient.', 'error')
            return redirect(url_for('auth.login'))
        # Refresh session on activity
        session.permanent = True
        session.modified = True
        return f(*args, **kwargs)
    return decorated_function

# Combined decorator for provider routes
def provider_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify(success=False, message='Authentication required'), 401
            return redirect(url_for('auth.login'))
        if session.get('user_role') != 'provider':
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify(success=False, message='Insufficient permissions'), 403
            flash('Access denied. Please log in as a provider.', 'error')
            return redirect(url_for('auth.login'))
        # Refresh session on activity
        session.permanent = True
        session.modified = True
        return f(*args, **kwargs)
    return decorated_function


def can_join_telehealth(patient_id):
    """True for the patient themself, or a provider of the same institution who has an appointment with them."""
    from extensions import db
    from models import Appointment, User
    uid, role = session.get('user_id'), session.get('user_role')
    if not uid:
        return False
    if role == 'patient':
        return uid == patient_id
    if role != 'provider':
        return False
    patient = db.session.get(User, patient_id)
    if not patient or patient.role != 'patient' or patient.institution != session.get('user_institution'):
        return False
    return Appointment.query.filter(Appointment.user_id == patient_id, Appointment.provider_id == uid,
                                    Appointment.status != 'rejected').first() is not None
