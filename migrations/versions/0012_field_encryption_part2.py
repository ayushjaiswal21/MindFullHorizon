"""O-04b: encrypt the remaining plaintext clinical free text at rest

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-26

Same pattern as 0011 (utils/field_encryption.py: `EncryptedText`, Fernet). Covers the fields left plaintext
by O-04/D-19: `Appointment.notes`/`rejection_reason`, `Prescription.diagnosis`/`allergies`/`current_meds`
and `Notification.message`. All are genuinely free text (not structured, no `LIKE`/`ILIKE`/full-text
search on any of them anywhere in the codebase - checked same as the O-04 pass).

Requires `FIELD_ENCRYPTION_KEY` to be set before running (same key `utils/field_encryption.py` uses
afterwards) - the upgrade fails fast if it is missing, before any schema change (see 0011's note on why
checking the key first matters: checking it after retyping columns can leave the DB half-migrated).

SQLite: `op.batch_alter_table` recreates the table (render_as_batch=True in migrations/env.py). PostgreSQL
cannot implicitly cast TEXT to BYTEA, so `postgresql_using='NULL'` clears the column during the type
change and step 3 refills it - verified against a real PostgreSQL 18 database 2026-11-25 (O-11), same as 0011.
"""
import json
import os

import sqlalchemy as sa
from alembic import op
from cryptography.fernet import Fernet

revision = '0012'
down_revision = '0011'
branch_labels = None
depends_on = None

# (table, column, is_json, existing_type) - existing_type must match the column as it stood before this migration.
_FIELDS = [
    ('appointments', 'notes', False, sa.Text()),
    ('appointments', 'rejection_reason', False, sa.Text()),
    ('prescriptions', 'diagnosis', False, sa.String(length=120)),
    ('prescriptions', 'allergies', False, sa.String(length=300)),
    ('prescriptions', 'current_meds', False, sa.String(length=300)),
    ('notifications', 'message', False, sa.Text()),
]


def _cipher():
    key = os.environ.get('FIELD_ENCRYPTION_KEY')
    if not key:
        raise RuntimeError(
            "FIELD_ENCRYPTION_KEY must be set before running this migration (the same key the app will "
            "use afterwards; see utils/field_encryption.py and .env.example)."
        )
    return Fernet(key.encode('utf-8') if isinstance(key, str) else key)


def _read_existing():
    """Read every current value of every affected column, before its type changes."""
    bind = op.get_bind()
    rows = {}
    for table_name, col_name, _is_json, _existing_type in _FIELDS:
        tbl = sa.table(table_name, sa.column('id'), sa.column(col_name))
        col = getattr(tbl.c, col_name)
        result = bind.execute(sa.select(tbl.c.id, col).where(col.isnot(None)))
        rows[(table_name, col_name)] = result.fetchall()
    return rows


def _retype_columns(to_binary):
    for table_name, col_name, _is_json, existing_type in _FIELDS:
        src_type = existing_type if to_binary else sa.LargeBinary()
        dst_type = sa.LargeBinary() if to_binary else existing_type
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.alter_column(col_name, existing_type=src_type, type_=dst_type,
                                   existing_nullable=True, postgresql_using='NULL')


def upgrade():
    # Check the key BEFORE any schema change (see module docstring and 0011's own note - a missing key
    # caught after _retype_columns leaves the DB half-migrated).
    cipher = _cipher()
    rows = _read_existing()
    _retype_columns(to_binary=True)

    bind = op.get_bind()
    for table_name, col_name, is_json, _existing_type in _FIELDS:
        tbl = sa.table(table_name, sa.column('id'), sa.column(col_name))
        for row_id, value in rows[(table_name, col_name)]:
            if value is None:
                continue
            plain = json.dumps(value) if is_json else value
            ciphertext = cipher.encrypt(plain.encode('utf-8'))
            bind.execute(tbl.update().where(tbl.c.id == row_id).values(**{col_name: ciphertext}))


def downgrade():
    """Decrypt back to plaintext columns. Needs the FIELD_ENCRYPTION_KEY that encrypted the data."""
    rows = _read_existing()
    cipher = _cipher()
    decrypted = {}
    for key, pairs in rows.items():
        _table_name, col_name = key
        is_json = next(f[2] for f in _FIELDS if f[0] == key[0] and f[1] == col_name)
        out = []
        for row_id, ciphertext in pairs:
            if ciphertext is None:
                continue
            plain = cipher.decrypt(bytes(ciphertext)).decode('utf-8')
            out.append((row_id, json.loads(plain) if is_json else plain))
        decrypted[key] = out

    _retype_columns(to_binary=False)

    bind = op.get_bind()
    for table_name, col_name, _is_json, _existing_type in _FIELDS:
        tbl = sa.table(table_name, sa.column('id'), sa.column(col_name))
        for row_id, value in decrypted[(table_name, col_name)]:
            bind.execute(tbl.update().where(tbl.c.id == row_id).values(**{col_name: value}))
