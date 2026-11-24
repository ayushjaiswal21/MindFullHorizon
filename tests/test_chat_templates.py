"""Starter questions: fixed allowlist, 24 h cache of guarded AI answers, static fallbacks, print markup. No network."""
import os
import re

import pytest

import ai.gemini_impl as g
from ai.interface import AIProvider
from utils import chat_templates as ct
from utils import llm_guard

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDS = [t.id for t in ct.TEMPLATES]
GOOD = "Try a short walk, regular sleep and slow breathing. Talking to your college counsellor can also help."
# medicine and diagnosis words must never appear in the fixed answers
FORBIDDEN = re.compile(r"\b(mg|tablet|pill|dose|dosage|sertraline|fluoxetine|escitalopram|alprazolam|clonazepam|"
                       r"melatonin|paracetamol|ibuprofen|antidepressant|medication|medicine|"
                       r"you have (depression|anxiety|adhd|ptsd|bipolar)|diagnos\w*)\b", re.I)


class Provider(AIProvider):
    def __init__(self, out=GOOD):
        self.out, self.calls = out, 0

    def ask(self, prompt, **kw):
        self.calls += 1
        if isinstance(self.out, BaseException):
            raise self.out
        return self.out


@pytest.fixture(autouse=True)
def fresh_cache():
    ct.clear_cache()
    yield
    ct.clear_cache()


@pytest.fixture
def provider(monkeypatch):
    def install(out=GOOD):
        p = Provider(out)
        monkeypatch.setattr(g, "PROVIDER", p)
        return p
    return install


def test_allowlist_is_small_fixed_and_free_of_personal_data():
    assert 3 <= len(ct.TEMPLATES) <= 6 and len(set(IDS)) == len(IDS)
    for t in ct.TEMPLATES:
        assert not re.search(r"\b(my name|i am \d|@|\d{6,})", t.text, re.I)
        assert t.text.endswith("?") and len(t.text) < 100


def test_unknown_ids_are_rejected(patient_client, provider):
    p = provider()
    c, _ = patient_client
    for bad in ("nope", "", None, 5, ["exam-stress"], {"id": 1}, "EXAM-STRESS", "exam-stress "):
        assert ct.answer(bad) is None
        assert c.post("/api/chat/template", json={"template_id": bad}).status_code == 400
    assert c.post("/api/chat/template", json={"message": "free text"}).status_code == 400
    assert p.calls == 0


def test_template_route_needs_login(client):
    assert client.post("/api/chat/template", json={"template_id": IDS[0]}).status_code == 401


def test_cache_hit_makes_no_ai_call(provider):
    p = provider()
    first = ct.answer("sleep")
    assert first["source"] == "ai" and first["reply"] == GOOD and first["saved"] is False and p.calls == 1
    second = ct.answer("sleep")
    assert second["source"] == "cache" and second["reply"] == GOOD and second["saved"] is True and p.calls == 1


def test_cache_expires_after_24_hours_and_follows_config_version(provider, monkeypatch):
    p = provider()
    now = [1000.0]
    monkeypatch.setattr(ct, "_clock", lambda: now[0])
    ct.answer("habits")
    now[0] += ct.TTL_SECONDS - 1
    assert ct.answer("habits")["source"] == "cache" and p.calls == 1
    now[0] += 2
    assert ct.answer("habits")["source"] == "ai" and p.calls == 2
    monkeypatch.setattr(g, "GEMINI_MODEL_NAME", "another-model")  # new AI configuration: old answers are not served
    assert ct.answer("habits")["source"] == "ai" and p.calls == 3


def test_cache_is_bounded(provider, monkeypatch):
    provider()
    monkeypatch.setattr(ct, "MAX_ENTRIES", 2)
    for tid in IDS:
        ct.answer(tid)
    assert len(ct._CACHE) <= 2


