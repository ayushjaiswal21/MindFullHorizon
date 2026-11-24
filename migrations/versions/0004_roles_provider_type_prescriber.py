"""roles (admin), provider_type, prescriber profiles, appointment modality

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-24

users: role CHECK gains 'admin'; new provider_type, deactivated_at, is_pharmacy_desk; existing providers become
'counsellor'. New table prescriber_profiles. appointments: modality, consult_started_at.
Design: docs/CLINICAL_DESIGN.md 1.3, 2.1, 3.3. No clinical rows are inserted.

SQLite recreates the table for a CHECK change. With foreign keys ON, DROP TABLE users would cascade-delete every child
row, so foreign keys are switched off around the batch (they cannot be changed inside a transaction, so the open one
is committed first). PostgreSQL runs plain ALTER TABLE statements.
"""
from alembic import op
import sqlalchemy as sa

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None

ROLE_OLD = "role IN ('patient','provider')"
ROLE_NEW = "role IN ('patient','provider','admin')"
PROVIDER_TYPE = "provider_type IS NULL OR provider_type IN ('counsellor','doctor')"
MODALITY = "modality IS NULL OR modality IN ('video','in_person','audio','chat')"
LIVE = "status IN ('pending','accepted','booked')"
LIVE_UNASSIGNED = LIVE + " AND provider_id IS NULL"
LIVE_PROFILE = "status IN ('pending','verified','suspended')"


def _fk_pragma(bind, on):
    """SQLite only: switch foreign key enforcement. Commits first because the pragma is ignored inside a transaction."""
    if bind.dialect.name != 'sqlite':
        return
    bind.commit()
    bind.exec_driver_sql('PRAGMA foreign_keys=' + ('ON' if on else 'OFF'))


def _recreate_partial_indexes(bind):
    """A SQLite batch recreate may rebuild partial unique indexes as plain ones: put the originals back."""
    if bind.dialect.name != 'sqlite':
        return
    op.drop_index('uq_appt_active_slot', table_name='appointments')
    op.drop_index('uq_appt_active_user_slot', table_name='appointments')
    op.create_index('uq_appt_active_slot', 'appointments', ['provider_id', 'date', 'time'], unique=True,
                    sqlite_where=sa.text(LIVE))
    op.create_index('uq_appt_active_user_slot', 'appointments', ['user_id', 'date', 'time'], unique=True,
                    sqlite_where=sa.text(LIVE_UNASSIGNED))


def upgrade():
    bind = op.get_bind()

    _fk_pragma(bind, on=False)
    with op.batch_alter_table('users') as b:
        b.add_column(sa.Column('provider_type', sa.String(length=12), nullable=True))
        b.add_column(sa.Column('deactivated_at', sa.DateTime(), nullable=True))
        b.add_column(sa.Column('is_pharmacy_desk', sa.Boolean(), nullable=False, server_default=sa.false()))
        b.drop_constraint('ck_user_role', type_='check')
        b.create_check_constraint('ck_user_role', ROLE_NEW)
        b.create_check_constraint('ck_user_provider_type', PROVIDER_TYPE)
    _fk_pragma(bind, on=True)
    op.execute("UPDATE users SET provider_type = 'counsellor' WHERE role = 'provider'")

    op.create_table('prescriber_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('registration_number', sa.String(length=20), nullable=False),
        sa.Column('council', sa.String(length=100), nullable=False),
        sa.Column('council_key', sa.String(length=100), nullable=False),
        sa.Column('registered_since', sa.Integer(), nullable=False),
        sa.Column('specialisation', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=10), nullable=False),
        sa.Column('submitted_at', sa.DateTime(), nullable=False),
        sa.Column('verified_at', sa.DateTime(), nullable=True),
        sa.Column('verified_by', sa.Integer(), nullable=True),
        sa.Column('review_due_at', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.String(length=500), nullable=True),
        sa.Column('status_changed_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.CheckConstraint("status IN ('pending','verified','rejected','suspended')", name='ck_prescriber_status'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['verified_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id'),
    )
    op.create_index('idx_prescriber_status', 'prescriber_profiles', ['status'])
    op.create_index('uq_prescriber_reg_active', 'prescriber_profiles', ['registration_number', 'council_key'],
                    unique=True, sqlite_where=sa.text(LIVE_PROFILE), postgresql_where=sa.text(LIVE_PROFILE))

    with op.batch_alter_table('appointments') as b:
        b.add_column(sa.Column('modality', sa.String(length=10), nullable=True))
        b.add_column(sa.Column('consult_started_at', sa.DateTime(), nullable=True))
        b.create_check_constraint('ck_appt_modality', MODALITY)
    _recreate_partial_indexes(bind)


def downgrade():
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT COUNT(*) FROM users WHERE role = 'admin'")).scalar():
        raise RuntimeError("Refusing to downgrade 0004: admin accounts exist. Remove them first (development only).")
    with op.batch_alter_table('appointments') as b:
        b.drop_constraint('ck_appt_modality', type_='check')
        b.drop_column('consult_started_at')
        b.drop_column('modality')
    _recreate_partial_indexes(bind)

    op.drop_index('uq_prescriber_reg_active', table_name='prescriber_profiles')
    op.drop_index('idx_prescriber_status', table_name='prescriber_profiles')
    op.drop_table('prescriber_profiles')

    _fk_pragma(bind, on=False)
    with op.batch_alter_table('users') as b:
        b.drop_constraint('ck_user_provider_type', type_='check')
        b.drop_constraint('ck_user_role', type_='check')
        b.create_check_constraint('ck_user_role', ROLE_OLD)
        b.drop_column('is_pharmacy_desk')
        b.drop_column('deactivated_at')
        b.drop_column('provider_type')
    _fk_pragma(bind, on=True)
