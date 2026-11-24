"""Inventory: receiving, adjusting, write-off, quarantine, reorder, reconcile, availability, routes (design 4.1 to 4.5)."""
import re
from datetime import timedelta
from pathlib import Path

import pytest

from extensions import db
from models import AuditLog, InventoryBatch, InventoryTransaction
from services import inventory
from services.errors import ServiceError
from tests import inv_helpers as h
from utils.timeutil import ist_today

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def desk(make_user):
    return make_user('admin', is_pharmacy_desk=True)


def _recv(app, desk, mid, qty=50, key='k-recv-0001', days=100, batch_no='B1', **kw):
    with app.app_context():
        tx = inventory.receive(h.INST, mid, batch_no, ist_today() + timedelta(days=days), qty, desk, key, **kw)
        db.session.commit()
        return tx.id


def test_receive_creates_batch_and_ledger_in_one_tx(app, desk):
    mid = h.med(app)
    tx_id = _recv(app, desk, mid, 50, supplier='ACME', unit_cost='1.25')
    with app.app_context():
        b = InventoryBatch.query.one()
        tx = db.session.get(InventoryTransaction, tx_id)
        assert (b.quantity_on_hand, b.status, b.supplier) == (50, 'active', 'ACME')
        assert (tx.delta, tx.kind, tx.reason_code, tx.batch_id) == (50, 'receive', 'purchase', b.id)
        assert inventory.reconcile(h.INST) == []
        assert AuditLog.query.filter_by(action='stock_receive').one().meta == {'delta': 50, 'reason_code': 'purchase'}


def test_receive_tops_up_existing_batch_and_replays_by_key(app, desk):
    mid = h.med(app)
    first = _recv(app, desk, mid, 50)
    assert _recv(app, desk, mid, 50) == first  # same key: replay, no double count
    _recv(app, desk, mid, 20, key='k-recv-0002')
    with app.app_context():
        assert InventoryBatch.query.count() == 1 and InventoryBatch.query.one().quantity_on_hand == 70
        assert InventoryTransaction.query.count() == 2 and inventory.reconcile(h.INST) == []


def test_receive_rejects_expired_controlled_inactive_and_bad_input(app, desk):
    ok, ctl = h.med(app), h.med(app, name='Strongol', schedule='X')
    off = h.med(app, name='Offol', active=False)
    cases = [(ok, 0, 100, 'validation'), (ok, 5, 0, 'already_expired'), (ok, 5, -3, 'already_expired'),
             (ctl, 5, 100, 'controlled_not_stocked'), (off, 5, 100, 'medicine_inactive'), (9999, 5, 100, 'not_found')]
    with app.app_context():
        for i, (mid, qty, days, code) in enumerate(cases):
            with pytest.raises(ServiceError) as e:
                inventory.receive(h.INST, mid, 'B1', ist_today() + timedelta(days=days), qty, desk, f'k-bad-{i:04d}')
            assert e.value.code == code, (mid, qty, days)
            db.session.rollback()
        with pytest.raises(ServiceError) as e:
            inventory.receive(h.INST, ok, 'B1', '2030-01', 5, desk, 'k-bad-month')  # month-only dates are ambiguous
        assert e.value.code == 'validation'
        assert InventoryBatch.query.count() == 0


def test_adjust_requires_reason_and_stays_nonnegative(app, desk):
    mid = h.med(app)
    bid = h.batch(app, mid, 10)
    with app.app_context():
        for delta, reason, code in ((-11, 'lost', 'would_go_negative'), (-1, 'because', 'bad_reason'), (0, 'lost', 'validation')):
            with pytest.raises(ServiceError) as e:
                inventory.adjust(bid, delta, reason, desk, 'k-adj-0001', institution_key=h.INST)
            assert e.value.code == code
            db.session.rollback()
        inventory.adjust(bid, -4, 'damaged', desk, 'k-adj-0002', institution_key=h.INST)
        inventory.adjust(bid, -4, 'damaged', desk, 'k-adj-0002', institution_key=h.INST)  # replay
        db.session.commit()
    assert h.on_hand(app, bid) == 6
    with app.app_context():
        assert inventory.reconcile(h.INST) == []


def test_writeoff_only_expired(app, desk):
    mid = h.med(app)
    live, dead = h.batch(app, mid, 10, 'LIVE', days=30), h.batch(app, mid, 7, 'DEAD', days=-1)
    with app.app_context():
        with pytest.raises(ServiceError) as e:
            inventory.write_off_expired(live, desk, 'k-wo-0001', institution_key=h.INST)
        assert e.value.code == 'not_expired'
        tx = inventory.write_off_expired(dead, desk, 'k-wo-0002', institution_key=h.INST)
        db.session.commit()
        assert (tx.kind, tx.delta, tx.reason_code) == ('expire', -7, 'expired_writeoff')
        b = db.session.get(InventoryBatch, dead)
        assert (b.quantity_on_hand, b.status) == (0, 'closed')
        assert inventory.alert_counts(h.INST)['awaiting_writeoff'] == 0


