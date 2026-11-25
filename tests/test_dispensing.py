"""Dispensing service: FEFO plan, confirm, replay, stale plans, blocks, reversal (design 4.6, 4.7)."""
from datetime import timedelta

import pytest

from core.extensions import db
from models import InventoryBatch, InventoryTransaction, PrescriberProfile, Prescription, PrescriptionItem
from services import dispensing, inventory
from services.errors import ServiceError
from tests import inv_helpers as h
from utils.rx_numbers import new_number
from utils.timeutil import utcnow

ID = dict(identity_checked=True, pharmacist_name='Pooja Rao', pharmacist_reg_no='PH12345')


@pytest.fixture
def world(app, make_user, make_doctor):
    """patient, doctor, desk admin and one medicine."""
    return {'patient': make_user('patient'), 'doctor': make_doctor(), 'desk': make_user('admin', is_pharmacy_desk=True),
            'med': h.med(app)}


def prepare(app, w, rx_id, lines=None, actor=None):
    with app.app_context():
        return dispensing.plan(rx_id, h.INST, actor or w['desk'], lines=lines)


def do_confirm(app, w, rx_id, token, key='confirm-key-0001', actor=None, **kw):
    args = dict(ID, **kw)
    with app.app_context():
        return dispensing.confirm(rx_id, h.INST, actor or w['desk'], token, key, **args)


def rx_of(app, w, qty, **kw):
    return h.rx(app, w['patient'], w['doctor'], [(w['med'], qty)], **kw)


def state(app, rx_id):
    with app.app_context():
        rx = db.session.get(Prescription, rx_id)
        return rx.status, [i.quantity_dispensed for i in rx.items]


def test_fefo_order_and_expired_never_allocated(app, world):
    early, late = h.batch(app, world['med'], 5, 'EARLY', days=10), h.batch(app, world['med'], 5, 'LATE', days=60)
    h.batch(app, world['med'], 50, 'DEAD', days=-1)
    h.batch(app, world['med'], 50, 'QUAR', days=5, status='quarantined')
    p = prepare(app, world, rx_of(app, world, 8))
    line = p['lines'][0]
    assert [(a['batch_id'], a['quantity']) for a in line['allocations']] == [(early, 5), (late, 3)] and line['shortfall'] == 0
    p2 = prepare(app, world, rx_of(app, world, 14))  # only 10 usable units exist
    assert p2['lines'][0]['shortfall'] == 4 and any(w['code'] == 'stock_short' for w in p2['warnings'])


def test_partial_then_full_dispense(app, world):
    b = h.batch(app, world['med'], 3)
    rx = rx_of(app, world, 5)
    p = prepare(app, world, rx)
    assert p['lines'][0]['shortfall'] == 2
    r = do_confirm(app, world, rx, p['token'])
    assert r['status'] == 'partially_dispensed' and not r['replayed'] and state(app, rx) == ('partially_dispensed', [3])
    assert h.on_hand(app, b) == 0
    with app.app_context():
        inventory.receive(h.INST, world['med'], 'B2', utcnow().date() + timedelta(days=90), 10, world['desk'], 'restock-0001')
        db.session.commit()
    p = prepare(app, world, rx)
    assert p['lines'][0]['requested'] == 2
    assert do_confirm(app, world, rx, p['token'], key='confirm-key-0002')['status'] == 'dispensed'
    assert state(app, rx) == ('dispensed', [5])
    with app.app_context():
        assert inventory.reconcile(h.INST) == []
        row = InventoryTransaction.query.filter_by(kind='dispense').first()
        assert row.dispenser_label == 'Pooja Rao, Reg. PH12345' and row.rx_number and row.group_ref
    with pytest.raises(ServiceError) as e:
        prepare(app, world, rx)
    assert e.value.code == 'rx_not_dispensable'


