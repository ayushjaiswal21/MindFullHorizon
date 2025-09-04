from flask_sqlalchemy import SQLAlchemy
"""Database models for the Mindful Horizon application."""
from database import db
from datetime import datetime, timedelta
from sqlalchemy import func
from werkzeug.security import generate_password_hash, check_password_hash

class User(db.Model):
    """User model for both patients and providers."""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'patient' or 'provider'
    institution = db.Column(db.String(100), nullable=True)  # For institutional aggregation
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    assessments = db.relationship('Assessment', backref='user', lazy=True)
    digital_detox_logs = db.relationship('DigitalDetoxLog', backref='user', lazy=True)
    rpm_data = db.relationship('RPMData', backref='user', lazy=True)
    gamification = db.relationship('Gamification', backref='user', uselist=False)
    medications = db.relationship('Medication', backref='user', lazy=True)
    medication_logs = db.relationship('MedicationLog', backref='user', lazy=True)
    breathing_logs = db.relationship('BreathingExerciseLog', backref='user', lazy=True)
    yoga_logs = db.relationship('YogaLog', backref='user', lazy=True)
    
    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check if provided password matches hash"""
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.email}>'

class Assessment(db.Model):
    """Assessment model for storing user assessments."""
    __tablename__ = 'assessments'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    assessment_type = db.Column(db.String(50), nullable=False)  # 'GAD-7', 'PHQ-9', 'mood'
    score = db.Column(db.Integer, nullable=False)
    responses = db.Column(db.JSON, nullable=True)  # Store individual question responses
    ai_insights = db.Column(db.Text, nullable=True)  # AI-generated insights (stored as JSON string)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class DigitalDetoxLog(db.Model):
    """Digital detox log model for storing user screen time and other digital wellness data."""
    __tablename__ = 'digital_detox_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    screen_time_hours = db.Column(db.Float, nullable=False)
    academic_score = db.Column(db.Integer, nullable=True)
    social_interactions = db.Column(db.String(20), nullable=True)  # 'high', 'medium', 'low'
    ai_score = db.Column(db.String(20), nullable=True)  # AI-generated wellness score
    ai_suggestion = db.Column(db.Text, nullable=True)  # AI-generated suggestions
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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
    
    # Relationships
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
    
    # Relationship
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

    logs = db.relationship('MedicationLog', backref='medication', lazy=True, cascade="all, delete-orphan")

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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<YogaLog {self.session_name} - {self.duration_minutes} minutes>'

class MoodLog(db.Model):
    """Mood log model for storing user mood data."""
    __tablename__ = 'mood_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    mood_score = db.Column(db.Integer, nullable=False)  # 1-5 scale
    notes = db.Column(db.Text, nullable=True)  # Optional notes about mood
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<MoodLog {self.mood_score}/5 - {self.created_at}>'

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

def get_institutional_summary(institution, db):
    """Get summary statistics for an institution"""
    users = User.query.filter_by(institution=institution, role='patient').all()
    user_ids = [u.id for u in users]
    
    if not user_ids:
        return None
    
    # Get recent digital detox data
    recent_detox = DigitalDetoxLog.query.filter(
        DigitalDetoxLog.user_id.in_(user_ids),
        DigitalDetoxLog.date >= datetime.now().date() - timedelta(days=7)
    ).all()
    
    # Calculate metrics
    avg_screen_time = db.session.query(func.avg(DigitalDetoxLog.screen_time_hours)).filter(
        DigitalDetoxLog.user_id.in_(user_ids),
        DigitalDetoxLog.date >= datetime.now().date() - timedelta(days=7)
    ).scalar() or 0
    
    # Count high-risk users (screen time > 8 hours average)
    high_risk_count = 0
    for user_id in user_ids:
        user_avg = db.session.query(func.avg(DigitalDetoxLog.screen_time_hours)).filter(
            DigitalDetoxLog.user_id == user_id,
            DigitalDetoxLog.date >= datetime.now().date() - timedelta(days=7)
        ).scalar()
        if user_avg and user_avg > 8:
            high_risk_count += 1
    
    return {
        'total_users': len(users),
        'active_users': len(set([log.user_id for log in recent_detox])),
        'avg_screen_time': round(avg_screen_time, 1),
        'high_risk_users': high_risk_count,
        'engagement_rate': round((len(set([log.user_id for log in recent_detox])) / len(users)) * 100, 1) if users else 0
    }
