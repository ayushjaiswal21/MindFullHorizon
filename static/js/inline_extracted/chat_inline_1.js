/* Chat UI. All server and user text is inserted with textContent / DOM nodes (no HTML parsing).
   Helplines come from the API payload or the #helplines-data JSON block, never from this file. */
(function () {
  'use strict';
  if (window.__mfhChat) return;
  window.__mfhChat = true;

  var BOT_NAME = 'Anya';
  var LIMIT = 2000;
  var COUNT_FROM = 1800;
  var UI_TIMEOUT_MS = 12000;
  var crisisShown = false;
  var sending = false;
  var seenIds = {};
  var pollTimer = null;

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function byId(id) { return document.getElementById(id); }
  function csrf() {
    var m = document.querySelector('meta[name="csrf-token"]');
    if (m && m.content) return m.content;
    var i = document.querySelector('#chat-form input[name="csrf_token"]');
    return i ? i.value : '';
  }
  function toast(msg, type) { if (window.MFH && typeof MFH.toast === 'function') MFH.toast(msg, type || 'info'); }
  function pageHelplines() {
    try { return JSON.parse(byId('helplines-data').textContent) || []; } catch (e) { return []; }
  }

  var log, input, form, sendBtn, status, count;

  function scrollDown() { log.scrollTop = log.scrollHeight; }

  function addMessage(user, text, kind, parent) {
    var box = el('div', 'msg ' + (kind === 'user' ? 'msg-user' : kind === 'system' ? 'msg-system' : 'msg-bot'));
    box.append(el('p', 'msg-who', user), el('p', 'msg-text', String(text)));
    (parent || log).appendChild(box);
    if (!parent) scrollDown();
    if (kind === 'bot' && !parent) log.dispatchEvent(new CustomEvent('chat:bot', { detail: box }));  /* chat_actions.js adds Copy / Print */
    return box;
  }

  /* A quiet line inside a reply bubble, above its buttons. */
  function addNote(box, text) {
    var note = el('p', 'msg-note', text);
    box.insertBefore(note, box.querySelector('.msg-actions'));
    scrollDown();
  }

  /* Static "Anya is replying" bubble (no animation, so nothing to switch off for reduced motion). Returns a remover. */
  function addPending() {
    var box = el('div', 'msg msg-bot msg-pending no-print');
    box.append(el('p', 'msg-who', BOT_NAME), el('p', 'msg-text', 'Anya is replying'));
    log.appendChild(box);
    scrollDown();
    return function () { box.remove(); };
  }

  /* POST JSON with a UI timeout. Resolves {res, json}; rejects with the fetch error (AbortError on timeout). */
  function post(url, body, ms) {
    var ctl = new AbortController();
    var timer = setTimeout(function () { ctl.abort(); }, ms);
    return fetch(url, {
      method: 'POST', credentials: 'include', signal: ctl.signal,
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
      body: JSON.stringify(body)
    }).then(function (res) {
      return res.json().catch(function () { return null; }).then(function (json) { clearTimeout(timer); return { res: res, json: json }; });
    }, function (err) { clearTimeout(timer); throw err; });
  }

  function setBusy(on) {
    sending = on;
    input.disabled = on;
    sendBtn.disabled = on;
    if (on) sendBtn.setAttribute('aria-busy', 'true'); else sendBtn.removeAttribute('aria-busy');
    status.textContent = on ? 'Anya is replying' : '';
    document.querySelectorAll('[data-template-id]').forEach(function (b) { b.disabled = on; });
    if (!on) input.focus();
  }

  function helplineList(helplines) {
    var ul = el('ul', 'mt-2');
    (Array.isArray(helplines) ? helplines : []).forEach(function (h) {
      var li = el('li');
      var tel = String(h.tel || '').replace(/[^0-9]/g, '');
      var label = h.name + ': ' + h.number;
      if (tel) {
        var a = el('a', null, label);
        a.href = 'tel:' + tel;
        a.style.fontWeight = '600';
        li.appendChild(a);
      } else {
        li.appendChild(el('strong', null, label));
      }
      if (h.hours) li.append(' (' + h.hours + ')');
      ul.appendChild(li);
    });
    return ul;
  }

  function removeStarters() { document.querySelectorAll('.cheerful-prompt').forEach(function (n) { n.remove(); }); }

  /* Crisis: persistent banner with the helplines the API returned (page list as fallback). */
  function showCrisisBanner(helplines) {
    crisisShown = true;
    var lines = Array.isArray(helplines) && helplines.length ? helplines : pageHelplines();
    var banner = byId('chat-banner');
    banner.textContent = '';
    banner.append(
      el('p', null, 'You are not alone. If you are in immediate danger, call emergency services now.'),
      el('p', null, 'Free support, any time:'),
      helplineList(lines)
    );
    banner.hidden = false;
    removeStarters();
    var n = byId('chat-notice');
    n.hidden = true;
    n.textContent = '';
    input.placeholder = 'Type here when you are ready';
    banner.scrollIntoView({ block: 'nearest' });
  }

  function showNotice(nodes) {
    if (crisisShown) return;
    var n = byId('chat-notice');
    n.textContent = '';
    n.append.apply(n, nodes);
    n.hidden = false;
  }

  function showSupportInfo(helplines) {
    showNotice([el('p', null, 'Support lines you can use or share:'), helplineList(helplines)]);
  }

  function showAppointmentBanner(userText) {
    var btn = el('button', 'btn btn-primary btn-sm', 'Request an appointment');
    btn.type = 'button';
    btn.addEventListener('click', function () {
      btn.disabled = true;
      btn.setAttribute('aria-busy', 'true');
      fetch('/api/chat/book-appointment', {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
        body: JSON.stringify({ user_message: userText })
      }).then(function (r) {
        if (!r.ok) throw new Error('bad status');
        byId('chat-notice').textContent = 'Appointment requested. A provider will contact you.';
        toast('Appointment requested.', 'success');
      }).catch(function () {
        btn.disabled = false;
        btn.removeAttribute('aria-busy');
        toast('Could not send the request. You can also book from the schedule page.', 'error');
      });
    });
    showNotice([el('p', null, 'It may help to speak to a counsellor.'), btn]);
  }

  /* Inline error bubble; retry is a function that repeats the failed request (no second copy of the user's bubble). */
  function addError(message, retry) {
    var box = addMessage('System', message, 'system');
    if (retry) {
      var b = el('button', 'btn btn-secondary btn-sm', 'Retry');
      b.type = 'button';
      b.addEventListener('click', function () { box.remove(); retry(); });
      box.appendChild(b);
      scrollDown();
    }
  }

  var SLOW = 'Anya is taking longer than usual. Your message was not lost: press Retry to send it again.';
  var DOWN = 'The network seems to be down. Check your connection, then press Retry.';
  function failMessage(err) { return err && err.name === 'AbortError' ? SLOW : DOWN; }

  /* A reply to show: success, or a 429 budget reply (its own text and helplines). Anything else returns false. */
  function showReply(r, text) {
    var json = r.json, ok = r.res.ok && json && json.ok;
    if (!ok && !(r.res.status === 429 && json && json.reply)) return false;
    var box = addMessage(BOT_NAME, json.reply, 'bot');
    if (json.ai_unavailable && json.notice) addNote(box, json.notice);
    var hasLines = Array.isArray(json.helplines) && json.helplines.length > 0;
    if (json.escalate || json.recommended_action === 'emergency_hotline') showCrisisBanner(json.helplines);
    else if (json.recommended_action === 'recommend_appointment' && !crisisShown) showAppointmentBanner(text);
    else if (hasLines && !crisisShown) showSupportInfo(json.helplines);
    return true;
  }

  function deliver(text) {
    if (sending) return;
    if (!csrf()) { addError('Your session token is missing. Refresh the page and try again.', function () { deliver(text); }); return; }
    setBusy(true);
    var done = addPending();
    post('/api/chat', { message: text }, UI_TIMEOUT_MS).then(function (r) {
      done();
      if (showReply(r, text)) return;
      var msg = 'Anya could not reply. Your message was not lost: press Retry to send it again.';
      if (r.res.status === 401) { addError('Your session has expired. Log in again to continue.'); return; }
      addError(msg, function () { deliver(text); });
    }).catch(function (err) {
      done();
      addError(failMessage(err), function () { deliver(text); });
    }).then(function () { setBusy(false); });
  }

  function updateCount() {
    var left = LIMIT - input.value.length;
    count.textContent = input.value.length >= COUNT_FROM ? left + ' characters left' : '';
  }

  function renderHistory(msgs) {
    var box = byId('chat-history');
    msgs.forEach(function (m) {
      if (seenIds[m.id]) return;
      seenIds[m.id] = true;
      addMessage(m.user || 'System', m.text, 'system', box);
    });
  }

  function loadHistory(first) {
    var id = log.dataset.chatId;
    if (!id) { var s0 = byId('chat-skeleton'); if (s0) s0.remove(); return; }
    fetch('/api/chats/' + encodeURIComponent(id) + '/messages', { credentials: 'include' })
      .then(function (res) {
        if (res.status === 429) { schedule(300000); return null; }
        return res.ok ? res.json() : null;
      })
      .then(function (msgs) { if (Array.isArray(msgs)) renderHistory(msgs); })
      .catch(function () { /* history is optional; chat still works */ })
      .then(function () {
        var s = byId('chat-skeleton');
        if (s) s.remove();
        if (first) schedule(60000);
      });
  }

  function schedule(ms) {
    clearTimeout(pollTimer);
    pollTimer = setTimeout(function () {
      if (document.hidden) { schedule(60000); return; }
      loadHistory(true);
    }, ms);
  }

  document.addEventListener('DOMContentLoaded', function () {
    log = byId('chat-messages'); input = byId('chat-input'); form = byId('chat-form');
    sendBtn = byId('chat-send'); status = byId('chat-status'); count = byId('chat-count');
    if (!log || !input || !form || !sendBtn) return;

    /* Capture phase on document: the legacy handler in scripts.js is also bound to this form and would otherwise run
       first (it empties the box and posts to /api/ask, then draws into a container that does not exist). */
    document.addEventListener('submit', function (e) {
      if (e.target !== form) return;
      e.preventDefault();
      e.stopPropagation();
      var text = input.value.trim();
      if (!text || sending) return;
      removeStarters();
      addMessage('You', text, 'user');
      input.value = '';
      updateCount();
      deliver(text);
    }, true);

    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
        e.preventDefault();
        if (typeof form.requestSubmit === 'function') form.requestSubmit(); else sendBtn.click();
      }
    });
    input.addEventListener('input', updateCount);

    window.MFHChat = {
      log: log, addMessage: addMessage, addNote: addNote, addPending: addPending, addError: addError, post: post,
      setBusy: setBusy, showReply: showReply, failMessage: failMessage, toast: toast, isSending: function () { return sending; }
    };
    document.dispatchEvent(new CustomEvent('chat:ready'));
    loadHistory(true);
    window.addEventListener('beforeunload', function () { clearTimeout(pollTimer); });
  });
})();
