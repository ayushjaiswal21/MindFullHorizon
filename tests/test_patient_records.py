"""Patient feature tests: journal and voice log persistence/isolation, the progress API's session-user
scoping, and landing-page honesty. Split out of test_patient.py (300-line rule); gamification, mood,
medication, goals, appointments and detox tests are in test_patient_activities.py."""
from models import Gamification

XHR = {"X-Requested-With": "XMLHttpRequest"}


def _gam(app, uid):
    with app.app_context():
        g = Gamification.query.filter_by(user_id=uid).first()
        return (g.points, g.streak) if g else (0, 0)


# ---- 8. journal and voice logs persist in the DB ---------------------------

def test_journal_roundtrip_and_isolation(app, patient_client, make_user, login):
    from models import JournalEntry
    c, uid = patient_client
    r = c.post("/patient/journal", data={"title": "Day one", "content": "Felt okay today."})
    assert r.status_code == 302
    assert c.post("/patient/journal", data={"title": "t" * 101, "content": "x"}).status_code == 302
    with app.app_context():
        rows = JournalEntry.query.all()
        assert [(e.user_id, e.title) for e in rows] == [(uid, "Day one")]
        eid = rows[0].id
    assert "Day one" in c.get("/patient/journal").get_data(as_text=True)
    assert _gam(app, uid)[0] == 15 + 5  # 15 for the entry, 5 for the first page visit of the day
    # another patient cannot see or delete it
    other = make_user("patient")
    c2 = app.test_client()
    from conftest import _login_as
    _login_as(c2, app, other)
    assert "Day one" not in c2.get("/patient/journal").get_data(as_text=True)
    assert c2.delete(f"/api/delete-journal-entry/{eid}", headers=XHR).status_code == 404
    assert c.delete(f"/api/delete-journal-entry/{eid}", headers=XHR).status_code == 200
    with app.app_context():
        assert JournalEntry.query.count() == 0


def test_voice_upload_list_delete(app, patient_client, make_user):
    import io
    from models import VoiceLog
    c, uid = patient_client
    r = c.post("/api/upload-voice", data={"audio": (io.BytesIO(b"RIFF....WAVEfmt "), "voice_log.wav", "audio/wav")},
               content_type="multipart/form-data", headers=XHR)
    assert r.status_code == 200, r.get_data(as_text=True)
    bad = c.post("/api/upload-voice", data={"audio": (io.BytesIO(b"x"), "evil.exe", "audio/wav")},
                 content_type="multipart/form-data", headers=XHR)
    assert bad.status_code == 400
    assert c.post("/api/upload-voice", data={}, headers=XHR).status_code == 400
    with app.app_context():
        logs = VoiceLog.query.all()
        assert len(logs) == 1 and logs[0].user_id == uid and logs[0].emotion is None
        lid = logs[0].id
    assert c.get("/patient/voice-logs").status_code == 200
    assert _gam(app, uid)[0] == 20 + 5  # 20 for the voice log, 5 for the first page visit of the day
    other = make_user("patient")
    c2 = app.test_client()
    from conftest import _login_as
    _login_as(c2, app, other)
    assert c2.delete(f"/api/delete-voice-log/{lid}", headers=XHR).status_code == 404
    assert c.delete(f"/api/delete-voice-log/{lid}", headers=XHR).status_code == 200


# ---- 9. progress API is scoped to the session user -------------------------

def test_progress_api_requires_login_and_scopes(app, client, patient_client, make_user):
    from core.extensions import db
    from models import Assessment
    assert client.get("/patient/api/progress").status_code in (302, 401)
    c, uid = patient_client
    other = make_user("patient")
    with app.app_context():
        db.session.add(Assessment(user_id=other, assessment_type="PHQ-9", score=3))
        db.session.commit()
    r = c.get("/patient/api/progress", headers=XHR)
    assert r.status_code == 200 and r.get_json()["assessments"] == []


# ---- 10. landing page honesty ---------------------------------------------

def test_index_and_landing_have_no_fake_claims(client, patient_client):
    pages = [client.get("/").get_data(as_text=True), patient_client[0].get("/").get_data(as_text=True)]
    for html in pages:
        for fake in ("52K", "4.9", "hero_image.png", "Priya Sharma", "25K+", "1M+", "End-to-end encryption"):
            assert fake not in html, fake
    assert "14416" in pages[0]
