/* Voice logs: record in the browser, preview, then save. The microphone is only requested when the person
   presses Start recording. No waveform or other animation. */
(function () {
  'use strict';
  var root = document.getElementById('voice-root');
  if (!root || window.__mfhVoice) return;
  window.__mfhVoice = true;

  var MAX_SECONDS = 120;
  var $ = function (id) { return document.getElementById(id); };
  var recBtn = $('recordBtn'), stopBtn = $('stopBtn'), upBtn = $('uploadBtn'), discardBtn = $('discardBtn'),
      statusEl = $('recordingStatus'), timerEl = $('timer'), micEl = $('mic-state'), upStatus = $('uploadStatus'),
      previewWrap = $('preview-wrap'), preview = $('preview'), list = $('voice-list');
  var pageSize = parseInt(root.dataset.pageSize, 10) || 10;

  var rec = null, stream = null, chunks = [], startedAt = 0, tick = null, previewUrl = '';

  function say(t) { statusEl.textContent = t; }
  function pad(n) { return ('0' + n).slice(-2); }

  /* Permission state without prompting. */
  function describePermission(state) {
    if (state === 'granted') micEl.textContent = 'Microphone: allowed for this site.';
    else if (state === 'denied') micEl.textContent = 'Microphone: blocked. Allow it in your browser\'s site settings, then reload this page.';
    else micEl.textContent = 'Microphone: not asked yet. Your browser asks for permission when you press Start recording.';
  }
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || typeof window.MediaRecorder === 'undefined') {
    recBtn.disabled = true;
    micEl.textContent = 'This browser cannot record audio. Try a current version of Chrome, Edge, Firefox or Safari.';
  } else if (navigator.permissions && navigator.permissions.query) {
    navigator.permissions.query({ name: 'microphone' }).then(function (p) {
      describePermission(p.state);
      p.onchange = function () { describePermission(p.state); };
    }).catch(function () { /* some browsers do not support querying the microphone */ });
  }

  function releaseStream() {
    if (stream) { stream.getTracks().forEach(function (t) { t.stop(); }); stream = null; }
  }
  function clearPreview() {
    if (previewUrl) { URL.revokeObjectURL(previewUrl); previewUrl = ''; }
    preview.removeAttribute('src');
    previewWrap.hidden = true;
    upBtn.disabled = true;
    chunks = [];
  }

  function stopRecording() {
    clearInterval(tick);
    if (rec && rec.state !== 'inactive') rec.stop();
    stopBtn.disabled = true;
    recBtn.disabled = false;
  }

  function startRecording() {
    clearPreview();
    navigator.mediaDevices.getUserMedia({ audio: true }).then(function (s) {
      stream = s;
      chunks = [];
      rec = new MediaRecorder(s);
      rec.ondataavailable = function (e) { if (e.data && e.data.size) chunks.push(e.data); };
      rec.onstop = function () {
        releaseStream();
        if (!chunks.length) { say('Nothing was recorded. Try again.'); return; }
        var blob = new Blob(chunks, { type: 'audio/wav' });
        previewUrl = URL.createObjectURL(blob);
        preview.src = previewUrl;
        previewWrap.hidden = false;
        upBtn.disabled = false;
        say('Recording finished. Play it back, then save or discard it.');
        describePermission('granted');
      };
      rec.start();
      startedAt = Date.now();
      recBtn.disabled = true;
      stopBtn.disabled = false;
      say('Recording. Press Stop when you are done.');
      timerEl.textContent = '00:00';
      tick = setInterval(function () {
        var s2 = Math.floor((Date.now() - startedAt) / 1000);
        timerEl.textContent = pad(Math.floor(s2 / 60)) + ':' + pad(s2 % 60);
        if (s2 >= MAX_SECONDS) stopRecording();
      }, 500);
    }).catch(function (err) {
      releaseStream();
      var name = err && err.name;
      if (name === 'NotAllowedError' || name === 'SecurityError') {
        describePermission('denied');
        say('Microphone access was blocked. Allow it in your browser\'s site settings, then press Start recording again.');
      } else if (name === 'NotFoundError') {
        say('No microphone was found. Connect one and try again.');
      } else {
        say('The microphone could not be started. Close other apps that use it and try again.');
      }
    });
  }

  function upload() {
    if (!chunks.length) { say('There is no recording to save.'); return; }
    var fd = new FormData();
    fd.append('audio', new Blob(chunks, { type: 'audio/wav' }), 'voice_log.wav');
    upBtn.disabled = true;
    upBtn.setAttribute('aria-busy', 'true');
    discardBtn.disabled = true;
    upStatus.hidden = false;
    fetch('/api/upload-voice', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': window.WL ? WL.csrf() : '' },
      body: fd
    }).then(function (res) {
      return res.json().catch(function () { return null; }).then(function (d) { return { ok: res.ok, status: res.status, d: d }; });
    }).then(function (r) {
      upStatus.hidden = true;
      if (r.ok && r.d && r.d.success) {
        say('Saved. Loading your list.');
        if (window.WL) WL.toast('Voice log saved.', 'success');
        window.location.reload();
        return;
      }
      upBtn.disabled = false;
      var m = 'The recording could not be saved. Try again.';
      if (r.status === 429) m = 'You have reached the limit of 5 voice logs an hour. Try again later.';
      else if (r.status === 401 || r.status === 403) m = 'Your session has expired. Log in again, then save.';
      else if (r.d && r.d.message) m = r.d.message;
      say(m);
      if (window.WL) WL.toast(m, 'error');
    }).catch(function () {
      upStatus.hidden = true;
      upBtn.disabled = false;
      say('The network seems to be down. Your recording is still here. Try saving again.');
    }).then(function () {
      upBtn.removeAttribute('aria-busy');
      discardBtn.disabled = false;
    });
  }

  recBtn.addEventListener('click', startRecording);
  stopBtn.addEventListener('click', stopRecording);
  upBtn.addEventListener('click', upload);
  discardBtn.addEventListener('click', function () {
    clearPreview();
    timerEl.textContent = '00:00';
    say('Recording discarded. Ready to record. Maximum 2 minutes.');
  });
  window.addEventListener('beforeunload', function () { releaseStream(); clearInterval(tick); });

  /* Paging and delete */
  var more = $('show-more-btn'), moreStatus = $('show-more-status');
  function refreshLists() {
    var total = list.querySelectorAll('.voice-log').length;
    var c = $('log-count');
    if (c) c.textContent = '(' + total + ')';
    $('voice-empty').hidden = total > 0;
    if (more) {
      var hidden = list.querySelectorAll('.voice-log[hidden]').length;
      more.hidden = hidden === 0;
      moreStatus.textContent = 'Showing ' + (total - hidden) + ' of ' + total + '.';
    }
  }
  if (more) {
    more.addEventListener('click', function () {
      var items = list.querySelectorAll('.voice-log[hidden]');
      var first = items[0];
      for (var i = 0; i < Math.min(pageSize, items.length); i++) items[i].hidden = false;
      refreshLists();
      if (first) { var h = first.querySelector('h3'); if (h) { h.tabIndex = -1; h.focus(); } }
    });
    refreshLists();
  }

  list.addEventListener('click', function (e) {
    var btn = e.target.closest('.delete-voice-log-btn');
    if (!btn || !window.WL) return;
    var id = btn.dataset.logId, card = btn.closest('.voice-log');
    WL.ask({ title: 'Delete this voice log?', message: 'The recording and its measurements are removed and cannot be brought back.', confirmText: 'Delete voice log', danger: true })
      .then(function (yes) {
        if (!yes) return;
        btn.disabled = true;
        btn.setAttribute('aria-busy', 'true');
        return WL.api('/api/delete-voice-log/' + encodeURIComponent(id), { method: 'DELETE' }).then(function (r) {
          if (r.ok && r.data && r.data.success) {
            if (card) card.remove();
            refreshLists();
            WL.toast('Voice log deleted.', 'success');
            recBtn.focus();
          } else {
            btn.disabled = false;
            btn.removeAttribute('aria-busy');
            WL.toast('Could not delete the voice log. Try again.', 'error');
          }
        });
      })
      .catch(function () {
        btn.disabled = false;
        btn.removeAttribute('aria-busy');
        WL.toast('Could not delete the voice log. Check your connection and try again.', 'error');
      });
  });
})();
