"""Prescription services: eligibility, drafts and the issue transaction (design 3.3 to 3.7)."""
import sys
import threading
from datetime import timedelta

import pytest

from extensions import db
from models import AuditLog, Medication, Prescription, PrescriberProfile
from services import consent, prescriptions as P
from services.errors import ServiceError
from tests.rx_support import (KEY, code_of, give_consent, issue, issued, item, link, make_consult, make_med,
                              ready_draft, setup)
from utils import rx_numbers
from utils.timeutil import ist_day_bounds, to_ist_date, utcnow


@pytest.fixture
def s(app, make_user, make_doctor):
    return setup(app, make_user, make_doctor, meds=("A", "B", "C"))


# ---- eligibility ----

def test_eligibility_no_consult(app, make_user, make_doctor):
    d, p = make_doctor(), make_user("patient")
    link(app, d, p)
    give_consent(app, p)
    with app.app_context():
        assert P.consult_eligibility(d, p).blockers == ["no_consult"]


def test_eligibility_stale_consult_after_window(app, make_user, make_doctor):
    d, p = make_doctor(), make_user("patient")
    link(app, d, p)
    give_consent(app, p)
    make_consult(app, d, p, hours_ago=25)
    with app.app_context():
        assert "no_consult" in P.consult_eligibility(d, p).blockers


def test_eligibility_first_vs_followup_vs_in_person(app, make_user, make_doctor):
    d, p = make_doctor(), make_user("patient")
    link(app, d, p)
    give_consent(app, p)
    make_consult(app, d, p, modality="video", time="09:00")
    with app.app_context():
        el = P.consult_eligibility(d, p)
        assert (el.tpg_context, el.allowed_lists, el.blockers, el.follow_up_possible) == ("first", {"O", "A"}, [], False)
    make_consult(app, d, p, modality="in_person", status="completed", hours_ago=24 * 30, time="11:00")
    with app.app_context():
        assert P.consult_eligibility(d, p).follow_up_possible is True
        assert P.consult_eligibility(d, p).tpg_context == "first"  # needs the doctor's attestation
        assert P.consult_eligibility(d, p, True).tpg_context == "follow_up"
        assert P.consult_eligibility(d, p, True).allowed_lists == {"O", "A", "B"}
    make_consult(app, d, p, modality="in_person", time="12:00")
    with app.app_context():
        assert P.consult_eligibility(d, p).tpg_context == "in_person"


def test_eligibility_no_consent_blocker(app, make_user, make_doctor):
    d, p = make_doctor(), make_user("patient")
    link(app, d, p)
    make_consult(app, d, p)
    with app.app_context():
        assert P.consult_eligibility(d, p).blockers == ["no_consent"]


# ---- drafts ----

def test_draft_create_idempotent_and_assigned_only(app, s, make_user):
    with app.app_context():
        a = P.create_draft(s["doctor"], s["patient"], "crid-0000001")
        b = P.create_draft(s["doctor"], s["patient"], "crid-0000001")
        db.session.commit()
        assert a.id == b.id and Prescription.query.count() == 1
    stranger = make_user("patient")
    assert code_of(app, lambda: P.create_draft(s["doctor"], stranger)) == "patient_not_assigned"
    with app.app_context():
        assert Prescription.query.count() == 1


def test_draft_row_version_conflict_and_other_doctor(app, s, make_doctor):
    rx = ready_draft(app, s["doctor"], s["patient"], s["meds"][:1])
    with app.app_context():
        v = db.session.get(Prescription, rx).row_version
    assert code_of(app, lambda: P.save_draft(s["doctor"], rx, {"diagnosis": "x"}, v - 1)) == "stale_draft"
    other = make_doctor()
    assert code_of(app, lambda: P.save_draft(other, rx, {"diagnosis": "x"}, v)) == "not_found"
    assert code_of(app, lambda: P.delete_draft(other, rx)) == "not_found"
    with app.app_context():
        P.save_draft(s["doctor"], rx, {"diagnosis": "x"}, v)
        db.session.commit()
        assert db.session.get(Prescription, rx).row_version == v + 1


def test_draft_rejects_duplicate_medicine_and_bad_numbers(app, s):
    m = s["meds"][0]
    with app.app_context():
        rx = P.create_draft(s["doctor"], s["patient"])
        db.session.commit()
        v, rid = rx.row_version, rx.id
    assert code_of(app, lambda: P.save_draft(s["doctor"], rid, {"items": [item(m), item(m)]}, v)) == "duplicate_medicine"
    assert code_of(app, lambda: P.save_draft(s["doctor"], rid, {"items": [item(m, duration_days=0)]}, v)) == "field_invalid"


