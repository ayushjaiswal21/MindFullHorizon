"""post-crisis follow-up tracker: followup_plans, followup_steps

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-24

One plan per acknowledged crisis event; steps hold due dates, a status and a fixed outcome code only (no free text).
No rows are inserted.
"""
from alembic import op
import sqlalchemy as sa

revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('followup_plans',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('crisis_event_id', sa.Integer(), nullable=False),
        sa.Column('patient_id', sa.Integer(), nullable=False),
        sa.Column('owner_provider_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=12), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        sa.Column('closed_reason', sa.String(length=20), nullable=True),
        sa.CheckConstraint("status IN ('open','completed','closed_early')", name='ck_fplan_status'),
        sa.ForeignKeyConstraint(['crisis_event_id'], ['crisis_events.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['patient_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['owner_provider_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('crisis_event_id'),
    )
    op.create_index('ix_followup_plans_patient_id', 'followup_plans', ['patient_id'])
    op.create_index('ix_followup_plans_owner_provider_id', 'followup_plans', ['owner_provider_id'])
    op.create_index('idx_fplan_status', 'followup_plans', ['status'])

    op.create_table('followup_steps',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('plan_id', sa.Integer(), nullable=False),
        sa.Column('seq', sa.Integer(), nullable=False),
        sa.Column('due_date', sa.Date(), nullable=False),
        sa.Column('status', sa.String(length=8), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('outcome', sa.String(length=24), nullable=True),
        sa.CheckConstraint("status IN ('pending','done','missed','skipped')", name='ck_fstep_status'),
        sa.ForeignKeyConstraint(['plan_id'], ['followup_plans.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('plan_id', 'seq', name='uq_fstep_plan_seq'),
    )
    op.create_index('idx_fstep_status_due', 'followup_steps', ['status', 'due_date'])


def downgrade():
    op.drop_table('followup_steps')  # drops its index with it
    op.drop_table('followup_plans')
