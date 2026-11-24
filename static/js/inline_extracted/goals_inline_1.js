// Goals page. Talks to /patient/api/goals (GET, POST) and /patient/api/goals/<id> (PUT, DELETE).
// The server filters by the session user. Goal text is untrusted: nodes are built with textContent.
document.addEventListener('DOMContentLoaded', function () {
  if (!window.PT) return;
  var $ = function (id) { return document.getElementById(id); };
  var list = $('goals-container');
  var emptyBox = $('empty-state');

  var PRIORITY = { high: 'danger', medium: 'warning', low: 'neutral' };
  var STATUS = { active: 'info', completed: 'success', paused: 'neutral' };

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    return n;
  }
  function badge(kind, text) { return el('span', 'badge badge-' + kind, text); }
  function nice(s) { return String(s || '').replace(/_/g, ' ').replace(/^./, function (c) { return c.toUpperCase(); }); }
  function day(iso) {
    var d = new Date(iso + 'T12:00:00');
    return isNaN(d) ? iso : d.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
  }
  function fieldError(id, msg) {
    var e = $(id);
    e.textContent = msg || '';
    e.hidden = !msg;
  }
  function open(dlg) { if (typeof dlg.showModal === 'function') dlg.showModal(); else dlg.setAttribute('open', ''); }
  function close(dlg) { if (typeof dlg.close === 'function') dlg.close(); else dlg.removeAttribute('open'); }

  function card(goal) {
    var c = el('article', 'card');
    var body = el('div', 'card-body');
    body.appendChild(el('h2', 'pt-title', goal.title));
    if (goal.description) body.appendChild(el('p', 'pt-sub', goal.description));
    var tags = el('p', 'mt-3 flex gap-2 flex-wrap');
    tags.append(badge('neutral', nice(goal.category)), badge(PRIORITY[goal.priority] || 'neutral', nice(goal.priority) + ' priority'), badge(STATUS[goal.status] || 'neutral', nice(goal.status)));
    body.appendChild(tags);

    if (goal.target_value) {
      var unit = goal.unit ? ' ' + goal.unit : '';
      var pct = Math.max(0, Math.min(100, Math.round(goal.progress_percentage || 0)));
      var wrap = el('div', 'mt-3');
      wrap.appendChild(el('p', 'muted', (goal.current_value || 0) + unit + ' of ' + goal.target_value + unit + ' (' + pct + '%)'));
      var meter = el('progress', 'meter');
      meter.max = 100; meter.value = pct;
      meter.setAttribute('aria-label', 'Progress on ' + goal.title);
      wrap.appendChild(meter);
      body.appendChild(wrap);
    }
    body.appendChild(el('p', 'pt-sub', (goal.target_date ? 'Target: ' + day(goal.target_date) : 'No target date') + (goal.created_at ? '. Added ' + day(goal.created_at) + '.' : '')));

    var actions = el('div', 'flex gap-2 mt-4 flex-wrap');
    var upd = el('button', 'btn btn-secondary btn-sm', 'Update progress');
    upd.type = 'button';
    upd.setAttribute('aria-label', 'Update progress on ' + goal.title);
    upd.addEventListener('click', function () {
      $('progress-goal-id').value = goal.id;
      $('current-value').value = goal.current_value || 0;
      $('goal-status').value = goal.status;
      fieldError('current-value-error', '');
      fieldError('progress-form-error', '');
      open($('progress-modal'));
    });
    var del = el('button', 'btn btn-danger btn-sm', 'Delete');
    del.type = 'button';
    del.setAttribute('aria-label', 'Delete goal ' + goal.title);
    del.addEventListener('click', function () { remove(goal); });
    actions.append(upd, del);
    body.appendChild(actions);
    c.appendChild(body);
    return c;
  }

  function show(goals) {
    list.textContent = '';
    list.removeAttribute('aria-busy');
    emptyBox.hidden = goals.length > 0;
    goals.forEach(function (g) { list.appendChild(card(g)); });
  }

  function load() {
    PT.api('/patient/api/goals').then(function (r) {
      if (!(r.ok && r.data && r.data.success)) throw new Error('bad response');
      $('goals-error').hidden = true;
      show(r.data.goals || []);
    }).catch(function () {
      list.textContent = '';
      list.removeAttribute('aria-busy');
      var e = $('goals-error');
      e.textContent = 'Could not load your goals. Reload the page to try again. If you were signed out, sign in again.';
      e.hidden = false;
    });
  }

  function remove(goal) {
    PT.ask({ title: 'Delete this goal?', message: goal.title + ' will be removed. This cannot be undone.', confirmText: 'Delete goal', danger: true }).then(function (ok) {
      if (!ok) return;
      PT.api('/patient/api/goals/' + encodeURIComponent(goal.id), { method: 'DELETE' }).then(function (r) {
        if (r.ok && r.data && r.data.success) { PT.toast('Goal deleted.', 'success'); load(); }
        else PT.toast((r.data && r.data.message) || 'Could not delete the goal.', 'error');
      }).catch(function () { PT.toast('Could not reach the server. Try again.', 'error'); });
    });
  }

  function busy(btn, on) {
    if (on) { btn.dataset.label = btn.textContent; btn.disabled = true; btn.setAttribute('aria-busy', 'true'); btn.textContent = btn.getAttribute('data-loading-text') || 'Saving'; }
    else { btn.disabled = false; btn.removeAttribute('aria-busy'); btn.textContent = btn.dataset.label || btn.textContent; }
  }

  function openAdd() {
    $('goal-form').reset();
    fieldError('goal-title-error', '');
    fieldError('goal-form-error', '');
    open($('goal-modal'));
    $('goal-title').focus();
  }

  $('add-goal-btn').addEventListener('click', openAdd);
  $('empty-add-btn').addEventListener('click', openAdd);
  document.querySelectorAll('[data-close]').forEach(function (b) {
    b.addEventListener('click', function () { close($(b.getAttribute('data-close'))); });
  });

  $('goal-title').addEventListener('input', PT.debounce(function () {
    if ($('goal-title').value.trim()) fieldError('goal-title-error', '');
  }, 150));

  $('goal-form').addEventListener('submit', function (e) {
    e.preventDefault();
    var form = e.target;
    var title = $('goal-title');
    if (!title.value.trim()) {
      title.setAttribute('aria-invalid', 'true');
      fieldError('goal-title-error', 'Enter a title for the goal.');
      title.focus();
      return;
    }
    title.removeAttribute('aria-invalid');
    var btn = form.querySelector('button[type="submit"]');
    busy(btn, true);
    PT.api('/patient/api/goals', { method: 'POST', json: Object.fromEntries(new FormData(form).entries()) }).then(function (r) {
      if (r.ok && r.data && r.data.success) { close($('goal-modal')); PT.toast('Goal added.', 'success'); load(); }
      else fieldError('goal-form-error', (r.data && r.data.message) || 'Could not save the goal. Try again.');
    }).catch(function () {
      fieldError('goal-form-error', 'Could not reach the server. Check your connection and try again.');
    }).then(function () { busy(btn, false); });
  });

  $('progress-form').addEventListener('submit', function (e) {
    e.preventDefault();
    var form = e.target;
    var cur = $('current-value');
    if (cur.value === '' || isNaN(Number(cur.value))) {
      cur.setAttribute('aria-invalid', 'true');
      fieldError('current-value-error', 'Enter a number.');
      cur.focus();
      return;
    }
    cur.removeAttribute('aria-invalid');
    var btn = form.querySelector('button[type="submit"]');
    busy(btn, true);
    var id = $('progress-goal-id').value;
    PT.api('/patient/api/goals/' + encodeURIComponent(id), { method: 'PUT', json: Object.fromEntries(new FormData(form).entries()) }).then(function (r) {
      if (r.ok && r.data && r.data.success) { close($('progress-modal')); PT.toast('Progress saved.', 'success'); load(); }
      else fieldError('progress-form-error', (r.data && r.data.message) || 'Could not save progress. Try again.');
    }).catch(function () {
      fieldError('progress-form-error', 'Could not reach the server. Check your connection and try again.');
    }).then(function () { busy(btn, false); });
  });

  load();
});
