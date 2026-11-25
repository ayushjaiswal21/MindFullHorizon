"""Content-Security-Policy: enforcing, strict, and no page depends on inline code (docs/SECURITY.md)."""
import os
import re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HANDLER = re.compile(r'<[a-zA-Z][^>]*\son[a-z]+\s*=', re.S)
STYLE_ATTR = re.compile(r'<[a-zA-Z][^>]*\sstyle\s*=', re.S)
SCRIPT = re.compile(r'<script\b([^>]*)>', re.S)
JS_URL = re.compile(r'(?:href|src|action|formaction)\s*=\s*["\']\s*javascript:', re.I)
EXTERNAL = re.compile(r"""<(?:script|iframe|img|source|audio|video)[^>]*\ssrc=["'](https?://[^"']+)|<link[^>]*rel=["']stylesheet["'][^>]*href=["'](https?://[^"']+)""", re.S)
SKIP_RULES = ('logout', 'static', 'download', 'export', '/api/', 'csp-report', '/login/google')


def directives(response):
    header = response.headers['Content-Security-Policy']
    return {p.split()[0]: p.split()[1:] for p in (x.strip() for x in header.split(';')) if p}


def test_header_is_enforcing_on_public_page_error_page_and_json(client):
    for path in ('/login', '/', '/no-such-page-xyz', '/health'):
        r = client.get(path)
        assert 'Content-Security-Policy' in r.headers, path
        assert 'Content-Security-Policy-Report-Only' not in r.headers, path


def test_header_on_logged_in_and_admin_pages(patient_client, admin_client):
    for c, path in ((patient_client[0], '/patient/dashboard'), (admin_client[0], '/admin/dashboard')):
        r = c.get(path)
        assert r.status_code == 200
        assert 'Content-Security-Policy' in r.headers and 'Content-Security-Policy-Report-Only' not in r.headers


def test_every_directive_present_and_strict(client):
    d = directives(client.get('/login'))
    assert d['default-src'] == ["'self'"]
    assert d['object-src'] == ["'none'"] and d['frame-ancestors'] == ["'none'"]
    assert d['base-uri'] == ["'self'"] and d['form-action'] == ["'self'"]
    assert d['font-src'] == ["'self'"] and d['style-src-attr'] == ["'none'"]
    assert d['img-src'] == ["'self'", 'data:', 'https://i.ytimg.com']
    assert d['frame-src'] == ['https://www.youtube-nocookie.com']
    assert d['media-src'][:2] == ["'self'", 'blob:'] and "'self'" in d['connect-src']
    assert any(v.startswith('wss://') for v in d['connect-src'])
    assert d['report-uri'] == ['/csp-report']
    for name in ('script-src', 'style-src'):
        assert d[name][0] == "'self'" and d[name][1].startswith("'nonce-")
        assert len(d[name]) == 2  # no CDN, no unsafe-*: libraries are vendored in static/vendor
    blob = ' '.join(' '.join(v) for v in d.values())
    assert 'unsafe-inline' not in blob and 'unsafe-eval' not in blob and 'unsafe-hashes' not in blob
    assert 'upgrade-insecure-requests' not in d  # production only


def test_headers_other_than_csp(client):
    r = client.get('/login')
    assert r.headers['Cross-Origin-Opener-Policy'] == 'same-origin'
    assert r.headers['X-Content-Type-Options'] == 'nosniff'
    assert 'microphone=(self)' in r.headers['Permissions-Policy'] and 'camera=(self)' in r.headers['Permissions-Policy']
    assert 'Strict-Transport-Security' not in r.headers


def test_production_adds_hsts_and_upgrade(client, monkeypatch):
    monkeypatch.setenv('FLASK_ENV', 'production')
    r = client.get('/login')
    assert 'Strict-Transport-Security' in r.headers
    assert 'upgrade-insecure-requests' in directives(r)
    assert not any(v.startswith('ws://') for v in directives(r)['connect-src'])


def test_audio_base_url_origin_in_media_src(client, monkeypatch):
    monkeypatch.setenv('AUDIO_BASE_URL', 'https://audio.example.com/tracks/')
    assert 'https://audio.example.com' in directives(client.get('/login'))['media-src']


def test_report_only_fallback_switch(client, monkeypatch):
    monkeypatch.setenv('CSP_REPORT_ONLY', '1')
    h = client.get('/login').headers
    assert 'Content-Security-Policy-Report-Only' in h and 'Content-Security-Policy' not in h