# ---- issue ----

def test_issue_happy_path_sets_snapshots_and_number(app, s):
    rx = ready_draft(app, s["doctor"], s["patient"], s["meds"][:1], diagnosis="  F41.1\n\x00 anxiety ")
    rid, replayed = issue(app, s, rx)
    with app.app_context():
        r = db.session.get(Prescription, rid)
        assert not replayed and r.status == "issued" and rx_numbers.is_valid_number(r.number)
        assert r.diagnosis == "F41.1 anxiety"
        assert r.doctor_reg_no.startswith("REG") and r.doctor_council == "State Medical Council"
        assert r.patient_name and r.institution_name == "Test University" and r.tpg_context == "first"
        assert r.items[0].medicine_label == "DRUGA 10 mg tablet" and r.items[0].tpg_list == "A"
        assert r.consult_appointment_id == s["appt"] and r.consent_version


def test_issue_idempotent_replay_and_other_key_conflict(app, s):
    rx = ready_draft(app, s["doctor"], s["patient"], s["meds"][:1])
    issue(app, s, rx)
    _, replayed = issue(app, s, rx)
    assert replayed is True
    assert code_of(app, lambda: P.issue(s["doctor"], rx, "another-key-0002", [])) == "already_issued"
    with app.app_context():
        assert Prescription.query.filter(Prescription.number.isnot(None)).count() == 1


def test_issue_concurrent_double_submit_one_row(app, s):
    rx = ready_draft(app, s["doctor"], s["patient"], s["meds"][:1])
    out = []

    def run(key):
        with app.app_context():
            try:
                res = P.issue(s["doctor"], rx, key, [])
                db.session.commit()
                out.append(("ok", res.replayed))
            except ServiceError as e:
                db.session.rollback()
                out.append((e.code, None))
            finally:
                db.session.remove()
    threads = [threading.Thread(target=run, args=(k,)) for k in ("same-key-00001", "same-key-00001", "other-key-00002")]
    [t.start() for t in threads]
    [t.join() for t in threads]
    with app.app_context():
        assert Prescription.query.filter(Prescription.status == "issued").count() == 1
    assert sum(1 for o in out if o == ("ok", False)) == 1


@pytest.mark.parametrize("letter,schedule,code", [("C", "none", "medicine_blocked_c"), ("A", "H1", "medicine_controlled"),
                                                  ("A", "X", "medicine_controlled"), ("A", "NDPS", "medicine_controlled"),
                                                  ("B", "none", "medicine_needs_followup")])
def test_issue_blocks_restricted_medicines(app, s, letter, schedule, code):
    m = make_med(app, name="Restricted", tpg=letter, schedule=schedule)
    rx = ready_draft(app, s["doctor"], s["patient"], [m])
    assert code_of(app, lambda: P.issue(s["doctor"], rx, KEY, [])) == code
    with app.app_context():
        assert db.session.get(Prescription, rx).status == "draft"
        assert AuditLog.query.filter_by(action="rx_issue_blocked").one().meta == {"code": code}


def test_issue_list_b_allowed_at_in_person_consult(app, make_user, make_doctor):
    s = setup(app, make_user, make_doctor, meds=("B",), modality="in_person")
    rx = ready_draft(app, s["doctor"], s["patient"], s["meds"])
    issue(app, s, rx)


def test_issue_item_limits_and_duration_cap(app, s):
    ms = [make_med(app, name=f"Many{i}", tpg="O") for i in range(7)]
    rx = ready_draft(app, s["doctor"], s["patient"], ms)
    assert code_of(app, lambda: P.issue(s["doctor"], rx, KEY, [])) == "too_many_items"
    rx2 = ready_draft(app, s["doctor"], s["patient"], s["meds"][:1], items=[item(s["meds"][0], duration_days=15)])
    assert code_of(app, lambda: P.issue(s["doctor"], rx2, KEY + "2", [])) == "duration_too_long"


def test_issue_requires_consent_after_withdrawal(app, s):
    rx = ready_draft(app, s["doctor"], s["patient"], s["meds"][:1])
    with app.app_context():
        consent.set_erx_consent(s["patient"], False)
        db.session.commit()
    assert code_of(app, lambda: P.issue(s["doctor"], rx, KEY, [])) == "no_consent"
    with app.app_context():
        consent.set_erx_consent(s["patient"], True)
        db.session.commit()
    issue(app, s, rx)


