"""Post-crisis follow-up tracker tables (docs/FOLLOWUPS.md).

Same metadata as models.py (imported at the bottom of that file). A plan belongs to one acknowledged CrisisEvent;
steps hold dates, a status and a fixed outcome code only. Any note text is a ClinicalNote, never a step column.
"""
from core.extensions import db
from utils.timeutil import utcnow

__all__ = ["FollowUpPlan", "FollowUpStep"]


class FollowUpPlan(db.Model):
    __tablename__ = 'followup_plans'
    id = db.Column(db.Integer, primary_key=True)
    crisis_event_id = db.Column(db.Integer, db.ForeignKey('crisis_events.id', ondelete='CASCADE'), nullable=False, unique=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    owner_provider_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    status = db.Column(db.String(12), nullable=False, default='open')  # open | completed | closed_early
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    closed_at = db.Column(db.DateTime, nullable=True)
    closed_reason = db.Column(db.String(20), nullable=True)  # code from utils.followups.CLOSE_REASONS

    steps = db.relationship('FollowUpStep', backref='plan', order_by='FollowUpStep.seq', cascade='all, delete-orphan',
                            passive_deletes=True)

    __table_args__ = (
        db.CheckConstraint("status IN ('open','completed','closed_early')", name='ck_fplan_status'),
        db.Index('idx_fplan_status', 'status'),
    )


class FollowUpStep(db.Model):
    __tablename__ = 'followup_steps'
    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey('followup_plans.id', ondelete='CASCADE'), nullable=False)
    seq = db.Column(db.Integer, nullable=False)
    due_date = db.Column(db.Date, nullable=False)  # IST calendar day
    status = db.Column(db.String(8), nullable=False, default='pending')  # pending | done | missed | skipped
    completed_at = db.Column(db.DateTime, nullable=True)
    outcome = db.Column(db.String(24), nullable=True)  # code from utils.followups.OUTCOMES

    __table_args__ = (
        db.UniqueConstraint('plan_id', 'seq', name='uq_fstep_plan_seq'),
        db.CheckConstraint("status IN ('pending','done','missed','skipped')", name='ck_fstep_status'),
        db.Index('idx_fstep_status_due', 'status', 'due_date'),
    )