def test_quarantine_skips_allocation(app, desk):
    mid = h.med(app)
    bid = h.batch(app, mid, 10)
    with app.app_context():
        assert inventory.usable_batches(h.INST, mid).count() == 1
        inventory.set_quarantine(bid, True, desk, institution_key=h.INST)
        assert inventory.usable_batches(h.INST, mid).count() == 0
        assert inventory.availability(h.INST, [(mid, 0)])[mid]['status'] == 'out'
        inventory.set_quarantine(bid, False, desk, institution_key=h.INST)
        assert inventory.usable_batches(h.INST, mid).count() == 1


def test_reconcile_detects_mismatch_and_never_fixes(app):
    mid = h.med(app)
    bid = h.batch(app, mid, 10)
    with app.app_context():
        db.session.execute(db.text('UPDATE inventory_batches SET quantity_on_hand = 12'))
        db.session.commit()
        assert inventory.reconcile(h.INST) == [{'batch_id': bid, 'on_hand': 12, 'ledger_sum': 10}]
        assert db.session.get(InventoryBatch, bid).quantity_on_hand == 12


def test_reorder_rule_crud_and_availability_badges(app, desk):
    mid, other = h.med(app), h.med(app, name='Otherol')
    h.batch(app, mid, 20)
    with app.app_context():
        assert inventory.availability(h.INST, [(mid, 5), (mid, 30), (other, 0)]) == {
            mid: {'status': 'low', 'on_hand': 20}, other: {'status': 'out', 'on_hand': 0}}  # 30 wanted, 20 usable
        assert inventory.availability(h.INST, [(mid, 5)])[mid]['status'] == 'in_stock'
        inventory.set_reorder_level(h.INST, mid, 25, desk)
        inventory.set_reorder_level(h.INST, mid, 30, desk)
        db.session.commit()
        assert inventory.availability(h.INST, [(mid, 5)])[mid]['status'] == 'low'
        rows, _ = inventory.stock_levels(h.INST)
        assert rows == [{'medicine_id': mid, 'label': 'TESTAMOL 10 mg tablet', 'usable': 20, 'expired': 0,
                         'reorder_level': 30, 'status': 'low'}]
        assert inventory.alert_counts(h.INST) == {'low': 1, 'out': 0, 'near_expiry': 0, 'awaiting_writeoff': 0}


def test_institution_isolation(app, desk, make_user):
    mid = h.med(app)
    h.batch(app, mid, 10, inst='other campus')
    bid = h.batch(app, mid, 5, 'B2')
    with app.app_context():
        assert inventory.availability(h.INST, [(mid, 0)])[mid]['on_hand'] == 5
        other = InventoryBatch.query.filter_by(institution_key='other campus').one().id
        with pytest.raises(ServiceError) as e:
            inventory.adjust(other, -1, 'lost', desk, 'k-iso-0001', institution_key=h.INST)
        assert e.value.http == 404 and bid != other


def test_ledger_never_updated_or_deleted_in_code():
    pattern = re.compile(r'(update|delete)\(\s*InventoryTransaction|InventoryTransaction[^\n]*\.(update|delete)\(')
    for folder in ('routes', 'services'):
        for path in (ROOT / folder).rglob('*.py'):
            assert not pattern.search(path.read_text(encoding='utf-8')), path


def test_routes_desk_writes_and_non_desk_read_only(app, admin_client, desk_client):
    mid = h.med(app)
    body = {'medicine_id': mid, 'batch_no': 'B9', 'expiry_date': (ist_today() + timedelta(days=90)).isoformat(), 'quantity': 25}
    base, desk_c = admin_client[0], desk_client[0]
    assert base.post('/admin/api/inventory/receive', json=body, headers={'Idempotency-Key': 'route-key-0001'}).status_code == 403
    assert desk_c.post('/admin/api/inventory/receive', json=body).get_json()['error'] == 'idempotency_key_required'
    r = desk_c.post('/admin/api/inventory/receive', json=body, headers={'Idempotency-Key': 'route-key-0001'})
    assert r.status_code == 201 and r.get_json()['transaction']['delta'] == 25
    stock = base.get('/admin/api/inventory/stock').get_json()  # read-only admin sees both numbers
    assert stock['items'][0]['usable'] == 25 and stock['stats']['out'] == 0
    batch = base.get('/admin/api/inventory/batches').get_json()['items'][0]
    assert batch['batch_no'] == 'B9' and batch['days_left'] == 90
    assert desk_c.put(f'/admin/api/inventory/reorder/{mid}', json={'reorder_level': 30}).get_json()['reorder_level'] == 30
    assert base.put(f'/admin/api/inventory/reorder/{mid}', json={'reorder_level': 1}).status_code == 403
    adj = desk_c.post(f"/admin/api/inventory/batches/{batch['id']}/adjust", json={'delta': -5, 'reason_code': 'lost'},
                      headers={'Idempotency-Key': 'route-key-0002'})
    assert adj.status_code == 200
    assert desk_c.post(f"/admin/api/inventory/batches/{batch['id']}/adjust", json={'delta': -99, 'reason_code': 'lost'},
                       headers={'Idempotency-Key': 'route-key-0003'}).get_json()['error'] == 'would_go_negative'
    assert desk_c.post(f"/admin/api/inventory/batches/{batch['id']}/quarantine", json={'on': True}).get_json()['status'] == 'quarantined'
    assert base.get('/admin/api/inventory/stock?status=out').get_json()['items'][0]['usable'] == 0
