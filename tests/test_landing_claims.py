"""Guest landing page: the "How this differs" section must stay specific, sourced and free of superlatives.

Facts come from docs/research/competitive-2026.md section 6 (checked November 2026)."""
import re

from utils.helplines import get_helplines

HEADINGS = [
    "Counsellor alert with timed escalation",
    "Crisis help does not depend on the AI",
    "PHQ-9 and GAD-7 scored on the server",
    "Counsellors see linked students only",
    "Export and delete your data",
    "A labelled AI that does not diagnose",
]
# Brand names the research doc verified as current, neutral facts. They may appear only inside the sources <details>.
COMPETITOR_ALLOWLIST = ["Headspace"]
KNOWN_BRANDS = ["Headspace", "Wysa", "Woebot", "Youper", "Calm", "Daylio", "Amaha", "BetterHelp", "Talkspace",
                "Finch", "Bearable", "MindDoc", "Sanvello", "7 Cups", "Togetherall", "YourDOST", "Lissun",
                "MindPeers", "Practo", "TimelyCare", "Mantra Health"]
SUPERLATIVES = re.compile(
    r"\b(best|number one|leading|top-rated|top rated|better than|only app|unlike (?:others|other apps|every)|"
    r"guaranteed?|proven|certified|compliant|hipaa|most trusted)\b|#1|"
    r"24\s*[x/]\s*7\s+(?:monitor|counsel|human|support|team|watch)|(?:monitored|watched)\s+(?:24|around)", re.I)
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿⭐️‍]")


def _page(client):
    r = client.get("/")
    assert r.status_code == 200
    return r.get_data(as_text=True)


def _split(html):
    m = re.search(r"<details[^>]*diff-sources.*?</details>", html, re.S)
    assert m, "sources <details> missing"
    return html[:m.start()] + html[m.end():], m.group(0)


def _text(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def test_headings_and_limits_box(client):
    html = _page(client)
    for h in HEADINGS:
        assert f"<dt>{h}</dt>" in html, h
    assert "How this differs from other options" in html
    assert 'id="limits"' in html and "What we do not do" in html
    for phrase in ("not therapy", "does not diagnose", "no clinical trial", "early-stage", "18 and over", "Out-of-hours"):
        assert phrase in _text(html), phrase
    assert 'href="/ai"' in html and 'href="/privacy"' in html and 'href="/terms"' in html
    assert "Read how the AI works" in html


def test_no_superlatives_or_comparatives_about_us(client):
    text = _text(_page(client))
    assert not [m.group(0) for m in SUPERLATIVES.finditer(text)]


def test_no_competitor_names_outside_sources(client):
    outside, sources = _split(_page(client))
    for brand in KNOWN_BRANDS:
        assert not re.search(rf"\b{re.escape(brand)}\b", outside, re.I), brand
        if brand not in COMPETITOR_ALLOWLIST:
            assert not re.search(rf"\b{re.escape(brand)}\b", sources, re.I), brand


def test_helplines_match_config(client):
    html = _page(client)
    configured = {h["number"] for h in get_helplines()}
    seen = set(re.findall(r"\b1800-\d{3}-\d{4}\b|\b14416\b|\b112\b", html))
    assert seen == configured
    section = re.search(r'id="diff-2".*?</div>', html, re.S).group(0)
    for n in configured:
        assert n in section


def test_every_compared_with_claim_has_a_source(client):
    html = _page(client)
    _, sources = _split(html)
    assert "Sources and date" in sources and "Checked November 2026" in sources
    claims = re.findall(r'id="diff-(\d)"(.*?)(?=id="diff-\d"|</dl>)', html, re.S)
    assert len(claims) == 6
    covered = set()
    for li in re.findall(r'<li data-claim="([^"]+)">(.*?)</li>', sources, re.S):
        if re.search(r'href="https://[^"]+"', li[1]):
            covered.update(li[0].split())
    needs = {n for n, body in claims if "compare-with" in body}
    assert needs == {"1", "2", "6"}
    assert needs <= covered


def test_data_link_only_for_logged_in_users(client, patient_client):
    assert "/account/data" not in _page(client)
    assert "You need to be logged in" in _page(client)


def test_page_has_no_emoji_or_em_dash(client):
    html = _page(client)
    assert "—" not in html and not EMOJI.search(html)
    assert "gradient" not in html
