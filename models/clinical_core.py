"""Core clinical workflow tables: notes, appointments, goals, medications, crisis events, assignments."""
from datetime import datetime
from core.extensions import db
from utils.field_encryption import EncryptedText
from utils.timeutil import ist_today

__all__ = [
    "ClinicalNote", "InstitutionalAnalytics", "Appointment", "Goal", "Medication",
    "MedicationLog", "CrisisEvent", "ProviderPatient",
]


class ClinicalNote(db.Model):
    """Clinical note model for storing provider notes."""
    __tablename__ = 'clinical_notes'

    id = db.Column(db.Integer, primary_key=True)
    provider_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    session_date = db.Column(db.DateTime, nullable=False)
    transcript = db.Column(EncryptedText, nullable=True)  # O-04: clinical free text, encrypted at rest
    ai_generated_note = db.Column(EncryptedText, nullable=True)
    provider_notes = db.Column(EncryptedText, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.Index('idx_note_patient_session', 'patient_id', 'session_date'),)


class InstitutionalAnalytics(db.Model):
    """Institutional analytics model for storing institutional data."""
    __tablename__ = 'institutional_analytics'

    id = db.Column(db.Integer, primary_key=True)
    institution = db.Column(db.String(100), nullable=False)
    date = db.Column(db.Date, nullable=False)
    total_users = db.Column(db.Integer, default=0)
    active_users = db.Column(db.Integer, default=0)
    avg_wellness_score = db.Column(db.Float, nullable=True)
    avg_screen_time = db.Column(db.Float, nullable=True)
    high_risk_users = db.Column(db.Integer, default=0)
    engagement_rate = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


_LIVE_APPT = "status IN ('pending','accepted','booked')"
_LIVE_UNASSIGNED = _LIVE_APPT + " AND provider_id IS NULL"  # double submits of a provider-less request


class Appointment(db.Model):
    """Appointment model for storing user appointments."""
    __tablename__ = 'appointments'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    provider_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    date = db.Column(db.Date, nullable=False, index=True)
    time = db.Column(db.String(10), nullable=False)
    appointment_type = db.Column(db.String(50), nullable=False)
    notes = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='pending', nullable=False, index=True)
    rejection_reason = db.Column(db.Text, nullable=True)
    modality = db.Column(db.String(10), nullable=True)  # doctor appointments: video | in_person (design 3.3)
    consult_started_at = db.Column(db.DateTime, nullable=True)  # set once by the doctor pressing "Start consult"
    client_request_id = db.Column(db.String(64), nullable=True)  # idempotency key (utils/idempotency.py)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships - Fixed: removed delete-orphan from many-to-one relationships
    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('appointments', cascade='all, delete-orphan', passive_deletes=True))
    provider = db.relationship('User', foreign_keys=[provider_id])

    __table_args__ = (
        # speeds the provider/date/time conflict check
        db.Index('idx_appt_provider_date_time', 'provider_id', 'date', 'time'),
        db.CheckConstraint("status IN ('pending','accepted','rejected','booked','completed','cancelled')", name='ck_appt_status'),
        db.CheckConstraint("modality IS NULL OR modality IN ('video','in_person','audio','chat')", name='ck_appt_modality'),
        db.Index('uq_appt_user_crid', 'user_id', 'client_request_id', unique=True),
        # no double booking: one live appointment per provider slot, and one live provider-less request per patient slot (frees on reject/cancel/complete)
        db.Index('uq_appt_active_slot', 'provider_id', 'date', 'time', unique=True,
                 sqlite_where=db.text(_LIVE_APPT), postgresql_where=db.text(_LIVE_APPT)),
        db.Index('uq_appt_active_user_slot', 'user_id', 'date', 'time', unique=True,
                 sqlite_where=db.text(_LIVE_UNASSIGNED), postgresql_where=db.text(_LIVE_UNASSIGNED)),
    )

    def __repr__(self):
        return f'<Appointment {self.id} - {self.user_id} on {self.date} at {self.time}>'