def test_unsafe_ai_output_is_not_cached_and_falls_back(provider):
    p = provider("Take 500 mg of paracetamol twice a day and you have depression.")
    res = ct.answer("sleep")
    assert res["source"] == "fallback" and "paracetamol" not in res["reply"] and not ct._CACHE
    assert p.calls == 1


def test_ai_failure_and_blank_output_use_static_answer_without_caching(provider):
    for out in (RuntimeError("boom"), "", "   "):
        ct.clear_cache()
        provider(out)
        res = ct.answer("lonely")
        assert res["source"] == "fallback" and res["saved"] is True and not ct._CACHE and len(res["reply"]) > 80


def test_no_key_gives_instant_fallback_without_ai_call(monkeypatch):
    class Off(Provider):
        def configured(self):
            return False
    p = Off()
    monkeypatch.setattr(g, "PROVIDER", p)
    assert ct.answer("counsellor")["source"] == "fallback" and p.calls == 0


@pytest.mark.parametrize("tid", IDS)
def test_fallback_answers_are_safe_plain_and_pass_the_output_guard(tid):
    tpl = ct.get(tid)
    text = ct.fallback_answer(tpl)
    assert "{help}" not in text and not FORBIDDEN.search(text), text
    assert "counsellor" in text
    guarded = llm_guard.guard_output(text)
    assert not guarded.blocked and guarded.text == text
    assert len(text) <= llm_guard.max_reply_chars() + 150 and "\u2014" not in text and "\u2013" not in text


def test_helpline_in_fallback_comes_from_the_single_config():
    text = ct.fallback_answer(ct.get("counsellor"))
    assert "14416" in text  # Tele-MANAS from utils/helplines.py, not typed into the template list


def test_free_text_is_never_cached(patient_client, provider, monkeypatch):
    import ai.service as svc
    provider()
    monkeypatch.setattr(svc, "ask_gemini_system_user", lambda *a, **k: '{"reply": "ok friend", "severity": 0}')
    c, _ = patient_client
    for _ in range(2):
        assert c.post("/api/chat", json={"message": "How can I manage stress before my exams?"}).status_code == 200
    assert not ct._CACHE  # even text identical to a template goes through the full chat pipeline, uncached


def test_template_route_returns_text_reply_and_saved_flag(patient_client, provider):
    provider()
    c, _ = patient_client
    r = c.post("/api/chat/template", json={"template_id": "exam-stress"}).get_json()
    assert r["ok"] and r["text"] == ct.get("exam-stress").text and r["reply"] == GOOD and r["source"] == "ai"
    r = c.post("/api/chat/template", json={"template_id": "exam-stress"}).get_json()
    assert r["source"] == "cache" and r["saved"] is True


def test_chat_page_has_starters_print_buttons_and_print_rules(patient_client):
    c, _ = patient_client
    html = c.get("/chat").get_data(as_text=True)
    for tid in IDS:
        assert f'data-template-id="{tid}"' in html
    assert 'id="chat-print-all"' in html and "Print conversation" in html
    assert "AI-generated, not advice" in html and 'id="chat-print-date"' in html
    for tag in ('id="chat-form"', 'id="chat-banner"', 'id="chat-starters"'):
        assert re.search(tag + r'[^>]*no-print|no-print[^>]*' + tag, html), tag
    css = open(os.path.join(ROOT, "static/css/wellness.css"), encoding="utf-8").read()
    assert "@media print" in css and ".chat-page .no-print" in css and "chat-print-one" in css
    js = open(os.path.join(ROOT, "static/js/inline_extracted/chat_actions.js"), encoding="utf-8").read()
    assert "Copy" in js and "Print" in js and "window.print" in js and "innerHTML" not in js


def test_new_chat_files_stay_small_and_clean():
    for rel in ("utils/chat_templates.py", "static/js/inline_extracted/chat_actions.js",
                "static/js/inline_extracted/chat_inline_1.js", "tests/test_chat_templates.py"):
        src = open(os.path.join(ROOT, rel), encoding="utf-8").read()
        assert src.count("\n") <= 300 and "\u2014" not in src and "\u2013" not in src, rel
