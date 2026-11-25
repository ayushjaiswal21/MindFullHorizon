"""Public pages (about, faq, contact, privacy, terms) and the auth page markup."""
import html
import json
import logging
import re
import shutil
import subprocess
import time

import pytest

from core.extensions import db
from models import ContactMessage, Job
from routes import pages

PUBLIC = ['/about', '/faq', '/contact', '/privacy', '/terms']
SECRET_TEXT = 'zebra-crossing-secret-body-4471'


def _ld_blocks(body):
    return [json.loads(m) for m in re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', body, re.S)]


@pytest.mark.parametrize('url', PUBLIC)
def test_public_page_basics(client, url):
    r = client.get(url)
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert re.search(r'<title>[^<]{3,}</title>', body)
    assert re.search(r'<meta name="description" content="[^"]{20,}"', body)
    assert 'rel="canonical"' in body
    assert 'index, follow' in body
    assert len(re.findall(r'<h1[\s>]', body)) == 1
    assert any(b.get('@type') == 'BreadcrumbList' for b in _ld_blocks(body))
    assert '—' not in body  # no em dashes


def test_faq_jsonld_matches_visible_questions(client):
    body = client.get('/faq').get_data(as_text=True)
    faq = [b for b in _ld_blocks(body) if b.get('@type') == 'FAQPage']
    assert len(faq) == 1
    asked = [q['name'] for q in faq[0]['mainEntity']]
    # only the FAQ list: the consent banner in base.html also uses a <details><summary> ("More detail")
    faq_list = re.search(r'<div class="mfh-accordion[^>]*>(.*?)</main>', body, re.S).group(1)
    visible = [html.unescape(s.strip()) for s in re.findall(r'<summary>(.*?)</summary>', faq_list, re.S)]
    assert asked == visible
    assert 10 <= len(asked) <= 12
    assert '/account/data' in body


def test_faq_helplines_come_from_config(client):
    from utils.helplines import HELPLINES
    body = client.get('/faq').get_data(as_text=True)
    for h in HELPLINES:
        assert h['number'] in body


@pytest.mark.parametrize('url', ['/privacy', '/terms'])
def test_legal_pages_have_draft_notice_and_version(client, url, monkeypatch):
    monkeypatch.delenv('CONSENT_VERSION', raising=False)
    body = client.get(url).get_data(as_text=True)
    assert 'Draft pending legal review' in body
    assert 'Version 2026-11' in body
    assert 'class="toc"' in body and 'href="#' in body
    assert 'class="prose"' in body


def test_privacy_placeholders_when_env_unset(client, monkeypatch):
    for k in ('GRIEVANCE_EMAIL', 'DATA_FIDUCIARY_NAME'):
        monkeypatch.delenv(k, raising=False)
    body = client.get('/privacy').get_data(as_text=True)
    assert '[to be set by the operator]' in body
    monkeypatch.setenv('GRIEVANCE_EMAIL', 'grievance@example.org')
    assert 'grievance@example.org' in client.get('/privacy').get_data(as_text=True)


def test_privacy_makes_no_false_claims(client):
    body = client.get('/privacy').get_data(as_text=True).lower()
    assert 'hipaa' in body and 'make no claim' in body  # mentioned only to disclaim
    # O-04/D-19: clinical free text is encrypted at rest, but the operator's key can still read it
    # (not end-to-end encryption, no certification claim) and some fields are still plaintext.
    assert 'encrypted at rest in the database' in body
    assert 'not yet encrypted' in body
    assert 'key the operator holds' in body


# ---------- contact ----------
def _form(client):
    body = client.get('/contact').get_data(as_text=True)
    token = re.search(r'name="form_token" value="([^"]+)"', body).group(1)
    return {'name': 'Asha', 'email': 'asha@example.com', 'subject': '', 'message': f'Hello team, {SECRET_TEXT}',
            'website': '', 'form_token': token}


@pytest.fixture
def slow(monkeypatch):
    """Pretend 10 seconds passed since the form was rendered."""
    monkeypatch.setattr(pages, '_now', lambda: time.time() + 10)


def _count(model, app):
    with app.app_context():
        return model.query.count()


def test_contact_get_has_form_fields(client):
    body = client.get('/contact').get_data(as_text=True)
    for name in ('name', 'email', 'subject', 'message', 'website', 'form_token'):
        assert f'name="{name}"' in body
    assert 'Response time' in body and '14416' in body
    assert 'cannot answer crisis messages' in body


def test_contact_prefills_logged_in_user(patient_client):
    c, _ = patient_client
    body = c.get('/contact').get_data(as_text=True)
    assert 'patient1@test.local' in body


def test_contact_email_shown_only_if_configured(client, monkeypatch):
    monkeypatch.delenv('CONTACT_RECIPIENT', raising=False)
    assert 'mailto:team@example.org' not in client.get('/contact').get_data(as_text=True)
    monkeypatch.setenv('CONTACT_RECIPIENT', 'team@example.org')
    assert 'mailto:team@example.org' in client.get('/contact').get_data(as_text=True)


@pytest.mark.parametrize('change,field', [
    ({'name': ''}, 'name'),
    ({'email': ''}, 'email'),
    ({'email': 'not-an-email'}, 'email'),
    ({'message': 'too short'}, 'message'),
    ({'message': 'x' * 2001}, 'message'),
])
def test_contact_validation_errors(client, app, slow, change, field):
    data = {**_form(client), **change}
    r = client.post('/contact', data=data)
    assert r.status_code == 400
    body = r.get_data(as_text=True)
    assert f'id="{field}-error"' in body and 'role="alert"' in body
    assert _count(ContactMessage, app) == 0


def test_contact_honeypot_stores_nothing(client, app, slow):
    r = client.post('/contact', data={**_form(client), 'website': 'http://spam.example'})
    assert r.status_code == 302
    assert _count(ContactMessage, app) == 0 and _count(Job, app) == 0


def test_contact_too_fast_is_rejected(client, app):
    r = client.post('/contact', data=_form(client))
    assert r.status_code == 400
    assert 'quick' in r.get_data(as_text=True)
    assert _count(ContactMessage, app) == 0


def test_contact_bad_token_is_rejected(client, app, slow):
    r = client.post('/contact', data={**_form(client), 'form_token': 'forged'})
    assert r.status_code == 400
    assert _count(ContactMessage, app) == 0


def test_contact_valid_post_saves_message_and_queues_job(client, app, slow, monkeypatch):
    monkeypatch.delenv('SMTP_HOST', raising=False)
    monkeypatch.delenv('CONTACT_RECIPIENT', raising=False)
    data = _form(client)
    r = client.post('/contact', data=data)
    assert r.status_code == 302 and r.headers['Location'].endswith('/contact?sent=1')
    with app.app_context():
        msg = ContactMessage.query.one()
        assert msg.email == 'asha@example.com' and msg.status == 'new' and msg.user_id is None
        job = Job.query.one()
        assert job.kind == 'send_email' and job.payload == {'contact_message_id': msg.id}
        assert job.idempotency_key == f'contact-email:{msg.id}'
    ok = client.get(r.headers['Location']).get_data(as_text=True)
    assert 'no email confirmation will be sent' in ok


def test_contact_success_text_when_email_configured(client, monkeypatch):
    monkeypatch.setenv('SMTP_HOST', 'smtp.example.org')
    monkeypatch.setenv('CONTACT_RECIPIENT', 'team@example.org')
    body = client.get('/contact?sent=1').get_data(as_text=True)
    assert 'queued to be emailed' in body and 'no email confirmation' not in body


def test_contact_double_submit_does_not_duplicate(client, app, slow):
    data = _form(client)
    assert client.post('/contact', data=data).status_code == 302
    assert client.post('/contact', data=data).status_code == 302
    assert _count(ContactMessage, app) == 1
    assert _count(Job, app) == 1


def test_contact_logs_never_contain_message_text(client, app, slow, caplog):
    caplog.set_level(logging.DEBUG)
    client.post('/contact', data=_form(client))
    assert _count(ContactMessage, app) == 1
    assert SECRET_TEXT not in caplog.text


def test_contact_links_user_when_logged_in(patient_client, app, slow):
    c, uid = patient_client
    assert c.post('/contact', data=_form(c)).status_code == 302
    with app.app_context():
        assert ContactMessage.query.one().user_id == uid


# ---------- auth pages ----------
def test_signup_page_markup(client):
    body = client.get('/signup').get_data(as_text=True)
    assert 'name="consent"' in body and 'name="age_confirm"' in body
    assert body.count('type="checkbox"') == 2
    assert 'I am 18 or older' in body
    assert 'data-toggle-password' in body
    assert 'data-validate' in body and 'data-loading-text' in body
    for field in ('name', 'email', 'institution', 'invite_code', 'password', 'confirm_password', 'role'):
        assert f'name="{field}"' in body
    assert '/privacy' in body and '/terms' in body
    assert 'onclick=' not in body and 'onsubmit=' not in body
    assert len(re.findall(r'<h1[\s>]', body)) == 1


def test_login_page_markup(client):
    body = client.get('/login').get_data(as_text=True)
    for field in ('email', 'password', 'role'):
        assert f'name="{field}"' in body
    assert '/login/google' in body
    assert 'data-toggle-password' in body and 'data-validate' in body
    assert 'onclick=' not in body and 'onsubmit=' not in body


def test_login_failure_keeps_inline_alert(client):
    body = client.post('/login', data={'email': 'a@b.co', 'password': 'x', 'role': 'patient'}).get_data(as_text=True)
    assert 'id="auth-alert"' in body and 'class="alert alert-danger"' in body


def test_role_selection_page(patient_client):
    c, _ = patient_client
    body = c.get('/role_selection').get_data(as_text=True)
    assert 'name="role"' in body and 'value="patient"' in body


# ---------- static assets ----------
@pytest.mark.skipif(shutil.which('node') is None, reason='node not installed')
@pytest.mark.parametrize('path', ['static/js/components.js', 'static/js/signup.js'])
def test_js_syntax(path):
    import os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    subprocess.run(['node', '--check', os.path.join(root, path)], check=True)


def test_components_assets_follow_design_rules():
    import os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    js = open(os.path.join(root, 'static/js/components.js'), encoding='utf-8').read()
    css = open(os.path.join(root, 'static/css/components.css'), encoding='utf-8').read()
    assert '{{' not in js and '{%' not in js
    assert 'gradient' not in css and '9999px' not in css and '999px' not in css
    assert '—' not in js + css
