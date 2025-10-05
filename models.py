"""Database models for the Mindful Horizon application."""
from datetime import datetime, timedelta
from sqlalchemy import func
from sqlalchemy.exc import OperationalError
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db
import logging

# Module logger
logger = logging.getLogger(__name__)

class User(db.Model):
    """User model for both patients and providers."""
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=True, index=True)  # 'patient' or 'provider'
    institution = db.Column(db.String(100), nullable=True, index=True)  # For institutional aggregation
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    last_assessment_at = db.Column(db.DateTime, nullable=True, index=True)
    profile_pic = db.Column(db.String(255), nullable=True)  # Path to profile picture
    google_id = db.Column(db.String(120), unique=True, nullable=True, index=True)
    
    # Composite indexes for common queries
    __table_args__ = (
        db.Index('idx_user_role_institution', 'role', 'institution'),
        db.Index('idx_user_email_role', 'email', 'role'),
    )
    
    # Relationships with cascade delete rules
    assessments = db.relationship('Assessment', backref='user', lazy=True, cascade='all, delete-orphan')
    digital_detox_logs = db.relationship('DigitalDetoxLog', backref='user', lazy=True, cascade='all, delete-orphan')
    rpm_data = db.relationship('RPMData', backref='user', lazy=True, cascade='all, delete-orphan')
    gamification = db.relationship('Gamification', backref='user', uselist=False, cascade='all, delete-orphan')
    medications = db.relationship('Medication', backref='user', lazy=True, cascade='all, delete-orphan')
    medication_logs = db.relationship('MedicationLog', backref='user', lazy=True, cascade='all, delete-orphan')
    breathing_logs = db.relationship('BreathingExerciseLog', backref='user', lazy=True, cascade='all, delete-orphan')
    yoga_logs = db.relationship('YogaLog', backref='user', lazy=True, cascade='all, delete-orphan')
    music_logs = db.relationship('MusicTherapyLog', backref='user', lazy=True, cascade='all, delete-orphan')
    progress_recommendations = db.relationship('ProgressRecommendation', backref='user', lazy=True, cascade='all, delete-orphan')
    clinical_notes = db.relationship('ClinicalNote', foreign_keys='[ClinicalNote.patient_id]', backref='patient_user', lazy=True, cascade='all, delete-orphan')

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
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    category = db.Column(db.String(50), default='general')
    tags = db.Column(db.Text, nullable=True)  # Comma-separated tags
    views = db.Column(db.Integer, default=0)
    is_featured = db.Column(db.Boolean, default=False)
    is_published = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    author = db.relationship('User', backref='blog_posts')
    likes = db.relationship('BlogLike', backref='post', lazy='dynamic', cascade='all, delete-orphan')
    comments = db.relationship('BlogComment', backref='post', lazy='dynamic', cascade='all, delete-orphan')
    
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
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('blog_posts.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships - Fixed: removed delete-orphan from many-to-one relationship
    user = db.relationship('User', backref='blog_likes')
    
    # Ensure a user can only like a post once
    __table_args__ = (db.UniqueConstraint('user_id', 'post_id', name='unique_user_post_like'),)
    
    def __repr__(self):
        return f'<BlogLike user:{self.user_id} post:{self.post_id}>'


class BlogComment(db.Model):
    """Blog comment model for storing post comments."""
    __tablename__ = 'blog_comments'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('blog_posts.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('blog_comments.id'), nullable=True)  # For reply functionality
    content = db.Column(db.Text, nullable=False)
    is_edited = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships - Fixed: self-referencing relationship should use delete instead of delete-orphan
    parent = db.relationship('BlogComment', remote_side=[id], backref='replies')
    
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
    most_popular_post_id = db.Column(db.Integer, db.ForeignKey('blog_posts.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    most_popular_post = db.relationship('BlogPost', backref='insights')
    
    def __repr__(self):
        return f'<BlogInsight {self.date}>'

class Assessment(db.Model):
    """Assessment model for storing user assessments."""
    __tablename__ = 'assessments'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    assessment_type = db.Column(db.String(50), nullable=False, index=True)  # 'GAD-7', 'PHQ-9', 'mood'
    score = db.Column(db.Integer, nullable=False)
    responses = db.Column(db.JSON, nullable=True)  # Store individual question responses
    ai_insights = db.Column(db.Text, nullable=True)  # AI-generated insights (stored as JSON string)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Composite indexes for common queries
    __table_args__ = (
        db.Index('idx_assessment_user_type', 'user_id', 'assessment_type'),
        db.Index('idx_assessment_user_created', 'user_id', 'created_at'),
    )

class DigitalDetoxLog(db.Model):
    """Digital detox log model for storing user screen time and other digital wellness data."""
    __tablename__ = 'digital_detox_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, index=True)
    screen_time_hours = db.Column(db.Float, nullable=False)
    academic_score = db.Column(db.Integer, nullable=True)
    social_interactions = db.Column(db.String(20), nullable=True)  # 'high', 'medium', 'low'
    ai_score = db.Column(db.String(20), nullable=True)  # AI-generated wellness score
    ai_suggestion = db.Column(db.Text, nullable=True)  # AI-generated suggestions
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Composite indexes for common queries
    __table_args__ = (
        db.Index('idx_detox_user_date', 'user_id', 'date'),
        db.Index('idx_detox_user_created', 'user_id', 'created_at'),
    )

class RPMData(db.Model):
    """RPM data model for storing user remote patient monitoring data."""
    __tablename__ = 'rpm_data'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    heart_rate = db.Column(db.Integer, nullable=True)
    sleep_duration = db.Column(db.Float, nullable=True)
    steps = db.Column(db.Integer, nullable=True)
    mood_score = db.Column(db.Integer, nullable=True)  # 1-10 scale
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Gamification(db.Model):
    """Gamification model for storing user gamification data."""
    __tablename__ = 'gamification'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    points = db.Column(db.Integer, default=0)
    streak = db.Column(db.Integer, default=0)
    badges = db.Column(db.JSON, default=list)  # List of earned badges
    last_activity = db.Column(db.Date, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ClinicalNote(db.Model):
    """Clinical note model for storing provider notes."""
    __tablename__ = 'clinical_notes'
    
    id = db.Column(db.Integer, primary_key=True)
    provider_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    session_date = db.Column(db.DateTime, nullable=False)
    transcript = db.Column(db.Text, nullable=True)
    ai_generated_note = db.Column(db.Text, nullable=True)
    provider_notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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

class Appointment(db.Model):
    """Appointment model for storing user appointments."""
    __tablename__ = 'appointments'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    provider_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.String(10), nullable=False)
    appointment_type = db.Column(db.String(50), nullable=False)
    notes = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='booked', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships - Fixed: removed delete-orphan from many-to-one relationships
    user = db.relationship('User', foreign_keys=[user_id], backref='appointments')
    provider = db.relationship('User', foreign_keys=[provider_id])
    
    def __repr__(self):
        return f'<Appointment {self.id} - {self.user_id} on {self.date} at {self.time}>'

class Goal(db.Model):
    """Goal model for storing user goals."""
    __tablename__ = 'goals'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
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
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship - Fixed: removed delete-orphan from many-to-one relationship
    user = db.relationship('User', backref='goals')
    
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
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    dosage = db.Column(db.String(50), nullable=True)
    frequency = db.Column(db.String(50), nullable=True)
    time_of_day = db.Column(db.String(50), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Fixed: removed delete-orphan from many-to-one relationship
    logs = db.relationship('MedicationLog', backref='medication', lazy=True)

    def __repr__(self):
        return f'<Medication {self.name}>'

class MedicationLog(db.Model):
    """Medication log model for storing user medication logs."""
    __tablename__ = 'medication_logs'
    id = db.Column(db.Integer, primary_key=True)
    medication_id = db.Column(db.Integer, db.ForeignKey('medications.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    taken_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<MedicationLog {self.id}>'

class BreathingExerciseLog(db.Model):
    """Breathing exercise log model for storing user breathing exercise logs."""
    __tablename__ = 'breathing_exercise_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    exercise_name = db.Column(db.String(100), nullable=False)
    duration_minutes = db.Column(db.Integer, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<BreathingExerciseLog {self.exercise_name}>'

class YogaLog(db.Model):
    """Yoga log model for storing user yoga logs."""
    __tablename__ = 'yoga_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    session_name = db.Column(db.String(100), nullable=False)
    duration_minutes = db.Column(db.Integer, nullable=False)
    difficulty_level = db.Column(db.String(20), nullable=False, default='Beginner')
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<YogaLog {self.session_name} - {self.duration_minutes} minutes>'

class MusicTherapyLog(db.Model):
    """Music therapy log model for tracking user mood music sessions."""
    __tablename__ = 'music_therapy_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    mood = db.Column(db.String(50), nullable=False)  # happy, sad, angry, calm, anxious, focus
    brainwave = db.Column(db.String(20), nullable=True)  # alpha, beta, delta, gamma, theta
    frequency = db.Column(db.Float, nullable=True)  # Hz
    type = db.Column(db.String(20), nullable=True)  # pure, isochronic, solfeggio
    label = db.Column(db.String(255), nullable=True)
    filename = db.Column(db.String(255), nullable=True)
    duration_minutes = db.Column(db.Integer, nullable=True)  # optional
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f'<MusicTherapyLog {self.mood} - {self.label or self.filename}>'


class ProgressRecommendation(db.Model):
    """Model for storing AI-generated progress recommendations."""
    __tablename__ = 'progress_recommendations'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    recommendations = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Prescription(db.Model):
    """Prescription model for providers to send to patients."""
    __tablename__ = 'prescriptions'
    id = db.Column(db.Integer, primary_key=True)
    provider_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    medication_name = db.Column(db.String(200), nullable=False)
    dosage = db.Column(db.String(100), nullable=False)
    instructions = db.Column(db.Text, nullable=True)
    issue_date = db.Column(db.DateTime, default=datetime.utcnow)
    expiry_date = db.Column(db.DateTime, nullable=True)

    # Relationships - Fixed: removed delete-orphan from many-to-one relationships
    provider = db.relationship('User', foreign_keys=[provider_id], backref='prescribed_prescriptions')
    patient = db.relationship('User', foreign_keys=[patient_id], backref='received_prescriptions')

    def __repr__(self):
        return f'<Prescription {self.medication_name} for patient {self.patient_id}>'

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


class Notification(db.Model):
    """Simple notification/message model for provider->patient quick messages and alerts."""
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    type = db.Column(db.String(50), nullable=False, default='message')
    payload = db.Column(db.JSON, nullable=True)
    message = db.Column(db.Text, nullable=True)
    read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_notifications')
    recipient = db.relationship('User', foreign_keys=[recipient_id], backref='notifications')

    def __repr__(self):
        return f'<Notification {self.type} to {self.recipient_id}>'


# Helper functions for analytics
def get_user_wellness_trend(user_id, days=30):
    """Get wellness trend for a specific user over the last N days"""
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)
    
    detox_data = DigitalDetoxLog.query.filter(
        DigitalDetoxLog.user_id == user_id,
        DigitalDetoxLog.date >= start_date,
        DigitalDetoxLog.date <= end_date
    ).order_by(DigitalDetoxLog.date).all()
    
    assessments = Assessment.query.filter(
        Assessment.user_id == user_id,
        Assessment.created_at >= datetime.combine(start_date, datetime.min.time())
    ).order_by(Assessment.created_at).all()
    
    return {
        'digital_detox': detox_data,
        'assessments': assessments
    }

def get_institutional_summary(institution, db, days_active=7, days_risk=7, days_assessments=30):
    """Get summary statistics for an institution"""
    users = User.query.filter_by(institution=institution, role='patient').all()
    user_ids = [u.id for u in users]

    if not user_ids:
        return {
            'total_users': 0,
            'active_users': 0,
            'avg_screen_time': 0.0,
            'high_risk_users': 0,
            'engagement_rate': 0.0,
            'avg_wellness_score': 0.0,
            'avg_session_duration': 0,
            'completion_rate': 0.0,
            'satisfaction_score': 0.0
        }

    # Define timeframes
    active_start_date = datetime.now().date() - timedelta(days=days_active)
    risk_start_date = datetime.now().date() - timedelta(days=days_risk)
    assessment_start_date = datetime.now().date() - timedelta(days=days_assessments)

    # --- Active Users and Engagement Rate ---
    # Consider various activities for engagement
    active_detox_users = db.session.query(DigitalDetoxLog.user_id).filter(
        DigitalDetoxLog.user_id.in_(user_ids),
        DigitalDetoxLog.date >= active_start_date
    ).distinct().all()
    active_assessment_users = db.session.query(Assessment.user_id).filter(
        Assessment.user_id.in_(user_ids),
        Assessment.created_at >= datetime.combine(active_start_date, datetime.min.time())
    ).distinct().all()
    active_medication_users = db.session.query(MedicationLog.user_id).filter(
        MedicationLog.user_id.in_(user_ids),
        MedicationLog.taken_at >= datetime.combine(active_start_date, datetime.min.time())
    ).distinct().all()
    active_breathing_users = db.session.query(BreathingExerciseLog.user_id).filter(
        BreathingExerciseLog.user_id.in_(user_ids),
        BreathingExerciseLog.created_at >= datetime.combine(active_start_date, datetime.min.time())
    ).distinct().all()
    active_yoga_users = db.session.query(YogaLog.user_id).filter(
        YogaLog.user_id.in_(user_ids),
        YogaLog.created_at >= datetime.combine(active_start_date, datetime.min.time())
    ).distinct().all()
    try:
        active_music_users = db.session.query(MusicTherapyLog.user_id).filter(
            MusicTherapyLog.user_id.in_(user_ids),
            MusicTherapyLog.created_at >= datetime.combine(active_start_date, datetime.min.time())
        ).distinct().all()
    except OperationalError as e:
        # If the music_therapy_logs table doesn't exist (e.g., migrations not applied),
        # treat as zero activity instead of crashing the provider dashboard.
        logger.warning(f"Database table missing or inaccessible when querying music therapy logs: {e}")
        active_music_users = []

    all_active_user_ids = set()
    for result in active_detox_users + active_assessment_users + active_medication_users + active_breathing_users + active_yoga_users + active_music_users:
        all_active_user_ids.add(result[0])

    active_users_count = len(all_active_user_ids)
    engagement_rate = round((active_users_count / len(users)) * 100, 1) if users else 0.0

    # --- Average Screen Time ---
    avg_screen_time = db.session.query(func.avg(DigitalDetoxLog.screen_time_hours)).filter(
        DigitalDetoxLog.user_id.in_(user_ids),
        DigitalDetoxLog.date >= risk_start_date
    ).scalar() or 0.0

    # --- High-Risk Users (screen time > 8 hours average, or low mood score) ---
    # Efficiently calculate average screen time for each user
    user_avg_screen_times = db.session.query(
        DigitalDetoxLog.user_id,
        func.avg(DigitalDetoxLog.screen_time_hours)
    ).filter(
        DigitalDetoxLog.user_id.in_(user_ids),
        DigitalDetoxLog.date >= risk_start_date
    ).group_by(DigitalDetoxLog.user_id).all()

    high_risk_count = 0
    for user_id, avg_st in user_avg_screen_times:
        if avg_st and avg_st > 8:
            high_risk_count += 1
        # Add other risk factors here, e.g., low mood score from RPMData
        # For example:
        # latest_rpm = RPMData.query.filter_by(user_id=user_id).order_by(RPMData.date.desc()).first()
        # if latest_rpm and latest_rpm.mood_score and latest_rpm.mood_score < 4:
        #     high_risk_count += 1

    # --- Average Wellness Score (based on recent assessments) ---
    recent_assessments = Assessment.query.filter(
        Assessment.user_id.in_(user_ids),
        Assessment.created_at >= datetime.combine(assessment_start_date, datetime.min.time())
    ).all()

    total_wellness_score = 0
    scored_assessments_count = 0
    for assessment in recent_assessments:
        # Assuming a simple mapping for GAD-7/PHQ-9 to a 1-10 wellness scale
        # This is a simplified example; a more robust calculation might be needed
        if assessment.assessment_type in ['GAD-7', 'PHQ-9'] and assessment.score is not None:
            # Invert score: lower assessment score = higher wellness
            max_score = 21 if assessment.assessment_type == 'GAD-7' else 27
            wellness_contribution = (1 - (assessment.score / max_score)) * 10 # Scale to 0-10
            total_wellness_score += wellness_contribution
            scored_assessments_count += 1
        elif assessment.assessment_type == 'Daily Mood' and assessment.score is not None:
            total_wellness_score += assessment.score * 2 # Scale mood (1-5) to 1-10
            scored_assessments_count += 1

    avg_wellness_score = round(total_wellness_score / scored_assessments_count, 1) if scored_assessments_count > 0 else 0.0

    # --- Average Session Duration and Completion Rate (Appointments) ---
    all_appointments = Appointment.query.filter(
        Appointment.provider_id.in_(user_ids), # Assuming provider_id in Appointment refers to the institution's providers
        Appointment.date >= active_start_date
    ).all()

    total_session_duration = 0 # Placeholder, as Appointment model doesn't have duration
    completed_appointments = 0
    for appt in all_appointments:
        # Placeholder for duration, assuming an average session length if not stored
        total_session_duration += 45 # Assuming 45 minutes per session
        if appt.status == 'completed': # Assuming a 'completed' status for appointments
            completed_appointments += 1

    avg_session_duration = round(total_session_duration / len(all_appointments), 1) if all_appointments else 0.0
    completion_rate = round((completed_appointments / len(all_appointments)) * 100, 1) if all_appointments else 0.0

    # --- Patient Satisfaction Score (Placeholder) ---
    # This would typically come from a separate feedback/survey model
    satisfaction_score = 4.2 # Placeholder for now

    return {
        'total_users': len(users),
        'active_users': active_users_count,
        'avg_screen_time': round(avg_screen_time, 1),
        'high_risk_users': high_risk_count,
        'engagement_rate': engagement_rate,
        'avg_wellness_score': avg_wellness_score,
        'avg_session_duration': avg_session_duration,
        'completion_rate': completion_rate,
        'satisfaction_score': satisfaction_score
    }
