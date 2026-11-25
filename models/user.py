"""Core User model."""
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from core.extensions import db

__all__ = ["User"]


class User(db.Model):
    """User model for both patients and providers."""
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='patient', index=True)  # 'patient', 'provider' or 'admin'
    provider_type = db.Column(db.String(12), nullable=True)  # providers only: 'counsellor' (or NULL) or 'doctor'
    deactivated_at = db.Column(db.DateTime, nullable=True)
    is_pharmacy_desk = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    institution = db.Column(db.String(100), nullable=True, index=True)  # For institutional aggregation
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    last_assessment_at = db.Column(db.DateTime, nullable=True, index=True)
    profile_pic = db.Column(db.String(255), nullable=True)  # Path to profile picture
    google_id = db.Column(db.String(120), unique=True, nullable=True, index=True)

    # Composite indexes for common queries
    __table_args__ = (
        db.Index('idx_user_role_institution', 'role', 'institution'),
        db.Index('idx_user_email_role', 'email', 'role'),
        db.CheckConstraint("role IN ('patient','provider','admin')", name='ck_user_role'),
        db.CheckConstraint("provider_type IS NULL OR provider_type IN ('counsellor','doctor')", name='ck_user_provider_type'),
    )

    # Relationships with cascade delete rules
    assessments = db.relationship('Assessment', backref='user', lazy=True, cascade='all, delete-orphan', passive_deletes=True)
    digital_detox_logs = db.relationship('DigitalDetoxLog', backref='user', lazy=True, cascade='all, delete-orphan', passive_deletes=True)
    rpm_data = db.relationship('RPMData', backref='user', lazy=True, cascade='all, delete-orphan', passive_deletes=True)
    gamification = db.relationship('Gamification', backref='user', uselist=False, cascade='all, delete-orphan', passive_deletes=True)
    medications = db.relationship('Medication', backref='user', lazy=True, cascade='all, delete-orphan', passive_deletes=True)
    medication_logs = db.relationship('MedicationLog', backref='user', lazy=True, cascade='all, delete-orphan', passive_deletes=True)
    breathing_logs = db.relationship('BreathingExerciseLog', backref='user', lazy=True, cascade='all, delete-orphan', passive_deletes=True)
    yoga_logs = db.relationship('YogaLog', backref='user', lazy=True, cascade='all, delete-orphan', passive_deletes=True)
    music_logs = db.relationship('MusicTherapyLog', backref='user', lazy=True, cascade='all, delete-orphan', passive_deletes=True)
    progress_recommendations = db.relationship('ProgressRecommendation', backref='user', lazy=True, cascade='all, delete-orphan', passive_deletes=True)
    clinical_notes = db.relationship('ClinicalNote', foreign_keys='[ClinicalNote.patient_id]', backref='patient_user', lazy=True, cascade='all, delete-orphan', passive_deletes=True)
    crisis_events = db.relationship('CrisisEvent', foreign_keys='[CrisisEvent.user_id]', backref='user', lazy=True, cascade='all, delete-orphan', passive_deletes=True)
    journal_entries = db.relationship('JournalEntry', backref='user', lazy=True, cascade='all, delete-orphan', passive_deletes=True)
    voice_logs = db.relationship('VoiceLog', backref='user', lazy=True, cascade='all, delete-orphan', passive_deletes=True)

    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Check if provided password matches hash"""
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.email}>'
