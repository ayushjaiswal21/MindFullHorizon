"""Database models for the Mindful Horizon application."""
from datetime import date, datetime, timedelta
import sqlite3
from sqlalchemy import case, event, func, select, union
from sqlalchemy.engine import Engine
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db
from utils.timeutil import ist_today
import logging

# Module logger
logger = logging.getLogger(__name__)


@event.listens_for(Engine, 'connect')
def _sqlite_foreign_keys_on(dbapi_conn, _record):
    """SQLite ignores FOREIGN KEY / ON DELETE CASCADE unless this pragma is set per connection."""
    if isinstance(dbapi_conn, sqlite3.Connection):
        cur = dbapi_conn.cursor()
        cur.execute('PRAGMA foreign_keys=ON')
        cur.close()


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


# BlogPost model for blog system (enhanced with relationships)
class BlogPost(db.Model):
    """Blog post model for storing blog entries."""
    __tablename__ = 'blog_posts'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    category = db.Column(db.String(50), default='general')
    tags = db.Column(db.Text, nullable=True)  # Comma-separated tags
    views = db.Column(db.Integer, default=0)
    is_featured = db.Column(db.Boolean, default=False)
    is_published = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    author = db.relationship('User', backref=db.backref('blog_posts', cascade='all, delete-orphan', passive_deletes=True))
    likes = db.relationship('BlogLike', backref='post', lazy='dynamic', cascade='all, delete-orphan', passive_deletes=True)
    comments = db.relationship('BlogComment', backref='post', lazy='dynamic', cascade='all, delete-orphan', passive_deletes=True)

    @property
    def like_count(self):
        """Get total number of likes for this post"""
        return self.likes.count()

    @property
    def comment_count(self):
        """Get total number of comments for this post"""
        return self.comments.count()

    def is_liked_by(self, user_id):
        """Check if a user has liked this post"""
        return self.likes.filter_by(user_id=user_id).first() is not None

    @property
    def engagement_score(self):
        """Calculate engagement score based on likes, comments, and views"""
        return (self.like_count * 2) + (self.comment_count * 3) + (self.views * 0.1)

    def __repr__(self):
        return f'<BlogPost {self.title}>'


class BlogLike(db.Model):
    """Blog like model for tracking post likes."""
    __tablename__ = 'blog_likes'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('blog_posts.id', ondelete='CASCADE'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('blog_likes', cascade='all, delete-orphan', passive_deletes=True))

    # Ensure a user can only like a post once
    __table_args__ = (db.UniqueConstraint('user_id', 'post_id', name='unique_user_post_like'),)

    def __repr__(self):
        return f'<BlogLike user:{self.user_id} post:{self.post_id}>'


class BlogComment(db.Model):
    """Blog comment model for storing post comments."""
    __tablename__ = 'blog_comments'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    post_id = db.Column(db.Integer, db.ForeignKey('blog_posts.id', ondelete='CASCADE'), nullable=False, index=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('blog_comments.id', ondelete='CASCADE'), nullable=True)  # For reply functionality
    content = db.Column(db.Text, nullable=False)
    is_edited = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships - Fixed: self-referencing relationship should use delete instead of delete-orphan
    parent = db.relationship('BlogComment', remote_side=[id], backref=db.backref('replies', cascade='all, delete-orphan', passive_deletes=True))
    user = db.relationship('User', backref=db.backref('blog_comments', cascade='all, delete-orphan', passive_deletes=True))

    @property
    def author_name(self):
        return self.user.name if self.user else 'Deleted user'

    def __repr__(self):
        return f'<BlogComment {self.id} by {self.user_id}>'


