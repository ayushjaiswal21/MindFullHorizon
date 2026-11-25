"""Patient self-logged wellness activities: assessments, detox, exercises, journal, mood, voice."""
from datetime import datetime
from core.extensions import db
from utils.field_encryption import EncryptedJSON, EncryptedText
from utils.timeutil import ist_today

__all__ = [
    "Assessment", "DigitalDetoxLog", "RPMData", "BreathingExerciseLog", "YogaLog",
    "MusicTherapyLog", "ProgressRecommendation", "BinauralTrack", "MoodLog",
    "JournalEntry", "VoiceLog",
]


class Assessment(db.Model):
    """Assessment model for storing user assessments."""
    __tablename__ = 'assessments'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    assessment_type = db.Column(db.String(50), nullable=False, index=True)  # 'GAD-7', 'PHQ-9', 'mood'
    score = db.Column(db.Integer, nullable=False)
    # O-04: responses/contextual_responses can carry free text (e.g. mood check-in notes), encrypted at rest.
    responses = db.Column(EncryptedJSON, nullable=True)  # Store individual question responses
    contextual_responses = db.Column(EncryptedJSON, nullable=True) # Store contextual question responses
    ai_insights = db.Column(EncryptedText, nullable=True)  # AI-generated insights (stored as JSON string)
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
    notes = db.Column(EncryptedText, nullable=True)  # O-04: free text, encrypted at rest
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


class JournalEntry(db.Model):
    """Patient journal entry (replaces the in-memory shared_data dict)."""
    __tablename__ = 'journal_entries'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    # O-04: journal text is clinical free text, encrypted at rest.
    title = db.Column(EncryptedText, nullable=False)
    content = db.Column(EncryptedText, nullable=False)
    sentiment = db.Column(db.String(20), nullable=True)
    ai_suggestions = db.Column(EncryptedText, nullable=True)  # extra: the journal page shows AI suggestions
    client_request_id = db.Column(db.String(64), nullable=True)  # idempotency key (utils/idempotency.py)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (db.Index('uq_journal_user_crid', 'user_id', 'client_request_id', unique=True),)


class VoiceLog(db.Model):
    """Patient voice log (replaces the in-memory shared_data dict)."""
    __tablename__ = 'voice_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False)
    transcript = db.Column(EncryptedText, nullable=True)  # O-04: voice transcript, encrypted at rest
    # emotion: unused by new code since 2026-11-25 (migration 0010). The tone/emotion label was measured invalid
    # (docs/research/ai/SYNTHESIS.md 1.1, 3(c) item c1: pitch thresholds mostly detect pitch/sex not mood, EU AI
    # Act recital 44, Kintsugi shutdown). Column kept, nullable, non-destructive; never written for new rows.
    emotion = db.Column(db.String(30), nullable=True)
    # audio_features: now holds only {'duration': seconds} for new rows (pitch/energy/zcr/spectral-centroid, which
    # fed only the removed label and are speaker-identifying, are no longer computed or stored); see migration 0010.
    audio_features = db.Column(db.JSON, nullable=True)  # extra: voice log page renders these (duration only, not sensitive)
    ai_analysis = db.Column(EncryptedText, nullable=True)  # extra: voice log page renders this (unused for voice since 0010), encrypted at rest (O-04)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
