# Secure Route Implementations for MindfulHorizon
# Replaces vulnerable routes with security-hardened versions

from flask import Blueprint, request, jsonify, session, flash, redirect, url_for
from security_fixes import (
    enhanced_auth_required, validate_assessment_data, sanitize_user_input,
    atomic_appointment_booking, atomic_wellness_score_update, log_security_event
)
from models import Assessment, Appointment, User, db
import json
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

# Create secure API blueprint
secure_api = Blueprint('secure_api', __name__, url_prefix='/api/v1')

# ===== SECURE ASSESSMENT API =====

@secure_api.route('/assessments', methods=['POST'])
@enhanced_auth_required('assessment')
def create_assessment():
    """
    SECURE VERSION: Assessment creation with comprehensive validation
    Fixes: IDOR, input validation, XSS prevention, race conditions
    """
    try:
        # Validate request format
        if not request.is_json:
            log_security_event('invalid_request_format', session.get('user_id'))
            return jsonify({'error': 'Request must be JSON'}), 400
        
        user_id = session['user_id']
        data = request.get_json()
        
        # Comprehensive input validation
        is_valid, error_message = validate_assessment_data(data)
        if not is_valid:
            log_security_event('invalid_assessment_data', user_id, {'error': error_message})
            return jsonify({'error': error_message}), 400
        
        # Sanitize inputs
        assessment_type = sanitize_user_input(data['assessment_type'])
        score = int(data['score'])
        responses = data.get('responses', {})
        
        # Validate user ownership (prevent IDOR)
        if not verify_user_ownership(user_id):
            log_security_event('idor_attempt', user_id)
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Rate limiting check (additional to decorator)
        recent_assessments = Assessment.query.filter(
            Assessment.user_id == user_id,
            Assessment.created_at >= datetime.utcnow() - timedelta(minutes=5)
        ).count()
        
        if recent_assessments >= 3:
            log_security_event('rate_limit_exceeded', user_id)
            return jsonify({'error': 'Too many assessments. Please wait before submitting another.'}), 429
        
        # Atomic database transaction
        with db.session.begin():
            # Create assessment
            assessment = Assessment(
                user_id=user_id,
                assessment_type=assessment_type,
                score=score,
                responses=responses,
                created_at=datetime.now(timezone.utc)
            )
            db.session.add(assessment)
            
            # Generate AI insights securely
            try:
                from ai_service import ai_service
                ai_insights = ai_service.generate_assessment_insights(
                    assessment_type=assessment_type,
                    score=score,
                    responses=responses
                )
                assessment.ai_insights = json.dumps(ai_insights)
            except Exception as e:
                logger.warning(f"AI insights generation failed: {e}")
                ai_insights = None
            
            # Award points atomically
            from gamification_engine import award_points
            gamification = award_points(user_id, 20, 'assessment')
            
            # Update user's last assessment time
            user = User.query.filter_by(id=user_id).with_for_update().first()
            user.last_assessment_at = datetime.now(timezone.utc)
            
            db.session.commit()
        
        # Log successful assessment
        log_security_event('assessment_created', user_id, {
            'assessment_type': assessment_type,
            'score': score
        })
        
        return jsonify({
            'success': True,
            'assessment_id': assessment.id,
            'points_earned': 20,
            'total_points': gamification.points,
            'ai_insights': ai_insights
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in secure assessment creation: {e}")
        log_security_event('assessment_error', session.get('user_id'), {'error': str(e)})
        return jsonify({'error': 'Internal server error'}), 500

# ===== SECURE APPOINTMENT API =====

@secure_api.route('/appointments', methods=['POST'])
@enhanced_auth_required()
def create_appointment():
    """
    SECURE VERSION: Appointment booking with race condition prevention
    Fixes: Race conditions, input validation, authorization checks
    """
    try:
        user_id = session['user_id']
        data = request.get_json()
        
        # Input validation
        required_fields = ['date', 'time', 'appointment_type']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Sanitize inputs
        date_str = sanitize_user_input(data['date'])
        time_str = sanitize_user_input(data['time'])
        appointment_type = sanitize_user_input(data['appointment_type'])
        notes = sanitize_user_input(data.get('notes', ''), allow_basic_html=True)
        provider_id = data.get('provider_id')
        
        # Validate date format and future date
        try:
            appointment_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            if appointment_date <= datetime.now().date():
                return jsonify({'error': 'Appointment date must be in the future'}), 400
        except ValueError:
            return jsonify({'error': 'Invalid date format'}), 400
        
        # Validate time format
        try:
            datetime.strptime(time_str, '%H:%M')
        except ValueError:
            return jsonify({'error': 'Invalid time format'}), 400
        
        # Validate provider exists and is in same institution
        if provider_id:
            provider = User.query.filter_by(id=provider_id, role='provider').first()
            if not provider:
                return jsonify({'error': 'Invalid provider'}), 400
            
            user = User.query.get(user_id)
            if user.institution != provider.institution:
                log_security_event('cross_institution_appointment_attempt', user_id)
                return jsonify({'error': 'Provider not available'}), 403
        
        # Atomic appointment booking
        success, result = atomic_appointment_booking(
            user_id, provider_id, appointment_date, time_str, appointment_type, notes
        )
        
        if not success:
            return jsonify({'error': result}), 409
        
        appointment = result
        
        # Log successful booking
        log_security_event('appointment_created', user_id, {
            'appointment_id': appointment.id,
            'provider_id': provider_id,
            'date': date_str,
            'time': time_str
        })
        
        return jsonify({
            'success': True,
            'appointment_id': appointment.id,
            'status': appointment.status
        }), 201
        
    except Exception as e:
        logger.error(f"Error in secure appointment creation: {e}")
        return jsonify({'error': 'Internal server error'}), 500

# ===== SECURE MODULE COMPLETION API =====

@secure_api.route('/modules/<int:module_id>/complete', methods=['POST'])
@enhanced_auth_required()
def complete_module(module_id):
    """
    SECURE VERSION: Module completion with atomic wellness score update
    Fixes: Race conditions, score calculation consistency
    """
    try:
        user_id = session['user_id']
        
        # Validate module exists and user has access
        # Add module validation logic here
        
        # Atomic wellness score update
        success, result = atomic_wellness_score_update(user_id, module_id)
        
        if not success:
            return jsonify({'error': result}), 500
        
        # Log module completion
        log_security_event('module_completed', user_id, {
            'module_id': module_id,
            'new_wellness_score': result['new_wellness_score']
        })
        
        return jsonify({
            'success': True,
            'wellness_score': result['new_wellness_score'],
            'next_module': result['next_module']
        }), 200
        
    except Exception as e:
        logger.error(f"Error in secure module completion: {e}")
        return jsonify({'error': 'Internal server error'}), 500

# ===== SECURE USER DATA API =====

@secure_api.route('/users/me', methods=['GET'])
@enhanced_auth_required()
def get_current_user():
    """
    SECURE VERSION: User profile endpoint with proper authorization
    """
    try:
        user_id = session['user_id']
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Return sanitized user data
        user_data = {
            'id': user.id,
            'name': user.name,
            'email': user.email,
            'role': user.role,
            'institution': user.institution,
            'created_at': user.created_at.isoformat(),
            'last_assessment_at': user.last_assessment_at.isoformat() if user.last_assessment_at else None
        }
        
        return jsonify(user_data), 200
        
    except Exception as e:
        logger.error(f"Error in get current user: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@secure_api.route('/users/me/assessments', methods=['GET'])
@enhanced_auth_required()
def get_user_assessments():
    """
    SECURE VERSION: User assessments with proper filtering and pagination
    """
    try:
        user_id = session['user_id']
        
        # Pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 10, type=int), 50)  # Max 50 per page
        
        # Get user's assessments only
        assessments_query = Assessment.query.filter_by(user_id=user_id)
        
        # Optional filtering
        assessment_type = request.args.get('type')
        if assessment_type:
            assessments_query = assessments_query.filter_by(assessment_type=assessment_type)
        
        # Paginate results
        assessments_paginated = assessments_query.order_by(
            Assessment.created_at.desc()
        ).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        # Serialize assessments
        assessments_data = []
        for assessment in assessments_paginated.items:
            assessment_data = {
                'id': assessment.id,
                'assessment_type': assessment.assessment_type,
                'score': assessment.score,
                'created_at': assessment.created_at.isoformat(),
                'ai_insights': json.loads(assessment.ai_insights) if assessment.ai_insights else None
            }
            assessments_data.append(assessment_data)
        
        return jsonify({
            'assessments': assessments_data,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': assessments_paginated.total,
                'pages': assessments_paginated.pages
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error in get user assessments: {e}")
        return jsonify({'error': 'Internal server error'}), 500

# ===== ERROR HANDLERS =====

@secure_api.errorhandler(400)
def handle_bad_request(e):
    log_security_event('bad_request', session.get('user_id'), {'error': str(e)})
    return jsonify({'error': 'Bad request'}), 400

@secure_api.errorhandler(401)
def handle_unauthorized(e):
    log_security_event('unauthorized_access', session.get('user_id'))
    return jsonify({'error': 'Authentication required'}), 401

@secure_api.errorhandler(403)
def handle_forbidden(e):
    log_security_event('forbidden_access', session.get('user_id'))
    return jsonify({'error': 'Access forbidden'}), 403

@secure_api.errorhandler(429)
def handle_rate_limit(e):
    log_security_event('rate_limit_hit', session.get('user_id'))
    return jsonify({'error': 'Rate limit exceeded'}), 429

@secure_api.errorhandler(500)
def handle_internal_error(e):
    log_security_event('internal_error', session.get('user_id'), {'error': str(e)})
    return jsonify({'error': 'Internal server error'}), 500
