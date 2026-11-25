"""O-04: encrypt clinical free text at rest

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-25

Changes the columns listed in `_FIELDS` from plain TEXT/VARCHAR/JSON to a binary ciphertext column
(utils/field_encryption.py: `EncryptedText`/`EncryptedJSON`, Fernet). This is a genuine data migration,
not just a schema change: any plaintext already in these columns is read, encrypted and written back,
not merely retyped.

Requires `FIELD_ENCRYPTION_KEY` to be set in the environment before running (same key
`utils/field_encryption.py` uses afterwards) — the upgrade fails fast if it is missing rather than
silently leaving rows unencrypted.

SQLite: `op.batch_alter_table` recreates the table (render_as_batch=True in migrations/env.py); the
recreate copies the old text as-is (SQLite columns are dynamically typed) and step 3 below then
overwrites every row with ciphertext in the same migration. PostgreSQL cannot implicitly cast
TEXT/JSON to BYTEA, so `postgresql_using='NULL'` clears the column during the type change and step 3
refills it from the plaintext captured in step 1 — only tested against SQLite here (same gap as O-11;
nothing in this migration is SQLite-specific, but the PostgreSQL path has not been run).
"""
import json
import os

import sqlalchemy as sa
from alembic import op
from cryptography.fernet import Fernet

revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None

# (table, column, is_json, existing_type) - existing_type must match the column as it stood before this migration.
_FIELDS = [
    ('clinical_notes', 'transcript', False, sa.Text()),
    ('clinical_notes', 'ai_generated_note', False, sa.Text()),
    ('clinical_notes', 'provider_notes', False, sa.Text()),
    ('journal_entries', 'title', False, sa.String(length=100)),
    ('journal_entries', 'content', False, sa.Text()),
    ('journal_entries', 'ai_suggestions', False, sa.Text()),
    ('mood_logs', 'notes', False, sa.Text()),
    ('assessments', 'responses', True, sa.JSON()),
    ('assessments', 'contextual_responses', True, sa.JSON()),
    ('assessments', 'ai_insights', False, sa.Text()),
    ('voice_logs', 'transcript', False, sa.Text()),
    ('voice_logs', 'ai_analysis', False, sa.Text()),
    ('safety_plans', 'warning_signs', False, sa.Text()),
    ('safety_plans', 'coping_alone', False, sa.Text()),
    ('safety_plans', 'places_people', False, sa.Text()),
    ('safety_plans', 'professionals', False, sa.Text()),
    ('safety_plans', 'safer_surroundings', False, sa.Text()),
    ('safety_plans', 'help_people', True, sa.JSON()),
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
    # Check the key BEFORE any schema change: calling this after _retype_columns (as an earlier version of
    # this migration did) meant a missing key left the DB in an inconsistent half-migrated state (columns
    # already retyped to binary but not yet encrypted) and, on SQLite, a dangling _alembic_tmp_* table from
    # the batch_alter_table that never got to rename itself back, which then broke every retry with "table
    # already exists" instead of the real "key missing" error. Fail here instead: zero schema change yet.
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
