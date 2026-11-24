"""Admin sign-in and the admin home (design 1.2, 5.4). Admins are created only by `flask create-admin`."""
from flask import current_app, flash, make_response, redirect, render_template, request, session, url_for

from extensions import limiter
from models import User
from routes.admin import admin_bp
from routes.auth import LOGIN_ERROR
from utils.session_stamp import stamp_session


def safe_next(value):
    """A post-login target must be an admin path on this site (no scheme, no //host)."""
    value = value or ''
    return value if value.startswith('/admin') and not value.startswith('//') and chr(92) not in value else None


def _login_page(**ctx):
    resp = make_response(render_template('admin/login.html', **ctx))
    resp.headers['X-Robots-Tag'] = 'noindex, nofollow'
    return resp


@admin_bp.route('/')
def home():
    """/admin/ is the overview for a signed-in admin; everyone else goes to the admin sign-in page."""
    if session.get('user_role') == 'admin':
        from routes.admin.dashboard import dashboard
        return dashboard()
    return redirect(url_for('admin.login'))


@admin_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit('10 per minute', methods=['POST'])
def login():
    if request.method == 'GET':
        if session.get('user_role') == 'admin':
            return redirect(safe_next(request.args.get('next')) or url_for('admin.home'))
        return _login_page(form={})
    email = (request.form.get('email') or '').strip().lower()
    password = request.form.get('password') or ''
    user = User.query.filter_by(email=email).first() if email and password else None
    # one message for unknown email, wrong password, wrong role and deactivated account
    if not (user and user.role == 'admin' and user.deactivated_at is None and user.password_hash
            and user.check_password(password)):
        current_app.logger.warning('Admin login failed')
        flash(LOGIN_ERROR, 'error')
        return _login_page(form={'email': email})
    session.clear()
    session.permanent = True
    session.update(user_id=user.id, user_email=user.email, user_role='admin', user_name=user.name,
                   user_institution=user.institution)
    stamp_session(user)  # without the stamp the next request is treated as signed out (utils/session_stamp.py)
    current_app.logger.info('Admin login successful - user id %s', user.id)
    return redirect(safe_next(request.values.get('next')) or url_for('admin.home'))
