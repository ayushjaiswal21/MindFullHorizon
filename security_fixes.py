# Security Fixes for MindfulHorizon
# Critical vulnerability patches and security enhancements

from functools import wraps
from flask import session, request, jsonify, abort
import re
import bleach
from werkzeug.security import check_password_hash
import secrets
import hashlib

# ===== AUTHORIZATION FIXES =====

def verify_user_ownership(user_id, resource_id=None, resource_type='assessment'):
    """
    CRITICAL FIX: Prevent Insecure Direct Object Reference (IDOR) attacks
    Ensures users can only access their own resources
    """
    if not user_id or user_id != session.get('user_id'):
        return False
    
    if resource_id and resource_type == 'assessment':
        from models import Assessment
        assessment = Assessment.query.filter_by(id=resource_id, user_id=user_id).first()
        return assessment is not None
    
    return True

def enhanced_auth_required(resource_type=None):
    """Enhanced authentication decorator with IDOR protection"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Standard login check
            if 'user_email' not in session:
                return jsonify({'error': 'Authentication required'}), 401
            
            # IDOR protection for resource access
            if resource_type and request.method in ['POST', 'PUT', 'DELETE']:
                data = request.get_json() or {}
                resource_id = data.get(f'{resource_type}_id')
                
                if resource_id and not verify_user_ownership(session['user_id'], resource_id, resource_type):
                    return jsonify({'error': 'Unauthorized access to resource'}), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ===== INPUT VALIDATION FIXES =====

def validate_assessment_data(data):
    """
    CRITICAL FIX: Comprehensive input validation for assessment data
    Prevents injection attacks and data corruption
    """
    if not isinstance(data, dict):
        return False, "Invalid data format"
    
    # Required fields validation
    required_fields = ['assessment_type', 'score']
    for field in required_fields:
        if field not in data or data[field] is None:
            return False, f"Missing required field: {field}"
    
    # Assessment type validation
    valid_types = ['GAD-7', 'PHQ-9', 'Daily Mood']
    if data['assessment_type'] not in valid_types:
        return False, "Invalid assessment type"
    
    # Score validation
    score_ranges = {
        'GAD-7': (0, 21),
        'PHQ-9': (0, 27),
        'Daily Mood': (1, 5)
    }
    
    score = data['score']
    if not isinstance(score, int):
        return False, "Score must be an integer"
    
    min_score, max_score = score_ranges[data['assessment_type']]
    if not (min_score <= score <= max_score):
        return False, f"Score must be between {min_score} and {max_score}"
    
    # Responses validation
    if 'responses' in data:
        responses = data['responses']
        if not isinstance(responses, (dict, list)):
            return False, "Responses must be a dictionary or list"
    
    return True, "Valid"

def sanitize_user_input(text, allow_basic_html=False):
    """
    CRITICAL FIX: Sanitize user input to prevent XSS attacks
    """
    if not text:
        return ""
    
    if allow_basic_html:
        # Allow only safe HTML tags for journal entries
        allowed_tags = ['p', 'br', 'strong', 'em', 'ul', 'ol', 'li']
        allowed_attributes = {}
        return bleach.clean(text, tags=allowed_tags, attributes=allowed_attributes)
    else:
        # Strip all HTML for other inputs
        return bleach.clean(text, tags=[], strip=True)

# ===== PASSWORD SECURITY FIXES =====

def is_strong_password_enhanced(password):
    """
    CRITICAL FIX: Enhanced password validation with entropy checking
    """
    if len(password) < 12:  # Increased from 8
        return False, "Password must be at least 12 characters long"
    
    # Character variety checks
    checks = [
        (r"[a-z]", "Password must contain at least one lowercase letter"),
        (r"[A-Z]", "Password must contain at least one uppercase letter"),
        (r"[0-9]", "Password must contain at least one number"),
        (r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?]", "Password must contain at least one special character")
    ]
    
    for pattern, message in checks:
        if not re.search(pattern, password):
            return False, message
    
    # Common password check
    common_passwords = [
        'password123', '123456789', 'qwerty123', 'admin123',
        'password!', 'Password1', 'welcome123', 'letmein123'
    ]
    
    if password.lower() in [p.lower() for p in common_passwords]:
        return False, "Password is too common. Please choose a more unique password"
    
    # Entropy check (basic)
    unique_chars = len(set(password))
    if unique_chars < 8:
        return False, "Password must contain at least 8 different characters"
    
    return True, "Password is strong"

# ===== SESSION SECURITY FIXES =====

def secure_session_management():
    """
    CRITICAL FIX: Enhanced session security
    """
    # Generate secure session token
    session_token = secrets.token_urlsafe(32)
    
    # Store session metadata for security tracking
    session_metadata = {
        'token': session_token,
        'created_at': datetime.utcnow(),
        'last_activity': datetime.utcnow(),
        'ip_address': request.remote_addr,
        'user_agent': request.headers.get('User-Agent', '')
    }
    
    return session_metadata

def validate_session_security():
    """
    CRITICAL FIX: Validate session integrity and detect hijacking
    """
    if 'session_token' not in session:
        return False, "Invalid session"
    
    # Check session age (max 24 hours)
    if 'session_created' in session:
        session_age = datetime.utcnow() - session['session_created']
        if session_age.total_seconds() > 86400:  # 24 hours
            return False, "Session expired"
    
    # Check for session hijacking indicators
    current_ip = request.remote_addr
    current_ua = request.headers.get('User-Agent', '')
    
    if 'session_ip' in session and session['session_ip'] != current_ip:
        # Log potential hijacking attempt
        logger.warning(f"Session IP mismatch for user {session.get('user_email')}: {session['session_ip']} vs {current_ip}")
        return False, "Session security violation"
    
    return True, "Session valid"

# ===== RACE CONDITION FIXES =====

def atomic_appointment_booking(user_id, provider_id, date, time, appointment_type, notes):
    """
    CRITICAL FIX: Prevent race conditions in appointment scheduling
    Uses database-level locking to ensure atomicity
    """
    from models import Appointment, User, db
    from sqlalchemy import and_
    
    try:
        with db.session.begin():
            # Check for conflicting appointments with row-level locking
            existing_appointment = Appointment.query.filter(
                and_(
                    Appointment.provider_id == provider_id,
                    Appointment.date == date,
                    Appointment.time == time,
                    Appointment.status.in_(['pending', 'accepted', 'booked'])
                )
            ).with_for_update().first()
            
            if existing_appointment:
                return False, "Time slot already booked"
            
            # Create new appointment
            new_appointment = Appointment(
                user_id=user_id,
                provider_id=provider_id,
                date=date,
                time=time,
                appointment_type=appointment_type,
                notes=sanitize_user_input(notes),
                status='pending'
            )
            
            db.session.add(new_appointment)
            db.session.commit()
            
            return True, new_appointment
            
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in atomic appointment booking: {e}")
        return False, str(e)

# ===== WELLNESS SCORE UPDATE FIX =====

def atomic_wellness_score_update(user_id, module_id):
    """
    CRITICAL FIX: Atomic wellness score update with module completion
    Prevents race conditions and ensures data consistency
    """
    from models import User, ModuleCompletion, Assessment, db
    from sqlalchemy import func
    
    try:
        with db.session.begin():
            # Lock user record for update
            user = User.query.filter_by(id=user_id).with_for_update().first()
            if not user:
                return False, "User not found"
            
            # Record module completion
            module_completion = ModuleCompletion(
                user_id=user_id,
                module_id=module_id,
                completed_at=datetime.utcnow()
            )
            db.session.add(module_completion)
            
            # Recalculate wellness score based on recent assessments
            recent_assessments = Assessment.query.filter(
                Assessment.user_id == user_id,
                Assessment.created_at >= datetime.utcnow() - timedelta(days=30)
            ).all()
            
            if recent_assessments:
                # Calculate weighted average wellness score
                total_score = 0
                total_weight = 0
                
                for assessment in recent_assessments:
                    # Weight recent assessments more heavily
                    days_old = (datetime.utcnow() - assessment.created_at).days
                    weight = max(1, 30 - days_old)  # More recent = higher weight
                    
                    # Convert assessment score to wellness scale (0-10)
                    if assessment.assessment_type == 'GAD-7':
                        wellness_contribution = (1 - (assessment.score / 21)) * 10
                    elif assessment.assessment_type == 'PHQ-9':
                        wellness_contribution = (1 - (assessment.score / 27)) * 10
                    elif assessment.assessment_type == 'Daily Mood':
                        wellness_contribution = assessment.score * 2  # Scale 1-5 to 2-10
                    else:
                        continue
                    
                    total_score += wellness_contribution * weight
                    total_weight += weight
                
                if total_weight > 0:
                    user.wellness_score = round(total_score / total_weight, 1)
            
            # Determine next recommended module
            next_module = determine_next_module(user_id, user.wellness_score)
            
            db.session.commit()
            
            return True, {
                'new_wellness_score': user.wellness_score,
                'next_module': next_module,
                'completion_id': module_completion.id
            }
            
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in atomic wellness score update: {e}")
        return False, str(e)

def determine_next_module(user_id, current_wellness_score):
    """
    CRITICAL FIX: Psychologically sound module recommendation logic
    """
    from models import Assessment, ModuleCompletion
    
    # Get user's latest assessment scores
    latest_gad7 = Assessment.query.filter_by(
        user_id=user_id, 
        assessment_type='GAD-7'
    ).order_by(Assessment.created_at.desc()).first()
    
    latest_phq9 = Assessment.query.filter_by(
        user_id=user_id, 
        assessment_type='PHQ-9'
    ).order_by(Assessment.created_at.desc()).first()
    
    # Get completed modules
    completed_modules = ModuleCompletion.query.filter_by(user_id=user_id).all()
    completed_module_ids = [cm.module_id for cm in completed_modules]
    
    # Psychological intervention logic
    if latest_gad7 and latest_gad7.score >= 15:  # Severe anxiety
        if 3 not in completed_module_ids:  # Cognitive Restructuring
            return {
                'module_id': 3,
                'module_name': 'Cognitive Restructuring',
                'reason': 'High anxiety levels detected',
                'priority': 'high'
            }
        elif 4 not in completed_module_ids:  # Mindfulness Practice
            return {
                'module_id': 4,
                'module_name': 'Mindfulness Practice',
                'reason': 'Anxiety management progression',
                'priority': 'high'
            }
    
    elif latest_phq9 and latest_phq9.score >= 15:  # Moderate-severe depression
        if 5 not in completed_module_ids:  # Behavioral Activation
            return {
                'module_id': 5,
                'module_name': 'Behavioral Activation',
                'reason': 'Depression symptoms detected',
                'priority': 'high'
            }
    
    elif current_wellness_score < 6:  # General low wellness
        if 1 not in completed_module_ids:  # Sleep Hygiene
            return {
                'module_id': 1,
                'module_name': 'Sleep Hygiene',
                'reason': 'Foundation wellness improvement',
                'priority': 'medium'
            }
    
    # Default maintenance module
    return {
        'module_id': 6,
        'module_name': 'Relapse Prevention',
        'reason': 'Maintenance and progress consolidation',
        'priority': 'low'
    }

# ===== LOGGING AND MONITORING =====

def log_security_event(event_type, user_id=None, details=None):
    """
    CRITICAL FIX: Comprehensive security event logging
    """
    import logging
    
    security_logger = logging.getLogger('security')
    
    log_entry = {
        'timestamp': datetime.utcnow().isoformat(),
        'event_type': event_type,
        'user_id': user_id,
        'ip_address': request.remote_addr if request else None,
        'user_agent': request.headers.get('User-Agent') if request else None,
        'details': details
    }
    
    security_logger.warning(f"SECURITY_EVENT: {json.dumps(log_entry)}")
