"""The doctor's prescribing profile (design 2, 5.3). Reachable while pending, rejected or suspended."""
from flask import flash, g, redirect, render_template, request, url_for

from core.decorators import doctor_provider_required, login_required, prescriptions_required
from core.extensions import db
from services import prescriber
from services.errors import ServiceError
from services.http import iso

FIELDS = ('registration_number', 'council', 'registered_since', 'specialisation')


def _profile_dict(p):
    if p is None:
        return None
    return {'status': p.status, 'registration_number': p.registration_number, 'council': p.council,
            'registered_since': p.registered_since, 'specialisation': p.specialisation,
            'submitted_at': iso(p.submitted_at), 'verified_at': iso(p.verified_at),
            'review_due_at': iso(p.review_due_at)}


def _render(form, errors, status=200):
    p = prescriber.get_profile(g.actor.id)
    return render_template('provider_rx/profile.html', profile=_profile_dict(p), state=prescriber.state_of(p),
                           form=form, errors=errors), status


def init(bp):
    @bp.route('/prescribing-profile')
    @prescriptions_required
    @login_required
    @doctor_provider_required
    def rx_profile():
        p = prescriber.get_profile(g.actor.id)
        return _render({k: (_profile_dict(p) or {}).get(k) or '' for k in FIELDS}, {})

    @bp.route('/prescribing-profile', methods=['POST'])
    @prescriptions_required
    @login_required
    @doctor_provider_required
    def rx_profile_save():
        form = {k: (request.form.get(k) or '').strip() for k in FIELDS}
        try:
            prescriber.submit_profile(g.actor.id, form['registration_number'], form['council'],
                                      form['registered_since'], form['specialisation'])
            db.session.commit()
        except ServiceError as err:
            db.session.rollback()
            return _render(form, err.fields or {'registration_number': err.message}, err.http)
        flash('Your prescribing profile was saved.', 'success')
        return redirect(url_for('provider.rx_profile'))
