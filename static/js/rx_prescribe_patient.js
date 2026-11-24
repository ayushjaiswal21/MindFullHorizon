/* Prescribe page, step 1: pick an assigned patient and show eligibility (consult, TPG lists, consent, limits).
   GET /provider/api/rx/patients?q= and GET /provider/api/rx/eligibility?patient_id=&attest= (docs/CLINICAL_DESIGN.md 5.3, 5.5). */
(function () {
  'use strict';
  var rx = window.MFH && MFH.rx;
  if (!rx) return;
  var $ = rx.$, S = rx.state, H = MFH.h;
  var searchCtl = null, eligCtl = null;
  var CONTEXT = {
    first: 'First consult: medicines from List O and List A only',
    follow_up: 'Follow-up: List B also allowed',
    in_person: 'In-person consult: lists O, A and B'
  };
  var BLOCKERS = {
    no_consult: 'No consult is in progress with this patient.',
    no_consent: 'Ask the patient to allow e-prescriptions on their Prescriptions page.',
    patient_not_assigned: 'This patient is not assigned to you.'
  };
  var MODALITY = { video: 'video', in_person: 'in person' };

  rx.limitText = function (l) {
    l = l || {};
    return 'Up to ' + (l.max_items || 6) + ' medicines. Up to ' + (l.max_days || 14) + ' days each.';
  };

  function renderPanel() {
    var box = MFH.clear($('pt-panel')), e = S.elig, next = $('s1-next');
    box.hidden = !S.patient;
    if (!S.patient) { next.disabled = true; return; }
    var blockers = e ? (e.blockers || []) : null;
    var consult = e && e.consult ? 'Consult in progress since ' + MFH.istTime(e.consult.started_at) + ', ' + (MODALITY[e.consult.modality] || e.consult.modality) : 'No consult in progress';
    box.appendChild(H('h3', { text: S.patient.name }));
    if (!e) { box.appendChild(H('p', { class: 'muted', text: 'Checking consult and consent.' })); next.disabled = true; return; }
    box.appendChild(H('dl', { class: 'cl-dl' }, [
      H('dt', { text: 'Consult' }), H('dd', { text: consult }),
      H('dt', { text: 'Medicines allowed' }), H('dd', { text: CONTEXT[e.tpg_context] || 'Not known until a consult is started' }),
      H('dt', { text: 'E-prescription consent' }), H('dd', { text: e.erx_consent ? 'The patient has allowed e-prescriptions' : 'Not given' }),
      H('dt', { text: 'Limits' }), H('dd', { text: rx.limitText(e.limits) })
    ]));
    if (blockers.length) {
      var ul = H('ul', { class: 'cl-errors' });
      blockers.forEach(function (c) {
        var li = H('li', { text: BLOCKERS[c] || 'You cannot prescribe for this patient yet (' + c + ').' });
        if (c === 'no_consult' && rx.urls.appointments) li.appendChild(H('span', {}, [' ', H('a', { class: 'cl-link', href: rx.urls.appointments, text: 'Start a consult' })]));
        ul.appendChild(li);
      });
      box.appendChild(H('div', { class: 'alert alert-warning', role: 'status' }, [MFH.icon('alert'), ul]));
    }
    $('attest-wrap').hidden = !e.follow_up_possible;
    $('attest').checked = S.attest;
    next.disabled = blockers.length > 0;
  }

  rx.loadEligibility = function () {
    if (!S.patient) return Promise.resolve();
    if (eligCtl) eligCtl.abort();
    eligCtl = window.AbortController ? new AbortController() : null;
    S.elig = null; renderPanel();
    return MFH.api('GET', rx.urls.eligibility + MFH.qs({ patient_id: S.patient.id, attest: S.attest ? 1 : 0 }), null, { signal: eligCtl && eligCtl.signal })
      .then(function (r) { S.elig = r; if (r.limits) rx.limits = r.limits; renderPanel(); MFH.say($('rx-live'), 'Eligibility checked for ' + S.patient.name + '.'); },
        function (err) { if (!err.aborted) { rx.alert(err.message); } });
  };

  function select(p) {
    S.patient = p; S.attest = false;
    MFH.clear($('pt-results'));
    rx.loadEligibility();
  }

  function renderResults(r, q) {
    var box = MFH.clear($('pt-results')), items = r.items || [];
    if (!items.length) {
      box.appendChild(q ? MFH.emptyState('No patients match your search.', 'Check the spelling or clear the search box.', 'search')
        : MFH.emptyState('No patients are assigned to you yet.', 'A patient appears here after booking an appointment with you.', 'users'));
      return;
    }
    var ul = H('ul', { class: 'cl-results' });
    items.forEach(function (p) {
      ul.appendChild(H('li', {}, [H('strong', { text: p.name }),
        H('button', { type: 'button', class: 'btn btn-secondary btn-sm', text: 'Select', 'aria-label': 'Select ' + p.name, on: { click: function () { select(p); } } })]));
    });
    box.appendChild(ul);
    if (r.meta && r.meta.has_next) box.appendChild(H('p', { class: 'help', text: 'More patients match. Type more of the name to narrow the list.' }));
  }

  function search() {
    var q = $('pt-q').value.trim();
    if (searchCtl) searchCtl.abort();
    searchCtl = window.AbortController ? new AbortController() : null;
    MFH.api('GET', rx.urls.patients + MFH.qs({ q: q }), null, { signal: searchCtl && searchCtl.signal })
      .then(function (r) { renderResults(r, q); }, function (err) { if (!err.aborted) rx.alert(err.message); });
  }

  rx.enter[1] = function () {
    var locked = !!S.draft;                       // a draft belongs to one patient
    $('pt-search').hidden = locked;
    renderPanel();
    if (!locked && !S.patient) search();
  };
  rx.enter.init = function () {
    $('pt-q').addEventListener('input', MFH.debounce(search, 250));
    $('attest').addEventListener('change', function () { S.attest = $('attest').checked; rx.dirty(); rx.loadEligibility(); });
    $('s1-next').addEventListener('click', function () {
      var btn = $('s1-next');
      MFH.busy(btn, true);
      rx.ensureDraft().then(function () { rx.go(2); }, function (err) { rx.alert(err.message); }).then(function () { MFH.busy(btn, false); renderPanel(); });
    });
    if (S.patient) rx.loadEligibility();
  };
})();
