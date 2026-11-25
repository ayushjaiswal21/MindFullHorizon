"""SYNTHESIS.md section 3(c) item c2: the LLM-generated digital-detox / adherence scores must
always carry the exact caveat copy and the raw logged-entries count beside them, and must never
appear as a bare number on a counsellor-facing screen.
"""
import re

from utils import ai_caveats

XHR = {"X-Requested-With": "XMLHttpRequest"}


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def test_detox_page_shows_caveat_and_count(app, patient_client):
    c, uid = patient_client
    good = {"screen_time": 5, "academic_score": 80, "social_interactions": "high"}
    r = c.post("/patient/api/log-digital-detox", json=good, headers=XHR)
    assert r.status_code == 200
    body = r.get_json()
    assert body["caveat"] == ai_caveats.DETOX_CAVEAT
    assert body["logged_count"] == 1

    page = c.get("/patient/digital-detox")
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert ai_caveats.DETOX_CAVEAT in html
    assert "Logged entries used" in html and ">1<" in html


def test_detox_caveat_js_uses_correct_keys():
    src = _read("static/js/inline_extracted/digital_detox_inline_1.js")
    assert "ai.score" in src and "ai.analysis" in src
    assert "ai.ai_score" not in src and "ai.ai_suggestion" not in src
    assert "logged_count" in src and "caveat" in src


def test_profile_shows_detox_score_caveat_and_count(app, patient_client):
    c, uid = patient_client
    good = {"screen_time": 4, "academic_score": 70, "social_interactions": "medium"}
    assert c.post("/patient/api/log-digital-detox", json=good, headers=XHR).status_code == 200

    page = c.get("/profile")
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert "Logged entries used" in html
    if "n/a" not in html.split("Latest score")[1].split("</dd>")[0]:
        assert ai_caveats.DETOX_CAVEAT in html


def test_wellness_report_never_shows_bare_adherence_score():
    """Grep-based: if an adherence_score ever appears in the counsellor report, the exact
    caveat and a logged-count must be right beside it in the template source."""
    html = _read("templates/wellness_report.html")
    if "adherence_score" in html:
        assert ai_caveats.ADHERENCE_CAVEAT in html
        assert "logged_count" in html


def test_no_counsellor_template_aggregates_the_ai_detox_score():
    """SYNTHESIS.md c2: the LLM-generated digital-detox score must never be fed into an
    aggregate, chart, ranking or alert, even with a caveat. Confirms the institution-wide
    'average wellness score' chart (built from DigitalDetoxLog.ai_score) was removed."""
    analytics_html = _read("templates/analytics.html")
    assert "wellness_score_data" not in analytics_html
    assert "wellnessChart" not in analytics_html

    core_src = _read("routes/provider/analytics.py")
    assert "wellness_score_data" not in core_src

    js_src = _read("static/js/inline_extracted/analytics_inline_1.js")
    assert "wellness" not in js_src.lower() or "wellnessChart" not in js_src


def test_caveat_text_matches_synthesis_c2():
    """Exact copy from docs/research/ai/SYNTHESIS.md section 3(c) item c2 (adherence), and the
    same structure/honesty level adapted for the digital-detox context."""
    assert ai_caveats.ADHERENCE_CAVEAT == (
        "This number is an estimate written by an AI model from a few logged entries. "
        "It is not a clinical measurement and has not been checked against real adherence. "
        "Use the logged dates below to see what was actually recorded."
    )
    assert re.search(r"estimate written by an AI model from a few logged entries", ai_caveats.DETOX_CAVEAT)
    assert "not a clinical measurement" in ai_caveats.DETOX_CAVEAT


def test_detox_page_uses_design_system_component_not_hardcoded_colour():
    html = _read("templates/digital_detox.html")
    assert 'class="alert alert-info"' in html
    assert "#" not in html.split('id="ai-score-caveat"')[0][-200:]  # no inline hex colour near it
