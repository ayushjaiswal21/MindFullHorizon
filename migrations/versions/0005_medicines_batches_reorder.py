"""medicine catalogue, inventory batches, reorder rules

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-24

Three new tables. NO rows are inserted: the catalogue is empty until an administrator adds medicines
(design C-12; tests/test_inventory_csv.py checks it).
"""
from alembic import op
import sqlalchemy as sa

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('medicines',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('generic_name', sa.String(length=120), nullable=False),
        sa.Column('generic_key', sa.String(length=120), nullable=False),
        sa.Column('brand_name', sa.String(length=120), nullable=False),
        sa.Column('strength', sa.String(length=40), nullable=False),
        sa.Column('form', sa.String(length=30), nullable=False),
        sa.Column('route', sa.String(length=20), nullable=False),
        sa.Column('tpg_list', sa.String(length=1), nullable=False),
        sa.Column('schedule', sa.String(length=8), nullable=False),
        sa.Column('is_controlled', sa.Boolean(), nullable=False),
        sa.Column('therapeutic_class', sa.String(length=60), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('is_demo', sa.Boolean(), nullable=False),
        sa.Column('list_verified_at', sa.DateTime(), nullable=True),
        sa.Column('list_verified_by', sa.Integer(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.CheckConstraint("tpg_list IN ('O','A','B','C')", name='ck_med_list'),
        sa.CheckConstraint("schedule IN ('none','H','H1','X','NDPS')", name='ck_med_schedule'),
        sa.CheckConstraint("schedule NOT IN ('X','NDPS') OR is_controlled", name='ck_med_controlled'),
        sa.ForeignKeyConstraint(['list_verified_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('generic_key', 'brand_name', 'strength', 'form', name='uq_medicine_identity'),
    )

    op.create_table('inventory_batches',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('institution_key', sa.String(length=100), nullable=False),
        sa.Column('medicine_id', sa.Integer(), nullable=False),
        sa.Column('batch_no', sa.String(length=40), nullable=False),
        sa.Column('expiry_date', sa.Date(), nullable=False),
        sa.Column('quantity_on_hand', sa.Integer(), nullable=False),
        sa.Column('unit_cost', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('supplier', sa.String(length=120), nullable=True),
        sa.Column('status', sa.String(length=12), nullable=False),
        sa.Column('received_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.CheckConstraint('quantity_on_hand >= 0', name='ck_batch_qty'),
        sa.CheckConstraint("status IN ('active','quarantined','closed')", name='ck_batch_status'),
        sa.ForeignKeyConstraint(['medicine_id'], ['medicines.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('institution_key', 'medicine_id', 'batch_no', 'expiry_date', name='uq_batch_identity'),
    )
    op.create_index('idx_batch_fefo', 'inventory_batches', ['institution_key', 'medicine_id', 'status', 'expiry_date'])

    op.create_table('reorder_rules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('institution_key', sa.String(length=100), nullable=False),
        sa.Column('medicine_id', sa.Integer(), nullable=False),
        sa.Column('reorder_level', sa.Integer(), nullable=False),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.CheckConstraint('reorder_level >= 0', name='ck_reorder_level'),
        sa.ForeignKeyConstraint(['medicine_id'], ['medicines.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('institution_key', 'medicine_id', name='uq_reorder_inst_medicine'),
    )


def downgrade():
    op.drop_table('reorder_rules')
    op.drop_index('idx_batch_fefo', table_name='inventory_batches')
    op.drop_table('inventory_batches')
    op.drop_table('medicines')
