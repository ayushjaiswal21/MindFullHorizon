/* Guided breathing page. Timing lives in breathing-guide.js (window.MFHBreath); this file draws it.
   The circle grows on inhale, holds, shrinks on exhale, using the Web Animations API with a duration equal
   to the phase length. When the OS asks for reduced motion the guide starts without animation (circle size
   changes in steps) and the "Animated guide" switch lets the student turn the animation on. Phase word and
   countdown are always shown. Saving reuses the existing log form. */
(function () {
  'use strict';
  var root = document.getElementById('breathing-root');
  if (!root || window.__mfhBreathing || !window.MFHBreath) return;
  window.__mfhBreathing = true;

  var PATTERNS = MFHBreath.PATTERNS;
  var LABEL = { inhale: 'Inhale', hold: 'Hold', exhale: 'Exhale' };
  var MIN_MINUTES = 1, MAX_MINUTES = 180, MIN_SAVE_SECONDS = 60, SMALL = 0.55, PREF = 'mfh.breathing.animated';

  var $ = function (id) { return document.getElementById(id); };
  var circle = $('breathing-circle'), count = $('breathing-text'), phaseEl = $('breathing-instruction'),
      statusEl = $('breathing-status'), cycleEl = $('breathing-cycle'), timerEl = $('timer-display'),
      progressEl = $('breathing-progress'), toggle = $('animated-toggle'),
      startBtn = $('start-btn'), pauseBtn = $('pause-btn'), stopBtn = $('stop-btn'),
      minutesEl = $('session-minutes'), minutesErr = $('session-minutes-error'), savePrompt = $('save-prompt'),
      saveText = $('save-prompt-text'), saveBtn = $('save-session-btn'), logForm = $('breathing-log-form');

  var reduce = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  var animated = !reduce, anim = null, pattern = 'box', saved = null, shown = {};
  try {
    var pref = localStorage.getItem(PREF);
    if (pref === '1') animated = true; else if (pref === '0') animated = false;
  } catch (e) { /* storage blocked: keep the default */ }
  toggle.checked = animated;

  function fmt(sec) { return Math.floor(sec / 60) + ':' + ('0' + (sec % 60)).slice(-2); }
  function put(el, key, text) { if (shown[key] !== text) { shown[key] = text; el.textContent = text; } }
  function selectedPattern() {
    var r = document.querySelector('input[name="pattern"]:checked');
    return r ? r.value : 'box';
  }
  function lock(on) {
    document.querySelectorAll('input[name="pattern"]').forEach(function (r) { r.disabled = on; });
    minutesEl.disabled = on;
  }
  function setErr(msg) {
    minutesErr.textContent = msg || '';
    minutesErr.hidden = !msg;
    if (msg) minutesEl.setAttribute('aria-invalid', 'true'); else minutesEl.removeAttribute('aria-invalid');
  }
  function minutesValue() {
    var v = Number(minutesEl.value);
    if (minutesEl.value === '' || !isFinite(v) || v < MIN_MINUTES || v > MAX_MINUTES || Math.floor(v) !== v) {
      setErr('Enter a whole number of minutes from ' + MIN_MINUTES + ' to ' + MAX_MINUTES + '.');
      minutesEl.focus();
      return null;
    }
    setErr('');
    return v;
  }

  // Circle: inhale grows to 1, exhale shrinks to SMALL, hold keeps the size.
  function drawPhase(loc) {
    if (anim) { anim.cancel(); anim = null; }
    if (loc.name === 'hold') return;
    var to = loc.name === 'inhale' ? 1 : SMALL, from = loc.name === 'inhale' ? SMALL : 1;
    circle.style.transform = 'scale(' + to + ')';
    if (!animated || !circle.animate) return;
    anim = circle.animate([{ transform: 'scale(' + from + ')' }, { transform: 'scale(' + to + ')' }],
      { duration: loc.secs * 1000, easing: 'ease-in-out', fill: 'both' });
    anim.currentTime = loc.intoMs;
    if (guide.isPaused()) anim.pause();
  }

  var guide = MFHBreath.create({
    onPhase: function (loc) {
      put(phaseEl, 'phase', LABEL[loc.name]);
      drawPhase(loc);
    },
    onTick: function (t) {
      put(count, 'count', String(t.left));
      put(timerEl, 'timer', fmt(Math.max(t.remaining, 0)) + ' left');
      put(cycleEl, 'cycle', 'Cycle ' + Math.min(t.cycle + 1, t.cycles) + ' of ' + t.cycles);
      progressEl.value = Math.round(t.progress * 1000) / 10;
    },
    onDone: function (completed) { finish(completed); }
  });

  function resetView() {
    if (anim) { anim.cancel(); anim = null; }
    circle.style.transform = '';
    put(count, 'count', '0');
    put(phaseEl, 'phase', 'Ready');
    put(timerEl, 'timer', '0:00 left');
    put(cycleEl, 'cycle', '');
    progressEl.value = 0;
    startBtn.disabled = false;
    pauseBtn.disabled = true;
    stopBtn.disabled = true;
    pauseBtn.textContent = 'Pause';
    lock(false);
  }

  function finish(completed) {
    var secs = Math.round(guide.elapsedSeconds());
    var minutes = Math.min(MAX_MINUTES, Math.max(1, Math.round(secs / 60)));
    resetView();
    statusEl.textContent = completed ? 'Session complete.' : 'Session stopped.';
    if (secs >= MIN_SAVE_SECONDS) {
      saved = { name: PATTERNS[pattern].name, minutes: minutes };
      saveText.textContent = (completed ? 'Session finished: ' : 'Session stopped: ') + saved.name + ', about ' +
        minutes + (minutes === 1 ? ' minute.' : ' minutes.');
      savePrompt.hidden = false;
    }
  }

  function start(key, minutes) {
    guide.cancel();
    savePrompt.hidden = true;
    pattern = key;
    shown = {};
    lock(true);
    startBtn.disabled = true;
    pauseBtn.disabled = false;
    stopBtn.disabled = false;
    pauseBtn.textContent = 'Pause';
    statusEl.textContent = '';
    guide.start(key, minutes);
  }

  startBtn.addEventListener('click', function () {
    var m = minutesValue();
    if (m !== null) start(selectedPattern(), m);
  });
  pauseBtn.addEventListener('click', function () {
    if (!guide.isRunning()) return;
    if (guide.isPaused()) {
      guide.resume();
      if (anim) anim.play();
      pauseBtn.textContent = 'Pause';
      statusEl.textContent = '';
    } else {
      guide.pause();
      if (anim) anim.pause();
      pauseBtn.textContent = 'Resume';
      statusEl.textContent = 'Paused.';
    }
  });
  stopBtn.addEventListener('click', function () { guide.stop(); });

  toggle.addEventListener('change', function () {
    animated = toggle.checked;
    try { localStorage.setItem(PREF, animated ? '1' : '0'); } catch (e) { /* storage blocked */ }
    var cur = guide.current();
    if (cur) drawPhase(cur);
  });

  document.querySelectorAll('.start-guided-session-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var key = btn.dataset.pattern, minutes = parseInt(btn.dataset.sessionDuration, 10);
      if (!PATTERNS[key] || !minutes) return;
      var radio = document.querySelector('input[name="pattern"][value="' + key + '"]');
      if (guide.isRunning()) { guide.cancel(); resetView(); }
      if (radio) radio.checked = true;
      minutesEl.value = String(minutes);
      setErr('');
      root.scrollIntoView({ block: 'start' });
      start(key, minutes);
      pauseBtn.focus();
    });
  });

  if (saveBtn && logForm) {
    saveBtn.addEventListener('click', function () {
      if (!saved) return;
      logForm.querySelector('[name="exercise_name"]').value = saved.name;
      logForm.querySelector('[name="duration_minutes"]').value = String(saved.minutes);
      saveBtn.disabled = true;
      saveBtn.setAttribute('aria-busy', 'true');
      if (typeof logForm.requestSubmit === 'function') logForm.requestSubmit(); else logForm.submit();
    });
  }

  if (window.WL) WL.guardRanges(logForm);
  window.addEventListener('beforeunload', function () { guide.cancel(); });
  resetView();
})();
