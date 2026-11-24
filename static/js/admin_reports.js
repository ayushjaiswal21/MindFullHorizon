/* Reports screen: loads GET /admin/api/reports/<name> and draws a table.
   Assumed response: {success, items: [...], meta}. Row keys follow CLINICAL_DESIGN 4.11 (see COLS). */
(function () {
  'use strict';
  var MFH = window.MFH;
  var out = document.getElementById('report-out');
  if (!out) return;
  var cfg = MFH.cfg(), form = document.getElementById('report-filters');
  var live = document.getElementById('report-live'), csv = document.getElementById('report-csv');
  var pageNo = 1, ctl = null;

  function col(label, key, o) {
    o = o || {};
    return { label: label, th: !!o.th, render: function (r) {
      var v = r[key];
      if (o.fn) return o.fn(v, r);
      return v == null ? null : String(v);
    } };
  }
  var HIDDEN = 'Hidden, fewer than 5 patients';
  var COLS = {
    stock: [col('Medicine', 'label', { th: true }), col('Usable on hand', 'usable'), col('Expired, awaiting write-off', 'expired'),
      col('Reorder level', 'reorder_level'), col('Status', 'status', { fn: function (v) { return MFH.availBadge(v, true); } })],
    expiring: [col('Medicine', 'label', { th: true }), col('Batch', 'batch_no'), col('Expiry date', 'expiry_date'), col('Quantity', 'quantity'),
      col('Days left', 'days_left')],
    log: [col('Time', 'time', { fn: function (v) { return MFH.ist(v); } }), col('Kind', 'kind'), col('Prescription', 'rx_number'),
      col('Medicine', 'label'), col('Batch', 'batch_no'), col('Change', 'delta'), col('Reason', 'reason_code')],
    usage: [col('Medicine', 'label', { th: true }),
      col('Units given', 'units', { fn: function (v, r) { return r.suppressed || v == null ? HIDDEN : String(v); } }),
      col('Prescriptions', 'prescriptions')]
  };
  if (cfg.tab === 'log' && cfg.desk) COLS.log.splice(6, 0, col('Dispensed by', 'dispenser_label'));
  var CAPTION = { stock: 'Stock on hand', expiring: 'Batches expiring soon', log: 'Dispensing log', usage: 'Usage by medicine' };
  var EMPTY = { stock: 'No stock recorded yet.', expiring: 'No batches expire in this period.', log: 'No dispensing in this period.', usage: 'No medicines were given in this period.' };

  function params() {
    var p = {};
    if (form) [].forEach.call(form.elements, function (el) { if (el.name && el.value) p[el.name] = el.value; });
    return p;
  }

  function load(page) {
    pageNo = page || 1;
    var p = params(); p.page = pageNo;
    if (ctl) ctl.abort();
    ctl = typeof AbortController === 'function' ? new AbortController() : null;
    out.setAttribute('aria-busy', 'true'); MFH.say(live, 'Loading the report.');
    if (csv) { var q = params(); csv.href = cfg.csv + MFH.qs(q); }
    MFH.api('GET', cfg.api + MFH.qs(p), null, { signal: ctl && ctl.signal }).then(function (r) {
      var rows = r.items || [];
      MFH.clear(out);
      out.appendChild(MFH.table(CAPTION[cfg.tab], COLS[cfg.tab], rows, MFH.emptyState('Nothing to show', EMPTY[cfg.tab], 'file')));
      var pg = MFH.pager(r.meta, load);
      if (pg) out.appendChild(pg);
      MFH.initTimes(out);
      MFH.say(live, rows.length + ' rows shown.');
    }, function (e) {
      if (e.aborted) return;
      MFH.clear(out);
      out.appendChild(MFH.h('div', { class: 'alert alert-danger', role: 'alert' }, [MFH.icon('alert'), MFH.h('p', { text: e.message })]));
      MFH.say(live, 'The report could not be loaded.');
    }).then(function () { out.setAttribute('aria-busy', 'false'); });
  }

  if (form) form.addEventListener('submit', function (e) { e.preventDefault(); load(1); });
  load(1);
})();
