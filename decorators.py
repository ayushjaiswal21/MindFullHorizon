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
