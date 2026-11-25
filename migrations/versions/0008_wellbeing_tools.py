"""wellbeing tools: safety plan, sleep log, reminder preference

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-24

Three private per-student tables (FK CASCADE on users). No rows are inserted.
"""
from alembic import op
import sqlalchemy as sa

revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('safety_plans',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('warning_signs', sa.Text(), nullable=True),
        sa.Column('coping_alone', sa.Text(), nullable=True),
        sa.Column('places_people', sa.Text(), nullable=True),
        sa.Column('help_people', sa.JSON(), nullable=True),
        sa.Column('professionals', sa.Text(), nullable=True),
        sa.Column('safer_surroundings', sa.Text(), nullable=True),
        sa.Column('share_with_counsellors', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('client_request_id', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('uq_safety_plan_user', 'safety_plans', ['user_id'], unique=True)
    op.create_index('uq_safety_plan_user_crid', 'safety_plans', ['user_id', 'client_request_id'], unique=True)

    op.create_table('sleep_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('night_date', sa.Date(), nullable=False),
        sa.Column('bedtime', sa.String(length=5), nullable=False),
        sa.Column('wake_time', sa.String(length=5), nullable=False),
        sa.Column('duration_minutes', sa.Integer(), nullable=False),
        sa.Column('quality', sa.Integer(), nullable=False),
        sa.Column('note', sa.String(length=200), nullable=True),
        sa.Column('client_request_id', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint('quality BETWEEN 1 AND 5', name='ck_sleep_quality'),
        sa.CheckConstraint('duration_minutes BETWEEN 1 AND 1440', name='ck_sleep_duration'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('uq_sleep_user_night', 'sleep_logs', ['user_id', 'night_date'], unique=True)
    op.create_index('uq_sleep_user_crid', 'sleep_logs', ['user_id', 'client_request_id'], unique=True)

    op.create_table('reminder_prefs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('frequency', sa.String(length=6), nullable=False),
        sa.Column('hour_ist', sa.Integer(), nullable=False),
        sa.Column('weekday', sa.Integer(), server_default='0', nullable=False),
        sa.Column('status', sa.String(length=8), nullable=False),
        sa.Column('nonce', sa.String(length=16), nullable=False),
        sa.Column('confirmed_at', sa.DateTime(), nullable=True),
        sa.Column('last_sent_on', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint("frequency IN ('daily','weekly')", name='ck_reminder_frequency'),
        sa.CheckConstraint('hour_ist BETWEEN 0 AND 23', name='ck_reminder_hour'),
        sa.CheckConstraint('weekday BETWEEN 0 AND 6', name='ck_reminder_weekday'),
        sa.CheckConstraint("status IN ('pending','active')", name='ck_reminder_status'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('uq_reminder_user', 'reminder_prefs', ['user_id'], unique=True)


def downgrade():
    op.drop_table('reminder_prefs')
    op.drop_table('sleep_logs')
    op.drop_table('safety_plans')
