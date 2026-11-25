"""AI personal-data policy (zero-cost deployment): with AI_SEND_PERSONAL_TEXT off (the default) no student text reaches a
model, every model call is classified, the tip of the day is the only general use, and the copy says what is true.
The autouse fixture in conftest turns the flag ON for other tests; here `off` unsets it. Fake providers only."""
import ast
import asyncio
import io
import os
import re

import pytest

import ai.service as svc
from ai import gemini_impl as g
from ai.interface import AIProvider
from utils import ai_policy, daily_tip
from utils.tip_data import TIPS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XHR = {"X-Requested-With": "XMLHttpRequest"}


class Counting(AIProvider):
    def __init__(self, text="Rest well and drink water today.", fail=False):
        self.calls, self.text, self.fail, self.systems = 0, text, fail, []

    def ask(self, prompt, **kw):
        self.calls += 1
        self.systems.append(kw.get("system_prompt", ""))
        if self.fail:
            raise RuntimeError("down")
        return self.text


@pytest.fixture
def prov(monkeypatch):
    p = Counting()
    monkeypatch.setattr(g, "PROVIDER", p)
    monkeypatch.setenv("GEMINI_API_KEY", "fake")  # the voice route checks the env var before it asks the service
    return p


@pytest.fixture
def off(monkeypatch):
    monkeypatch.delenv("AI_SEND_PERSONAL_TEXT", raising=False)


def text_of(client, url):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", client.get(url).get_data(as_text=True)))


# ---- the switch and the classification ------------------------------------------------------------------
@pytest.mark.parametrize("value,expected", [(None, False), ("", False), ("0", False), ("no", False), ("false", False),
                                            ("2", False), ("1", True), ("true", True), ("YES", True), (" on ", True)])
def test_flag_is_truthy_only_for_known_values(monkeypatch, value, expected):
    monkeypatch.delenv("AI_SEND_PERSONAL_TEXT", raising=False)
    if value is not None:
        monkeypatch.setenv("AI_SEND_PERSONAL_TEXT", value)
    assert ai_policy.personal_text_allowed() is expected


def test_unclassified_call_raises(prov):
    with pytest.raises(TypeError):
        g.ask_gemini_system_user("s", "u")
    with pytest.raises(TypeError):
        g.ask_gemini_system_user("s", "u", personal="yes")
    with pytest.raises(TypeError):
        svc.ask("hello")
    assert prov.calls == 0


def test_every_call_site_in_the_source_is_classified():
    """Static scan: a call to the model layer must say personal=True/False (a literal), so a new one cannot forget."""
    watched, sites = {"ask_gemini_system_user", "_personal_call", "ask"}, 0
    for sub in ("ai", "routes", "utils", "services", "scripts", ""):
        base = os.path.join(ROOT, sub)
        for name in sorted(os.listdir(base)):
            path = os.path.join(base, name)
            if not name.endswith(".py") or not os.path.isfile(path):
                continue
            rel = os.path.relpath(path, ROOT).replace("\\", "/")
            tree = ast.parse(open(path, encoding="utf-8").read())
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                f = node.func
                fname = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""
                if fname == "ask" and not (rel == "ai/service.py" and isinstance(f, ast.Name)):
                    continue  # PROVIDER.ask and other unrelated .ask methods
                if fname == "_personal_call" and rel != "ai/service.py":
                    pytest.fail(f"{rel}: _personal_call is private to ai/service.py")
                if fname not in watched or fname == "_personal_call":
                    continue
                sites += 1
                kw = {k.arg: k.value for k in node.keywords}
                ok = "personal" in kw and (isinstance(kw["personal"], ast.Constant) and isinstance(kw["personal"].value, bool)
                                           or (rel == "ai/service.py" and isinstance(kw["personal"], ast.Name)))
                assert ok, f"{rel}:{node.lineno} calls {fname} without personal=True/False"
            assert "PROVIDER.ask(" not in open(path, encoding="utf-8").read() or rel == "ai/gemini_impl.py", rel
    assert sites >= 6, sites
    src = open(os.path.join(ROOT, "ai", "service.py"), encoding="utf-8").read()
    assert src.count("personal=True") >= 3 and "_personal_call(" in src


