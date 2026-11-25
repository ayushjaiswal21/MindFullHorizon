"""Cross-cutting system tables: notifications, background jobs, audit, consent, analytics."""
from datetime import datetime
from core.extensions import db

__all__ = ["Notification", "Job", "AuditLog", "ConsentRecord", "AnalyticsEvent"]


class Notification(db.Model):
    """Simple notification/message model for provider->patient quick messages and alerts."""
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    type = db.Column(db.String(50), nullable=False, default='message')
    payload = db.Column(db.JSON, nullable=True)
    message = db.Column(db.Text, nullable=True)
    read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.Index('idx_notif_recipient_created', 'recipient_id', 'created_at'),)

    sender = db.relationship('User', foreign_keys=[sender_id], backref=db.backref('sent_notifications', passive_deletes=True))
    recipient = db.relationship('User', foreign_keys=[recipient_id], backref=db.backref('notifications', cascade='all, delete-orphan', passive_deletes=True))

    def __repr__(self):
        return f'<Notification {self.type} to {self.recipient_id}>'


class Job(db.Model):
    """Durable background job (transactional outbox). Worker: utils/jobs.py. `last_error` is a short code, NEVER user text."""
    __tablename__ = 'jobs'
    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(50), nullable=False)  # 'crisis_alert' | 'send_email' | 'ai_insight' ...
    payload = db.Column(db.JSON, nullable=True)  # ids only, no free text from patients
    status = db.Column(db.String(10), nullable=False, default='queued')
    attempts = db.Column(db.Integer, nullable=False, default=0)
    max_attempts = db.Column(db.Integer, nullable=False, default=5)
    run_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    locked_at = db.Column(db.DateTime, nullable=True)
    locked_by = db.Column(db.String(60), nullable=True)
    last_error = db.Column(db.String(200), nullable=True)
    idempotency_key = db.Column(db.String(120), unique=True, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    finished_at = db.Column(db.DateTime, nullable=True)

    __table_args__ = (
        db.Index('idx_jobs_status_run_at', 'status', 'run_at'),
        db.CheckConstraint("status IN ('queued','running','done','failed','dead')", name='ck_job_status'),
    )


class AuditLog(db.Model):
    """Who accessed or changed sensitive data. `meta` holds ids/codes only, never patient text."""
    __tablename__ = 'audit_log'
    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    action = db.Column(db.String(50), nullable=False, index=True)  # e.g. 'view_patient', 'ack_crisis'
    target_type = db.Column(db.String(30), nullable=True)
    target_id = db.Column(db.Integer, nullable=True)
    meta = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)


class ConsentRecord(db.Model):
    """Stored proof of consent: which notice version a user accepted, and when."""
    __tablename__ = 'consent_records'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    kind = db.Column(db.String(20), nullable=False)  # 'privacy' | 'age18'
    version = db.Column(db.String(20), nullable=False)
    accepted_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('user_id', 'kind', 'version', name='uq_consent_user_kind_version'),)


class AnalyticsEvent(db.Model):
    """First-party, consent-gated product event. No user id, no IP, no free text."""
    __tablename__ = 'analytics_events'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, index=True)
    path = db.Column(db.String(200), nullable=True)
    utm_source = db.Column(db.String(100), nullable=True)
    utm_medium = db.Column(db.String(100), nullable=True)
    utm_campaign = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