def test_issue_requires_allergy_and_meds_status(app, s):
    with app.app_context():
        d = P.create_draft(s["doctor"], s["patient"])
        P.save_draft(s["doctor"], d.id, {"diagnosis": "F41", "items": [item(s["meds"][0])]}, d.row_version)
        db.session.commit()
        res = P.validate(s["doctor"], d.id)
        assert {(e["code"], e["field"]) for e in res.errors} == {("field_required", "allergies_status"),
                                                                 ("field_required", "current_meds_status")}


def test_issue_requires_assigned_patient_still_assigned(app, s):
    rx = ready_draft(app, s["doctor"], s["patient"], s["meds"][:1])
    with app.app_context():
        from models import ProviderPatient
        ProviderPatient.query.delete()
        db.session.commit()
    assert code_of(app, lambda: P.issue(s["doctor"], rx, KEY, [])) == "patient_not_assigned"


def test_issue_warning_ack_required(app, s):
    with app.app_context():
        db.session.add(Medication(user_id=s["patient"], name="Druga tablets", is_active=True))
        db.session.commit()
    rx = ready_draft(app, s["doctor"], s["patient"], s["meds"][:1], allergies_status="listed", allergies="reaction to DRUGA")
    with app.app_context():
        codes = {w["code"] for w in P.validate(s["doctor"], rx).warnings}
    assert codes == {"dup_self_logged", "allergy_text_match"}
    assert code_of(app, lambda: P.issue(s["doctor"], rx, KEY, ["dup_self_logged"])) == "warnings_unacknowledged"
    issue(app, s, rx, ack=["dup_self_logged", "allergy_text_match"])
    with app.app_context():
        assert db.session.get(Prescription, rx).warnings_ack == ["allergy_text_match", "dup_self_logged"]


def test_duplicate_active_rx_and_class_warnings(app, s):
    first = make_med(app, name="Sertralex", tpg="A", therapeutic_class="ssri")
    second = make_med(app, name="Fluoxetex", tpg="A", therapeutic_class="ssri")
    issued(app, s, [first])
    rx = ready_draft(app, s["doctor"], s["patient"], [first, second])
    with app.app_context():
        got = {(w["code"], w["item"]) for w in P.validate(s["doctor"], rx).warnings}
    assert got == {("dup_active_rx", 1), ("dup_class", 2)}


def test_issue_demo_medicine_blocked_in_production(app, s, monkeypatch):
    m = make_med(app, name="Democillin", tpg="A", is_demo=True)
    rx = ready_draft(app, s["doctor"], s["patient"], [m])
    monkeypatch.setenv("FLASK_ENV", "production")
    assert code_of(app, lambda: P.issue(s["doctor"], rx, KEY, [])) == "medicine_demo_blocked"
    monkeypatch.setenv("ALLOW_DEMO_DATA", "1")
    issue(app, s, rx)


def test_suspension_blocks_issue_and_lapse_blocks_issue(app, s):
    rx = ready_draft(app, s["doctor"], s["patient"], s["meds"][:1])
    with app.app_context():
        p = PrescriberProfile.query.filter_by(user_id=s["doctor"]).one()
        p.review_due_at = utcnow() - timedelta(days=1)
        db.session.commit()
    assert code_of(app, lambda: P.issue(s["doctor"], rx, KEY, [])) == "prescriber_not_verified"
    with app.app_context():
        assert db.session.get(Prescription, rx).status == "draft"


def test_number_collision_retries(app, s, monkeypatch):
    first = issued(app, s)
    with app.app_context():
        taken = db.session.get(Prescription, first).number
    fresh = rx_numbers.new_number
    seq = iter([taken, taken, fresh()])
    monkeypatch.setattr(sys.modules["services.prescriptions.issue"], "new_number", lambda: next(seq))
    rx = ready_draft(app, s["doctor"], s["patient"], [make_med(app, name="Other", tpg="O")])
    issue(app, s, rx, key="collide-key-01")
    with app.app_context():
        assert db.session.get(Prescription, rx).status == "issued"


def test_expiry_end_of_ist_day(app, s):
    rx = issued(app, s, expiry_days=3)
    with app.app_context():
        r = db.session.get(Prescription, rx)
        last_day = to_ist_date(r.issue_date) + timedelta(days=3)
        start, end = ist_day_bounds(last_day)
        assert start < r.expiry_date < end and end - r.expiry_date <= timedelta(seconds=1)
