"""CSV import and export for the catalogue and stock (design 4.9)."""
import io
from datetime import timedelta

import pytest

from core.extensions import db
from models import InventoryBatch, Medicine
from services import inventory_csv as csvs
from services.errors import ServiceError
from tests import inv_helpers as h
from utils.timeutil import ist_today

HEADER = ','.join(csvs.CATALOGUE_COLUMNS)
STOCK_HEADER = ','.join(csvs.STOCK_COLUMNS)


def cat_csv(*rows):
    return ('\n'.join([HEADER, *rows]) + '\n').encode()


def up(data, dry=None):
    body = {'file': (io.BytesIO(data), 'x.csv')}
    if dry is not None:
        body['dry_run'] = dry
    return body


def test_templates_are_header_only():
    assert csvs.catalogue_template() == HEADER + '\r\n' and csvs.stock_template() == STOCK_HEADER + '\r\n'


def test_catalogue_import_dry_run_and_all_or_nothing(app, admin_client):
    c, _ = admin_client
    good = cat_csv('Testamol,,10 mg,tablet,oral,A,none,Analgesic,true', 'Otherol,Brandx,5 mg,capsule,,,,,')
    r = c.post('/admin/api/catalogue/import', data=up(good), content_type='multipart/form-data')  # dry run is the default
    assert r.status_code == 200 and r.get_json()['dry_run'] is True and r.get_json()['created'] == 2
    with app.app_context():
        assert Medicine.query.count() == 0
    bad = cat_csv('Testamol,,10 mg,tablet,oral,A,none,,true', ',,10 mg,tablet,oral,Q,none,,true', 'Dup,,1 mg,tablet,,,,,', 'dup,,1 mg,tablet,,,,,')
    r = c.post('/admin/api/catalogue/import', data=up(bad, '0'), content_type='multipart/form-data')
    body = r.get_json()
    assert r.status_code == 422 and body['error'] == 'import_invalid'
    assert {(e['row'], e['field']) for e in body['errors']} >= {(3, 'generic_name'), (3, 'tpg_list'), (5, 'generic_name')}
    assert 'Testamol' not in r.get_data(as_text=True)  # cell text is never echoed
    with app.app_context():
        assert Medicine.query.count() == 0  # one bad row rejects the whole file
    assert c.post('/admin/api/catalogue/import', data=up(good, '0'), content_type='multipart/form-data').status_code == 200
    with app.app_context():
        assert Medicine.query.count() == 2


def test_catalogue_import_never_verifies_and_resets_changed_classification(app, admin_client, make_user):
    c, admin = admin_client
    mid = h.med(app, name='Testamol')  # verified, list O
    with app.app_context():
        m = db.session.get(Medicine, mid)
        keep = Medicine.query.count()
    data = cat_csv('Testamol,,10 mg,tablet,oral,A,none,,true', 'Freshol,,5 mg,tablet,,,,,')  # list O -> A; empty list -> C
    assert c.post('/admin/api/catalogue/import', data=up(data, '0'), content_type='multipart/form-data').status_code == 200
    with app.app_context():
        changed = db.session.get(Medicine, mid)
        fresh = Medicine.query.filter_by(generic_key='freshol').one()
        assert changed.tpg_list == 'A' and changed.list_verified_at is None and changed.updated_by == admin
        assert fresh.tpg_list == 'C' and fresh.list_verified_at is None and fresh.is_demo is False and keep == 1


def test_catalogue_import_limits_header_bom_and_size(app, admin_client):
    c, _ = admin_client
    post = lambda data: c.post('/admin/api/catalogue/import', data=up(data), content_type='multipart/form-data')  # noqa: E731
    assert post(b'wrong,header\n1,2\n').get_json()['errors'][0]['code'] == 'bad_header'
    assert post(('﻿' + HEADER + '\nTestamol,,10 mg,tablet,,,,,\n').encode('utf-8')).status_code == 200  # BOM tolerated
    assert post(b'\xff\xfe\x00').status_code == 422
    many = cat_csv(*[f'M{i},,1 mg,tablet,,,,,' for i in range(2001)])
    assert post(many).status_code == 413
    assert post(b'x' * 1_100_000).status_code == 413


