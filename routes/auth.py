from flask import (Blueprint, render_template, request, redirect, url_for, flash, session, current_app,
                   jsonify, Response)
from models import (User, Gamification, ConsentRecord, db, Assessment, DigitalDetoxLog, RPMData, Medication,
                    MedicationLog, BreathingExerciseLog, YogaLog, MusicTherapyLog, ProgressRecommendation, Goal,
                    MoodLog, JournalEntry, VoiceLog, Appointment, Notification, CrisisEvent, Prescription,
                    PrescriptionItem, BlogPost, BlogComment, ContactMessage, ProviderPatient)
from datetime import datetime, date
import hmac
import json
import os
import re
from extensions import limiter
from decorators import login_required
from utils.audit import audit
from utils.session_stamp import stamp_session
from services.errors import ServiceError
from services.prescriber import submit_profile
from services.roles import home_endpoint
from services.wellbeing_export import WELLBEING_EXPORT

auth_bp = Blueprint('auth', __name__)
CONSENT_KINDS = ('privacy', 'age18')
DELETE_PHRASE = 'DELETE MY ACCOUNT'  # typed by Google-only users, who have no password to re-enter
LOGIN_ERROR = 'Invalid email, password or role. Please check them and try again.'
# Paths a user with a pending consent may still open (everything else is sent to /consent).
CONSENT_EXEMPT = ('/consent', '/logout', '/privacy', '/terms', '/health')


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


# ---------- consent helpers ----------

def consent_version():
    """Version of the privacy notice users accept now (env CONSENT_VERSION, default 2026-11). Read per call."""
    return os.getenv('CONSENT_VERSION', '2026-11')


def has_current_consent(user_id):
    """True when the user has accepted BOTH the privacy notice and the 18+ statement at the current version."""
    kinds = {k for (k,) in db.session.query(ConsentRecord.kind).filter_by(user_id=user_id, version=consent_version())}
    return set(CONSENT_KINDS) <= kinds


def needs_reconsent(user):
    """True when the user consented to an OLDER notice version and not yet to the current one.

    Bumping CONSENT_VERSION (for example after the privacy notice changes) makes every earlier ConsentRecord stale:
    the next login of each such user is routed to /consent, and accepting writes new rows, so the old rows stay as proof
    of what was accepted when. Accounts with no consent rows at all (created before consent was recorded) return False
    and are not interrupted; they are listed in docs/PRIVACY_AND_CONSENT.md as an operator decision.
    """
    if not ConsentRecord.query.filter_by(user_id=user.id).first():
        return False
    return not has_current_consent(user.id)


def add_consent_records(user_id):
    """Add the two ConsentRecord rows for the current version to the caller's transaction (skips ones that exist)."""
    version = consent_version()
    have = {k for (k,) in db.session.query(ConsentRecord.kind).filter_by(user_id=user_id, version=version)}
    for kind in CONSENT_KINDS:
        if kind not in have:
            db.session.add(ConsentRecord(user_id=user_id, kind=kind, version=version))


def _checked(name):
    return (request.form.get(name) or '').strip().lower() in ('yes', 'on', 'true', '1')


def _home(role):
    return url_for(home_endpoint(role))


@auth_bp.before_app_request
def consent_guard():
    """Send users whose consent is pending (new Google sign-ups, version bumps) to /consent first."""
    if not session.get('consent_pending'):
        return None
    path = request.path
    if path.startswith('/static/') or path in CONSENT_EXEMPT:
        return None
    if path.startswith('/api') or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify(success=False, error='consent_required', message='Please accept the privacy notice first.'), 403
    return redirect(url_for('auth.consent'))


@auth_bp.route('/consent', methods=['GET', 'POST'])
@login_required
def consent():
    """Privacy notice and 18+ confirmation for users who did not go through the signup form."""
    user_id = session['user_id']
    if request.method == 'POST':
        if not (_checked('consent') and _checked('age_confirm')):
            flash('Please tick both boxes to continue.', 'error')
            return render_template('consent.html', consent_version=consent_version()), 400
        add_consent_records(user_id)
        db.session.commit()
        session.pop('consent_pending', None)
        return redirect(_home(session.get('user_role')))
    if not session.get('consent_pending') and has_current_consent(user_id):
        return redirect(_home(session.get('user_role')))
    return render_template('consent.html', consent_version=consent_version())


# ---------- login / signup / logout ----------

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


# ---------- account data rights (export and delete) ----------

def _row(r, skip=()):
    out = {}
    for c in r.__table__.columns:
        if c.name not in skip:
            v = getattr(r, c.key)
            out[c.name] = v.isoformat() if isinstance(v, (datetime, date)) else v
    return out


