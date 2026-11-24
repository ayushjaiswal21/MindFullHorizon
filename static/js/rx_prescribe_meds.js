/* Prescribe page, step 3: medicine search (250 ms debounce, 2 characters minimum, previous request aborted) and item editors.
   GET /provider/api/rx/medicines?q=&patient_id= returns MedicineSearchItem[] (docs/CLINICAL_DESIGN.md 5.5). */
(function () {
  'use strict';
  var rx = window.MFH && MFH.rx;
  if (!rx) return;
  var $ = rx.$, S = rx.state, H = MFH.h;
  var ctl = null;
  var HELP = 'Availability is a guide. Stock is not held for this prescription.';
  var EMPTY_CATALOGUE = 'No medicines are available yet. Ask your institution administrator to add them.';
  var ITEM_FIELDS = [
    ['dose_text', 'Dose', 60, 'text', '1 tablet'], ['frequency', 'Frequency', 60, 'text', 'twice daily after food'],
    ['duration_days', 'Duration in days', null, 'number', ''], ['quantity', 'Quantity', null, 'number', ''],
    ['instructions', 'Instructions (optional)', 200, 'text', '']
  ];

  function maxItems() { return (S.elig && S.elig.limits && S.elig.limits.max_items) || rx.limits.max_items || 6; }
  function maxDays() { return (S.elig && S.elig.limits && S.elig.limits.max_days) || rx.limits.max_days || 14; }
  function say(msg) { MFH.say($('med-msg'), msg); }

  /* ---------- Items ---------- */
  function renderItems() {
    var box = MFH.clear($('rx-items'));
    $('items-count').textContent = 'Medicines in this prescription (' + S.items.length + ' of ' + maxItems() + ')';
    if (!S.items.length) {
      box.appendChild(MFH.emptyState('No medicines added yet.', 'Search above and add at least one medicine.', 'pill'));
      return;
    }
    S.items.forEach(function (it, idx) { box.appendChild(itemEditor(it, idx)); });
  }

  function itemEditor(it, idx) {
    var n = idx + 1, wrap = H('div', { class: 'cl-item', id: 'item-' + idx });
    wrap.appendChild(H('div', { class: 'cl-item-head' }, [
      H('h3', {}, [it.label, ' ', MFH.badge('List ' + it.tpg_list, 'neutral')]),
      H('button', { type: 'button', class: 'btn btn-ghost btn-sm', text: 'Remove', 'aria-label': 'Remove ' + it.label,
        on: { click: function () { S.items.splice(idx, 1); rx.dirty(); renderItems(); say(it.label + ' removed.'); } } })
    ]));
    var grid = H('div', { class: 'cl-item-grid' });
    ITEM_FIELDS.forEach(function (f) {
      var id = 'item-' + idx + '-' + f[0];
      var attrs = { class: 'input', id: id, type: f[3], value: it[f[0]] == null ? '' : it[f[0]], 'data-nodirty': true, 'aria-describedby': id + '-err' };
      if (f[2]) attrs.maxlength = f[2];
      if (f[3] === 'number') { attrs.min = 1; attrs.max = f[0] === 'duration_days' ? maxDays() : 500; attrs.inputmode = 'numeric'; }
      if (f[4]) attrs.placeholder = f[4];
      var input = H('input', attrs);
      input.addEventListener('input', function () { it[f[0]] = input.value; rx.dirty(); });
      grid.appendChild(H('div', { class: 'field' }, [H('label', { class: 'label', for: id, text: f[1] }), input,
        H('p', { class: 'error-text', id: id + '-err', hidden: true })]));
    });
    wrap.appendChild(grid);
    return wrap;
  }

  /* Client-side completeness check before Review; the server repeats every rule. */
  rx.validateItems = function () {
    var ok = true, firstBad = null;
    if (!S.items.length) { rx.alert('Add at least one medicine.'); return false; }
    S.items.forEach(function (it, idx) {
      var wrap = $('item-' + idx), bad = false;
      ITEM_FIELDS.forEach(function (f) {
        var key = f[0], id = 'item-' + idx + '-' + key, e = $(id + '-err'), msg = '';
        var v = String(it[key] == null ? '' : it[key]).trim();
        if (key === 'instructions') msg = '';
        else if (!v) msg = 'Enter a value.';
        else if (key === 'duration_days' && (Number(v) < 1 || Number(v) > maxDays())) msg = 'Duration must be 1 to ' + maxDays() + ' days.';
        else if (key === 'quantity' && (Number(v) < 1 || Number(v) > 500)) msg = 'Quantity must be 1 to 500.';
        e.textContent = msg; e.hidden = !msg;
        if (msg) { $(id).setAttribute('aria-invalid', 'true'); bad = true; if (!firstBad) firstBad = $(id); } else $(id).removeAttribute('aria-invalid');
      });
      wrap.setAttribute('data-invalid', bad ? 'true' : 'false');
      ok = ok && !bad;
    });
    if (!ok) { rx.alert('Some medicines need more detail.'); if (firstBad) firstBad.focus(); }
    return ok;
  };
  /* Used by the review step to jump to an item. */
  rx.focusItem = function (idx) { var el = $('item-' + idx + '-dose_text'); if (el) el.focus(); };

  /* ---------- Search ---------- */
  function add(m) {
    if (S.items.length >= maxItems()) { say(rx.limitText({ max_items: maxItems(), max_days: maxDays() })); return; }
    if (S.items.some(function (i) { return i.medicine_id === m.id; })) { say('This medicine is already in the prescription.'); return; }
    S.items.push({ medicine_id: m.id, label: m.label, tpg_list: m.tpg_list, dose_text: '', frequency: '', duration_days: '', quantity: '', instructions: '' });
    rx.dirty(); renderItems(); renderResults(S.lastResults || []);
    say(m.label + ' added.');
    var d = $('item-' + (S.items.length - 1) + '-dose_text'); if (d) d.focus();
  }

  function renderResults(items) {
    S.lastResults = items;
    var box = MFH.clear($('med-results'));
    var ul = H('ul', { class: 'cl-results' });
    items.forEach(function (m) {
      var added = S.items.some(function (i) { return i.medicine_id === m.id; });
      var why = m.prescribable ? null : H('p', { class: 'cl-blocked', id: 'blk-' + m.id, text: m.blocked_text || 'This medicine cannot be prescribed in this system.' });
      ul.appendChild(H('li', {}, [
        H('div', { class: 'cl-result-main' }, [H('strong', { text: m.label }),
          H('div', { class: 'cl-result-meta' }, [MFH.badge('List ' + m.tpg_list, 'neutral'), MFH.availBadge(m.availability)])]),
        H('button', { type: 'button', class: 'btn btn-secondary btn-sm', text: added ? 'Added' : 'Add', disabled: !m.prescribable || added,
          'aria-label': (added ? 'Added: ' : 'Add ') + m.label, 'aria-describedby': why ? 'blk-' + m.id : null, on: { click: function () { add(m); } } }),
        why
      ]));
    });
    box.appendChild(ul);
  }

  function search() {
    var q = $('med-q').value.trim(), box = $('med-results');
    if (ctl) ctl.abort();
    if (q.length < 2) { MFH.clear(box); say(''); return; }
    ctl = window.AbortController ? new AbortController() : null;
    MFH.api('GET', rx.urls.medicines + MFH.qs({ q: q, patient_id: S.patient && S.patient.id }), null, { signal: ctl && ctl.signal }).then(function (r) {
      var items = r.items || [];
      if (!items.length) {
        MFH.clear(box).appendChild(r.catalogue_empty ? MFH.emptyState(EMPTY_CATALOGUE, null, 'pill')
          : MFH.emptyState('No medicines match your search.', 'Try the generic name. If you expect a medicine here, ask your institution administrator to add it.', 'search'));
        say('No medicines found.');
        return;
      }
      renderResults(items);
      say(items.length + (items.length === 1 ? ' medicine found.' : ' medicines found.'));
    }, function (err) { if (!err.aborted) say(err.message); });
  }

  rx.enter[3] = function () {
    $('limits-text').textContent = rx.limitText({ max_items: maxItems(), max_days: maxDays() }) + ' ' + HELP;
    renderItems();
  };
  var prevInit = rx.enter.init;
  rx.enter.init = function () {
    if (prevInit) prevInit();
    $('med-q').addEventListener('input', MFH.debounce(search, 250));
  };
})();
