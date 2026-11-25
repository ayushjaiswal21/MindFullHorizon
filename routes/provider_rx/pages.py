"""Server-rendered prescribing pages (design 5.3): prescribe, my prescriptions, detail, print."""
from flask import abort, g, redirect, render_template, request, url_for

from core.decorators import login_required, prescriptions_required, verified_prescriber_required
from core.extensions import db
from models import Prescription
from routes.provider_rx._common import limits, page_config, patient_or_404, rx_texts
from services.prescriptions import effective_status, serialize
from services.prescriptions._common import ACTIVE
from utils.audit import audit
from utils.seo import site_url
from utils.timeutil import utcnow

TABS = ('draft', 'issued', 'closed')


def _own_or_404(rx_id):
    rx = Prescription.query.filter_by(id=rx_id, provider_id=g.actor.id).first()
    if rx is None or rx.status == 'legacy':
        abort(404)
    return rx


def init(bp):
    @bp.route('/prescriptions')
    @prescriptions_required
    @login_required
    @verified_prescriber_required
    def rx_list():
        tab = request.args.get('tab') if request.args.get('tab') in TABS else 'issued'
        return render_template('provider_rx/list.html', tab=tab, config=page_config())

    @bp.route('/prescribe')
    @prescriptions_required
    @login_required
    @verified_prescriber_required
    def rx_prescribe():
        draft, patient = None, None
        if request.args.get('draft_id', type=int):
            rx = _own_or_404(request.args.get('draft_id', type=int))
            if rx.status != 'draft':
                return redirect(url_for('provider.rx_detail', rx_id=rx.id))
            draft, patient = serialize(rx, 'doctor'), patient_or_404(rx.patient_id)
        elif request.args.get('patient_id', type=int):
            patient = patient_or_404(request.args.get('patient_id', type=int))
        return render_template('provider_rx/prescribe.html', config=page_config(), limits=limits(), draft=draft,
                               patient={'id': patient.id, 'name': patient.name} if patient else None,
                               rx_texts=rx_texts())

    @bp.route('/prescriptions/<int:rx_id>')
    @prescriptions_required
    @login_required
    @verified_prescriber_required
    def rx_detail(rx_id):
        rx = _own_or_404(rx_id)
        if rx.status == 'draft':
            return redirect(url_for('provider.rx_prescribe', draft_id=rx.id))
        eff = effective_status(rx)
        return render_template('provider_rx/detail.html', rx=serialize(rx, 'doctor'), config=page_config(),
                               can_cancel=rx.status in ACTIVE, can_amend=eff == 'issued')

    @bp.route('/prescriptions/<int:rx_id>/print')
    @prescriptions_required
    @login_required
    @verified_prescriber_required
    def rx_print(rx_id):
        rx = _own_or_404(rx_id)
        if rx.status == 'draft':
            abort(404)
        audit(g.actor.id, 'rx_print', 'prescription', rx.id, by='doctor')
        db.session.commit()
        return render_template('provider_rx/print.html', rx=serialize(rx, 'doctor'), site_url=site_url(),
                               printed_at=utcnow())
