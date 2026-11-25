// PHQ-9 / GAD-7 screening flow for /patient/assessment.
// Questions come from /static/questions.json. The server recomputes the score from the answers and returns
// {success, score, band, crisis, helplines, ai_insights}. When crisis is true (PHQ-9 item 9 or a severe score)
// the crisis banner with the helplines is shown first. No points or streaks are attached to any score.
(function () {
  'use strict';
  if (window.__assessmentFixesInit) return;

  var $ = function (id) { return document.getElementById(id); };
  var picker = $('assessment-picker'), panel = $('assessmentModal');
  // base.html loads this file before PT exists: bail out WITHOUT the init flag so the later include still wires the buttons.
  if (!picker || !panel || !window.PT) return;
  window.__assessmentFixesInit = true;

  var QUESTIONS_URL = picker.getAttribute('data-questions-url') || '/static/questions.json';
  var MAX = { 'PHQ-9': 27, 'GAD-7': 21 };
  var STEM = 'Over the last 2 weeks, how often have you been bothered by:';
  var EXPLAIN = {
    'minimal': 'Few or no symptoms were reported over the last two weeks.',
    'mild': 'Some symptoms were reported. Notice how you feel over the next few weeks, and repeat the screening if things change.',
    'moderate': 'Symptoms that may be affecting your daily life were reported. Consider speaking with your college counsellor or a doctor.',
    'moderately severe': 'Symptoms that are likely affecting your daily life were reported. Please book a session with a counsellor or doctor soon.',
    'severe': 'Many symptoms were reported. Please book a session with a counsellor or doctor soon, and reach out to someone you trust.'
  };
  var BADGE = { 'minimal': 'success', 'mild': 'info', 'moderate': 'warning', 'moderately severe': 'danger', 'severe': 'danger' };

  var state = { all: null, key: null, def: null, phase: 'standard', i: 0, standard: [], contextual: {}, saving: false };

  function setHidden(el, hidden) { if (el) el.hidden = !!hidden; }
  function showError(msg) {
    var el = $('assessment-error');
    el.textContent = msg || '';
    el.hidden = !msg;
  }

  function list() {
    return state.phase === 'standard' ? state.def.questions : (state.def.contextual_questions || []);
  }
  function hasFollowUp() { return !!(state.def.contextual_questions && state.def.contextual_questions.length); }
  function isLast() { return state.i === list().length - 1; }
  function hasAnswers() {
    return state.standard.some(function (v) { return v !== undefined; }) || Object.keys(state.contextual).length > 0;
  }

  function loadQuestions() {
    if (state.all) return Promise.resolve(state.all);
    return fetch(QUESTIONS_URL, { credentials: 'same-origin' }).then(function (res) {
      if (!res.ok) throw new Error('http ' + res.status);
      return res.json();
    }).then(function (json) { state.all = json; return json; });
  }

  function start(key) {
    setHidden($('assessment-loading'), false);
    showError('');
    setHidden(panel, false);
    setHidden(picker, true);
    setHidden($('assessment-form'), true);
    loadQuestions().then(function (all) {
      var def = all[key];
      if (!def) throw new Error('unknown type');
      state.key = key; state.def = def; state.phase = 'standard'; state.i = 0; state.standard = []; state.contextual = {};
      $('assessmentTitle').textContent = def.title;
      setHidden($('assessment-loading'), true);
      setHidden($('assessment-form'), false);
      render(true);
    }).catch(function () {
      setHidden($('assessment-loading'), true);
      showError('Could not load the questions. Check your connection and try again.');
      setHidden(picker, false);
    });
  }

  function choice(type, name, value, label, checked) {
    var lab = document.createElement('label');
    lab.className = 'choice';
    var input = document.createElement('input');
    input.type = type; input.name = name; input.value = value; input.checked = !!checked;
    var span = document.createElement('span');
    span.textContent = label;
    lab.append(input, span);
    return lab;
  }

  function render(moveFocus) {
    var q = list()[state.i];
    var n = list().length;
    var standard = state.phase === 'standard';
    showError('');

    $('assessment-progress').textContent = standard
      ? 'Question ' + (state.i + 1) + ' of ' + n
      : 'Follow-up ' + (state.i + 1) + ' of ' + n + ' (optional)';
    $('assessment-stem').textContent = q.type === 'scale' ? STEM : '';
    $('assessment-question').textContent = q.text;
    setHidden($('item9-note'), q.id !== 'phq9_9');

    var box = $('assessment-options');
    box.textContent = '';
    if (q.type === 'scale') {
      q.options.forEach(function (opt, idx) {
        var lab = choice('radio', 'answer', idx, (idx + 1) + '. ' + opt, state.standard[state.i] === idx);
        lab.firstChild.addEventListener('change', function () { state.standard[state.i] = idx; showError(''); });
        box.appendChild(lab);
      });
    } else if (q.type === 'multiple-choice') {
      var picked = state.contextual[q.id] || [];
      q.options.forEach(function (opt) {
        var lab = choice('checkbox', 'answer', opt, opt, picked.indexOf(opt) > -1);
        lab.firstChild.addEventListener('change', function (e) {
          var cur = (state.contextual[q.id] || []).slice();
          var at = cur.indexOf(opt);
          if (e.target.checked && at < 0) cur.push(opt);
          if (!e.target.checked && at > -1) cur.splice(at, 1);
          if (cur.length) state.contextual[q.id] = cur; else delete state.contextual[q.id];
        });
        box.appendChild(lab);
      });
    } else {
      var ta = document.createElement('textarea');
      ta.className = 'textarea';
      ta.rows = 4; ta.maxLength = 1000; ta.name = 'answer';
      ta.setAttribute('aria-labelledby', 'assessment-question');
      ta.value = state.contextual[q.id] || '';
      ta.addEventListener('input', PT.debounce(function () {
        if (ta.value.trim()) state.contextual[q.id] = ta.value; else delete state.contextual[q.id];
      }, 200));
      ta.addEventListener('blur', function () { if (ta.value.trim()) state.contextual[q.id] = ta.value; });
      box.appendChild(ta);
    }

    var back = $('prevBtn'), next = $('nextBtn'), alt = $('altBtn');
    back.disabled = standard && state.i === 0;
    var last = isLast();
    if (standard) {
      next.textContent = last ? 'Save and see result' : 'Next';
      next.setAttribute('data-action', last ? 'save' : 'next');
      alt.hidden = !(last && hasFollowUp());
      alt.textContent = 'Answer optional follow-up questions';
      alt.setAttribute('data-action', 'followup');
    } else {
      next.textContent = last ? 'Save and see result' : 'Next';
      next.setAttribute('data-action', last ? 'save' : 'next');
      alt.hidden = last;
      alt.textContent = 'Skip the rest and save';
      alt.setAttribute('data-action', 'save');
    }
    if (moveFocus) $('assessment-legend').focus();
  }

  function advance(action) {
    if (state.saving) return;
    if (state.phase === 'standard' && action !== 'back' && state.standard[state.i] === undefined) {
      showError('Choose an answer to continue.');
      var first = $('assessment-options').querySelector('input');
      if (first) first.focus();
      return;
    }
    if (action === 'save') { save(); return; }
    if (action === 'followup') { state.phase = 'context'; state.i = 0; render(true); return; }
    if (action === 'back') {
      if (state.i > 0) state.i--;
      else if (state.phase === 'context') { state.phase = 'standard'; state.i = state.def.questions.length - 1; }
      render(true);
      return;
    }
    state.i++; // next
    render(true);
  }

  function save() {
    // Every standard item must be answered; the server recomputes the score from these and ignores any client score.
    var n = state.def.questions.length;
    for (var k = 0; k < n; k++) {
      if (state.standard[k] === undefined) {
        state.phase = 'standard'; state.i = k; render(true);
        showError('Answer this question before saving.');
        return;
      }
    }
    state.saving = true;
    showError('');
    var next = $('nextBtn');
    var label = next.textContent;
    next.disabled = true; next.setAttribute('aria-busy', 'true'); next.textContent = 'Saving';
    var payload = {
      assessment_type: state.key,
      responses: state.standard.slice(0, n),
      contextual_responses: state.contextual
    };
    PT.api('/patient/api/save-assessment', { method: 'POST', json: payload }).then(function (r) {
      var d = r.data;
      if (d && d.crisis) {
        // A crisis payload is always shown, whatever the HTTP status or `success` says.
        if (r.ok && d.success) { showResult(d); return; }
        crisisBanner(d.helplines).focus();
        fillInsights(d.ai_insights, false);
        failSave('Your result could not be saved. Your answers are still here, so try saving again.');
        return;
      }
      if (r.ok && d && d.success) { showResult(d); return; }
      failSave((d && d.message) || 'Could not save your screening (error ' + r.status + '). Your answers are still here, so try again.');
    }).catch(function () {
      failSave('Could not reach the server. Your answers are still here, so try again.');
    }).then(function () {
      state.saving = false;
      next.disabled = false; next.removeAttribute('aria-busy'); next.textContent = label;
    });
  }

  // Save failed: keep the answers, say so, and never hide emergency help when item 9 was positive.
  function failSave(msg) {
    showError(msg);
    PT.toast(msg, 'error');
    var item9 = state.key === 'PHQ-9' && typeof state.standard[8] === 'number' && state.standard[8] > 0;
    if (item9 && !$('crisis-card')) crisisBanner([]);
  }

  function crisisBanner(helplines) {
    var slot = $('crisis-slot');
    slot.textContent = '';
    var b = document.createElement('div');
    b.className = 'crisis-banner';
    b.id = 'crisis-card';
    b.setAttribute('role', 'alert');
    b.tabIndex = -1;
    var h = document.createElement('h2');
    h.textContent = 'You are not alone';
    var p = document.createElement('p');
    p.textContent = 'Your answers suggest you may be going through a very hard time. Please talk to someone now. These services are free:';
    var ul = document.createElement('ul');
    ul.className = 'helpline-list';
    if (!Array.isArray(helplines) || !helplines.length) {
      var fb = document.querySelector('#helplines-fallback ul');
      if (fb) ul = fb.cloneNode(true); // server-rendered list from utils/helplines.py
      helplines = [];
    }
    helplines.forEach(function (hl) {
      var li = document.createElement('li');
      var tel = String(hl.tel || '').replace(/[^0-9]/g, '');
      var a = document.createElement(tel ? 'a' : 'span');
      if (tel) a.href = 'tel:' + tel;
      a.textContent = hl.name + ': ' + hl.number;
      li.appendChild(a);
      li.append(' (' + hl.hours + ')');
      ul.appendChild(li);
    });
    b.append(h, p, ul, ...Array.from(document.querySelectorAll('#helplines-fallback p'), function (n) { return n.cloneNode(true); })); // safety plan link: an extra line after the helplines
    slot.appendChild(b);
    return b;
  }

  // AI text is untrusted: build nodes with textContent, never innerHTML.
  function fillList(el, items) {
    el.textContent = '';
    items.forEach(function (t) {
      var li = document.createElement('li');
      li.textContent = String(t);
      el.appendChild(li);
    });
  }

  function fillInsights(ins, generated) {
    ins = ins || {};
    var box = $('aiInsightsContent');
    if (ins.summary || (ins.recommendations || []).length || (ins.resources || []).length) {
      $('aiSummary').textContent = ins.summary || '';
      fillList($('aiRecommendations'), Array.isArray(ins.recommendations) ? ins.recommendations : []);
      fillList($('aiResources'), Array.isArray(ins.resources) ? ins.resources : []);
      setHidden(box, false);
      setHidden($('aiInsightsNote'), !generated);
    }
  }

  function showResult(d) {
    setHidden(panel, true);
    setHidden(picker, true);
    var res = $('assessment-result');
    setHidden(res, false);

    var banner = d.crisis ? crisisBanner(d.helplines) : ($('crisis-slot').textContent = '', null);
    var band = String(d.band || '').toLowerCase();
    $('result-title').textContent = state.def.title;
    $('result-score').textContent = String(d.score);
    $('result-max').textContent = 'of ' + (MAX[state.key] || '') + ' on the ' + state.key;
    var badge = $('result-band');
    badge.className = 'badge badge-' + (BADGE[band] || 'neutral');
    badge.textContent = band ? band.charAt(0).toUpperCase() + band.slice(1) : 'n/a';
    $('result-explain').textContent = EXPLAIN[band] || '';

    fillInsights(d.ai_insights, !!d.ai_insights_generated);
    (banner || $('result-heading')).focus();
  }

  // Wiring
  document.addEventListener('click', function (e) {
    var startBtn = e.target.closest && e.target.closest('.start-assessment-btn');
    if (startBtn && picker.contains(startBtn)) {
      e.preventDefault();
      start(startBtn.getAttribute('data-assessment-type'));
    }
  });

  $('assessment-form').addEventListener('submit', function (e) {
    e.preventDefault();
    advance($('nextBtn').getAttribute('data-action'));
  });
  $('prevBtn').addEventListener('click', function () { advance('back'); });
  $('altBtn').addEventListener('click', function () { advance($('altBtn').getAttribute('data-action')); });

  $('cancelBtn').addEventListener('click', function () {
    function leave() {
      setHidden(panel, true);
      setHidden(picker, false);
    }
    if (!hasAnswers()) { leave(); return; }
    PT.ask({ title: 'Stop this screening?', message: 'Your answers have not been saved.', confirmText: 'Stop screening', danger: true })
      .then(function (ok) { if (ok) leave(); });
  });

  $('again-btn').addEventListener('click', function () { window.location.reload(); });

  // Keys 1 to 4 pick the matching answer on scale questions (focus sits on the question after Next, so listen on the form).
  $('assessment-form').addEventListener('keydown', function (e) {
    var q = list()[state.i];
    if (!q || q.type !== 'scale' || (e.target.tagName === 'TEXTAREA') || e.ctrlKey || e.metaKey || e.altKey) return;
    var idx = parseInt(e.key, 10) - 1;
    var inputs = $('assessment-options').querySelectorAll('input[type="radio"]');
    if (idx >= 0 && idx < inputs.length) {
      inputs[idx].checked = true;
      inputs[idx].dispatchEvent(new Event('change', { bubbles: true }));
      inputs[idx].focus();
    }
  });
})();
