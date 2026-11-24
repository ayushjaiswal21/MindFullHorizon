"""idempotency keys, one-per-day and no-double-booking constraints, points ledger, value CHECKs

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-24

Data is repaired before each constraint is added (keep one row, never fail the upgrade on old duplicates):
duplicate live appointments for one slot become 'cancelled' (earliest id wins), duplicate detox logs and
medication logs for one day keep one row, out-of-range values are clamped.
"""
from alembic import op
import sqlalchemy as sa

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None

LIVE = "status IN ('pending','accepted','booked')"
LIVE_UNASSIGNED = LIVE + " AND provider_id IS NULL"
IST_OFFSET_SECONDS = 5 * 3600 + 30 * 60
# table -> unique index name for (user_id, client_request_id)
KEYED = {
    'assessments': 'uq_assessment_user_crid',
    'mood_logs': 'uq_mood_user_crid',
    'appointments': 'uq_appt_user_crid',
    'goals': 'uq_goal_user_crid',
    'journal_entries': 'uq_journal_user_crid',
    'breathing_exercise_logs': 'uq_breathing_user_crid',
    'yoga_logs': 'uq_yoga_user_crid',
    'music_therapy_logs': 'uq_music_user_crid',
}
DURATION_CHECKS = {
    'breathing_exercise_logs': 'ck_breathing_duration',
    'yoga_logs': 'ck_yoga_duration',
    'music_therapy_logs': 'ck_music_duration',
}


def _backfill_medication_log_date(bind):
    """log_date = IST calendar day of taken_at; then drop later duplicates of (medication_id, log_date)."""
    from datetime import timedelta
    t = sa.table('medication_logs', sa.column('id', sa.Integer), sa.column('medication_id', sa.Integer),
                 sa.column('taken_at', sa.DateTime), sa.column('log_date', sa.Date))
    seen, drop = set(), []
    for row in bind.execute(sa.select(t.c.id, t.c.medication_id, t.c.taken_at).order_by(t.c.id)):
        day = (row.taken_at + timedelta(seconds=IST_OFFSET_SECONDS)).date() if row.taken_at else None
        if day is None or (row.medication_id, day) in seen:
            drop.append(row.id)
            continue
        seen.add((row.medication_id, day))
        bind.execute(t.update().where(t.c.id == row.id).values(log_date=day))
    if drop:
        bind.execute(t.delete().where(t.c.id.in_(drop)))


