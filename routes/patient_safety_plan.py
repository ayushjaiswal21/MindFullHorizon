"""Safety plan pages (attached to the patient blueprint). Private to the student; shared read-only with assigned
providers only when the student switches sharing on. Never logs or echoes the text outside the student's own pages."""
import uuid

from flask import flash, g, jsonify, redirect, render_template, request, session, url_for

from decorators import login_required, patient_required
from extensions import db
from routes.patient import patient_bp
from services import safety_plan as sp
from utils import idempotency as idem

GENERIC_ERROR = 'The safety plan could not be saved. Please try again.'


def _plan_values(plan):
    if plan is None:
        return {k: '' for k, _, _ in sp.TEXT_FIELDS} | {'help_people': []}
    return {k: getattr(plan, k) or '' for k, _, _ in sp.TEXT_FIELDS} | {'help_people': plan.help_people or []}


def _edit(values, error=None, status=200):
    padded = list(values.get('help_people') or [])
    padded += [{'name': '', 'phone': ''}] * (sp.MAX_PEOPLE - len(padded))
    return render_template('safety_plan_edit.html', fields=sp.TEXT_FIELDS, v=values, people=padded, error=error,
                           limits=sp, request_id=uuid.uuid4().hex, exists=sp.get_plan(session['user_id']) is not None), status


@patient_bp.route('/safety-plan')
@login_required
@patient_required
def safety_plan():
    plan = sp.get_plan(session['user_id'])
    return render_template('safety_plan.html', plan=plan, fields=sp.TEXT_FIELDS, v=_plan_values(plan))


@patient_bp.route('/safety-plan/edit')
@login_required
@patient_required
def safety_plan_edit():
    return _edit(_plan_values(sp.get_plan(session['user_id'])))


@patient_bp.route('/safety-plan', methods=['POST'])
@login_required
@patient_required
def safety_plan_save():
    values, error = sp.parse_form(request.form)
    if error:
        return _edit(values, error, 400)
    key = idem.get_key()  # a malformed key raises InvalidKey, answered by the blueprint handler
    try:
        _, created = sp.save_plan(session['user_id'], values, key)
    except Exception:
        db.session.rollback()
        return _edit(values, GENERIC_ERROR, 500)
    flash('Your safety plan was saved.' if created else 'Your safety plan was updated.', 'success')
    return redirect(url_for('patient.safety_plan'))


@patient_bp.route('/safety-plan/delete', methods=['POST'])
@login_required
@patient_required
def safety_plan_delete():
    sp.delete_plan(session['user_id'])
    flash('Your safety plan was deleted.', 'success')
    return redirect(url_for('patient.safety_plan'))


@patient_bp.route('/safety-plan/sharing', methods=['POST'])
@login_required
@patient_required
def safety_plan_sharing():
    plan = sp.set_sharing(session['user_id'], request.form.get('share') == 'on')
    if plan is None:
        flash('Make a safety plan first.', 'error')
    else:
        flash('Your counsellors can now read your safety plan.' if plan.share_with_counsellors
              else 'Your safety plan is private again.', 'success')
    return redirect(url_for('patient.safety_plan'))


@patient_bp.route('/api/safety-plan/link')
@login_required
@patient_required
def safety_plan_link_api():
    """For the chat crisis banner (built in the browser): which link text to show. No plan text."""
    return jsonify(sp.link_state(session['user_id']) | {'url': url_for('patient.safety_plan')})


@patient_bp.app_template_global('safety_plan_link')
def safety_plan_link():
    """{'url', 'label', 'exists'} for the signed-in student; None for everyone else (templates guard on it)."""
    if session.get('user_role') != 'patient' or not session.get('user_id'):
        return None
    if not hasattr(g, 'sp_link'):  # one query per request, even with the footer and the page both asking
        g.sp_link = sp.link_state(session['user_id']) | {'url': url_for('patient.safety_plan')}
    return g.sp_link


@patient_bp.app_template_global('shared_safety_plan')
def shared_safety_plan(patient_id):
    """The plan a student chose to share, for the provider report. None unless shared and assigned (audited)."""
    if session.get('user_role') != 'provider' or not session.get('user_id'):
        return None
    return sp.shared_plan_for_provider(session['user_id'], patient_id)
