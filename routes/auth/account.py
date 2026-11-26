"""Account data rights: export (GDPR-style download) and delete."""
import hmac
import json
from datetime import datetime, date

from flask import render_template, request, redirect, url_for, flash, session, current_app, Response

from models import (User, Gamification, ConsentRecord, db, Assessment, DigitalDetoxLog, RPMData, Medication,
                    MedicationLog, BreathingExerciseLog, YogaLog, MusicTherapyLog, ProgressRecommendation, Goal,
                    MoodLog, JournalEntry, VoiceLog, Appointment, Notification, CrisisEvent, Prescription,
                    PrescriptionItem, BlogPost, BlogComment, ContactMessage, ProviderPatient)
from core.decorators import login_required
from core.extensions import limiter
from utils.audit import audit
from services.wellbeing_export import WELLBEING_EXPORT

from . import auth_bp
from .consent import consent_version

DELETE_PHRASE = 'DELETE MY ACCOUNT'  # typed by Google-only users, who have no password to re-enter


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
