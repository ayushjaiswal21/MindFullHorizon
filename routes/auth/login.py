"""Login, signup and logout routes."""
import hmac
import os
import re
from datetime import datetime

from flask import render_template, request, redirect, url_for, flash, session, current_app

from models import User, Gamification, db
from core.extensions import limiter
from utils.session_stamp import stamp_session
from services.errors import ServiceError
from services.prescriber import submit_profile

from . import auth_bp
from .consent import _checked, _home, add_consent_records, needs_reconsent

LOGIN_ERROR = 'Invalid email, password or role. Please check them and try again.'


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
@limiter.limit('10 per minute', methods=['POST'])
def login():
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        role = (request.form.get('role') or '').strip().lower()

        if not all([email, password, role]):
            flash('Please provide email, password, and select a role.', 'error')
            return render_template('login.html')

        try:
            user = User.query.filter_by(email=email).first()

            # One message for unknown email, wrong role, wrong password: the response never says which one failed.
            # admins sign in at /admin/login only; deactivated accounts get the same generic error
            if (not user or role not in ('patient', 'provider') or user.role.lower() != role or user.deactivated_at
                    or not user.password_hash or not user.check_password(password)):
                current_app.logger.warning("Login failed")
                flash(LOGIN_ERROR, 'error')
                return render_template('login.html')

            session.clear()  # fresh session: nothing from before the login survives
            session.permanent = True
            session['user_email'] = email
            session['user_role'] = role
            session['user_name'] = user.name
            session['user_id'] = user.id
            session['user_institution'] = user.institution
            stamp_session(user)  # lets a password or role change revoke this cookie (utils/session_stamp.py)
            if needs_reconsent(user):
                session['consent_pending'] = True
            session.modified = True

            current_app.logger.info("Login successful - user id %s, role %s", user.id, role)
            if session.get('consent_pending'):
                return redirect(url_for('auth.consent'))
            return redirect(_home(role))

        except Exception:
            current_app.logger.error("Login error", exc_info=True)
            flash('An error occurred during login. Please try again.', 'error')
            return render_template('login.html')

    return render_template('login.html')


def _invite_ok(ptype, code):
    """The code must belong to the CHOSEN provider type. Equal codes disable doctor signup (a code must pick one role)."""
    counsellor, doctor = os.getenv('PROVIDER_INVITE_CODE', ''), os.getenv('DOCTOR_INVITE_CODE', '')
    if ptype == 'doctor' and counsellor and counsellor == doctor:
        current_app.logger.warning('DOCTOR_INVITE_CODE equals PROVIDER_INVITE_CODE: doctor signup is disabled')
        return False
    expected = doctor if ptype == 'doctor' else counsellor
    return bool(expected) and hmac.compare_digest(code.encode(), expected.encode())


@auth_bp.route('/signup', methods=['GET', 'POST'])
@limiter.limit('10 per minute', methods=['POST'])
def signup():
    if request.method == 'POST':
        # Values to re-fill the form on an error. Passwords and the invite code are never echoed back.
        form = {k: v for k, v in request.form.items() if k in ('name', 'email', 'role', 'institution', 'consent', 'age_confirm',
                                                           'provider_type', 'registration_number', 'council',
                                                           'registered_since', 'specialisation')}

        def again(message):
            flash(message, 'error')
            return render_template('signup.html', form=form)

        try:
            name = request.form.get('name', '').strip()
            email = (request.form.get('email', '').strip()).lower()
            password = request.form.get('password', '')
            confirm_password = request.form.get('confirm_password', '')
            role = request.form.get('role', '').strip().lower()
            institution = ' '.join(request.form.get('institution', 'Default University').split())
            invite_code = request.form.get('invite_code', '')
            ptype = (request.form.get('provider_type') or 'counsellor').strip().lower() if role == 'provider' else None

            if not all([name, email, password, confirm_password, role]):
                return again('All fields are required.')
            if not _checked('consent'):
                return again('Please accept the privacy and consent notice to create an account.')
            if not _checked('age_confirm'):
                return again('Please confirm that you are 18 or older. Mind Full Horizon is for adults only.')

            # Only patients can self-register; counsellors and doctors need their own invite code (unset = closed).
            if role not in ('patient', 'provider') or ptype not in (None, 'counsellor', 'doctor'):
                return again('Invalid role.')
            if role == 'provider' and not _invite_ok(ptype, invite_code):
                return again('Doctor accounts need a valid invite code.' if ptype == 'doctor'
                             else 'Provider accounts need a valid invite code.')
            if ptype == 'doctor' and not institution:
                return again('Doctors must enter their institution.')
            if password != confirm_password:
                return again('Passwords do not match.')
            is_strong, message = is_strong_password(password)
            if not is_strong:
                return again(message)

            if User.query.filter_by(email=email).first():
                # Generic wording: it does not confirm that the address has an account.
                return again('We could not create an account with those details. If you already have an account, please log in.')

            new_user = User(name=name, email=email, role=role, institution=institution, provider_type=ptype)
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.flush()  # Get the new user ID

            if role == 'patient':
                db.session.add(Gamification(user_id=new_user.id, points=0, streak=0, badges=[],
                                            last_activity=datetime.utcnow()))
            add_consent_records(new_user.id)  # same transaction as the account: no account without proof of consent
            if ptype == 'doctor':  # pending until an administrator of the institution checks the registration
                submit_profile(new_user.id, request.form.get('registration_number'), request.form.get('council'),
                               request.form.get('registered_since'), request.form.get('specialisation'))

            db.session.commit()
            current_app.logger.info("Registration successful - User ID: %s", new_user.id)

            flash('Registration successful! Please login with your credentials.', 'success')
            return redirect(url_for('auth.login'))

        except ServiceError as err:  # doctor registration details failed validation: nothing was created
            db.session.rollback()
            return again(' '.join((err.fields or {}).values()) or err.message)
        except Exception:
            db.session.rollback()
            current_app.logger.error("Signup error", exc_info=True)
            return again('Registration failed due to a system error. Please try again.')

    return render_template('signup.html', form={})


@auth_bp.route('/logout')
def logout():
    # shortcut: still GET (templates link to it); make it POST-only once the shell sends a CSRF-protected form.
    session.clear()
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('core.index'))
