"""State machines (appointments, crisis ack), /api/message authorisation, telehealth entry-point parity."""
from datetime import timedelta

import pytest

import app as app_module
from conftest import _login_as
from extensions import db
from models import Appointment, CrisisEvent, Notification, ProviderPatient, get_institutional_summary
from utils.state import RULES, TransitionError, canonical, transition
from utils.timeutil import ist_today

XHR = {"X-Requested-With": "XMLHttpRequest"}
STATUSES = ["pending", "accepted", "rejected", "booked", "completed", "cancelled"]


def make_appt(app, patient, provider=None, status="pending", time="10:00", day=None):
    with app.app_context():
        a = Appointment(user_id=patient, provider_id=provider, date=day or ist_today(), time=time,
                        appointment_type="video", status=status)
        db.session.add(a)
        db.session.commit()
        return a.id


def status_of(app, aid):
    with app.app_context():
        return db.session.get(Appointment, aid).status


def client_for(app, uid):
    c = app.test_client()
    _login_as(c, app, uid)
    return c


# ---- transition table ---------------------------------------------------------

@pytest.mark.parametrize("old", STATUSES)
@pytest.mark.parametrize("new", STATUSES)
@pytest.mark.parametrize("actor", ["patient", "provider", "system"])
def test_every_transition_pair(app, make_user, old, new, actor):
    pid = make_user("patient")
    aid = make_appt(app, pid, status=old)
    legal = (canonical(old), new) in RULES and (actor == "system" or actor in RULES[(canonical(old), new)])
    with app.app_context():
        appt = db.session.get(Appointment, aid)
        if legal:
            transition(appt, new, actor)
            db.session.commit()
            assert db.session.get(Appointment, aid).status == new
        else:
            with pytest.raises(TransitionError):
                transition(appt, new, actor)
            db.session.rollback()
            assert db.session.get(Appointment, aid).status == old


def test_terminal_states_never_move(app, make_user):
    pid = make_user("patient")
    for old in ("rejected", "cancelled", "completed"):
        aid = make_appt(app, pid, status=old, time=f"1{len(old)}:00")
        with app.app_context():
            for new in STATUSES:
                with pytest.raises(TransitionError):
                    transition(db.session.get(Appointment, aid), new, "system")
            db.session.rollback()


def test_stale_object_loses_the_race(app, make_user):
    pid = make_user("patient")
    aid = make_appt(app, pid)
    with app.app_context():
        stale = db.session.get(Appointment, aid)
        db.session.execute(db.update(Appointment).where(Appointment.id == aid).values(status="cancelled"))
        with pytest.raises(TransitionError):  # the row says 'pending' in memory, the DB says 'cancelled'
            transition(stale, "accepted", "provider")


# ---- provider routes: 409 mapping, complete flow, completion rate -----------------

def test_provider_accept_reject_complete_cancel_flow(app, make_user, provider_client):
    pc, prov = provider_client
    patient = make_user("patient")
    a = make_appt(app, patient, prov, time="09:00")
    r = pc.post(f"/provider/appointments/accept/{a}")
    assert r.status_code == 200 and r.get_json()["status"] == "accepted"
    assert pc.post(f"/provider/appointments/accept/{a}").status_code == 409  # already accepted
    r = pc.post(f"/provider/appointments/complete/{a}")
    assert r.status_code == 200 and status_of(app, a) == "completed"
    assert pc.post(f"/provider/appointments/cancel/{a}").status_code == 409  # terminal
    body = pc.post(f"/provider/appointments/reject/{a}", json={"reason": "x"})
    assert body.status_code == 409 and "str" not in body.get_data(as_text=True).lower()

    b = make_appt(app, patient, prov, time="11:00")
    assert pc.post(f"/provider/appointments/complete/{b}").status_code == 409  # pending cannot complete
    assert pc.post(f"/provider/appointments/cancel/{b}").status_code == 409    # provider rejects a pending request instead
    assert pc.post(f"/provider/appointments/reject/{b}", json={"reason": "busy"}).status_code == 200
    c = make_appt(app, patient, prov, time="12:00")
    pc.post(f"/provider/appointments/accept/{c}")
    assert pc.post(f"/provider/appointments/cancel/{c}").status_code == 200 and status_of(app, c) == "cancelled"


