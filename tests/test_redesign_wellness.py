"""Redesign checks for the chat and wellness pages: render, safety hooks, hygiene, no banned patterns."""
import os
import re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PAGES = ["/chat", "/patient/breathing", "/patient/yoga", "/patient/yoga/videos", "/music",
         "/patient/digital-detox", "/patient/journal", "/patient/voice-logs"]

TEMPLATES = ["chat", "breathing", "yoga", "yoga_videos", "music", "digital_detox", "patient_journal", "patient_voice_logs"]
JS_FILES = ["static/js/inline_extracted/chat_inline_1.js", "static/js/inline_extracted/breathing_inline_1.js",
            "static/js/yoga.js", "static/js/video-facade.js", "static/js/inline_extracted/music_inline_1.js",
            "static/js/inline_extracted/digital_detox_inline_1.js", "static/js/inline_extracted/patient_journal_inline_1.js",
            "static/js/inline_extracted/patient_voice_logs_inline_1.js", "static/js/wellness-common.js"]

EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿⭐⬆⏱⏰▶✅❌]")
BANNED_PHRASES = ["powered by ai", "made with ai", "ai-powered", "transform your", "unlock your potential",
                  "trusted by", "rounded-full", "9999px", "gradient"]


def _read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


def _main(html):
    m = re.search(r"<main\b.*?</main>", html, re.S)
    return m.group(0) if m else html


@pytest.fixture
def pages(patient_client):
    c, _ = patient_client
    out = {}
    for url in PAGES:
        r = c.get(url)
        assert r.status_code == 200, url
        out[url] = r.get_data(as_text=True)
    return out


def test_every_page_renders_for_a_patient(pages):
    assert set(pages) == set(PAGES)


def test_chat_page_safety_markup(pages):
    html = pages["/chat"]
    assert "Anya is an AI assistant, not a therapist" in html
    assert 'role="log"' in html and 'aria-live="polite"' in html
    assert 'id="chat-input"' in html and 'for="chat-input"' in html
    assert 'class="crisis-banner' in html
    assert "14416" in html  # helplines come from utils/helplines.py via the context variable


def test_chat_js_safety():
    src = _read("static/js/inline_extracted/chat_inline_1.js")
    assert "innerHTML" not in src and "outerHTML" not in src and "insertAdjacentHTML" not in src
    assert not re.search(r"\b(14416|112|1800-?599-?0019)\b", src), "helpline numbers must not be hard-coded in JS"
    assert "textContent" in src and "/api/chat" in src and "helplines" in src
    assert "alert(" not in src
    # the retired poller must not come back and render messages unsafely
    assert "innerHTML" not in _read("static/js/chat.js")


@pytest.mark.parametrize("path", JS_FILES)
def test_js_hygiene(path):
    src = _read(path)
    assert "{{" not in src and "{%" not in src, "no Jinja in static JS"
    assert not re.search(r"(?<![\w.])(alert|confirm)\(", src), "use MFH.toast / MFH.confirm"
    assert not EMOJI.search(src)
    assert "—" not in src and "–" not in src
    assert "innerHTML" not in src


@pytest.mark.parametrize("name", TEMPLATES)
def test_template_hygiene(name):
    src = _read(f"templates/{name}.html")
    assert not re.search(r"\son\w+\s*=", src), "no inline event handlers"
    assert not EMOJI.search(src)
    assert "—" not in src and "–" not in src
    for bad in BANNED_PHRASES:
        assert bad not in src.lower(), bad
    assert "fas fa-" not in src, "use the icon macro, not Font Awesome"


def test_rendered_pages_have_no_banned_patterns(pages):
    for url, html in pages.items():
        main = _main(html)
        assert not EMOJI.search(main), url
        assert "—" not in main and "–" not in main, url
        low = main.lower()
        for bad in BANNED_PHRASES:
            assert bad not in low, (url, bad)
        assert "<h1" in main, url


def test_yoga_videos_facade_is_safe(pages):
    html = pages["/patient/yoga/videos"]
    assert "autoplay" not in html.lower()
    assert "<iframe" not in html, "iframes are created only after a click"
    assert 'loading="lazy"' in html and 'width="480"' in html and 'height="360"' in html
    assert "https://i.ytimg.com/vi/" in html
    js = _read("static/js/video-facade.js")
    assert "youtube-nocookie.com/embed/" in js and "autoplay" not in js.lower()
    assert "www.youtube.com/embed" not in html + js


def test_breathing_page_bounds_and_empty_state(pages):
    html = pages["/patient/breathing"]
    assert 'id="session-minutes"' in html and 'max="180"' in html
    assert "No sessions yet" in html
    assert "prefers-reduced-motion" in _read("static/css/wellness.css")


def test_music_page_with_empty_library(pages, patient_client, tmp_path, monkeypatch):
    html = pages["/music"]
    assert 'preload="none"' in html and "<audio" in html
    assert 'id="music-empty"' in html
    assert "autoplay" not in html.lower()
    c, _ = patient_client
    # An empty library answers with an empty list, which the page renders as an empty state.
    monkeypatch.chdir(tmp_path)
    r = c.post("/api/mood-audio", json={"mood": "calm"})
    assert r.status_code == 200 and r.get_json()["success"] is True
    assert isinstance(r.get_json()["files"], list)
    js = _read("static/js/inline_extracted/music_inline_1.js")
    assert "autoplay" not in js.lower() and "AudioContext" not in js


def test_forms_validate_and_label_ai_text(pages):
    for url in ("/patient/journal", "/patient/breathing", "/patient/yoga", "/patient/digital-detox"):
        assert "data-validate" in pages[url], url
    assert "not advice" in pages["/patient/digital-detox"]


def test_journal_ai_section_is_labelled(patient_client):
    c, _ = patient_client
    c.post("/patient/journal", data={"title": "Day one", "content": "Felt okay today."})
    html = c.get("/patient/journal").get_data(as_text=True)
    assert "Day one" in html
    assert "AI-generated suggestions, not advice" in html
    assert "hidden" in re.search(r'id="journal-empty"[^>]*>', html).group(0), "empty state is hidden when entries exist"


def test_voice_page_is_honest_about_storage(pages):
    html = pages["/patient/voice-logs"]
    low = html.lower()  # the audio is analysed and discarded (not stored): the page must say so
    assert "not stored: the audio" in low and "discarded" in low
    assert 'id="mic-state"' in html
    assert "getUserMedia" not in html
    js = _read("static/js/inline_extracted/patient_voice_logs_inline_1.js")
    assert "getUserMedia" in js and "permissions.query" in js and "AudioContext" not in js


def test_detox_js_keeps_endpoint_and_json_block(pages):
    js = _read("static/js/inline_extracted/digital_detox_inline_1.js")
    assert "'/patient/api/log-digital-detox'" in js
    assert 'id="screen-time-data"' in pages["/patient/digital-detox"]
    assert "new Chart(" not in js, "no chart library on this page"