# (key, model, owner column, columns left out). Clinical notes written by providers are NOT exported: the product
# does not show them to patients. Crisis events are exported as code and time only. Chat has no stored messages.
_EXPORT = [
    ('assessments', Assessment, 'user_id', ()), ('mood_logs', MoodLog, 'user_id', ()),
    ('journal_entries', JournalEntry, 'user_id', ()), ('voice_logs', VoiceLog, 'user_id', ()),
    ('digital_detox_logs', DigitalDetoxLog, 'user_id', ()), ('daily_check_ins', RPMData, 'user_id', ()),
    ('medications', Medication, 'user_id', ()), ('medication_logs', MedicationLog, 'user_id', ()),
    ('breathing_logs', BreathingExerciseLog, 'user_id', ()), ('yoga_logs', YogaLog, 'user_id', ()),
    ('music_logs', MusicTherapyLog, 'user_id', ()), ('progress_recommendations', ProgressRecommendation, 'user_id', ()),
    ('goals', Goal, 'user_id', ()), ('appointments', Appointment, 'user_id', ()),
    ('appointments_as_provider', Appointment, 'provider_id', ('user_id', 'notes', 'rejection_reason')),
    ('notifications', Notification, 'recipient_id', ()),
    ('crisis_events', CrisisEvent, 'user_id', ('acknowledged_by', 'escalated_at', 'escalation_level')),
    ('consent_records', ConsentRecord, 'user_id', ()),
    ('blog_posts', BlogPost, 'author_id', ()), ('blog_comments', BlogComment, 'user_id', ()),
    ('contact_messages', ContactMessage, 'user_id', ()), ('assigned_providers', ProviderPatient, 'patient_id', ('id', 'patient_id')),
] + WELLBEING_EXPORT


def export_user_data(user):
    """Everything stored about `user` that belongs to them, as a JSON-serialisable dict."""
    data = {'exported_at': datetime.utcnow().isoformat(), 'profile': _row(user, skip=('password_hash',))}
    gam = Gamification.query.filter_by(user_id=user.id).first()
    data['gamification'] = _row(gam) if gam else None
    for key, model, col, skip in _EXPORT:
        data[key] = [_row(r, skip) for r in model.query.filter(getattr(model, col) == user.id).all()]
    # issued prescriptions only (a doctor's unfinished drafts are not the patient's record) and their items
    rx = Prescription.query.filter(Prescription.patient_id == user.id, Prescription.status != 'draft')
    skip = ('client_request_id', 'issue_request_id', 'row_version')
    data['prescriptions'] = [_row(r, skip) for r in rx.all()]
    data['prescription_items'] = [_row(i) for i in PrescriptionItem.query.filter(
        PrescriptionItem.prescription_id.in_(rx.with_entities(Prescription.id))).order_by(PrescriptionItem.id)]
    return data


@auth_bp.route('/account/data')
@login_required
def account_data():
    user = db.session.get(User, session['user_id'])
    return render_template('account_data.html', user=user, google_only=bool(user.google_id),
                           delete_phrase=DELETE_PHRASE, consent_version=consent_version(),
                           consents=ConsentRecord.query.filter_by(user_id=user.id).order_by(ConsentRecord.accepted_at).all())


@auth_bp.route('/account/export', methods=['POST'])
@login_required
@limiter.limit('10 per hour', methods=['POST'])
def account_export():
    user = db.session.get(User, session['user_id'])
    payload = json.dumps(export_user_data(user), indent=2, default=str)
    audit(user.id, 'export_account', 'user', user.id)
    db.session.commit()
    resp = Response(payload, mimetype='application/json')
    resp.headers['Content-Disposition'] = f'attachment; filename="mind-full-horizon-data-{user.id}.json"'
    resp.headers['Cache-Control'] = 'no-store'
    return resp


@auth_bp.route('/account/delete', methods=['POST'])
@login_required
@limiter.limit('5 per hour', methods=['POST'])
def account_delete():
    """Permanently delete the logged-in user's account after re-authentication.

    Child rows go through the ON DELETE CASCADE foreign keys; links that must survive (appointments where this user
    was the provider, crisis acknowledgements, audit actors, sent notifications) are set to NULL by the database.
    Only an AuditLog row with the user id and the action stays.
    """
    user = db.session.get(User, session['user_id'])
    if user.role == 'admin':  # administrators are removed by the operator (CLI), never from the web
        flash('Administrator accounts cannot be deleted here. Ask the service operator.', 'error')
        return redirect(url_for('auth.account_data'))
    if user.google_id:  # no usable password: re-authenticate with the email address plus a typed phrase
        ok = (hmac.compare_digest((request.form.get('confirm_email') or '').strip().lower().encode(), user.email.encode())
              and (request.form.get('confirm_phrase') or '').strip() == DELETE_PHRASE)
    else:
        ok = user.check_password(request.form.get('password') or '')
    if not ok:
        flash('We could not confirm it is you, so the account was not deleted.', 'error')
        return redirect(url_for('auth.account_data'))

    uid = user.id
    if Prescription.query.filter_by(provider_id=uid).first():  # issued prescriptions must be kept: deactivate instead
        user.deactivated_at = datetime.utcnow()
        audit(uid, 'staff_deactivate', 'user', uid, by='self')
        db.session.commit()
        session.clear()
        flash('Your account was deactivated, not deleted, because prescriptions you issued must be kept. '
              'Contact your institution administrator.', 'success')
        return redirect(url_for('core.index'))
    try:
        audit(None, 'delete_account', 'user', uid)  # actor None: the user row is about to disappear
        db.session.delete(user)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.error("Account deletion failed", exc_info=True)
        flash('The account could not be deleted. Please try again.', 'error')
        return redirect(url_for('auth.account_data'))
    session.clear()
    flash('Your account and its data have been deleted.', 'success')
    return redirect(url_for('core.index'))