def test_provider_complete_scope_and_legacy_booked(app, make_user, provider_client):
    pc, prov = provider_client
    other = make_user("provider")
    patient = make_user("patient")
    mine = make_appt(app, patient, prov, status="booked")
    theirs = make_appt(app, patient, other, time="11:00", status="accepted")
    assert pc.post(f"/provider/appointments/complete/{theirs}").status_code == 403
    assert pc.post(f"/provider/appointments/complete/{mine}").status_code == 200  # booked behaves as accepted
    assert status_of(app, mine) == "completed" and status_of(app, theirs) == "accepted"
    assert app.test_client().post(f"/provider/appointments/complete/{mine}").status_code in (302, 401)


def test_patient_cannot_use_provider_transitions(app, make_user, patient_client):
    c, uid = patient_client
    prov = make_user("provider")
    a = make_appt(app, uid, prov, status="accepted")
    for path in ("complete", "cancel", "accept"):
        assert c.post(f"/provider/appointments/{path}/{a}", headers=XHR).status_code == 403
    assert status_of(app, a) == "accepted"


def test_patient_cancel_uses_state_machine(app, make_user, patient_client):
    c, uid = patient_client
    prov = make_user("provider")
    a = make_appt(app, uid, prov)
    c.post(f"/patient/appointments/{a}/cancel")
    assert status_of(app, a) == "cancelled"
    r = c.post(f"/patient/appointments/{a}/cancel", headers=XHR)  # terminal: refused
    assert r.status_code == 409 and r.get_json()["success"] is False
    done = make_appt(app, uid, prov, status="completed", time="13:00")
    c.post(f"/patient/appointments/{done}/cancel")
    assert status_of(app, done) == "completed"
    stranger = client_for(app, make_user("patient"))
    mine = make_appt(app, uid, prov, time="14:00")
    stranger.post(f"/patient/appointments/{mine}/cancel")
    assert status_of(app, mine) == "pending"


def test_completion_rate_uses_completed(app, make_user):
    patients = [make_user("patient") for _ in range(3)]
    prov = make_user("provider")
    a = make_appt(app, patients[0], prov, status="accepted")
    make_appt(app, patients[1], prov, status="cancelled")
    make_appt(app, patients[2], prov, status="accepted", time="11:00")
    with app.app_context():
        assert get_institutional_summary("Test University", db)["completion_rate"] == 0.0  # 0 completed, 1 cancelled
    with app.app_context():
        transition(db.session.get(Appointment, a), "completed", "provider")
        db.session.commit()
        assert get_institutional_summary("Test University", db)["completion_rate"] == 50.0


def test_partial_unique_slot_frees_after_reject(app, make_user):
    prov = make_user("provider")
    p1, p2 = make_user("patient"), make_user("patient")
    a = make_appt(app, p1, prov, time="10:00")
    with pytest.raises(Exception):
        make_appt(app, p2, prov, time="10:00")
    with app.app_context():
        transition(db.session.get(Appointment, a), "rejected", "provider")
        db.session.commit()
    assert make_appt(app, p2, prov, time="10:00")


# ---- crisis acknowledge is idempotent ----------------------------------------------

def test_crisis_acknowledge_twice_keeps_first_acker(app, make_user):
    patient, p1, p2 = make_user("patient"), make_user("provider"), make_user("provider")
    with app.app_context():
        ev = CrisisEvent(user_id=patient, source="chat", severity=9, reason="x")
        db.session.add(ev)
        db.session.commit()
        eid = ev.id
    assert client_for(app, p1).post(f"/provider/crisis/{eid}/acknowledge", headers=XHR).status_code == 200
    with app.app_context():
        first_at = db.session.get(CrisisEvent, eid).acknowledged_at
    assert client_for(app, p2).post(f"/provider/crisis/{eid}/acknowledge", headers=XHR).status_code == 200
    with app.app_context():
        ev = db.session.get(CrisisEvent, eid)
        assert ev.acknowledged_by == p1 and ev.acknowledged_at == first_at


# ---- /api/message authorisation matrix ------------------------------------------

def send(client, **body):
    return client.post("/api/message", json=body, headers=XHR)


def test_message_requires_login(client):
    assert client.post("/api/message", json={"recipient_id": 1, "message": "hi"}, headers=XHR).status_code == 401