# ---- off: no model call for any personal feature --------------------------------------------------------
def _exercise(app, patient_client, provider_client, make_user):
    """Hit every personal call site once; returns nothing, the caller reads the provider's counter."""
    from extensions import db
    from models import Assessment, ProviderPatient
    c, uid = patient_client
    pc, prov_id = provider_client
    assert c.post("/api/chat", json={"message": "I felt low about my exams today"}).status_code == 200
    assert c.post("/api/ask", json={"prompt": "I feel tired and sad"}).status_code == 200
    assert svc.generate_chat_response("hello there", user_id=uid)
    assert c.post("/patient/journal", data={"title": "Day", "content": "Felt anxious before the viva."}).status_code in (200, 302)
    c.post("/api/upload-voice", data={"audio": (io.BytesIO(b"RIFF....WAVEfmt "), "v.wav", "audio/wav")},
           content_type="multipart/form-data", headers=XHR)
    c.post("/patient/api/save-assessment", json={"assessment_type": "PHQ-9", "responses": [1] * 8 + [0]})  # item 9 at 0: no crisis path
    c.get("/patient/api/progress/suggestions")
    c.post("/patient/api/log-digital-detox", json={"screen_time": 5, "academic_score": 70, "social_interactions": "low"})
    pat = make_user("patient", email="note.patient@test.local")
    with app.app_context():
        db.session.add(ProviderPatient(provider_id=prov_id, patient_id=pat, source="manual"))
        db.session.add(Assessment(user_id=uid, assessment_type="PHQ-9", score=8, responses=[1] * 9))
        db.session.commit()
    pc.post("/provider/ai-documentation", data={"transcript": "student said exams are heavy", "patient_email": "note.patient@test.local"})
    svc.generate_goal_suggestions({"goals": ["sleep"]})
    svc.analyze_medication_adherence([{"taken": True}], {"name": "x"})


def test_off_blocks_every_personal_call_site(app, off, prov, patient_client, provider_client, make_user):
    _exercise(app, patient_client, provider_client, make_user)
    assert prov.calls == 0


def test_on_allows_the_personal_call_sites(app, monkeypatch, prov, patient_client, provider_client, make_user):
    monkeypatch.setenv("AI_SEND_PERSONAL_TEXT", "1")
    _exercise(app, patient_client, provider_client, make_user)
    blob = " ".join(prov.systems)
    for marker in ("Anya", "journal entry", "screening result", "mental health coach", "digital wellness coach",
                   "session notes", "Wellness coach", "Medical assistant"):
        assert marker.lower() in blob.lower(), marker


@pytest.mark.parametrize("fn,args", [(svc.generate_journal_insights, ("t", "felt low today", "Neutral")),
                                     (svc.generate_clinical_note, ("transcript text",)),
                                     (svc.generate_progress_recommendations, ({"phq9_score": 9},)),
                                     (svc.generate_digital_detox_insights, ({"screen_time": 4},)),
                                     (svc.generate_goal_suggestions, ({"goals": []},)),
                                     (svc.analyze_medication_adherence, ([], {}))])
def test_each_generator_skips_the_model_when_off_and_keeps_its_fallback(off, prov, fn, args):
    assert fn(*args) is not None
    assert prov.calls == 0
    with pytest.raises(ai_policy.PersonalTextBlocked):
        svc.generate_assessment_insights("PHQ-9", 8, [1] * 9)
    assert prov.calls == 0


def test_chat_off_has_no_unavailable_notice_and_uses_no_budget(off, prov, patient_client):
    c, _ = patient_client
    body = c.post("/api/chat", json={"message": "I am worried about my results"}).get_json()
    assert body["reply"].startswith(svc.off_reply()[:40]) and "ai_unavailable" not in body
    assert "no AI model reads what you write" in body["reply"] and body["severity"] == 0
    assert prov.calls == 0


def test_crisis_floor_is_unaffected_when_off(off, prov, patient_client):
    from ai.severity import classify
    c, _ = patient_client
    body = c.post("/api/chat", json={"message": "I want to kill myself"}).get_json()
    assert body["escalate"] and body["reply"] == svc.CRISIS_REPLY and body["helplines"]
    friend = "my friend said he wants to kill himself"
    assert classify(friend) == "friend"
    assert c.post("/api/chat", json={"message": friend}).get_json()["reply"] == svc.FRIEND_REPLY
    assert c.post("/api/ask", json={"prompt": "I want to kill myself"}).get_json()["response"] == svc.CRISIS_REPLY
    assert asyncio.run(svc.ask_with_severity("I want to end my life", user_id=1))["escalate"] is True
    assert prov.calls == 0


def test_starter_answers_are_fixed_questions_and_stay_available_when_off(off, prov, patient_client):
    c, _ = patient_client
    body = c.post("/api/chat/template", json={"template_id": "sleep"}).get_json()
    assert body["ok"] and body["reply"]  # personal=False: the allowlisted question carries no student text


# ---- tip of the day ---------------------------------------------------------------------------------------
@pytest.fixture
def tip(monkeypatch):
    monkeypatch.setattr(daily_tip, "_run", lambda fn: fn())
    daily_tip.reset()


def test_static_tips_are_thirty_vetted_lines():
    assert len(TIPS) == 30 and len(set(TIPS)) == 30
    for t in TIPS:
        assert 20 < len(t) <= 160 and "—" not in t and not re.search(r"\d+\s?mg|http|@", t) and t.isascii()


def test_tip_one_model_call_per_ist_day_and_it_works_with_the_flag_off(off, prov, tip, patient_client, monkeypatch):
    from datetime import date
    c, _ = patient_client
    assert c.get("/patient/dashboard").status_code == 200 and prov.calls == 0  # a page render never calls the model
    seen = [c.get("/api/tip").get_json() for _ in range(5)]
    assert prov.calls == 1 and seen[-1] == {"text": "Rest well and drink water today.", "source": "model"}
    monkeypatch.setattr(daily_tip, "ist_today", lambda: date(2030, 1, 2))
    c.get("/api/tip"), c.get("/api/tip")
    assert prov.calls == 2


