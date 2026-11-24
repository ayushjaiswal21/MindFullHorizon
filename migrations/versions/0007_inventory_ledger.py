"""inventory ledger (append-only)

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-24

inventory_transactions references inventory_batches (0005) and prescription_items (0006). No rows are inserted.
"""
from alembic import op
import sqlalchemy as sa

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None

SIGN = ("(kind IN ('receive','return') AND delta > 0) OR (kind IN ('dispense','expire') AND delta < 0) "
        "OR (kind = 'adjust' AND delta <> 0)")
REASONS = ("'purchase','donation','transfer_in','opening_stock','dispense','dispense_reversed',"
           "'count_correction','damaged','lost','recalled','expired_writeoff'")


def upgrade():
    op.create_table('inventory_transactions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('batch_id', sa.Integer(), nullable=False),
        sa.Column('delta', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(length=10), nullable=False),
        sa.Column('prescription_item_id', sa.Integer(), nullable=True),
        sa.Column('rx_number', sa.String(length=24), nullable=True),
        sa.Column('actor_id', sa.Integer(), nullable=True),
        sa.Column('reason_code', sa.String(length=24), nullable=False),
        sa.Column('group_ref', sa.String(length=36), nullable=True),
        sa.Column('reverses_id', sa.Integer(), nullable=True),
        sa.Column('dispenser_label', sa.String(length=140), nullable=True),
        sa.Column('idempotency_key', sa.String(length=80), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint("kind IN ('receive','dispense','adjust','expire','return')", name='ck_invtx_kind'),
        sa.CheckConstraint(SIGN, name='ck_invtx_sign'),
        sa.CheckConstraint(f'reason_code IN ({REASONS})', name='ck_invtx_reason'),
        sa.ForeignKeyConstraint(['batch_id'], ['inventory_batches.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['prescription_item_id'], ['prescription_items.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['reverses_id'], ['inventory_transactions.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_inventory_transactions_batch_id', 'inventory_transactions', ['batch_id'])
    op.create_index('ix_inventory_transactions_group_ref', 'inventory_transactions', ['group_ref'])
    op.create_index('ix_inventory_transactions_created_at', 'inventory_transactions', ['created_at'])
    op.create_index('uq_invtx_idem', 'inventory_transactions', ['idempotency_key'], unique=True)
    op.create_index('uq_invtx_reverses', 'inventory_transactions', ['reverses_id'], unique=True)


def downgrade():
    op.drop_table('inventory_transactions')  # drops its indexes with it