def test_csv_export_escapes_formula_injection(app, admin_client):
    c, _ = admin_client
    h.med(app, name='=HYPERLINK("http://x")', strength='+1 mg')
    text = c.get('/admin/catalogue.csv').get_data(as_text=True)
    assert text.startswith(HEADER) and "'=HYPERLINK" in text and "'+1 mg" in text
    assert c.get('/admin/catalogue.csv').headers['Content-Disposition'].startswith('attachment')
    assert c.get('/admin/catalogue.csv').headers['Cache-Control'] == 'no-store'
    assert csvs.safe_cell('@x') == "'@x" and csvs.safe_cell('-5') == "'-5" and csvs.safe_cell('ok') == 'ok'


def stock_csv(*rows):
    return ('\n'.join([STOCK_HEADER, *rows]) + '\n').encode()


def test_stock_import_dry_run_import_and_duplicate_file_rejected(app, desk_client):
    c, _ = desk_client
    h.med(app, name='Testamol', strength='10 mg')
    ok_date = (ist_today() + timedelta(days=200)).isoformat()
    data = stock_csv(f'Testamol,,10 mg,tablet,B1,{ok_date},40,1.50,ACME', f'Testamol,,10 mg,tablet,B2,{ok_date},10,,')
    r = c.post('/admin/api/inventory/import', data=up(data), content_type='multipart/form-data')
    assert r.status_code == 200 and r.get_json()['rows'] == 2
    with app.app_context():
        assert InventoryBatch.query.count() == 0  # dry run writes nothing
    r = c.post('/admin/api/inventory/import', data=up(data, '0'), content_type='multipart/form-data')
    assert r.status_code == 200
    with app.app_context():
        assert sorted(b.quantity_on_hand for b in InventoryBatch.query) == [10, 40]
    r = c.post('/admin/api/inventory/import', data=up(data, '0'), content_type='multipart/form-data')
    assert r.status_code == 409 and r.get_json()['error'] == 'import_duplicate'  # same file twice never doubles stock
    with app.app_context():
        assert sum(b.quantity_on_hand for b in InventoryBatch.query) == 50


def test_stock_import_rejects_bad_rows_all_or_nothing(app, desk_client):
    c, _ = desk_client
    h.med(app, name='Testamol', strength='10 mg')
    h.med(app, name='Strongol', strength='1 mg', schedule='X')
    ok_date = (ist_today() + timedelta(days=200)).isoformat()
    past = (ist_today() - timedelta(days=1)).isoformat()
    data = stock_csv(f'Testamol,,10 mg,tablet,B1,{ok_date},40,,', f'Nothing,,1 mg,tablet,B1,{ok_date},1,,',
                     f'Strongol,,1 mg,tablet,B1,{ok_date},1,,', f'Testamol,,10 mg,tablet,B3,{past},5,,',
                     'Testamol,,10 mg,tablet,B4,2030-01,5,,', f'Testamol,,10 mg,tablet,B5,{ok_date},0,,')
    r = c.post('/admin/api/inventory/import', data=up(data, '0'), content_type='multipart/form-data')
    codes = {(e['row'], e['code']) for e in r.get_json()['errors']}
    assert r.status_code == 422 and {(3, 'unknown_medicine'), (4, 'controlled_not_stocked')} <= codes
    with app.app_context():
        assert InventoryBatch.query.count() == 0
    dry = c.post('/admin/api/inventory/import', data=up(stock_csv(f'Testamol,,10 mg,tablet,B3,{past},5,,')),
                 content_type='multipart/form-data')
    assert dry.status_code == 422 and dry.get_json()['errors'][0]['code'] == 'already_expired'


def test_import_needs_desk_and_stock_export(app, admin_client, desk_client):
    mid = h.med(app)
    h.batch(app, mid, 7)
    assert admin_client[0].post('/admin/api/inventory/import', data=up(b''), content_type='multipart/form-data').status_code == 403
    out = admin_client[0].get('/admin/inventory/stock.csv')  # any admin may export stock (read only)
    assert out.status_code == 200 and 'TESTAMOL 10 mg tablet' in out.get_data(as_text=True)
    assert desk_client[0].get('/admin/inventory/template.csv').get_data(as_text=True).strip() == STOCK_HEADER
    with pytest.raises(ServiceError):
        csvs.parse(b'a,b\n', csvs.STOCK_COLUMNS)