@pytest.mark.parametrize("bad", ["Take 500 mg of it and see https://x.example", "", "You are diagnosed with depression."])
def test_tip_falls_back_when_the_model_text_is_unusable(off, prov, tip, patient_client, bad):
    prov.text = bad
    out = patient_client[0].get("/api/tip").get_json()
    assert out["source"] == "static" and out["text"] in TIPS and prov.calls == 1


def test_tip_falls_back_on_outage_and_without_a_key(off, tip, patient_client, monkeypatch):
    p = Counting(fail=True)
    monkeypatch.setattr(g, "PROVIDER", p)
    c, _ = patient_client
    assert [c.get("/api/tip").get_json()["source"] for _ in range(3)] == ["static"] * 3 and p.calls <= 1
    daily_tip.reset()
    monkeypatch.setattr(g, "PROVIDER", g.GeminiProvider())
    monkeypatch.setattr(g, "GEMINI_API_KEY", "")
    assert c.get("/api/tip").get_json()["text"] in TIPS


def test_dashboard_shows_the_labelled_tip_card(off, patient_client):
    html = patient_client[0].get("/patient/dashboard").get_data(as_text=True)
    assert 'id="tip-card"' in html and "General tip, not advice for you." in html and "Tip of the day" in html


# ---- copy follows the flag ---------------------------------------------------------------------------------
DISCLOSURE = "no AI model reads what you write"
FORBIDDEN_WHEN_OFF = ["AI assistant, not a therapist", "is sent to Google Gemini", "sent to Google's Gemini model",
                      "may be sent to an AI service", "receives the text of the features that use AI",
                      "your chat message; a journal entry", "Anya is an AI"]


def test_copy_when_off_never_claims_ai_reads_personal_text(app, off, client, patient_client, provider_client):
    pc = patient_client[0]
    pages = {"/": client, "/ai": client, "/privacy": client, "/terms": client, "/about": client, "/faq": client,
             "/chat": pc, "/patient/dashboard": pc, "/patient/journal": pc, "/patient/voice-logs": pc,
             "/provider/ai-documentation": provider_client[0]}
    for url, who in pages.items():
        t = text_of(who, url)
        for bad in FORBIDDEN_WHEN_OFF:
            assert bad not in t, (url, bad)
    assert "Anya replies from saved answers and a safety check; no AI model reads what you write" in text_of(pc, "/chat")
    assert "an automated assistant" in text_of(pc, "/chat")
    assert "No AI model reads your messages, journal, voice, mood or screening data" in text_of(client, "/faq")
    assert "no personal text is sent to an AI model" in text_of(client, "/privacy")
    assert "the tip of the day" in text_of(client, "/ai") and DISCLOSURE in text_of(client, "/ai")
    assert "Anya is an automated assistant" in text_of(client, "/")
    claim6 = re.search(r'id="diff-6".*?</div>', client.get("/").get_data(as_text=True), re.S).group(0)
    assert DISCLOSURE in claim6 and "A labelled AI that does not diagnose" in claim6


def test_copy_when_on_is_the_original_and_mentions_the_free_tier(app, client, patient_client):
    assert "Anya is an AI assistant, not a therapist" in text_of(patient_client[0], "/chat")
    assert DISCLOSURE not in text_of(patient_client[0], "/chat")
    assert "free-tier terms may allow" in text_of(client, "/ai") and "free-tier terms may allow" in text_of(client, "/privacy")
    assert "receives the text of the features that use AI" in text_of(client, "/faq")
    assert "The companion tells you it is an AI" in text_of(client, "/")


def test_config_and_docs_carry_the_flag():
    read = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read()
    assert "AI_SEND_PERSONAL_TEXT=0" in read(".env.example")
    assert "AI_SEND_PERSONAL_TEXT" in read("render.yaml") and "AI_SEND_PERSONAL_TEXT" in read("docs/DEPLOY.md")
    assert "Personal-text policy" in read("docs/LLM_SECURITY.md") and "AI_PERSONAL_TEXT_APPROVED_BY" in read("docs/PRIVACY_AND_CONSENT.md")


def test_predeploy_warns_when_on_without_the_approval_record():
    import importlib.util
    spec = importlib.util.spec_from_file_location("predeploy", os.path.join(ROOT, "scripts", "predeploy_check.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.check_ai_policy({})[0][0] == "PASS"
    assert mod.check_ai_policy({"AI_SEND_PERSONAL_TEXT": "1"})[0][0] == "WARN"
    assert mod.check_ai_policy({"AI_SEND_PERSONAL_TEXT": "1", "AI_PERSONAL_TEXT_APPROVED_BY": "Dean, 2026-12-01"})[0][0] == "PASS"
