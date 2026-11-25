"""Inventory reports: stock, expiring, dispensing log masking, usage suppression below K (design 4.11)."""
from datetime import timedelta

import pytest

from core.extensions import db
from models import AuditLog, InventoryTransaction
from services import dispensing, reports
from tests import inv_helpers as h
from utils.timeutil import ist_today

ID = dict(identity_checked=True, pharmacist_name='Pooja Rao', pharmacist_reg_no='PH12345')


def dispense(app, desk, patient, doctor, med, qty, key):
    rx = h.rx(app, patient, doctor, [(med, qty)], patient_name='Asha Sharma')
    with app.app_context():
        token = dispensing.plan(rx, h.INST, desk)['token']
        dispensing.confirm(rx, h.INST, desk, token, key, **ID)
    return rx


@pytest.fixture
def stocked(app, make_user, make_doctor):
    med = h.med(app)
    h.batch(app, med, 100, 'LIVE', days=200)
    h.batch(app, med, 4, 'SOON', days=20)
    h.batch(app, med, 6, 'DEAD', days=-3)
    return {'med': med, 'desk': make_user('admin', is_pharmacy_desk=True), 'doctor': make_doctor()}


def test_stock_and_expiring_reports(app, stocked):
    with app.app_context():
        assert reports.stock(h.INST) == [{'medicine_id': stocked['med'], 'label': 'TESTAMOL 10 mg tablet', 'usable': 104,
                                          'expired': 6, 'reorder_level': None, 'status': 'in_stock'}]
        soon = reports.expiring(h.INST, 60)
        assert [(r['batch_no'], r['days_left']) for r in soon] == [('DEAD', -3), ('SOON', 20)]
        assert [r['batch_no'] for r in reports.expiring(h.INST, 1)] == ['DEAD']
        assert [r['batch_no'] for r in reports.expiring(h.INST, 9999)] == ['DEAD', 'SOON', 'LIVE']  # days clamp to 365
        assert reports.expiring('other campus', 60) == []


def test_log_masks_number_for_base_admin_and_full_for_desk(app, stocked, make_user):
    dispense(app, stocked['desk'], make_user('patient'), stocked['doctor'], stocked['med'], 3, 'rep-key-00001')
    with app.app_context():
        number = InventoryTransaction.query.filter_by(kind='dispense').one().rx_number
        masked, meta = reports.log(h.INST, masked=True)
        full, _ = reports.log(h.INST, masked=False)
        d = next(r for r in masked if r['kind'] == 'dispense')
        f = next(r for r in full if r['kind'] == 'dispense')
        assert d['rx_number'] == number[:7] + '*' * 8 + number[-3:] and d['dispenser_label'] is None
        assert f['rx_number'] == number and f['dispenser_label'] == 'Pooja Rao, Reg. PH12345'
        assert meta['total'] == 4 and 'Asha' not in str(masked + full)  # 3 opening rows plus the dispense


def test_log_range_is_capped_at_92_days(app, stocked):
    start, end = reports.date_range(ist_today() - timedelta(days=400), ist_today())
    assert (end - start).days == 91
    assert reports.date_range(None, None)[0] == ist_today() - timedelta(days=6)
    assert reports.date_range(ist_today(), ist_today() - timedelta(days=2)) == (ist_today() - timedelta(days=2), ist_today())


def test_usage_suppresses_below_k(app, stocked, make_user, monkeypatch):
    for i in range(2):
        dispense(app, stocked['desk'], make_user('patient'), stocked['doctor'], stocked['med'], 3, f'use-key-{i:05d}')
    with app.app_context():
        rows = reports.usage(h.INST)  # two patients, K = 5
        assert rows == [{'medicine_id': stocked['med'], 'label': 'TESTAMOL 10 mg tablet', 'units': None,
                         'prescriptions': None, 'suppressed': True}]
        assert reports.usage(h.INST, k=2)[0] == {'medicine_id': stocked['med'], 'label': 'TESTAMOL 10 mg tablet',
                                                      'units': 6, 'prescriptions': 2, 'suppressed': False}
    monkeypatch.setenv('MIN_AGGREGATE_GROUP', '2')
    with app.app_context():
        assert reports.usage(h.INST)[0]['units'] == 6


def test_usage_subtracts_reversals(app, stocked, make_user):
    dispense(app, stocked['desk'], make_user('patient'), stocked['doctor'], stocked['med'], 3, 'rev-use-00001')
    with app.app_context():
        line = InventoryTransaction.query.filter_by(kind='dispense').one().id
        dispensing.reverse(line, stocked['desk'], 'rev-use-key-1', institution_key=h.INST)
        assert reports.usage(h.INST, k=1)[0]['units'] == 0


def test_report_routes_and_csv(app, stocked, admin_client, desk_client, make_user):
    dispense(app, stocked['desk'], make_user('patient'), stocked['doctor'], stocked['med'], 3, 'route-rep-0001')
    base, desk = admin_client[0], desk_client[0]
    assert base.get('/admin/api/reports/nope').status_code == 404
    items = base.get('/admin/api/reports/log').get_json()['items']
    assert '*' in next(r['rx_number'] for r in items if r['kind'] == 'dispense')
    assert '*' not in next(r['rx_number'] for r in desk.get('/admin/api/reports/log').get_json()['items'] if r['kind'] == 'dispense')
    assert base.get('/admin/api/reports/stock').get_json()['items'][0]['usable'] == 101
    assert base.get('/admin/api/reports/expiring?days=30').get_json()['items'][1]['batch_no'] == 'SOON'
    assert base.get('/admin/api/reports/usage').get_json()['items'][0]['suppressed'] is True
    csv = base.get('/admin/reports/expiring.csv')
    assert csv.status_code == 200 and csv.data.startswith(b'label,batch_no,expiry_date,quantity,days_left')
    assert 'attachment' in csv.headers['Content-Disposition'] and csv.headers['Cache-Control'] == 'no-store'
    with app.app_context():
        assert AuditLog.query.filter_by(action='export_stock_csv').count() == 1
