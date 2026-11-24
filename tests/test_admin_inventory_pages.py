"""The HTML pages of the catalogue, inventory, dispensing and reports screens render with real data (templates: package B)."""
from pathlib import Path

import pytest

from extensions import db
from models import Prescription
from tests import inv_helpers as h

TEMPLATES = Path(__file__).resolve().parent.parent / 'templates'


def _need(*names):
    missing = [n for n in names if not (TEMPLATES / n).exists()]
    if missing:
        pytest.skip(f'template not written yet: {missing}')


@pytest.fixture
def data(app, make_user, make_doctor):
    med = h.med(app)
    bid = h.batch(app, med, 10)
    rx = h.rx(app, make_user('patient'), make_doctor(), [(med, 2)])
    with app.app_context():
        number = db.session.get(Prescription, rx).number
    return {'med': med, 'batch': bid, 'rx': rx, 'number': number}


@pytest.mark.parametrize('path,template', [
    ('/admin/catalogue', 'admin/catalogue.html'), ('/admin/catalogue/new', 'admin/catalogue_form.html'),
    ('/admin/catalogue/{med}/edit', 'admin/catalogue_form.html'), ('/admin/inventory', 'admin/inventory.html'),
    ('/admin/inventory/batches?medicine_id={med}', 'admin/batches.html'), ('/admin/inventory/receive', 'admin/receive.html'),
    ('/admin/dispensing', 'admin/dispensing.html'), ('/admin/dispensing/{rx}', 'admin/dispensing_detail.html'),
    ('/admin/reports', 'admin/reports.html'), ('/admin/reports?tab=log', 'admin/reports.html'),
])
def test_pages_render_for_the_desk(desk_client, data, path, template):
    _need(template)
    r = desk_client[0].get(path.format(**data))
    assert r.status_code == 200, path


def test_non_desk_admin_sees_inventory_but_not_dispensing(admin_client, data):
    _need('admin/inventory.html')
    assert admin_client[0].get('/admin/inventory').status_code == 200
    for path in ('/admin/dispensing', f"/admin/dispensing/{data['rx']}", '/admin/inventory/receive'):
        assert admin_client[0].get(path).status_code in (302, 403), path


def test_dispensing_print_uses_print_template_and_audits(desk_client, data, app):
    if not (TEMPLATES / 'provider_rx/print.html').exists():
        pytest.skip('print template not written yet')
    r = desk_client[0].get(f"/admin/dispensing/{data['rx']}/print")
    assert r.status_code == 200 and data['number'] in r.get_data(as_text=True)
    with app.app_context():
        from models import AuditLog
        assert AuditLog.query.filter_by(action='rx_print').one().meta == {'by': 'desk'}


def test_unqueued_prescription_page_is_404_until_looked_up(desk_client, make_user, make_doctor, app):
    _need('admin/dispensing_detail.html')
    med = h.med(app, name='Hidden')
    rx = h.rx(app, make_user('patient'), make_doctor(), [(med, 1)], requested=False)
    c = desk_client[0]
    assert c.get(f'/admin/dispensing/{rx}').status_code == 404
    with app.app_context():
        number = db.session.get(Prescription, rx).number
    c.post('/admin/api/dispensing/lookup', json={'number': number})
    assert c.get(f'/admin/dispensing/{rx}').status_code == 200
