"""The site shell (templates/base.html) renders the same contract on every page."""
import json
import re

import pytest

PAGES = [("guest", "/"), ("guest", "/login"), ("guest", "/this-page-does-not-exist"), ("patient", "/patient/dashboard")]


@pytest.fixture
def page(app, client, patient_client):
    def _get(who, url):
        c = patient_client[0] if who == "patient" else client
        r = c.get(url)
        assert r.status_code in (200, 404), (url, r.status_code)
        return r.get_data(as_text=True)
    return _get


@pytest.mark.parametrize("who,url", PAGES)
def test_shell_contract(page, who, url):
    html = page(who, url)
    assert 'class="skip-link" href="#main-content"' in html
    assert len(re.findall(r"<main[\s>]", html)) == 1
    assert re.search(r'<link rel="canonical" href="http[^"]+"', html)
    assert 'property="og:title"' in html and 'property="og:image" content="http' in html
    assert 'name="twitter:card"' in html
    assert 'id="consent-banner"' in html and "Essential only" in html and "Accept analytics" in html
    assert "data-theme-toggle" in html
    assert 'href="/privacy"' in html and 'href="/terms"' in html and "data-consent-open" in html
    assert "cdn.tailwindcss.com" not in html
    assert "Made with" not in html
    assert 'lang="en"' in html and "viewport" in html
    assert "14416" in html  # helplines come from the context processor


@pytest.mark.parametrize("who,url", PAGES)
def test_json_ld_parses(page, who, url):
    html = page(who, url)
    blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    assert blocks
    graphs = [json.loads(b) for b in blocks]
    types = {n["@type"] for g in graphs for n in g.get("@graph", [g])}
    assert {"Organization", "WebSite"} <= types


def test_nav_is_role_aware(page):
    guest = page("guest", "/login")
    assert "Create account" in guest and "Sign out" not in guest
    patient = page("patient", "/patient/dashboard")
    assert "Sign out" in patient and "Create account" not in patient and "Assessments" in patient


def test_title_pattern_and_default_robots(page):
    html = page("guest", "/login")
    assert re.search(r"<title>[^<]+ \| MindFull Horizon</title>", html) or "<title>MindFull Horizon</title>" in html
    assert 'name="robots"' in html


def test_404_is_html_and_api_404_is_json(client):
    r = client.get("/nothing-here")
    assert r.status_code == 404 and b"Page not found" in r.data
    j = client.get("/api/nothing-here")
    assert j.status_code == 404 and j.get_json()["success"] is False


def test_500_page_hides_exception_text(app):
    from utils.site_context import render_error_page
    with app.test_request_context("/somewhere"):
        body, code = render_error_page(500)
    assert code == 500 and "Something went wrong" in body
    assert "Traceback" not in body


def test_site_context_values(app):
    with app.test_request_context("/"):
        ctx = app.jinja_env.globals and {}
        for fn in app.template_context_processors[None]:
            ctx.update(fn())
    assert ctx["prescriptions_enabled"] is True  # owner decision: default on; issuing is gated by a verified doctor
    assert ctx["consent_version"] and ctx["site_last_updated"] and ctx["asset_version"]
    assert {h["number"] for h in ctx["helplines"]} >= {"14416", "112"}


def test_static_shell_files_exist():
    import os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for rel in ("static/css/site.css", "static/css/site-components.css", "static/css/site-legacy-1.css",
                "static/css/tailwind.css", "static/css/print.css", "static/js/shell.js", "static/img/icons.svg",
                "static/img/favicon.svg", "static/img/favicon.ico", "static/favicon.ico", "static/img/apple-touch-icon.png",
                "static/img/icon-192.png", "static/img/icon-512.png", "static/img/og-default.png", "static/img/og-default.webp",
                "static/site.webmanifest"):
        assert os.path.getsize(os.path.join(root, rel)) > 0, rel
    sprite = open(os.path.join(root, "static/img/icons.svg"), encoding="utf-8").read()
    for name in "home chart calendar chat heart book user users settings bell check alert info x menu search sun moon arrow-right arrow-left play pause clock pill video music leaf lock mail phone edit trash copy external shield mood journal mic target logout plus filter download eye eye-off wind activity file help chevron-down chevron-up".split():
        assert f'id="icon-{name}"' in sprite, name