def test_confirm_idempotent_replay(app, world):
    b = h.batch(app, world['med'], 10)
    rx = rx_of(app, world, 4)
    token = prepare(app, world, rx)['token']
    first = do_confirm(app, world, rx, token)
    again = do_confirm(app, world, rx, token)  # even with a token that is now stale
    assert again['replayed'] is True and again['group_ref'] == first['group_ref'] and again['status'] == first['status']
    assert h.on_hand(app, b) == 6 and state(app, rx)[1] == [4]


def test_desk_may_lower_but_not_raise_a_line(app, world):
    h.batch(app, world['med'], 10)
    rx = rx_of(app, world, 4)
    with app.app_context():
        item = PrescriptionItem.query.filter_by(prescription_id=rx).one().id
    p = prepare(app, world, rx, lines=[{'item_id': item, 'quantity': 1}])
    assert p['lines'][0]['requested'] == 1
    with pytest.raises(ServiceError) as e:
        prepare(app, world, rx, lines=[{'item_id': item, 'quantity': 5}])
    assert e.value.code == 'validation'
    with pytest.raises(ServiceError) as e:
        prepare(app, world, rx, lines=[{'item_id': item, 'quantity': 0}])
    assert e.value.code == 'nothing_to_dispense'


def test_plan_stale_when_stock_changed_or_prescription_touched(app, world):
    b = h.batch(app, world['med'], 10)
    rx = rx_of(app, world, 4)
    token = prepare(app, world, rx)['token']
    with app.app_context():
        inventory.adjust(b, -10, 'lost', world['desk'], 'adj-key-0001', institution_key=h.INST)
        db.session.commit()
    with pytest.raises(ServiceError) as e:
        do_confirm(app, world, rx, token)
    assert e.value.code == 'plan_stale' and e.value.http == 409 and 'plan' in e.value.ctx
    assert state(app, rx) == ('issued', [0])
    h.batch(app, world['med'], 10, 'B2')
    token = prepare(app, world, rx)['token']
    with app.app_context():  # the patient resends the request: updated_at moves, the old plan is stale
        db.session.get(Prescription, rx).dispense_requested_at = utcnow()
        db.session.commit()
    with pytest.raises(ServiceError) as e:
        do_confirm(app, world, rx, token, key='confirm-key-0009')
    assert e.value.code == 'plan_stale' and e.value.ctx['plan']['lines'][0]['requested'] == 4
    assert state(app, rx)[1] == [0]


def test_identity_pharmacist_and_token_required(app, world):
    h.batch(app, world['med'], 10)
    rx = rx_of(app, world, 4)
    token = prepare(app, world, rx)['token']
    for kw, code in (({'identity_checked': False}, 'identity_required'), ({'pharmacist_name': 'Pu'}, 'pharmacist_required'),
                     ({'pharmacist_reg_no': ''}, 'pharmacist_required')):
        with pytest.raises(ServiceError) as e:
            do_confirm(app, world, rx, token, **kw)
        assert e.value.code == code
    with pytest.raises(ServiceError) as e:
        do_confirm(app, world, rx, token + 'x')
    assert e.value.code == 'bad_token'
    other = h.INST and h.rx(app, world['patient'], world['doctor'], [(world['med'], 1)])
    with pytest.raises(ServiceError) as e:  # a token is bound to its prescription
        do_confirm(app, world, other, token)
    assert e.value.code == 'bad_token'
    assert state(app, rx) == ('issued', [0])


def test_cancelled_expired_and_foreign_rx_not_dispensable(app, world):
    h.batch(app, world['med'], 10)
    for kw in ({'status': 'cancelled'}, {'status': 'dispensed'}, {'days_valid': -1}, {'status': 'draft'}):
        with pytest.raises(ServiceError) as e:
            prepare(app, world, rx_of(app, world, 2, **kw))
        assert e.value.code in ('rx_not_dispensable', 'not_found'), kw
    foreign = rx_of(app, world, 2, inst='other campus')
    with pytest.raises(ServiceError) as e:
        prepare(app, world, foreign)
    assert e.value.http == 404


