/* "Listen" button: reads already-approved static text aloud with the browser's own speechSynthesis.
   Zero download, zero dependency, device-only: nothing is ever sent anywhere. Only ever used for pre-written
   clinician text (starter answers, the daily tip, FAQ answers) - never for live AI replies, never for text the
   student typed. Speech starts only on a click, never automatically.
   Public API: window.MFH.speak(text, lang), MFH.pauseSpeaking(), MFH.resumeSpeaking(), MFH.stopSpeaking(),
   MFH.speechSupported(), MFH.createListenButton(text, opts) for JS-built chat bubbles.
   No Jinja here; text comes from data-speak-text / data-speak-target attributes or a JS string. */
(function () {
  'use strict';
  var MFH = window.MFH = window.MFH || {};
  var supported = typeof window.speechSynthesis !== 'undefined' && typeof window.SpeechSynthesisUtterance === 'function';
  var synth = supported ? window.speechSynthesis : null;
  var reduceMotion = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  var NUDGE_KEY = 'mfh_listen_nudge_seen';

  // Split long text at sentence boundaries (incl. Devanagari) so some Android TTS engines do not cut it off.
  function sentences(text) {
    var parts = String(text).split(/(?<=[.?!।])\s+/);
    return parts.map(function (p) { return p.trim(); }).filter(Boolean);
  }

  // Only voices that run on the device qualify; a non-local voice would send the text to a remote server.
  function localVoices() {
    try { return (synth.getVoices() || []).filter(function (v) { return v.localService === true; }); }
    catch (e) { return []; }
  }

  function pickVoice(lang) {
    var voices = localVoices();
    if (!voices.length) return null;
    var want = String(lang || document.documentElement.getAttribute('lang') || 'en').toLowerCase().split('-')[0];
    var match = voices.filter(function (v) { return v.lang && v.lang.toLowerCase().indexOf(want) === 0; });
    if (match.length) return match[0];
    var def = voices.filter(function (v) { return v.default; });
    return def[0] || voices[0];
  }

  MFH.speechSupported = function () { return supported; };

  var activeStop = null;

  /** Speak text (split into sentences), using only a local, on-device voice. Returns false if unsupported,
      empty, or no local voice is available yet (callers should not retry remote voices in that case). */
  MFH.speak = function (text, lang, callbacks) {
    callbacks = callbacks || {};
    if (!supported || !text) return false;
    var voice = pickVoice(lang);
    if (!voice) return false;
    MFH.stopSpeaking();
    var queue = sentences(text), i = 0, stopped = false;
    function speakNext() {
      if (stopped) return;
      if (i >= queue.length) { activeStop = null; if (callbacks.onend) callbacks.onend(); return; }
      var u = new SpeechSynthesisUtterance(queue[i]);
      u.voice = voice;
      u.lang = voice.lang;
      i++;
      u.onend = speakNext;
      u.onerror = function () { activeStop = null; if (callbacks.onend) callbacks.onend(); };
      synth.speak(u);
    }
    activeStop = function () { stopped = true; synth.cancel(); };
    if (callbacks.onstart) callbacks.onstart();
    speakNext();
    return true;
  };

  MFH.pauseSpeaking = function () { if (supported && synth.speaking) synth.pause(); };
  MFH.resumeSpeaking = function () { if (supported && synth.paused) synth.resume(); };
  MFH.stopSpeaking = function () {
    if (activeStop) activeStop();
    else if (supported) synth.cancel();
    activeStop = null;
  };

  function iconUse(btn) { return btn.querySelector('.mfh-listen-icon svg use'); }
  function setIcon(use, name) {
    if (!use) return;
    var href = use.getAttribute('href') || use.getAttribute('xlink:href') || '';
    use.setAttribute('href', href.replace(/#icon-[a-z-]+$/, '#icon-' + name));
  }

  function headphoneNudge() {
    try {
      if (localStorage.getItem(NUDGE_KEY)) return;
      localStorage.setItem(NUDGE_KEY, '1');
    } catch (e) { /* private mode: nudge every time is acceptable, but do not crash */ }
    if (MFH.toast) MFH.toast('Use headphones if others are nearby. Nothing is sent anywhere; this reads text on your device.', 'info');
  }

  function textFor(btn) {
    var target = btn.getAttribute('data-speak-target');
    if (target) {
      var node = document.querySelector(target);
      return node ? node.textContent.trim() : '';
    }
    return btn.getAttribute('data-speak-text') || '';
  }

  function setSpeaking(btn, speaking) {
    var label = btn.querySelector('.mfh-listen-label');
    btn.classList.toggle('is-speaking', speaking);
    btn.setAttribute('aria-pressed', speaking ? 'true' : 'false');
    btn.setAttribute('aria-label', speaking ? 'Stop reading' : 'Listen to this');
    if (label) label.textContent = speaking ? 'Reading...' : 'Listen';
    setIcon(iconUse(btn), speaking ? 'pause' : 'play');
  }

  function attach(btn, getText, lang) {
    if (btn.__mfhListenWired) return;
    btn.__mfhListenWired = true;
    btn.addEventListener('click', function () {
      if (btn.classList.contains('is-speaking')) { MFH.stopSpeaking(); setSpeaking(btn, false); return; }
      var text = getText();
      if (!text) return;
      headphoneNudge();
      var ok = MFH.speak(text, lang || btn.getAttribute('data-speak-lang'), {
        onend: function () { setSpeaking(btn, false); }
      });
      if (ok) setSpeaking(btn, true);
      else if (MFH.toast) MFH.toast('No on-device voice is available to read this aloud right now.', 'info');
    });
  }

  /* For chat replies built in JS (chat_actions.js): a fully wired button, never auto-played. */
  MFH.createListenButton = function (text, opts) {
    opts = opts || {};
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'btn btn-ghost btn-sm mfh-listen' + (opts.className ? ' ' + opts.className : '');
    btn.setAttribute('aria-pressed', 'false');
    btn.setAttribute('aria-label', 'Listen to this');
    var iconsUrl = document.body.getAttribute('data-icons') || '/static/img/icons.svg';
    var SVGNS = 'http://www.w3.org/2000/svg';
    var svg = document.createElementNS(SVGNS, 'svg');
    svg.setAttribute('class', 'icon'); svg.setAttribute('width', '18'); svg.setAttribute('height', '18');
    svg.setAttribute('viewBox', '0 0 24 24'); svg.setAttribute('fill', 'none'); svg.setAttribute('stroke', 'currentColor');
    svg.setAttribute('stroke-width', '1.75'); svg.setAttribute('stroke-linecap', 'round'); svg.setAttribute('stroke-linejoin', 'round');
    svg.setAttribute('aria-hidden', 'true'); svg.setAttribute('focusable', 'false');
    var use = document.createElementNS(SVGNS, 'use');
    use.setAttribute('href', iconsUrl + '#icon-play');
    svg.appendChild(use);
    var span = document.createElement('span');
    span.className = 'mfh-listen-icon';
    span.appendChild(svg);
    var label = document.createElement('span');
    label.className = 'mfh-listen-label';
    label.setAttribute('aria-live', 'polite');
    label.textContent = 'Listen';
    btn.appendChild(span);
    btn.appendChild(label);
    attach(btn, function () { return typeof text === 'function' ? text() : text; }, opts.lang);
    return btn;
  };

  function wireAll() {
    document.querySelectorAll('.mfh-listen[data-speak-text], .mfh-listen[data-speak-target]').forEach(function (btn) {
      if (!supported) { btn.hidden = true; return; }
      attach(btn, function () { return textFor(btn); }, btn.getAttribute('data-speak-lang'));
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', wireAll);
  else wireAll();

  if (reduceMotion) document.documentElement.setAttribute('data-mfh-reduce-motion', 'true');
})();