def upgrade():
    bind = op.get_bind()

    op.create_table('points_ledger',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('ref', sa.String(length=80), nullable=False),
        sa.Column('activity_type', sa.String(length=30), nullable=False),
        sa.Column('points', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'ref', name='uq_points_user_ref'),
    )
    op.create_index('idx_points_user_activity_created', 'points_ledger', ['user_id', 'activity_type', 'created_at'])

    # --- idempotency keys: column + unique (user_id, client_request_id); NULL keys never collide
    for table, index in KEYED.items():
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(sa.Column('client_request_id', sa.String(length=64), nullable=True))
        op.create_index(index, table, ['user_id', 'client_request_id'], unique=True)

    # --- medication log: one per medication per IST day
    with op.batch_alter_table('medication_logs') as batch_op:
        batch_op.add_column(sa.Column('log_date', sa.Date(), nullable=True))
    _backfill_medication_log_date(bind)
    with op.batch_alter_table('medication_logs') as batch_op:
        batch_op.alter_column('log_date', existing_type=sa.Date(), nullable=False)
        batch_op.create_unique_constraint('uq_medlog_med_day', ['medication_id', 'log_date'])

    # --- digital detox: one log per user per day (index becomes unique)
    op.execute("DELETE FROM digital_detox_logs WHERE id NOT IN "
               "(SELECT MAX(id) FROM digital_detox_logs GROUP BY user_id, date)")
    op.drop_index('idx_detox_user_date', table_name='digital_detox_logs')
    op.create_index('idx_detox_user_date', 'digital_detox_logs', ['user_id', 'date'], unique=True)

    # --- appointments: no double booking of a live slot (partial unique indexes)
    for cols, extra in (('provider_id, date, time', ' AND provider_id IS NOT NULL'), ('user_id, date, time', ' AND provider_id IS NULL')):
        op.execute(f"UPDATE appointments SET status = 'cancelled' WHERE {LIVE}{extra} AND id NOT IN "
                   f"(SELECT MIN(id) FROM appointments WHERE {LIVE}{extra} GROUP BY {cols})")
    op.create_index('uq_appt_active_slot', 'appointments', ['provider_id', 'date', 'time'], unique=True,
                    sqlite_where=sa.text(LIVE), postgresql_where=sa.text(LIVE))
    op.create_index('uq_appt_active_user_slot', 'appointments', ['user_id', 'date', 'time'], unique=True,
                    sqlite_where=sa.text(LIVE_UNASSIGNED), postgresql_where=sa.text(LIVE_UNASSIGNED))

    # --- CHECK constraints (clamp old rows first)
    op.execute("UPDATE goals SET status = 'active' WHERE status IS NULL OR status NOT IN ('active','completed','paused')")
    op.execute("UPDATE goals SET priority = 'medium' WHERE priority IS NULL OR priority NOT IN ('low','medium','high')")
    op.execute("UPDATE goals SET target_value = NULL WHERE target_value < 0")
    op.execute("UPDATE goals SET current_value = 0 WHERE current_value < 0")
    with op.batch_alter_table('goals') as batch_op:
        batch_op.create_check_constraint('ck_goal_status', "status IN ('active','completed','paused')")
        batch_op.create_check_constraint('ck_goal_priority', "priority IN ('low','medium','high')")
        batch_op.create_check_constraint('ck_goal_values_nonneg', 'target_value >= 0 AND current_value >= 0')
    for table, name in DURATION_CHECKS.items():
        op.execute(f"UPDATE {table} SET duration_minutes = 180 WHERE duration_minutes > 180")
        op.execute(f"UPDATE {table} SET duration_minutes = 1 WHERE duration_minutes < 1")
        with op.batch_alter_table(table) as batch_op:
            batch_op.create_check_constraint(name, 'duration_minutes BETWEEN 1 AND 180')
    op.execute("UPDATE mood_logs SET mood_score = 10 WHERE mood_score > 10")
    op.execute("UPDATE mood_logs SET mood_score = 1 WHERE mood_score < 1")
    with op.batch_alter_table('mood_logs') as batch_op:
        batch_op.create_check_constraint('ck_mood_score', 'mood_score BETWEEN 1 AND 10')
    op.execute("UPDATE gamification SET points = 0 WHERE points < 0")
    op.execute("UPDATE gamification SET streak = 0 WHERE streak < 0")
    with op.batch_alter_table('gamification') as batch_op:
        batch_op.create_check_constraint('ck_gamification_nonneg', 'points >= 0 AND streak >= 0')

    # --- hot-path indexes
    op.create_index('idx_note_patient_session', 'clinical_notes', ['patient_id', 'session_date'])
    op.create_index('idx_notif_recipient_created', 'notifications', ['recipient_id', 'created_at'])


def downgrade():
    op.drop_index('idx_notif_recipient_created', table_name='notifications')
    op.drop_index('idx_note_patient_session', table_name='clinical_notes')

    with op.batch_alter_table('gamification') as batch_op:
        batch_op.drop_constraint('ck_gamification_nonneg', type_='check')
    with op.batch_alter_table('mood_logs') as batch_op:
        batch_op.drop_constraint('ck_mood_score', type_='check')
    for table, name in DURATION_CHECKS.items():
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_constraint(name, type_='check')
    with op.batch_alter_table('goals') as batch_op:
        batch_op.drop_constraint('ck_goal_values_nonneg', type_='check')
        batch_op.drop_constraint('ck_goal_priority', type_='check')
        batch_op.drop_constraint('ck_goal_status', type_='check')

    op.drop_index('uq_appt_active_user_slot', table_name='appointments')
    op.drop_index('uq_appt_active_slot', table_name='appointments')

    op.drop_index('idx_detox_user_date', table_name='digital_detox_logs')
    op.create_index('idx_detox_user_date', 'digital_detox_logs', ['user_id', 'date'], unique=False)

    with op.batch_alter_table('medication_logs') as batch_op:
        batch_op.drop_constraint('uq_medlog_med_day', type_='unique')
        batch_op.drop_column('log_date')

    for table, index in KEYED.items():
        op.drop_index(index, table_name=table)
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_column('client_request_id')

    op.drop_index('idx_points_user_activity_created', table_name='points_ledger')
    op.drop_table('points_ledger')
