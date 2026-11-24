"""Database layer: schema, cascades, institutional summary, migrations."""
import os
import subprocess
import sys
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

import models as m
from extensions import db
from tests.conftest import PASSWORD, ROOT


def _user(role, email, institution="Alpha University"):
    u = m.User(email=email, name=email.split("@")[0], role=role, institution=institution)
    u.set_password(PASSWORD)
    db.session.add(u)
    db.session.flush()
    return u


def test_new_models_roundtrip(app):
    with app.app_context():
        u = _user("patient", "p@t.local")
        db.session.add_all([
            m.CrisisEvent(user_id=u.id, source="chat", severity=3, reason="keyword"),
            m.JournalEntry(user_id=u.id, title="t", content="c", sentiment="Neutral"),
            m.VoiceLog(user_id=u.id, filename="a.wav", transcript=None, emotion="calm"),
        ])
        db.session.commit()
        assert m.CrisisEvent.query.one().acknowledged_at is None
        assert m.JournalEntry.query.one().created_at is not None
        assert m.VoiceLog.query.one().emotion == "calm"


def test_check_constraints(app):
    with app.app_context():
        _user("patient", "p@t.local")
        db.session.commit()
        db.session.add(m.User(email="x@t.local", name="x", role="superuser", password_hash="h"))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()
        db.session.add(m.User(email="a@t.local", name="a", role="admin", password_hash="h"))
        db.session.commit()  # 'admin' is a valid role since design C-01
        with pytest.raises(IntegrityError):  # NULL role (the column default only fills omitted values)
            db.session.execute(text("INSERT INTO users (email, name, role, password_hash) VALUES ('y@t.local','y',NULL,'h')"))
        db.session.rollback()
        p = m.User.query.filter_by(role="patient").one()
        db.session.add(m.Appointment(user_id=p.id, date=date.today(), time="10:00", appointment_type="x", status="bogus"))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def _fill_children(patient, provider):
    """One row in every table that references a user."""
    pid, vid, today = patient.id, provider.id, date.today()
    med = m.Medication(user_id=pid, name="med")
    post = m.BlogPost(title="t", content="c", author_id=pid)
    other_post = m.BlogPost(title="t2", content="c", author_id=vid)
    db.session.add_all([med, post, other_post])
    db.session.flush()
    parent = m.BlogComment(user_id=pid, post_id=other_post.id, content="c")
    db.session.add(parent)
    db.session.flush()
    db.session.add_all([
        m.Assessment(user_id=pid, assessment_type="PHQ-9", score=3),
        m.DigitalDetoxLog(user_id=pid, date=today, screen_time_hours=2),
        m.RPMData(user_id=pid, date=today),
        m.Gamification(user_id=pid),
        m.MedicationLog(medication_id=med.id, user_id=pid),
        m.BreathingExerciseLog(user_id=pid, exercise_name="b", duration_minutes=1),
        m.YogaLog(user_id=pid, session_name="y", duration_minutes=1),
        m.MusicTherapyLog(user_id=pid, mood="calm"),
        m.ProgressRecommendation(user_id=pid, recommendations={}),
        m.ClinicalNote(provider_id=vid, patient_id=pid, session_date=datetime.utcnow()),
        m.Prescription(provider_id=vid, patient_id=pid, medication_name="m", dosage="1", status="legacy"),
        m.Appointment(user_id=pid, provider_id=vid, date=today, time="10:00", appointment_type="x"),
        m.Goal(user_id=pid, title="g", category="c", start_date=today),
        m.MoodLog(user_id=pid, mood_score=5),
        m.Notification(sender_id=vid, recipient_id=pid),
        m.Notification(sender_id=pid, recipient_id=vid),
        m.BlogLike(user_id=pid, post_id=other_post.id),
        m.BlogComment(user_id=vid, post_id=post.id, content="reply"),
        m.BlogComment(user_id=pid, post_id=other_post.id, parent_id=parent.id, content="reply"),
        m.CrisisEvent(user_id=pid, source="phq9", severity=2, reason="item9", acknowledged_by=vid),
        m.JournalEntry(user_id=pid, title="t", content="c"),
        m.VoiceLog(user_id=pid, filename="a.wav"),
    ])
    db.session.commit()


