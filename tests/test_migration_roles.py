"""Migrations 0004 to 0007: rows survive the role CHECK rebuild, legacy prescriptions, no seed data, downgrade."""
import sqlite3

import pytest

from tests.test_migrations import connect, flask_db


def _seed_old_schema(conn):
    conn.execute("INSERT INTO users (id, email, password_hash, name, role, institution) VALUES "
                 "(1,'p@t.l','h','P','patient','Test University'), (2,'v@t.l','h','V','provider','Test University')")
    conn.execute("INSERT INTO assessments (user_id, assessment_type, score) VALUES (1, 'PHQ-9', 4)")
    conn.execute("INSERT INTO appointments (user_id, provider_id, date, time, appointment_type, status) "
                 "VALUES (1, 2, '2030-01-01', '10:00', 'video', 'pending')")
    conn.execute("INSERT INTO prescriptions (provider_id, patient_id, medication_name, dosage) VALUES (2, 1, 'Old', '1')")
    conn.execute("INSERT INTO notifications (sender_id, recipient_id, type) VALUES (2, 1, 'message')")
    conn.commit()


def _counts(conn):
    tables = ('users', 'assessments', 'appointments', 'prescriptions', 'notifications')
    return {t: conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in tables}


@pytest.fixture(scope='module')
def upgraded(tmp_path_factory):
    path = tmp_path_factory.mktemp('roles') / 'old.db'
    flask_db(path, 'upgrade', '0003')
    conn = connect(path)
    _seed_old_schema(conn)
    before = _counts(conn)
    conn.close()
    flask_db(path, 'upgrade')
    return path, before


def test_migration_preserves_rows(upgraded):
    """The role CHECK rebuild must not cascade-delete children of users (foreign keys are off during the batch)."""
    path, before = upgraded
    conn = connect(path)
    assert _counts(conn) == before
    assert conn.execute("SELECT provider_type, is_pharmacy_desk FROM users WHERE id=2").fetchone() == ('counsellor', 0)
    assert conn.execute("SELECT provider_type FROM users WHERE id=1").fetchone()[0] is None
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    conn.close()


def test_legacy_prescription_row(upgraded):
    path, _ = upgraded
    conn = connect(path)
    assert conn.execute("SELECT status, medication_name, number FROM prescriptions").fetchone() == ('legacy', 'Old', None)
    conn.close()


def test_role_check_allows_admin_rejects_unknown(upgraded):
    path, _ = upgraded
    conn = connect(path)
    conn.execute("INSERT INTO users (email, password_hash, name, role) VALUES ('a@t.l','h','A','admin')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO users (email, password_hash, name, role) VALUES ('s@t.l','h','S','superuser')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO users (email, password_hash, name, role, provider_type) VALUES ('d@t.l','h','D','provider','nurse')")
    conn.rollback()
    conn.close()


def test_partial_indexes_survive_table_rebuild(upgraded):
    path, _ = upgraded
    conn = connect(path)
    for name in ('uq_appt_active_slot', 'uq_appt_active_user_slot', 'uq_prescriber_reg_active'):
        sql = conn.execute("SELECT sql FROM sqlite_master WHERE name=?", (name,)).fetchone()[0]
        assert ' WHERE ' in sql.upper(), name
    conn.close()


def test_provider_fk_is_restrict_and_tables_empty(upgraded):
    path, _ = upgraded
    conn = connect(path)
    with pytest.raises(sqlite3.IntegrityError):  # the doctor has a legacy prescription: hard delete is refused
        conn.execute("DELETE FROM users WHERE id=2")
    conn.rollback()
    for table in ('medicines', 'inventory_batches', 'inventory_transactions', 'reorder_rules', 'prescriber_profiles',
                  'prescription_items'):
        assert conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] == 0, table  # no seed data (design C-12)
    conn.close()


def test_downgrade_refused_with_admin_then_ok(tmp_path):
    path = tmp_path / 'down.db'
    flask_db(path, 'upgrade')
    conn = connect(path)
    conn.execute("INSERT INTO users (email, password_hash, name, role) VALUES ('a@t.l','h','A','admin')")
    conn.commit()
    conn.close()
    import os
    import subprocess
    import sys
    from tests.conftest import ROOT
    env = dict(os.environ, DATABASE_URL='sqlite:///' + path.as_posix(), FLASK_APP='app.py', SKIP_CREATE_ALL='1')
    r = subprocess.run([sys.executable, '-m', 'flask', 'db', 'downgrade', '0003'], cwd=ROOT, env=env,
                       capture_output=True, text=True, timeout=240)
    assert r.returncode != 0 and 'admin' in r.stderr
    conn = connect(path)
    conn.execute("DELETE FROM users WHERE role='admin'")
    conn.commit()
    conn.close()
    flask_db(path, 'downgrade', '0003')
    conn = connect(path)
    assert 'prescriber_profiles' not in {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert 'provider_type' not in {r[1] for r in conn.execute('PRAGMA table_info(users)')}
    conn.close()
    flask_db(path, 'upgrade')
