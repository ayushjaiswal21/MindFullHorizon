"""Profile and role-selection routes moved out of app.py (continuing the O-15 cleanup).

Endpoint names and URLs are unchanged (`url_for('profile')`, `url_for('role_selection')`, ...): they
are registered on the app with `add_url_rule`, not on a blueprint, because a blueprint would prefix
every endpoint name.
"""
import logging
import os

from flask import flash, redirect, render_template, request, send_from_directory, session, url_for

logger = logging.getLogger('app')  # same logger (and file handler) the routes used inside app.py


def favicon():
    from flask import current_app
    try:
        return send_from_directory(os.path.join(current_app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')
    except FileNotFoundError:
        # Return empty response for missing favicon to avoid 404
        return '', 204


def profile():
    from extensions import db
    from models import DigitalDetoxLog, Gamification, User
    from routes.auth import is_strong_password
    from utils.session_stamp import stamp_session

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
                return redirect(url_for('profile'))
            user.set_password(password)

        try:
            db.session.commit()
            session['user_name'] = user.name  # Update session name if changed
            stamp_session(user)  # a new password changes the stamp: keep THIS session valid
            flash('Profile updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating profile for user {user_id}: {e}")
            flash('Failed to update profile.', 'error')
        return redirect(url_for('profile'))

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


def role_selection():
    """Renders the role selection page for new users."""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    return render_template('role_selection.html')


def save_role():
    """Lets a role-less/patient account confirm 'patient'. Provider accounts are only created via the signup invite code."""
    from extensions import db
    from models import User
    from utils.session_stamp import stamp_session

    user = db.session.get(User, session['user_id'])
    if request.form.get('role') != 'patient' or not user or user.role not in (None, '', 'patient'):
        flash("That role cannot be selected here.", "warning")
        return redirect(url_for('role_selection'))
    try:
        user.role = 'patient'
        db.session.commit()
        session['user_role'] = 'patient'
        stamp_session(user)  # the role is part of the stamp
        return redirect(url_for('patient.patient_dashboard'))
    except Exception as e:
        db.session.rollback()
        logger.error(f"Could not save user role: {e}")
        flash("Could not save your role. Please try again.", "danger")
        return redirect(url_for('role_selection'))


def register_profile_onboarding_routes(app):
    from decorators import login_required

    app.add_url_rule('/favicon.ico', 'favicon', favicon)
    app.add_url_rule('/profile', 'profile', login_required(profile), methods=['GET', 'POST'])
    app.add_url_rule('/role_selection', 'role_selection', role_selection)
    app.add_url_rule('/save_role', 'save_role', login_required(save_role), methods=['POST'])
