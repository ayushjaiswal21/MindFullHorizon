/* Prescribe page, step 4 (review) and the issue call.
   POST .../validate shows errors and warnings; POST .../issue sends Idempotency-Key and acknowledged_warnings (docs/CLINICAL_DESIGN.md 3.5, 3.7, 5.3, 5.5).
   The issue key is made when the page opens and re-sent on a network retry, so a retry cannot issue twice. */
(function () {
  'use strict';
  var rx = window.MFH && MFH.rx;
  if (!rx) return;
  var $ = rx.$, S = rx.state, H = MFH.h;
  var result = null;
  var STATUS_TEXT = { none_reported: 'None reported', unknown: 'Not recorded' };
  var FIELD_STEP = { diagnosis: 2, allergies: 2, allergies_status: 2, current_meds: 2, current_meds_status: 2, expiry_days: 2 };

  function plain(status, text) { return status === 'listed' ? (text || 'Not recorded') : (STATUS_TEXT[status] || 'Not recorded'); }

  function validUntil() {
    var days = Number(S.fields.expiry_days) || 1;
    var today = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kolkata' }).format(new Date());
    var d = new Date(today + 'T00:00:00Z');
    d.setUTCDate(d.getUTCDate() + days);
    return MFH.istDate(d.toISOString().slice(0, 10));
  }

  function summary() {
    var f = S.fields, box = MFH.clear($('rv-summary'));
    box.appendChild(H('dl', { class: 'cl-dl cl-block' }, [
      H('dt', { text: 'Patient' }), H('dd', { text: S.patient ? S.patient.name : 'n/a' }),
      H('dt', { text: 'Diagnosis' }), H('dd', { text: f.diagnosis || 'n/a' }),
      H('dt', { text: 'Allergies' }), H('dd', { text: plain(f.allergies_status, f.allergies) }),
      H('dt', { text: 'Current medicines' }), H('dd', { text: plain(f.current_meds_status, f.current_meds) }),
      H('dt', { text: 'Valid until' }), H('dd', { text: validUntil() + ', end of day' })
    ]));
    box.appendChild(MFH.table('Medicines in this prescription', [
      { label: 'Medicine', th: true, render: function (i) { return i.label; } },
      { label: 'Dose', render: function (i) { return i.dose_text; } },
      { label: 'Frequency', render: function (i) { return i.frequency; } },
      { label: 'Days', render: function (i) { return i.duration_days; } },
      { label: 'Quantity', render: function (i) { return i.quantity; } }
    ], S.items));
  }

  function jump(e) {
    var step = e.item ? 3 : (FIELD_STEP[e.field] || 2);
    rx.go(step).then(function () {
      var el = e.item ? null : document.getElementById('f-' + e.field);
      if (e.item) rx.focusItem(e.item - 1); else if (el) el.focus();
    });
  }

  function render(r) {
    result = r;
    var errs = MFH.clear($('rv-errors')), warns = MFH.clear($('rv-warnings'));
    (r.errors || []).length && errs.appendChild(H('div', { class: 'alert alert-danger' }, [MFH.icon('alert'),
      H('div', {}, [H('p', { text: 'Fix these before you issue.' }), H('ul', { class: 'cl-errors' }, r.errors.map(function (e) {
        return H('li', {}, [e.message + ' ', H('button', { type: 'button', class: 'cl-link-btn', text: 'Go to this' + (e.item ? ' medicine' : ' field'), on: { click: function () { jump(e); } } })]);
      }))])]));
    (r.warnings || []).forEach(function (w, i) {
      var id = 'ack-' + i;
      warns.appendChild(H('div', { class: 'cl-warn' }, [
        H('p', {}, [MFH.icon('alert'), ' ', w.message]),
        H('div', { class: 'check' }, [H('input', { type: 'checkbox', id: id, 'data-code': w.code, on: { change: refresh } }), H('label', { for: id, text: 'I have seen this' })])
      ]));
    });
    refresh();
  }

  function acknowledged() {
    var all = [].slice.call(document.querySelectorAll('#rv-warnings input[type="checkbox"]'));
    return { all: all.every(function (c) { return c.checked; }), codes: all.map(function (c) { return c.getAttribute('data-code'); }).filter(function (c, i, a) { return a.indexOf(c) === i; }) };
  }
  function refresh() {
    var ok = result && (result.errors || []).length === 0 && acknowledged().all && !S.stale;
    $('rv-issue').disabled = !ok;
    MFH.say($('rx-live'), ok ? 'Ready to issue.' : '');
  }

  function review() {
    rx.collect();
    summary();
    MFH.clear($('rv-errors')); MFH.clear($('rv-warnings')); $('rv-issue').disabled = true; result = null;
    var run = S.dirty ? rx.save() : Promise.resolve();
    run.then(function () { return MFH.api('POST', MFH.fill(rx.urls.drafts + '/0/validate', S.draft.id), {}); })
      .then(render, function (err) { if (err.error !== 'stale_draft') rx.alert(err.message); });
  }
  rx.enter[4] = review;

  function showIssueErrors(err) {
    var b = err.body || {};
    if (err.error === 'warnings_unacknowledged' && b.warnings) { render({ errors: [], warnings: b.warnings }); rx.alert('Some warnings need your attention before this can be issued.'); return; }
    if (b.errors && b.errors.length) { render({ errors: b.errors, warnings: b.warnings || [] }); rx.alert(err.message); return; }
    if (err.error === 'stale_draft') { S.stale = true; rx.alert('This draft was changed in another tab. Reload to continue.', true); return; }
    rx.alert(err.status === 0 ? 'Could not reach the server. Your request was not lost: press Issue prescription again. It cannot be issued twice.' : err.message);
  }

  function issue() {
    var btn = $('rv-issue'), names = S.items.map(function (i) { return i.label; }).join('; ');
    var msg = 'Patient: ' + (S.patient ? S.patient.name : '') + '. Medicines: ' + names + '. Valid until ' + validUntil() + ', end of day. ' +
      'This cannot be edited after it is issued. You can cancel it or write a new one.';
    MFH.ask({ title: 'Issue this prescription?', message: msg, confirmText: 'Issue prescription' }).then(function (yes) {
      if (!yes) return null;
      rx.clearAlert(); MFH.busy(btn, true); $('rx-steps').children[4].setAttribute('aria-current', 'step');
      return MFH.api('POST', MFH.fill(rx.urls.drafts + '/0/issue', S.draft.id), { acknowledged_warnings: acknowledged().codes }, { idem: S.issueKey }).then(function (r) {
        var p = r.prescription || {};
        window.location.href = MFH.fill(rx.urls.detail_template, p.id || S.draft.id) + '?issued=1';
      }, function (err) {
        if (err.status >= 400 && err.status < 500) S.issueKey = MFH.newKey();   // a definite refusal: next try is a new attempt
        showIssueErrors(err);
        MFH.busy(btn, false); $('rx-steps').children[4].removeAttribute('aria-current'); refresh();
      });
    });
  }

  var prevInit = rx.enter.init;
  rx.enter.init = function () {
    if (prevInit) prevInit();
    $('rv-issue').addEventListener('click', issue);
  };
})();
