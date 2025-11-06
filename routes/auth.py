from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models import User, Gamification, db
import re

auth_bp = Blueprint('auth', __name__)

def is_strong_password(password):
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r"[0-9]", password):
        return False, "Password must contain at least one number."
    if not re.search(r"[\W_]", password):
        return False, "Password must contain at least one special character."
    return True, ""

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        role = (request.form.get('role') or '').strip().lower()

        if not email or not password or not role:
            flash('Please provide email, password, and select a role.', 'error')
            return render_template('login.html')

        user = User.query.filter_by(email=email).first()

        if not user:
            flash('No account found with that email. Please sign up first.', 'error')
            return render_template('login.html')

        if user.role.lower() != role:
            flash('Selected role does not match account role. Please choose the correct role.', 'error')
            return render_template('login.html')

        if not user.password_hash:
            flash('Your account was created without a password. Please use a different sign-in method or reset your password.', 'error')
            return render_template('login.html')

        if not user.check_password(password):
            flash('Invalid credentials. Please check your email and password.', 'error')
            return render_template('login.html')

        session.clear()
        session.permanent = True
        session['user_email'] = email
        session['user_role'] = role
        session['user_name'] = user.name
        session['user_id'] = user.id
        session['user_institution'] = user.institution
        session.modified = True

        if role == 'patient':
            return redirect(url_for('patient.patient_dashboard'))
        else:
            return redirect(url_for('provider.provider_dashboard'))

    return render_template('login.html')

@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        role = request.form['role']
        institution = request.form.get('institution', 'Default University')

        if not all([name, email, password, confirm_password, role]):
            flash('All fields are required.', 'error')
            return render_template('signup.html')

        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('signup.html')

        is_strong, message = is_strong_password(password)
        if not is_strong:
            flash(message, 'error')
            return render_template('signup.html')

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email already registered. Please use a different email or login.', 'error')
            return render_template('signup.html')

        new_user = User(
            name=name,
            email=email,
            role=role,
            institution=institution
        )
        new_user.set_password(password)

        try:
            db.session.add(new_user)
            db.session.commit()

            if role == 'patient':
                gamification = Gamification(
                    user_id=new_user.id,
                    points=0,
                    streak=0,
                    badges=[],
                    last_activity=None
                )
                db.session.add(gamification)
                db.session.commit()

            flash('Registration successful! Please login with your credentials.', 'success')
            return redirect(url_for('auth.login'))

        except Exception as e:
            db.session.rollback()
            flash('Registration failed. Please try again.', 'error')
            return render_template('signup.html')

    return render_template('signup.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('core.index'))
