/* Patient prescription page actions: e-prescription consent and "send to pharmacy desk".
   No Jinja here. URLs come from data-* attributes. Needs patient-common.js (PT). */
(function () {
  'use strict';

  var keys = {};   // one Idempotency-Key per prescription for this page load; a retry re-sends the same key

  function newKey() {
    if (window.crypto && typeof window.crypto.randomUUID === 'function') return window.crypto.randomUUID();
    return 'k' + Date.now().toString(36) + Math.random().toString(36).slice(2, 12);
  }

  function post(url, body, key) {
    var headers = { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': window.PT.csrf() };
    if (key) headers['Idempotency-Key'] = key;
    return fetch(url, { method: 'POST', credentials: 'same-origin', headers: headers, body: JSON.stringify(body || {}) })
      .then(function (res) {
        return res.json().catch(function () { return null; }).then(function (data) { return { ok: res.ok, status: res.status, data: data }; });
      });
  }

  function busy(btn, on) {
    if (on) btn.setAttribute('aria-busy', 'true'); else btn.removeAttribute('aria-busy');
    btn.disabled = !!on;
  }

  function failure(r) {
    var msg = r.data && r.data.message;
    window.PT.toast(msg || 'That did not work. Please try again.', 'error');
  }

  function confirmThen(btn, run) {
    if (!btn.dataset.confirm) { run(); return; }
    window.PT.ask({
      title: btn.dataset.confirmTitle || 'Please confirm',
      message: btn.dataset.confirm,
      confirmText: btn.dataset.confirmText || 'Confirm',
      danger: false
    }).then(function (yes) { if (yes) run(); });
  }

  function sendToDesk(btn) {
    var url = btn.dataset.url;
    keys[url] = keys[url] || newKey();
    busy(btn, true);
    post(url, {}, keys[url]).then(function (r) {
      busy(btn, false);
      if (!r.ok) { failure(r); return; }
      var note = btn.parentNode.querySelector('[data-rx-sent]');
      btn.hidden = true;
      if (note) note.hidden = false;
      var step = document.querySelector('[data-rx-step="sent"]');
      if (step) { step.classList.add('done'); step.textContent = 'Sent to the pharmacy desk'; }
      window.PT.toast('Sent to the pharmacy desk.', 'success');
    }).catch(function () {
      busy(btn, false);
      window.PT.toast('No connection. Your request was not lost: press the button again to retry.', 'error');
    });
  }

  function setConsent(btn) {
    var on = btn.dataset.rxConsent === 'on';
    var page = document.getElementById('rx-page');
    var url = page && page.dataset.consentUrl;
    if (!url) return;
    busy(btn, true);
    post(url, { consent: on }).then(function (r) {
      busy(btn, false);
      if (!r.ok) { failure(r); return; }
      var offBox = document.querySelector('[data-rx-consent-off]');
      var onBox = document.querySelector('[data-rx-consent-on]');
      if (offBox) offBox.hidden = on;
      if (onBox) onBox.hidden = !on;
      window.PT.toast(on ? 'E-prescriptions allowed.' : 'E-prescriptions withdrawn.', 'success');
    }).catch(function () {
      busy(btn, false);
      window.PT.toast('No connection. Please try again.', 'error');
    });
  }

  document.addEventListener('click', function (e) {
    var send = e.target.closest && e.target.closest('[data-rx-send]');
    if (send) { e.preventDefault(); confirmThen(send, function () { sendToDesk(send); }); return; }
    var consent = e.target.closest && e.target.closest('[data-rx-consent]');
    if (consent) { e.preventDefault(); confirmThen(consent, function () { setConsent(consent); }); }
  });
})();
