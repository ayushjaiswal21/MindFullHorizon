"""Google OAuth sign-in moved out of app.py (continuing the O-15 cleanup).

Registered with `register_google_oauth(app)` from app.py.
"""
import logging
import os
import secrets

from flask import flash, redirect, session, url_for

logger = logging.getLogger('app')  # same logger (and file handler) the handler used inside app.py


def register_google_oauth(app):
    from flask_dance.consumer import oauth_authorized
    from flask_dance.contrib.google import make_google_blueprint

    app.config["GOOGLE_OAUTH_CLIENT_ID"] = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
    app.config["GOOGLE_OAUTH_CLIENT_SECRET"] = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")

    google_bp = make_google_blueprint(
        scope=["openid", "https://www.googleapis.com/auth/userinfo.profile", "https://www.googleapis.com/auth/userinfo.email"]
    )
    app.register_blueprint(google_bp, url_prefix="/login")

    @oauth_authorized.connect_via(google_bp)
    def google_logged_in(blueprint, token):
        """Handles the logic after a user logs in with Google."""
        from core.extensions import db
        from models import Gamification, User
        from utils.session_stamp import stamp_session

        if not token:
            flash("Failed to log in with Google.", "danger")
            return redirect(url_for("auth.login"))

        try:
            logger.info("Google authorized, fetching user info.")
            resp = blueprint.session.get("/oauth2/v2/userinfo")
            assert resp.ok, resp.text
            user_info = resp.json()
            google_id = user_info['id']
            email = (user_info['email'] or '').strip().lower()
            name = user_info.get('name', 'User')

            logger.info(f"Looking for user with google_id={google_id}")
            user = User.query.filter_by(google_id=google_id).first()
            new_google_user = False

            if not user:
                logger.info(f"User not found with google_id, looking for user with email={email}")
                user = User.query.filter_by(email=email).first()
                if user and not (user_info.get('verified_email') or user_info.get('email_verified')):
                    # never attach a Google identity to an existing account unless Google vouches for the address
                    flash("Your Google email is not verified, so we cannot sign you in with it.", "danger")
                    return redirect(url_for("auth.login"))
                if user:
                    logger.info(f"User found with email, linking google_id")
                    user.google_id = google_id
                    db.session.commit()
                    logger.info("google_id linked to existing user.")
                else:
                    logger.info("No existing user found, creating a new user with default patient role.")
                    new_google_user = True
                    # Create new user with default patient role and institution
                    user = User(
                        email=email,
                        google_id=google_id,
                        name=name,
                        role='patient',  # Default role for Google OAuth users
                        institution='Default University'
                    )
                    user.set_password(secrets.token_urlsafe(32))  # random, never shown: password login stays unusable
                    db.session.add(user)
                    db.session.commit()
                    logger.info("New user created with patient role.")

                    # Create gamification profile for new patient
                    try:
                        gamification = Gamification(
                            user_id=user.id,
                            points=0,
                            streak=0,
                            badges=[],
                            last_activity=None
                        )
                        db.session.add(gamification)
                        db.session.commit()
                        logger.info(f'Gamification profile created for Google OAuth user: {email}')
                    except Exception as gam_error:
                        logger.error(f'Error creating gamification profile for Google user: {gam_error}')
                        db.session.rollback()

            if user.role == 'admin' or user.deactivated_at is not None:  # admins sign in with a password at /admin/login only
                flash("Please sign in with your email and password.", "danger")
                return redirect(url_for("auth.login"))

            logger.info(f"Logging in user: {user.email} (id={user.id})")

            # Ensure user has a role - assign default if missing
            if not user.role:
                logger.warning(f"User {user.email} has no role, assigning default 'patient' role.")
                user.role = 'patient'
                user.institution = user.institution or 'Default University'
                try:
                    db.session.commit()
                    logger.info("Default role assigned to user.")

                    # Create gamification profile if it doesn't exist
                    if not Gamification.query.filter_by(user_id=user.id).first():
                        gamification = Gamification(
                            user_id=user.id,
                            points=0,
                            streak=0,
                            badges=[],
                            last_activity=None
                        )
                        db.session.add(gamification)
                        db.session.commit()
                        logger.info(f'Gamification profile created for user: {user.email}')
                except Exception as role_error:
                    logger.error(f'Error assigning default role: {role_error}')
                    db.session.rollback()
                    # Continue with session creation even if role assignment fails

            session.clear()
            session.permanent = True
            session['user_id'] = user.id
            session['user_email'] = user.email
            session['user_name'] = user.name
            session['user_role'] = user.role
            session['user_institution'] = user.institution or 'Default University'
            stamp_session(user)
            session.modified = True
            logger.info("Session created for user.")

            from routes.auth import needs_reconsent
            if new_google_user or needs_reconsent(user):  # no consent was recorded for this sign-in yet (P-05)
                session['consent_pending'] = True
                return redirect(url_for('auth.consent'))

            if user.role == 'patient':
                logger.info("User is a patient, redirecting to patient_dashboard.")
                return redirect(url_for('patient.patient_dashboard'))
            else:
                logger.info("User is a provider, redirecting to provider_dashboard.")
                return redirect(url_for('provider.provider_dashboard'))

        except Exception as e:
            logger.error(f"An error occurred during Google login: {e}", exc_info=True)
            flash("Google sign-in failed. Please try again.", "danger")
            return redirect(url_for('auth.login'))

    return google_logged_in
