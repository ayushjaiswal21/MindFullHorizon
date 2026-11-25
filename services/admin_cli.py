"""Operator CLI for accounts that cannot be created through the web (design 1.2).

    flask create-admin --email E --name N --institution I [--pharmacy-desk] [--password-env VAR]
    flask set-pharmacy-desk --email E --on|--off
    flask admin-set-password --email E [--password-env VAR]
    flask set-provider-type --email E --type counsellor|doctor

They use whatever DATABASE_URL is set, so the owner can run them from their own machine against the production
database. Passwords come from a hidden prompt (asked twice) or from the environment variable named by --password-env;
they are never accepted as a command-line value. Every command writes an AuditLog row with actor None.
"""
import os

import click

from core.extensions import db
from models import PrescriberProfile, User
from services.roles import norm_inst
from utils.audit import audit
from utils.timeutil import utcnow


def _password(password_env):
    from routes.auth import is_strong_password
    if password_env:
        value = os.environ.get(password_env, '')
        if not value:
            raise click.ClickException(f'Environment variable {password_env} is empty or not set.')
    else:
        value = click.prompt('Password', hide_input=True, confirmation_prompt=True)
    ok, message = is_strong_password(value)
    if not ok:
        raise click.ClickException(message)
    return value


def _user(email, role):
    user = User.query.filter_by(email=(email or '').strip().lower()).first()
    if user is None or user.role != role:
        raise click.ClickException(f'No {role} account with that email.')
    return user


def _create_admin(email, name, institution, pharmacy_desk, password_env):
    email, name = email.strip().lower(), ' '.join(name.split())
    institution = ' '.join(institution.split())
    if not (email and name and norm_inst(institution)):
        raise click.ClickException('Email, name and institution are all required.')
    if User.query.filter_by(email=email).first():
        raise click.ClickException('An account with that email already exists. Nothing was changed.')
    password = _password(password_env)
    user = User(email=email, name=name, role='admin', institution=institution, is_pharmacy_desk=bool(pharmacy_desk))
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    audit(None, 'admin_created', 'user', user.id, pharmacy_desk=bool(pharmacy_desk))
    db.session.commit()
    click.echo(f'Administrator created: {email} (id {user.id}). Sign in at /admin/login.')


def init_admin_cli(app):
    @app.cli.command('create-admin')
    @click.option('--email', required=True)
    @click.option('--name', required=True)
    @click.option('--institution', required=True)
    @click.option('--pharmacy-desk', is_flag=True, help='Also the pharmacy desk (dispensing and stock changes).')
    @click.option('--password-env', default=None, help='Name of an environment variable holding the password.')
    def create_admin(email, name, institution, pharmacy_desk, password_env):
        """Create an institution administrator (the only way to make one)."""
        _create_admin(email, name, institution, pharmacy_desk, password_env)

    @app.cli.command('set-pharmacy-desk')
    @click.option('--email', required=True)
    @click.option('--on/--off', 'on', required=True)
    def set_pharmacy_desk(email, on):
        """Give or take away the pharmacy desk capability of an administrator."""
        user = _user(email, 'admin')
        user.is_pharmacy_desk = on
        audit(None, 'admin_pharmacy_desk_set', 'user', user.id, on=on)
        db.session.commit()
        click.echo(f'Pharmacy desk {"on" if on else "off"} for {user.email}.')

    @app.cli.command('admin-set-password')
    @click.option('--email', required=True)
    @click.option('--password-env', default=None)
    def admin_set_password(email, password_env):
        """Set a new password for an administrator."""
        user = _user(email, 'admin')
        user.set_password(_password(password_env))
        audit(None, 'admin_password_set', 'user', user.id)
        db.session.commit()
        click.echo('Password updated.')

    @app.cli.command('set-provider-type')
    @click.option('--email', required=True)
    @click.option('--type', 'ptype', type=click.Choice(['counsellor', 'doctor']), required=True)
    def set_provider_type(email, ptype):
        """Make a provider a counsellor or a doctor (a doctor gets a pending prescriber profile if it has none)."""
        user = _user(email, 'provider')
        if ptype == 'doctor' and not norm_inst(user.institution):
            raise click.ClickException('A doctor needs an institution.')
        user.provider_type = ptype
        audit(None, 'provider_type_set', 'user', user.id, to=ptype)
        if ptype == 'doctor' and PrescriberProfile.query.filter_by(user_id=user.id).first() is None:
            now = utcnow()
            db.session.add(PrescriberProfile(user_id=user.id, registration_number=f'PENDING{user.id}',
                                             council='Not provided', council_key='not provided',
                                             registered_since=now.year, status='pending', submitted_at=now,
                                             status_changed_at=now))
            click.echo('A pending prescriber profile was created: the doctor must enter the real registration details.')
        db.session.commit()
        click.echo(f'{user.email} is now a {ptype}.')
