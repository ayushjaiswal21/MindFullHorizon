from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
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

        # Debug logging
        current_app.logger.info(f"Login attempt - Email: {email}, Role: {role}")

        if not all([email, password, role]):
            flash('Please provide email, password, and select a role.', 'error')
            current_app.logger.warning("Login failed - Missing required fields")
            return render_template('login.html')

        try:
            user = User.query.filter_by(email=email).first()

            if not user:
                current_app.logger.warning(f"Login failed - No user found with email: {email}")
                flash('No account found with that email. Please sign up first.', 'error')
                return render_template('login.html')

            if user.role.lower() != role:
                current_app.logger.warning(
                    f"Role mismatch for user {email}. Expected: {role}, Found: {user.role}"
                )
                flash('Selected role does not match account role. Please choose the correct role.', 'error')
                return render_template('login.html')

            if not user.password_hash:
                current_app.logger.warning(f"Login failed - No password set for user: {email}")
                flash('Your account was created without a password. Please use a different sign-in method or reset your password.', 'error')
                return render_template('login.html')

            if not user.check_password(password):
                current_app.logger.warning(f"Login failed - Invalid password for user: {email}")
                flash('Invalid credentials. Please check your email and password.', 'error')
                return render_template('login.html')

            # Login successful
            session.clear()
            session.permanent = True
            session['user_email'] = email
            session['user_role'] = role
            session['user_name'] = user.name
            session['user_id'] = user.id
            session['user_institution'] = user.institution
            session.modified = True

            current_app.logger.info(f"Login successful - User: {email}, Role: {role}")
            
            if role == 'patient':
                return redirect(url_for('patient.patient_dashboard'))
            else:
                return redirect(url_for('provider.provider_dashboard'))

        except Exception as e:
            current_app.logger.error(f"Login error: {str(e)}", exc_info=True)
            flash('An error occurred during login. Please try again.', 'error')
            return render_template('login.html')

    return render_template('login.html')

@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        try:
            # Get form data with safe defaults
            name = request.form.get('name', '').strip()
            email = (request.form.get('email', '').strip()).lower()
            password = request.form.get('password', '')
            confirm_password = request.form.get('confirm_password', '')
            role = request.form.get('role', '').strip().lower()
            institution = request.form.get('institution', 'Default University').strip()

            # Log registration attempt
            current_app.logger.info(
                f"Registration attempt - Name: {name}, Email: {email}, "
                f"Role: {role}, Institution: {institution}"
            )

            # Validate required fields
            if not all([name, email, password, confirm_password, role]):
                flash('All fields are required.', 'error')
                current_app.logger.warning("Signup failed - Missing required fields")
                return render_template('signup.html')

            # Validate password match
            if password != confirm_password:
                flash('Passwords do not match.', 'error')
                current_app.logger.warning("Signup failed - Password mismatch")
                return render_template('signup.html')

            # Validate password strength
            is_strong, message = is_strong_password(password)
            if not is_strong:
                flash(message, 'error')
                current_app.logger.warning(f"Signup failed - Weak password: {message}")
                return render_template('signup.html')

            # Check for existing user
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                flash('Email already registered. Please use a different email or login.', 'error')
                current_app.logger.warning(f"Signup failed - Email already registered: {email}")
                return render_template('signup.html')

            # Create new user
            new_user = User(
                name=name,
                email=email,
                role=role,
                institution=institution
            )
            new_user.set_password(password)

            db.session.add(new_user)
            db.session.flush()  # Get the new user ID

            # Create gamification profile for patients
            if role == 'patient':
                gamification = Gamification(
                    user_id=new_user.id,
                    points=0,
                    streak=0,
                    badges=[],
                    last_activity=datetime.utcnow()
                )
                db.session.add(gamification)

            db.session.commit()
            current_app.logger.info(f"Registration successful - User ID: {new_user.id}, Email: {email}")

            flash('Registration successful! Please login with your credentials.', 'success')
            return redirect(url_for('auth.login'))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Signup error: {str(e)}", exc_info=True)
            flash('Registration failed due to a system error. Please try again.', 'error')
            return render_template('signup.html')

    return render_template('signup.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('core.index'))
