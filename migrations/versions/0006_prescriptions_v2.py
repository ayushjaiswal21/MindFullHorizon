"""prescriptions v2: lifecycle columns, items table, RESTRICT on the doctor

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-24

Existing prescription rows (the old open form) become status 'legacy' and stay read-only. The legacy columns
medication_name and dosage become nullable. provider_id changes from ON DELETE CASCADE to RESTRICT so a doctor with
prescriptions cannot be hard-deleted. New table prescription_items. Design: docs/CLINICAL_DESIGN.md 3.1, 11.
"""
from alembic import op
import sqlalchemy as sa

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None

THREE = "('none_reported','listed','unknown')"
FK_CONVENTION = {'fk': 'fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s'}  # names SQLite's unnamed FKs
NEW_COLUMNS = ('number', 'status', 'institution_key', 'institution_name', 'doctor_name', 'doctor_reg_no',
               'doctor_council', 'doctor_specialisation', 'patient_name', 'consult_appointment_id', 'tpg_context',
               'same_condition_attested', 'diagnosis', 'allergies_status', 'allergies', 'current_meds_status',
               'current_meds', 'warnings_ack', 'consent_version', 'amends_id', 'cancelled_at', 'cancelled_by',
               'cancel_reason', 'dispense_requested_at', 'client_request_id', 'issue_request_id', 'expiry_days',
               'row_version', 'created_at', 'updated_at')


def _fk_pragma(bind, on):
    """SQLite only: foreign key enforcement off while a table is recreated (see 0004)."""
    if bind.dialect.name == 'sqlite':
        bind.commit()
        bind.exec_driver_sql('PRAGMA foreign_keys=' + ('ON' if on else 'OFF'))


def _provider_fk_name(bind):
    for fk in sa.inspect(bind).get_foreign_keys('prescriptions'):
        if fk['constrained_columns'] == ['provider_id']:
            return fk['name'] or 'fk_prescriptions_provider_id_users'
    raise RuntimeError('prescriptions.provider_id foreign key not found')


def _set_provider_fk(bind, ondelete):
    name = _provider_fk_name(bind)
    with op.batch_alter_table('prescriptions', naming_convention=FK_CONVENTION) as b:
        b.drop_constraint(name, type_='foreignkey')
        b.create_foreign_key('fk_prescriptions_provider_id_users', 'users', ['provider_id'], ['id'], ondelete=ondelete)