def test_cancel_between_prepare_and_confirm_blocks(app, world):
    b = h.batch(app, world['med'], 10)
    rx = rx_of(app, world, 4)
    token = prepare(app, world, rx)['token']
    with app.app_context():
        db.session.get(Prescription, rx).status = 'cancelled'
        db.session.commit()
    with pytest.raises(ServiceError) as e:
        do_confirm(app, world, rx, token)
    assert e.value.code == 'rx_not_dispensable' and h.on_hand(app, b) == 10


def test_suspended_prescriber_blocks_confirm(app, world):
    b = h.batch(app, world['med'], 10)
    rx = rx_of(app, world, 4)
    token = prepare(app, world, rx)['token']
    with app.app_context():
        PrescriberProfile.query.filter_by(user_id=world['doctor']).one().status = 'suspended'
        db.session.commit()
    assert prepare(app, world, rx)['warnings'][0]['code'] == 'prescriber_not_verified'
    with pytest.raises(ServiceError) as e:
        do_confirm(app, world, rx, token)
    assert e.value.code == 'prescriber_not_verified' and h.on_hand(app, b) == 10


def test_reverse_within_24h_once_and_restores_status(app, world):
    b = h.batch(app, world['med'], 10)
    rx = rx_of(app, world, 4)
    do_confirm(app, world, rx, prepare(app, world, rx)['token'])
    assert state(app, rx) == ('dispensed', [4])
    with app.app_context():
        line = InventoryTransaction.query.filter_by(kind='dispense').one().id
        back = dispensing.reverse(line, world['desk'], 'rev-key-0001', institution_key=h.INST)
        assert (back.kind, back.delta, back.reverses_id) == ('return', 4, line)
        assert dispensing.reverse(line, world['desk'], 'rev-key-0001', institution_key=h.INST).id == back.id  # replay
        with pytest.raises(ServiceError) as e:
            dispensing.reverse(line, world['desk'], 'rev-key-0002', institution_key=h.INST)
        assert e.value.code == 'not_reversible'
        assert inventory.reconcile(h.INST) == []
    assert state(app, rx) == ('issued', [0]) and h.on_hand(app, b) == 10  # not restocked elsewhere: it is the same batch
    with app.app_context():
        assert InventoryTransaction.query.filter_by(kind='return').count() == 1


def test_reverse_refused_after_24_hours_or_other_institution(app, world):
    h.batch(app, world['med'], 10)
    rx = rx_of(app, world, 4)
    do_confirm(app, world, rx, prepare(app, world, rx)['token'])
    with app.app_context():
        tx = InventoryTransaction.query.filter_by(kind='dispense').one()
        with pytest.raises(ServiceError) as e:
            dispensing.reverse(tx.id, world['desk'], 'rev-key-0003', institution_key='other campus')
        assert e.value.http == 404
        tx.created_at = utcnow() - timedelta(hours=25)
        db.session.commit()
        with pytest.raises(ServiceError) as e:
            dispensing.reverse(tx.id, world['desk'], 'rev-key-0004', institution_key=h.INST)
        assert e.value.code == 'not_reversible'


def test_queue_shows_initials_only_and_lookup_validates(app, world):
    h.batch(app, world['med'], 10)
    queued = rx_of(app, world, 2, patient_name='Asha Kumari Sharma')
    rx_of(app, world, 2, requested=False)
    rx_of(app, world, 2, inst='other campus')
    with app.app_context():
        q = dispensing.queue(h.INST)
        assert len(q) == 1 and q[0]['initials'] == 'A. S.' and q[0]['items'] == 1 and q[0]['rx_id'] == queued
        assert 'Asha' not in str(q) and 'Sharma' not in str(q)
        number = db.session.get(Prescription, queued).number
        assert dispensing.lookup(number.lower(), h.INST).id == queued
        for bad, code in ((number[:-1] + ('0' if number[-1] != '0' else '1'), 'bad_number'), ('nonsense', 'bad_number'),
                          (new_number(), 'not_found')):
            with pytest.raises(ServiceError) as e:
                dispensing.lookup(bad, h.INST)
            assert e.value.code == code
        with pytest.raises(ServiceError) as e:
            dispensing.lookup(number, 'other campus')
        assert e.value.code == 'not_found'
