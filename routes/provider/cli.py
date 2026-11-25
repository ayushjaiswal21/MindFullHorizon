"""CLI: manual provider<->patient assignment (flask assign-patient <provider_email> <patient_email>)."""
import click

from models import Appointment, User, db
from utils.assignments import link_provider_patient
from utils.audit import audit

from . import provider_bp


@provider_bp.cli.command('assign-patient')
@click.argument('provider_email')
@click.argument('patient_email')
def assign_patient_cli(provider_email, patient_email):
    """Link a patient to a provider of the same institution (source 'manual')."""
    prov = User.query.filter_by(email=provider_email.strip().lower(), role='provider').first()
    pat = User.query.filter_by(email=patient_email.strip().lower(), role='patient').first()
    if not (prov and pat):
        raise click.ClickException('Provider or patient not found.')
    if not link_provider_patient(prov.id, pat.id, 'manual'):
        raise click.ClickException('Provider and patient must belong to the same institution.')
    audit(None, 'assign_patient', 'user', pat.id, provider_id=prov.id, source='manual')
    db.session.commit()
    click.echo('Assigned.')


@provider_bp.cli.command('backfill-assignments')
def backfill_assignments_cli():
    """One-off for databases that predate P-02: link every patient who already has a non-rejected appointment with a provider."""
    rows = (db.session.query(Appointment.provider_id, Appointment.user_id)
            .filter(Appointment.provider_id.isnot(None), Appointment.status != 'rejected').distinct().all())
    n = sum(bool(link_provider_patient(p, u)) for p, u in rows)
    db.session.commit()
    click.echo(f'Linked {n} of {len(rows)} provider-patient pairs.')