class BlogInsight(db.Model):
    """Blog insight model for tracking analytics and insights."""
    __tablename__ = 'blog_insights'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    total_posts = db.Column(db.Integer, default=0)
    total_views = db.Column(db.Integer, default=0)
    total_likes = db.Column(db.Integer, default=0)
    total_comments = db.Column(db.Integer, default=0)
    top_categories = db.Column(db.JSON, nullable=True)  # Store popular categories
    engagement_rate = db.Column(db.Float, default=0.0)
    most_popular_post_id = db.Column(db.Integer, db.ForeignKey('blog_posts.id', ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    most_popular_post = db.relationship('BlogPost', backref=db.backref('insights', passive_deletes=True))

    def __repr__(self):
        return f'<BlogInsight {self.date}>'

class Assessment(db.Model):
    """Assessment model for storing user assessments."""
    __tablename__ = 'assessments'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    assessment_type = db.Column(db.String(50), nullable=False, index=True)  # 'GAD-7', 'PHQ-9', 'mood'
    score = db.Column(db.Integer, nullable=False)
    responses = db.Column(db.JSON, nullable=True)  # Store individual question responses
    contextual_responses = db.Column(db.JSON, nullable=True) # Store contextual question responses
    ai_insights = db.Column(db.Text, nullable=True)  # AI-generated insights (stored as JSON string)
    client_request_id = db.Column(db.String(64), nullable=True)  # idempotency key (utils/idempotency.py)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # Composite indexes for common queries
    __table_args__ = (
        db.Index('idx_assessment_user_type', 'user_id', 'assessment_type'),
        db.Index('idx_assessment_user_created', 'user_id', 'created_at'),
        db.Index('uq_assessment_user_crid', 'user_id', 'client_request_id', unique=True),
    )

class DigitalDetoxLog(db.Model):
    """Digital detox log model for storing user screen time and other digital wellness data."""
    __tablename__ = 'digital_detox_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, index=True)
    screen_time_hours = db.Column(db.Float, nullable=False)
    academic_score = db.Column(db.Integer, nullable=True)
    social_interactions = db.Column(db.String(20), nullable=True)  # 'high', 'medium', 'low'
    ai_score = db.Column(db.String(20), nullable=True)  # AI-generated wellness score
    ai_suggestion = db.Column(db.Text, nullable=True)  # AI-generated suggestions
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # Composite indexes for common queries
    __table_args__ = (
        db.Index('idx_detox_user_date', 'user_id', 'date', unique=True),  # one log per user per IST day
        db.Index('idx_detox_user_created', 'user_id', 'created_at'),
    )

class RPMData(db.Model):
    """RPM data model for storing user remote patient monitoring data."""
    __tablename__ = 'rpm_data'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    heart_rate = db.Column(db.Integer, nullable=True)
    sleep_duration = db.Column(db.Float, nullable=True)
    steps = db.Column(db.Integer, nullable=True)
    mood_score = db.Column(db.Integer, nullable=True)  # 1-10 scale
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.Index('idx_rpm_user_date', 'user_id', 'date'),)

class Gamification(db.Model):
    """Gamification model for storing user gamification data."""
    __tablename__ = 'gamification'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True)
    points = db.Column(db.Integer, default=0)
    streak = db.Column(db.Integer, default=0)
    badges = db.Column(db.JSON, default=list)  # List of earned badges
    last_activity = db.Column(db.Date, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (db.CheckConstraint('points >= 0 AND streak >= 0', name='ck_gamification_nonneg'),)


class PointsLedger(db.Model):
    """One row per points award. UNIQUE(user_id, ref) makes a replayed award a no-op (ref e.g. 'medlog:12')."""
    __tablename__ = 'points_ledger'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    ref = db.Column(db.String(80), nullable=False)
    activity_type = db.Column(db.String(30), nullable=False)
    points = db.Column(db.Integer, nullable=False)  # 0 when the daily cap was already reached
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'ref', name='uq_points_user_ref'),
        db.Index('idx_points_user_activity_created', 'user_id', 'activity_type', 'created_at'),
    )


class ClinicalNote(db.Model):
    """Clinical note model for storing provider notes."""
    __tablename__ = 'clinical_notes'

    id = db.Column(db.Integer, primary_key=True)
    provider_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    session_date = db.Column(db.DateTime, nullable=False)
    transcript = db.Column(db.Text, nullable=True)
    ai_generated_note = db.Column(db.Text, nullable=True)
    provider_notes = db.Column(db.Text, nullable=True)
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

class BreathingExerciseLog(db.Model):
    """Breathing exercise log model for storing user breathing exercise logs."""
    __tablename__ = 'breathing_exercise_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    exercise_name = db.Column(db.String(100), nullable=False)
    duration_minutes = db.Column(db.Integer, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    client_request_id = db.Column(db.String(64), nullable=True)  # idempotency key (utils/idempotency.py)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.Index('idx_breathing_user_created', 'user_id', 'created_at'),
        db.CheckConstraint('duration_minutes BETWEEN 1 AND 180', name='ck_breathing_duration'),
        db.Index('uq_breathing_user_crid', 'user_id', 'client_request_id', unique=True),
    )

    def __repr__(self):
        return f'<BreathingExerciseLog {self.exercise_name}>'

