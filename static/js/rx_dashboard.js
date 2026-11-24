/* Prescribing section of the provider dashboard. Data: GET /provider/api/rx/dashboard (docs/CLINICAL_DESIGN.md 5.3, 5.5). */
(function () {
  'use strict';
  var root = document.getElementById('rx-dashboard');
  if (!root) return;
  var H = function () { return window.MFH.h.apply(null, arguments); };
  var cfg, live = document.getElementById('rx-status');
  var START_TEXT = 'Starting a consult records that you are seeing this patient now. Only start it while the consult is happening.';

  function timeText(t) { return t && String(t).indexOf('T') > -1 ? MFH.istTime(t) : (t || 'n/a'); }
  function fail(err) { if (!err.aborted) MFH.toast(err.message, 'error'); }

  function act(id, tpl, confirmOpts, done) {
    MFH.ask(confirmOpts).then(function (yes) {
      if (!yes) return null;
      return MFH.api('POST', MFH.fill(tpl, id), {}).then(function () { MFH.toast(done, 'success'); load(); }, fail);
    });
  }

  function consults(rows) {
    var box = MFH.clear(document.getElementById('rx-consults'));
    if (!rows.length) return box.appendChild(MFH.emptyState('No consults today.', null, 'calendar'));
    box.appendChild(MFH.table('Consults today', [
      { label: 'Time', render: function (r) { return timeText(r.time); } },
      { label: 'Patient', th: true, render: function (r) { return r.patient_name; } },
      { label: 'Type', render: function (r) { return r.modality === 'in_person' ? 'In person' : r.modality === 'video' ? 'Video' : r.modality; } },
      { label: 'Status', render: function (r) { return r.started ? MFH.badge('Consult started', 'success', 'check') : MFH.statusBadge(r.status); } },
      { label: 'Actions', render: function (r) {
        var out = [];
        if (r.can_start) out.push(H('button', { type: 'button', class: 'btn btn-secondary btn-sm', text: 'Start consult',
          'aria-label': 'Start consult with ' + r.patient_name,
          on: { click: function () { act(r.appointment_id, cfg.start_template, { title: 'Start this consult?', message: START_TEXT, confirmText: 'Start consult' }, 'Consult started.'); } } }));
        if (r.can_complete) out.push(H('button', { type: 'button', class: 'btn btn-secondary btn-sm', text: 'Complete',
          'aria-label': 'Complete consult with ' + r.patient_name,
          on: { click: function () { act(r.appointment_id, cfg.complete_template, { title: 'Complete this consult?', message: 'The appointment is marked as completed.', confirmText: 'Complete' }, 'Consult completed.'); } } }));
        return H('div', { class: 'cl-actions' }, out.length ? out : 'n/a');
      } }
    ], rows));
  }

  function removeDraft(d) {
    MFH.ask({ title: 'Delete this draft?', message: 'The draft is removed. Nothing has been issued.', confirmText: 'Delete draft', danger: true }).then(function (yes) {
      if (yes) MFH.api('DELETE', MFH.fill(cfg.draft_template, d.id)).then(function () { MFH.toast('Draft deleted.', 'success'); load(); }, fail);
    });
  }

  function drafts(rows, total) {
    var box = MFH.clear(document.getElementById('rx-drafts'));
    if (!rows.length) return box.appendChild(MFH.emptyState('No drafts.', null, 'file'));
    var ul = H('ul', { class: 'cl-list' });
    rows.forEach(function (d) {
      ul.appendChild(H('li', {}, [
        H('span', {}, [H('strong', { text: d.patient_name }), H('span', { class: 'muted', text: ', ' + d.items + ' medicine' + (d.items === 1 ? '' : 's') + ', saved ' + MFH.ist(d.updated_at) })]),
        H('span', { class: 'cl-actions' }, [
          H('a', { class: 'btn btn-secondary btn-sm', href: cfg.prescribe + '?draft_id=' + encodeURIComponent(d.id), text: 'Continue', 'aria-label': 'Continue draft for ' + d.patient_name }),
          H('button', { type: 'button', class: 'btn btn-ghost btn-sm', text: 'Delete', 'aria-label': 'Delete draft for ' + d.patient_name, on: { click: function () { removeDraft(d); } } })
        ])
      ]));
    });
    box.appendChild(ul);
    if (total > rows.length) box.appendChild(H('p', { class: 'help', text: 'Showing ' + rows.length + ' of ' + total + ' drafts.' }));
  }

  function recent(rows) {
    var box = MFH.clear(document.getElementById('rx-recent'));
    if (!rows.length) return box.appendChild(MFH.emptyState('You have not issued a prescription yet.', null, 'pill'));
    box.appendChild(MFH.table('Recently issued prescriptions', [
      { label: 'Number', th: true, render: function (r) { return H('a', { class: 'cl-link cl-mono', href: MFH.fill(cfg.detail_template, r.id), text: r.number }); } },
      { label: 'Patient', render: function (r) { return r.patient_name; } },
      { label: 'Status', render: function (r) { return MFH.statusBadge(r.status); } },
      { label: 'Issued', render: function (r) { return MFH.ist(r.issued_at); } }
    ], rows));
  }

  function render(d) {
    consults(d.consults_today || []);
    drafts(d.drafts || [], d.drafts_total || 0);
    recent(d.recent || []);
    var aw = document.getElementById('rx-awaiting');
    aw.hidden = !d.awaiting_collection;
    if (d.awaiting_collection) aw.textContent = d.awaiting_collection + ' issued prescription' + (d.awaiting_collection === 1 ? ' has' : 's have') + ' not been collected after 7 days.';
    MFH.say(live, 'Prescribing section updated.');
  }

  function load() {
    MFH.api('GET', cfg.dashboard).then(render, function (err) {
      if (err.aborted) return;
      ['rx-consults', 'rx-drafts', 'rx-recent'].forEach(function (id) {
        MFH.clear(document.getElementById(id)).appendChild(MFH.h('p', { class: 'error-text', role: 'alert', text: err.message }));
      });
    });
  }

  document.addEventListener('DOMContentLoaded', function () { cfg = MFH.cfg(); load(); });
})();
