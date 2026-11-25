"""O-04: clinical free-text columns are encrypted at rest (utils/field_encryption.py).

ORM round-trip is covered incidentally by every existing model test (JournalEntry, SafetyPlan, MoodLog,
ClinicalNote, Assessment, VoiceLog all still assert plain Python values). This file checks the thing
those tests cannot: what is actually sitting in the database column.
"""
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import text

from extensions import db
from models import Assessment, ClinicalNote, JournalEntry, MoodLog
from models_wellbeing import SafetyPlan
from utils.field_encryption import EncryptedText, reset_cipher_cache

SECRET = "I have been thinking about ending my life and nobody knows."


def _raw_column(app, table, column, row_id):
    """Read a column straight from the DB, bypassing the ORM/TypeDecorator."""
    with app.app_context():
        row = db.session.execute(text(f"SELECT {column} FROM {table} WHERE id = :id"), {"id": row_id}).fetchone()
        return row[0]


def test_journal_content_is_ciphertext_on_disk(app, patient_client):
    c, uid = patient_client
    with app.app_context():
        entry = JournalEntry(user_id=uid, title="t", content=SECRET, sentiment="Neutral")
        db.session.add(entry)
        db.session.commit()
        entry_id = entry.id

    raw = _raw_column(app, "journal_entries", "content", entry_id)
    assert raw is not None
    assert SECRET.encode("utf-8") not in bytes(raw)  # not plaintext on disk
    assert bytes(raw).startswith(b"gAAAAA")  # Fernet token prefix (version byte 0x80 + timestamp, base64url)

    with app.app_context():
        assert JournalEntry.query.get(entry_id).content == SECRET  # transparent at the ORM boundary


def test_safety_plan_warning_signs_is_ciphertext_on_disk(app, patient_client):
    c, uid = patient_client
    with app.app_context():
        plan = SafetyPlan(user_id=uid, warning_signs=SECRET)
        db.session.add(plan)
        db.session.commit()
        plan_id = plan.id

    raw = _raw_column(app, "safety_plans", "warning_signs", plan_id)
    assert SECRET.encode("utf-8") not in bytes(raw)

    with app.app_context():
        assert SafetyPlan.query.get(plan_id).warning_signs == SECRET


def test_clinical_note_text_fields_are_ciphertext_on_disk(app, patient_client):
    _, patient_id = patient_client
    with app.app_context():
        from datetime import datetime
        note = ClinicalNote(provider_id=patient_id, patient_id=patient_id, session_date=datetime.utcnow(),
                             transcript=SECRET, provider_notes="session went well")
        db.session.add(note)
        db.session.commit()
        note_id = note.id

    for column, plain in (("transcript", SECRET), ("provider_notes", "session went well")):
        raw = _raw_column(app, "clinical_notes", column, note_id)
        assert plain.encode("utf-8") not in bytes(raw)


def test_mood_log_notes_and_assessment_responses_are_ciphertext_on_disk(app, patient_client):
    _, uid = patient_client
    with app.app_context():
        mood = MoodLog(user_id=uid, mood_score=3, notes=SECRET)
        a = Assessment(user_id=uid, assessment_type="mood", score=3, responses={"mood": 3, "notes": SECRET})
        db.session.add_all([mood, a])
        db.session.commit()
        mood_id, a_id = mood.id, a.id

    raw_mood = _raw_column(app, "mood_logs", "notes", mood_id)
    assert SECRET.encode("utf-8") not in bytes(raw_mood)

    raw_resp = _raw_column(app, "assessments", "responses", a_id)
    assert SECRET.encode("utf-8") not in bytes(raw_resp)

    with app.app_context():
        assert Assessment.query.get(a_id).responses == {"mood": 3, "notes": SECRET}


def test_round_trip_is_exact(app):
    """Encrypt/decrypt correctness directly against the TypeDecorator, independent of any model."""
    col = EncryptedText()
    with app.app_context():
        ciphertext = col.process_bind_param(SECRET, None)
        assert isinstance(ciphertext, bytes)
        assert col.process_result_value(ciphertext, None) == SECRET
        assert col.process_bind_param(None, None) is None
        assert col.process_result_value(None, None) is None


def test_wrong_key_cannot_decrypt(app, monkeypatch):
    """A different FIELD_ENCRYPTION_KEY must not silently return garbage or the wrong plaintext."""
    with app.app_context():
        col = EncryptedText()
        ciphertext = col.process_bind_param(SECRET, None)

        monkeypatch.setenv("FIELD_ENCRYPTION_KEY", Fernet.generate_key().decode())
        reset_cipher_cache()
        try:
            try:
                col.process_result_value(ciphertext, None)
                assert False, "decryption should have failed with a different key"
            except InvalidToken:
                pass
        finally:
            reset_cipher_cache()  # restore the real test key for every other test in this process
