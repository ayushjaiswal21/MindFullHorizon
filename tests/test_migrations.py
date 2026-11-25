"""Alembic migrations: upgrade/downgrade on a fresh SQLite DB, no drift from models.py, constraints really bite."""
import os
import sqlite3
import subprocess
import sys

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine

from core.extensions import db
from tests.conftest import ROOT


def flask_db(db_path, *args):
    env = dict(os.environ, DATABASE_URL="sqlite:///" + db_path.as_posix(), FLASK_APP="app.py", SKIP_CREATE_ALL="1")
    r = subprocess.run([sys.executable, "-m", "flask", "db", *args], cwd=ROOT, env=env, capture_output=True,
                       text=True, timeout=240)
    assert r.returncode == 0, r.stderr[-2000:]
    return r


def head_revision():
    from alembic.config import Config
    cfg = Config(os.path.join(ROOT, "migrations", "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(ROOT, "migrations"))
    return ScriptDirectory.from_config(cfg).get_current_head()


def connect(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@pytest.fixture(scope="module")
def migrated(tmp_path_factory):
    path = tmp_path_factory.mktemp("mig") / "head.db"
    flask_db(path, "upgrade")
    return path


def test_upgrade_reaches_head(migrated):
    conn = connect(migrated)
    assert conn.execute("SELECT version_num FROM alembic_version").fetchone()[0] == head_revision()
    conn.close()


def test_no_schema_drift_between_models_and_migrations(migrated, app):
    engine = create_engine("sqlite:///" + migrated.as_posix())
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn, opts={"compare_type": True}), db.metadata)
    engine.dispose()
    assert diff == [], diff


def test_downgrade_one_step_and_back(tmp_path):
    path = tmp_path / "down.db"
    flask_db(path, "upgrade")
    flask_db(path, "downgrade", "0002")  # undo every revision after 0002 (0003 to 0007)
    conn = connect(path)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "points_ledger" not in tables  # 0003 undone
    assert conn.execute("SELECT version_num FROM alembic_version").fetchone()[0] != head_revision()
    cols = {r[1] for r in conn.execute("PRAGMA table_info(appointments)")}
    assert "client_request_id" not in cols
    conn.close()
    flask_db(path, "upgrade")
    conn = connect(path)
    assert "points_ledger" in {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()


def seed_user(conn, n, role="patient"):
    conn.execute("INSERT INTO users (id, email, password_hash, name, role, institution) VALUES (?,?,?,?,?,?)",
                 (n, f"u{n}@t.l", "h", f"U{n}", role, "Test University"))


def test_partial_unique_index_blocks_double_booking(migrated):
    conn = connect(migrated)
    for n, role in ((1, "provider"), (2, "patient"), (3, "patient")):
        seed_user(conn, n, role)
    ins = ("INSERT INTO appointments (user_id, provider_id, date, time, appointment_type, status) "
           "VALUES (?, ?, '2030-01-01', '10:00', 'video', ?)")
    conn.execute(ins, (2, 1, "pending"))
    for status in ("pending", "accepted", "booked"):  # every live status collides
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(ins, (3, 1, status))
    conn.execute(ins, (3, 1, "rejected"))  # a dead row does not block
    conn.execute("UPDATE appointments SET status='cancelled' WHERE user_id=2")
    conn.execute(ins, (3, 1, "pending"))  # slot freed by the cancel
    null_slot = ("INSERT INTO appointments (user_id, provider_id, date, time, appointment_type, status) "
                 "VALUES (3, NULL, '2030-01-01', '11:00', 'video', 'pending')")
    conn.execute(null_slot)
    with pytest.raises(sqlite3.IntegrityError):  # same patient, same slot, no provider yet: a double submit
        conn.execute(null_slot)
    conn.rollback()
    conn.close()


def test_constraints_bite(migrated):
    conn = connect(migrated)
    seed_user(conn, 10)
    conn.execute("INSERT INTO medications (id, user_id, name) VALUES (1, 10, 'm')")
    bad = [
        "INSERT INTO mood_logs (user_id, mood_score) VALUES (10, 11)",
        "INSERT INTO mood_logs (user_id, mood_score) VALUES (10, 0)",
        "INSERT INTO breathing_exercise_logs (user_id, exercise_name, duration_minutes) VALUES (10, 'b', 181)",
        "INSERT INTO yoga_logs (user_id, session_name, duration_minutes, difficulty_level) VALUES (10, 'y', 0, 'x')",
        "INSERT INTO music_therapy_logs (user_id, mood, duration_minutes) VALUES (10, 'calm', 500)",
        "INSERT INTO goals (user_id, title, category, status, start_date) VALUES (10, 'g', 'c', 'bogus', '2030-01-01')",
        "INSERT INTO goals (user_id, title, category, priority, start_date) VALUES (10, 'g', 'c', 'urgent', '2030-01-01')",
        "INSERT INTO goals (user_id, title, category, target_value, start_date) VALUES (10, 'g', 'c', -1, '2030-01-01')",
        "INSERT INTO gamification (user_id, points, streak) VALUES (10, -5, 0)",
    ]
    for sql in bad:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(sql)
    conn.execute("INSERT INTO music_therapy_logs (user_id, mood) VALUES (10, 'calm')")  # NULL duration is fine
    # one medication log per medication per day
    conn.execute("INSERT INTO medication_logs (medication_id, user_id, log_date) VALUES (1, 10, '2030-01-01')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO medication_logs (medication_id, user_id, log_date) VALUES (1, 10, '2030-01-01')")
    # one detox log per user per day
    conn.execute("INSERT INTO digital_detox_logs (user_id, date, screen_time_hours) VALUES (10, '2030-01-01', 1)")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO digital_detox_logs (user_id, date, screen_time_hours) VALUES (10, '2030-01-01', 2)")
    # idempotency key unique per user, NULLs never collide
    key = "INSERT INTO mood_logs (user_id, mood_score, client_request_id) VALUES (10, 5, ?)"
    conn.execute(key, ("abcdefgh1",))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(key, ("abcdefgh1",))
    conn.execute(key, (None,))
    conn.execute(key, (None,))
    # points ledger: one award per (user, ref)
    pl = "INSERT INTO points_ledger (user_id, ref, activity_type, points, created_at) VALUES (10, 'r:1', 'yoga_session', 5, '2030-01-01')"
    conn.execute(pl)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(pl)
    conn.rollback()
    conn.close()


def test_upgrade_repairs_legacy_duplicates(tmp_path):
    """Rows that violate the new constraints (old double submits) must not make the upgrade fail."""
    path = tmp_path / "legacy.db"
    flask_db(path, "upgrade", "0002")
    conn = connect(path)
    for n, role in ((1, "provider"), (2, "patient"), (3, "patient")):
        seed_user(conn, n, role)
    conn.execute("INSERT INTO medications (id, user_id, name) VALUES (1, 2, 'm')")
    conn.executemany("INSERT INTO medication_logs (medication_id, user_id, taken_at) VALUES (1, 2, ?)",
                     [("2030-01-01 02:00:00",), ("2030-01-01 03:00:00",),   # same IST day (07:30, 08:30)
                      ("2030-01-01 20:00:00",)])                             # next IST day (01:30 on the 2nd)
    conn.executemany("INSERT INTO digital_detox_logs (user_id, date, screen_time_hours) VALUES (2, '2030-01-01', ?)",
                     [(1,), (2,)])
    ins = ("INSERT INTO appointments (user_id, provider_id, date, time, appointment_type, status) "
           "VALUES (?, 1, '2030-01-01', '10:00', 'video', 'pending')")
    conn.execute(ins, (2,))
    conn.execute(ins, (3,))  # double-booked slot
    conn.execute("INSERT INTO goals (user_id, title, category, status, priority, start_date) "
                 "VALUES (2, 'g', 'c', 'weird', 'urgent', '2030-01-01')")
    conn.execute("INSERT INTO breathing_exercise_logs (user_id, exercise_name, duration_minutes) VALUES (2, 'b', 9999)")
    conn.commit()
    conn.close()

    flask_db(path, "upgrade")

    conn = connect(path)
    assert conn.execute("SELECT COUNT(*) FROM medication_logs").fetchone()[0] == 2
    assert [r[0] for r in conn.execute("SELECT log_date FROM medication_logs ORDER BY id")] == ["2030-01-01", "2030-01-02"]
    assert conn.execute("SELECT COUNT(*) FROM digital_detox_logs").fetchone()[0] == 1
    assert [r[0] for r in conn.execute("SELECT status FROM appointments ORDER BY id")] == ["pending", "cancelled"]
    assert conn.execute("SELECT status, priority FROM goals").fetchone() == ("active", "medium")
    assert conn.execute("SELECT duration_minutes FROM breathing_exercise_logs").fetchone()[0] == 180
    conn.close()
