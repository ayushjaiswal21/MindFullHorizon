"""Points and streaks (never attached to assessment/mood scores; see CLAUDE.md)."""
from datetime import datetime
from extensions import db

__all__ = ["Gamification", "PointsLedger"]


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