def upgrade():
    bind = op.get_bind()
    _fk_pragma(bind, on=False)
    with op.batch_alter_table('prescriptions') as b:
        b.add_column(sa.Column('number', sa.String(length=24), nullable=True))
        b.add_column(sa.Column('status', sa.String(length=20), nullable=True))  # NOT NULL once old rows are 'legacy'
        for name, size in (('institution_key', 100), ('institution_name', 100), ('doctor_name', 100),
                           ('doctor_reg_no', 20), ('doctor_council', 100), ('doctor_specialisation', 100),
                           ('patient_name', 100), ('diagnosis', 120), ('allergies', 300), ('current_meds', 300),
                           ('consent_version', 20), ('client_request_id', 64), ('issue_request_id', 64)):
            b.add_column(sa.Column(name, sa.String(length=size), nullable=True))
        b.add_column(sa.Column('tpg_context', sa.String(length=10), nullable=True))
        b.add_column(sa.Column('allergies_status', sa.String(length=12), nullable=True))
        b.add_column(sa.Column('current_meds_status', sa.String(length=12), nullable=True))
        b.add_column(sa.Column('cancel_reason', sa.String(length=20), nullable=True))
        b.add_column(sa.Column('same_condition_attested', sa.Boolean(), nullable=False, server_default=sa.false()))
        b.add_column(sa.Column('warnings_ack', sa.JSON(), nullable=True))
        b.add_column(sa.Column('expiry_days', sa.Integer(), nullable=True))
        b.add_column(sa.Column('row_version', sa.Integer(), nullable=False, server_default='1'))
        for name in ('cancelled_at', 'dispense_requested_at', 'created_at', 'updated_at'):
            b.add_column(sa.Column(name, sa.DateTime(), nullable=True))
        b.add_column(sa.Column('consult_appointment_id', sa.Integer(),
                               sa.ForeignKey('appointments.id', ondelete='SET NULL', name='fk_rx_consult_appointment'),
                               nullable=True))
        b.add_column(sa.Column('amends_id', sa.Integer(), sa.ForeignKey('prescriptions.id', ondelete='SET NULL', name='fk_rx_amends'),
                               nullable=True))
        b.add_column(sa.Column('cancelled_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL', name='fk_rx_cancelled_by'),
                               nullable=True))

    op.execute("UPDATE prescriptions SET status = 'legacy', created_at = issue_date, updated_at = issue_date")

    with op.batch_alter_table('prescriptions') as b:
        b.alter_column('status', existing_type=sa.String(length=20), nullable=False)
        b.alter_column('medication_name', existing_type=sa.String(length=200), nullable=True)
        b.alter_column('dosage', existing_type=sa.String(length=100), nullable=True)
        b.create_check_constraint('ck_rx_status', "status IN ('draft','issued','partially_dispensed','dispensed',"
                                                  "'cancelled','expired','legacy')")
        b.create_check_constraint('ck_rx_allergies', f'allergies_status IS NULL OR allergies_status IN {THREE}')
        b.create_check_constraint('ck_rx_current_meds', f'current_meds_status IS NULL OR current_meds_status IN {THREE}')
        b.create_check_constraint('ck_rx_cancel_reason', "cancel_reason IS NULL OR cancel_reason IN "
                                  "('error','patient_request','clinical_change','amended','system')")
    _set_provider_fk(bind, 'RESTRICT')
    _fk_pragma(bind, on=True)

    op.create_index('uq_rx_number', 'prescriptions', ['number'], unique=True)
    op.create_index('idx_rx_provider_status', 'prescriptions', ['provider_id', 'status'])
    op.create_index('idx_rx_patient_status', 'prescriptions', ['patient_id', 'status'])
    op.create_index('idx_rx_inst_status_req', 'prescriptions', ['institution_key', 'status', 'dispense_requested_at'])
    op.create_index('uq_rx_provider_crid', 'prescriptions', ['provider_id', 'client_request_id'], unique=True)
    op.create_index('uq_rx_provider_issue_rid', 'prescriptions', ['provider_id', 'issue_request_id'], unique=True)

    op.create_table('prescription_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('prescription_id', sa.Integer(), nullable=False),
        sa.Column('line_no', sa.Integer(), nullable=False),
        sa.Column('medicine_id', sa.Integer(), nullable=False),
        sa.Column('medicine_label', sa.String(length=200), nullable=True),
        sa.Column('tpg_list', sa.String(length=1), nullable=True),
        sa.Column('dose_text', sa.String(length=60), nullable=False),
        sa.Column('frequency', sa.String(length=60), nullable=False),
        sa.Column('duration_days', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('quantity_dispensed', sa.Integer(), nullable=False),
        sa.Column('instructions', sa.String(length=200), nullable=True),
        sa.CheckConstraint('duration_days BETWEEN 1 AND 90', name='ck_rxi_duration'),
        sa.CheckConstraint('quantity BETWEEN 1 AND 500', name='ck_rxi_qty'),
        sa.CheckConstraint('quantity_dispensed >= 0 AND quantity_dispensed <= quantity', name='ck_rxi_dispensed'),
        sa.ForeignKeyConstraint(['prescription_id'], ['prescriptions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['medicine_id'], ['medicines.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('prescription_id', 'line_no', name='uq_rxi_line'),
        sa.UniqueConstraint('prescription_id', 'medicine_id', name='uq_rxi_medicine'),
    )


def downgrade():
    """Development only: new-style prescriptions cannot be represented in the old table, so they are deleted."""
    bind = op.get_bind()
    op.drop_table('prescription_items')
    op.execute("DELETE FROM prescriptions WHERE status <> 'legacy'")
    for name in ('uq_rx_provider_issue_rid', 'uq_rx_provider_crid', 'idx_rx_inst_status_req', 'idx_rx_patient_status',
                 'idx_rx_provider_status', 'uq_rx_number'):
        op.drop_index(name, table_name='prescriptions')
    op.execute("UPDATE prescriptions SET medication_name = COALESCE(medication_name, ''), dosage = COALESCE(dosage, '')")
    _fk_pragma(bind, on=False)
    _set_provider_fk(bind, 'CASCADE')
    with op.batch_alter_table('prescriptions') as b:
        for name in ('ck_rx_cancel_reason', 'ck_rx_current_meds', 'ck_rx_allergies', 'ck_rx_status'):
            b.drop_constraint(name, type_='check')
        b.alter_column('medication_name', existing_type=sa.String(length=200), nullable=False)
        b.alter_column('dosage', existing_type=sa.String(length=100), nullable=False)
        for name in reversed(NEW_COLUMNS):
            b.drop_column(name)
    _fk_pragma(bind, on=True)
