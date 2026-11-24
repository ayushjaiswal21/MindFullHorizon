// Dashboard: recent mood chart, loaded from GET /api/mood (the server returns only the session user's entries).
document.addEventListener('DOMContentLoaded', function () {
  var host = document.getElementById('mood-trend');
  if (!host || !window.PT) return;

  function parse(iso) {
    var s = String(iso || '');
    return new Date(/(Z|[+-]\d\d:\d\d)$/.test(s) ? s : s + 'Z'); // stored as naive UTC
  }
  function short(d) {
    return d.toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
  }

  function empty() {
    host.textContent = '';
    var box = document.createElement('div');
    box.className = 'empty-state';
    var h = document.createElement('h3');
    h.textContent = 'No mood entries yet';
    var p = document.createElement('p');
    p.textContent = 'Log how you feel today to start your history.';
    box.append(h, p);
    host.appendChild(box);
  }

  function draw(moods) {
    var rows = moods.filter(function (m) { return typeof m.mood === 'number'; }).slice(-14);
    if (!rows.length) { empty(); return; }
    var labels = rows.map(function (m) { return short(parse(m.created_at)); });
    PT.lineChart(host, {
      labels: labels,
      series: [{ values: rows.map(function (m) { return m.mood; }), cls: 'a' }],
      min: 1, max: 10, ticks: 3, height: 200,
      label: 'Mood from 1 to 10 over your last ' + rows.length + ' entries'
    });
    var note = document.createElement('p');
    note.className = 'help';
    var last = rows[rows.length - 1];
    note.textContent = 'Latest: ' + last.mood + ' of 10 on ' + labels[labels.length - 1] + '. ' + rows.length + (rows.length === 1 ? ' entry' : ' entries') + ' shown.';
    host.appendChild(note);
  }

  function load() {
    PT.api(host.getAttribute('data-src')).then(function (r) {
      if (r.ok && r.data && Array.isArray(r.data.moods)) { draw(r.data.moods); return; }
      throw new Error('bad response');
    }).catch(function () {
      host.textContent = '';
      var p = document.createElement('p');
      p.className = 'text-danger';
      p.textContent = 'Could not load your mood history. Reload the page to try again.';
      host.appendChild(p);
    });
  }

  load();
  document.addEventListener('mood:saved', load);
});