class YogaLog(db.Model):
    """Yoga log model for storing user yoga logs."""
    __tablename__ = 'yoga_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    session_name = db.Column(db.String(100), nullable=False)
    duration_minutes = db.Column(db.Integer, nullable=False)
    difficulty_level = db.Column(db.String(20), nullable=False, default='Beginner')
    notes = db.Column(db.Text, nullable=True)
    client_request_id = db.Column(db.String(64), nullable=True)  # idempotency key (utils/idempotency.py)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.Index('idx_yoga_user_created', 'user_id', 'created_at'),
        db.CheckConstraint('duration_minutes BETWEEN 1 AND 180', name='ck_yoga_duration'),
        db.Index('uq_yoga_user_crid', 'user_id', 'client_request_id', unique=True),
    )

    def __repr__(self):
        return f'<YogaLog {self.session_name} - {self.duration_minutes} minutes>'

class MusicTherapyLog(db.Model):
    """Music therapy log model for tracking user mood music sessions."""
    __tablename__ = 'music_therapy_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    mood = db.Column(db.String(50), nullable=False)  # happy, sad, angry, calm, anxious, focus
    brainwave = db.Column(db.String(20), nullable=True)  # alpha, beta, delta, gamma, theta
    frequency = db.Column(db.Float, nullable=True)  # Hz
    type = db.Column(db.String(20), nullable=True)  # pure, isochronic, solfeggio
    label = db.Column(db.String(255), nullable=True)
    filename = db.Column(db.String(255), nullable=True)
    duration_minutes = db.Column(db.Integer, nullable=True)  # optional
    client_request_id = db.Column(db.String(64), nullable=True)  # idempotency key (utils/idempotency.py)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        db.CheckConstraint('duration_minutes BETWEEN 1 AND 180', name='ck_music_duration'),
        db.Index('uq_music_user_crid', 'user_id', 'client_request_id', unique=True),
    )

    def __repr__(self):
        return f'<MusicTherapyLog {self.mood} - {self.label or self.filename}>'


class ProgressRecommendation(db.Model):
    """Model for storing AI-generated progress recommendations."""
    __tablename__ = 'progress_recommendations'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    recommendations = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class BinauralTrack(db.Model):
    """Optional table for storing binaural beats dataset tracks."""
    __tablename__ = 'binaural_tracks'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    artist = db.Column(db.String(200), nullable=True)
    emotion = db.Column(db.String(100), nullable=True, index=True)
    youtube_id = db.Column(db.String(100), nullable=True, index=True)
    tags = db.Column(db.JSON, nullable=True)
    source_file = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'artist': self.artist,
            'emotion': self.emotion,
            'youtube_id': self.youtube_id,
            'tags': self.tags,
            'source_file': self.source_file
        }

    def __repr__(self):
        return f'<BinauralTrack {self.id} - {self.title}>'


class MoodLog(db.Model):
    """Mood log model for storing user mood entries."""
    __tablename__ = 'mood_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    mood_score = db.Column(db.Integer, nullable=False)  # e.g., 1-10 scale
    notes = db.Column(db.Text, nullable=True)
    client_request_id = db.Column(db.String(64), nullable=True)  # idempotency key (utils/idempotency.py)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        db.CheckConstraint('mood_score BETWEEN 1 AND 10', name='ck_mood_score'),
        db.Index('uq_mood_user_crid', 'user_id', 'client_request_id', unique=True),
    )

    # Relationship - Fixed: removed delete-orphan from many-to-one relationship
    user = db.relationship('User', backref=db.backref('mood_logs', cascade='all, delete-orphan', passive_deletes=True))

    def __repr__(self):
        return f'<MoodLog {self.id} for user {self.user_id}>'


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


class JournalEntry(db.Model):
    """Patient journal entry (replaces the in-memory shared_data dict)."""
    __tablename__ = 'journal_entries'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    sentiment = db.Column(db.String(20), nullable=True)
    ai_suggestions = db.Column(db.Text, nullable=True)  # extra: the journal page shows AI suggestions
    client_request_id = db.Column(db.String(64), nullable=True)  # idempotency key (utils/idempotency.py)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (db.Index('uq_journal_user_crid', 'user_id', 'client_request_id', unique=True),)


class VoiceLog(db.Model):
    """Patient voice log (replaces the in-memory shared_data dict)."""
    __tablename__ = 'voice_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False)
    transcript = db.Column(db.Text, nullable=True)
    emotion = db.Column(db.String(30), nullable=True)
    audio_features = db.Column(db.JSON, nullable=True)  # extra: voice log page renders these
    ai_analysis = db.Column(db.Text, nullable=True)  # extra: voice log page renders this
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)


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