class Goal(db.Model):
    """Goal model for storing user goals."""
    __tablename__ = 'goals'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(50), nullable=False)  # 'mental_health', 'physical_health', 'digital_wellness', etc.
    target_value = db.Column(db.Float, nullable=True)  # For measurable goals
    current_value = db.Column(db.Float, default=0.0)
    unit = db.Column(db.String(20), nullable=True)  # 'minutes', 'hours', 'days', etc.
    status = db.Column(db.String(20), default='active')  # 'active', 'completed', 'paused'
    priority = db.Column(db.String(10), default='medium')  # 'low', 'medium', 'high'
    start_date = db.Column(db.Date, nullable=False)
    target_date = db.Column(db.Date, nullable=True)
    completed_date = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    client_request_id = db.Column(db.String(64), nullable=True)  # idempotency key (utils/idempotency.py)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.CheckConstraint("status IN ('active','completed','paused')", name='ck_goal_status'),
        db.CheckConstraint("priority IN ('low','medium','high')", name='ck_goal_priority'),
        db.CheckConstraint('target_value >= 0 AND current_value >= 0', name='ck_goal_values_nonneg'),
        db.Index('uq_goal_user_crid', 'user_id', 'client_request_id', unique=True),
    )

    # Relationship - Fixed: removed delete-orphan from many-to-one relationship
    user = db.relationship('User', backref=db.backref('goals', cascade='all, delete-orphan', passive_deletes=True))

    @property
    def progress_percentage(self):
        """Calculate progress percentage based on current and target values."""
        if self.target_value and self.target_value > 0:
            return min((self.current_value / self.target_value) * 100, 100)
        return 0


class Medication(db.Model):
    """Medication model for storing user medications."""
    __tablename__ = 'medications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    dosage = db.Column(db.String(50), nullable=True)
    frequency = db.Column(db.String(50), nullable=True)
    time_of_day = db.Column(db.String(50), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Fixed: removed delete-orphan from many-to-one relationship
    logs = db.relationship('MedicationLog', backref='medication', lazy=True, cascade='all, delete-orphan', passive_deletes=True)

    def __repr__(self):
        return f'<Medication {self.name}>'


class MedicationLog(db.Model):
    """Medication log model for storing user medication logs."""
    __tablename__ = 'medication_logs'
    id = db.Column(db.Integer, primary_key=True)
    medication_id = db.Column(db.Integer, db.ForeignKey('medications.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    taken_at = db.Column(db.DateTime, default=datetime.utcnow)
    log_date = db.Column(db.Date, nullable=False, default=ist_today)  # IST day; one log per medication per day

    __table_args__ = (
        db.Index('idx_medlog_user_taken', 'user_id', 'taken_at'),
        db.UniqueConstraint('medication_id', 'log_date', name='uq_medlog_med_day'),
    )

    def __repr__(self):
        return f'<MedicationLog {self.id}>'


class CrisisEvent(db.Model):
    """Audit record of a detected crisis. `reason` is a short code, NEVER user text."""
    __tablename__ = 'crisis_events'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    source = db.Column(db.String(20), nullable=False)  # 'chat' | 'phq9' | 'journal'
    severity = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    acknowledged_at = db.Column(db.DateTime, nullable=True)
    acknowledged_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    escalated_at = db.Column(db.DateTime, nullable=True)  # last time an unacknowledged alert was escalated
    escalation_level = db.Column(db.Integer, nullable=False, default=0, server_default='0')

    __table_args__ = (db.CheckConstraint("source IN ('chat','phq9','journal')", name='ck_crisis_source'),)


class ProviderPatient(db.Model):
    """Assignment of a patient to a provider (assigned-only visibility, decision P-02)."""
    __tablename__ = 'provider_patients'
    id = db.Column(db.Integer, primary_key=True)
    provider_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    source = db.Column(db.String(15), nullable=False, default='appointment')  # 'appointment' | 'manual'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('provider_id', 'patient_id', name='uq_provider_patient'),
        db.CheckConstraint("source IN ('appointment','manual')", name='ck_pp_source'),
    )
