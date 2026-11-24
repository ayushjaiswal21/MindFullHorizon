/* Screen time page: saves the daily entry, then redraws the chart, table and latest values.
   Entries come from the #screen-time-data JSON block (newest first). The chart is inline SVG, no library. */
(function () {
  'use strict';
  var root = document.getElementById('detox-root');
  if (!root || window.__mfhDetox) return;
  window.__mfhDetox = true;

  var $ = function (id) { return document.getElementById(id); };
  var form = $('digital-detox-form'), msg = $('form-message'), chartHost = $('screen-time-chart');
  var SVG = 'http://www.w3.org/2000/svg';
  var logs = [];
  try { logs = JSON.parse($('screen-time-data').textContent) || []; } catch (e) { logs = []; }
  if (!Array.isArray(logs)) logs = [];

  function svg(name, attrs) {
    var n = document.createElementNS(SVG, name);
    Object.keys(attrs || {}).forEach(function (k) { n.setAttribute(k, attrs[k]); });
    return n;
  }
  function cap(s) { return s ? s.charAt(0).toUpperCase() + s.slice(1) : 'n/a'; }

  function drawChart() {
    chartHost.textContent = '';
    if (!logs.length) return;
    var data = logs.slice().sort(function (a, b) { return a.date < b.date ? -1 : 1; });
    var W = 640, H = 220, m = { l: 34, r: 10, t: 10, b: 26 };
    var iw = W - m.l - m.r, ih = H - m.t - m.b;
    var top = Math.max(8, Math.ceil(Math.max.apply(null, data.map(function (d) { return d.hours; })) / 2) * 2);
    var n = data.length;
    function x(i) { return m.l + (n < 2 ? iw / 2 : (iw * i) / (n - 1)); }
    function y(v) { return m.t + ih - (v / top) * ih; }
    var s = svg('svg', { viewBox: '0 0 ' + W + ' ' + H, 'class': 'wl-chart', role: 'img',
      'aria-label': 'Line chart of daily screen time in hours. The table below lists the same values.' });
    for (var t = 0; t <= 4; t++) {
      var v = (top * t) / 4;
      s.appendChild(svg('line', { x1: m.l, x2: W - m.r, y1: y(v), y2: y(v), 'class': t === 0 ? 'axis' : 'grid' }));
      var tx = svg('text', { x: m.l - 6, y: y(v) + 4, 'text-anchor': 'end' });
      tx.textContent = String(v);
      s.appendChild(tx);
    }
    [0, n - 1].forEach(function (i, k) {
      if (k === 1 && n === 1) return;
      var lx = svg('text', { x: x(i), y: H - 6, 'text-anchor': k === 0 ? (n === 1 ? 'middle' : 'start') : 'end' });
      lx.textContent = data[i].date;
      s.appendChild(lx);
    });
    var d = '';
    data.forEach(function (p, i) { d += (i ? 'L' : 'M') + x(i).toFixed(1) + ' ' + y(p.hours).toFixed(1) + ' '; });
    s.appendChild(svg('path', { d: d, 'class': 'line' }));
    data.forEach(function (p, i) { s.appendChild(svg('circle', { cx: x(i), cy: y(p.hours), r: 3, 'class': 'dot' })); });
    chartHost.appendChild(s);
  }

  function drawTable() {
    var body = $('detox-rows');
    body.textContent = '';
    logs.forEach(function (l) {
      var tr = document.createElement('tr');
      [l.date, String(l.hours), l.academic_score === null || l.academic_score === undefined ? 'n/a' : String(l.academic_score), cap(l.social_interactions)]
        .forEach(function (t) { var c = document.createElement('td'); c.textContent = t; tr.appendChild(c); });
      body.appendChild(tr);
    });
    var any = logs.length > 0;
    $('detox-empty').hidden = any;
    $('detox-table-wrap').hidden = !any;
    var avg = any ? Math.round((logs.reduce(function (a, l) { return a + l.hours; }, 0) / logs.length) * 10) / 10 : 0;
    $('detox-average').textContent = any ? 'Average of your last ' + logs.length + (logs.length === 1 ? ' entry: ' : ' entries: ') + avg + ' hours a day.' : '';
  }

  function say(text, kind) {
    msg.textContent = '';
    if (!text) return;
    var p = document.createElement('p');
    p.className = kind === 'error' ? 'alert alert-danger' : 'success-text';
    p.textContent = text;
    msg.appendChild(p);
  }

  function upsert(entry) {
    logs = logs.filter(function (l) { return l.date !== entry.date; });
    logs.unshift(entry);
    logs.sort(function (a, b) { return a.date < b.date ? 1 : -1; });
    logs = logs.slice(0, 30);
  }

  if (window.WL) WL.guardRanges(form);

  form.addEventListener('submit', function (e) {
    var rangeBad = e.defaultPrevented; // WL.guardRanges runs first and blocks out-of-range numbers
    e.preventDefault();
    if (rangeBad) return;
    if (window.MFH && typeof MFH.validateForm === 'function' && !MFH.validateForm(form)) return;
    var btn = $('detox-submit');
    var fd = new FormData(form);
    var payload = { screen_time: fd.get('screen_time'), academic_score: fd.get('academic_score'), social_interactions: fd.get('social_interactions') };
    btn.disabled = true;
    btn.setAttribute('aria-busy', 'true');
    say('');
    fetch('/patient/api/log-digital-detox', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'X-Requested-With': 'XMLHttpRequest', 'Content-Type': 'application/json', 'X-CSRFToken': fd.get('csrf_token') || (window.WL ? WL.csrf() : '') },
      body: JSON.stringify(payload)
    }).then(function (res) {
      return res.json().catch(function () { return null; }).then(function (d) { return { ok: res.ok, status: res.status, d: d }; });
    }).then(function (r) {
      if (r.ok && r.d && r.d.success) {
        var ai = r.d.ai_analysis || {};
        $('ai-score').textContent = ai.ai_score || 'n/a';
        $('ai-suggestion').textContent = ai.ai_suggestion || 'No suggestion available.';
        $('last-analysis-time').textContent = new Date().toLocaleTimeString();
        $('last-analysis').hidden = false;
        if (r.d.log) {
          upsert(r.d.log);
          $('current-academic-score').textContent = r.d.log.academic_score === null || r.d.log.academic_score === undefined ? 'n/a' : String(r.d.log.academic_score);
          $('current-social-level').textContent = cap(r.d.log.social_interactions);
          drawChart();
          drawTable();
        }
        form.reset();
        say('Saved. Today\'s entry is updated.', 'success');
        if (window.WL) WL.toast('Saved.', 'success');
      } else if (r.status === 401 || r.status === 403) {
        say('Your session has expired. Log in again, then save.', 'error');
      } else if (r.status === 429) {
        say('Too many saves in a short time. Wait a minute and try again.', 'error');
      } else {
        say((r.d && r.d.message) || 'Could not save. Check the numbers and try again.', 'error');
      }
    }).catch(function () {
      say('The network seems to be down. Check your connection and try again.', 'error');
    }).then(function () {
      btn.disabled = false;
      btn.removeAttribute('aria-busy');
    });
  });

  drawChart();
})();
