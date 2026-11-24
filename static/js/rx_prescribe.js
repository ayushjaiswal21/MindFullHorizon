/* Prescribe page core: state, step navigation, draft create and autosave, step 2 (clinical details).
   Step modules attach to MFH.rx: rx_prescribe_patient.js (1), rx_prescribe_meds.js (3), rx_prescribe_review.js (4 and issue).
   Contract: docs/CLINICAL_DESIGN.md 5.3 (screen), 5.5 (JSON). Free text is never logged or sent anywhere except the draft calls. */
(function () {
  'use strict';
  var stepsEl = document.getElementById('rx-steps');
  if (!stepsEl) return;
  var $ = function (id) { return document.getElementById(id); };
  var LABELS = ['Patient', 'Clinical details', 'Medicines', 'Review', 'Confirm'];
  var rx = (MFH.rx = {
    $: $, enter: {}, urls: {}, limits: {},
    state: { step: 1, patient: null, elig: null, attest: false, draft: null, dirty: false, items: [], stale: false,
             fields: { diagnosis: '', allergies_status: '', allergies: '', current_meds_status: '', current_meds: '', expiry_days: null },
             createKey: MFH.newKey(), issueKey: MFH.newKey() }
  });
  var S = rx.state, chain = Promise.resolve();

  /* ---------- Alerts ---------- */
  rx.alert = function (msg, reload) {
    var box = $('rx-alert'), p = $('rx-alert-text');
    p.textContent = msg;
    MFH.clear($('rx-alert-action'));
    if (reload) $('rx-alert-action').appendChild(MFH.h('button', { type: 'button', class: 'btn btn-secondary btn-sm', text: 'Reload', on: { click: function () { window.location.reload(); } } }));
    box.hidden = false;
  };
  rx.clearAlert = function () { $('rx-alert').hidden = true; };

  /* ---------- Draft: create, apply, save ---------- */
  rx.applyDraft = function (d) {
    S.draft = d;
    S.attest = !!d.same_condition_attested;
    var f = S.fields;
    ['diagnosis', 'allergies_status', 'allergies', 'current_meds_status', 'current_meds'].forEach(function (k) { f[k] = d[k] || ''; });
    if (d.expiry_days) f.expiry_days = d.expiry_days;
    if (d.patient) S.patient = d.patient;
    S.items = (d.items || []).map(function (i) {
      return { medicine_id: i.medicine_id, label: i.medicine_label, tpg_list: i.tpg_list, dose_text: i.dose_text, frequency: i.frequency,
               duration_days: i.duration_days, quantity: i.quantity, instructions: i.instructions || '' };
    });
  };
  function pick(r) { return r.prescription || r.draft || r; }

  rx.ensureDraft = function () {
    if (S.draft) return Promise.resolve(S.draft);
    return MFH.api('POST', rx.urls.drafts, { patient_id: S.patient.id, client_request_id: S.createKey, same_condition_attested: S.attest }, { idem: S.createKey })
      .then(function (r) { var d = pick(r); S.draft = d; S.draft.row_version = d.row_version; return d; });
  };

  rx.payload = function () {
    var f = S.fields;
    return {
      row_version: S.draft.row_version, same_condition_attested: S.attest, diagnosis: f.diagnosis,
      allergies_status: f.allergies_status || null, allergies: f.allergies_status === 'listed' ? f.allergies : null,
      current_meds_status: f.current_meds_status || null, current_meds: f.current_meds_status === 'listed' ? f.current_meds : null,
      expiry_days: f.expiry_days,
      items: S.items.map(function (i) {
        return { medicine_id: i.medicine_id, dose_text: i.dose_text, frequency: i.frequency, duration_days: Number(i.duration_days) || null,
                 quantity: Number(i.quantity) || null, instructions: i.instructions || null };
      })
    };
  };

  /* Saves are queued so two requests never carry the same row_version. */
  rx.save = function () {
    if (!S.draft || S.stale) return Promise.resolve(null);
    var run = function () {
      if (!S.dirty) return null;
      S.dirty = false;
      return MFH.api('PUT', MFH.fill(rx.urls.drafts + '/0', S.draft.id), rx.payload()).then(function (r) {
        S.draft.row_version = pick(r).row_version; return r;
      }, function (err) {
        S.dirty = true;
        if (err.error === 'stale_draft') { S.stale = true; rx.alert('This draft was changed in another tab. Reload to continue.', true); }
        throw err;
      });
    };
    chain = chain.then(run, run);
    return chain;
  };
  rx.dirty = function () { S.dirty = true; };

  /* ---------- Steps ---------- */
  rx.show = function (n) {
    S.step = n;
    [].forEach.call(document.querySelectorAll('[data-step]'), function (p) { p.hidden = Number(p.getAttribute('data-step')) !== n; });
    [].forEach.call(stepsEl.children, function (li, i) {
      if (i + 1 === n) li.setAttribute('aria-current', 'step'); else li.removeAttribute('aria-current');
      li.classList.toggle('is-done', i + 1 < n);
    });
    MFH.say($('rx-live'), 'Step ' + n + ' of 5: ' + LABELS[n - 1]);
    var h = document.querySelector('[data-step="' + n + '"] h2');
    if (h) { h.setAttribute('tabindex', '-1'); h.focus(); }
    if (rx.enter[n]) rx.enter[n]();
  };
  /* go(n): leaving a step saves the draft first (step 1 to 2 creates it). A failed save keeps you on the step. */
  rx.go = function (n) {
    rx.clearAlert();
    rx.collect();
    var p = S.draft ? rx.save() : Promise.resolve();
    return p.then(function () { rx.show(n); }, function (err) { if (err.error !== 'stale_draft') rx.alert('The draft could not be saved. ' + err.message); });
  };

  /* ---------- Step 2: clinical details ---------- */
  var FIELDS = ['diagnosis', 'allergies', 'current_meds'];
  var filled = false;   // the form is read back only after fillStep2 has put the draft values in it
  rx.collect = function () {
    if (!filled) return;
    var f = S.fields;
    FIELDS.forEach(function (k) { f[k] = $('f-' + k).value; });
    ['allergies_status', 'current_meds_status'].forEach(function (k) {
      var r = document.querySelector('input[name="' + k + '"]:checked'); f[k] = r ? r.value : '';
    });
    f.expiry_days = Number($('f-expiry_days').value) || null;
  };
  function fieldError(id, msg) {
    var e = $('err-' + id), i = $('f-' + id);
    e.textContent = msg || ''; e.hidden = !msg;
    if (i) { if (msg) i.setAttribute('aria-invalid', 'true'); else i.removeAttribute('aria-invalid'); }
    return !msg;
  }
  rx.fieldError = fieldError;
  function toggleText() {
    ['allergies', 'current_meds'].forEach(function (k) {
      var r = document.querySelector('input[name="' + k + '_status"]:checked');
      $('wrap-' + k).hidden = !(r && r.value === 'listed');
    });
  }
  function validateStep2() {
    rx.collect();
    var f = S.fields, ok = true;
    ok = fieldError('diagnosis', f.diagnosis.trim() ? '' : 'Enter a diagnosis or an ICD-10 code.') && ok;
    ok = fieldError('allergies_status', f.allergies_status ? '' : 'Choose one option.') && ok;
    ok = fieldError('allergies', f.allergies_status === 'listed' && !f.allergies.trim() ? 'List the allergies.' : '') && ok;
    ok = fieldError('current_meds_status', f.current_meds_status ? '' : 'Choose one option.') && ok;
    ok = fieldError('current_meds', f.current_meds_status === 'listed' && !f.current_meds.trim() ? 'List the current medicines.' : '') && ok;
    return ok;
  }
  function fillStep2() {
    var f = S.fields;
    filled = true;
    FIELDS.forEach(function (k) { $('f-' + k).value = f[k] || ''; });
    ['allergies_status', 'current_meds_status'].forEach(function (k) {
      [].forEach.call(document.querySelectorAll('input[name="' + k + '"]'), function (r) { r.checked = r.value === f[k]; });
    });
    var sel = $('f-expiry_days'), max = (S.elig && S.elig.limits && S.elig.limits.expiry_days_max) || rx.limits.expiry_days_max || 30;
    MFH.clear(sel);
    for (var d = 1; d <= max; d++) sel.appendChild(MFH.h('option', { value: d, text: d + (d === 1 ? ' day' : ' days') }));
    sel.value = String(f.expiry_days && f.expiry_days <= max ? f.expiry_days : max);
    toggleText();
  }
  rx.enter[2] = fillStep2;

  /* ---------- Start ---------- */
  document.addEventListener('DOMContentLoaded', function () {
    var cfg = MFH.cfg();
    rx.urls = cfg.urls || {}; rx.limits = cfg.limits || {};
    if (cfg.patient) S.patient = cfg.patient;
    if (cfg.draft) rx.applyDraft(cfg.draft);
    document.addEventListener('input', function (e) { if (e.target.closest && e.target.closest('[data-step]') && !e.target.hasAttribute('data-nodirty')) rx.dirty(); });
    document.addEventListener('change', function (e) {
      if (e.target.closest && e.target.closest('[data-step]') && !e.target.hasAttribute('data-nodirty')) rx.dirty();
      if (e.target.name === 'allergies_status' || e.target.name === 'current_meds_status') toggleText();
    });
    [].forEach.call(document.querySelectorAll('[data-nav]'), function (b) {
      b.addEventListener('click', function () {
        var to = Number(b.getAttribute('data-to'));
        if (b.getAttribute('data-nav') === 'next') {
          if (S.step === 2 && !validateStep2()) return;
          if (S.step === 3 && rx.validateItems && !rx.validateItems()) return;
        }
        rx.go(to);
      });
    });
    window.setInterval(function () { if (S.dirty && S.draft && !S.stale) { rx.collect(); rx.save().catch(function () {}); } }, 20000);
    if (rx.enter.init) rx.enter.init();
    var want = Number((/[?&]step=([2-3])/.exec(window.location.search) || [])[1]);   // an amended draft opens at step 2
    rx.show(S.draft ? (want || (S.items.length ? 3 : 2)) : 1);
  });
})();
