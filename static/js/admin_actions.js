/* Generic admin action button: <button data-api-post="/url" [data-method] [data-body='{json}'] [data-idem]
   [data-ask="message" data-ask-title data-ask-text data-ask-danger] [data-done="toast text"]>.
   Asks first when data-ask is present, calls the API, shows a toast, then reloads the page.
   data-idem keeps ONE Idempotency-Key per button, sent again on retry and dropped after a success. */
(function () {
  'use strict';
  var MFH = window.MFH;
  var keys = new WeakMap();

  function run(btn) {
    var body = null;
    try { body = btn.dataset.body ? JSON.parse(btn.dataset.body) : null; } catch (e) { body = null; }
    var opts = {};
    if (btn.hasAttribute('data-idem')) {
      if (!keys.has(btn)) keys.set(btn, MFH.newKey());
      opts.idem = keys.get(btn);
    }
    MFH.busy(btn, true);
    return MFH.api(btn.dataset.method || 'POST', btn.dataset.apiPost, body, opts).then(function () {
      keys.delete(btn);
      MFH.toast(btn.dataset.done || 'Done', 'success');
      setTimeout(function () { window.location.reload(); }, 700);
    }, function (err) {
      // A network failure keeps the key, so pressing again cannot repeat the action twice.
      if (err.status && err.status < 500 && err.status !== 409) keys.delete(btn);
      MFH.toast(err.message, 'error');
      MFH.busy(btn, false);
    });
  }

  document.addEventListener('click', function (e) {
    var btn = e.target.closest && e.target.closest('[data-api-post]');
    if (!btn || btn.disabled || btn.getAttribute('aria-busy') === 'true') return;
    e.preventDefault();
    if (!btn.hasAttribute('data-ask')) { run(btn); return; }
    MFH.ask({
      title: btn.dataset.askTitle || 'Please confirm', message: btn.dataset.ask,
      confirmText: btn.dataset.askText || 'Confirm', danger: btn.hasAttribute('data-ask-danger')
    }).then(function (yes) { if (yes) run(btn); });
  });
})();
