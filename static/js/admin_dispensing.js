/* Dispensing desk: prescription lookup, and the two-step dispense (Prepare shows the plan, Confirm writes it).
   Assumed: lookup returns {rx_id}; prepare takes {lines: [{item_id, quantity}]} and returns the DispensePlan of 5.5. */
(function () {
  'use strict';
  var MFH = window.MFH;

  /* ---- Lookup ---- */
  var lookup = document.getElementById('lookup-form');
  if (lookup) {
    var num = document.getElementById('rx-number'), lerr = document.getElementById('lookup-error'), llive = document.getElementById('lookup-live');
    lookup.addEventListener('submit', function (e) {
      e.preventDefault();
      var n = num.value.trim().toUpperCase().replace(/\s+/g, '');
      lerr.hidden = !!n;
      if (!n) { lerr.textContent = 'Enter the prescription number.'; num.focus(); return; }
      var btn = lookup.querySelector('button[type="submit"]');
      MFH.busy(btn, true); MFH.say(llive, 'Looking up.');
      MFH.api('POST', lookup.getAttribute('data-url'), { number: n }).then(function (r) {
        window.location.href = lookup.getAttribute('data-detail-url') + '/' + r.rx_id;
      }, function (err) {
        lerr.textContent = err.message; lerr.hidden = false; MFH.say(llive, ''); MFH.busy(btn, false); num.focus();
      });
    });
  }

  /* ---- Dispense ---- */
  var prep = document.getElementById('prepare-btn');
  if (!prep) return;
  var cfg = MFH.cfg(), plan = document.getElementById('plan'), panel = document.getElementById('confirm-panel');
  var cbtn = document.getElementById('confirm-btn'), cerr = document.getElementById('confirm-error'), receipt = document.getElementById('receipt');
  var token = '', key = MFH.newKey();

  function reset() { token = ''; panel.hidden = true; MFH.clear(plan); }
  [].forEach.call(document.querySelectorAll('[data-item]'), function (i) { i.addEventListener('input', reset); });

  function show(p) {
    token = p.token;
    var kids = [MFH.h('h3', { class: 'text-lg mb-3', text: 'Plan' })];
    (p.warnings || []).forEach(function (w) { kids.push(MFH.h('div', { class: 'alert alert-warning' }, [MFH.icon('alert'), MFH.h('p', { text: w.message || w })])); });
    kids.push(MFH.table('Planned stock for each medicine', [
      { label: 'Medicine', th: true, render: function (l) { return l.medicine_label; } },
      { label: 'Giving', render: function (l) { return l.requested + ' of ' + l.remaining; } },
      { label: 'From batches', render: function (l) {
        return l.allocations && l.allocations.length ? MFH.h('ul', { class: 'cl-list' }, l.allocations.map(function (a) {
          return MFH.h('li', { text: 'Batch ' + a.batch_no + ', expires ' + MFH.istDate(a.expiry_date) + ': ' + a.quantity + ' units' }); })) : 'No stock';
      } },
      { label: 'Short by', render: function (l) {
        return l.shortfall ? MFH.badge(l.shortfall + ' units short', 'warning', 'alert') : MFH.badge('None', 'success', 'check'); } }
    ], p.lines || []));
    var mins = Math.max(1, Math.round((p.expires_in || 600) / 60));
    kids.push(MFH.h('p', { class: 'help', text: 'This plan is valid for ' + mins + ' minutes. Nothing has been recorded yet.' }));
    MFH.clear(plan); kids.forEach(function (k) { plan.appendChild(k); });
    panel.hidden = false; cerr.hidden = true;
  }

  prep.addEventListener('click', function () {
    var lines = [], bad = '';
    [].forEach.call(document.querySelectorAll('[data-item]'), function (i) {
      if (i.disabled) return;
      var n = parseInt(i.value, 10), max = parseInt(i.getAttribute('max'), 10);
      if (isNaN(n) || n < 0 || n > max) bad = 'Quantities must be between 0 and the remaining amount.';
      else if (n > 0) lines.push({ item_id: parseInt(i.getAttribute('data-item'), 10), quantity: n });
    });
    if (!bad && !lines.length) bad = 'Choose at least one quantity above zero.';
    if (bad) { MFH.clear(plan); plan.appendChild(MFH.h('p', { class: 'error-text', role: 'alert', text: bad })); return; }
    MFH.busy(prep, true);
    MFH.api('POST', cfg.prepare, { lines: lines }).then(show, function (e) {
      MFH.clear(plan); plan.appendChild(MFH.h('p', { class: 'error-text', role: 'alert', text: e.message }));
    }).then(function () { MFH.busy(prep, false); });
  });

  cbtn.addEventListener('click', function () {
    var name = document.getElementById('ph-name').value.trim(), reg = document.getElementById('ph-reg').value.trim();
    var problem = !document.getElementById('identity').checked ? 'Tick the box to confirm you checked the identity and the number.' :
      (name.length < 3 || name.length > 100) ? 'Enter the pharmacist name (3 to 100 characters).' :
      (reg.length < 3 || reg.length > 40) ? 'Enter the pharmacist registration number (3 to 40 characters).' : '';
    cerr.hidden = !problem; cerr.textContent = problem;
    if (problem) return;
    MFH.ask({ title: 'Confirm dispensing?', message: 'Stock is taken from the shelf records now. A mistake can be reversed for 24 hours.', confirmText: 'Confirm dispensing' }).then(function (yes) {
      if (!yes) return;
      MFH.busy(cbtn, true);
      MFH.api('POST', cfg.confirm, { token: token, identity_checked: true, pharmacist_name: name, pharmacist_reg_no: reg }, { idem: key }).then(function (r) {
        key = MFH.newKey(); reset(); prep.disabled = true;
        MFH.clear(receipt);
        receipt.appendChild(MFH.h('div', { class: 'alert alert-success' }, [MFH.icon('check'), MFH.h('div', {}, [
          MFH.h('p', { text: (r.replayed ? 'Already recorded. ' : 'Dispensed. ') + 'Prescription status: ' + String(r.status || '').replace(/_/g, ' ') + '.' }),
          r.group_ref ? MFH.h('p', { class: 'cl-mono', text: 'Reference ' + r.group_ref }) : null,
          MFH.h('a', { class: 'cl-link', href: window.location.href, text: 'Reload to see the lines you can reverse' })])]));
        MFH.toast('Dispensed', 'success');
      }, function (e) {
        if (e.error === 'plan_stale' && e.body && e.body.plan) {
          key = MFH.newKey(); show(e.body.plan);
          cerr.textContent = 'Stock changed since you prepared this. Review the new plan and confirm again.'; cerr.hidden = false;
        } else { cerr.textContent = e.message; cerr.hidden = false; }
        MFH.busy(cbtn, false);
      });
    });
  });
})();