def _orphans():
    """Rows whose FK to users points at a missing user (also catches PRAGMA foreign_keys being off)."""
    found = {}
    for table in db.metadata.sorted_tables:
        for fk in table.foreign_keys:
            if fk.column.table.name == "users":
                n = db.session.execute(text(
                    f"SELECT COUNT(*) FROM {table.name} WHERE {fk.parent.name} IS NOT NULL "
                    f"AND {fk.parent.name} NOT IN (SELECT id FROM users)")).scalar()
                if n:
                    found[f"{table.name}.{fk.parent.name}"] = n
    return found


@pytest.mark.parametrize("victim", ["patient", "provider"])
def test_delete_user_leaves_no_orphans(app, victim):
    with app.app_context():
        patient, provider = _user("patient", "p@t.local"), _user("provider", "v@t.local")
        _fill_children(patient, provider)
        if victim == "provider":  # a doctor with prescriptions cannot be hard-deleted (ON DELETE RESTRICT, design 3.9)
            db.session.delete(provider)
            with pytest.raises(IntegrityError):
                db.session.commit()
            db.session.rollback()
            m.Prescription.query.delete()
            db.session.commit()
            provider = db.session.get(m.User, provider.id)
        db.session.delete(patient if victim == "patient" else provider)
        db.session.commit()
        assert _orphans() == {}
        if victim == "provider":  # patient's own data survives; appointment keeps existing without a provider
            assert m.Appointment.query.one().provider_id is None
            assert m.Notification.query.filter_by(sender_id=None).count() == 1
        else:
            assert m.Assessment.query.count() == 0 and m.JournalEntry.query.count() == 0


def test_delete_user_via_raw_sql_cascades(app):
    """DB-level cascade (PRAGMA foreign_keys=ON), independent of the ORM."""
    with app.app_context():
        patient, provider = _user("patient", "p@t.local"), _user("provider", "v@t.local")
        _fill_children(patient, provider)
        db.session.execute(text("DELETE FROM users WHERE id = :i"), {"i": patient.id})
        db.session.commit()
        assert _orphans() == {}


def test_hot_indexes_exist(app):
    with app.app_context():
        insp = inspect(db.engine)

        def cols(table):
            return [tuple(i["column_names"]) for i in insp.get_indexes(table)]

        assert ("user_id", "date") in cols("rpm_data")
        assert ("provider_id", "date", "time") in cols("appointments")
        assert ("user_id", "taken_at") in cols("medication_logs")
        assert ("user_id", "created_at") in cols("yoga_logs")
        assert ("user_id", "created_at") in cols("breathing_exercise_logs")
        assert any(u["column_names"] == ["user_id"] for u in insp.get_unique_constraints("gamification")) or \
            any(i["unique"] and i["column_names"] == ["user_id"] for i in insp.get_indexes("gamification"))


# --- institutional summary -------------------------------------------------

def _seed_two_institutions():
    a1 = _user("patient", "a1@t.local", "Alpha University")
    a2 = _user("patient", "a2@t.local", "  alpha UNIVERSITY ")  # same institution, messy spelling
    a3 = _user("patient", "a3@t.local", "Alpha University")  # inactive
    b1 = _user("patient", "b1@t.local", "Beta University")
    ap = _user("provider", "ap@t.local", "Alpha University")  # providers are not counted
    near = _user("patient", "n@t.local", "Alpha University of Arts")  # keyword overlap must NOT match
    today = date.today()
    db.session.add_all([
        m.DigitalDetoxLog(user_id=a1.id, date=today, screen_time_hours=10),
        m.DigitalDetoxLog(user_id=a2.id, date=today, screen_time_hours=4),
        m.Assessment(user_id=a1.id, assessment_type="PHQ-9", score=0),   # wellness 10
        m.Assessment(user_id=a2.id, assessment_type="GAD-7", score=21),  # wellness 0
        m.Assessment(user_id=a1.id, assessment_type="PHQ-9", score=9, created_at=datetime.utcnow() - timedelta(days=90)),
        m.DigitalDetoxLog(user_id=b1.id, date=today, screen_time_hours=12),
        m.YogaLog(user_id=near.id, session_name="y", duration_minutes=5),
        m.Appointment(user_id=a1.id, provider_id=ap.id, date=today, time="9:00", appointment_type="x", status="completed"),
        m.Appointment(user_id=a2.id, provider_id=ap.id, date=today, time="10:00", appointment_type="x", status="completed"),
        m.Appointment(user_id=a2.id, provider_id=ap.id, date=today, time="11:00", appointment_type="x", status="cancelled"),
        m.Appointment(user_id=b1.id, provider_id=ap.id, date=today, time="12:00", appointment_type="x", status="cancelled"),
    ])
    db.session.commit()
    return a3


