"""Admin and provider prescribing screens: every template renders with sample context (empty and populated), and the new
static files follow the project rules. Needs no routes or services (docs/CLINICAL_DESIGN.md 5.7, "UI (B)")."""
import os
import re
import shutil
import subprocess
from html.parser import HTMLParser

import pytest
from flask import render_template, session

import clinical_samples_admin as ADM
import clinical_samples_rx as RXS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES = {**ADM.CASES, **RXS.CASES}
PARAMS = [(t, c) for t, cases in CASES.items() for c in cases]
NEW_JS = [f for f in os.listdir(os.path.join(ROOT, 'static/js')) if re.match(r'(admin_|rx_prescribe|rx_list|rx_detail|rx_dashboard|clinical-common)', f)]
NEW_FILES = ([os.path.join('static/js', f) for f in NEW_JS] + ['static/css/clinical.css', 'tests/clinical_samples_admin.py', 'tests/clinical_samples_rx.py']
             + [os.path.join('templates', d, f) for d in ('admin', 'provider_rx') for f in os.listdir(os.path.join(ROOT, 'templates', d))])
LIST_PAGES = ['admin/staff.html', 'admin/verification.html', 'admin/catalogue.html', 'admin/inventory.html', 'admin/batches.html',
              'admin/dispensing.html', 'admin/audit.html', 'admin/messages.html', 'admin/annual.html']


def render(app, template, ctx):
    role = 'admin' if template.startswith('admin/') else 'provider'
    with app.test_request_context('/clinical-test'):
        session.update(user_email='x@example.org', user_role=role, user_name='Test User', user_id=1)
        return render_template(template, **ctx)


