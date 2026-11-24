"""Dispensing under concurrency (two threads, separate sessions) and through the desk routes (design 4.3, 4.6, 5.4)."""
import threading

import pytest

from extensions import db
from models import InventoryTransaction, Prescription, PrescriptionItem
from services import dispensing, inventory
from services.errors import ServiceError
from tests import inv_helpers as h

ID = dict(identity_checked=True, pharmacist_name='Pooja Rao', pharmacist_reg_no='PH12345')


def run_parallel(app, jobs):
    """Run each callable in its own thread and app context, released together. Returns ('ok', v) or ('err', code)."""
    gate, out = threading.Barrier(len(jobs)), [None] * len(jobs)

    def worker(i, fn):
        with app.app_context():
            gate.wait()
            try:
                out[i] = ('ok', fn())
            except ServiceError as err:
                out[i] = ('err', err.code)
            except Exception as exc:  # reported, never swallowed: the assertions below would fail
                out[i] = ('exc', type(exc).__name__)
            finally:
                db.session.remove()

    threads = [threading.Thread(target=worker, args=(i, fn)) for i, fn in enumerate(jobs)]
    [t.start() for t in threads]
    [t.join(30) for t in threads]
    return out


@pytest.fixture
def two_desks(make_user):
    return make_user('admin', is_pharmacy_desk=True), make_user('admin', is_pharmacy_desk=True)


def _plan(app, rx_id, desk):
    with app.app_context():
        return dispensing.plan(rx_id, h.INST, desk)['token']


def _confirm(rx_id, desk, token, key):
    return lambda: dispensing.confirm(rx_id, h.INST, desk, token, key, **ID)


def test_two_threads_cannot_oversell(app, make_user, make_doctor, two_desks):
    """Ten units, two prescriptions of ten, both planned against the same batch before either confirms."""
    med, doctor = h.med(app), make_doctor()
    bid = h.batch(app, med, 10)
    rx1 = h.rx(app, make_user('patient'), doctor, [(med, 10)])
    rx2 = h.rx(app, make_user('patient'), doctor, [(med, 10)])
    t1, t2 = _plan(app, rx1, two_desks[0]), _plan(app, rx2, two_desks[1])
    results = run_parallel(app, [_confirm(rx1, two_desks[0], t1, 'thread-key-0001'), _confirm(rx2, two_desks[1], t2, 'thread-key-0002')])
    assert sorted(r[0] for r in results) == ['err', 'ok'], results
    assert [r[1] for r in results if r[0] == 'err'] == ['plan_stale']
    assert h.on_hand(app, bid) == 0
    with app.app_context():
        assert inventory.reconcile(h.INST) == []
        assert InventoryTransaction.query.filter_by(kind='dispense').count() == 1
        assert sorted(p.status for p in Prescription.query) == ['dispensed', 'issued']


def test_two_desks_same_rx_one_wins(app, make_user, make_doctor, two_desks):
    med = h.med(app)
    bid = h.batch(app, med, 50)
    rx = h.rx(app, make_user('patient'), make_doctor(), [(med, 10)])
    t1, t2 = _plan(app, rx, two_desks[0]), _plan(app, rx, two_desks[1])
    results = run_parallel(app, [_confirm(rx, two_desks[0], t1, 'desk-key-00001'), _confirm(rx, two_desks[1], t2, 'desk-key-00002')])
    assert sorted(r[0] for r in results) == ['err', 'ok'], results
    assert [r[1] for r in results if r[0] == 'err'][0] in ('plan_stale', 'rx_not_dispensable')
    assert h.on_hand(app, bid) == 40
    with app.app_context():
        assert PrescriptionItem.query.one().quantity_dispensed == 10 and inventory.reconcile(h.INST) == []


def test_same_key_twice_at_once_dispenses_once(app, make_user, make_doctor, two_desks):
    """A double click: both requests carry the same Idempotency-Key. One does the work, the other gets its result."""
    med = h.med(app)
    bid = h.batch(app, med, 20)
    rx = h.rx(app, make_user('patient'), make_doctor(), [(med, 6)])
    token = _plan(app, rx, two_desks[0])
    job = _confirm(rx, two_desks[0], token, 'double-click-001')
    results = run_parallel(app, [job, job])
    assert [r[0] for r in results] == ['ok', 'ok'], results
    assert sorted(r[1]['replayed'] for r in results) == [False, True]
    assert h.on_hand(app, bid) == 14


def test_desk_routes_flow(app, make_user, make_doctor, desk_client, admin_client):
    med = h.med(app)
    bid = h.batch(app, med, 10)
    rx = h.rx(app, make_user('patient'), make_doctor(), [(med, 4)], requested=False, patient_name='Asha Sharma')
    with app.app_context():
        number = db.session.get(Prescription, rx).number
    desk, base = desk_client[0], admin_client[0]
    assert base.post('/admin/api/dispensing/lookup', json={'number': number}).status_code == 403
    assert base.get('/admin/api/dispensing/queue').status_code == 403
    assert desk.get('/admin/api/dispensing/queue').get_json()['items'] == []
    assert desk.post('/admin/api/dispensing/lookup', json={'number': number[:-1] + 'Z'}).get_json()['error'] in ('bad_number', 'not_found')
    assert desk.post(f'/admin/api/dispensing/{rx}/prepare').status_code == 404  # not queued, not looked up
    assert desk.post('/admin/api/dispensing/lookup', json={'number': number}).get_json()['rx_id'] == rx
    plan = desk.post(f'/admin/api/dispensing/{rx}/prepare', json={}).get_json()
    assert plan['lines'][0]['requested'] == 4 and plan['rx']['patient_name'] == 'Asha Sharma' and plan['expires_in'] == 600
    body = {'token': plan['token'], 'identity_checked': True, 'pharmacist_name': 'Pooja Rao', 'pharmacist_reg_no': 'PH12345'}
    url = f'/admin/api/dispensing/{rx}/confirm'
    assert desk.post(url, json=body).get_json()['error'] == 'idempotency_key_required'
    assert desk.post(url, json=dict(body, identity_checked=False), headers={'Idempotency-Key': 'route-conf-001'}).status_code == 422
    r = desk.post(url, json=body, headers={'Idempotency-Key': 'route-conf-001'})
    assert r.status_code == 200 and r.get_json()['status'] == 'dispensed' and r.get_json()['replayed'] is False
    again = desk.post(url, json=body, headers={'Idempotency-Key': 'route-conf-001'}).get_json()
    assert again['replayed'] is True and h.on_hand(app, bid) == 6
    tx = r.get_json()['lines'][0]['tx_id']
    rev = desk.post(f'/admin/api/dispensing/transactions/{tx}/reverse', headers={'Idempotency-Key': 'route-rev-0001'})
    assert rev.status_code == 200 and rev.get_json()['transaction']['kind'] == 'return' and h.on_hand(app, bid) == 10


def test_queue_route_shows_initials_and_queued_rx_opens_by_id(app, make_user, make_doctor, desk_client):
    med = h.med(app)
    h.batch(app, med, 10)
    rx = h.rx(app, make_user('patient'), make_doctor(), [(med, 2)], patient_name='Asha Sharma')
    desk = desk_client[0]
    items = desk.get('/admin/api/dispensing/queue').get_json()['items']
    assert items[0]['initials'] == 'A. S.' and 'Asha' not in str(items)
    assert desk.post(f'/admin/api/dispensing/{rx}/prepare', json={}).status_code == 200