def test_message_matrix(app, make_user):
    patient, other_patient = make_user("patient"), make_user("patient")
    linked, appt_linked, stranger = make_user("provider"), make_user("provider"), make_user("provider")
    with app.app_context():
        db.session.add(ProviderPatient(provider_id=linked, patient_id=patient, source="manual"))
        db.session.commit()
    make_appt(app, patient, appt_linked)
    pc, lc = client_for(app, patient), client_for(app, linked)

    assert send(pc, recipient_id=linked, message=" hello ").status_code == 200  # ProviderPatient link
    assert send(pc, recipient_id=appt_linked, message="hi").status_code == 200  # appointment link
    assert send(lc, recipient_id=patient, message="reply").status_code == 200   # provider -> patient
    with app.app_context():
        assert Notification.query.filter_by(recipient_id=linked).one().message == "hello"  # stripped
    for rid in (stranger, other_patient, patient, 999999):  # unlinked provider, patient<->patient, self, unknown
        r = send(pc, recipient_id=rid, message="x")
        assert r.status_code == 403 and r.get_json()["success"] is False, rid
    assert send(lc, recipient_id=linked, message="x").status_code == 403           # provider -> self
    assert send(lc, recipient_id=stranger, message="x").status_code == 403         # provider -> provider
    assert send(lc, recipient_id=other_patient, message="x").status_code == 403    # provider -> unlinked patient
    with app.app_context():
        assert Notification.query.count() == 3


@pytest.mark.parametrize("body", [{}, {"recipient_id": "abc", "message": "x"}, {"recipient_id": True, "message": "x"},
                                  {"recipient_id": 1, "message": "   "}, {"recipient_id": 1, "message": 5},
                                  {"recipient_id": 1, "message": "x" * 1001}, {"recipient_id": [1], "message": "x"}])
def test_message_validation_400(app, patient_client, body):
    c, _ = patient_client
    r = send(c, **body)
    assert r.status_code == 400 and r.get_json()["success"] is False


def test_message_errors_are_generic(app, make_user, monkeypatch):
    patient, prov = make_user("patient"), make_user("provider")
    with app.app_context():
        db.session.add(ProviderPatient(provider_id=prov, patient_id=patient, source="manual"))
        db.session.commit()

    def boom(*a, **k):
        raise RuntimeError("SECRET-DB-DETAIL")
    monkeypatch.setattr(db.session, "commit", boom)
    r = send(client_for(app, patient), recipient_id=prov, message="x")
    assert r.status_code == 500 and "SECRET" not in r.get_data(as_text=True)


# ---- telehealth: provider page, /telehealth_session and the socket join agree --------

def _joined(app, client, room):
    sio = app_module.socketio.test_client(app, flask_test_client=client)
    sio.get_received()
    sio.emit("join", {"room": room})
    return "message" in [m["name"] for m in sio.get_received()]


def test_telehealth_entry_points_agree(app, make_user):
    patient = make_user("patient")
    other_patient = make_user("patient")
    appt_provider, linked_provider = make_user("provider"), make_user("provider")
    stranger = make_user("provider")
    foreign = make_user("provider", institution="Elsewhere U")
    foreign_linked = make_user("provider", institution="Elsewhere U")
    rejected = make_user("provider")
    make_appt(app, patient, appt_provider)
    make_appt(app, patient, rejected, status="rejected", time="12:00")
    make_appt(app, patient, foreign, time="13:00")  # appointment, but another institution
    with app.app_context():
        db.session.add_all([ProviderPatient(provider_id=linked_provider, patient_id=patient, source="manual"),
                            ProviderPatient(provider_id=foreign_linked, patient_id=patient, source="manual")])
        db.session.commit()
    room = f"telehealth_room_{patient}"
    cases = [(patient, True), (appt_provider, True), (linked_provider, True), (stranger, False), (foreign, False),
             (foreign_linked, False), (rejected, False), (other_patient, False)]
    for uid, allowed in cases:
        c = client_for(app, uid)
        page_ok = c.get(f"/provider/telehealth/{patient}").status_code == 200
        legacy_ok = c.get(f"/telehealth_session/{patient}").status_code == 200
        assert _joined(app, c, room) is allowed, uid
        is_provider = uid not in (patient, other_patient)
        if is_provider:  # both provider pages follow the same rule as the socket
            assert page_ok is allowed and legacy_ok is allowed, uid
        else:
            assert not page_ok and not legacy_ok