class _Buttons(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack, self.bad = [], []

    def handle_starttag(self, tag, attrs):
        if tag == 'button':
            a = dict(attrs)
            self.stack.append({'a': a, 'text': ''})
            if 'type' not in a:
                self.bad.append('button without type')

    def handle_data(self, data):
        if self.stack:
            self.stack[-1]['text'] += data.strip()

    def handle_endtag(self, tag):
        if tag == 'button' and self.stack:
            b = self.stack.pop()
            if not b['text'] and not b['a'].get('aria-label') and not b['a'].get('aria-labelledby'):
                self.bad.append(f"unlabelled button {b['a']}")


@pytest.mark.parametrize('template,case', PARAMS)
def test_templates_render_with_sample_context(app, template, case):
    html = render(app, template, CASES[template][case])
    assert html.strip()
    assert '{{' not in html and '{%' not in html
    assert '—' not in html
    if template.endswith('_dashboard_section.html') or template.startswith('admin/') or template.startswith('provider_rx/'):
        parser = _Buttons()
        parser.feed(html)
        assert not parser.bad, parser.bad


@pytest.mark.parametrize('template', LIST_PAGES)
def test_empty_states_present(app, template):
    html = render(app, template, CASES[template]['empty'])
    assert 'empty-state' in html, template


def test_standing_notices_on_prescribing_and_admin_medicine_pages(app):
    for t in ('provider_rx/prescribe.html', 'provider_rx/list.html', 'provider_rx/detail.html', 'admin/catalogue.html',
              'admin/inventory.html', 'admin/dispensing.html', 'admin/reports.html', 'admin/verification.html'):
        html = render(app, t, CASES[t].get('full') or CASES[t]['empty'])
        assert 'Legal and pharmacist review' in html and 'does not check drug interactions' in html, t


def test_dashboard_section_states_and_hidden_for_others(app):
    texts = {'pending': 'Your registration is waiting for an administrator to check it. You cannot prescribe yet.',
             'rejected': 'Your registration was not accepted. Check the details and send them again.',
             'suspended': 'Prescribing is switched off for your account. Contact your administrator.',
             'lapsed': 'Your registration check has expired. An administrator needs to check it again.',
             'verified': 'Verified until'}
    for state, text in texts.items():
        html = render(app, 'provider_rx/_dashboard_section.html', RXS.CASES['provider_rx/_dashboard_section.html'][state])
        assert text in html and 'id="rx-consults"' in html
        assert ('href="/provider/prescribe"' in html) == (state == 'verified')
    assert render(app, 'provider_rx/_dashboard_section.html', {'rx_section': {'show': False}}).strip() == ''
    assert render(app, 'provider_rx/_dashboard_section.html', {}).strip() == ''


def test_prescribe_page_carries_contract_text_and_config(app):
    html = render(app, 'provider_rx/prescribe.html', RXS.CASES['provider_rx/prescribe.html']['full'])
    for s in ('It is not a drug interaction check.', 'Same condition as the previous in-person consult', 'id="page-config"',
              'id="med-q"',
              'id="rv-issue"', 'aria-live="polite"'):
        assert s in html, s
    assert 'SECRET_KEY' not in html and 'test-secret-key' not in html   # the Flask `config` global must never be dumped


def test_print_sheet_content_and_banners(app):
    cases = RXS.CASES['provider_rx/print.html']
    html = render(app, 'provider_rx/print.html', cases['full'])
    for s in ('MH12345', 'Maharashtra Medical Council', 'Test University', 'RX2611-7K3M9QX4PD2', 'e-prescription', 'ESCITALOPRAM 10 mg tablet',
              'This document has no handwritten or digital signature', 'https://example.org/rx/RX2611-7K3M9QX4PD2', 'no-print'):
        assert s in html, s
    assert 'rx-banner' not in html
    assert 'CANCELLED' in render(app, 'provider_rx/print.html', cases['cancelled'])
    assert 'EXPIRED' in render(app, 'provider_rx/print.html', cases['expired'])


def test_admin_nav_and_provider_nav(app, monkeypatch):
    monkeypatch.setenv('ENABLE_PRESCRIPTIONS', '1')
    full = render(app, 'admin/dashboard.html', ADM.CASES['admin/dashboard.html']['full'])
    assert 'Verification' in full and 'Audit log' in full and 'Dispensing' in full
    nodesk = render(app, 'admin/dashboard.html', ADM.CASES['admin/dashboard.html']['full_nodesk'])
    assert 'Dispensing' not in nodesk and 'Inventory' in nodesk
    nav = render(app, 'provider_rx/list.html', dict(RXS.CASES['provider_rx/list.html']['full'], rx_section={'show': True}))
    assert 'Prescriptions</span>' in nav
    assert 'Prescriptions</span>' not in render(app, 'provider_rx/list.html', RXS.CASES['provider_rx/list.html']['full'])


def test_admin_pages_show_no_patient_identity(app):
    secret = 'A. Student'
    for t, cases in ADM.CASES.items():
        if t == 'admin/dispensing_detail.html':
            continue
        for c, ctx in cases.items():
            assert secret not in render(app, t, ctx), (t, c)


@pytest.mark.parametrize('rel', NEW_FILES)
def test_no_emoji_no_em_dash_and_size_limit(rel):
    text = open(os.path.join(ROOT, rel), encoding='utf-8').read()
    assert text.count('\n') + 1 <= 300, f'{rel} is over 300 lines'
    assert '—' not in text and not re.search(r'[\U0001F000-\U0001FAFF☀-➿]', text), rel


@pytest.mark.parametrize('rel', [f for f in NEW_FILES if f.startswith('templates')])
def test_templates_have_no_inline_handlers_or_scripts(rel):
    text = open(os.path.join(ROOT, rel), encoding='utf-8').read()
    assert not re.search(r'\son[a-z]+\s*=\s*["\']', text), 'inline event handler'
    for tag in re.findall(r'<script\b[^>]*>', text):
        assert 'src=' in tag or 'application/json' in tag, tag
    assert not re.search(r'\b(bg|text|border)-(gray|slate|red|green|blue|purple|indigo|pink)-\d', text)


@pytest.mark.parametrize('name', NEW_JS)
def test_no_jinja_in_new_js(name):
    text = open(os.path.join(ROOT, 'static/js', name), encoding='utf-8').read()
    assert '{{' not in text and '{%' not in text
    assert 'innerHTML' not in text and 'on' + 'click=' not in text


@pytest.mark.skipif(not shutil.which('node'), reason='node is not installed')
@pytest.mark.parametrize('name', NEW_JS)
def test_node_check_js(name):
    r = subprocess.run(['node', '--check', os.path.join(ROOT, 'static/js', name)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
