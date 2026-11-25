from functools import wraps
from flask import session, flash, redirect, url_for, request, jsonify, abort, g

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


def prescriptions_required(f):
    """404 for every prescription route while ENABLE_PRESCRIPTIONS is off (decision P-01). Put it first, above login_required."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from utils.feature_flags import prescriptions_enabled
        if not prescriptions_enabled():
            if request.path.startswith('/api') or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify(error='not_found'), 404
            abort(404)
        return f(*args, **kwargs)
    return decorated_function


def can_join_telehealth(patient_id):
    """True for the patient themself, or a provider of the same institution (case-insensitive) linked to them by a
    ProviderPatient row or a non-rejected appointment. The single rule for the provider page and the socket join."""
    from extensions import db
    from models import Appointment, ProviderPatient, User
    from utils.assignments import same_institution
    uid, role = session.get('user_id'), session.get('user_role')
    if not uid:
        return False
    if role == 'patient':
        return uid == patient_id
    if role != 'provider':
        return False
    patient = db.session.get(User, patient_id)
    if not patient or patient.role != 'patient' or not same_institution(patient.institution, session.get('user_institution')):
        return False
    return (ProviderPatient.query.filter_by(provider_id=uid, patient_id=patient_id).first() is not None
            or Appointment.query.filter(Appointment.user_id == patient_id, Appointment.provider_id == uid,
                                        Appointment.status != 'rejected').first() is not None)


# ---------- clinical roles (docs/CLINICAL_DESIGN.md 1.5) ----------
# Every check re-reads the User row, so a suspension or deactivation takes effect on the next request.

def _wants_json():
    p = request.path
    return (p.startswith(('/provider/api/', '/admin/api/', '/patient/api/', '/api'))
            or request.headers.get('X-Requested-With') == 'XMLHttpRequest')


def _json_error(status, code):
    from services.errors import MESSAGES
    return jsonify(success=False, error=code, message=MESSAGES.get(code, 'Not allowed.')), status


def _audit_denied(code):
    """One AuditLog row in its own short transaction, so it survives the rollback of the denied request."""
    try:
        from extensions import db
        from models import AuditLog
        from utils.timeutil import utcnow
        with db.engine.begin() as conn:
            conn.execute(AuditLog.__table__.insert().values(
                actor_id=session.get('user_id'), action='denied', target_type='route', meta={'code': code},
                created_at=utcnow()))
    except Exception:  # an audit failure must not turn a denial into a 500
        pass


def _deny(status, json_code, html_endpoint, message, audit_code=None):
    if audit_code:
        _audit_denied(audit_code)
    if _wants_json():
        return _json_error(status, json_code)
    if status == 404:
        abort(404)
    flash(message, 'error')
    return redirect(url_for(html_endpoint))


def _fresh_user(role):
    """The logged-in User row if it still exists, has `role` and is not deactivated; else None."""
    from extensions import db
    from models import User
    user = db.session.get(User, session.get('user_id') or 0)
    if user is None or user.role != role or user.deactivated_at is not None:
        return None
    return user


def roles_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_email' not in session:
                if _wants_json():
                    return _json_error(401, 'forbidden')
                return redirect(url_for('auth.login'))
            if session.get('user_role') not in roles:
                return _deny(403, 'forbidden', 'auth.login', 'Access denied. Insufficient permissions.')
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def _admin_gate(desk):
    """None when the session is a live admin (and has the desk flag if `desk`); otherwise the response to return."""
    if 'user_email' not in session:
        if _wants_json():
            return _json_error(401, 'forbidden')
        nxt = request.full_path.rstrip('?') if request.method == 'GET' else None
        return redirect(url_for('admin.login', next=nxt) if nxt else url_for('admin.login'))
    if session.get('user_role') != 'admin':
        return _deny(403, 'forbidden', 'admin.login', 'Access denied. Please sign in as an administrator.', 'role')
    user = _fresh_user('admin')
    if user is None:
        session.clear()
        return _deny(401 if _wants_json() else 403, 'forbidden', 'admin.login', 'Your session has ended.', 'inactive')
    if desk and not user.is_pharmacy_desk:
        _audit_denied('not_desk')
        if _wants_json():
            return _json_error(403, 'forbidden')
        abort(403)
    g.actor = user
    session.permanent = True
    session.modified = True
    return None


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        return _admin_gate(False) or f(*args, **kwargs)
    return decorated_function


def pharmacy_desk_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        return _admin_gate(True) or f(*args, **kwargs)
    return decorated_function


def _doctor_gate(verified):
    if 'user_email' not in session:
        return _json_error(401, 'forbidden') if _wants_json() else redirect(url_for('auth.login'))
    if session.get('user_role') != 'provider':
        return _deny(403, 'forbidden', 'auth.login', 'Access denied. Please log in as a provider.', 'role')
    user = _fresh_user('provider')
    if user is None:
        session.clear()
        return _deny(401 if _wants_json() else 403, 'forbidden', 'auth.login', 'Your session has ended.', 'inactive')
    if user.provider_type != 'doctor':  # counsellors must not learn that prescribing exists
        _audit_denied('role')
        if _wants_json():
            return _json_error(404, 'not_found')
        abort(404)
    if verified:
        from services.errors import ServiceError
        from services.prescriber import require_verified
        try:
            require_verified(user.id)
        except ServiceError:
            return _deny(403, 'prescriber_not_verified', 'provider.rx_profile',
                         'Your registration has not been verified yet, so you cannot prescribe.', 'not_verified')
    g.actor = user
    session.permanent = True
    session.modified = True
    return None


def doctor_provider_required(f):
    """A live provider with provider_type 'doctor' (verified or not). Counsellors get 404."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        return _doctor_gate(False) or f(*args, **kwargs)
    return decorated_function


def verified_prescriber_required(f):
    """doctor_provider_required plus a verified, in-date PrescriberProfile, re-checked on every request."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        return _doctor_gate(True) or f(*args, **kwargs)
    return decorated_function
