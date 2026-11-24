/* Inventory screens (pharmacy desk): reorder level, adjust dialog, receive-stock form.
   Idempotency: one key per open dialog or form, re-sent on retry, replaced after a success. */
(function () {
  'use strict';
  var MFH = window.MFH;

  /* ---- Reorder level, one small form per row ---- */
  var live = document.getElementById('inv-live');
  [].forEach.call(document.querySelectorAll('.js-reorder'), function (f) {
    f.addEventListener('submit', function (e) {
      e.preventDefault();
      var input = f.querySelector('input'), btn = f.querySelector('button');
      var n = parseInt(input.value, 10);
      if (isNaN(n) || n < 0) { MFH.say(live, 'Enter a reorder level of 0 or more.'); input.focus(); return; }
      MFH.busy(btn, true);
      MFH.api('PUT', f.getAttribute('data-url'), { reorder_level: n }).then(function () {
        MFH.say(live, 'Reorder level saved.'); MFH.toast('Reorder level saved', 'success');
      }, function (err) { MFH.say(live, err.message); MFH.toast(err.message, 'error'); })
        .then(function () { MFH.busy(btn, false); });
    });
  });

  /* ---- Adjust dialog on the batches screen ---- */
  var dlg = document.getElementById('adjust-dialog');
  if (dlg) {
    var url = '', key = '', delta = document.getElementById('adjust-delta'), reason = document.getElementById('adjust-reason');
    var errEl = document.getElementById('adjust-error'), save = document.getElementById('adjust-save');
    document.addEventListener('click', function (e) {
      var b = e.target.closest('[data-adjust]');
      if (!b) return;
      url = b.getAttribute('data-url'); key = MFH.newKey();
      document.getElementById('adjust-for').textContent = b.getAttribute('data-label');
      delta.value = ''; errEl.hidden = true; delta.removeAttribute('aria-invalid');
      dlg.showModal(); delta.focus();
    });
    document.getElementById('adjust-cancel').addEventListener('click', function () { dlg.close(); });
    save.addEventListener('click', function () {
      var n = parseInt(delta.value, 10);
      if (isNaN(n) || n === 0) {
        errEl.textContent = 'Enter a whole number that is not zero.'; errEl.hidden = false; delta.setAttribute('aria-invalid', 'true'); delta.focus(); return;
      }
      MFH.busy(save, true);
      MFH.api('POST', url, { delta: n, reason_code: reason.value }, { idem: key }).then(function () {
        key = MFH.newKey(); dlg.close();
        MFH.toast('Stock adjusted', 'success');
        setTimeout(function () { window.location.reload(); }, 700);
      }, function (err) { errEl.textContent = err.message; errEl.hidden = false; MFH.busy(save, false); });
    });
  }

  /* ---- Receive stock form ---- */
  var form = document.getElementById('receive-form');
  if (!form) return;
  var q = document.getElementById('rcv-q'), sel = document.getElementById('rcv-medicine');
  var rcvErr = document.getElementById('rcv-error'), rcvLive = document.getElementById('rcv-live');
  var rkey = MFH.newKey(), ctl = null;

  function fillOptions(items) {
    MFH.clear(sel);
    if (!items.length) { sel.appendChild(MFH.h('option', { value: '', text: 'No matching medicine' })); return; }
    sel.appendChild(MFH.h('option', { value: '', text: items.length + ' found, choose one' }));
    items.forEach(function (m) { sel.appendChild(MFH.h('option', { value: m.id, text: m.label })); });
  }

  q.addEventListener('input', MFH.debounce(function () {
    var term = q.value.trim();
    if (ctl) ctl.abort();
    if (term.length < 2) return;
    ctl = typeof AbortController === 'function' ? new AbortController() : null;
    MFH.api('GET', form.getAttribute('data-search-url') + MFH.qs({ q: term, active: 1 }), null, { signal: ctl && ctl.signal }).then(function (r) {
      fillOptions(r.items || []);
      MFH.say(rcvLive, (r.items || []).length + ' medicines found.');
    }, function (e) { if (!e.aborted) MFH.say(rcvLive, e.message); });
  }, 250));

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var v = function (id) { return document.getElementById(id).value.trim(); };
    var qty = parseInt(v('rcv-qty'), 10), cost = v('rcv-cost');
    var problem = !sel.value ? 'Search for a medicine and choose it.' : !v('rcv-batch') ? 'Enter the batch number.' :
      !v('rcv-expiry') ? 'Enter the expiry date.' : (isNaN(qty) || qty < 1 || qty > 100000) ? 'Enter a quantity from 1 to 100000.' : '';
    rcvErr.hidden = !problem; rcvErr.textContent = problem;
    if (problem) return;
    var btn = form.querySelector('button[type="submit"]'), label = sel.options[sel.selectedIndex].text;
    MFH.busy(btn, true);
    MFH.api('POST', form.getAttribute('data-url'), {
      medicine_id: parseInt(sel.value, 10), batch_no: v('rcv-batch'), expiry_date: v('rcv-expiry'), quantity: qty,
      unit_cost: cost === '' ? null : parseFloat(cost), supplier: v('rcv-supplier') || null, reason_code: v('rcv-reason')
    }, { idem: rkey }).then(function () {
      rkey = MFH.newKey();
      MFH.say(rcvLive, 'Received ' + qty + ' units of ' + label + '.'); MFH.toast('Stock received', 'success');
      form.reset(); MFH.clear(sel); sel.appendChild(MFH.h('option', { value: '', text: 'Search above, then choose' }));
    }, function (err) { rcvErr.textContent = err.message; rcvErr.hidden = false; })
      .then(function () { MFH.busy(btn, false); });
  });
})();
