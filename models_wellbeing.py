"""Private wellbeing tools of a student: safety plan, sleep log, reminder preference.

Same metadata as models.py (imported at the bottom of that file, so `from models import SafetyPlan` keeps working).
All three belong to one user, are deleted with the account (FK CASCADE) and are part of the account export.
SafetyPlan text is sensitive free text: never log it, never send it to the AI.
"""
from core.extensions import db
from utils.field_encryption import EncryptedJSON, EncryptedText
from utils.timeutil import utcnow

__all__ = ["SafetyPlan", "SleepLog", "ReminderPref"]


class SafetyPlan(db.Model):
    """One Stanley-Brown style safety plan per student (six sections). Shared with assigned providers only if the
    student switches `share_with_counsellors` on."""
    __tablename__ = 'safety_plans'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    # O-04: safety-plan text (and the named contacts in help_people) is sensitive free text, encrypted at rest.
    warning_signs = db.Column(EncryptedText, nullable=True)
    coping_alone = db.Column(EncryptedText, nullable=True)
    places_people = db.Column(EncryptedText, nullable=True)
    help_people = db.Column(EncryptedJSON, nullable=True)  # list of {"name": str, "phone": str}, at most 5
    professionals = db.Column(EncryptedText, nullable=True)  # the student's own additions; national helplines are not stored
    safer_surroundings = db.Column(EncryptedText, nullable=True)
    share_with_counsellors = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    client_request_id = db.Column(db.String(64), nullable=True)  # idempotency key (utils/idempotency.py)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    user = db.relationship('User', backref=db.backref('safety_plan', uselist=False, cascade='all, delete-orphan',
                                                      passive_deletes=True))

    __table_args__ = (
        db.Index('uq_safety_plan_user', 'user_id', unique=True),
        db.Index('uq_safety_plan_user_crid', 'user_id', 'client_request_id', unique=True),
    )


class SleepLog(db.Model):
    """One night of sleep. `night_date` is the IST date the student woke up (one row per user and date)."""
    __tablename__ = 'sleep_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    night_date = db.Column(db.Date, nullable=False)
    bedtime = db.Column(db.String(5), nullable=False)  # 'HH:MM', IST wall clock
    wake_time = db.Column(db.String(5), nullable=False)
    duration_minutes = db.Column(db.Integer, nullable=False)
    quality = db.Column(db.Integer, nullable=False)
    note = db.Column(db.String(200), nullable=True)
    client_request_id = db.Column(db.String(64), nullable=True)  # idempotency key (utils/idempotency.py)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    user = db.relationship('User', backref=db.backref('sleep_logs', cascade='all, delete-orphan', passive_deletes=True))

    __table_args__ = (
        db.CheckConstraint('quality BETWEEN 1 AND 5', name='ck_sleep_quality'),
        db.CheckConstraint('duration_minutes BETWEEN 1 AND 1440', name='ck_sleep_duration'),
        db.Index('uq_sleep_user_night', 'user_id', 'night_date', unique=True),
        db.Index('uq_sleep_user_crid', 'user_id', 'client_request_id', unique=True),
    )


class ReminderPref(db.Model):
    """Opt-in reminder email. Status 'pending' until the student clicks the link sent to the account address.
    `nonce` changes on every (re)enable so an old confirmation link stops working. `last_sent_on` is the IST date of
    the last reminder (hard limit: one per user per day)."""
    __tablename__ = 'reminder_prefs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    frequency = db.Column(db.String(6), nullable=False, default='daily')
    hour_ist = db.Column(db.Integer, nullable=False, default=20)
    weekday = db.Column(db.Integer, nullable=False, default=0, server_default='0')  # 0 = Monday, weekly only
    status = db.Column(db.String(8), nullable=False, default='pending')
    nonce = db.Column(db.String(16), nullable=False)
    confirmed_at = db.Column(db.DateTime, nullable=True)
    last_sent_on = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    user = db.relationship('User', backref=db.backref('reminder_pref', uselist=False, cascade='all, delete-orphan',
                                                      passive_deletes=True))

    __table_args__ = (
        db.CheckConstraint("frequency IN ('daily','weekly')", name='ck_reminder_frequency'),
        db.CheckConstraint('hour_ist BETWEEN 0 AND 23', name='ck_reminder_hour'),
        db.CheckConstraint('weekday BETWEEN 0 AND 6', name='ck_reminder_weekday'),
        db.CheckConstraint("status IN ('pending','active')", name='ck_reminder_status'),
        db.Index('uq_reminder_user', 'user_id', unique=True),
    )
