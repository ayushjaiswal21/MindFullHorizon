/* Yoga session timer. Text and a native progress element only; no sound, no animation. */
(function () {
  'use strict';
  var root = document.getElementById('yoga-root');
  if (!root || window.__mfhYoga) return;
  window.__mfhYoga = true;

  var MIN_SAVE_SECONDS = 60;
  var $ = function (id) { return document.getElementById(id); };
  var display = $('timer-display'), bar = $('progress-bar'), status = $('session-status'),
      startBtn = $('start-timer-btn'), pauseBtn = $('pause-timer-btn'), stopBtn = $('stop-timer-btn'),
      savePrompt = $('save-prompt'), saveText = $('save-prompt-text'), saveBtn = $('save-session-btn'),
      logForm = $('yoga-log-form');

  var s = { total: 0, elapsed: 0, running: false, paused: false, timer: null, accum: 0, last: 0, logName: 'Custom Session' };

  function pad(n) { return ('0' + n).slice(-2); }
  function render() {
    var left = Math.max(s.total - s.elapsed, 0);
    display.textContent = pad(Math.floor(left / 60)) + ':' + pad(left % 60);
    bar.value = s.total ? Math.min(100, Math.round((s.elapsed / s.total) * 100)) : 0;
  }
  function buttons(mode) {
    startBtn.hidden = mode !== 'ready' && mode !== 'idle';
    startBtn.disabled = mode === 'idle';
    pauseBtn.hidden = mode !== 'running';
    stopBtn.hidden = mode !== 'running';
  }
  function stopTicking() { clearInterval(s.timer); s.timer = null; }
  function startTicking() { s.last = Date.now(); clearInterval(s.timer); s.timer = setInterval(loop, 250); }

  function loop() {
    var now = Date.now();
    s.accum += now - s.last;
    s.last = now;
    while (s.accum >= 1000 && s.running) {
      s.accum -= 1000;
      s.elapsed += 1;
      if (s.elapsed >= s.total) { finish(true); break; }
    }
    render();
  }

  function finish(completed) {
    stopTicking();
    var longEnough = s.elapsed >= MIN_SAVE_SECONDS;
    var minutes = Math.max(1, Math.round(s.elapsed / 60));
    s.running = false;
    s.paused = false;
    status.textContent = completed ? 'Session complete.' : 'Session stopped.';
    if (longEnough) {
      s.savedMinutes = minutes;
      s.savedName = s.logName;
      saveText.textContent = 'You practised for about ' + minutes + (minutes === 1 ? ' minute.' : ' minutes.');
      savePrompt.hidden = false;
    }
    s.elapsed = 0;
    render();
    pauseBtn.textContent = 'Pause';
    buttons('ready');
  }

  function setLength(minutes, logName, label) {
    stopTicking();
    s.running = false;
    s.paused = false;
    s.total = minutes * 60;
    s.elapsed = 0;
    s.logName = logName || 'Custom Session';
    savePrompt.hidden = true;
    status.textContent = label || (minutes + ' minute session ready.');
    pauseBtn.textContent = 'Pause';
    render();
    buttons('ready');
  }

  function begin() {
    if (!s.total) { status.textContent = 'Choose a length first.'; return; }
    s.running = true;
    s.paused = false;
    s.accum = 0;
    status.textContent = 'Session in progress.';
    buttons('running');
    startTicking();
    pauseBtn.focus();
  }

  startBtn.addEventListener('click', begin);
  pauseBtn.addEventListener('click', function () {
    if (!s.running) return;
    if (s.paused) {
      s.paused = false;
      pauseBtn.textContent = 'Pause';
      status.textContent = 'Session in progress.';
      startTicking();
    } else {
      s.paused = true;
      pauseBtn.textContent = 'Resume';
      status.textContent = 'Paused.';
      stopTicking();
    }
  });
  stopBtn.addEventListener('click', function () { if (s.running) finish(false); });

  document.querySelectorAll('.quick-session-btn').forEach(function (b) {
    b.addEventListener('click', function () {
      var m = parseInt(b.dataset.duration, 10);
      if (m) setLength(m, 'Custom Session');
    });
  });
  document.querySelectorAll('.start-guided-session-card').forEach(function (b) {
    b.addEventListener('click', function () {
      var m = parseInt(b.dataset.sessionDuration, 10);
      if (!m) return;
      setLength(m, b.dataset.logName, b.querySelector('strong').textContent + ', ' + m + ' minutes ready.');
      root.scrollIntoView({ block: 'start' });
      startBtn.focus();
    });
  });

  if (saveBtn && logForm) {
    saveBtn.addEventListener('click', function () {
      logForm.querySelector('[name="session_name"]').value = s.savedName;
      logForm.querySelector('[name="duration_minutes"]').value = String(s.savedMinutes);
      saveBtn.disabled = true;
      saveBtn.setAttribute('aria-busy', 'true');
      if (typeof logForm.requestSubmit === 'function') logForm.requestSubmit(); else logForm.submit();
    });
  }

  if (window.WL) WL.guardRanges(logForm);
  window.addEventListener('beforeunload', stopTicking);
  render();
  buttons('idle');
})();
