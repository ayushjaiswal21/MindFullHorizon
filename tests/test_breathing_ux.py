"""Breathing guide page and the compact landing helpline card (structure only; the real-browser check is
tools/e2e/specs/breathing.mjs)."""
import os
import re

from utils.helplines import get_helplines

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


def test_breathing_page_has_controls_live_region_toggle_and_form(patient_client):
    c, _ = patient_client
    html = c.get("/patient/breathing").get_data(as_text=True)
    for value in ("box", "478", "diaphragmatic", "pursed"):
        assert f'name="pattern" value="{value}"' in html
    for ident in ("start-btn", "pause-btn", "stop-btn", "breathing-cycle", "timer-display", "breathing-progress",
                  "session-minutes", "breathing-log-form", "exercise_name", "duration_minutes"):
        assert f'id="{ident}"' in html, ident
    assert re.search(r'id="breathing-instruction"[^>]*aria-live="polite"', html)
    assert 'id="animated-toggle"' in html and 'role="switch"' in html and "Animated guide" in html
    assert html.count("Stop if dizzy") >= 4  # one plain "how it works" line per pattern
    assert 'max="180"' in html and "breathing-guide.js" in html


def test_log_endpoint_still_saves_minutes(patient_client):
    c, _ = patient_client
    r = c.post("/patient/breathing", json={"exercise_name": "Box Breathing", "duration_minutes": 180})
    assert r.status_code == 200 and r.get_json()["success"]
    assert c.post("/patient/breathing", json={"exercise_name": "Box Breathing", "duration_minutes": 181}).status_code == 400


def test_js_has_all_pattern_timings_and_real_time_loop():
    guide = _read("static/js/breathing-guide.js")
    assert "box: { name: 'Box Breathing', phases: [['inhale', 4], ['hold', 4], ['exhale', 4], ['hold', 4]] }" in guide
    assert "'478': { name: '4-7-8 Breathing', phases: [['inhale', 4], ['hold', 7], ['exhale', 8]] }" in guide
    assert "diaphragmatic: { name: 'Diaphragmatic Breathing', phases: [['inhale', 4], ['exhale', 6]] }" in guide
    assert "pursed: { name: 'Pursed-lip Breathing', phases: [['inhale', 2], ['exhale', 4]] }" in guide
    assert "performance.now" in guide and "requestAnimationFrame" in guide and "setInterval" not in guide
    page = _read("static/js/inline_extracted/breathing_inline_1.js")
    assert ".animate(" in page and "prefers-reduced-motion" in page and "localStorage" in page
    assert "{{" not in page and "{%" not in page


def test_landing_helpline_card_is_compact_and_from_source(client):
    html = client.get("/").get_data(as_text=True)
    m = re.search(r'<aside class="card home-help home-help-compact".*?</aside>', html, re.S)
    assert m, "compact helpline card missing"
    card = m.group(0)
    for h in get_helplines():
        assert f'href="tel:{h["tel"]}"' in card and h["number"] in card
    assert card.count('href="tel:') == 3
