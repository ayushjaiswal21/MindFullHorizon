/* Chat page extras: starter questions as real conversation turns, plus Copy and Print on replies.
   Needs window.MFHChat from chat_inline_1.js. Text is inserted with textContent only. */
(function () {
  'use strict';
  var C;
  var UI_TIMEOUT_MS = 12000;

  function btn(label, onClick) {
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'btn btn-ghost btn-sm';
    b.textContent = label;
    b.addEventListener('click', onClick);
    return b;
  }

  function copyText(text) {
    var p = navigator.clipboard && navigator.clipboard.writeText ? navigator.clipboard.writeText(text) : Promise.reject();
    p.then(function () { C.toast('Copied to clipboard.', 'success'); },
           function () { C.toast('Could not copy. Select the text and copy it yourself.', 'error'); });
  }

  /* Print the whole conversation (default), or one reply when `box` is given. Layout comes from wellness.css @media print. */
  function printChat(box) {
    var stamp = document.getElementById('chat-print-date');
    if (stamp) stamp.textContent = new Date().toLocaleString('en-IN', { dateStyle: 'long', timeStyle: 'short' });
    document.body.classList.add('chat-printing');
    if (box) { box.classList.add('is-printing'); document.body.classList.add('chat-print-one'); }
    function reset() {
      document.body.classList.remove('chat-printing', 'chat-print-one');
      if (box) box.classList.remove('is-printing');
      window.removeEventListener('afterprint', reset);
    }
    window.addEventListener('afterprint', reset);
    window.print();
  }

  function decorate(box) {
    var row = document.createElement('div');
    row.className = 'msg-actions no-print';
    row.append(
      btn('Copy', function () { copyText(box.querySelector('.msg-text').textContent); }),
      btn('Print', function () { printChat(box); })
    );
    box.appendChild(row);
  }

  /* A starter question is a normal turn: the question appears as the student's own bubble, then the reply. */
  function runTemplate(id, text, echo) {
    if (C.isSending()) return;
    if (echo) C.addMessage('You', text, 'user');
    C.setBusy(true);
    var done = C.addPending();
    function again() { runTemplate(id, text, false); }
    C.post('/api/chat/template', { template_id: id }, UI_TIMEOUT_MS).then(function (r) {
      done();
      var j = r.json;
      if (r.res.ok && j && j.ok) {
        var box = C.addMessage('Anya', j.reply, 'bot');
        if (j.saved) C.addNote(box, 'Saved answer');
      } else if (r.res.status === 401) {
        C.addError('Your session has expired. Log in again to continue.');
      } else {
        C.addError('Anya could not answer that. Press Retry to try again.', again);
      }
    }).catch(function (err) {
      done();
      C.addError(C.failMessage(err), again);
    }).then(function () { C.setBusy(false); });
  }

  function init() {
    C = window.MFHChat;
    if (!C || init.done) return;
    init.done = true;
    C.log.addEventListener('chat:bot', function (e) { decorate(e.detail); });
    document.querySelectorAll('[data-template-id]').forEach(function (b) {
      b.addEventListener('click', function () { runTemplate(b.dataset.templateId, b.dataset.templateText, true); });
    });
    var all = document.getElementById('chat-print-all');
    if (all) all.addEventListener('click', function () { printChat(null); });
  }

  document.addEventListener('chat:ready', init);
  if (window.MFHChat) init();
})();
