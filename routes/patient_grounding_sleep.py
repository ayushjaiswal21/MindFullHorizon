"""Grounding exercise (5-4-3-2-1) and sleep log pages, attached to the patient blueprint.

Grounding earns the normal wellbeing-activity points (same daily cap and ledger key as breathing, never tied to a
score). The sleep log is private and earns nothing."""
import uuid

from flask import flash, jsonify, redirect, render_template, request, session, url_for

from decorators import login_required, patient_required
from routes.patient import patient_bp
from services import sleep_log as sl
from utils import idempotency as idem
from utils.gamification import award_points
from utils.timeutil import ist_today

GROUNDING_POINTS = 20  # as a breathing session (docs/GAMIFICATION.md)
GROUNDING_STEPS = (
    (5, 'see', 'Look around and name 5 things you can see.', 'A pen, a crack in the wall, the colour of a curtain. Take your time.'),
    (4, 'feel', 'Notice 4 things you can feel.', 'Your feet on the floor, the chair under you, the fabric of your clothes.'),
    (3, 'hear', 'Listen for 3 things you can hear.', 'A fan, voices far away, your own breathing.'),
    (2, 'smell', 'Notice 2 things you can smell.', 'Or recall 2 smells you like. It is fine if you cannot find any.'),
    (1, 'taste', 'Notice 1 thing you can taste.', 'Or take a sip of water and notice that.'),
)


@patient_bp.route('/grounding')
@login_required
@patient_required
def grounding():
    return render_template('grounding.html', steps=GROUNDING_STEPS, request_id=uuid.uuid4().hex)


@patient_bp.route('/grounding/complete', methods=['POST'])
@login_required
@patient_required
def grounding_complete():
    """Record one finished exercise. The key is required: the ledger ref `grounding:<key>` makes a replay award nothing."""
    key = idem.get_key()
    if not key:
        return jsonify(success=False, message='Missing request id.'), 400
    award_points(session['user_id'], GROUNDING_POINTS, 'grounding_exercise', ref=f'grounding:{key}')
    return jsonify(success=True, message='Well done. Take a slow breath before you go back to what you were doing.')


def _sleep_page(form=None, error=None, status=200):
    ctx = sl.summary(session['user_id'])
    return render_template('sleep_log.html', s=ctx, quality=sl.QUALITY, form=form or {}, error=error,
                           today=ist_today().isoformat(), request_id=uuid.uuid4().hex, limits=sl), status


@patient_bp.route('/sleep')
@login_required
@patient_required
def sleep_log():
    return _sleep_page()


@patient_bp.route('/sleep', methods=['POST'])
@login_required
@patient_required
def sleep_log_save():
    key = idem.get_key()
    try:
        _, created = sl.add(session['user_id'], sl.parse(request.form), key)
    except sl.SleepError as exc:
        return _sleep_page(request.form, str(exc), 400)
    flash('Sleep entry saved.' if created else 'That entry was already saved.', 'success')
    return redirect(url_for('patient.sleep_log'))


@patient_bp.route('/sleep/<int:log_id>/delete', methods=['POST'])
@login_required
@patient_required
def sleep_log_delete(log_id):
    if not sl.delete(session['user_id'], log_id):
        return 'Not found', 404
    flash('Sleep entry deleted.', 'success')
    return redirect(url_for('patient.sleep_log'))