def test_institutional_summary_scoped_and_computed(app):
    with app.app_context():
        _seed_two_institutions()
        r = m.get_institutional_summary("alpha university ", db)
        assert r["total_users"] == 3  # a1, a2, a3 only
        assert r["active_users"] == 2
        assert r["engagement_rate"] == 66.7
        assert r["avg_screen_time"] == 7.0
        assert r["high_risk_users"] == 1
        assert r["avg_wellness_score"] == 5.0  # old assessment excluded
        assert r["completion_rate"] == 66.7  # 2 completed, 1 cancelled; Beta's cancelled excluded
        assert r["avg_session_duration"] is None and r["satisfaction_score"] is None

        b = m.get_institutional_summary("Beta University", db)
        assert (b["total_users"], b["active_users"], b["high_risk_users"]) == (1, 1, 1)
        assert b["avg_screen_time"] == 12.0 and b["completion_rate"] == 0.0


def test_institutional_summary_empty_and_unknown(app):
    with app.app_context():
        for inst in ("Nowhere", "", None, "   "):
            r = m.get_institutional_summary(inst, db)
            assert r["total_users"] == 0 and r["active_users"] == 0
            assert r["avg_screen_time"] is None and r["engagement_rate"] is None


def test_institutional_summary_is_constant_query_count(app):
    """No per-user loops: query count must not grow with user count."""
    from sqlalchemy import event
    with app.app_context():
        _seed_two_institutions()
        for i in range(20):
            _user("patient", f"x{i}@t.local", "Alpha University")
        db.session.commit()
        seen = []
        count = lambda *a: seen.append(1)
        event.listen(db.engine, "before_cursor_execute", count)
        try:
            m.get_institutional_summary("Alpha University", db)
        finally:
            event.remove(db.engine, "before_cursor_execute", count)
        assert len(seen) <= 6


# --- migrations -------------------------------------------------------------

def _shape(insp, t):
    return (
        sorted((c["name"], c["nullable"]) for c in insp.get_columns(t)),
        sorted((tuple(i["column_names"]), bool(i["unique"])) for i in insp.get_indexes(t)),
        sorted((tuple(f["constrained_columns"]), f["referred_table"], f["options"].get("ondelete"))
               for f in insp.get_foreign_keys(t)),
    )


def test_migration_upgrade_matches_create_all(tmp_path, app):
    """`flask db upgrade` on a fresh DB creates the same tables/columns/indexes/FKs as create_all."""
    url = "sqlite:///" + (tmp_path / "mig.db").as_posix()
    env = dict(os.environ, DATABASE_URL=url, FLASK_APP="app.py", SKIP_CREATE_ALL="1")
    r = subprocess.run([sys.executable, "-m", "flask", "db", "upgrade"], cwd=ROOT, env=env,
                       capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stderr[-2000:]
    mig_engine = create_engine(url)
    mig = inspect(mig_engine)
    with app.app_context():
        ref = inspect(db.engine)
        names = set(ref.get_table_names())
        assert set(mig.get_table_names()) - {"alembic_version"} == names
        for t in names:
            assert _shape(mig, t) == _shape(ref, t), t
    mig_engine.dispose()