def test_nonce_changes_per_request_and_is_on_inline_scripts(client):
    seen = []
    for _ in range(2):
        r = client.get('/login')
        nonce = directives(r)['script-src'][1][len("'nonce-"):-1]
        html = r.get_data(as_text=True)
        assert f'nonce="{nonce}"' in html
        seen.append(nonce)
        for attrs in SCRIPT.findall(html):
            if 'src=' not in attrs and 'application/' not in attrs:
                assert f'nonce="{nonce}"' in attrs
    assert seen[0] != seen[1]


def test_csp_report_endpoint_logs_directive_only(client, caplog):
    body = '{"csp-report": {"blocked-uri": "https://evil.example/x?secret=1", "effective-directive": "script-src"}}'
    with caplog.at_level('WARNING'):
        r = client.post('/csp-report', data=body, content_type='application/csp-report')
    assert r.status_code == 204
    assert 'script-src' in caplog.text and 'https://evil.example' in caplog.text and 'secret=1' not in caplog.text
    assert client.post('/csp-report', data='not json').status_code == 204


def _rules(app):
    for rule in app.url_map.iter_rules():
        if 'GET' in rule.methods and not rule.arguments and not any(s in rule.rule for s in SKIP_RULES):
            yield rule.rule


def _check_html(path, html, findings):
    if HANDLER.search(html):
        findings.append(f'{path}: inline on*= handler')
    if STYLE_ATTR.search(html):
        findings.append(f'{path}: inline style= attribute')
    if JS_URL.search(html):
        findings.append(f'{path}: javascript: URL')
    for attrs in SCRIPT.findall(html):
        if 'src=' not in attrs and 'nonce=' not in attrs and 'application/' not in attrs:
            findings.append(f'{path}: inline <script> without nonce')
    for url in (u for pair in EXTERNAL.findall(html) for u in pair if u):
        if not url.startswith(('https://i.ytimg.com/', 'https://www.youtube-nocookie.com/')):
            findings.append(f'{path}: external resource {url}')


def test_no_inline_code_across_the_url_map(app, client, patient_client, provider_client, doctor_client, admin_client):
    findings, pages = [], 0
    for c in (client, patient_client[0], provider_client[0], doctor_client[0], admin_client[0]):
        for path in _rules(app):
            r = c.get(path)
            if r.status_code == 200 and r.mimetype == 'text/html':
                pages += 1
                _check_html(path, r.get_data(as_text=True), findings)
    assert pages > 40
    assert not findings, '\n'.join(sorted(set(findings)))




def test_prescription_pages_have_no_inline_code(app, doctor_client, patient_client, desk_client):
    from tests.rx_helpers import consent_row, make_medicine, make_rx
    doctor, patient = doctor_client[1], patient_client[1]
    consent_row(app, patient)
    rx = make_rx(app, doctor, patient, make_medicine(app), requested=True)
    findings = []
    for c, path in ((patient_client[0], f'/patient/prescriptions/{rx}'), (patient_client[0], f'/patient/prescriptions/{rx}/print'),
                    (doctor_client[0], f'/provider/prescriptions/{rx}'), (doctor_client[0], f'/provider/prescriptions/{rx}/print'),
                    (desk_client[0], f'/admin/dispensing/{rx}'), (desk_client[0], f'/admin/dispensing/{rx}/print')):
        r = c.get(path)
        assert r.status_code == 200, path
        _check_html(path, r.get_data(as_text=True), findings)
    assert not findings, '\n'.join(findings)


def test_static_js_does_not_build_inline_handlers_or_styles():
    bad = re.compile(r"""\son(?:click|change|submit|input|load|error|keydown|keyup)\s*=\s*\?["']|\sstyle\s*=\s*\?["']|javascript:""")
    findings = []
    for dirpath, _, files in os.walk(os.path.join(ROOT, 'static', 'js')):
        for f in files:
            if f.endswith('.js'):
                for n, line in enumerate(open(os.path.join(dirpath, f), encoding='utf-8'), 1):
                    if bad.search(line):
                        findings.append(f'{f}:{n}: {line.strip()[:90]}')
    assert not findings, '\n'.join(findings)


def test_vendored_libraries_exist_with_licences():
    for f in ('chart.umd.min.js', 'chart.LICENSE.md', 'socket.io.min.js', 'socket.io.LICENSE'):
        assert os.path.getsize(os.path.join(ROOT, 'static', 'vendor', f)) > 500
