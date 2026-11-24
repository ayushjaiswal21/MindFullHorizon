/* My prescriptions: tabs Drafts, Issued, Closed. GET /provider/api/rx/prescriptions?status=&q=&page= (docs/CLINICAL_DESIGN.md 5.3, 5.5). */
(function () {
  'use strict';
  var app = document.getElementById('rl-app');
  if (!app) return;
  var H = function () { return window.MFH.h.apply(null, arguments); };
  var cfg, tab = app.getAttribute('data-tab'), page = 1, ctl = null;
  var EMPTY = { draft: 'No drafts.', issued: 'No issued prescriptions.', closed: 'Nothing closed yet.' };

  function table(rows) {
    var cols = [
      { label: 'Number', th: true, render: function (r) {
        var href = tab === 'draft' ? cfg.prescribe + '?draft_id=' + encodeURIComponent(r.id) : MFH.fill(cfg.detail_template, r.id);
        return H('a', { class: 'cl-link' + (r.number ? ' cl-mono' : ''), href: href, text: r.number || 'Draft, continue' });
      } },
      { label: 'Patient', render: function (r) { return r.patient_name; } },
      { label: 'Date', render: function (r) { return MFH.ist(r.issued_at || r.updated_at); } },
      { label: 'Medicines', render: function (r) { return String(r.items); } },
      { label: 'Status', render: function (r) { return MFH.statusBadge(r.status); } }
    ];
    if (tab !== 'draft') cols.push({ label: 'Collection', render: function (r) { return MFH.COLLECTION[r.collection] || 'n/a'; } });
    return MFH.table('Prescriptions', cols, rows);
  }

  function load() {
    var q = (document.getElementById('rl-q') || { value: '' }).value.trim();
    if (ctl) ctl.abort();
    ctl = window.AbortController ? new AbortController() : null;
    MFH.api('GET', cfg.list + MFH.qs({ status: tab, q: q, page: page }), null, { signal: ctl && ctl.signal }).then(function (r) {
      var rows = r.items || [], box = MFH.clear(document.getElementById('rl-list'));
      box.appendChild(rows.length ? table(rows) : MFH.emptyState(q ? 'No prescription matches that number.' : EMPTY[tab], q ? 'Check the number and try again.' : null, q ? 'search' : 'file'));
      var pg = MFH.clear(document.getElementById('rl-pager')), p = MFH.pager(r.meta, function (n) { page = n; load(); });
      if (p) pg.appendChild(p);
      MFH.say(document.getElementById('rl-status'), rows.length + (rows.length === 1 ? ' prescription shown.' : ' prescriptions shown.'));
    }, function (err) {
      if (err.aborted) return;
      MFH.clear(document.getElementById('rl-list')).appendChild(H('p', { class: 'error-text', role: 'alert', text: err.message }));
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    cfg = MFH.cfg();
    var q = document.getElementById('rl-q');
    if (q) q.addEventListener('input', MFH.debounce(function () { page = 1; load(); }, 250));
    load();
  });
})();
