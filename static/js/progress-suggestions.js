// Loads the AI suggestions for /patient/progress after the page has rendered. The page never waits on this.
// Server text is untrusted: nodes are built with textContent only.
(function () {
  'use strict';
  var host = document.getElementById('suggestions');
  if (!host) return;

  function note(text) {
    host.textContent = '';
    var p = document.createElement('p');
    p.className = 'muted';
    p.textContent = text;
    host.appendChild(p);
    host.setAttribute('aria-busy', 'false');
  }

  function column(title, items) {
    var box = document.createElement('div');
    var h = document.createElement('h3');
    h.className = 'pt-title';
    h.textContent = title;
    var ul = document.createElement('ul');
    ul.className = 'rows';
    items.forEach(function (it) {
      if (!it || typeof it !== 'object') return;
      var li = document.createElement('li');
      var div = document.createElement('div');
      var strong = document.createElement('strong');
      strong.textContent = String(it.title || '');
      var desc = document.createElement('div');
      desc.className = 'muted';
      desc.textContent = String(it.desc || '');
      div.append(strong, desc);
      li.appendChild(div);
      ul.appendChild(li);
    });
    box.append(h, ul);
    return box;
  }

  function show(d) {
    var actions = Array.isArray(d.actions) ? d.actions : [];
    var insights = Array.isArray(d.insights) ? d.insights : [];
    if (d.status !== 'ok' || !(actions.length || insights.length)) { note(d.message || 'Suggestions are not available right now.'); return; }
    host.textContent = '';
    var grid = document.createElement('div');
    grid.className = 'grid gap-6 md:grid-cols-2';
    if (actions.length) grid.appendChild(column('Things to try', actions));
    if (insights.length) grid.appendChild(column('Observations', insights));
    host.appendChild(grid);
    host.setAttribute('aria-busy', 'false');
  }

  // A little longer than the server cap (8 s) so the server's own fallback text normally arrives first.
  var ctl = typeof AbortController === 'function' ? new AbortController() : null;
  var timer = ctl ? setTimeout(function () { ctl.abort(); }, 12000) : null;
  fetch(host.getAttribute('data-src'), { credentials: 'same-origin', headers: { 'Accept': 'application/json' }, signal: ctl ? ctl.signal : undefined })
    .then(function (res) { if (!res.ok) throw new Error('http'); return res.json(); })
    .then(show)
    .catch(function () { note('Suggestions are not available right now. Your scores and goals above are up to date.'); })
    .then(function () { if (timer) clearTimeout(timer); });
})();