class ContactMessage(db.Model):
    """Message from the public contact form. Always stored first; email is a job."""
    __tablename__ = 'contact_messages'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(150), nullable=True)
    message = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    status = db.Column(db.String(15), nullable=False, default='new')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (db.CheckConstraint("status IN ('new','emailed','email_failed','read')", name='ck_contact_status'),)


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


def get_institutional_summary(institution, db=db, days_active=7, days_risk=7, days_assessments=30):
    """Aggregate stats for the patients of ONE institution (case-insensitive exact match).

    Everything is a SQL aggregate. A metric that cannot be computed from stored data is None
    (never a made-up number): avg_session_duration and satisfaction_score are not stored at all.
    """
    name = (institution or '').strip().lower()
    out = {'total_users': 0, 'active_users': 0, 'avg_screen_time': None, 'high_risk_users': 0,
           'engagement_rate': None, 'avg_wellness_score': None, 'avg_session_duration': None,
           'completion_rate': None, 'satisfaction_score': None}
    if not name:
        return out
    s = db.session
    pids = select(User.id).where(User.role == 'patient', func.lower(func.trim(User.institution)) == name)
    total = s.scalar(select(func.count()).select_from(pids.subquery()))
    if not total:
        return out

    now = datetime.utcnow()  # created_at/taken_at columns are stored as naive UTC
    since = lambda days: now - timedelta(days=days)
    active_from, risk_from = since(days_active), since(days_risk)
    active = union(*(
        select(col).where(col.in_(pids), when >= (ist_today() - timedelta(days=days_active) if when.type.python_type is date else active_from))
        for col, when in (
            (DigitalDetoxLog.user_id, DigitalDetoxLog.date), (Assessment.user_id, Assessment.created_at),
            (MedicationLog.user_id, MedicationLog.taken_at), (BreathingExerciseLog.user_id, BreathingExerciseLog.created_at),
            (YogaLog.user_id, YogaLog.created_at), (MusicTherapyLog.user_id, MusicTherapyLog.created_at),
        )))
    active_users = s.scalar(select(func.count()).select_from(active.subquery()))

    screen = (select(DigitalDetoxLog.user_id, func.avg(DigitalDetoxLog.screen_time_hours).label('avg'))
              .where(DigitalDetoxLog.user_id.in_(pids), DigitalDetoxLog.date >= ist_today() - timedelta(days=days_risk))
              .group_by(DigitalDetoxLog.user_id).subquery())
    avg_screen, high_risk = s.execute(select(
        func.avg(screen.c.avg), func.coalesce(func.sum(case((screen.c.avg > 8, 1), else_=0)), 0))).one()

    # lower GAD-7/PHQ-9 score = better; scale to 0-10. Daily Mood is stored 1-10 already (no scaling).
    wellness = case(
        (Assessment.assessment_type == 'GAD-7', (1 - Assessment.score / 21.0) * 10),
        (Assessment.assessment_type == 'PHQ-9', (1 - Assessment.score / 27.0) * 10),
        (Assessment.assessment_type == 'Daily Mood', Assessment.score * 1.0))
    avg_wellness = s.scalar(select(func.avg(wellness)).where(
        Assessment.user_id.in_(pids), Assessment.created_at >= since(days_assessments)))

    # completion = completed / (completed + cancelled) over the active window, patients' own appointments
    done, cancelled = s.execute(select(
        func.coalesce(func.sum(case((Appointment.status == 'completed', 1), else_=0)), 0),
        func.coalesce(func.sum(case((Appointment.status == 'cancelled', 1), else_=0)), 0),
    ).where(Appointment.user_id.in_(pids), Appointment.date >= ist_today() - timedelta(days=days_active))).one()

    out.update(
        total_users=total, active_users=active_users,
        engagement_rate=round(active_users / total * 100, 1),
        avg_screen_time=None if avg_screen is None else round(avg_screen, 1),
        high_risk_users=int(high_risk or 0),
        avg_wellness_score=None if avg_wellness is None else round(avg_wellness, 1),
        completion_rate=round(done / (done + cancelled) * 100, 1) if done + cancelled else None)
    return out


from models_clinical import *  # noqa: E402,F401,F403  (same metadata; keeps `from models import Prescription` working)
