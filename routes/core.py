from flask import Blueprint, render_template, session, redirect, url_for, flash, request, send_from_directory
from models import User, Gamification, DigitalDetoxLog, BlogPost, db
from decorators import login_required
import uuid
import os
from werkzeug.utils import secure_filename
from routes.auth import is_strong_password
from datetime import datetime

core_bp = Blueprint('core', __name__)


def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_file_security(file):
    """Comprehensive file validation for security"""
    ALLOWED_MIME_TYPES = {'image/png', 'image/jpeg', 'image/jpg', 'image/gif'}
    if not file or not file.filename:
        return False, "No file provided"
    
    # Check file extension
    if not allowed_file(file.filename):
        return False, "Invalid file type. Only PNG, JPG, JPEG, and GIF files are allowed."
    
    # Check file size (additional check beyond Flask's MAX_CONTENT_LENGTH)
    file.seek(0, 2)  # Seek to end
    file_size = file.tell()
    file.seek(0)  # Reset to beginning
    
    if file_size > 5 * 1024 * 1024:  # 5MB
        return False, "File too large. Maximum size is 5MB."
    
    # Check MIME type
    file_mime = file.content_type
    if file_mime not in ALLOWED_MIME_TYPES:
        return False, "Invalid file type detected."
    
    # Check for path traversal attempts
    if '..' in file.filename or '/' in file.filename or '\\' in file.filename:
        return False, "Invalid filename detected."
    
    return True, "File is valid"

@core_bp.route('/')
def index():
    # Get blog insights for the landing page
    try:
        # Get featured/recent blog posts for display
        featured_posts = BlogPost.query.filter_by(
            is_published=True,
            is_featured=True
        ).order_by(BlogPost.created_at.desc()).limit(3).all()

        # If no featured posts, get recent ones
        if not featured_posts:
            featured_posts = BlogPost.query.filter_by(
                is_published=True
            ).order_by(BlogPost.created_at.desc()).limit(3).all()

        # Student-focused homepage theme data
        landing_theme = {
            "hero_title": "Welcome to MindFull Horizon",
            "hero_subtitle": "Empowering Students for Better Mental Wellness",
            "hero_message": "Track your mood, set goals, join wellness challenges, and connect with campus providers. Your journey to a healthier mind starts here!",
            "features": [
                {
                    "title": "Daily Mood Tracker",
                    "desc": "Check in with your feelings and see your progress over time."
                },
                {
                    "title": "Digital Detox",
                    "desc": "Reduce screen time and boost your academic and social life."
                },
                {
                    "title": "Gamified Wellness",
                    "desc": "Earn points, badges, and rewards for healthy habits and activities."
                }
            ]
        }

        # FAQ section data
        faqs = [
            {
                "question": "What is MindFull Horizon?",
                "answer": "MindFull Horizon is a student wellness platform designed to help you track your mood, set goals, and improve your mental health."
            },
            {
                "question": "How do I join wellness challenges?",
                "answer": "Sign up and visit your dashboard to participate in ongoing wellness challenges and earn rewards."
            },
            {
                "question": "Is my data private?",
                "answer": "Yes, your data is securely stored and only accessible to you and authorized campus providers."
            },
            {
                "question": "Can I connect with campus counselors?",
                "answer": "Absolutely! Use the telehealth feature to book appointments and chat with campus counselors."
            }
        ]

    except Exception as e:
        featured_posts = []
        landing_theme = {
            "hero_title": "Welcome to MindFull Horizon",
            "hero_subtitle": "Empowering Students for Better Mental Wellness",
            "hero_message": "Track your mood, set goals, join wellness challenges, and connect with campus providers. Your journey to a healthier mind starts here!",
            "features": []
        }
        faqs = []

    return render_template(
        'index.html',
        featured_posts=featured_posts,
        landing_theme=landing_theme,
        faqs=faqs,
        datetime=datetime
    )

@core_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user_id = session['user_id']
    user = User.query.get(user_id)
    if not user:
        flash('User not found. Please log in again.', 'error')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        user.name = request.form.get('name', user.name)
        user.email = request.form.get('email', user.email)
        user.institution = request.form.get('institution', user.institution)

        # Handle password change
        password = request.form.get('password')
        if password:
            is_strong, message = is_strong_password(password)
            if not is_strong:
                flash(message, 'error')
                return redirect(url_for('core.profile'))
            user.set_password(password)

        # Handle profile picture upload with enhanced security
        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file and file.filename:
                is_valid, error_message = validate_file_security(file)
                if is_valid:
                    try:
                        filename = secure_filename(file.filename)
                        # Ensure unique filename to prevent overwrites and path traversal
                        unique_filename = str(uuid.uuid4()) + '_' + filename
                        # This is not ideal, as the blueprint shouldn't know about the app config.
                        # A better approach would be to use a service to handle file uploads.
                        file_path = os.path.join('static', 'uploads', unique_filename)

                        with open(file_path, 'wb') as f:
                            file.seek(0)  # Reset file pointer
                            f.write(file.read())
                        user.profile_pic = unique_filename
                        flash('Profile picture updated successfully!', 'success')
                    except Exception as e:
                        flash('Error saving profile picture.', 'error')
                else:
                    flash(error_message, 'error')

        try:
            db.session.commit()
            session['user_name'] = user.name  # Update session name if changed
            flash('Profile updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash('Failed to update profile.', 'error')
        return redirect(url_for('core.profile'))

    gamification = Gamification.query.filter_by(user_id=user_id).first()
    digital_detox_logs = DigitalDetoxLog.query.filter_by(user_id=user_id).order_by(DigitalDetoxLog.date.desc()).all()

    avg_screen_time_7_days = None
    avg_screen_time_30_days = None

    if digital_detox_logs:
        recent_7_days = digital_detox_logs[:7]
        if recent_7_days:
            avg_screen_time_7_days = sum(log.screen_time_hours for log in recent_7_days) / len(recent_7_days)

        recent_30_days = digital_detox_logs[:30]
        if recent_30_days:
            avg_screen_time_30_days = sum(log.screen_time_hours for log in recent_30_days) / len(recent_30_days)

    return render_template('profile.html',
                         user_name=session['user_name'],
                         user=user,
                         gamification=gamification,
                         digital_detox_logs=digital_detox_logs,
                         avg_screen_time_7_days=avg_screen_time_7_days,
                         avg_screen_time_30_days=avg_screen_time_30_days)

@core_bp.route('/chat')
@login_required
def chat():
    return render_template('chat.html', user_name=session['user_name'])

@core_bp.route('/telehealth_session/<int:user_id>')
@login_required
def telehealth_session(user_id):
    patient = User.query.get_or_404(user_id)
    return render_template('telehealth.html', 
                           user_name=session['user_name'],
                           patient_id=patient.id,
                           patient_name=patient.name)

@core_bp.route('/telehealth')
@login_required
def telehealth():
    return render_template('telehealth.html', user_name=session['user_name'])

@core_bp.route('/yoga-videos')
def yoga_videos():
    return render_template('yoga_videos.html')

@core_bp.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(os.getcwd(), 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')
