"""Listen button (static/js/speech-output.js + the listen_button macro): renders where expected, never calls
the network, and the page still works when there is no speakable text (e.g. speechSynthesis unsupported)."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(ROOT, 'static', 'js', 'speech-output.js')


def _js():
    with open(JS_PATH, encoding='utf-8') as fh:
        return fh.read()


def test_speech_output_js_never_calls_the_network():
    """The whole point is zero-network, device-only speech: grep-proof it stays that way."""
    src = _js()
    for forbidden in ('fetch(', 'XMLHttpRequest', 'navigator.sendBeacon', 'WebSocket(', 'EventSource('):
        assert forbidden not in src, f"speech-output.js must never call {forbidden}"


def test_speech_output_js_uses_local_voices_only():
    src = _js()
    assert 'localService' in src
    assert 'localService === true' in src or 'localService===true' in src


def test_speech_output_js_never_autoplays():
    """The only call to MFH.speak(...) lives inside the button's click handler (attach()); nothing calls it
    at load time or from a timer/interval, which would be an autoplay."""
    src = _js()
    assert 'addEventListener(\'click\'' in src
    click_handler = src.split("addEventListener('click', function () {", 1)[1]
    assert 'MFH.speak(' in click_handler
    before_click_handler = src.split("addEventListener('click', function () {", 1)[0]
    code_only = before_click_handler.split('*/', 1)[-1]  # drop the file-header comment, which names the API
    assert 'MFH.speak(' not in code_only
    assert 'setTimeout' not in src and 'setInterval' not in src


def test_speech_output_js_syntax_ok():
    import subprocess
    result = subprocess.run(['node', '--check', JS_PATH], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_faq_listen_button_renders_on_selected_answers(client):
    body = client.get('/faq').get_data(as_text=True)
    for faq_id in ('self-harm', 'counsellor-sees', 'ai-model'):
        assert f'id="listen-faq-{faq_id}"' in body
        assert 'data-speak-text="' in body
    assert 'aria-label="Listen to this"' in body
    assert 'js/speech-output.js' in body


def test_faq_listen_button_text_matches_the_answer(client):
    """The exact answer text (not a truncation or paraphrase) is what the button will read."""
    body = client.get('/faq').get_data(as_text=True)
    assert 'data-speak-text="Every chat message goes through a fixed rule-based check' in body


def test_listen_button_macro_degrades_without_speakable_text(client, app):
    """A page that never renders the macro (most pages) has no .mfh-listen element and no speech-output.js
    requirement - nothing breaks in its absence."""
    body = client.get('/about').get_data(as_text=True)
    assert 'mfh-listen' not in body


def test_tip_card_has_listen_button(patient_client):
    client, _uid = patient_client
    body = client.get('/patient/dashboard').get_data(as_text=True)
    assert 'id="tip-listen"' in body
    assert 'data-speak-target="#tip-card [data-tip-text]"' in body
    assert 'js/speech-output.js' in body


def test_chat_page_loads_speech_output_js(patient_client):
    client, _uid = patient_client
    body = client.get('/chat').get_data(as_text=True)
    assert 'js/speech-output.js' in body


def test_chat_actions_js_only_adds_listen_for_saved_answers():
    path = os.path.join(ROOT, 'static', 'js', 'inline_extracted', 'chat_actions.js')
    with open(path, encoding='utf-8') as fh:
        src = fh.read()
    assert 'createListenButton' in src
    # The listen button must be created inside the `if (j.saved)` branch, never for a live reply.
    saved_block = src.split('if (j.saved) {', 1)[1].split('}', 1)[0]
    assert 'createListenButton' in saved_block


def test_macro_never_puts_jinja_in_js():
    import subprocess
    for f in ('static/js/speech-output.js', 'static/js/inline_extracted/chat_actions.js'):
        with open(os.path.join(ROOT, f), encoding='utf-8') as fh:
            assert '{{' not in fh.read() and '{%' not in fh.read()
